import React,{lazy,Suspense,useEffect,useRef,useState} from 'react';
import {useGSAP} from '@gsap/react';
import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
import {FileText,GitCompareArrows,ScanLine,ShieldCheck,Mouse} from 'lucide-react';
const EvidenceCore=lazy(()=>import('./EvidenceCore.jsx'));
gsap.registerPlugin(ScrollTrigger,useGSAP);

export default function Disassembly({t,lang,paused}){
  const [modelReady,setModelReady]=useState(false);
  const root=useRef();const progress=useRef(0);const trigger=useRef();const [stage,setStage]=useState(0);
  const icons=[FileText,GitCompareArrows,ScanLine,ShieldCheck];
  useEffect(()=>{
    const observer=new IntersectionObserver(([entry])=>{
      if(entry.isIntersecting){setModelReady(true);observer.disconnect();}
    },{rootMargin:'400px'});
    observer.observe(root.current);
    return()=>observer.disconnect();
  },[]);

  useGSAP(()=>{
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    if(reduced){progress.current=.7;return;}
    const value={p:0};
    const tween=gsap.to(value,{p:1,ease:'none',scrollTrigger:{trigger:root.current,start:'top top',end:'bottom bottom',scrub:.65,invalidateOnRefresh:true},onUpdate:()=>{
      progress.current=value.p;
      root.current.dataset.progress=value.p.toFixed(2);
      const next=Math.min(3,Math.floor(value.p*4));setStage(previous=>previous===next?previous:next);
      root.current.querySelector('.assembly-progress-fill')?.style.setProperty('transform',`scaleX(${value.p})`);
    }});
    trigger.current=tween.scrollTrigger;
    return()=>{trigger.current=null;tween.scrollTrigger?.kill();tween.kill();};
  },{scope:root,dependencies:[lang]});
  function choose(index){
    const p=(index+.22)/4;
    if(trigger.current){ScrollTrigger.refresh();window.scrollTo({top:trigger.current.start+(trigger.current.end-trigger.current.start)*p,behavior:'smooth'});}
    else{progress.current=p;setStage(index);}
  }
  const Icon=icons[stage];
  return <section className="disassembly" ref={root} id="inside" data-progress="0">
    <div className="disassembly-sticky">
      <div className="assembly-heading"><h2>{t('assemblyTitle')}</h2><p>{t('assemblyIntro')}</p></div>
      <div className="assembly-layout">
        <div className="assembly-copy" aria-live="polite">
          <div className="assembly-step-icon"><Icon size={27} strokeWidth={1.4}/></div>
          <h3 key={'title'+stage}>{t('assembly'+stage)}</h3>
          <p key={'body'+stage}>{t('assembly'+stage+'Body')}</p>
          <div className="assembly-equation"><span>{t('assembly'+stage+'Label')}</span><strong>{['500.00 USD','500 × 490.60','245 300 KZT','4 700 KZT'][stage]}</strong><span>{t('assembly'+stage+'Note')}</span></div>
        </div>
        <div className="assembly-model">{modelReady&&<Suspense fallback={null}><EvidenceCore progressRef={progress} paused={paused} lang={lang}/></Suspense>}<span className="assembly-model-note">{t('conceptModel')}</span></div>
      </div>
      <div className="assembly-controls"><div className="assembly-tabs" role="tablist" aria-label={t('assemblyTitle')}>{icons.map((StepIcon,i)=><button key={i} role="tab" aria-selected={stage===i} className={stage===i?'active':''} onClick={()=>choose(i)}><StepIcon size={17}/><span>{t('assembly'+i)}</span></button>)}</div><div className="assembly-progress"><span className="assembly-progress-fill"/></div><p><Mouse size={14}/>{t('scrollDisassemble')}</p></div>
    </div>
  </section>;
}
