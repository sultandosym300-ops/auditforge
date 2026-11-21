import {loadPyodide} from './python/pyodide.mjs';
let runtime;
async function ready(){
  if(!runtime)runtime=(async()=>{
    const py=await loadPyodide({indexURL:new URL('./python/',self.location.href).href});
    const files=await (await fetch('/python-core.json')).json();
    py.FS.mkdirTree('/app/auditforge');
    for(const [name,content] of Object.entries(files))py.FS.writeFile('/app/auditforge/'+name,content);
    py.runPython(`import sys,json,secrets\nsys.path.insert(0,'/app')\nfrom auditforge.env import Session\nfrom auditforge.policies import run_policy\nfrom auditforge.training import Trainer\nfrom auditforge.efficient_training import EfficientTrainer,load_trainer\nfrom auditforge.counterfactual import challenge\ntrainer=None\nsession=Session()\ntrajectory=[]\ninitial=None\nclass Bridge:\n def step(self,action):\n  result=session.step(action)\n  trajectory.append(dict(episode_id=session.public['manifest']['episode_id'],step=len(trajectory)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))\n  return result\nbridge=Bridge()\ndef request(path,payload):\n global initial,trajectory,trainer\n if path=='training_create':\n  trainer=EfficientTrainer(payload.get('seed',20261121),payload.get('scenario','period'))\n  return trainer.checkpoint()\n if path=='training_import':\n  trainer=load_trainer(payload['checkpoint'])\n  return trainer.checkpoint()\n if path=='training_step':\n  if trainer is None: raise ValueError('Create an agent first')\n  return trainer.train_episode()\n if path=='training_checkpoint':\n  if trainer is None: raise ValueError('Create an agent first')\n  return trainer.checkpoint()\n if path=='training_evaluate':\n  if trainer is None: raise ValueError('Create an agent first')\n  return trainer.evaluate(payload.get('count',12),payload.get('seed',70193))\n if path=='training_counterfactual':\n  if trainer is None: raise ValueError('Create an agent first')\n  return challenge(trainer,payload.get('count',10),payload.get('seed',907193))\n if path=='training_run':\n  if trainer is None or initial is None: raise ValueError('Create agent and episode first')\n  if session.done: raise ValueError('Create a fresh episode')\n  observed=dict(initial,steps_remaining=100-session.steps)\n  result=trainer.run(bridge,observed)\n  return dict(result=result,report=session.report,trajectory=trajectory)\n if path=='reset':\n  initial,_=session.reset(payload.get('seed',secrets.randbelow(2**32)),payload.get('config',{}),'train')\n  trajectory=[]\n  return dict(observation=initial)\n if path=='step':\n  result=bridge.step(payload['action'])\n  return dict(observation=result[0],reward=result[1],terminated=result[2],truncated=result[3],report=session.report if session.done else None)\n if path=='run':\n  result=run_policy(bridge,initial,payload.get('policy','reconciliation'))\n  return dict(result=result,report=session.report,trajectory=trajectory)\n if path=='trajectory':return trajectory\n raise ValueError('Unknown public request')`);
    return py;
  })().catch(error=>{runtime=null;throw error;});
  return runtime;
}
let queue=Promise.resolve();
self.onmessage=({data})=>{queue=queue.then(async()=>{
  try{const py=await ready();py.globals.set('request_path',data.path);py.globals.set('request_json',JSON.stringify(data.payload||{}));const result=py.runPython(`json.dumps(request(request_path,json.loads(request_json)))`);self.postMessage({id:data.id,result:JSON.parse(result)});}
  catch(error){self.postMessage({id:data.id,error:'environment_error'});}
});};
