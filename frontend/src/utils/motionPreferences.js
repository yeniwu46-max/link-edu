// One browser preference subscription shared by decorative effects.
export function createMotionPreferences(environment = globalThis) {
  const listeners = new Set()
  let cleanups = []
  let state
  const read = () => ({
    reducedMotion: environment.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    finePointer: environment.matchMedia?.('(hover: hover) and (pointer: fine)').matches ?? false,
    visible: environment.document?.visibilityState !== 'hidden',
  })
  const notify = () => {
    state = read()
    listeners.forEach(listener => listener(state))
  }
  return {
    subscribe(listener) {
      if (!listeners.size) {
        for (const query of ['(prefers-reduced-motion: reduce)', '(hover: hover) and (pointer: fine)']) {
          const media = environment.matchMedia?.(query)
          media?.addEventListener('change', notify)
          cleanups.push(() => media?.removeEventListener('change', notify))
        }
        environment.document?.addEventListener('visibilitychange', notify)
        cleanups.push(() => environment.document?.removeEventListener('visibilitychange', notify))
        state = read()
      }
      listeners.add(listener)
      listener(state)
      return () => {
        listeners.delete(listener)
        if (!listeners.size) {
          cleanups.forEach(cleanup => cleanup())
          cleanups = []
        }
      }
    },
  }
}

const preferences = createMotionPreferences()
export const subscribeMotionPreferences = listener => preferences.subscribe(listener)

export function motionQuality(finePointer, slow = false) {
  return { fps: finePointer && !slow ? 60 : 30, pixelRatio: finePointer && !slow ? 1.5 : 1 }
}

export const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

// Pointer normalization adapted from Vue Bits TiltedCard (David Haz).
// See deploy/third-party/licenses/vue-bits/LICENSE.md.
export function tiltFromPoint(rect, clientX, clientY, amplitude = 4) {
  if (!rect.width || !rect.height) return { x: 0, y: 0, lightX: 50, lightY: 50 }
  const x = clamp((clientX - rect.left) / rect.width, 0, 1)
  const y = clamp((clientY - rect.top) / rect.height, 0, 1)
  return { x: (0.5 - y) * 2 * amplitude, y: (x - 0.5) * 2 * amplitude, lightX: x * 100, lightY: y * 100 }
}
