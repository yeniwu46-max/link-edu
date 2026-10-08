import { Scene, WebGLRenderer, PerspectiveCamera, HemisphereLight, DirectionalLight, SRGBColorSpace, ACESFilmicToneMapping } from 'three'
import { buildInteractiveModel } from './interactiveModels.js'
import { disposeScene } from './heroAvatarScene.js'

export function createInteractiveModel(host, { kind, policy: initialPolicy, onError }) {
  const scene = new Scene(), model = buildInteractiveModel(kind)
  const renderer = new WebGLRenderer({ alpha: true, antialias: initialPolicy.finePointer, powerPreference: 'low-power' })
  renderer.outputColorSpace = SRGBColorSpace; renderer.toneMapping = ACESFilmicToneMapping; renderer.toneMappingExposure = 1.25
  renderer.setClearColor(0, 0); host.append(renderer.domElement); scene.add(model.root)
  scene.add(new HemisphereLight(0xe9d3ff, 0x24142c, 2.7))
  const key = new DirectionalLight(0xffe4cd, 4); key.position.set(-3, 4, 5); scene.add(key)
  const rim = new DirectionalLight(0xb679ff, 4); rim.position.set(3, 1, -2); scene.add(rim)
  const camera = new PerspectiveCamera(38, 1, .1, 20)
  let policy = initialPolicy, visible = false, disposed = false, raf = 0, previous = 0, reactedAt = -Infinity, frames = 0
  let yaw = 0, pitch = 0, expansion = 0, targetYaw = 0, targetPitch = 0, expanded = false, px = 0, py = 0, quiet = false
  const baseYaw = kind === 'robot' ? 0 : -.42
  function render(now, delta) {
    const mix = policy.reducedMotion ? 1 : 1 - Math.exp(-delta / .13)
    yaw += (targetYaw - yaw) * mix; pitch += (targetPitch - pitch) * mix; expansion += (Number(expanded) - expansion) * mix
    const age = now - reactedAt, reaction = !policy.reducedMotion && !quiet && age < 1000 ? Math.sin(age / 1000 * Math.PI) : 0
    model.root.rotation.set((kind === 'robot' ? 0 : -.13) + pitch, baseYaw + yaw, 0)
    model.pose({ expansion, pointerX: policy.reducedMotion ? 0 : px, pointerY: policy.reducedMotion ? 0 : py, reaction, reduced: policy.reducedMotion })
    renderer.render(scene, camera); host.dataset.frames = String(++frames)
    return Math.abs(targetYaw - yaw) + Math.abs(targetPitch - pitch) + Math.abs(Number(expanded) - expansion) > .001 || (!quiet && age >= 0 && age < 1000)
  }
  function tick(now) {
    raf = 0
    if (disposed || !visible || !policy.visible) return
    const elapsed = now - previous, interval = 1000 / 30
    if (previous && elapsed < interval - .5) { raf = requestAnimationFrame(tick); return }
    previous = now - elapsed % interval
    const settling = render(now, Math.min(elapsed / 1000 || .1, .1))
    if (!policy.reducedMotion && settling) raf = requestAnimationFrame(tick)
    else host.dataset.motion = 'resting'
  }
  function wake() {
    if (disposed || !visible || !policy.visible || raf) return
    host.dataset.motion = policy.reducedMotion ? 'static' : 'settling'
    previous = 0; raf = requestAnimationFrame(tick)
  }
  function resize() {
    if (disposed) return
    const w = Math.max(1, host.clientWidth), h = Math.max(1, host.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, policy.finePointer ? 1.25 : 1)); renderer.setSize(w, h, false)
    camera.aspect = w / h; camera.position.set(0, kind === 'robot' ? 0 : .15, Math.max(kind === 'robot' ? 3.1 : 4.3, 2.7 / camera.aspect)); camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); wake()
  }
  function lost(event) { event.preventDefault(); dispose(); onError?.() }
  function dispose() {
    if (disposed) return
    disposed = true; cancelAnimationFrame(raf); observer.disconnect()
    renderer.domElement.removeEventListener('webglcontextlost', lost)
    disposeScene(scene); renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove(); host.dataset.disposed = 'true'
  }
  const observer = new ResizeObserver(resize); observer.observe(host)
  renderer.domElement.addEventListener('webglcontextlost', lost); resize()
  return {
    setVisible(next) { visible = next; if (next) wake(); else { cancelAnimationFrame(raf); raf = 0 } },
    setPolicy(next) { policy = next; if (!next.visible) { cancelAnimationFrame(raf); raf = 0 } else { resize(); wake() } },
    setState(next) { expanded = next.active; quiet = next.quiet; wake() },
    react() { reactedAt = performance.now(); wake() },
    setPointer(x, y) { px = x; py = y; if (!policy.reducedMotion) { targetPitch = -y * .12; wake() } },
    setRotation(value) { targetYaw = value; wake() },
    dispose,
  }
}
