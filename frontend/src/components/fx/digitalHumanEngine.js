import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm'

export async function createDigitalHuman(host, { policy, onError, onReady }) {
  const renderer = new THREE.WebGLRenderer({ alpha:true, antialias:true, powerPreference:'low-power' })
  renderer.setClearColor(0,0); renderer.outputColorSpace = THREE.SRGBColorSpace
  host.append(renderer.domElement)
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(29,1,.01,30)
  scene.add(new THREE.HemisphereLight(0xf5e4ff,0x513253,2.1))
  for (const [color,x,z] of [[0xc896ff,-2,2],[0xffac72,2,1]]) { const l = new THREE.DirectionalLight(color,2);l.position.set(x,2,z);scene.add(l) }
  let frames=0, renderMs=0
  let disposed=false, visible=true, raf=0, last=0, elapsed=0, vrm, state='idle', level=0, pointer=0, dirty=true
  const rendererLost = event => { event.preventDefault(); onError(); handle.dispose() }
  renderer.domElement.addEventListener('webglcontextlost',rendererLost)
  function stop() { cancelAnimationFrame(raf);raf=0;last=0 }
  function resize() { if(disposed)return;const {width,height}=host.getBoundingClientRect();renderer.setPixelRatio(Math.min(devicePixelRatio,policy.finePointer?1.25:1));renderer.setSize(Math.max(1,width),Math.max(1,height));camera.aspect=width/Math.max(1,height);camera.updateProjectionMatrix();dirty=true;wake() }
  function frame(now) {
    raf=0;if(disposed||!visible||!policy.visible||!vrm)return
    if(now-last<1000/30-.3){raf=requestAnimationFrame(frame);return}
    const delta=Math.min(.06,(now-last)/1000||.033);last=now;elapsed+=delta
    const reduced=policy.reducedMotion
    const head=vrm.humanoid.getNormalizedBoneNode('head'), spine=vrm.humanoid.getNormalizedBoneNode('spine')
    if(head){head.rotation.y=reduced?0:pointer*.16;head.rotation.z=state==='thinking'?.09:0;head.rotation.x=state==='listening'?-.04:!reduced&&state==='speaking'?Math.sin(elapsed*9)*level*.055:0}
    if(spine)spine.rotation.z=reduced?0:Math.sin(elapsed*1.2)*.012
    const blink=!reduced&&elapsed%4.5>4.34?Math.sin((elapsed%4.5-4.34)/.16*Math.PI):0
    vrm.expressionManager?.setValue('blink',Math.max(0,blink))
    vrm.expressionManager?.setValue('aa',state==='speaking'?Math.min(.9,level):0)
    vrm.expressionManager?.setValue('happy',state==='listening'?.18:.06)
    const renderStarted=performance.now();vrm.update(reduced?0:delta);renderer.render(scene,camera);renderMs+=performance.now()-renderStarted;frames++;dirty=false
    if(!reduced&&(state!=='idle'||visible))raf=requestAnimationFrame(frame)
  }
  function wake(){if(!raf&&!disposed&&visible&&policy.visible&&vrm&&(dirty||!policy.reducedMotion))raf=requestAnimationFrame(frame)}
  const observer=new ResizeObserver(resize);observer.observe(host)
  const handle={snapshot(){renderer.render(scene,camera);return renderer.domElement.toDataURL('image/png')},stats(){return {frames,renderMs,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,disposed}},setPolicy(next){policy=next;dirty=true;resize();if(!policy.visible)stop();else wake()},setVisible(value){visible=value;if(!value)stop();else {dirty=true;wake()}},setState(next,audioLevel=0){state=next;level=audioLevel;dirty=true;wake()},setPointer(value){pointer=value;dirty=true;wake()},dispose(){if(disposed)return;disposed=true;stop();observer.disconnect();renderer.domElement.removeEventListener('webglcontextlost',rendererLost);if(vrm)VRMUtils.deepDispose(vrm.scene);renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove()}}
  // Return the owner immediately so unmount can release the context during loading.
  const loader=new GLTFLoader().register(parser=>new VRMLoaderPlugin(parser))
  loader.load('/assets/models/assistant/olivia.vrm',gltf=>{
    if(disposed){VRMUtils.deepDispose(gltf.scene);return}
    vrm=gltf.userData.vrm;VRMUtils.rotateVRM0(vrm)
    vrm.humanoid.setNormalizedPose({leftUpperArm:{rotation:new THREE.Quaternion().setFromEuler(new THREE.Euler(0,0,1.18)).toArray()},rightUpperArm:{rotation:new THREE.Quaternion().setFromEuler(new THREE.Euler(0,0,-1.18)).toArray()}})
    vrm.update(0);scene.add(vrm.scene);vrm.scene.updateMatrixWorld(true)
    const box=new THREE.Box3().setFromObject(vrm.scene),h=box.max.y-box.min.y
    camera.position.set(0,box.min.y+h*.77,h*1.07);camera.lookAt(0,box.min.y+h*.77,0)
    resize();onReady?.(renderer.domElement);wake()
  },undefined,()=>{if(!disposed){stop();onError();handle.dispose()}})
  return handle
}
