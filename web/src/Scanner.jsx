import React,{useEffect,useRef} from 'react';
import * as THREE from 'three';

export default function Scanner({paused=false,dark=false,progressRef=null,exploded=false}){
  const host=useRef();
  useEffect(()=>{
    const element=host.current;
    let renderer;
    try{renderer=new THREE.WebGLRenderer({alpha:true,antialias:true,powerPreference:'low-power'});}catch{return;}
    renderer.setPixelRatio(Math.min(Math.max(devicePixelRatio,2),3));
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.setClearColor(0,0);
    element.appendChild(renderer.domElement);
    const scene=new THREE.Scene();
    const camera=new THREE.PerspectiveCamera(31,1,.1,100);camera.position.set(0,.2,exploded?12.3:10.8);
    scene.add(new THREE.HemisphereLight(0xffffff,0x66717d,3.5));
    const key=new THREE.DirectionalLight(0xffffff,5);key.position.set(-3,5,6);scene.add(key);
    const rim=new THREE.DirectionalLight(0x8cbfd3,4);rim.position.set(4,-1,3);scene.add(rim);
    const group=new THREE.Group();scene.add(group);group.rotation.set(-.15,exploded?-.65:-.35,-.13);
    const textures=[];const geometries=[];const materials=[];
    function material(props){const m=new THREE.MeshStandardMaterial(props);materials.push(m);return m;}
    function mesh(geometry,m,parent=group){geometries.push(geometry);const o=new THREE.Mesh(geometry,m);parent.add(o);return o;}
    const paper=material({color:0xfafafa,roughness:.5,metalness:.04});
    const edge=material({color:0xcbd0d4,roughness:.35,metalness:.5});
    const ink=material({color:0x111a24,roughness:.2,metalness:.8});
    const metal=material({color:0x9ba9b6,roughness:.2,metalness:.9});
    const lightMetal=material({color:0xe8edf2,roughness:.16,metalness:.85});
    const pages=[];
    for(let i=3;i>=0;i--){const page=mesh(new THREE.BoxGeometry(3.15,4.05,.045),i===0?paper:edge);page.position.set((i-1.5)*.1,-.13*i,-.07*i);page.rotation.z=(i-1.5)*.04;pages.push(page);}
    const canvas=document.createElement('canvas');canvas.width=768;canvas.height=1024;
    const c=canvas.getContext('2d');c.fillStyle='#fafafa';c.fillRect(0,0,768,1024);
    c.fillStyle='#17212e';c.font='600 36px sans-serif';c.fillText('AUDITFORGE',65,100);
    c.font='18px sans-serif';c.fillStyle='#697581';c.fillText('SYNTHETIC COMPANY / OCT 2026',65,145);
    c.fillStyle='#16212e';c.font='bold 50px sans-serif';c.fillText('Evidence.',65,250);
    c.fillStyle='#b5bdc7';c.fillRect(65,285,638,2);
    for(let i=0;i<9;i++){c.fillStyle=i===4?'#d6e8ed':'#e9edf1';c.fillRect(65,340+i*51,638,38);c.fillStyle=i===4?'#356779':'#8d9aa7';c.fillRect(80,353+i*51,100,8);c.fillRect(230,353+i*51,190+(i%3)*20,8);c.fillRect(553,353+i*51,128,8);}
    c.fillStyle='#8c9aa7';c.font='16px sans-serif';c.fillText('INVOICE / PAYMENT / JOURNAL',65,930);
    const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=4;textures.push(texture);
    const face=material({map:texture,roughness:.8});const doc=mesh(new THREE.PlaneGeometry(3.15,4.05),face);doc.position.set(-.15,0,.026);doc.rotation.z=-.06;
    const lens=new THREE.Group();group.add(lens);lens.position.set(.5,.32,1.15);
    const ring=mesh(new THREE.TorusGeometry(1.12,.16,32,100),metal,lens);
    const outer=mesh(new THREE.TorusGeometry(1.29,.045,24,100),lightMetal,lens);outer.position.z=-.06;
    const inner=mesh(new THREE.TorusGeometry(.96,.07,24,100),ink,lens);inner.position.z=.02;
    const glass=new THREE.MeshPhysicalMaterial({color:0xadd8df,metalness:.1,roughness:.06,transparent:true,opacity:.22,side:THREE.DoubleSide,clearcoat:1});materials.push(glass);
    const disc=mesh(new THREE.CircleGeometry(.96,80),glass,lens);disc.position.z=.03;
    const beam=new THREE.MeshBasicMaterial({color:0x61a3b6,transparent:true,opacity:.1,side:THREE.DoubleSide});materials.push(beam);
    const shaft=mesh(new THREE.CylinderGeometry(.94,1.05,1.05,64,1,true),beam,lens);shaft.rotation.x=Math.PI/2;shaft.position.z=-.52;
    const handle=mesh(new THREE.CylinderGeometry(.13,.18,1.42,32),ink,lens);handle.rotation.z=.7;handle.position.set(1.27,-1.34,0);
    const end=mesh(new THREE.CylinderGeometry(.18,.18,.14,32),metal,lens);end.rotation.z=.7;end.position.set(1.73,-1.9,0);
    const scan=mesh(new THREE.PlaneGeometry(1.72,.018),new THREE.MeshBasicMaterial({color:0x27a7b5,transparent:true,opacity:.8}),lens);materials.push(scan.material);scan.position.z=.06;
    const sensorMaterial=material({color:0x173d4c,metalness:.65,roughness:.25});
    const sensor=mesh(new THREE.BoxGeometry(1.65,1.65,.055),sensorMaterial,lens);sensor.position.z=-.15;
    for(let i=0;i<7;i++){const trace=mesh(new THREE.BoxGeometry(1.3,.012,.01),lightMetal,sensor);trace.position.set(0,-.55+i*.18,.035);}
    const chip=mesh(new THREE.BoxGeometry(.53,.53,.08),ink,sensor);chip.position.z=.05;
    if(!exploded)sensor.visible=false;
    const lensParts=[outer,ring,inner,disc,sensor];
    const bases=lensParts.map(o=>o.position.clone());
    const pageBases=pages.map(o=>o.position.clone());
    let target={x:0,y:0},visible=true,frame=0;
    const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    function move(event){const box=element.getBoundingClientRect();target.x=((event.clientX-box.left)/box.width-.5)*.45;target.y=((event.clientY-box.top)/box.height-.5)*.35;}
    element.parentElement.addEventListener('pointermove',move);
    const resize=new ResizeObserver(()=>{const {width,height}=element.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix();group.scale.setScalar(width<500?.85:1);});resize.observe(element);
    const observer=new IntersectionObserver(([entry])=>visible=entry.isIntersecting);observer.observe(element);
    const bounds=new THREE.Box3(),sphere=new THREE.Sphere();
    const start=performance.now();
    function render(){
      frame=requestAnimationFrame(render);if(!visible)return;
      const t=(performance.now()-start)/1000;
      const p=Math.max(0,Math.min(1,progressRef?.current||0));
      if(exploded){
        group.rotation.y=-.4-p*.4+(reduced?0:target.x*.16);
        group.rotation.x=-.12+(reduced?0:-target.y*.15);
        group.rotation.z=-.1+p*.12;
        lens.position.set(.2+p*.2,.24+p*.25,.7+p*.45);
        lensParts.forEach((o,i)=>{o.position.copy(bases[i]);o.position.z+=(i-2)*p*1.75;o.position.x-=(i-2)*p*.1;});
        pages.forEach((o,i)=>{o.position.copy(pageBases[i]);o.position.z-=p*(.4+i*.24);o.position.x-=p*(.12+i*.13);});
        doc.position.z=.026-p*.32;
        handle.position.set(1.27+p*.1,-1.34,-p*1.75);
        end.position.set(1.73+p*.1,-1.9,-p*1.75);
        shaft.material.opacity=.1*(1-p);
        scan.position.y=.65-p*1.3;scan.position.z=.06+p*1.05;
      }else if(!paused&&!reduced){
        group.rotation.y+=(target.x-.28-group.rotation.y)*.045;
        group.rotation.x+=(-target.y-.12-group.rotation.x)*.045;
        scan.position.y=Math.sin(t*1.15)*.65;
      }
      group.updateMatrixWorld(true);bounds.setFromObject(group);bounds.getBoundingSphere(sphere);const limitingFov=Math.min(camera.fov*Math.PI/180,2*Math.atan(Math.tan(camera.fov*Math.PI/360)*camera.aspect));const distance=sphere.radius/Math.sin(limitingFov/2)*1.12;camera.position.set(sphere.center.x,sphere.center.y,distance+sphere.center.z);camera.lookAt(sphere.center);
      renderer.render(scene,camera);element.dataset.ready='true';
    }
    render();
    return()=>{cancelAnimationFrame(frame);resize.disconnect();observer.disconnect();element.parentElement?.removeEventListener('pointermove',move);textures.forEach(t=>t.dispose());geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());renderer.dispose();renderer.domElement.remove();};
  },[paused,dark,exploded,progressRef]);
  return <div className={'scanner'+(exploded?' scanner-exploded':'')} ref={host} role="img" aria-label={exploded?'Interactive exploded audit scanner showing source, reconciliation, FX and evidence layers':'3D evidence scanner linking financial documents'}/>;
}
