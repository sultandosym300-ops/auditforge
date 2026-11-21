import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {X,FileText,FlaskConical,ScanLine,ShieldCheck,Layers3} from 'lucide-react';

export default function Tutorial({t,step,onNext,onClose,busy,selector,prefix='guide',total=5}){
  const panel=useRef();const [box,setBox]=useState(null);const [size,setSize]=useState({w:370,h:300});
  useLayoutEffect(()=>{
    let target;let raf;
    function locate(){
      target=document.querySelector(selector);
      if(!target){setBox(null);return;}
      const r=target.getBoundingClientRect();
      setBox({x:Math.max(8,r.left-8),y:Math.max(8,r.top-8),w:Math.min(innerWidth-16,r.width+16),h:Math.min(innerHeight-16,r.height+16)});
    }
    function update(){cancelAnimationFrame(raf);raf=requestAnimationFrame(locate);}
    target=document.querySelector(selector);
    target?.scrollIntoView({block:'center',behavior:'instant'});
    locate();window.addEventListener('resize',update);window.addEventListener('scroll',update,true);
    const observer=new ResizeObserver(update);if(target)observer.observe(target);
    const mutation=new MutationObserver(update);mutation.observe(document.querySelector('.work-content')||document.body,{childList:true,subtree:true});
    return()=>{cancelAnimationFrame(raf);observer.disconnect();mutation.disconnect();window.removeEventListener('resize',update);window.removeEventListener('scroll',update,true);};
  },[step,selector,busy]);
  useLayoutEffect(()=>{if(panel.current){const r=panel.current.getBoundingClientRect();setSize({w:r.width,h:r.height});}},[step,t]);
  useEffect(()=>{panel.current?.querySelector('button')?.focus({preventScroll:true});},[step]);
  const vw=window.innerWidth,vh=window.innerHeight;
  let left=vw-size.w-28,top=vh-size.h-28;
  if(box){
    const right=box.x+box.w+26;
    if(right+size.w<vw-16){left=right;top=Math.max(18,Math.min(box.y,vh-size.h-18));}
    else if(box.x-size.w>35){left=box.x-size.w-26;top=Math.max(18,Math.min(box.y,vh-size.h-18));}
    else if(box.y+box.h+size.h+28<vh){left=Math.max(16,Math.min(box.x,vw-size.w-16));top=box.y+box.h+22;}
    else{left=Math.max(16,Math.min(box.x,vw-size.w-16));top=Math.max(16,box.y-size.h-22);}
  }
  const target=box?{x:box.x+box.w/2,y:box.y+box.h/2}:null;
  const anchor=target?{x:target.x<left?left:target.x>left+size.w?left+size.w:left+size.w/2,y:target.y<top?top:target.y>top+size.h?top+size.h:top+size.h/2}:null;
  const icons=[FlaskConical,Layers3,FileText,ScanLine,ShieldCheck];const Icon=icons[step];
  function key(e){if(e.key==='Escape')onClose();if(e.key==='Tab'){const list=panel.current.querySelectorAll('button:not(:disabled)');const a=list[0],b=list[list.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();b.focus();}else if(!e.shiftKey&&document.activeElement===b){e.preventDefault();a.focus();}}}
  return <div className="guided-tour" onKeyDown={key}>
    {box?<>
      <div className="tour-shade" style={{top:0,left:0,width:'100%',height:box.y}}/>
      <div className="tour-shade" style={{top:box.y+box.h,left:0,width:'100%',bottom:0}}/>
      <div className="tour-shade" style={{top:box.y,left:0,width:box.x,height:box.h}}/>
      <div className="tour-shade" style={{top:box.y,left:box.x+box.w,right:0,height:box.h}}/>
      <div className="tour-focus-frame" style={{left:box.x,top:box.y,width:box.w,height:box.h}}/>
      <svg className="tour-arrow" width="100%" height="100%" aria-hidden="true"><defs><marker id="tour-tip" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="none" stroke="#89d8f1" strokeWidth="1.5"/></marker></defs><path d={`M${anchor.x} ${anchor.y} Q${anchor.x+(target.x-anchor.x)*.7} ${anchor.y} ${target.x} ${target.y}`} fill="none" stroke="#89d8f1" strokeWidth="2" strokeDasharray="5 5" markerEnd="url(#tour-tip)"/></svg>
    </>:<div className="tour-shade full-shade"/>}
    <section ref={panel} className="guided-panel" style={{left,top}} role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="tour-top"><span>{step+1} / {total}</span><button className="icon-button" onClick={onClose} aria-label={t('close')}><X size={19}/></button></div>
      <div className="guided-title"><Icon size={24}/><h2 id="tour-title">{t(prefix+step)}</h2></div>
      <p>{t(prefix+step+'Body')}</p>
      <div className="tour-bottom"><button className="text-button" onClick={onClose}>{t('tutorialSkip')}</button><button className="button primary" disabled={busy} onClick={onNext}>{busy?t('loading'):t(prefix+step+'Action')}</button></div>
    </section>
  </div>;
}
