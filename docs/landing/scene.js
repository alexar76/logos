import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const canvas3d=document.getElementById('hero-galaxy');
const host=document.getElementById('hero-visual');
const mobile=matchMedia('(max-width:700px), (pointer:coarse)').matches;
const reduced=matchMedia('(prefers-reduced-motion:reduce)').matches;

try{
  const renderer=new THREE.WebGLRenderer({canvas:canvas3d,alpha:true,antialias:true,powerPreference:'high-performance'});
  renderer.setPixelRatio(Math.min(devicePixelRatio,mobile?1.35:1.8));
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.05;
  renderer.setClearColor(0x000000,1);

  const scene=new THREE.Scene();
  const camera=new THREE.PerspectiveCamera(38,1,.1,80);
  camera.position.set(0,.25,10.4);
  const controls=new OrbitControls(camera,canvas3d);
  controls.enableDamping=true;controls.dampingFactor=.055;controls.enablePan=false;
  controls.minDistance=6;controls.maxDistance=13;controls.rotateSpeed=.55;
  controls.autoRotate=!reduced;controls.autoRotateSpeed=.42;
  controls.listenToKeyEvents(canvas3d);
  controls.keyRotateSpeed=1.4;

  scene.add(new THREE.AmbientLight(0x49635c,1.15));
  const cyanLight=new THREE.PointLight(0xa8d7c5,55,24);cyanLight.position.set(4,4,5);scene.add(cyanLight);
  const violetLight=new THREE.PointLight(0x88abbc,42,20);violetLight.position.set(-5,-2,3);scene.add(violetLight);
  const pinkLight=new THREE.PointLight(0xc6bba5,24,16);pinkLight.position.set(2,-4,-3);scene.add(pinkLight);

  const system=new THREE.Group();system.rotation.set(-.12,0,.12);scene.add(system);

  // LOGOS analytical core: layered, refractive geometry with a luminous kernel.
  const shell=new THREE.Mesh(new THREE.IcosahedronGeometry(1.18,4),new THREE.MeshPhysicalMaterial({
    color:0x233f3b,emissive:0x4e8576,emissiveIntensity:.34,metalness:.28,roughness:.12,
    transmission:.32,thickness:1.5,transparent:true,opacity:.92,clearcoat:1,iridescence:0,
    iridescenceIOR:1.35,iridescenceThicknessRange:[140,560]
  }));system.add(shell);
  const wire=new THREE.Mesh(new THREE.IcosahedronGeometry(1.23,2),new THREE.MeshBasicMaterial({
    color:0xa8d7c5,wireframe:true,transparent:true,opacity:.13,blending:THREE.AdditiveBlending,depthWrite:false
  }));system.add(wire);
  const kernel=new THREE.Mesh(new THREE.OctahedronGeometry(.48,2),new THREE.MeshBasicMaterial({
    color:0xeaf0ee,transparent:true,opacity:.72,blending:THREE.AdditiveBlending,depthWrite:false
  }));system.add(kernel);

  // An illustrative model of connected sources; measured telemetry lives in the dashboard.
  const ringGroup=new THREE.Group();system.add(ringGroup);
  const ringData=[
    [2.05,.015,0xa8d7c5,.72,.18,.18],[2.48,.012,0x88abbc,-.5,.78,.24],[2.9,.009,0xc6bba5,.48,-.3,.85],
    [3.25,.007,0x729b87,1.08,.42,-.25]
  ];
  ringData.forEach(([radius,tube,color,rx,ry,rz])=>{
    const ring=new THREE.Mesh(new THREE.TorusGeometry(radius,tube,8,180),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.46,blending:THREE.AdditiveBlending,depthWrite:false}));
    ring.rotation.set(rx,ry,rz);ringGroup.add(ring);
  });

  const hubs=[];
  const hubColors=[0xa8d7c5,0x88abbc,0x729b87,0xc6bba5,0xdfc79e,0xa8d7c5,0x88abbc,0x729b87];
  for(let i=0;i<8;i++){
    const angle=i/8*Math.PI*2+(i%2)*.23,radius=2.2+(i%3)*.42;
    const pos=new THREE.Vector3(Math.cos(angle)*radius,Math.sin(angle*1.7)*.82,Math.sin(angle)*radius);
    const group=new THREE.Group();group.position.copy(pos);
    const color=hubColors[i];
    group.add(new THREE.Mesh(new THREE.SphereGeometry(.105+(i%3)*.022,18,18),new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:.8,roughness:.22,metalness:.35})));
    const halo=new THREE.Mesh(new THREE.SphereGeometry(.22,16,16),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.08,blending:THREE.AdditiveBlending,depthWrite:false}));group.add(halo);
    const anomaly=new THREE.Mesh(new THREE.TorusGeometry(.25,.009,6,48),new THREE.MeshBasicMaterial({color,transparent:true,opacity:i===3?.9:.2,blending:THREE.AdditiveBlending,depthWrite:false}));
    anomaly.rotation.x=Math.PI/2;group.add(anomaly);system.add(group);
    hubs.push({group,halo,anomaly,phase:i*.83,color});
  }

  // Curved routing paths plus packets travelling from every hub to LOGOS.
  const routes=[];
  hubs.forEach((hub,i)=>{
    const start=hub.group.position.clone(),mid=start.clone().multiplyScalar(.53);
    mid.y+=(i%2?.55:-.55);
    const curve=new THREE.QuadraticBezierCurve3(start,mid,new THREE.Vector3());
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)),new THREE.LineBasicMaterial({color:hub.color,transparent:true,opacity:.19,blending:THREE.AdditiveBlending,depthWrite:false}));system.add(line);
    const packet=new THREE.Mesh(new THREE.SphereGeometry(.035,8,8),new THREE.MeshBasicMaterial({color:hub.color,blending:THREE.AdditiveBlending,depthWrite:false}));system.add(packet);
    routes.push({curve,packet,phase:i/8});
  });

  // Volumetric point cloud around the federation.
  const count=mobile?480:900,positions=new Float32Array(count*3),colors=new Float32Array(count*3);
  const palette=[new THREE.Color(0xa8d7c5),new THREE.Color(0x88abbc),new THREE.Color(0xeaf0ee)];
  for(let i=0;i<count;i++){
    const r=3.6+Math.random()*3.8,theta=Math.random()*Math.PI*2,phi=Math.acos(2*Math.random()-1);
    positions[i*3]=r*Math.sin(phi)*Math.cos(theta);positions[i*3+1]=r*Math.cos(phi)*.62;positions[i*3+2]=r*Math.sin(phi)*Math.sin(theta);
    const c=palette[(Math.random()*palette.length)|0];colors.set([c.r,c.g,c.b],i*3);
  }
  const dustGeo=new THREE.BufferGeometry();dustGeo.setAttribute('position',new THREE.BufferAttribute(positions,3));dustGeo.setAttribute('color',new THREE.BufferAttribute(colors,3));
  const dust=new THREE.Points(dustGeo,new THREE.PointsMaterial({size:.026,vertexColors:true,transparent:true,opacity:.55,blending:THREE.AdditiveBlending,depthWrite:false}));system.add(dust);

  const composer=new EffectComposer(renderer);composer.addPass(new RenderPass(scene,camera));
  const bloom=new UnrealBloomPass(new THREE.Vector2(1,1),.22,.45,.72);composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const clock=new THREE.Clock();

  function resize3d(){const w=Math.max(1,host.clientWidth),h=Math.max(1,host.clientHeight);renderer.setSize(w,h,false);composer.setSize(w,h);camera.aspect=w/h;camera.fov=w/h<.9?48:38;camera.updateProjectionMatrix()}
  new ResizeObserver(resize3d).observe(host);resize3d();

  function render(){
    const t=clock.getElapsedTime();
    if(!reduced){shell.rotation.y=t*.13;shell.rotation.x=Math.sin(t*.27)*.08;wire.rotation.set(-t*.07,t*.11,t*.035);kernel.rotation.set(t*.28,-t*.35,t*.17);ringGroup.rotation.y=t*.045;dust.rotation.y=-t*.018}
    const pulse=reduced?1:1+Math.sin(t*2.1)*.035;kernel.scale.setScalar(pulse);
    hubs.forEach((h,i)=>{if(reduced)return;const p=1+Math.sin(t*2.4+h.phase)*.14;h.halo.scale.setScalar(p);h.anomaly.rotation.z=t*(i===3?.85:.16)+h.phase});
    routes.forEach((r,i)=>!reduced&&r.packet.position.copy(r.curve.getPoint((t*(.16+(i%3)*.018)+r.phase)%1)));
    controls.update();composer.render();requestAnimationFrame(render);
  }
  render();
}catch(err){
  host.classList.add('webgl-fallback');
  console.warn('LOGOS 3D scene unavailable',err);
}
