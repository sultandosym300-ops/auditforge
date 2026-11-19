import {loadPyodide} from './python/pyodide.mjs';
let runtime;
async function ready(){
  if(!runtime)runtime=(async()=>{
    const py=await loadPyodide({indexURL:'/python/'});
    const files=await (await fetch('/python-core.json')).json();
    py.FS.mkdirTree('/app/auditforge');
    for(const [name,content] of Object.entries(files))py.FS.writeFile('/app/auditforge/'+name,content);
    py.runPython(`import sys,json,secrets\nsys.path.insert(0,'/app')\nfrom auditforge.env import Session\nfrom auditforge.policies import run_policy\nsession=Session()\ntrajectory=[]\ninitial=None\nclass Bridge:\n def step(self,action):\n  result=session.step(action)\n  trajectory.append(dict(episode_id=session.public['manifest']['episode_id'],step=len(trajectory)+1,action=action,observation=result[0],reward=result[1],terminated=result[2],truncated=result[3]))\n  return result\nbridge=Bridge()\ndef request(path,payload):\n global initial,trajectory\n if path=='reset':\n  initial,_=session.reset(payload.get('seed',secrets.randbelow(2**32)),payload.get('config',{}),'train')\n  trajectory=[]\n  return dict(observation=initial)\n if path=='step':\n  result=bridge.step(payload['action'])\n  return dict(observation=result[0],reward=result[1],terminated=result[2],truncated=result[3],report=session.report if session.done else None)\n if path=='run':\n  result=run_policy(bridge,initial,payload.get('policy','reconciliation'))\n  return dict(result=result,report=session.report,trajectory=trajectory)\n if path=='trajectory':return trajectory\n raise ValueError('Unknown public request')`);
    return py;
  })();
  return runtime;
}
let queue=Promise.resolve();
self.onmessage=({data})=>{queue=queue.then(async()=>{
  try{const py=await ready();py.globals.set('request_path',data.path);py.globals.set('request_json',JSON.stringify(data.payload||{}));const result=py.runPython(`json.dumps(request(request_path,json.loads(request_json)))`);self.postMessage({id:data.id,result:JSON.parse(result)});}
  catch(error){self.postMessage({id:data.id,error:'environment_error'});}
});};
