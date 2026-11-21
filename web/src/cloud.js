import {createClient} from '@supabase/supabase-js';

const url=import.meta.env.VITE_SUPABASE_URL?.trim();
const key=import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
export const cloud=url&&key?createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:true}}):null;
export const cloudEnabled=!!cloud;

export async function cloudUser(){
 if(!cloud)return null;
 const {data,error}=await cloud.auth.getSession();
 if(error)throw error;
 const user=data.session?.user;
 return user?{id:user.id,name:user.email||user.user_metadata?.name||'User',guest:false}:null;
}
export async function cloudSign(path,payload){
 if(path==='register'){
  const {data,error}=await cloud.auth.signUp({email:payload.name.trim(),password:payload.password,options:{emailRedirectTo:window.location.origin}});
  if(error)throw error;
  if(!data.session)throw Error('email_confirmation_required');
 }else{
  const {error}=await cloud.auth.signInWithPassword({email:payload.name.trim(),password:payload.password});
  if(error)throw error;
 }
 return cloudUser();
}
function localKey(){const user=JSON.parse(sessionStorage.getItem('af-user')||'null');return 'af-agent:'+String(user?.id||user?.name||'guest');}
export function storeLocalAgent(value){localStorage.setItem(localKey(),JSON.stringify(value));}
export async function saveAgent(value){
 storeLocalAgent(value);
 if(!cloud)return {cloud:false};
 const user=await cloudUser();
 if(!user)return {cloud:false};
 const {error}=await cloud.from('agent_checkpoints').upsert({user_id:user.id,name:value.name,checkpoint:value.checkpoint,updated_at:new Date().toISOString()},{onConflict:'user_id'});
 if(error)throw Error('cloud_save_failed');
 return {cloud:true};
}
export async function restoreAgent(){
 if(cloud){
  const user=await cloudUser();
  if(user){
   const {data,error}=await cloud.from('agent_checkpoints').select('name,checkpoint').eq('user_id',user.id).maybeSingle();
   if(error)throw Error('cloud_load_failed');
   if(data){storeLocalAgent(data);return data;}
  }
 }
 const raw=localStorage.getItem(localKey());
 if(!raw)throw Error('no_checkpoint');
 return JSON.parse(raw);
}
export async function removeAgent(){
 if(cloud){
  const user=await cloudUser();
  if(user){const {error}=await cloud.from('agent_checkpoints').delete().eq('user_id',user.id);if(error)throw Error('cloud_delete_failed');}
 }
 localStorage.removeItem(localKey());
}
