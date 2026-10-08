// Vite-only fixture. It is not an entry in the production build.
import { createApp } from 'vue'
import Fixture from './EffectsFixture.vue'
import '../src/styles.css'
import '../src/ambient-effects.css'
import '../src/classroom.css'

const originalMedia = window.matchMedia.bind(window)
const reduce = new EventTarget()
reduce.matches = false
let hidden = false
let unavailable = false
const originalContext = HTMLCanvasElement.prototype.getContext
HTMLCanvasElement.prototype.getContext = function(type, ...options) {
  if (unavailable && (type === 'webgl' || type === 'webgl2' || type === 'experimental-webgl')) return null
  return originalContext.call(this, type, ...options)
}
window.matchMedia = query => query === '(prefers-reduced-motion: reduce)' ? reduce : originalMedia(query)
Object.defineProperty(document, 'visibilityState', { configurable:true, get:() => hidden ? 'hidden' : 'visible' })
createApp(Fixture, {
  setReduced(value) { reduce.matches = value; reduce.dispatchEvent(new Event('change')) },
  setHidden(value) { hidden = value; document.dispatchEvent(new Event('visibilitychange')) },
  setUnavailable(value) { unavailable = value },
}).mount('#app')
