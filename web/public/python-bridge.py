import sys,json,secrets
if '/app' not in sys.path: sys.path.insert(0,'/app')
from auditforge.env import Session
from auditforge.policies import run_policy
from auditforge.agent_only import run_agent_only
from auditforge.training import Trainer
from auditforge.efficient_training import EfficientTrainer,load_trainer
from auditforge.counterfactual import challenge
from auditforge.proof import public_story,proof_suite,explain_completed,receipt_scenario
trainer=None
session=Session()
trajectory=[]
initial=None
class Bridge:
 def step(self,action):
  result=session.step(action)
  trajectory.append(dict(episode_id=session.public['manifest']['episode_id'],step=len(trajectory)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))
  return result
bridge=Bridge()
def request(path,payload):
 global initial,trajectory,trainer
 if path=='proof_suite':
  return proof_suite(payload.get('seed',2026112204))
 if path=='world_story':
  if initial is None: raise ValueError('Create a company first')
  return dict(public_story(session.public),business=session.public.get('business'))
 if path=='demo_explain':
  if initial is None: raise ValueError('Create a company first')
  return explain_completed(session,demo=payload.get('demo') is True)
 if path=='world_counterfactual':
  if initial is None: raise ValueError('Create a company first')
  return receipt_scenario(session.public,payload.get('event_id'),payload.get('amount_minor'))
 if path=='training_create':
  if payload.get('world_profile')=='investigation_v1':
   from auditforge.sequential_training import SequentialTrainer
   trainer=SequentialTrainer(payload.get('seed',314159),payload.get('budget',10),payload.get('algorithm','reinforce'),family=payload.get('family','procurement'))
  else:
   trainer=EfficientTrainer(payload.get('seed',20261121),payload.get('scenario','period'),world_profile=payload.get('world_profile'),business_type=payload.get('business_type','logistics'))
  return trainer.checkpoint()
 if path=='training_demo':
  from auditforge.sequential_policy import investigate
  if trainer is None or trainer.checkpoint().get('world_profile')!='investigation_v1':raise ValueError('Create a sequential agent')
  runs=[]
  for policy in ('random_valid','reconciliation','budget_aware','learned'):
   demo=Session();observed,_=demo.reset(202611230017,dict(profile='investigation_v1',family=trainer.family),'evaluation')
   result=investigate(demo.step,observed,policy=policy,budget=trainer.budget,weights=trainer.weights)
   runs.append(dict(policy=policy,report=demo.report,steps=demo.steps,trajectory=result['trajectory']))
  return dict(seed=202611230017,budget=trainer.budget,runs=runs)
 if path=='training_import':
  trainer=load_trainer(payload['checkpoint'])
  return trainer.checkpoint()
 if path=='training_step':
  if trainer is None: raise ValueError('Create an agent first')
  return trainer.train_episode()
 if path=='training_checkpoint':
  if trainer is None: raise ValueError('Create an agent first')
  return trainer.checkpoint()
 if path=='training_evaluate':
  if trainer is None: raise ValueError('Create an agent first')
  return trainer.evaluate(payload.get('count',12),payload.get('seed',70193))
 if path=='training_counterfactual':
  if trainer is None: raise ValueError('Create an agent first')
  return challenge(trainer,payload.get('count',10),payload.get('seed',907193))
 if path=='training_run':
  if trainer is None or initial is None: raise ValueError('Create agent and episode first')
  if session.done: raise ValueError('Create a fresh episode')
  observed=dict(initial,steps_remaining=100-session.steps)
  result=trainer.run(bridge,observed)
  return dict(result=result,report=session.report,trajectory=trajectory)
 if path=='reset':
  initial,_=session.reset(payload.get('seed',secrets.randbelow(2**32)),payload.get('config',{}),'train')
  trajectory=[]
  return dict(observation=initial)
 if path=='step':
  result=bridge.step(payload['action'])
  return dict(observation=result[0],reward=result[1],terminated=result[2],truncated=result[3],report=session.report if session.done else None)
 if path=='run':
  result=run_agent_only(bridge.step,initial)['terminal'] if payload.get('policy')=='corroboration' else run_policy(bridge,initial,payload.get('policy','reconciliation'))
  return dict(result=result,report=session.report,trajectory=trajectory)
 if path=='trajectory':return trajectory
 raise ValueError('Unknown public request')
