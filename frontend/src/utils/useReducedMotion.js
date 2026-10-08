import { getCurrentInstance, onMounted, onUnmounted, ref } from 'vue'
import { subscribeMotionPreferences } from './motionPreferences.js'

export function useReducedMotion() {
  const reduced = ref(globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  let unsubscribe
  if (getCurrentInstance()) {
    onMounted(() => { unsubscribe = subscribeMotionPreferences(state => { reduced.value = state.reducedMotion }) })
    onUnmounted(() => unsubscribe?.())
  }
  return reduced
}

// Mount a costly chart once its panel is visible; preserve its identity on updates.
export function useMotionReveal(target) {
  const seen = ref(!getCurrentInstance())
  let observer
  if (getCurrentInstance()) {
    onMounted(() => {
      if (!target.value || typeof IntersectionObserver === 'undefined') { seen.value = true; return }
      observer = new IntersectionObserver(entries => {
        if (!entries.some(entry => entry.isIntersecting)) return
        seen.value = true
        observer.disconnect()
      }, { threshold: 0.08 })
      observer.observe(target.value)
    })
    onUnmounted(() => observer?.disconnect())
  }
  return seen
}
