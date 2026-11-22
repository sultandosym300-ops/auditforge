import React,{useEffect,useState} from 'react';
import {api} from './api.js';
import {v4Text} from './v4Copy.js';
function amount(value,lang){return new Intl.NumberFormat(lang==='kk'?'kk-KZ':lang==='ru'?'ru-RU':'en-US',{style:'currency',currency:'KZT'}).format(Number(value)/100);}
export default function CausalPayment({business,lang}){
 const c=v4Text(lang),event=business?.events?.find(e=>e.type==='customer_receipt');
 const [value,setValue]=useState(''),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 useEffect(()=>{setValue(event?String((event.amount_minor/200).toFixed(2)):'');setResult(null);setError('');},[business]);
 if(!event)return null;
 async function calculate(){const minor=Math.round(Number(value)*100);if(!Number.isSafeInteger(minor)||minor<0||minor>1e12){setError(c.whatIfError);return;}setBusy(true);setError('');try{const response=await api('world_counterfactual',{event_id:event.event_id,amount_minor:minor});setResult(response);}catch(e){setError(c.whatIfError);}finally{setBusy(false);}}
 return <section className="causal-payment"><h3>{c.whatIfTitle}</h3><p>{c.whatIfBody}</p><p>{c.whatIfCurrent}: <strong>{amount(event.amount_minor,lang)}</strong></p><div className="causal-controls"><label>{c.whatIfAmount}<input type="number" min="0" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/></label><button className="button secondary causal-run" onClick={calculate} disabled={busy}>{busy?c.whatIfBusy:c.whatIfRun}</button></div>{error&&<p role="alert" className="error-message">{error}</p>}{result&&<><div className="proof-table-scroll"><table className="data-table causal-result"><thead><tr><th>{c.state}</th><th>{c.whatIfBefore}</th><th>{c.whatIfAfter}</th></tr></thead><tbody>{[['amount_minor',c.whatIfCurrent],['cash_minor',c.whatIfCash],['receivable_minor',c.whatIfReceivable]].map(([key,label])=><tr key={key}><td>{label}</td><td>{amount(result.before[key],lang)}</td><td>{amount(result.after[key],lang)}</td></tr>)}</tbody></table></div><details className="source-detail"><summary>{c.technical}</summary><pre>{JSON.stringify({event_id:event.event_id,before:result.before,after:result.after,scope:result.scope},null,2)}</pre></details></>}<p className="small-note">{c.whatIfHint}</p></section>;
}
