import { animate } from 'motion-v'
import { subscribeMotionPreferences, tiltFromPoint } from './motionPreferences.js'

const instances = new WeakMap()
const depthSelector = [
  '.page-dashboard .weekly', '.page-dashboard .continue', '.page-dashboard .feedback',
  '.page-dashboard .entries article', '.page-dashboard .growth',
  '.course-slab', '.course-tile', '.mooc-card', '.training-card',
  '.resource-card-depth', '.resource-board-card',
].join(',')
const revealSelector = [
  depthSelector, '.growth-chart-panel', '.growth-heat-panel', '.growth-practice',
  '.growth-records', '.review-panel', '.review-hub-card',
].join(',')

function bindDepth(el, policy) {
  let rect, frame = 0, returnAnimation, returnRevision = 0
  const current = { x: 0, y: 0 }
  let target = { x: 0, y: 0 }
  const amplitude = el.matches('.continue') ? 6 : 4
  const sheen = document.createElement('span')
  sheen.className = 'fx-sheen'
  sheen.setAttribute('aria-hidden', 'true')
  el.append(sheen)
  el.classList.add('fx-depth')
  function tick() {
    frame = 0
    current.x += (target.x - current.x) * 0.2
    current.y += (target.y - current.y) * 0.2
    el.style.setProperty('--fx-rx', current.x.toFixed(3) + 'deg')
    el.style.setProperty('--fx-ry', current.y.toFixed(3) + 'deg')
    if (Math.abs(target.x - current.x) + Math.abs(target.y - current.y) > 0.015) frame = requestAnimationFrame(tick)
  }
  function reset() {
    returnRevision++
    cancelAnimationFrame(frame)
    frame = 0
    returnAnimation?.stop()
    current.x = current.y = target.x = target.y = 0
    for (const name of ['--fx-rx', '--fx-ry', '--fx-lift']) el.style.removeProperty(name)
    el.classList.remove('fx-hover')
    el.style.willChange = ''
  }
  function enter(event) {
    if (!policy().finePointer || policy().reducedMotion || event.pointerType === 'touch') return
    rect = el.getBoundingClientRect()
    returnRevision++
    returnAnimation?.stop()
    el.style.willChange = 'transform'
  }
  function move(event) {
    const prefs = policy()
    if (!prefs.visible || prefs.reducedMotion || !prefs.finePointer || event.pointerType === 'touch') return
    if (el.closest('.is-dragging')) { reset(); return }
    rect ||= el.getBoundingClientRect()
    const point = tiltFromPoint(rect, event.clientX, event.clientY, amplitude)
    target = point
    el.style.setProperty('--fx-light-x', point.lightX + '%')
    el.style.setProperty('--fx-light-y', point.lightY + '%')
    el.style.setProperty('--fx-lift', '-3px')
    el.classList.add('fx-hover')
    if (!frame) frame = requestAnimationFrame(tick)
  }
  function leave() {
    const revision = ++returnRevision
    rect = null
    cancelAnimationFrame(frame)
    frame = 0
    el.classList.remove('fx-hover')
    if (policy().reducedMotion || !policy().visible) return reset()
    returnAnimation?.stop()
    returnAnimation = animate(el, { '--fx-rx': '0deg', '--fx-ry': '0deg', '--fx-lift': '0px' },
      { type: 'spring', stiffness: 180, damping: 24, mass: 0.8 })
    returnAnimation.then(() => {
      if (revision !== returnRevision) return
      current.x = current.y = target.x = target.y = 0
      el.style.willChange = ''
    })
  }
  el.addEventListener('pointerenter', enter)
  el.addEventListener('pointermove', move, { passive: true })
  el.addEventListener('pointerleave', leave)
  return {
    reset,
    dispose() {
      reset()
      el.removeEventListener('pointerenter', enter)
      el.removeEventListener('pointermove', move)
      el.removeEventListener('pointerleave', leave)
      sheen.remove()
      el.classList.remove('fx-depth')
    },
  }
}

