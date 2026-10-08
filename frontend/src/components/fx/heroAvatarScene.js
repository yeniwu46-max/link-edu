import {
  Box3, Vector3, Group, HemisphereLight, DirectionalLight, PointLight,
  MeshStandardMaterial, MeshBasicMaterial, Mesh, PlaneGeometry, CanvasTexture,
} from 'three'

export function prepareAvatar(scene, model) {
  const bounds = new Box3().setFromObject(model)
  const center = bounds.getCenter(new Vector3())
  const height = bounds.getSize(new Vector3()).y || 1
  const scale = 2.4 / height
  const avatar = new Group()
  model.scale.multiplyScalar(scale)
  model.position.set(-center.x * scale, -bounds.min.y * scale, -center.z * scale)
  avatar.add(model)
  avatar.rotation.y = -0.18
  scene.add(avatar)
  const meshes = []
  model.traverse(node => { if (node.isMesh) meshes.push(node) })
  const originals = new Set(), textures = new Set()
  meshes.forEach(mesh => {
    const previous = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    previous.forEach(material => {
      originals.add(material)
      Object.values(material).forEach(value => { if (value?.isTexture) textures.add(value) })
    })
    // Imported geometry and skeleton remain intact; replace the branded surface.
    mesh.material = new MeshStandardMaterial({
      color: 0x655569, metalness: 0.62, roughness: 0.36,
      emissive: 0x241035, emissiveIntensity: 0.28,
    })
    mesh.frustumCulled = false
    const wire = mesh.clone(false)
    wire.material = new MeshBasicMaterial({
      color: 0xc985ff, wireframe: true, transparent: true, opacity: 0.12,
      depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1,
    })
    wire.renderOrder = 1
    mesh.parent.add(wire)
  })
  originals.forEach(material => material.dispose())
  textures.forEach(texture => texture.dispose())
  scene.add(new HemisphereLight(0xcac0e2, 0x241020, 1.8))
  const key = new DirectionalLight(0xffe1c9, 3)
  key.position.set(-1, 3, 3)
  scene.add(key)
  const violet = new PointLight(0xb45cff, 18, 8, 2)
  violet.position.set(1.8, 2.5, 1)
  scene.add(violet)
  const orange = new PointLight(0xff7a18, 15, 8, 2)
  orange.position.set(-1.5, 1.5, .8)
  scene.add(orange)
  const shadowCanvas = document.createElement('canvas')
  shadowCanvas.width = shadowCanvas.height = 128
  const context = shadowCanvas.getContext('2d')
  if (context) {
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64)
    gradient.addColorStop(0, '#a05cff55')
    gradient.addColorStop(.4, '#17082488')
    gradient.addColorStop(1, '#00000000')
    context.fillStyle = gradient
    context.fillRect(0, 0, 128, 128)
  }
  const shadow = new Mesh(new PlaneGeometry(2.4, 2.4),
    new MeshBasicMaterial({ map: new CanvasTexture(shadowCanvas), transparent: true, depthWrite: false }))
  shadow.rotation.x = -Math.PI / 2
  shadow.position.y = .01
  scene.add(shadow)
  return { avatar, violet }
}

export function disposeScene(scene) {
  const geometries = new Set(), materials = new Set(), textures = new Set(), skeletons = new Set()
  scene.traverse(node => {
    if (node.geometry) geometries.add(node.geometry)
    for (const material of (Array.isArray(node.material) ? node.material : [node.material])) {
      if (!material) continue
      materials.add(material)
      Object.values(material).forEach(value => { if (value?.isTexture) textures.add(value) })
    }
    if (node.isSkinnedMesh && node.skeleton) skeletons.add(node.skeleton)
  })
  geometries.forEach(geometry => geometry.dispose())
  materials.forEach(material => material.dispose())
  textures.forEach(texture => texture.dispose())
  skeletons.forEach(skeleton => skeleton.dispose())
  scene.clear()
}
