import { AnimationMixer, Box3, Color, Group, HemisphereLight, DirectionalLight,
  Mesh, MeshBasicMaterial, MeshStandardMaterial, CylinderGeometry, RingGeometry, PerspectiveCamera, Vector3, LoopOnce } from 'three'

export function prepareStudentAvatar(scene, gltf, accent, glasses) {
  const model = gltf.scene
  const bounds = new Box3().setFromObject(model), size = bounds.getSize(new Vector3())
  const center = bounds.getCenter(new Vector3()), scale = 1.55 / (size.y || 1)
  const group = new Group()
  model.scale.multiplyScalar(scale)
  model.position.set(-center.x * scale, -bounds.min.y * scale, -center.z * scale)
  group.add(model)
  scene.add(group)
  const surface = { time: { value: 0 }, glow: { value: .18 }, scan: { value: 1 } }
  model.traverse(node => {
    if (!node.isMesh) return
    node.frustumCulled = false
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
      // Preserve the source atlas and face; add rim light directly to its existing material.
      material.metalness = .24
      material.roughness = .5
      material.color.lerp(new Color(accent), .32)
      material.emissive = new Color(accent)
      material.emissiveIntensity = .12
      material.onBeforeCompile = shader => {
        shader.uniforms.uStudentTime = surface.time
        shader.uniforms.uStudentGlow = surface.glow
        shader.uniforms.uStudentScan = surface.scan
        shader.uniforms.uStudentAccent = { value: new Color(accent) }
        shader.fragmentShader = 'uniform float uStudentTime; uniform float uStudentGlow; uniform float uStudentScan; uniform vec3 uStudentAccent;\n' + shader.fragmentShader
        shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>',
          `#include <emissivemap_fragment>
          float rim = pow(1.0 - max(dot(normalize(vNormal), normalize(vViewPosition)), 0.0), 2.0);
          float scan = smoothstep(0.93, 1.0, sin(vViewPosition.y * 56.0 + uStudentTime * 1.5));
          totalEmissiveRadiance += uStudentAccent * (rim * (0.6 + uStudentGlow) + scan * 0.08 * uStudentScan);`)
      }
      material.customProgramCacheKey = () => 'link-student-hologram-v1'
      material.needsUpdate = true
    }
  })
  const head = model.getObjectByName('head'), arm = model.getObjectByName('arm-right')
  if (glasses && head) {
    // This accessory is authored around its own origin; place it in the source head's local units.
    glasses.scene.position.set(0, .135, .1)
    head.add(glasses.scene)
    glasses.scene.traverse(node => {
      if (!node.isMesh) return
      node.frustumCulled = false
      node.material.emissive = new Color(accent)
      node.material.emissiveIntensity = .25
    })
  }
  scene.add(new HemisphereLight(0xf4dfff, 0x251737, 2.4))
  const key = new DirectionalLight(0xffede1, 3)
  key.position.set(-2, 3, 4)
  scene.add(key)
  const rim = new DirectionalLight(accent, 4)
  rim.position.set(2, 2, -2)
  scene.add(rim)
  const ring = new Mesh(new RingGeometry(.47, .51, 48), new MeshBasicMaterial({ color: accent, transparent: true, opacity: .6, depthWrite: false }))
  ring.rotation.x = -Math.PI / 2
  ring.position.y = .012
  scene.add(ring)
  const platform = new Mesh(new CylinderGeometry(.51, .6, .055, 40), new MeshStandardMaterial({color:'#24172f',metalness:.65,roughness:.4}))
  platform.position.y = -.04; scene.add(platform)
  const halo = new Mesh(new RingGeometry(.58, .6, 48, 1, .2, Math.PI * 1.65), new MeshBasicMaterial({color:accent,transparent:true,opacity:.25,depthWrite:false}))
  halo.rotation.x = -Math.PI / 2; halo.position.y = -.006; scene.add(halo)
  const mixer = new AnimationMixer(model)
  const idle = gltf.animations.find(clip => clip.name === 'idle')
  const idleAction = idle ? mixer.clipAction(idle) : null
  if (idleAction) { idleAction.play(); mixer.setTime(.2) }
  const yes = gltf.animations.find(clip => clip.name === 'emote-yes')
  const nod = yes ? mixer.clipAction(yes).setLoop(LoopOnce, 1) : null
  mixer.addEventListener('finished', event => { if (event.action === nod) { nod.fadeOut(.2); idleAction?.reset().fadeIn(.2).play() } })
  const camera = new PerspectiveCamera(42, 1, .1, 30)
  return { scene, model, group, head, arm, mixer, camera, surface, ring, halo, width: size.x * scale,
    headRest: head?.quaternion.clone(), armRest: arm?.quaternion.clone(),
    motion: { raised: 0, thinking: 0, speaking: 0 }, pointer: 0, gaze: 0, turn: 0, rotation: 0,
    acknowledge() { if (nod) { idleAction?.fadeOut(.2); nod.reset().fadeIn(.2).play() } } }
}

export function poseStudent(avatar, state, now, delta, reduced) {
  const mix = reduced ? 1 : 1 - Math.exp(-Math.max(delta, .001) / .23)
  for (const key of ['raised', 'thinking', 'speaking']) avatar.motion[key] += (Number(state[key]) - avatar.motion[key]) * mix
  // Restore the base pose before the mixer and overlays so untracked bones cannot accumulate rotation.
  if (avatar.head) avatar.head.quaternion.copy(avatar.headRest)
  if (avatar.arm) avatar.arm.quaternion.copy(avatar.armRest)
  if (reduced) avatar.mixer.setTime(.2)
  else avatar.mixer.update(delta)
  const { raised, thinking, speaking } = avatar.motion
  avatar.gaze += ((reduced ? 0 : avatar.pointer) - avatar.gaze) * mix
  avatar.rotation += (avatar.turn - avatar.rotation) * mix
  if (avatar.arm) { avatar.arm.rotation.z -= raised * 2.3; avatar.arm.rotation.x -= raised * .25 }
  if (avatar.head) {
    avatar.head.rotation.y += thinking * -.15 + avatar.gaze * .22
    avatar.head.rotation.x += reduced ? 0 : speaking * Math.sin(now / 180) * (.035 + state.level * .08)
  }
  avatar.group.rotation.y = -.14 + avatar.rotation + avatar.gaze * .12
  avatar.surface.time.value = reduced ? 0 : now / 1000
  avatar.surface.scan.value = reduced ? 0 : 1
  avatar.surface.glow.value = .18 + speaking * (.35 + state.level * .45) + raised * .15
  avatar.ring.material.opacity = .5 + raised * .25 + speaking * .2
  avatar.halo.material.opacity = .25 + speaking * (.25 + state.level * .3) + raised * .16
  avatar.halo.rotation.z = reduced ? 0 : speaking * Math.sin(now / 1200) * .25
}
