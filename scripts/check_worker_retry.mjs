import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const source=(await readFile('web/public/python-worker.js','utf8')).replace(/^import .+;\r?\n/,'');
let starts=0;
const replies=[];
const python={
 FS:{mkdirTree(){},writeFile(){}},
 globals:{set(){}},
 runPython(code){return code.startsWith('json.dumps(')?'{"ok":true}':null}
};
const sandbox={
 URL,
 fetch:async()=>({ok:true,json:async()=>({}),text:async()=>''}),
 loadPyodide:async()=>{
  starts++;
  if(starts===1)throw Error('Transient runtime download failure');
  return python;
 },
 self:{location:{href:'https://example.test/python-worker.js'},postMessage(message){replies.push(message)}}
};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
async function request(id){
 sandbox.self.onmessage({data:{id,path:'training_checkpoint',payload:{}}});
 for(let i=0;i<100&&replies.length<id;i++)await new Promise(r=>setTimeout(r,1));
 assert.equal(replies.length,id);
 return replies[id-1];
}
assert.equal((await request(1)).error,'environment_error');
assert.equal((await request(2)).result.ok,true);
assert.equal((await request(3)).result.ok,true);
assert.equal(starts,2);
console.log('Worker retries failed initialization and reuses successful runtime.');
