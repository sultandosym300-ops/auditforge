import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

// An authored physical dossier: source, rule, book and conclusion are separate layers.
export default function EvidenceCore({progressRef,paused=false,lang='ru'}){
  const host=useRef();
  useEffect(()=>{
    const element=host.current;
    let renderer;
    try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});}catch{return;}
    renderer.setPixelRatio(Math.min(devicePixelRatio,2));
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure=1.15;
    renderer.setClearColor(0,0);element.appendChild(renderer.domElement);
    const scene=new THREE.Scene();
    const camera=new THREE.OrthographicCamera(-5,5,3.5,-3.5,.1,60);camera.position.set(0,0,18);
    const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();
    const environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;
    room.dispose();pmrem.dispose();
    scene.add(new THREE.HemisphereLight(0xc9e9ff,0x182638,2));
    const key=new THREE.DirectionalLight(0xe1f4ff,3);key.position.set(-4,6,8);scene.add(key);
    const rim=new THREE.DirectionalLight(0x7ccbdc,2);rim.position.set(5,-1,4);scene.add(rim);
    const group=new THREE.Group();scene.add(group);
    const geometries=[],materials=[],textures=[];
    function mat(props){const value=new THREE.MeshStandardMaterial(props);materials.push(value);return value;}
    function mesh(geometry,material,parent){geometries.push(geometry);const value=new THREE.Mesh(geometry,material);parent.add(value);return value;}
    function outline(width,height,radius){
      const s=new THREE.Shape(),x=-width/2,y=-height/2;
      s.moveTo(x+radius,y);s.lineTo(x+width-radius,y);s.quadraticCurveTo(x+width,y,x+width,y+radius);
      s.lineTo(x+width,y+height-radius);s.quadraticCurveTo(x+width,y+height,x+width-radius,y+height);
      s.lineTo(x+radius,y+height);s.quadraticCurveTo(x,y+height,x,y+height-radius);
      s.lineTo(x,y+radius);s.quadraticCurveTo(x,y,x+radius,y);return s;
    }
    function plate(width,height,depth,radius,material,parent){
      const geo=new THREE.ExtrudeGeometry(outline(width,height,radius),{depth,bevelEnabled:true,bevelSegments:4,steps:1,bevelSize:.025,bevelThickness:.025,curveSegments:12});
      geo.translate(0,0,-depth/2);return mesh(geo,material,parent);
    }
    const metal=mat({color:0x8ca4b8,metalness:1,roughness:.26});
    const graphite=mat({color:0x1b2e3e,metalness:.75,roughness:.3});
    const inset=mat({color:0x07121c,metalness:.5,roughness:.26});
    const accent=mat({color:0x9ed8d9,emissive:0x2b6f79,emissiveIntensity:.35,metalness:.6,roughness:.25});
    const labels=lang==='kk'?['ТӨЛЕМ','ВАЛЮТА БАҒАМЫ','ӨТКІЗБЕ','ДӘЛЕЛ']:lang==='en'?['PAYMENT','EXCHANGE RATE','JOURNAL','EVIDENCE']:['ПЛАТЁЖ','ВАЛЮТНЫЙ КУРС','ПРОВОДКА','ДОКАЗАТЕЛЬСТВО'];
    const amounts=['500.00','490.60','250 000','4 700'];
    const currencies=['USD','KZT / USD','KZT','KZT'];
    const subs=lang==='kk'?['Бастапқы құжат','Ресми ереже','Кітаптағы сома','Дәлелденген айырма']:lang==='en'?['Source document','Declared conversion rule','Recorded book amount','Verified difference']:['Исходный документ','Правило конвертации','Сумма в учётной книге','Доказанное расхождение'];
    function texture(index){
      const canvas=document.createElement('canvas');canvas.width=900;canvas.height=1280;
      const c=canvas.getContext('2d');c.fillStyle=index===3?'#17373f':'#11202d';c.fillRect(0,0,900,1280);
      const glow=c.createLinearGradient(0,0,900,1280);glow.addColorStop(0,'#ffffff09');glow.addColorStop(1,'#00000018');c.fillStyle=glow;c.fillRect(0,0,900,1280);
      c.strokeStyle='#67879b55';c.lineWidth=2;c.strokeRect(40,40,820,1200);
      c.fillStyle='#9bb9cb';c.font='500 24px sans-serif';c.fillText('AUDITFORGE',78,103);
      c.font='22px monospace';c.textAlign='right';c.fillText('0'+(index+1)+' / 04',819,103);c.textAlign='left';
      c.strokeStyle='#7898ac66';c.beginPath();c.moveTo(78,143);c.lineTo(822,143);c.stroke();
      c.fillStyle='#d0e7ef';c.font='500 '+(index===3?34:38)+'px sans-serif';c.fillText(labels[index],78,230);
      c.fillStyle='#a6c3d1';c.font='25px sans-serif';c.fillText(subs[index],78,278);
      c.fillStyle=index===3?'#c6f4e3':'#f0f7fc';c.font='500 108px sans-serif';c.fillText(amounts[index],74,455);
      c.fillStyle='#a7cad9';c.font='30px monospace';c.fillText(currencies[index],78,513);
      c.strokeStyle='#9fc1d34d';c.beginPath();c.moveTo(78,560);c.lineTo(822,560);c.stroke();
      const rowLabels=index===0?['PAYMENT ID','REPORT PERIOD','SOURCE AMOUNT','CURRENCY']:index===1?['CURRENCY PAIR','DECLARED RATE','CONVERTED AMOUNT','PRECISION']:index===2?['ACCOUNT','BOOK AMOUNT','EXPECTED','DIFFERENCE']:['PAYMENT','EXCHANGE RATE','JOURNAL ENTRY','RESULT'];
      const values=[['PAY-0042','2026 / 10','500.00','USD'],['USD → KZT','490.60','245 300 KZT','DECIMAL'],['PAYABLE','250 000 KZT','245 300 KZT','4 700 KZT'],['PAY-0042','FX-USD-10','ROW-0084','VERIFIED']][index];
      for(let i=0;i<4;i++){
        const y=635+i*103;c.fillStyle='#88a7b9';c.font='21px monospace';c.fillText(rowLabels[i],78,y);
        c.fillStyle='#d1e3ed';c.font='26px monospace';c.textAlign='right';c.fillText(values[i],820,y);c.textAlign='left';
        c.strokeStyle='#63839a33';c.beginPath();c.moveTo(78,y+36);c.lineTo(822,y+36);c.stroke();
      }
      c.fillStyle='#8dc0c5';for(let i=0;i<66;i++){const w=i%3===0?4:2;c.fillRect(78+i*6,1092,w,49+(i%4)*5);}
      c.font='21px monospace';c.fillStyle='#90afc0';c.fillText('SYNTHETIC / DEMONSTRATION',78,1200);
      if(index===3){c.strokeStyle='#b7ead9';c.lineWidth=5;c.beginPath();c.arc(765,1118,38,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(745,1119);c.lineTo(760,1133);c.lineTo(787,1103);c.stroke();}
      const tex=new THREE.CanvasTexture(canvas);tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());textures.push(tex);return tex;
    }
    const layers=[];
    for(let i=0;i<4;i++){
      const layer=new THREE.Group();group.add(layer);layers.push(layer);
      plate(2.68,3.8,.11,.15,metal,layer);
      const shell=plate(2.6,3.72,.085,.13,graphite,layer);shell.position.z=.065;
      const gasket=plate(2.46,3.55,.018,.1,inset,layer);gasket.position.z=.122;
      const face=mesh(new THREE.ShapeGeometry(outline(2.36,3.43,.08)),mat({map:texture(i),roughness:.37,metalness:.15}),layer);
      // ShapeGeometry UVs use world coordinates; map the full authored face into 0..1.
      const uv=face.geometry.getAttribute('uv'),pos=face.geometry.getAttribute('position');
      for(let v=0;v<uv.count;v++)uv.setXY(v,(pos.getX(v)+1.18)/2.36,(pos.getY(v)+1.715)/3.43);uv.needsUpdate=true;
      face.position.z=.18;
      for(const x of [-1.23,1.23])for(const y of [-1.77,1.77]){
        const screw=mesh(new THREE.CylinderGeometry(.035,.035,.018,20),metal,layer);screw.rotation.x=Math.PI/2;screw.position.set(x,y,.132);
        const slot=mesh(new THREE.BoxGeometry(.037,.006,.003),inset,layer);slot.position.set(x,y,.144);slot.rotation.z=.65;
      }
      for(let j=0;j<15;j++){const vent=mesh(new THREE.BoxGeometry(.035,.14,.018),inset,layer);vent.position.set(-.73+j*.105,-1.882,.02);}
      const rail=plate(.032,2.7,.022,.015,accent,layer);rail.position.set(-1.325,.05,.035);
      for(let j=0;j<5;j++){const contact=mesh(new THREE.BoxGeometry(.1,.02,.09),metal,layer);contact.position.set(-.4+j*.2,-1.92,-.015);}
    }
    let visible=true,frame=0,targetX=0,targetY=0,lastP=-1;
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    function move(e){const b=element.getBoundingClientRect();targetX=(e.clientX-b.left)/b.width-.5;targetY=(e.clientY-b.top)/b.height-.5;}
    element.parentElement.addEventListener('pointermove',move);
    const resize=new ResizeObserver(()=>{const b=element.getBoundingClientRect();renderer.setSize(b.width,b.height);const halfW=4.95,halfH=halfW*b.height/Math.max(1,b.width);camera.left=-halfW;camera.right=halfW;camera.top=halfH;camera.bottom=-halfH;camera.updateProjectionMatrix();lastP=-1;});resize.observe(element);
    const visibility=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;});visibility.observe(element);
    function render(){
      frame=requestAnimationFrame(render);if(!visible)return;
      const p=Math.max(0,Math.min(1,progressRef.current));
      group.rotation.set(.08+(reduced||paused?0:-targetY*.06),-.28+(reduced||paused?0:targetX*.09),-.055);
      layers.forEach((layer,i)=>{
        const order=i-1.5;
        layer.position.set(order*(.14+p*1.64),-order*p*.15,order*(-.22+p*.72));
        layer.rotation.y=-.035+order*p*.035;
        layer.rotation.z=order*p*-.025;
        layer.scale.setScalar(1);
      });
      if(!paused||lastP!==p){renderer.render(scene,camera);lastP=p;}
    }
    render();
    return()=>{cancelAnimationFrame(frame);resize.disconnect();visibility.disconnect();element.parentElement?.removeEventListener('pointermove',move);geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());environment.dispose();renderer.dispose();renderer.domElement.remove();};
  },[progressRef,paused,lang]);
  const label=lang==='kk'?'Төлем, бағам, өткізбелер және дәлел қабаттары бар үш өлшемді досье':lang==='en'?'Exploded evidence dossier with payment, exchange rate, journal and verified finding layers':'Объёмное досье: платёж, валютный курс, проводка и доказанный вывод';
  return <div className="scanner evidence-core" ref={host} role="img" aria-label={label}/>;
}
