import React from 'react';
import {FileText,Wallet,RefreshCw,ShieldCheck,ScanLine} from 'lucide-react';
export default function Finale({t,onEnter}){
  return <section className="finale" id="begin">
    <div className="finale-aura" aria-hidden="true"/>
    <div className="finale-proof" aria-hidden="true">
      <svg viewBox="0 0 1000 270" fill="none"><path className="proof-route" d="M140 62C320 62 310 205 500 205M500 40V205M860 62C680 62 690 205 500 205"/><path className="proof-route-light" d="M140 62C320 62 310 205 500 205M500 40V205M860 62C680 62 690 205 500 205"/><circle cx="500" cy="205" r="35" fill="#10232e" stroke="#6aa7bd"/><path d="m487 205 9 9 18-20" stroke="#9fddd4" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg>
      <span className="proof-source source-invoice"><FileText size={20}/>{t('invoices')}</span><span className="proof-source source-payment"><Wallet size={20}/>{t('payments')}</span><span className="proof-source source-fx"><RefreshCw size={20}/>{t('fx')}</span>
    </div>
    <div className="finale-copy"><h2>{t('cta').split('\n').map((line,i)=><React.Fragment key={i}>{i>0&&<br/>}{line}</React.Fragment>)}</h2><p>{t('finaleBody')}</p><button className="button finale-button" onClick={onEnter}><ScanLine size={20}/>{t('start')}</button><div className="finale-footnote"><ShieldCheck size={16}/>{t('finaleNote')}</div></div>
    <div className="finale-horizon" aria-hidden="true"/>
  </section>;
}
