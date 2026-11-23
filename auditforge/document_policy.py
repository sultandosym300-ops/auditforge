"""Public-only document acquisition policies. No generator, truth or host imports.

Every competitor shares the same acquired-document decoder. The learned model
chooses requests and STOP; it does not learn monetary arithmetic. Blind fitted
risk uses only public documentary outcomes collected on training companies.
"""
import copy
import itertools
import math
import random
from .documentary_decode import decode

KINDS=('contract','invoice','payment','bank_confirmation','journal_entry','fx_quote','refund','allocation','fulfillment')
FEATURES=('bias',)+KINDS+('same_case_seen','references_seen','invoice_seen','payment_seen','journal_seen','foreign_seen','partial_proof','budget_fraction','stop')
CATEGORIES={'learned':'learned','untrained':'untrained_same_architecture','random':'uninformed','fixed':'uninformed','reconciliation':'generator_blind','blind_adaptive':'generator_blind','blind_fitted':'generator_blind','oracle_knowledge':'oracle_knowledge'}
ALIASES={'blind_statistical':'blind_fitted','blind_online':'blind_adaptive','fixed_source':'fixed','random_valid':'random','budget_aware':'oracle_knowledge','greedy':'oracle_knowledge','heuristic_search':'oracle_knowledge'}
CATEGORIES.update({name:CATEGORIES[target] for name,target in ALIASES.items()})
CATEGORIES.update(random_weights='untrained_same_architecture',no_document_features='ablation')
POLICIES=tuple(CATEGORIES)

def softmax(values):
 top=max(values);es=[math.exp(v-top) for v in values];total=sum(es)
 return [x/total for x in es]

class Network:
 """Shared action scorer: linear or one tanh hidden layer, analytic backprop."""
 def __init__(self,architecture='linear',seed=0,parameters=None):
  if architecture not in ('linear','mlp'):raise ValueError('Unknown architecture')
  self.architecture=architecture;self.seed=seed;self.hidden=8;self.dim=len(FEATURES)
  count=self.dim if architecture=='linear' else self.hidden*self.dim+self.hidden+self.hidden+1
  rng=random.Random(seed)
  self.parameters=([0.]*count if architecture=='linear' else [rng.uniform(-.08,.08) for _ in range(count)])
  if architecture=='linear':self.parameters[-1]=-2.
  if parameters is not None:
   if not isinstance(parameters,list) or len(parameters)!=count or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>30 for v in parameters):raise ValueError('Invalid model parameters')
   self.parameters=list(parameters)
 def score_gradient(self,x):
  if len(x)!=self.dim:raise ValueError('Invalid feature size')
  if self.architecture=='linear':return sum(a*b for a,b in zip(self.parameters,x)),list(x)
  n=self.dim;h=self.hidden;p=self.parameters
  hidden=[math.tanh(sum(p[j*n+i]*x[i] for i in range(n))+p[h*n+j]) for j in range(h)]
  gradient=[0.]*len(p)
  for j in range(h):
   factor=p[h*n+h+j]*(1-hidden[j]*hidden[j])
   for i in range(n):gradient[j*n+i]=factor*x[i]
   gradient[h*n+j]=factor;gradient[h*n+h+j]=hidden[j]
  gradient[-1]=1.
  return sum(p[h*n+h+j]*hidden[j] for j in range(h))+p[-1]-2*x[-1],gradient
 def score(self,x):return self.score_gradient(x)[0]

def distribution(model,xs):return softmax([model.score(x) for x in xs])

def objective_gradient(model,xs,chosen,advantage,entropy_coefficient=0.):
 """Gradient of A log pi(a|s) + beta H(pi); frozen on-policy objective."""
 values=[model.score_gradient(x) for x in xs];ps=softmax([v[0] for v in values]);expected=[sum(p*v[1][j] for p,v in zip(ps,values)) for j in range(len(model.parameters))]
 expected_log=sum(p*math.log(max(p,1e-30)) for p in ps)
 return [advantage*(values[chosen][1][j]-expected[j])-entropy_coefficient*sum(p*(math.log(max(p,1e-30))-expected_log)*v[1][j] for p,v in zip(ps,values)) for j in range(len(expected))]

def _kind(value):
 aliases={'bank_transfer':'bank_confirmation','bank_transfer_confirmation':'bank_confirmation','ledger':'journal_entry','exchange_rate':'fx_quote','exchange_quote':'fx_quote','allocation_document':'allocation','payment_allocation':'allocation','fulfillment_confirmation':'fulfillment','refund_document':'refund'}
 return aliases.get(value,value)