export const ambientUi = {
  mounted(root) {
    let policy = { reducedMotion: true, finePointer: false, visible: true }
    let scanFrame = 0, backgroundFrame = 0
    const depths = new Map(), reveals = new Set(), animations = new Map(), observed = new Set()
    const observer = new IntersectionObserver(entries => {
      entries.forEach(({ target, isIntersecting }) => {
        if (!isIntersecting) return
        observer.unobserve(target)
        observed.delete(target)
        target.classList.remove('fx-reveal-pending')
        if (policy.reducedMotion) return
        const delay = Number(target.dataset.fxDelay || 0)
        const keyframes = target.classList.contains('fx-depth')
          ? { opacity: [0, 1] }
          : { opacity: [0, 1], y: [12, 0] }
        const control = animate(target, keyframes, { duration: 0.36, delay, ease: [0.16, 1, 0.3, 1] })
        animations.set(target, control)
        control.then(() => animations.delete(target))
        target.classList.add('fx-revealed')
      })
    }, { threshold: 0.08 })
    function scan() {
      scanFrame = 0
      depths.forEach((binding, el) => {
        if (!root.contains(el)) { binding.dispose(); depths.delete(el) }
      })
      reveals.forEach(el => {
        if (!root.contains(el)) {
          observer.unobserve(el); observed.delete(el); reveals.delete(el)
          animations.get(el)?.stop(); animations.delete(el)
        }
      })
      root.querySelectorAll(depthSelector).forEach(el => {
        if (!depths.has(el)) depths.set(el, bindDepth(el, () => policy))
      })
      root.querySelectorAll(revealSelector).forEach((el, index) => {
        if (reveals.has(el)) return
        reveals.add(el)
        if (policy.reducedMotion) return
        el.dataset.fxDelay = String(Math.min(index % 5 * 0.04, 0.16))
        el.classList.add('fx-reveal-pending')
        observer.observe(el); observed.add(el)
      })
    }
    const unsubscribe = subscribeMotionPreferences(next => {
      policy = next
      root.classList.toggle('fx-reduced', next.reducedMotion)
      root.classList.toggle('fx-paused', !next.visible)
      if (next.reducedMotion || !next.visible || !next.finePointer) {
        depths.forEach(binding => binding.reset())
        cancelAnimationFrame(backgroundFrame); backgroundFrame = 0
        root.style.removeProperty('--fx-bg-x'); root.style.removeProperty('--fx-bg-y')
      }
      if (next.reducedMotion || !next.visible) {
        animations.forEach(control => control.complete())
        animations.clear()
      }
      if (next.reducedMotion) observed.forEach(el => {
        el.classList.remove('fx-reveal-pending'); observer.unobserve(el)
      })
      if (next.reducedMotion) observed.clear()
    })
    function backgroundMove(event) {
      if (!policy.visible || policy.reducedMotion || !policy.finePointer || event.pointerType === 'touch') return
      cancelAnimationFrame(backgroundFrame)
      backgroundFrame = requestAnimationFrame(() => {
        backgroundFrame = 0
        root.style.setProperty('--fx-bg-x', ((event.clientX / window.innerWidth - 0.5) * -16).toFixed(1) + 'px')
        root.style.setProperty('--fx-bg-y', ((event.clientY / window.innerHeight - 0.5) * -12).toFixed(1) + 'px')
      })
    }
    function resetPointers() { depths.forEach(binding => binding.reset()) }
    const mutation = new MutationObserver(() => {
      if (!scanFrame) scanFrame = requestAnimationFrame(scan)
    })
    scan()
    mutation.observe(root, { childList: true, subtree: true })
    root.addEventListener('pointermove', backgroundMove, { passive: true })
    root.addEventListener('scroll', resetPointers, { passive: true, capture: true })
    instances.set(root, () => {
      mutation.disconnect(); observer.disconnect(); unsubscribe()
      cancelAnimationFrame(scanFrame); cancelAnimationFrame(backgroundFrame)
      depths.forEach(binding => binding.dispose())
      animations.forEach(control => control.stop())
      root.removeEventListener('pointermove', backgroundMove)
      root.removeEventListener('scroll', resetPointers, true)
    })
  },
  unmounted(root) { instances.get(root)?.(); instances.delete(root) },
}
