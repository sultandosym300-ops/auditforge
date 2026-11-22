import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

const MODEL_PATHS={
 magnifier:'/models/magnifying-glass.glb',
 clipboard:'/models/clipboard.glb',
 calculator:'/models/calculator.glb',
 tray:'/models/document-tray.glb',
 sealedProof:'/models/letter.glb'
};

const COPY={
 ru:{brand:'AUDITFORGE',payment:'ПЛАТЁЖ',source:'Исходный документ',rate:'Курс на дату платежа',book:'Проводка в книге',proof:'Доказанное расхождение',verified:'ПРОВЕРЕНО'},
 en:{brand:'AUDITFORGE',payment:'PAYMENT',source:'Source document',rate:'Rate on payment date',book:'Journal entry',proof:'Proven difference',verified:'VERIFIED'},
 kk:{brand:'AUDITFORGE',payment:'ТӨЛЕМ',source:'Бастапқы құжат',rate:'Төлем күніндегі бағам',book:'Есеп кітабындағы жазба',proof:'Расталған айырма',verified:'ТЕКСЕРІЛДІ'}
};

const smooth=value=>value*value*(3-2*value);

export default function EvidenceCore({progressRef,paused=false,lang='ru',hero=false}){
 const host=useRef(null);
 useEffect(()=>{
  const element=host.current;if(!element)return undefined;
  let renderer;try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'high-performance'});}catch{return undefined;}
  let alive=true,frame=0,visible=true,sized=false,ready=false;
  const resources={geometry:[],materials:[],textures:[]};
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(hero?31:27,1,.05,100),root=new THREE.Group(),content=new THREE.Group();
  root.add(content);scene.add(root);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=hero?1.08:1.02;renderer.setClearColor(0x000000,0);element.appendChild(renderer.domElement);
  const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment(),environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;room.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xf4faff,0x182b3c,1.8));const key=new THREE.DirectionalLight(0xffffff,2.8);key.position.set(-4,7,6);scene.add(key);const fill=new THREE.DirectionalLight(0x9fdceb,1.15);fill.position.set(5,2,2);scene.add(fill);const rim=new THREE.DirectionalLight(0x5d9ac0,.9);rim.position.set(2,3,-5);scene.add(rim);

  function register(object){object.traverse(node=>{if(!node.isMesh)return;node.castShadow=false;node.receiveShadow=false;if(node.geometry)resources.geometry.push(node.geometry);const source=Array.isArray(node.material)?node.material:[node.material];node.material=source.map(material=>{const clone=material.clone();clone.envMapIntensity=1.15;resources.materials.push(clone);return clone;});if(node.material.length===1)node.material=node.material[0];});return object;}
  function normalize(object,target){const box=new THREE.Box3().setFromObject(object),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());object.position.sub(center);object.scale.setScalar(target/Math.max(size.x,size.y,size.z));object.updateMatrixWorld(true);const normalizedBox=new THREE.Box3().setFromObject(object);object.position.y-=normalizedBox.min.y;return object;}
  function makeDocumentTexture(type='payment'){
   const text=COPY[lang]||COPY.en,canvas=document.createElement('canvas');canvas.width=1200;canvas.height=1600;const c=canvas.getContext('2d');c.fillStyle=type==='proof'?'#dcefeb':'#edf3f6';c.fillRect(0,0,canvas.width,canvas.height);c.fillStyle='#425f72';c.font='600 30px Arial';c.fillText(text.brand,84,100);c.textAlign='right';c.fillText(type==='payment'?'PAY-0042':'ROW-0084',1116,100);c.textAlign='left';c.strokeStyle='#a7bcc8';c.lineWidth=3;c.beginPath();c.moveTo(84,145);c.lineTo(1116,145);c.stroke();
   const title=type==='rate'?text.rate:type==='book'?text.book:type==='proof'?text.proof:text.payment;c.fillStyle='#173548';c.font='700 54px Arial';c.fillText(title,84,276);c.fillStyle='#6b8290';c.font='32px Arial';c.fillText(type==='payment'?text.source:'Audit trail',84,332);const value=type==='rate'?'490.60':type==='book'?'250 000':type==='proof'?'4 700':'500.00',unit=type==='payment'?'USD':type==='rate'?'KZT / USD':'KZT';c.fillStyle='#12384c';c.font='600 132px Arial';c.fillText(value,78,610);c.fillStyle='#6c8391';c.font='36px Arial';c.fillText(unit,88,670);
   const rows=type==='payment'?['31 OCT 2026','SOURCE AMOUNT 500.00','CURRENCY USD']:type==='rate'?['500 × 490.60','PAYMENT DATE RULE','EXPECTED 245 300']:type==='book'?['BOOK ROW 0084','RECORDED 250 000','EXPECTED 245 300']:['PAY-0042 + FX-USD-10','ROW-0084','DIFFERENCE 4 700'];rows.forEach((row,index)=>{const y=850+index*138;c.fillStyle='#e9eff2';c.fillRect(84,y-56,1032,92);c.fillStyle='#456274';c.font='500 32px Arial';c.fillText(row,118,y+4);});
   if(type==='proof'){c.strokeStyle='#2d806f';c.lineWidth=12;c.beginPath();c.arc(1020,1410,74,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(977,1408);c.lineTo(1010,1440);c.lineTo(1066,1376);c.stroke();c.fillStyle='#2d806f';c.font='700 30px Arial';c.fillText(text.verified,82,1440);}
   const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());resources.textures.push(texture);return texture;
  }
  function makeSheet(type,width=2.65,height=3.55){const group=new THREE.Group(),edgeGeometry=new THREE.BoxGeometry(width,.055,height);resources.geometry.push(edgeGeometry);const edgeMaterial=new THREE.MeshStandardMaterial({color:0xdfe8ed,roughness:.78,metalness:.02});resources.materials.push(edgeMaterial);const edge=new THREE.Mesh(edgeGeometry,edgeMaterial);edge.position.y=.014;group.add(edge);const faceGeometry=new THREE.PlaneGeometry(width*.985,height*.985);resources.geometry.push(faceGeometry);const faceMaterial=new THREE.MeshStandardMaterial({map:makeDocumentTexture(type),roughness:.88,metalness:0});resources.materials.push(faceMaterial);const face=new THREE.Mesh(faceGeometry,faceMaterial);face.rotation.x=-Math.PI/2;face.position.y=.05;group.add(face);return group;}
  function setOpacity(object,opacity){object.visible=opacity>.015;object.traverse(node=>{if(!node.isMesh)return;const list=Array.isArray(node.material)?node.material:[node.material];list.forEach(material=>{material.transparent=opacity<.995||material.transparent;material.opacity=opacity;material.depthWrite=opacity>.72;});});}
  async function loadModel(path,target){const gltf=await new GLTFLoader().loadAsync(path);return normalize(register(gltf.scene),target);}

  const stages=[];
  async function buildHero(){const paper=makeSheet('payment',3.15,4.2);paper.rotation.z=-.045;content.add(paper);const magnifier=await loadModel(MODEL_PATHS.magnifier,3.75);magnifier.rotation.set(.02,-.38,-.12);magnifier.position.set(.35,.11,.2);content.add(magnifier);const focusGeometry=new THREE.RingGeometry(.61,.66,96);resources.geometry.push(focusGeometry);const focusMaterial=new THREE.MeshBasicMaterial({color:0x63bfcd,transparent:true,opacity:.5,side:THREE.DoubleSide});resources.materials.push(focusMaterial);const focus=new THREE.Mesh(focusGeometry,focusMaterial);focus.rotation.x=-Math.PI/2;focus.position.set(-.38,.076,.34);content.add(focus);content.rotation.set(-.08,.05,-.04);content.userData.magnifier=magnifier;content.userData.focus=focus;}
  async function buildStory(){
   const specs=[{path:MODEL_PATHS.clipboard,target:3.55,position:[0,0,0],rotation:[0,.1,-.02]},{path:MODEL_PATHS.calculator,target:2.5,position:[.66,.04,.18],rotation:[0,-.28,.04]},{path:MODEL_PATHS.tray,target:3.05,position:[.48,0,.08],rotation:[0,-.22,0]},{path:MODEL_PATHS.sealedProof,target:2.35,position:[.28,.08,.1],rotation:[0,-.18,.02]}],loaded=await Promise.all(specs.map(spec=>loadModel(spec.path,spec.target)));
   specs.forEach((spec,index)=>{const stage=new THREE.Group(),model=loaded[index];if(index===1){const sheet=makeSheet('rate',2.55,3.4);sheet.position.set(-.76,0,-.12);sheet.rotation.z=-.13;stage.add(sheet);}if(index===2){const left=makeSheet('book',2.15,2.9);left.position.set(-.78,.05,.12);left.rotation.z=-.08;stage.add(left);const right=makeSheet('rate',2,2.7);right.position.set(.55,.02,-.18);right.rotation.z=.08;stage.add(right);}if(index===3){const sheet=makeSheet('proof',2.9,3.85);sheet.position.set(-.5,0,-.06);sheet.rotation.z=-.035;stage.add(sheet);}model.position.add(new THREE.Vector3(...spec.position));model.rotation.set(...spec.rotation);stage.add(model);stage.userData.baseY=index===0?.03:0;content.add(stage);stages.push(stage);});
  }
  const loadPromise=(hero?buildHero():buildStory()).then(()=>{if(!alive)return;ready=true;element.dataset.ready='true';element.dataset.scene=hero?'forensic-magnifier':'audit-evidence-tools';}).catch(error=>{if(alive){element.dataset.error='model-load';console.error('3D asset load failed',error);}});
  let targetX=0,targetY=0,poseX=0,poseY=0,lastTime=performance.now();const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function resizeScene(){const bounds=element.getBoundingClientRect();sized=bounds.width>0&&bounds.height>0;if(!sized)return;renderer.setSize(bounds.width,bounds.height,false);camera.aspect=bounds.width/bounds.height;camera.updateProjectionMatrix();}
  const resize=new ResizeObserver(resizeScene);resize.observe(element);resizeScene();const observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;});observer.observe(element);function move(event){const bounds=element.getBoundingClientRect();targetX=(event.clientX-bounds.left)/bounds.width-.5;targetY=(event.clientY-bounds.top)/bounds.height-.5;}function leave(){targetX=0;targetY=0;}element.addEventListener('pointermove',move,{passive:true});element.addEventListener('pointerleave',leave);
  function render(){frame=requestAnimationFrame(render);if(!visible||!sized)return;const now=performance.now(),dt=Math.min((now-lastTime)/1000,.05);lastTime=now;poseX=THREE.MathUtils.damp(poseX,reduced||paused?0:targetX,6.5,dt);poseY=THREE.MathUtils.damp(poseY,reduced||paused?0:targetY,6.5,dt);
   if(hero){camera.position.set(0,5.5,8.6);camera.lookAt(0,.05,0);root.rotation.x=-poseY*.055;root.rotation.y=poseX*.12;if(content.userData.magnifier){content.userData.magnifier.position.x=.35+poseX*.3;content.userData.magnifier.position.z=.2+poseY*.28;content.userData.focus.position.x=-.38+poseX*.22;content.userData.focus.position.z=.34+poseY*.2;}}
   else{camera.position.set(0,5.2,8.8);camera.lookAt(0,.15,0);root.rotation.x=-poseY*.04;root.rotation.y=poseX*.075;const p=Math.max(0,Math.min(.9999,progressRef?.current||0)),active=Math.min(3,Math.floor(p*4)),local=p*4-active,eased=smooth(Math.min(1,local*2.2));stages.forEach((stage,index)=>{const selected=index===active;stage.position.set(0,stage.userData.baseY+.08*(1-eased),0);stage.rotation.y=(1-eased)*-.08;stage.rotation.z=(1-eased)*.018;stage.scale.setScalar(.94+.06*eased);setOpacity(stage,selected?1:0);});}
   if(ready)renderer.render(scene,camera);
  }render();
  return()=>{alive=false;cancelAnimationFrame(frame);resize.disconnect();observer.disconnect();element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);Promise.resolve(loadPromise).catch(()=>{});resources.geometry.forEach(item=>item.dispose());resources.materials.forEach(item=>item.dispose());resources.textures.forEach(item=>item.dispose());environment.dispose();renderer.dispose();renderer.domElement.remove();};
 },[hero,lang,paused,progressRef]);
 const label=hero?(lang==='ru'?'Лупа проверяет платёжный документ':'Magnifier inspecting a payment document'):(lang==='ru'?'Инструменты аудита: документ, расчёт, сверка и доказательство':'Audit tools: source, calculation, reconciliation and proof');return <div className={'scanner evidence-core'+(hero?' forensic-magnifier':' evidence-toolchain')} ref={host} role="img" aria-label={label}/>;
}
