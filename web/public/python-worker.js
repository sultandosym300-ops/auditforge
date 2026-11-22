import {loadPyodide} from './python/pyodide.mjs';
let runtime;
async function ready(){
  if(!runtime)runtime=(async()=>{
    const py=await loadPyodide({indexURL:new URL('./python/',self.location.href).href});
    const files=await (await fetch('/python-core.json')).json();
    py.FS.mkdirTree('/app/auditforge');
    for(const [name,content] of Object.entries(files))py.FS.writeFile('/app/auditforge/'+name,content);
    const bridge=await fetch('/python-bridge.py');
    if(!bridge.ok)throw Error('Python bridge unavailable');
    py.runPython(await bridge.text());
    return py;
  })().catch(error=>{runtime=null;throw error;});
  return runtime;
}
let queue=Promise.resolve();
self.onmessage=({data})=>{queue=queue.then(async()=>{
  try{const py=await ready();py.globals.set('request_path',data.path);py.globals.set('request_json',JSON.stringify(data.payload||{}));const result=py.runPython(`json.dumps(request(request_path,json.loads(request_json)))`);self.postMessage({id:data.id,result:JSON.parse(result)});}
  catch(error){self.postMessage({id:data.id,error:'environment_error'});}
});};
