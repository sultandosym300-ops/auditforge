import React,{lazy,Suspense,useEffect,useRef,useState} from 'react';
import {useGSAP} from '@gsap/react';
import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
import {Layers3,ArrowUpRight,Plus,X,Search,Play,Pause,FileText,Check,ChevronRight,ChevronLeft,Download,LogOut,BookOpen,ScanLine,FolderOpen,ShieldCheck,FlaskConical,RotateCcw,CheckCircle2,Calculator,Trash2,HelpCircle} from 'lucide-react';
import Disassembly from './Disassembly.jsx';
import Finale from './Finale.jsx';
import Tutorial from './Tutorial.jsx';
import WorldExplorer,{PlatformIntro} from './WorldExplorer.jsx';
import ProofCenter,{ErrorExplainer} from './ProofCenter.jsx';
import {v4Text} from './v4Copy.js';
const TrainingLab=lazy(()=>import('./TrainingLab.jsx'));
const Scanner=lazy(()=>import('./Scanner.jsx'));
import {cloudEnabled} from './cloud.js';
import {dictionaries,issueTypes} from './i18n.js';
import {api,detectBackend,getBackend,getTrajectory,download} from './api.js';
gsap.registerPlugin(ScrollTrigger,useGSAP);
const tabs=['trainingLab','episodes','records','documents','findings','trajectories','evaluation'];
const iconByTab=[FlaskConical,FlaskConical,Layers3,FolderOpen,ScanLine,BookOpen,ShieldCheck];
const br=text=>text.split('\n').map((s,i)=><React.Fragment key={i}>{i>0&&<br/>}{s}</React.Fragment>);
const format=(n,currency='KZT',lang='ru')=>new Intl.NumberFormat(lang==='kk'?'kk-KZ':lang==='ru'?'ru-RU':'en-US',{style:'currency',currency,maximumFractionDigits:2}).format(Number(n)/10**(currency==='JPY'?0:2));

function Brand({onClick}){return <button className="brand" onClick={onClick} aria-label="AuditForge"><img className="brand-symbol" src="/brand.svg" width="36" height="36" alt="" aria-hidden="true"/>AuditForge</button>;}
function Language({lang,setLang}){return <select className="language" aria-label="Language / Язык / Тіл" value={lang} onChange={e=>setLang(e.target.value)}><option value="ru">RU</option><option value="kk">ҚАЗ</option><option value="en">EN</option></select>;}

