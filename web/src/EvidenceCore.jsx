import React,{useEffect,useRef} from 'react';
import {CheckCircle2} from 'lucide-react';
import './OriginalCards.css';

// Original financial document cards from the first landing-page revision.
export default function EvidenceCore({progressRef,paused=false}){
 const host=useRef(null);
 useEffect(()=>{
  const element=host.current;
  let frame;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const cards=[...element.querySelectorAll('.original-card')];
  function render(){
   frame=requestAnimationFrame(render);
   const p=reduced?0:Math.max(0,Math.min(1,progressRef?.current||0));
   cards.forEach((card,index)=>{
    const offset=2-index;
    card.style.transform='translate3d('+(offset*p*48)+'px,'+(-offset*p*72)+'px,'+(-offset*24)+'px) rotateY(-15deg) rotateX(8deg) rotate('+(offset*p*7)+'deg)';
   });
   element.dataset.ready='true';
  }
  render();
  return()=>cancelAnimationFrame(frame);
 },[progressRef,paused]);
 return <div className="scanner evidence-core original-document-cards" ref={host} role="img" aria-label="FX POLICY, PAYMENT, JOURNAL ENTRY">
  <div className="original-card-stage">
   <div className="original-card original-policy"><span>FX POLICY</span><b>490.60</b><i/><i/><i/></div>
   <div className="original-card original-payment"><span>PAYMENT</span><b>USD 500.00</b><i/><i/><i/></div>
   <div className="original-card original-journal"><span>JOURNAL ENTRY</span><b>₸ 245 300</b><i/><i/><i/><div className="original-linked"><CheckCircle2 size={18}/> VERIFIED CONNECTION</div></div>
  </div>
 </div>;
}
