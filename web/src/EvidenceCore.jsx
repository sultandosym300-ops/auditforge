import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

// Financial source documents, never device mockups. Scroll reveals the evidence chain.
export default function EvidenceCore({progressRef,paused=false,lang='ru',hero=false}){
 const host=useRef();
 useEffect(()=>{
  const element=host.current;let renderer;
  try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});}catch{return;}
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;renderer.setClearColor(0,0);element.appendChild(renderer.domElement);
  const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-5,5,4,-4,.1,60);camera.position.z=18;
  const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment(),environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;room.dispose();pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xe5f3ff,0x476078,2.6));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(-3,5,8);scene.add(light);
  const group=new THREE.Group();scene.add(group);const geometry=[],materials=[],textures=[],sheets=[];
  const titles={ru:['Платёж','Валютный курс','Проводка','Доказательство'],en:['Payment','Exchange rate','Journal entry','Evidence'],kk:['Төлем','Валюта бағамы','Өткізбе','Дәлел']}[lang]||['Payment','Exchange rate','Journal entry','Evidence'];
  const subtitles={ru:['Исходный документ','Правило на дату платежа','Запись в учётной книге','Проверенное расхождение'],en:['Source document','Rule on payment date','Recorded book amount','Verified difference'],kk:['Бастапқы құжат','Төлем күніндегі ереже','Есеп кітабындағы жазба','Расталған айырма']}[lang]||[];
  const values=['500.00','490.60','250 000','4 700'],units=['USD','KZT / USD','KZT','KZT'];
  function material(options){const m=new THREE.MeshStandardMaterial(options);materials.push(m);return m;}
  function mesh(g,m,parent){geometry.push(g);const o=new THREE.Mesh(g,m);parent.add(o);return o;}
  function shape(w,h,r){const s=new THREE.Shape(),x=-w/2,y=-h/2;s.moveTo(x+r,y);s.lineTo(x+w-r,y);s.quadraticCurveTo(x+w,y,x+w,y+r);s.lineTo(x+w,y+h-r);s.quadraticCurveTo(x+w,y+h,x+w-r,y+h);s.lineTo(x+r,y+h);s.quadraticCurveTo(x,y+h,x,y+h-r);s.lineTo(x,y+r);s.quadraticCurveTo(x,y,x+r,y);return s;}
  function faceTexture(index){
   const canvas=document.createElement('canvas');canvas.width=1536;canvas.height=2048;const c=canvas.getContext('2d');c.scale(2,2);
   c.fillStyle=index===3?'#e2f4ef':'#fafcfd';c.fillRect(0,0,768,1024);
   c.fillStyle='#60788b';c.font='500 18px sans-serif';c.fillText('AUDITFORGE',58,76);c.textAlign='right';c.fillText(String(index+1).padStart(2,'0'),710,76);c.textAlign='left';
   c.strokeStyle='#ccd8e0';c.lineWidth=1;c.beginPath();c.moveTo(58,108);c.lineTo(710,108);c.stroke();
   c.fillStyle='#162e40';c.font='600 42px sans-serif';c.fillText(titles[index],58,196);c.font='22px sans-serif';c.fillStyle='#657f90';c.fillText(subtitles[index]||'',58,239);
   c.fillStyle='#163548';c.font='500 89px sans-serif';c.fillText(values[index],54,395);c.font='24px sans-serif';c.fillStyle='#637d8b';c.fillText(units[index],58,438);
   const labels=index===0?['PAY-0042','31 OCT 2026','USD → KZT']:index===1?['FX-USD-10','500 × 490.60','245 300 KZT']:index===2?['ROW-0084','245 300 KZT','250 000 KZT']:['PAY-0042 + FX-USD-10','ROW-0084','250 000 − 245 300'];
   labels.forEach((value,i)=>{const y=555+i*99;c.fillStyle='#edf2f5';c.fillRect(56,y-28,656,62);c.fillStyle='#476578';c.font='24px sans-serif';c.fillText(value,76,y+12);});
   if(index===3){c.strokeStyle='#397b6f';c.lineWidth=7;c.beginPath();c.arc(644,897,36,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(626,896);c.lineTo(641,911);c.lineTo(664,882);c.stroke();}
   c.fillStyle='#7e949f';c.font='18px sans-serif';c.fillText('SYNTHETIC · DEMONSTRATION',58,948);
   const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;t.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());textures.push(t);return t;
  }
  for(let i=0;i<(hero?1:4);i++){
   const sheet=new THREE.Group();group.add(sheet);sheets.push(sheet);const outline=shape(2.8,3.75,.075);
   const thickness=new THREE.ExtrudeGeometry(outline,{depth:.025,bevelEnabled:true,bevelSegments:2,bevelSize:.008,bevelThickness:.008,curveSegments:16});thickness.translate(0,0,-.025);
   mesh(thickness,material({color:0xe5edf2,roughness:.8}),sheet);
   const front=mesh(new THREE.ShapeGeometry(outline),(()=>{const m=new THREE.MeshBasicMaterial({map:faceTexture(hero?0:i)});materials.push(m);return m;})(),sheet);front.position.z=.012;
   const uv=front.geometry.getAttribute('uv'),pos=front.geometry.getAttribute('position');for(let n=0;n<uv.count;n++)uv.setXY(n,(pos.getX(n)+1.4)/2.8,(pos.getY(n)+1.875)/3.75);uv.needsUpdate=true;
  }
  // A thin optical plane highlights a document row; it is a visual explanation of inspection.
  let inspection;
  if(hero){inspection=new THREE.Group();group.add(inspection);const glass=new THREE.MeshPhysicalMaterial({color:0xb9e4e9,transparent:true,opacity:.25,roughness:.12,metalness:0,side:THREE.DoubleSide});materials.push(glass);
   mesh(new THREE.CircleGeometry(.93,96),glass,inspection);
   const rimMaterial=material({color:0x527b8e,metalness:.75,roughness:.2});
   mesh(new THREE.TorusGeometry(.96,.045,20,96),rimMaterial,inspection);
   const outer=mesh(new THREE.TorusGeometry(1.045,.012,12,96),rimMaterial,inspection);outer.position.z=-.02;

  }
  let visible=true,sized=false,frame=0,targetX=0,targetY=0,poseX=0,poseY=0,lastTime=performance.now();const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const bounds=new THREE.Box3(),size=new THREE.Vector3(),center=new THREE.Vector3();
  const resize=new ResizeObserver(()=>{const b=element.getBoundingClientRect();sized=b.width>0&&b.height>0;if(!sized)return;renderer.setSize(b.width,b.height);camera.left=-5;camera.right=5;camera.top=5*b.height/b.width;camera.bottom=-camera.top;camera.updateProjectionMatrix();});resize.observe(element);
  const observer=new IntersectionObserver(([entry])=>visible=entry.isIntersecting);observer.observe(element);
  function move(e){const b=element.getBoundingClientRect();targetX=(e.clientX-b.left)/b.width-.5;targetY=(e.clientY-b.top)/b.height-.5;}function leave(){targetX=targetY=0;}
  element.addEventListener('pointermove',move);element.addEventListener('pointerleave',leave);
  function render(){frame=requestAnimationFrame(render);if(!visible||!sized)return;const now=performance.now(),dt=Math.min((now-lastTime)/1000,.05);lastTime=now;const p=Math.max(0,Math.min(1,progressRef?.current||0));
   poseX=THREE.MathUtils.damp(poseX,reduced||paused?0:targetX,7,dt);poseY=THREE.MathUtils.damp(poseY,reduced||paused?0:targetY,7,dt);group.rotation.set(.06-poseY*.09,-.16+poseX*.13,-.055);
   sheets.forEach((sheet,i)=>{const order=i-1.5;sheet.position.set(hero?0:order*(.14+p*1.7),hero?0:-order*p*.15,hero?0:-i*(.12+p*.21));sheet.rotation.z=hero?0:order*p*-.025;});
   if(inspection){inspection.position.set(.36+poseX*.35,.28+poseY*.9,.42);inspection.rotation.y=.02;}
   group.updateMatrixWorld(true);bounds.setFromObject(group);bounds.getSize(size);bounds.getCenter(center);camera.zoom=Math.min((camera.right-camera.left)/(size.x*1.28),(camera.top-camera.bottom)/(size.y*1.28));camera.position.set(center.x,center.y,18);camera.lookAt(center.x,center.y,0);camera.updateProjectionMatrix();renderer.render(scene,camera);element.dataset.ready='true';element.dataset.scene=hero?'document-inspection':'financial-evidence';
  }render();
  return()=>{cancelAnimationFrame(frame);resize.disconnect();observer.disconnect();element.removeEventListener('pointermove',move);element.removeEventListener('pointerleave',leave);geometry.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());environment.dispose();renderer.dispose();renderer.domElement.remove();};
 },[hero,lang,paused,progressRef]);
 return <div className={'scanner evidence-core'+(hero?' document-inspection':'')} ref={host} role="img" aria-label={hero?(lang==='ru'?'Проверка строки платёжного документа':'Payment document inspection'):(lang==='ru'?'Связанные документы: платёж, курс, проводка и доказательство':'Connected financial evidence documents')}/>;
}
