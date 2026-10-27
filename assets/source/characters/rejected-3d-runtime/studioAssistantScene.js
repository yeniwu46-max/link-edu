import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { Box3, Vector3 } from 'three'
import { createStudioRig } from './studioCharacterRig.js'
import { disposeScene } from './heroAvatarScene.js'
export async function createStudioAssistant(signal) {
  const response=await fetch('/assets/models/studio/assistant.glb',{signal})
  if(!response.ok)throw new Error('Assistant model unavailable')
  const gltf=await new GLTFLoader().parseAsync(await response.arrayBuffer(),'/assets/models/studio/')
  if(signal?.aborted){disposeScene(gltf.scene);throw new DOMException('Aborted','AbortError')}
  const root=gltf.scene,box=new Box3().setFromObject(root),size=box.getSize(new Vector3()),center=box.getCenter(new Vector3())
  const scale=2.25/size.y;root.scale.multiplyScalar(scale);root.position.set(-center.x*scale,-box.min.y*scale,-center.z*scale)
  const rig=createStudioRig(root,false)
  return {root,pose(time,state,level,pointer,reduced){rig.pose(time,{speaking:state==='speaking',thinking:state==='thinking'||state==='listening',level,pointer},reduced)}}
}
