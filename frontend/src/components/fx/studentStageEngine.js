import { Scene, WebGLRenderer, SRGBColorSpace, ACESFilmicToneMapping } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { prepareStudentAvatar, poseStudent } from './studentAvatarScene.js'
import { disposeScene } from './heroAvatarScene.js'
import { STUDENT_MODELS, studentMotionState, studentRenderQuality } from '../../services/studentStageState.js'

export async function createStudentStage(host, { signal, policy: initialPolicy, getSlots, onModelState, modelBase }) {
  const began = performance.now(), avatars = new Map(), loader = new GLTFLoader()
  const renderer = new WebGLRenderer({ alpha: true, antialias: initialPolicy.finePointer, powerPreference: 'low-power' })
  renderer.outputColorSpace = SRGBColorSpace
  renderer.toneMapping = ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15
  renderer.autoClear = false
  renderer.setClearColor(0, 0)
  renderer.domElement.setAttribute('aria-hidden', 'true')
  host.append(renderer.domElement)
  const frameCanvas = document.createElement('canvas'), frameContext = frameCanvas.getContext('2d')
  let snapshot = null, state = {}, policy = initialPolicy, visible = true, disposed = false, slow = false, capture = false
  let raf = 0, previous = 0, sampledAt = 0, frames = 0, renderCost = 0, lastCapture = 0, slowSamples = 0
  let closeView = false, proximity = 0, lastRendered = 0
  const rects = new Map()
  function resize() {
    if (disposed) return
    const quality = studentRenderQuality(policy.finePointer, slow)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, quality.pixelRatio))
    renderer.setSize(Math.max(1, host.clientWidth), Math.max(1, host.clientHeight), false)
    host.dataset.quality = String(quality.fps)
    updateSlots()
  }
  function updateSlots() {
    const root = host.getBoundingClientRect()
    rects.clear()
    for (const slot of getSlots()) {
      const r = slot.element.getBoundingClientRect()
      if (r.width && r.height) rects.set(slot.id, { x: r.left - root.left, y: r.top - root.top, width: r.width, height: r.height })
    }
  }
  function cacheFrame(now) {
    if (!frameContext || (lastCapture && now - lastCapture < 1000 / 24)) return
    const canvas = renderer.domElement
    if (frameCanvas.width !== canvas.width || frameCanvas.height !== canvas.height) { frameCanvas.width = canvas.width; frameCanvas.height = canvas.height }
    frameContext.clearRect(0, 0, frameCanvas.width, frameCanvas.height)
    // Copy in the same task as WebGL rendering; preserveDrawingBuffer stays disabled.
    frameContext.drawImage(canvas, 0, 0)
    const ratio = renderer.getPixelRatio()
    snapshot = { canvas: frameCanvas, slots: Object.fromEntries([...rects].filter(([id]) => avatars.has(id)).map(([id, r]) =>
      [id, { x: r.x * ratio, y: r.y * ratio, width: r.width * ratio, height: r.height * ratio }])) }
    lastCapture = now
  }
  function render(now, delta = 0) {
    if (disposed) return
    const beganRender = performance.now()
    renderer.setScissorTest(false)
    renderer.clear()
    renderer.setScissorTest(true)
    proximity += (Number(closeView) - proximity) * (policy.reducedMotion ? 1 : 1 - Math.exp(-Math.max(delta, .001) / .23))
    for (const [id, avatar] of avatars) {
      const rect = rects.get(id)
      if (!rect) continue
      poseStudent(avatar, studentMotionState(id, state), now, delta, policy.reducedMotion)
      avatar.camera.aspect = rect.width / rect.height
      const distance = Math.max(2.65, avatar.width / avatar.camera.aspect * 1.55)
      avatar.camera.position.set(0, 1.35 + proximity * .2, distance * (1 - proximity * .26))
      avatar.camera.lookAt(0, .78 + proximity * .25, 0)
      avatar.camera.updateProjectionMatrix()
      const y = host.clientHeight - rect.y - rect.height
      renderer.setViewport(rect.x, y, rect.width, rect.height)
      renderer.setScissor(rect.x, y, rect.width, rect.height)
      renderer.render(avatar.scene, avatar.camera)
    }
    renderer.setScissorTest(false)
    if (capture || !snapshot) cacheFrame(now)
    frames++
    renderCost += performance.now() - beganRender
  }
  function tick(now) {
    raf = 0
    if (disposed || !visible || !policy.visible || policy.reducedMotion) return
    const interval = 1000 / studentRenderQuality(policy.finePointer, slow).fps
    if (now - previous >= interval - .5) {
      render(now, lastRendered ? Math.min((now - lastRendered) / 1000, .1) : 0)
      lastRendered = now
      previous = now - (now - previous) % interval
    }
    if (!sampledAt) sampledAt = now
    if (now - sampledAt >= 2000) {
      const cost = frames ? renderCost / frames : 0
      host.dataset.renderFps = (frames * 1000 / (now - sampledAt)).toFixed(1)
      host.dataset.renderMs = cost.toFixed(2)
      // Shader compilation and a throttled background tab do not indicate sustained GPU pressure.
      slowSamples = frames >= 8 && cost > 18 ? slowSamples + 1 : 0
      if (!slow && slowSamples >= 3) { slow = true; resize() }
      sampledAt = now; frames = renderCost = 0
    }
    raf = requestAnimationFrame(tick)
  }
  function sync() {
    cancelAnimationFrame(raf); raf = 0; previous = lastRendered = sampledAt = frames = renderCost = 0
    host.dataset.motion = policy.reducedMotion ? 'static' : 'animated'
    host.dataset.effectVisible = String(visible && policy.visible)
    if (disposed || !visible || !policy.visible) return
    render(performance.now())
    if (!policy.reducedMotion) raf = requestAnimationFrame(tick)
  }
  function lost(event) { event.preventDefault(); dispose(); for (const id of Object.keys(STUDENT_MODELS)) onModelState(id, 'fallback') }
  function dispose() {
    if (disposed) return
    disposed = true; cancelAnimationFrame(raf); observer.disconnect()
    renderer.domElement.removeEventListener('webglcontextlost', lost)
    signal.removeEventListener('abort', dispose)
    for (const avatar of avatars.values()) { avatar.mixer.stopAllAction(); avatar.mixer.uncacheRoot(avatar.model); disposeScene(avatar.scene) }
    avatars.clear(); rects.clear(); snapshot = null; frameCanvas.width = frameCanvas.height = 0
    renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove()
    host.dataset.disposed = 'true'
  }
  const observer = new ResizeObserver(() => { resize(); sync() })
  observer.observe(host)
  renderer.domElement.addEventListener('webglcontextlost', lost)
  signal.addEventListener('abort', dispose, { once: true })
  async function load(file) {
    const response = await fetch(modelBase + file, { signal })
    if (!response.ok) throw new Error('Student model unavailable')
    const gltf = await loader.parseAsync(await response.arrayBuffer(), modelBase)
    if (disposed || signal.aborted) { disposeScene(gltf.scene); throw new DOMException('Aborted', 'AbortError') }
    return gltf
  }
  try {
    await Promise.all(Object.entries(STUDENT_MODELS).map(async ([id, config]) => {
      let gltf, glasses
      try {
        gltf = await load(config.file)
        if (id === 'lin') { try { glasses = await load('aid-glasses.glb') } catch (error) { if (signal.aborted) throw error } }
        if (disposed || signal.aborted) throw new DOMException('Aborted', 'AbortError')
        avatars.set(id, prepareStudentAvatar(new Scene(), gltf, config.color, glasses))
        resize(); sync(); onModelState(id, 'ready')
      } catch (error) {
        if (gltf && !avatars.has(id)) disposeScene(gltf.scene)
        if (glasses && !avatars.has(id)) disposeScene(glasses.scene)
        if (!disposed && !signal.aborted) onModelState(id, 'fallback')
      }
    }))
    if (signal.aborted || disposed) throw new DOMException('Aborted', 'AbortError')
    if (!avatars.size) throw new Error('No student models available')
    host.dataset.loadMs = (performance.now() - began).toFixed(1)
    resize(); sync()
    return {
      setState(next) { state = next; if (policy.reducedMotion && visible && policy.visible) { lastCapture = 0; render(performance.now()) } },
      setPolicy(next) { policy = next; resize(); sync() },
      setVisible(next) { visible = next; sync() },
      setCapture(next) { capture = next; lastCapture = 0; if (next && visible && policy.visible) render(performance.now()) },
      setPointer(id, value) { const avatar = avatars.get(id); if (avatar) avatar.pointer = policy.finePointer && !policy.reducedMotion ? value : 0 },
      setRotation(id, value) { const avatar = avatars.get(id); if (avatar) { avatar.turn = value; if (policy.reducedMotion && visible && policy.visible) { lastCapture = 0; render(performance.now()) } } },
      setView(close) { closeView = close; if (policy.reducedMotion && visible && policy.visible) { lastCapture = 0; render(performance.now()) } },
      acknowledge(id) { if (!policy.reducedMotion) avatars.get(id)?.acknowledge() },
      snapshot: () => snapshot,
      refreshSlots() { updateSlots(); if (visible && policy.visible) render(performance.now()) },
      dispose,
    }
  } catch (error) { dispose(); throw error }
}
