let backend='browser';
let worker;
let nextId=0;
const pending=new Map();
function rpc(path,payload){
  if(!worker){
    worker=new Worker('/python-worker.js',{type:'module'});
    worker.onmessage=({data})=>{const p=pending.get(data.id);if(p){clearTimeout(p.timer);pending.delete(data.id);data.error?p.reject(new Error(data.error)):p.resolve(data.result);}};
    worker.onerror=()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('environment_error'));}pending.clear();worker.terminate();worker=null;};
  }
  return new Promise((resolve,reject)=>{const id=++nextId;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('environment_timeout'));},60000);pending.set(id,{resolve,reject,timer});worker.postMessage({id,path,payload});});
}
export async function detectBackend(){
  try{const response=await fetch('/api/me');if(response.headers.get('content-type')?.includes('application/json')){const value=await response.json();if(value.backend==='python'){backend='python';return value;}}}catch{}
  return {backend,user:JSON.parse(sessionStorage.getItem('af-user')||'null')};
}
async function digestPassword(password,salt){
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits']);
  const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt:new TextEncoder().encode(salt),iterations:210000,hash:'SHA-256'},key,256);
  return Array.from(new Uint8Array(bits),x=>x.toString(16).padStart(2,'0')).join('');
}
export async function trainingApi(path,payload={}){return rpc(path,payload);}
export async function api(path,payload={}){
  if(backend==='python'){
    const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const value=await response.json();if(!response.ok)throw new Error(value.error||'request_error');return value;
  }
  if(['guest','login','register'].includes(path)){
    let user={name:'Guest',guest:true};
    if(path!=='guest'){
      const name=payload.name?.trim();const password=payload.password||'';
      if(!name||name.length<3||name.length>40||password.length<8||password.length>128)throw new Error('invalid_credentials_format');
      const accounts=JSON.parse(localStorage.getItem('af-accounts')||'{}');const existing=accounts[name.toLowerCase()];
      if(path==='register'){
        if(existing)throw new Error('name_taken');
        const salt=crypto.randomUUID();accounts[name.toLowerCase()]={salt,digest:await digestPassword(password,salt)};localStorage.setItem('af-accounts',JSON.stringify(accounts));
      }else if(!existing||await digestPassword(password,existing.salt)!==existing.digest)throw new Error('wrong_password');
      user={name,guest:false};
    }
    sessionStorage.setItem('af-user',JSON.stringify(user));return {user,backend};
  }
  if(path==='logout'){sessionStorage.removeItem('af-user');if(worker){worker.terminate();worker=null;}return {ok:true};}
  if(!sessionStorage.getItem('af-user'))throw new Error('sign_in_required');
  return rpc(path,payload);
}
export function getBackend(){return backend;}
export async function getTrajectory(){if(backend==='browser')return rpc('trajectory');return (await fetch('/api/trajectory')).json();}
export function download(name,value,jsonl=false){const text=jsonl?value.map(x=>JSON.stringify(x)).join('\n')+'\n':JSON.stringify(value,null,2);const url=URL.createObjectURL(new Blob([text],{type:jsonl?'application/x-ndjson':'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
