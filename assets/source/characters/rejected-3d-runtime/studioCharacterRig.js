import { Quaternion, Vector3, MathUtils } from 'three'

// One bone/morph contract for the student family and assistant.
export function createStudioRig(root, seated = true) {
  const bones = {}, rest = new Map(), morphs = []
  root.traverse(node => {
    if (node.isBone) { bones[node.name] = node; rest.set(node, { q:node.quaternion.clone(), p:node.position.clone() }) }
    if (node.morphTargetDictionary) morphs.push(node)
  })
  root.updateMatrixWorld(true)
  const upper = bones.upper_arm_R, forearm = bones.forearm_R
  const restElbow = forearm ? root.worldToLocal(forearm.getWorldPosition(new Vector3())) : new Vector3()
  const restWrist = bones.hand_R ? root.worldToLocal(bones.hand_R.getWorldPosition(new Vector3())) : new Vector3()
  let open = 0
  function aim(bone, localTarget) {
    if (!bone) return
    root.updateMatrixWorld(true)
    const target = root.localToWorld(localTarget.clone())
    const world = bone.getWorldQuaternion(new Quaternion())
    const direction = target.sub(bone.getWorldPosition(new Vector3())).normalize()
    const delta = new Quaternion().setFromUnitVectors(new Vector3(0,1,0).applyQuaternion(world), direction)
    bone.quaternion.copy(bone.parent.getWorldQuaternion(new Quaternion()).invert().multiply(delta).multiply(world))
    bone.updateMatrixWorld(true)
  }
  function pose(time, state = {}, reduced = false, delta = .033) {
    for (const [bone, value] of rest) { bone.quaternion.copy(value.q); bone.position.copy(value.p) }
    const turn = MathUtils.clamp(state.turn || 0,-.35,.35), gaze = reduced ? 0 : (state.pointer || 0)
    const raised = Number(state.raised) || 0, thinking = Number(state.thinking) || 0, speaking = Number(state.speaking) || 0
    if (bones.head) {
      bones.head.rotation.y += turn + gaze * .13 - thinking * .08
      bones.head.rotation.x += thinking * .11 + (reduced ? 0 : Math.sin(time*2.1) * .012 + speaking * Math.sin(time*5.5) * .018 + (state.nod || 0))
      if (!reduced && !speaking && !raised && !thinking) bones.head.rotation.x += Math.max(0,Math.sin(time*.32)-.92)*1.2
    }
    if (bones.torso) {
      bones.torso.rotation.y += turn * .15
      if (!reduced) bones.torso.position.y += Math.sin(time*1.8)*.003
    }
    if (seated && raised) {
      aim(upper,restElbow.clone().lerp(new Vector3(.44,1.44,-.05),raised))
      aim(forearm,restWrist.clone().lerp(new Vector3(.46,1.80,.04),raised))
    } else if (!seated && bones.upper_arm_L) {
      bones.upper_arm_L.rotation.z += thinking*.25 + speaking*(.18 + (reduced ? 0 : Math.sin(time*2.3)*.07))
      if (bones.forearm_L) bones.forearm_L.rotation.x -= thinking*.3 + speaking*.2
    }
    const target = speaking ? MathUtils.clamp(Number(state.level)||0,0,1) : 0
    open += (target-open) * (reduced ? 1 : 1-Math.exp(-Math.max(delta,.001)/.06))
    const cycle=time%4.7, blink=reduced ? 0 : Math.max(0,1-Math.abs(cycle-4.4)/.09)
    for (const mesh of morphs) {
      for (const [name,index] of Object.entries(mesh.morphTargetDictionary)) {
        mesh.morphTargetInfluences[index] = name === 'blink' ? blink : name === 'open' ? open : 0
      }
    }
    root.updateMatrixWorld(true)
  }
  return { bones, morphs, pose }
}
