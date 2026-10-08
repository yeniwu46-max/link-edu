import { Scene, WebGLRenderer, PerspectiveCamera, AnimationMixer, ACESFilmicToneMapping, SRGBColorSpace } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { prepareAvatar, disposeScene } from './heroAvatarScene.js'
import { clamp, motionQuality } from '../../utils/motionPreferences.js'

export async function createHeroAvatar(host, { modelSrc, signal, policy: initialPolicy, onError }) {
  const loadStart = performance.now()
  const scene = new Scene()
  const renderer = new WebGLRenderer({ alpha: true, antialias: initialPolicy.finePointer, powerPreference: 'low-power' })
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = SRGBColorSpace
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15
  renderer.domElement.setAttribute('aria-hidden', 'true')
  host.append(renderer.domElement)
  const camera = new PerspectiveCamera(38, 1, .1, 20)
  let policy = initialPolicy, inView = true, disposed = false, slow = false
  let frame = 0, lastRender = 0, lastTick = 0, sampleStart = 0, frameTime = 0, ticks = 0, renderCount = 0, renderCost = 0, fastSamples = 0
  let mixer, model, avatar, violet, resizeObserver
  const pointer = { x: 0, y: 0 }, current = { x: 0, y: 0 }

  function resize() {
    if (disposed) return
    const width = host.clientWidth || 1, height = host.clientHeight || 1
    const quality = motionQuality(policy.finePointer, slow)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, quality.pixelRatio))
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    host.dataset.quality = String(quality.fps)
  }
  function render(now, delta = 0) {
    if (!avatar) return
    const start = performance.now()
    if (!policy.reducedMotion) {
      current.x += (pointer.x - current.x) * .12
      current.y += (pointer.y - current.y) * .12
      avatar.rotation.y = -.18 + current.x * .15 + Math.sin(now / 6000) * .07
      mixer.update(delta)
    } else {
      current.x = current.y = 0
      avatar.rotation.y = -.18
    }
    camera.position.set(.15 + current.x * .1, 1.68 + current.y * .06, 2.65)
    camera.lookAt(0, 1.62, 0)
    violet.position.x = 1.8 + current.x * .35
    renderer.render(scene, camera)
    renderCost += performance.now() - start
    renderCount++
  }
  function tick(now) {
    frame = 0
    if (disposed || !inView || !policy.visible || policy.reducedMotion) return
    if (lastTick) { frameTime += now - lastTick; ticks++ }
    lastTick = now
    if (!sampleStart) sampleStart = now
    if (now - lastRender >= 1000 / motionQuality(policy.finePointer, slow).fps - .5) {
      render(now, lastRender ? Math.min((now - lastRender) / 1000, .08) : 0)
      lastRender = now
    }
    if (now - sampleStart >= 2000) {
      const average = ticks ? frameTime / ticks : 0
      if (average > 25 && !slow) { slow = true; fastSamples = 0; resize() }
      else if (slow && average > 0 && average < 19) {
        if (++fastSamples >= 3) { slow = false; fastSamples = 0; resize() }
      } else fastSamples = 0
      host.dataset.renderFps = (renderCount * 1000 / (now - sampleStart)).toFixed(1)
      host.dataset.renderMs = (renderCount ? renderCost / renderCount : 0).toFixed(2)
      frameTime = ticks = renderCount = renderCost = 0
      sampleStart = now
    }
    frame = requestAnimationFrame(tick)
  }
  function sync() {
    cancelAnimationFrame(frame)
    frame = 0
    lastRender = lastTick = sampleStart = frameTime = ticks = renderCount = renderCost = 0
    host.dataset.motion = policy.reducedMotion ? 'static' : 'animated'
    host.dataset.effectVisible = String(policy.visible && inView)
    if (disposed || !inView || !policy.visible || !avatar) return
    if (policy.reducedMotion) render(0)
    else frame = requestAnimationFrame(tick)
  }
  function lost(event) {
    event.preventDefault()
    if (!disposed) { dispose(); onError?.() }
  }
  function dispose() {
    if (disposed) return
    disposed = true
    cancelAnimationFrame(frame)
    resizeObserver?.disconnect()
    renderer.domElement.removeEventListener('webglcontextlost', lost)
    mixer?.stopAllAction()
    if (model) mixer?.uncacheRoot(model)
    disposeScene(scene)
    renderer.dispose()
    renderer.forceContextLoss()
    renderer.domElement.remove()
  }
  renderer.domElement.addEventListener('webglcontextlost', lost)
  try {
    const response = await fetch(modelSrc, { signal })
    if (!response.ok) throw new Error('Avatar asset unavailable: ' + response.status)
    const gltf = await new GLTFLoader().parseAsync(await response.arrayBuffer(), '')
    if (signal.aborted || disposed) { disposeScene(gltf.scene); throw new DOMException('Aborted', 'AbortError') }
    model = gltf.scene
    const prepared = prepareAvatar(scene, model)
    avatar = prepared.avatar
    violet = prepared.violet
    mixer = new AnimationMixer(model)
    if (gltf.animations.length) {
      mixer.clipAction(gltf.animations[0]).play()
      mixer.timeScale = .4
      mixer.setTime(.8)
    }
    resize()
    render(0)
    host.dataset.loadMs = (performance.now() - loadStart).toFixed(1)
    resizeObserver = new ResizeObserver(() => { resize(); if (policy.visible && inView) render(0) })
    resizeObserver.observe(host)
    sync()
    return {
      setPolicy(next) { policy = next; if (next.reducedMotion || !next.finePointer) pointer.x = pointer.y = 0; resize(); sync() },
      setVisible(value) { inView = value; sync() },
      setPointer(x, y) {
        if (!policy.reducedMotion && policy.finePointer) {
          pointer.x = clamp(x, -1, 1); pointer.y = clamp(y, -1, 1)
        }
      },
      dispose,
    }
  } catch (error) { dispose(); throw error }
}
