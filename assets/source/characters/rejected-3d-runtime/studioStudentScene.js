import { AnimationMixer, Box3, Group, HemisphereLight, DirectionalLight, PerspectiveCamera, Vector3 } from 'three'
import { createStudioRig } from './studioCharacterRig.js'

export function prepareStudioStudent(scene, gltf) {
  const model=gltf.scene, bounds=new Box3().setFromObject(model), size=bounds.getSize(new Vector3())
  const center=bounds.getCenter(new Vector3()), scale=1.75/(size.y||1), group=new Group()
  model.scale.multiplyScalar(scale); model.position.set(-center.x*scale,-bounds.min.y*scale,-center.z*scale)
  group.add(model); scene.add(group)
  scene.add(new HemisphereLight(0xfff4e6,0x77718c,1.7))
  for(const [color,x,y,z,power] of [[0xfff1dd,-3,4,4,2.4],[0xdde8ff,3,2,2,1.2],[0xe2d7f7,0,3,-3,1.4]]){
    const light=new DirectionalLight(color,power);light.position.set(x,y,z);scene.add(light)
  }
  const rig=createStudioRig(model,true)
  let acknowledged=-10
  return { studio:true, scene,model,group,rig,camera:new PerspectiveCamera(42,1,.1,30),
    mixer:new AnimationMixer(model), width:Math.max(.95,size.x*scale), pointer:0,turn:0,gaze:0,rotation:0,
    motion:{raised:0,thinking:0,speaking:0},
    acknowledge(){acknowledged=performance.now()/1000},
    pose(state,now,delta,reduced){
      const mix=reduced?1:1-Math.exp(-Math.max(delta,.001)/.23)
      for(const key of ['raised','thinking','speaking'])this.motion[key]+=(Number(state[key])-this.motion[key])*mix
      this.rotation+=(this.turn-this.rotation)*mix;this.gaze+=(this.pointer-this.gaze)*mix
      const elapsed=now/1000-acknowledged,nod=!reduced&&elapsed>=0&&elapsed<.75 ? Math.sin(elapsed/.75*Math.PI*2)*.1 : 0
      rig.pose(now/1000,{...this.motion,level:state.level,turn:this.rotation,pointer:this.gaze,nod},reduced,delta)
    } }
}
