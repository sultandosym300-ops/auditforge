import fs from 'node:fs';
fs.mkdirSync('public/python',{recursive:true});
for(const file of ['pyodide.mjs','pyodide.asm.js','pyodide.asm.wasm','pyodide-lock.json','python_stdlib.zip'])fs.copyFileSync('node_modules/pyodide/'+file,'public/python/'+file);
const files={};
for(const name of ['__init__.py','generator.py','matcher.py','reconcile.py','policies.py'])files[name]=fs.readFileSync('../auditforge/'+name,'utf8');
files['env.py']=fs.readFileSync('../auditforge/env.py','utf8').replace('import multiprocessing\n','').split('\ndef _worker(')[0];
fs.writeFileSync('public/python-core.json',JSON.stringify(files));