function Landing({t,lang,setLang,onEnter}){
  const scope=useRef();const video=useRef();const [paused,setPaused]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);const [quote,setQuote]=useState(0);
  useGSAP(()=>{
    const mm=gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)',()=>{
      gsap.from('.hero-copy',{y:28,duration:1.1,ease:'power3.out'});
      gsap.from('.hero-model',{y:35,duration:1.5,ease:'power3.out',delay:.1});
      gsap.to('.hero-model',{y:95,scale:1.08,scrollTrigger:{trigger:'.hero',start:'top top',end:'bottom top',scrub:1.1},ease:'none'});
      gsap.utils.toArray('.reveal').forEach(el=>gsap.from(el,{y:35,duration:1,ease:'power3.out',scrollTrigger:{trigger:el,start:'top 88%'}}));
      gsap.fromTo('.city-media video',{scale:1.08},{scale:1,ease:'none',scrollTrigger:{trigger:'.cinema',start:'top bottom',end:'bottom top',scrub:1}});
    });
    return()=>mm.revert();
  },{scope,dependencies:[lang]});
  useEffect(()=>{scope.current?.querySelectorAll('video').forEach(v=>{if(paused)v.pause();else v.play().catch(()=>{});});},[paused]);
  return <main ref={scope} className="landing" data-paused={paused}>
    <header className="site-header"><div className="nav-inner"><Brand onClick={()=>window.scrollTo({top:0,behavior:'smooth'})}/><nav aria-label={t('overview')}><a href="#capabilities">{t('capabilities')}</a><a href="#workflow">{t('workflow')}</a></nav><div className="nav-actions"><Language lang={lang} setLang={setLang}/><button className="button small primary" onClick={onEnter}>{t('enter')}</button></div></div></header>
    <section className="hero">
      <div className="hero-model"><Suspense fallback={<div className="model-loading"/>}><Scanner paused={paused}/></Suspense></div>
      <div className="hero-copy"><h1 className="max-w-6xl">{t('heroA')}<br/><span>{t('heroB')}</span></h1><p className="hero-sub">{t('heroSub')}</p><p className="hero-description">{t('heroBody')}</p><div className="hero-ctas"><button className="button primary" onClick={onEnter}>{t('start')}</button><a className="text-link" href="#capabilities">{t('explore')}<span className="link-plus">+</span></a></div></div>
      <div className="hero-bottom"><span className="model-hint"><ScanLine size={17}/>{t('modelHint')}</span><button className="motion-control" onClick={()=>setPaused(!paused)} aria-label={t(paused?'play':'pause')}>{paused?<Play size={15}/>:<Pause size={15}/>}</button></div>
    </section>
    <section id="capabilities" className="features section-pad"><div className="section-heading reveal"><h2>{br(t('featureTitle'))}</h2><p>{t('featureBody')}</p></div>
      <div className="bento-grid">
        <article className="feature large company-feature reveal"><div><h3>{br(t('feat1'))}</h3><p>{t('feat1body')}</p></div><div className="document-fan" aria-hidden="true"><div className="fan-paper back-paper"><FileText size={34}/><i/><i/><i/><i/></div><div className="fan-paper mid-paper"><span>PAYMENT</span><b>₸ 245 000</b><i/><i/><i/></div><div className="fan-paper front-paper"><span>INVOICE</span><b>₸ 490 000</b><i/><i/><div className="paper-sign">AuditForge</div></div></div></article>
        <article className="feature proof-feature reveal"><ShieldCheck size={43} strokeWidth={1.25}/><h3>{br(t('feat2'))}</h3><p>{t('feat2body')}</p><div className="evidence-lines"><span><Check size={16}/> invoice.json</span><span><Check size={16}/> payment.json</span><span><Check size={16}/> ledger.csv</span></div></article>
        <article className="feature repeat-feature reveal"><div className="repeat-symbol" aria-hidden="true"><RotateCcw size={75} strokeWidth={.8}/></div><h3>{br(t('feat3'))}</h3><p>{t('feat3body')}</p></article>
        <article className="feature large interaction-feature reveal"><video muted playsInline autoPlay={!paused} loop preload="metadata" aria-hidden="true" poster="/media/city-hq-poster.jpg" src="/media/city-hq.webm"/><div className="video-shade"/><div><h3>{br(t('feat4'))}</h3><p>{t('feat4body')}</p></div><div className="floating-record" aria-hidden="true"><span>USD / KZT</span><b>31 OCT · 23:59</b><div><span>PAYMENT</span><CheckCircle2 size={21}/></div></div></article>
      </div>
    </section>
    <div className="type-marquee" aria-hidden="true"><div>{[...issueTypes,...issueTypes,...issueTypes].map((type,i)=><span key={i}>{t(type)}<span className="marquee-separator">/</span></span>)}</div></div>
    <Disassembly t={t} lang={lang} paused={paused}/>
    <section id="workflow" className="workflow-section section-pad"><div className="section-heading reveal"><h2>{t('inspectTitle')}</h2></div><div className="workflow-steps">{[1,2,3].map((n)=><article key={n} className="workflow-step reveal"><div className="step-icon">{n===1?<FlaskConical/>:n===2?<ScanLine/>:<ShieldCheck/>}</div><h3>{t('chapter'+n)}</h3><p>{t('chapter'+n+'body')}</p></article>)}</div></section>
    <section className="cinema"><div className="city-media"><video ref={video} autoPlay={!paused} muted playsInline loop preload="metadata" poster="/media/night-hq-poster.jpg" src="/media/night-hq.webm"/><div className="cinema-shade"/><div className="cinema-text"><blockquote>{t(quote===0?'proofQuote':quote===1?'feat3body':'sceneBody')}</blockquote><p>{t('proofAttribution')}</p><div className="quote-controls"><button aria-label={t('back')} onClick={()=>setQuote((quote+2)%3)}><ChevronLeft size={22}/></button><button aria-label={t('tutorialNext')} onClick={()=>setQuote((quote+1)%3)}><ChevronRight size={22}/></button></div></div><button className="motion-control video-motion" onClick={()=>setPaused(!paused)} aria-label={t(paused?'play':'pause')}>{paused?<Play size={17}/>:<Pause size={17}/>}</button></div></section>
    <Finale t={t} onEnter={onEnter}/>
    <footer><div><Brand onClick={()=>window.scrollTo({top:0,behavior:'smooth'})}/><p>{t('footer')}</p></div><div><p>{t('fiction')}</p><span>AuditForge · 2026</span></div></footer>
  </main>;
}

function Auth({t,lang,setLang,onBack,onSuccess}){
  const [mode,setMode]=useState('register');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  async function sign(path,payload){setBusy(true);setError('');try{const result=await api(path,payload);onSuccess(result.user);}catch(e){setError(t(e.message==='email_confirmation_required'?'confirmEmail':e.message==='name_taken'?'nameTaken':'authError'));}finally{setBusy(false);}}
  return <main className="auth-page"><header className="site-header"><div className="nav-inner"><Brand onClick={onBack}/><Language lang={lang} setLang={setLang}/></div></header><div className="auth-layout"><section className="auth-form"><button className="back-link" onClick={onBack}><ChevronLeft size={16}/>{t('back')}</button><h1>{br(t('authTitle'))}</h1><p>{t('authBody')}</p><div className="segmented">{['register','login'].map(m=><button key={m} onClick={()=>{setMode(m);setError('');}} className={mode===m?'active':''}>{t(m)}</button>)}</div><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);sign(mode,{name:f.get('name'),password:f.get('password')});}}><label>{cloudEnabled?'Email':t('username')}<input name="name" type={cloudEnabled?'email':'text'} autoComplete="username" required minLength={3} maxLength={254} placeholder={cloudEnabled?'name@example.com':'researcher'}/></label><label>{t('password')}<input name="password" type="password" autoComplete={mode==='register'?'new-password':'current-password'} required minLength={8} maxLength={128} placeholder={t('passwordHint')}/></label>{error&&<p className="error-message" role="alert">{error}</p>}<button className="button primary full" disabled={busy}>{busy?t('loading'):t(mode==='register'?'createAccount':'login')}</button></form><div className="auth-divider"/><button className="button secondary full" disabled={busy} onClick={()=>sign('guest',{})}>{t('guest')}</button><p className="auth-note">{t(cloudEnabled?'cloudProfile':getBackend()==='browser'?'localProfile':'localServer')}</p></section></div></main>;
}

