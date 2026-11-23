"""Small CPU policy-gradient candidates; reward only, no private labels as features."""
import copy
import json
import math
import random
import statistics
import time

from .generator import GENERATOR_VERSION
from .training import episode_seed


class SequentialTrainer:
    def __init__(self, seed=314159, budget=10, algorithm='reinforce', learning_rate=.03, *, family='procurement'):
        from .sequential_policy import INITIAL_WEIGHTS
        if (type(seed) is not int or not 0<=seed<2**128 or type(budget) is not int or not 2<=budget<=100
                or algorithm not in ('reinforce','actor_critic')
                or type(learning_rate) not in (int,float) or not math.isfinite(learning_rate) or not 0<learning_rate<=.5):
            raise ValueError('Invalid sequential training settings')
        from .investigation_world import FAMILIES
        if family not in FAMILIES:raise ValueError('Unknown financial family')
        self.family=family
        self.seed,self.budget,self.algorithm,self.learning_rate=seed,budget,algorithm,learning_rate
        self.weights=list(INITIAL_WEIGHTS);self.critic=[0.]*len(self.weights)
        self.episodes=0;self.baseline=0.;self.history=[]

    @staticmethod
    def config(index, family='procurement'):
        return dict(profile='investigation_v1',cases=6,clean=index%5==0,family=family)

    def train_episode(self):
        from .env import Session
        from .sequential_policy import investigate, FEATURES
        session=Session();initial,_=session.reset(episode_seed(self.seed,'sequential-train',self.episodes),self.config(self.episodes,self.family),'train')
        rng=random.Random(episode_seed(self.seed,'sequential-actions',self.episodes));rng.training=True
        started=time.perf_counter();previous=list(self.weights)
        result=investigate(session.step,initial,weights=self.weights,budget=self.budget,rng=rng)
        reward=result['terminal'][1];decisions=result['decisions']
        reference_reward=self.baseline
        if self.algorithm=='reinforce':
            reference=Session()
            reference_initial,_=reference.reset(episode_seed(self.seed,'sequential-train',self.episodes),self.config(self.episodes,self.family),'train')
            reference_reward=investigate(reference.step,reference_initial,weights=self.weights,budget=self.budget)['terminal'][1]
        states=[[statistics.mean(xs[j] for xs in row['features']) for j in range(len(FEATURES))] for row in decisions]
        # Read all advantages from the frozen pre-update critic (one on-policy trajectory).
        values=[sum(w*x for w,x in zip(self.critic,state)) for state in states]
        for i,row in enumerate(decisions):
            if self.algorithm=='reinforce':
                advantage=reward-reference_reward
            else:
                target=values[i+1] if i+1<len(values) else reward
                advantage=target-values[i]
                for j,x in enumerate(states[i]):
                    self.critic[j]=max(-10,min(10,self.critic[j]+.05*advantage*x))
            selected=row['features'][row['chosen']]
            for j in range(len(self.weights)):
                expected=sum(p*x[j] for p,x in zip(row['probabilities'],row['features']))
                self.weights[j]=max(-30,min(30,self.weights[j]+self.learning_rate*advantage*(selected[j]-expected)))
        self.baseline=.95*self.baseline+.05*reward
        self.episodes+=1
        row=dict(episode=self.episodes,optimizer_steps=self.episodes,steps=session.steps,inspection_steps=session.steps-1,
                 weight_norm=math.sqrt(sum(w*w for w in self.weights)),
                 weight_change=math.sqrt(sum((a-b)**2 for a,b in zip(self.weights,previous))),
                 seconds=time.perf_counter()-started,
                 **{key:session.report[key] for key in ('precision','recall','f1','reward')})
        if self.episodes%25==0:
            validation=self.evaluate(4,episode_seed(self.seed,'sequential-validation',0),policies=('learned',))
            row['validation_reward']=validation['results'][0]['reward']
            row['validation_f1']=validation['results'][0]['f1']
        self.history.append(row)
        return copy.deepcopy(row)

    def run(self, session, initial, log=None):
        from .sequential_policy import investigate
        result=investigate(session.step,initial,weights=self.weights,budget=self.budget)
        if log is not None:log.extend(result['trajectory'])
        return result['terminal']

    def evaluate(self,count=12,seed=70193,*,policies=None,family=None):
        from .env import Session
        from .sequential_policy import investigate
        if type(count) is not int or not 1<=count<=200 or type(seed) is not int:
            raise ValueError('Invalid evaluation configuration')
        family=self.family if family is None else family
        policies=policies or ('learned','untrained','random_valid','reconciliation','budget_aware','greedy','heuristic_search','fixed_source')
        rows=[]
        for i in range(count):
            for policy in policies:
                session=Session();initial,_=session.reset(episode_seed(seed,'sequential-evaluation',i),self.config(i,family),'evaluation')
                result=investigate(session.step,initial,policy=policy,weights=self.weights,budget=self.budget)
                rows.append(dict(policy=policy,index=i,steps=session.steps,inspection_steps=session.steps-1,
                                 **{key:session.report[key] for key in ('precision','recall','f1','reward')}))
        return dict(seed=seed,count=count,budget=self.budget,results=[dict(policy=policy,episodes=count,
                    **{key:statistics.mean(row[key] for row in rows if row['policy']==policy)
                       for key in ('precision','recall','f1','reward','steps','inspection_steps')}) for policy in policies],
                    episodes=rows,scope='Frozen weights. Shared financial rules; learned sequential query ordering and stopping, not learned arithmetic.')

    def checkpoint(self):
        from .sequential_policy import FEATURES
        result=dict(format='auditforge-sequential-policy',version=4,environment=GENERATOR_VERSION,
                    algorithm=self.algorithm,architecture='linear softmax query policy with explicit stop',
                    baseline_method='same-company frozen greedy rollout' if self.algorithm=='reinforce' else 'one-step TD linear state critic',
                    world_profile='investigation_v1',scenario='mixed',features=list(FEATURES),
                    seed=self.seed,budget=self.budget,learning_rate=self.learning_rate,
                    weights=list(self.weights),critic=list(self.critic),episodes=self.episodes,
                    optimizer_steps=self.episodes,baseline=self.baseline,history=copy.deepcopy(self.history))
        if self.family!='procurement':result['family']=self.family
        return result

    @classmethod
    def from_checkpoint(cls,data):
        from .sequential_policy import FEATURES
        if not isinstance(data,dict) or len(json.dumps(data,allow_nan=False))>10000000:
            raise ValueError('Invalid checkpoint object')
        model=cls(data.get('seed'),data.get('budget'),data.get('algorithm'),data.get('learning_rate'),family=data.get('family','procurement'))
        expected=model.checkpoint()
        if set(data)!=set(expected) or any(data.get(key)!=expected[key] for key in
                ('format','version','environment','architecture','baseline_method','world_profile','scenario','features')):
            raise ValueError('Incompatible checkpoint')
        for key in ('weights','critic'):
            values=data.get(key)
            if not isinstance(values,list) or len(values)!=len(FEATURES) or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>30 for x in values):
                raise ValueError('Invalid model parameters')
            setattr(model,key,list(values))
        if type(data['episodes']) is not int or not 0<=data['episodes']<=100000 or type(data['optimizer_steps']) is not int or data['optimizer_steps']!=data['episodes']:
            raise ValueError('Invalid optimizer counters')
        if type(data['baseline']) not in (int,float) or not math.isfinite(data['baseline']) or not -1<=data['baseline']<=1:
            raise ValueError('Invalid baseline')
        if not isinstance(data['history'],list) or len(data['history'])!=data['episodes']:
            raise ValueError('Invalid history')
        for i,row in enumerate(data['history'],1):
            if (not isinstance(row,dict) or type(row.get('episode')) is not int
                    or type(row.get('optimizer_steps')) is not int
                    or row.get('episode')!=i or row.get('optimizer_steps')!=i):
                raise ValueError('Invalid history sequence')
            for key in ('precision','recall','f1','reward','seconds','weight_norm','weight_change'):
                value=row.get(key)
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Invalid metric')
                low,high=(-1,1) if key=='reward' else ((0,1) if key in ('precision','recall','f1') else (0,1e9))
                if not low<=value<=high:raise ValueError('Metric out of range')
            if (type(row.get('steps')) is not int or not 1<=row['steps']<=model.budget
                    or type(row.get('inspection_steps')) is not int
                    or row.get('inspection_steps')!=row['steps']-1):
                raise ValueError('Invalid action count')
            for key in ('validation_reward','validation_f1'):
                low=0 if key=='validation_f1' else -1
                if key in row and (type(row[key]) not in (int,float) or not math.isfinite(row[key]) or not low<=row[key]<=1):
                    raise ValueError('Invalid validation metric')
        model.episodes=data['episodes'];model.baseline=data['baseline'];model.history=copy.deepcopy(data['history'])
        return model
