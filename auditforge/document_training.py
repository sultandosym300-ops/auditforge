"""Reward-only CPU document-policy training with explicit optimizer diagnostics."""
import copy
import json
import math
import random
import statistics
import time
from .document_policy import Network, FEATURES, KINDS, CATEGORIES, investigate, objective_gradient
from .training import episode_seed


def normalize_advantages(values):
 if not values:return []
 mean=statistics.mean(values);variance=statistics.mean((v-mean)**2 for v in values)
 if variance<1e-12:return [0.]*len(values)
 return [(v-mean)/math.sqrt(variance+1e-8) for v in values]


def actor_critic_targets(reward,values):
 """Undiscounted Monte Carlo targets; values read before any critic update."""
 return [reward-v for v in values],[reward]*len(values)


class DocumentTrainer:
 def __init__(self,seed=1202201,budget=20,algorithm='reinforce',learning_rate=.03,*,family='procurement',architecture='linear',entropy=0.,normalize_advantage=False,hidden=8,entropy_coefficient=None):
  entropy=entropy if entropy_coefficient is None else entropy_coefficient
  if (type(seed) is not int or not 0<=seed<2**128 or type(budget) is not int or not 2<=budget<=100 or algorithm not in ('reinforce','actor_critic') or family not in ('procurement','service_milestone') or type(normalize_advantage) is not bool or type(hidden) is not int or hidden!=8):raise ValueError('Invalid document trainer configuration')
  for v,low,high in ((learning_rate,0,.5),(entropy,-1e-12,.5)):
   if type(v) not in (float,int) or not math.isfinite(v) or not low<v<=high:raise ValueError('Invalid learning rate/entropy')
  self.seed,self.budget,self.algorithm,self.learning_rate=seed,budget,algorithm,learning_rate
  self.family,self.entropy,self.normalize_advantage=family,entropy,normalize_advantage
  self.model=Network(architecture,seed=seed);self.critic=[0.]*len(FEATURES)
  self.episodes=0;self.optimizer_steps=0;self.baseline=0.;self.history=[];self.pending=[]
  self.blind_statistics={kind:[0.,0.] for kind in KINDS}

 @property
 def network(self):return self.model

 @staticmethod
 def config(index,family='procurement'):
  return dict(profile='investigation_v2',family=family,clean=index%5==0)

 def _update(self):
  if not self.pending:return
  previous=list(self.model.parameters);trajectory_advantages=[x['reward']-x['baseline'] for x in self.pending]
  if self.normalize_advantage:trajectory_advantages=normalize_advantages(trajectory_advantages)
  gradient=[0.]*len(previous);critic_gradient=[0.]*len(self.critic);adv_values=[];entropy_values=[];trajectory_gradients=[]
  for episode,a in zip(self.pending,trajectory_advantages):
   trajectory_gradient=[0.]*len(previous)
   states=[[statistics.mean(x[j] for x in decision['features']) for j in range(len(FEATURES))] for decision in episode['decisions']]
   values=[sum(w*x for w,x in zip(self.critic,state)) for state in states]
   advantages,targets=actor_critic_targets(episode['reward'],values)
   for i,decision in enumerate(episode['decisions']):
    advantage=advantages[i] if self.algorithm=='actor_critic' else a
    g=objective_gradient(self.model,decision['features'],decision['chosen'],advantage,self.entropy)
    for j,v in enumerate(g):gradient[j]+=v/len(self.pending);trajectory_gradient[j]+=v
    if self.algorithm=='actor_critic':
     for j,x in enumerate(states[i]):critic_gradient[j]+=(targets[i]-values[i])*x/max(1,len(states))/len(self.pending)
    adv_values.append(advantage);entropy_values.append(decision['entropy'])
   trajectory_gradients.append(trajectory_gradient)
  # Clip the aggregate trajectory gradient by norm, not independently per decision.
  norm=math.sqrt(sum(g*g for g in gradient));scale=min(1.,5/max(1e-12,norm))
  self.model.parameters=[max(-30.,min(30.,w+self.learning_rate*g*scale)) for w,g in zip(previous,gradient)]
  self.critic=[max(-10.,min(10.,w+.05*g)) for w,g in zip(self.critic,critic_gradient)]
  self.optimizer_steps+=1
  diagnostics=dict(gradient_norm=norm,advantage_variance=statistics.pvariance(adv_values) if len(adv_values)>1 else 0.,gradient_variance=sum(statistics.pvariance(g[j] for g in trajectory_gradients) for j in range(len(previous))) if len(trajectory_gradients)>1 else 0.,mean_entropy=statistics.mean(entropy_values) if entropy_values else 0.,optimizer_steps=self.optimizer_steps,weight_change=math.sqrt(sum((a-b)**2 for a,b in zip(previous,self.model.parameters))))
  if self.history:self.history[-1].update(diagnostics,weight_norm=math.sqrt(sum(w*w for w in self.model.parameters)))
  self.pending=[]

 def flush(self):
  """Apply a partial final batch at an explicit training/checkpoint boundary."""
  self._update()

 def train_episode(self):
  from .env import Session
  index=self.episodes;session=Session();initial,_=session.reset(episode_seed(self.seed,'document-train',index),self.config(index,self.family),'train')
  rng=random.Random(episode_seed(self.seed,'document-actions',index));rng.training=True
  started=time.perf_counter();previous=list(self.model.parameters)
  result=investigate(session.step,initial,model=self.model,budget=self.budget,rng=rng)
  reward=result['terminal'][1]
  self.pending.append(dict(reward=reward,baseline=self.baseline,decisions=result['decisions']))
  self.baseline=.95*self.baseline+.05*reward;self.episodes+=1
  row=dict(episode=self.episodes,optimizer_steps=self.optimizer_steps,steps=session.steps,inspection_steps=session.steps-1,seconds=time.perf_counter()-started,weight_norm=math.sqrt(sum(w*w for w in self.model.parameters)),weight_change=0.,**{key:session.report[key] for key in ('precision','recall','f1','reward')})
  self.history.append(row)
  if not self.normalize_advantage or len(self.pending)>=4:self._update()
  self.history[-1]['weight_change']=math.sqrt(sum((a-b)**2 for a,b in zip(previous,self.model.parameters)))
  self.history[-1]['weight_norm']=math.sqrt(sum(w*w for w in self.model.parameters))
  if self.episodes%25==0:
   validation=self.evaluate(4,episode_seed(self.seed,'document-validation',0),policies=('learned',))['results'][0]
   self.history[-1].update(validation_reward=validation['reward'],validation_f1=validation['f1'])
  return copy.deepcopy(self.history[-1])

 def fit_blind(self,count=150,seed=None):
  """Fit public outcome frequencies, without truth, reward or report labels."""
  from .env import Session
  if type(count) is not int or not 1<=count<=1000:raise ValueError('Invalid fit count')
  root=self.seed if seed is None else seed
  stats={kind:[0.,0.] for kind in KINDS}
  for i in range(count):
   session=Session();initial,_=session.reset(episode_seed(root,'document-train',i),self.config(i,self.family),'evaluation')
   result=investigate(session.step,initial,policy='blind_online',budget=self.budget)
   for outcome in result['public_outcomes']:
    kind=outcome['kind']
    if kind in stats:stats[kind][0]+=outcome['positive'];stats[kind][1]+=1
  self.blind_statistics=stats
  return copy.deepcopy(stats)

 def run(self,session,initial,log=None,policy='learned',budget=None):
  result=investigate(session.step,initial,policy=policy,model=self.model,budget=self.budget if budget is None else budget,blind_statistics=self.blind_statistics)
  if log is not None:log.extend(result['trajectory'])
  return result['terminal']

 def evaluate(self,count=12,seed=22022001,*,policies=None,family=None,budget=None):
  from .env import Session
  if type(count) is not int or not 1<=count<=200 or type(seed) is not int:raise ValueError('Invalid evaluation')
  family=self.family if family is None else family;budget=self.budget if budget is None else budget
  if family not in ('procurement','service_milestone'):raise ValueError('Invalid evaluation family')
  policies=policies or ('learned','untrained','blind_statistical','blind_online','budget_aware','greedy','heuristic_search','fixed_source','random_valid','reconciliation')
  rows=[]
  for i in range(count):
   for policy in policies:
    session=Session();initial,_=session.reset(episode_seed(seed,'document-evaluation',i),self.config(i,family),'evaluation')
    started=time.perf_counter();result=investigate(session.step,initial,policy=policy,model=self.model,budget=budget,blind_statistics=self.blind_statistics)
    rows.append(dict(policy=policy,category=CATEGORIES[policy],index=i,steps=session.steps,inspection_steps=session.steps-1,seconds=time.perf_counter()-started,clean=i%5==0,**{key:session.report[key] for key in ('precision','recall','f1','reward','tp','fp','fn')}))
  keys=('precision','recall','f1','reward','steps','inspection_steps','seconds','tp','fp','fn')
  return dict(seed=seed,count=count,budget=budget,family=family,results=[dict(policy=p,category=CATEGORIES[p],episodes=count,**{key:statistics.mean(r[key] for r in rows if r['policy']==p) for key in keys}) for p in policies],episodes=rows,scope='Frozen inference; public document acquisition. Fitted blind statistics use training companies only.')

 def checkpoint(self):
  return dict(format='auditforge-document-policy',version=1,world_profile='investigation_v2',features=list(FEATURES),architecture=self.model.architecture,hidden=8,seed=self.seed,budget=self.budget,algorithm=self.algorithm,learning_rate=self.learning_rate,family=self.family,entropy=self.entropy,normalize_advantage=self.normalize_advantage,parameters=list(self.model.parameters),critic=list(self.critic),episodes=self.episodes,optimizer_steps=self.optimizer_steps,baseline=self.baseline,history=copy.deepcopy(self.history),pending=copy.deepcopy(self.pending),blind_statistics=copy.deepcopy(self.blind_statistics))

 @classmethod
 def from_checkpoint(cls,data):
  if not isinstance(data,dict):raise ValueError('Invalid checkpoint')
  try:
   if len(json.dumps(data,allow_nan=False))>10000000:raise ValueError('Checkpoint too large')
   model=cls(**{k:data[k] for k in ('seed','budget','algorithm','learning_rate','family','architecture','hidden','entropy','normalize_advantage')})
   if set(data)!=set(model.checkpoint()) or data['format']!='auditforge-document-policy' or data['version']!=1 or type(data['version']) is not int or data['world_profile']!='investigation_v2' or data['features']!=list(FEATURES):raise ValueError('Incompatible checkpoint')
   model.model=Network(data['architecture'],seed=data['seed'],parameters=data['parameters'])
   if any(type(data[k]) is not int or not 0<=data[k]<=100000 for k in ('episodes','optimizer_steps')) or data['optimizer_steps']>data['episodes']:raise ValueError('Invalid counters')
   if not isinstance(data['critic'],list) or len(data['critic'])!=len(FEATURES) or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10 for v in data['critic']):raise ValueError('Invalid critic')
   if type(data['baseline']) not in (int,float) or not math.isfinite(data['baseline']) or abs(data['baseline'])>1:raise ValueError('Invalid baseline')
   if not isinstance(data['history'],list) or len(data['history'])!=data['episodes']:raise ValueError('Invalid history')
   for i,row in enumerate(data['history'],1):
    if not isinstance(row,dict) or type(row.get('episode')) is not int or row['episode']!=i or type(row.get('optimizer_steps')) is not int or not 0<=row['optimizer_steps']<=i:raise ValueError('Invalid history sequence')
    for key in ('precision','recall','f1','reward','seconds','weight_norm','weight_change'):
     v=row.get(key);lo=-1 if key=='reward' else 0;hi=1 if key in ('precision','recall','f1','reward') else 1e10
     if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid metric')
    if type(row.get('steps')) is not int or not 1<=row['steps']<=model.budget or type(row.get('inspection_steps')) is not int or row.get('inspection_steps')!=row['steps']-1:raise ValueError('Invalid action counts')
    for key in ('gradient_norm','gradient_variance','advantage_variance','mean_entropy','validation_reward','validation_f1'):
     if key in row:
      v=row[key];lo=-1 if key=='validation_reward' else 0;hi=1 if key.startswith('validation_') else 1e12
      if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Invalid optional metric')
   pending=data['pending']
   if not isinstance(pending,list) or len(pending)>3 or (pending and not model.normalize_advantage):raise ValueError('Invalid pending batch')
   for ep in pending:
    if set(ep)!= {'reward','baseline','decisions'} or any(type(ep[k]) not in (int,float) or not math.isfinite(ep[k]) or abs(ep[k])>1 for k in ('reward','baseline')) or not isinstance(ep['decisions'],list) or len(ep['decisions'])>99:raise ValueError('Invalid pending trajectory')
    for decision in ep['decisions']:
     xs=decision['features'];ps=decision['probabilities'];chosen=decision['chosen']
     if not isinstance(xs,list) or not 1<=len(xs)<=100 or type(chosen) is not int or not 0<=chosen<len(xs) or not isinstance(ps,list) or len(ps)!=len(xs):raise ValueError('Invalid decision')
     if any(not isinstance(x,list) or len(x)!=len(FEATURES) or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1 for v in x) for x in xs):raise ValueError('Invalid features')
     if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in ps) or abs(sum(ps)-1)>1e-8:raise ValueError('Invalid probabilities')
     if type(decision['entropy']) not in (int,float) or not math.isfinite(decision['entropy']) or not 0<=decision['entropy']<=6:raise ValueError('Invalid entropy')
   stats=data['blind_statistics']
   if not isinstance(stats,dict) or set(stats)!=set(KINDS) or any(not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1e8 for x in v) or v[0]>v[1] for v in stats.values()):raise ValueError('Invalid blind statistics')
   for k in ('critic','episodes','optimizer_steps','baseline','history','pending','blind_statistics'):setattr(model,k,copy.deepcopy(data[k]))
   return model
  except (KeyError,TypeError,OverflowError) as exc:raise ValueError('Invalid checkpoint') from exc