function FocusDialog({className,onClose,returnFocus,suspended=false,children}){
  const root=useRef();const close=useRef(onClose);close.current=onClose;
  useEffect(()=>{
    if(suspended)return;
    const previous=returnFocus||document.activeElement;
    const background=Array.from(document.querySelectorAll('.workspace-header,.work-content'));
    background.forEach(el=>el.inert=true);
    const controls=()=>Array.from(root.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')).filter(el=>el.getClientRects().length);
    controls()[0]?.focus();
    function key(e){
      if(e.key==='Escape'){e.preventDefault();close.current();}
      if(e.key==='Tab'){
        const list=controls();const first=list[0],last=list[list.length-1];
        if(!first){e.preventDefault();return;}
        if(e.shiftKey&&(document.activeElement===first||!root.current.contains(document.activeElement))){e.preventDefault();last.focus();}
        else if(!e.shiftKey&&(document.activeElement===last||!root.current.contains(document.activeElement))){e.preventDefault();first.focus();}
      }
    }
    document.addEventListener('keydown',key);
    return()=>{document.removeEventListener('keydown',key);background.forEach(el=>el.inert=false);if(previous?.isConnected)previous.focus();};
  },[suspended]);
  return <div ref={root} className={className} onClick={e=>{if(e.target===e.currentTarget)close.current();}}>{children}</div>;
}

function Workspace({t,lang,setLang,user,onLogout,onHome}){
  const dialogTrigger=useRef();const pageRef=useRef();const trainingControls=useRef();const demoConfig=useRef();
  const c=v4Text(lang);
  const [profile,setProfile]=useState('compact'),[businessType,setBusinessType]=useState('logistics');
  const [story,setStory]=useState(null),[explanation,setExplanation]=useState(null),[proof,setProof]=useState(null),[demo,setDemo]=useState(null),[demoBusy,setDemoBusy]=useState(false);
  const [trainingVisited,setTrainingVisited]=useState(true);
  const [tourMode,setTourMode]=useState('training');
  const [tab,setTab]=useState('trainingLab');const [tour,setTour]=useState(()=>sessionStorage.getItem('af-tour-session')?null:0);
  useEffect(()=>{if(tab==='trainingLab')setTrainingVisited(true);},[tab]);
  const [initial,setInitial]=useState(null);const [remaining,setRemaining]=useState(100);const [done,setDone]=useState(false);const [truncated,setTruncated]=useState(false);const [report,setReport]=useState(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [scenario,setScenario]=useState('mixed');const [seed,setSeed]=useState('');const [table,setTable]=useState('ledger');const [rows,setRows]=useState([]);const [cursor,setCursor]=useState(null);const [page,setPage]=useState(1);const [search,setSearch]=useState('');const [detail,setDetail]=useState(null);const [evidence,setEvidence]=useState([]);const [findings,setFindings]=useState([]);const [editing,setEditing]=useState(false);const [trajectory,setTrajectory]=useState([]);const [policy,setPolicy]=useState('reconciliation');const [calc,setCalc]=useState('');const [calcResult,setCalcResult]=useState('');
  useEffect(()=>{window.scrollTo(0,0);},[tab]);
  useEffect(()=>{if(!matchMedia('(prefers-reduced-motion: reduce)').matches&&pageRef.current){const anim=gsap.fromTo(pageRef.current,{y:10},{y:0,duration:.24,ease:'power2.out'});return()=>anim.kill();}},[tab]);
  async function work(fn){if(busy)return;setBusy(true);setError('');try{return await fn();}catch(e){setError(t('requestError'));}finally{setBusy(false);}}
  function observe(value){if(value.observation?.steps_remaining!==undefined)setRemaining(value.observation.steps_remaining);if(value.terminated||value.truncated){setDone(true);setTruncated(!!value.truncated);}if(value.report)setReport(value.report);if(value.observation?.error)setError(t('requestError'));}
  async function refreshLog(){const log=await getTrajectory();setTrajectory(log);return log;}
  const action=async a=>{const value=await api('step',{action:a});observe(value);await refreshLog();return value;};
  async function create(options={}){return work(async()=>{
    if(initial&&!done&&!options.tutorial&&!confirm(t('confirmNew')))return;
    const config=options.configOverride||(scenario==='recognition'?{recognition_world:'blind'}:{clean:scenario==='clean',interaction:scenario==='interact1'?1:scenario==='interact2'?2:0});
    if(!options.configOverride&&profile==='realistic_v1'){config.profile=profile;config.business_type=businessType;}
    const payload={config};if(options.seedOverride!==undefined)payload.seed=options.seedOverride;else if(seed!=='')payload.seed=Number(seed);
    const value=await api('reset',payload);setInitial(value.observation);setRemaining(100);setDone(false);setTruncated(false);setReport(null);setRows([]);setCursor(null);setDetail(null);setEvidence([]);setFindings([]);setTrajectory([]);setPage(1);setExplanation(null);setTab('episodes');setStory(await api('world_story'));return value.observation;
  });}
  async function load(which=table,next=false){return work(async()=>{const value=await action({tool:'list_records',table:which,cursor:next?cursor:null,limit:50});if(value.observation.result){setRows(value.observation.result.records);setCursor(value.observation.result.next_cursor);setTable(which);setPage(next?page+1:1);setSearch('');}return value.observation.result;});}
  async function inspect(row){const id=row.doc_id||row.row_id;dialogTrigger.current=Array.from(document.querySelectorAll('.table-open')).find(b=>b.getAttribute('aria-label')===t('inspect')+' '+id)||document.activeElement;return work(async()=>{const value=await action(row.doc_id?{tool:'get_document',doc_id:id}:{tool:'get_record',table,id});if(value.observation.result)setDetail(value.observation.result);return value.observation.result;});}
  async function run(){return await work(async()=>{const value=await api('run',{policy});const last=value.trajectory?.at(-1);const terminal=value.result||(last?[last.observation,last.reward,last.terminated,last.truncated,{}]:null);if(terminal){setRemaining(terminal[0].steps_remaining);setDone(terminal[2]||terminal[3]);setTruncated(terminal[3]);}setReport(value.report);const log=value.trajectory||await refreshLog();setTrajectory(log);const submit=log.findLast(x=>x.action.tool==='submit');if(submit)setFindings(submit.action.findings.findings);setTab('findings');return value;});}
  async function submit(){await work(async()=>{await action({tool:'submit',findings:{episode_id:initial.manifest.episode_id,findings}});});}
  function pin(){const id=detail.doc_id||detail.row_id;if(!evidence.includes(id)&&evidence.length<10)setEvidence([...evidence,id]);}
  async function reveal(){return work(async()=>{const result=await api('demo_explain',{demo:true});setExplanation(result);return result;});}
  async function runProof(proofSeed=2026112204){return work(async()=>{const result=await api('proof_suite',{seed:proofSeed});setProof(result);return result;});}
  async function startDemo(){if(busy||demoBusy)return;setTour(null);setDetail(null);setEditing(false);setDemoBusy(true);setError('');try{const config={profile:'realistic_v1',business_type:businessType,interaction:1};const chosen=seed===''?2026112204:Number(seed);demoConfig.current={config,seed:chosen};const result=await create({tutorial:true,configOverride:config,seedOverride:chosen});if(result)setDemo(0);}finally{setDemoBusy(false);}}
  async function readyTraining(){for(let attempt=0;attempt<100;attempt++){await new Promise(resolve=>setTimeout(resolve,25));if(trainingControls.current&&!trainingControls.current.running)return trainingControls.current;}throw new Error('training_not_ready');}
  async function nextDemo(){if(busy||demoBusy)return;setDemoBusy(true);setError('');try{
    if(demo===0){setTab('episodes');setDemo(1);}
    else if(demo===1){const same=demoConfig.current;const created=await create({tutorial:true,configOverride:same.config,seedOverride:same.seed});if(!created)return;const executed=await run();if(executed?.report){setTab('trajectories');setDemo(2);}}
    else if(demo===2){setTab('findings');setDemo(3);}
    else if(demo===3){const result=await reveal();if(result){setTab('findings');setDemo(4);}}
    else if(demo===4){const result=await runProof();if(result){setTab('evaluation');setDemo(5);}}
    else if(demo===5){setTab('trainingLab');const control=trainingControls.current;if(!control||control.running)return;const created=await control.create({world_profile:'realistic_v1',business_type:demoConfig.current.config.business_type});if(!created)return;const ready=await readyTraining();const trained=await ready.train(10);if(!trained)return;const finished=await readyTraining();const evaluated=await finished.evaluate();if(evaluated)setDemo(6);}
    else setDemo(null);
  }catch(e){setError(t('requestError'));}finally{setDemoBusy(false);}}
  const filtered=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(search.toLowerCase()));
  const episodeId=initial?.manifest.episode_id;
  function beginTour(){setDetail(null);setEditing(false);setTourMode('manual');setTab('episodes');setTour(0);}
  function closeTour(){setDetail(null);setEditing(false);setTour(null);setTab(tourMode==='training'?'trainingLab':'episodes');sessionStorage.setItem('af-tour-session','1');}
  async function advanceTour(){
    if(busy)return;
    if(tourMode==='training'){const control=trainingControls.current;if(!control||control.running)return;setBusy(true);try{const success=await (tour===0?control.create():tour===1?control.train(10):control.evaluate());if(success){if(tour<2)setTour(tour+1);else closeTour();}}finally{setBusy(false);}return;}
    if(tour===0){
      if(!initial||done){const created=await create({tutorial:true});if(!created)return;}
      setTab('records');const result=await load('ledger');if(result?.records?.length)setTour(1);
    }else if(tour===1){if(rows[0]&&await inspect(rows[0]))setTour(2);}
    else if(tour===2){if(detail)pin();setDetail(null);setTab('findings');setEditing(true);setTour(3);}
    else if(tour===3){setEditing(false);setTour(4);}
    else{const fresh=await create({tutorial:true});if(fresh)closeTour();}
  }
  const tourSelectors=['.episode-config .button.primary','.data-table tbody tr:first-child','.record-drawer .button.primary','.finding-editor select[name="type"]','.submission-bar .button.primary'];
  const activeTourTab=null;
  return <main className="workspace">
    <header className="workspace-header"><div className="workspace-top"><Brand onClick={onHome}/><div className="workspace-account"><Language lang={lang} setLang={setLang}/><button className="help-button" aria-label={t('help')} onClick={beginTour}><HelpCircle size={17}/><span>{t('help')}</span></button><span className="avatar">{user.name.charAt(0).toUpperCase()}</span><span className="username">{user.guest?t('guest').replace('Продолжить как ',''):user.name}</span><button className="icon-button" onClick={onLogout} aria-label={t('logout')}><LogOut size={17}/></button></div></div>
      <nav className="workspace-tabs" aria-label={t('workspace')}>{tabs.map((name,i)=>{const Icon=iconByTab[i];return <button key={name} onClick={()=>{setTab(name);if(name==='documents'){setRows([]);setTable('invoices');}}} className={(tab===name?'active ':'')+(activeTourTab===name?'tour-target':'')} aria-current={tab===name?'page':undefined}><Icon size={18}/>{t(name)}{name==='findings'&&findings.length>0&&<span>{findings.length}</span>}</button>;})}</nav>
    </header>
    <div className="work-content" ref={pageRef}><div className="work-context"><span>{t('training')}</span><span>{t(getBackend()==='browser'?'browserMode':'nativeMode')}</span></div>
      <PlatformIntro lang={lang} onDemo={startDemo} busy={busy||demoBusy}/>
      {demo!==null&&<section className="demo-panel" aria-live="polite"><div className="demo-panel-header"><span>{c.demoTitle} · {demo+1} / 7</span><button className="text-button" onClick={()=>setDemo(null)} disabled={demoBusy}>{c.demoClose}</button></div><ol>{c.demoSteps.map((step,i)=><li className={i===demo?'active':''} key={step}>{i+1}. {step}</li>)}</ol><h2>{c.demoSteps[demo]}</h2><p>{c.demoBodies[demo]}</p>{demo===1&&<p className="small-note">{c.demoRefresh}</p>}<button className="button primary demo-next" disabled={busy||demoBusy} onClick={nextDemo}>{busy||demoBusy?t('loading'):demo===6?c.demoFinish:c.demoNext}</button></section>}
      {error&&<div className="error-banner" role="alert">{error}<button className="icon-button" onClick={()=>setError('')} aria-label={t('close')}><X size={16}/></button></div>}
      {busy&&<div className="loading-strip" role="status"><span/>{t('loading')}</div>}
      <div style={{display:tab==='trainingLab'?'block':'none'}}>{trainingVisited&&<Suspense fallback={<p role="status">{t('loading')}</p>}><TrainingLab controlsRef={trainingControls} lang={lang} hasEpisode={!!initial&&!done} onInvestigation={value=>{const last=value.trajectory?.at(-1);const terminal=value.result||(last?[last.observation,last.reward,last.terminated,last.truncated,{}]:null);if(terminal){setRemaining(terminal[0].steps_remaining);setDone(terminal[2]||terminal[3]);setTruncated(terminal[3]);}setReport(value.report);setTrajectory(value.trajectory||[]);const submit=value.trajectory?.findLast(x=>x.action.tool==='submit');if(submit)setFindings(submit.action.findings.findings);setTab('findings');}}/></Suspense>}</div>
      {tab==='episodes'&&<>
        <div className="work-heading"><div><h1>{t(initial?'episodes':'welcome')}</h1><p>{t(initial?'nextBody':'welcomeBody')}</p></div>{initial&&<div className="budget"><b>{remaining}</b><span>{t('remaining')}</span></div>}</div>
        <div className="episode-layout"><section className="episode-config"><div className="panel-title"><FlaskConical size={22}/><h2>{t(initial?'newEpisode':'createEpisode')}</h2></div><label>{c.profile}<select className="world-profile-select" value={profile} onChange={e=>{setProfile(e.target.value);if(e.target.value==='realistic_v1'&&scenario==='recognition')setScenario('mixed');}}><option value="compact">{c.compact}</option><option value="realistic_v1">{c.realistic}</option></select></label>{profile==='realistic_v1'&&<label>{c.businessType}<select className="business-type-select" value={businessType} onChange={e=>setBusinessType(e.target.value)}>{Object.entries(c.types).map(([key,name])=><option value={key} key={key}>{name}</option>)}</select></label>}<label>{t('difficulty')}<select value={scenario} onChange={e=>setScenario(e.target.value)}>{['mixed','recognition','clean','interact1','interact2'].filter(k=>profile!=='realistic_v1'||k!=='recognition').map(k=><option key={k} value={k}>{t(k)}</option>)}</select></label>{scenario==='recognition'&&<p className="small-note">{t('recognitionHint')}</p>}<label>{t('seed')}<input type="number" min="0" max="4294967295" value={seed} onChange={e=>setSeed(e.target.value)} placeholder={t('optionalSeed')}/></label><button className="button primary full" onClick={tour===0?advanceTour:create} disabled={busy}><Plus size={18}/>{t('createEpisode')}</button>{getBackend()==='browser'&&<p className="small-note">{t('browserHint')}</p>}</section>
          {initial?<section className="episode-overview"><div className="company-heading"><div className="company-icon"><Layers3 size={29}/></div><div><h2>{initial.manifest.company}</h2><span className="code-id">{episodeId}</span></div><span className={'state-badge '+(done?'completed':'')}>{done?t(truncated?'truncated':'finished'):t('training')}</span></div><div className="episode-facts"><div><span>{t('period')}</span><b>{initial.manifest.period_start.slice(0,10)} — {initial.manifest.period_end.slice(0,10)}</b></div><div><span>{t('currency')}</span><b>{initial.manifest.base_currency}</b></div><div><span>{t('records')}</span><b>{initial.manifest.records}</b></div><div><span>{t('documents')}</span><b>{initial.manifest.documents}</b></div></div><div className="next-action"><h3>{t('nextAction')}</h3><p>{t('nextBody')}</p><div className="next-buttons"><button className="button secondary" disabled={busy||done} onClick={()=>{setTab('records');load('ledger');}}><Layers3 size={17}/>{t('openRecords')}</button><button className="button primary" disabled={busy||done} onClick={run}><Play size={16}/>{t('runAgent')}</button></div></div></section>:<section className="episode-empty"><div className="empty-orbit"><div className="empty-paper"><FileText size={38} strokeWidth={1}/><span/><span/><span/></div><div className="empty-lens"><ScanLine size={44} strokeWidth={1}/></div></div><h2>{t('heroB')}</h2><p>{t('chapter1body')}</p><div className="empty-path"><span>{t('episodes')}</span><ChevronRight size={15}/><span>{t('evidence')}</span><ChevronRight size={15}/><span>{t('evaluation')}</span></div></section>}
        </div>
        {initial&&<WorldExplorer key={episodeId} story={story} lang={lang}/>}
      </>}
      {tab!=='episodes'&&tab!=='evaluation'&&tab!=='trainingLab'&&<div className="work-heading"><div><h1>{t(tab)}</h1><p>{episodeId||t('noEpisode')}</p></div>{initial&&<div className="budget compact"><b>{remaining}</b><span>{t('remaining')}</span></div>}</div>}
      {['records','documents'].includes(tab)&&initial&&<>
        <div className="data-toolbar"><div className="table-tabs">{(tab==='records'?['ledger','invoices','payments','fx']:['invoices','payments']).map(name=><button className={table===name?'active':''} key={name} disabled={busy||done} onClick={()=>load(name)}>{t(name)}</button>)}</div><div className="data-actions"><label className="search-input"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={t('search')}/></label><button className="button secondary small" onClick={()=>load()} disabled={busy||done}>{t('loadRecords')}</button></div></div>
        {rows.length?<><div className="data-table-wrap"><table className="data-table"><thead><tr><th>{t('record')}</th><th>{t('time')}</th><th>{t(table==='ledger'?'account':'currency')}</th><th>{t('amount')}</th><th/></tr></thead><tbody>{filtered.map((r,i)=>{const id=r.row_id||r.doc_id;const amount=r.total_minor??r.amount_minor??(r.debit_minor-r.credit_minor);return <tr key={id||i} onClick={()=>!busy&&!done&&(tour===1?advanceTour():inspect(r))}><td><span className="record-id">{id}</span>{r.invoice_id&&<span className="secondary-id">{r.invoice_id}</span>}</td><td>{(r.timestamp||r.issued_at||r.date||'').replace('T',' ').slice(0,19)}</td><td>{r.account||r.currency||r.source_currency+' / '+r.target_currency}</td><td className="numeric">{r.rate||format(amount,r.currency,lang)}</td><td><button className="table-open" disabled={busy||done} onClick={e=>{e.stopPropagation();if(tour===1)advanceTour();else inspect(r);}} aria-label={t('inspect')+' '+id}><ChevronRight size={17}/></button></td></tr>;})}</tbody></table>{!filtered.length&&<p className="empty-inline">{t('noResults')}</p>}</div><div className="table-footer"><span>{t('page')} {page} · {rows.length} {t('records').toLowerCase()}</span><button className="button secondary small" disabled={!cursor||busy||done} onClick={()=>load(table,true)}>{t('nextPage')}</button></div></>:<div className="blank-panel"><FolderOpen size={42} strokeWidth={1}/><h2>{t(tab==='documents'?'documents':'records')}</h2><p>{t(tab==='documents'?'emptyDocs':'chapter2body')}</p><button className="button primary" disabled={busy||done} onClick={()=>load(tab==='documents'?'invoices':'ledger')}>{t('loadRecords')}</button></div>}
        <div className="calculator-bar"><Calculator size={19}/><label>{t('calculator')}<input value={calc} onChange={e=>setCalc(e.target.value)} placeholder={t('expression')}/></label><button className="button secondary small" disabled={busy||done||!calc} onClick={()=>work(async()=>{const value=await action({tool:'calculator',expression:calc});if(value.observation.result!==undefined)setCalcResult(value.observation.result);})}>{t('calculate')}</button><output>{calcResult}</output></div><p className="small-note">{t('baseHint')}</p>
      </>}
      {tab==='findings'&&initial&&<>
        {report&&<section className="report-panel"><div className="report-title"><CheckCircle2 size={24}/><h2>{t(truncated?'truncated':'finished')}</h2></div><div className="report-metrics">{[['precision','precision'],['recall','recall'],['F1','f1'],['reward','reward']].map(([label,key])=><div key={key}><span>{label==='F1'?'F1':t(label)}</span><b>{Number(report[key]).toFixed(3)}</b></div>)}</div><div className="report-counts">TP {report.tp} · FP {report.fp} · FN {report.fn} · {100-remaining} / 100 {t('steps').toLowerCase()}</div></section>}
        {done&&<><button className="button secondary explain-result" disabled={busy} onClick={reveal}>{c.explain}</button><ErrorExplainer value={explanation} lang={lang} t={t}/></>}
        <div className="findings-toolbar"><span>{findings.length} / 30</span><div><button className="button secondary small" onClick={()=>download('findings.json',{episode_id:episodeId,findings})}><Download size={16}/>{t('exportFindings')}</button><button className="button primary small" disabled={busy||done||findings.length>=30} onClick={()=>setEditing(true)}><Plus size={17}/>{t('addFinding')}</button></div></div>
        {findings.length?<div className="finding-list">{findings.map((f,i)=><article className="finding-row" key={i}><div className="finding-icon"><ScanLine size={21}/></div><div><h3>{t(f.type)}</h3><p>{f.explanation==='Source documents and accounting policy disagree with the recorded posting.'?t('sceneBody'):f.explanation}</p><span>{f.affected_ids.join(', ')}</span><div className="evidence-tags">{f.evidence_ids.map(id=><code key={id}>{id}</code>)}</div></div><b>{format(f.claimed_amount_minor,f.currency,lang)}</b>{!done&&<button className="icon-button" aria-label={t('delete')} onClick={()=>setFindings(findings.filter((_,j)=>j!==i))}><Trash2 size={17}/></button>}</article>)}</div>:<div className="blank-panel compact-blank"><ScanLine size={42} strokeWidth={1}/><p>{t('emptyFindings')}</p></div>}
        {!done&&<div className="submission-bar"><div><h3>{t('submit')}</h3><p>{t('chapter3body')}</p></div><button className="button primary" disabled={busy} onClick={submit}>{t('submit')}</button></div>}
        {!done&&<div className="policy-bar"><label>{t('policy')}<select value={policy} onChange={e=>setPolicy(e.target.value)}><option value="reconciliation">{t('runAgent')}</option><option value="random">{t('runRandom')}</option>{initial?.manifest?.financial_profile==='realistic_v1'&&<option value="corroboration">{lang==='ru'?'Проверка связанных источников':lang==='kk'?'Байланысты дереккөздерді тексеру':'Corroborate linked sources'}</option>}<option value="mark_all">{t('runAttack')}</option></select></label><button className="button secondary" disabled={busy} onClick={run}><Play size={16}/>{t('runAgent')}</button></div>}
      </>}
      {tab==='trajectories'&&<><div className="trajectory-toolbar"><span>{trajectory.length} {t('steps').toLowerCase()}</span><button className="button secondary small" onClick={()=>download('trajectories.jsonl',trajectory,true)} disabled={!trajectory.length}><Download size={16}/>{t('downloadTrajectory')}</button></div>{trajectory.length?<div className="trajectory-list">{trajectory.map((row,i)=><details key={i}><summary><span className="trajectory-step">{row.step}</span><code>{row.action.tool}</code><span>{row.action.table||''}</span><span>{row.terminated?t('finished'):row.truncated?t('truncated'):''}</span><ChevronRight size={16}/></summary><pre>{JSON.stringify(row,null,2)}</pre></details>)}</div>:<div className="blank-panel"><BookOpen size={42} strokeWidth={1}/><p>{t('emptyTrajectory')}</p></div>}</>}
      {tab==='evaluation'&&<ProofCenter lang={lang} value={proof} onRun={runProof} busy={busy||demoBusy}/>}
      {tab!=='episodes'&&tab!=='evaluation'&&tab!=='trainingLab'&&!initial&&<div className="blank-panel"><FlaskConical size={42} strokeWidth={1}/><p>{t('noEpisode')}</p><button className="button primary" onClick={()=>setTab('episodes')}>{t('createEpisode')}</button></div>}
      <div className="work-footer"><span>{t('fiction')}</span><button className="text-button" onClick={beginTour}>{t('replay')}</button></div>
    </div>
    {detail&&<FocusDialog suspended={tour!==null} className="drawer-overlay" returnFocus={dialogTrigger.current} onClose={()=>setDetail(null)}><aside className="record-drawer" role="dialog" aria-modal="true" aria-label={t('record')} onClick={e=>e.stopPropagation()}><div className="drawer-heading"><FileText size={23}/><h2>{t('record')}</h2><button className="icon-button" aria-label={t('close')} onClick={()=>setDetail(null)}><X size={21}/></button></div><span className="code-id">{detail.doc_id||detail.row_id}</span><dl className="record-fields">{Object.entries(detail).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{typeof value==='object'?<pre>{JSON.stringify(value,null,2)}</pre>:String(value??'null')}</dd></div>)}</dl><button className="button primary full" disabled={evidence.includes(detail.doc_id||detail.row_id)||evidence.length>=10} onClick={tour===2?advanceTour:pin}>{evidence.includes(detail.doc_id||detail.row_id)?<Check size={17}/>:<Plus size={17}/>} {t(evidence.includes(detail.doc_id||detail.row_id)?'evidenceAdded':'pinEvidence')}</button><p className="small-note">{evidence.length} / 10 {t('evidence').toLowerCase()}</p></aside></FocusDialog>}
    {editing&&<FocusDialog suspended={tour!==null} className="modal-overlay" onClose={()=>setEditing(false)}><section className="finding-editor" role="dialog" aria-modal="true" aria-labelledby="finding-title"><div className="drawer-heading"><h2 id="finding-title">{t('addFinding')}</h2><button className="icon-button" onClick={()=>setEditing(false)} aria-label={t('close')}><X size={21}/></button></div><form onSubmit={e=>{e.preventDefault();const d=new FormData(e.currentTarget);const split=k=>String(d.get(k)||'').split(',').map(x=>x.trim()).filter(Boolean);const f={type:d.get('type'),affected_ids:split('affected'),claimed_amount_minor:Number(d.get('amount')),currency:d.get('currency'),evidence_ids:split('evidence'),explanation:d.get('explanation')};if(f.evidence_ids.length>10||!Number.isSafeInteger(f.claimed_amount_minor)){setError(t('requestError'));return;}setFindings([...findings,f]);setEditing(false);}}><label>{t('type')}<select name="type">{issueTypes.map(type=><option key={type} value={type}>{t(type)}</option>)}</select></label><label>{t('affected')}<input name="affected" required defaultValue={evidence.filter(x=>x.startsWith('row-')).join(', ')}/></label><div className="form-row"><label>{t('amountMinor')}<input name="amount" type="number" min="0" step="1" required/></label><label>{t('currency')}<select name="currency"><option>KZT</option><option>USD</option><option>EUR</option><option>JPY</option></select></label></div><label>{t('evidenceIds')}<textarea name="evidence" rows={2} required defaultValue={evidence.join(', ')}/></label><label>{t('explanation')}<textarea name="explanation" maxLength={1000} rows={3}/></label><button className="button primary full">{t('saveFinding')}</button></form></section></FocusDialog>}
    {tour!==null&&<Tutorial t={t} step={tour} busy={busy} selector={tourMode==='training'?['.training-create','.training-start','.training-evaluate'][tour]:tourSelectors[tour]} prefix={tourMode==='training'?'trainGuide':'guide'} total={tourMode==='training'?3:5} onNext={advanceTour} onClose={closeTour}/>}
  </main>;
}

export default function App(){
  const [lang,setLangState]=useState(()=>localStorage.getItem('af-language')||'ru');const [view,setView]=useState('landing');const [user,setUser]=useState(null);
  const t=key=>dictionaries[lang]?.[key]||dictionaries.en[key]||key;
  const setLang=value=>{setLangState(value);localStorage.setItem('af-language',value);};
  useEffect(()=>{document.documentElement.lang=lang;},[lang]);
  useEffect(()=>{detectBackend().then(value=>setUser(value.user)).catch(()=>setUser(null));},[]);
  function enter(){setView(user?'workspace':'auth');window.scrollTo(0,0);}
  function home(){setView('landing');window.scrollTo(0,0);}
  async function logout(){await api('logout');sessionStorage.removeItem('af-tour-session');setUser(null);setView('landing');window.scrollTo(0,0);}
  return view==='landing'?<Landing t={t} lang={lang} setLang={setLang} onEnter={enter}/>:view==='auth'?<Auth t={t} lang={lang} setLang={setLang} onBack={home} onSuccess={value=>{sessionStorage.removeItem('af-tour-session');setUser(value);setView('workspace');}}/>:<Workspace t={t} lang={lang} setLang={setLang} user={user} onLogout={logout} onHome={home}/>;
}
