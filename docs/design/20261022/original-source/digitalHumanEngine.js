import * as THREE from 'three';
import { createChibiAssistant } from './chibiAssistantScene.js';
import { disposeScene } from './heroAvatarScene.js';

export async function createDigitalHuman(host, { policy, onError, onReady }) {
  const renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true, powerPreference:'low-power' });
  renderer.setClearColor(0,0); renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  host.append(renderer.domElement);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(29,1,.01,30);
  scene.add(new THREE.HemisphereLight(0xfff5ee,0x7b759b,2.2));
  for (const [color,x,y,z,intensity] of [[0xfff0dc,-3,4,4,3],[0xd4deff,3,2,2,1.8],[0xd6c5ff,1,3,-3,2]]) {
    const light = new THREE.DirectionalLight(color,intensity); light.position.set(x,y,z); scene.add(light);
  }
  const character = createChibiAssistant(); scene.add(character.root);
  let frames=0, renderMs=0, disposed=false, visible=true, raf=0, last=0, elapsed=0;
  let state='idle', level=0, pointer=0, dirty=true;
  function stop() { cancelAnimationFrame(raf); raf=0; last=0; }
  function render() {
    character.pose(elapsed,state,level,pointer,policy.reducedMotion);
    const started=performance.now(); renderer.render(scene,camera); renderMs+=performance.now()-started; frames++; dirty=false;
  }
  function frame(now) {
    raf=0;
    if(disposed||!visible||!policy.visible)return;
    if(now-last<1000/30-.3){raf=requestAnimationFrame(frame);return;}
    elapsed+=Math.min(.06,(now-last)/1000||.033);last=now;
    render();
    if(!policy.reducedMotion)raf=requestAnimationFrame(frame);
  }
  function wake(){if(!raf&&!disposed&&visible&&policy.visible&&(dirty||!policy.reducedMotion))raf=requestAnimationFrame(frame);}
  function resize() {
    if(disposed)return;
    const {width,height}=host.getBoundingClientRect();
    renderer.setPixelRatio(Math.min(devicePixelRatio,policy.finePointer?1.25:1));
    renderer.setSize(Math.max(1,width),Math.max(1,height));
    camera.aspect=Math.max(1,width)/Math.max(1,height);
    const distance=Math.max(2.55,1.65/camera.aspect)/(2*Math.tan(THREE.MathUtils.degToRad(camera.fov/2)));
    camera.position.set(0,1.26,distance);camera.lookAt(0,1.26,0);camera.updateProjectionMatrix();dirty=true;wake();
  }
  const lost=event=>{event.preventDefault();onError?.();handle.dispose();};
  renderer.domElement.addEventListener('webglcontextlost',lost);
  const observer=new ResizeObserver(resize);observer.observe(host);
  const handle={
    snapshot(){render();return renderer.domElement.toDataURL('image/png');},
    stats(){return {frames,renderMs,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,disposed};},
    setPolicy(next){policy=next;dirty=true;resize();if(!policy.visible)stop();else wake();},
    setVisible(value){visible=value;if(!value)stop();else{dirty=true;wake();}},
    setState(next,audioLevel=0){state=next;level=audioLevel;dirty=true;wake();},
    setPointer(value){pointer=Math.max(-1,Math.min(1,value));dirty=true;wake();},
    dispose(){if(disposed)return;disposed=true;stop();observer.disconnect();renderer.domElement.removeEventListener('webglcontextlost',lost);disposeScene(scene);renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();},
  };
  resize();render();onReady?.(renderer.domElement);wake();
  return handle;
}