def feature_vector(candidate,acquired,public,remaining,budget,*,stop=False):
 if stop:return [0.]*(len(FEATURES)-1)+[1.]
 case=candidate.get('case_id');same=[d for d in acquired.values() if d.get('case_id')==case];kinds={_kind(d.get('kind')) for d in same};references={r.get('document_id',r.get('doc_id')) for d in same for r in d.get('references',[]) if isinstance(r,dict)}
 payments=[r for d in (acquired.values() if _kind(candidate.get('kind'))=='fx_quote' else same) for r in d.get('records',{}).get('payments',[])]
 foreign=any(r.get('currency')!=public['manifest']['base_currency'] for r in payments)
 # Flags describe acquired facts and document prerequisites, never risk coefficients.
 return [1.]+[float(_kind(candidate.get('kind'))==k) for k in KINDS]+[min(1.,len(same)/8),float(candidate['document_id'] in references),float('invoice' in kinds),float('payment' in kinds or 'refund' in kinds),float('journal_entry' in kinds),float(foreign),float(bool(kinds & {'invoice','payment','journal_entry'})),remaining/max(1,budget),0.]

def _blind_priority(x,kind):
 """Generic evidence-completion heuristic, independent of event probabilities."""
 k=len(KINDS)+1;same,reference,invoice,payment,journal,foreign,partial=x[k:k+7]
 if kind=='fx_quote':return 1.+4*foreign+2*journal
 if kind=='journal_entry':return 1.+3*invoice+3*payment+reference
 if kind in ('invoice','payment','refund'):return 2.+3*journal+reference
 return .5+reference+.25*same

