<template>
  <video ref="video" :src="loadedSource || undefined" :poster="poster" muted loop playsinline preload="none" @error="retryOriginal" />
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { subscribeMotionPreferences } from '../../utils/motionPreferences.js'

const props = defineProps({
  source: { type: String, required: true },
  poster: { type: String, required: true },
  fallbackSource: { type: String, default: '' },
})
const video = ref(null)
const loadedSource = ref('')
let policy, observer, unsubscribe, idle = 0, timer = 0, inView = false, disposed = false

function cancelLoad() {
  if (idle) window.cancelIdleCallback?.(idle)
  clearTimeout(timer)
  idle = timer = 0
}
function play() {
  if (disposed || !policy?.visible || policy.reducedMotion || !inView) return
  const element = video.value
  if (!element) return
  element.muted = true
  element.play()?.catch(() => {})
}
function sync() {
  if (!video.value) return
  if (!inView || !policy?.visible || policy.reducedMotion) {
    cancelLoad()
    video.value.pause()
    return
  }
  if (loadedSource.value) { play(); return }
  if (idle || timer) return
  const load = async () => {
    idle = timer = 0
    if (disposed || !inView || !policy?.visible || policy.reducedMotion) return
    loadedSource.value = props.source
    await nextTick()
    play()
  }
  if (window.requestIdleCallback) idle = window.requestIdleCallback(load, { timeout: 1500 })
  else timer = window.setTimeout(load, 300)
}
async function retryOriginal() {
  if (!props.fallbackSource || loadedSource.value === props.fallbackSource || disposed) return
  loadedSource.value = props.fallbackSource
  await nextTick()
  play()
}
onMounted(() => {
  unsubscribe = subscribeMotionPreferences(next => { policy = next; sync() })
  observer = new IntersectionObserver(entries => { inView = entries[0].isIntersecting; sync() })
  observer.observe(video.value)
})
onUnmounted(() => {
  disposed = true
  cancelLoad()
  unsubscribe?.()
  observer?.disconnect()
  video.value?.pause()
})
</script>