def investigate(step,initial,*,policy='learned',budget=20,model=None,parameters=None,architecture='linear',rng=None,blind_statistics=None):
 if policy not in POLICIES or type(budget) is not int or not 2<=budget<=100:raise ValueError('Invalid document policy settings')
 index=initial['manifest'].get('document_index')
 if not isinstance(index,list) or not index:raise ValueError('Document policy requires investigation_v2')
 requested_policy=policy;policy=ALIASES.get(policy,policy)
 model=model or Network(architecture,parameters=parameters)
 if policy=='untrained':model=Network(model.architecture,seed=model.seed)
 if policy=='random_weights':model=Network(model.architecture,parameters=[random.Random(719+i).uniform(-1,1) for i in range(len(model.parameters))])
 rng=rng or random.Random(0);remaining=min(budget,initial['steps_remaining'])
 public={key:[] for key in ('invoices','payments','ledger','fx')};public.update(manifest=initial['manifest'],policy=initial['policy'])
 acquired={};trajectory=[];decisions=[];outcomes=[];known_findings={};online_statistics={kind:[0.,0.] for kind in KINDS}
 def act(action,reason):
  nonlocal remaining
  response=step(action);remaining-=1
  trajectory.append(dict(episode_id=initial['manifest']['episode_id'],step=len(trajectory)+1,action=action,observation=response[0],reward=response[1],terminated=response[2],truncated=response[3],reason=reason))
  if 'error' in response[0]:raise ValueError('Document request failed: '+response[0]['error'])
  return response
 while remaining>1:
  candidates=[d for d in index if d['document_id'] not in acquired]
  if not candidates:break
  xs=[feature_vector(c,acquired,public,remaining,budget) for c in candidates];xs.append(feature_vector(None,acquired,public,remaining,budget,stop=True))
  probabilities=None
  if policy in ('learned','untrained','random_weights','no_document_features'):
   if policy=='no_document_features':xs=[[x[0]]+[0.]*(len(FEATURES)-2)+[x[-1]] for x in xs]
   probabilities=distribution(model,xs)
   chosen=rng.choices(range(len(xs)),weights=probabilities)[0] if getattr(rng,'training',False) else max(range(len(xs)),key=lambda i:probabilities[i])
   decisions.append(dict(features=xs,probabilities=probabilities,chosen=chosen,entropy=-sum(p*math.log(max(p,1e-30)) for p in probabilities)))
  elif policy=='random':chosen=rng.randrange(len(candidates))
  elif policy in ('fixed','reconciliation'):chosen=0
  else:
   planned_cases=None
   if requested_policy=='heuristic_search':
    financial={'invoice','payment','refund','journal_entry'}
    cases=sorted({d.get('case_id') for d in candidates if _kind(d.get('kind')) in financial})
    costs={case:sum(d.get('case_id')==case and _kind(d.get('kind')) in financial for d in candidates) for case in cases}
    shared=sum(_kind(d.get('kind'))=='fx_quote' for d in candidates)
    prior=.65 if initial['manifest'].get('family')=='procurement' else .5
    portfolios=[subset for size in range(1,len(cases)+1) for subset in itertools.combinations(cases,size) if sum(costs[c] for c in subset)+shared<=remaining-1]
    if portfolios:
     planned_cases=max(portfolios,key=lambda subset:(4*prior*len(subset),-sum(costs[c] for c in subset)))
    elif cases:planned_cases=(min(cases,key=lambda c:costs[c]),)
   def priority(i):
    c=candidates[i];x=xs[i];kind=_kind(c.get('kind'))
    result=_blind_priority(x,kind)
    if policy in ('blind_fitted','blind_adaptive'):
     statistics_used=blind_statistics if policy=='blind_fitted' and blind_statistics else online_statistics
     # Empirical posterior fitted only from acquired public documentary outcomes.
     stat=statistics_used.get(kind,[0.,0.]);result+=3*(stat[0]+1)/(stat[1]+2)
    if policy=='oracle_knowledge':
     # Explicit informed family prior: accounting transformations may affect
     # ledger, source payment, invoice and FX; no company-specific hidden label.
     prior=.65 if initial['manifest'].get('family')=='procurement' else .5
     case_count=max(1,len({item.get('case_id') for item in index if item.get('case_id')!='shared'}))
     # Public generator distribution: each error mechanism has uniform target case.
     expected=prior/case_count
     mechanism_value={'journal_entry':4.,'invoice':2.,'payment':2.,'refund':2.,'fx_quote':2.}.get(kind,0.)
     if requested_policy=='greedy':
      entropy=-expected*math.log(max(expected,1e-12))-(1-expected)*math.log(max(1-expected,1e-12))
      result=entropy*result+mechanism_value*expected
     elif requested_policy=='heuristic_search':
      result+=mechanism_value*expected
      if planned_cases and c.get('case_id') not in planned_cases and kind!='fx_quote':result-=100.
     else:result+=mechanism_value*expected
    return result
   chosen=max(range(len(candidates)),key=priority)
  if chosen==len(candidates):break
  c=candidates[chosen];reason=dict(policy=policy,category=CATEGORIES[policy],document_kind=c.get('kind'),remaining_budget=remaining,features=xs[chosen])
  response=act(dict(tool='get_document',doc_id=c['document_id']),reason);document=response[0]['result'];acquired[c['document_id']]=copy.deepcopy(document)
  records=document.get('records',{})
  for table in ('invoices','payments','ledger','fx'):
   existing={r.get('row_id',r.get('doc_id')) for r in public[table]}
   for row in records.get(table,[]):
    if row.get('row_id',row.get('doc_id')) not in existing:public[table].append(copy.deepcopy(row))
  recovered=decode(public)
  # Duplicate totals require all referenced recognition entries. Otherwise a
  # partial duplicate group could be submitted with an understated amount.
  complete=[]
  by_row={r['row_id']:r for r in public['ledger']}
  for finding in recovered:
   if finding['type']=='duplicate_invoice':
    iid=by_row[finding['affected_ids'][0]]['invoice_id']
    invoice_doc=next((d for d in acquired.values() if any(r['invoice_id']==iid for r in d.get('records',{}).get('invoices',[]))),None)
    refs=[r.get('document_id',r.get('doc_id')) for r in (invoice_doc or {}).get('references',[]) if _kind(r.get('kind'))=='journal_entry']
    if any(ref not in acquired for ref in refs):continue
   complete.append(finding)
  recovered=complete
  new={(f['type'],tuple(f['affected_ids'])):f for f in recovered}
  outcome=dict(kind=_kind(c.get('kind')),positive=float(bool(set(new)-set(known_findings))))
  outcomes.append(outcome)
  if outcome['kind'] in online_statistics:
   online_statistics[outcome['kind']][0]+=outcome['positive'];online_statistics[outcome['kind']][1]+=1
  known_findings=new
 findings=list(known_findings.values())[:30]
 terminal=act(dict(tool='submit',findings=dict(episode_id=initial['manifest']['episode_id'],findings=findings)),'Submit findings supported by individually acquired records')
 return dict(terminal=terminal,decisions=decisions,trajectory=trajectory,findings=findings,documents=list(acquired.values()),public_outcomes=outcomes,category=CATEGORIES[requested_policy])
