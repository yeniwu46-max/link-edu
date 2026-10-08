<template>
  <div ref="root" class="hero-avatar" :class="{ 'is-ready': state === 'ready' }" :data-renderer="state">
    <img class="hero-avatar__poster" :src="posterSrc" alt="" aria-hidden="true" />
    <AmbientVideo v-if="state === 'fallback'" class="hero-avatar__fallback" :source="fallbackSrc" :poster="posterSrc" aria-hidden="true" />
    <div ref="canvasHost" class="hero-avatar__canvas" aria-hidden="true"></div>
    <div class="hero-avatar__veil" aria-hidden="true"></div>
    <a v-if="state === 'ready'" class="hero-avatar__credit" href="/assets/models/credits.json" target="_blank" rel="noopener noreferrer" aria-label="人物模型来源：Cesium，CC BY 4.0">模型：Cesium</a>
  </div>
</template>
<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import AmbientVideo from './AmbientVideo.vue'
import { subscribeMotionPreferences } from '../../utils/motionPreferences.js'

const props = defineProps({
  modelSrc: { type: String, default: '/assets/models/CesiumMan.glb' },
  posterSrc: { type: String, default: '/assets/hero-clean.png' },
  fallbackSrc: { type: String, default: '/assets/hero-hair.mp4' },
})
const root = ref(null), canvasHost = ref(null), state = ref('loading')
const abort = new AbortController()
let handle, policy, observer, unsubscribe, inView = false, disposed = false, started = false, idle = 0, timer = 0, surface
function cancelDeferred() {
  if (idle) window.cancelIdleCallback?.(idle)
  clearTimeout(timer)
  idle = timer = 0
}
async function start() {
  idle = timer = 0
  if (started || disposed || !inView || !policy?.visible) return
  started = true
  try {
    const { createHeroAvatar } = await import('./heroAvatarEngine.js')
    if (disposed) return
    handle = await createHeroAvatar(canvasHost.value, {
      modelSrc: props.modelSrc, signal: abort.signal, policy,
      onError: () => { if (!disposed) state.value = 'fallback' },
    })
    if (disposed) { handle.dispose(); return }
    handle.setPolicy(policy)
    handle.setVisible(inView)
    state.value = 'ready'
  } catch (error) {
    if (!disposed && error.name !== 'AbortError') state.value = 'fallback'
  }
}
function sync() {
  handle?.setPolicy(policy)
  handle?.setVisible(inView)
  if (!inView || !policy?.visible) { cancelDeferred(); return }
  if (started || idle || timer) return
  if (window.requestIdleCallback) idle = window.requestIdleCallback(start, { timeout: 1500 })
  else timer = window.setTimeout(start, 300)
}
function move(event) {
  if (!handle || !policy.finePointer || policy.reducedMotion || event.pointerType === 'touch') return
  const rect = surface.getBoundingClientRect()
  handle.setPointer((event.clientX - rect.left) / rect.width * 2 - 1, .5 - (event.clientY - rect.top) / rect.height)
}
function leave() { handle?.setPointer(0, 0) }
onMounted(() => {
  surface = root.value.closest('.continue') || root.value
  surface.addEventListener('pointermove', move, { passive: true })
  surface.addEventListener('pointerleave', leave)
  unsubscribe = subscribeMotionPreferences(next => { policy = next; sync() })
  observer = new IntersectionObserver(entries => { inView = entries[0].isIntersecting; sync() })
  observer.observe(root.value)
})
onUnmounted(() => {
  disposed = true
  cancelDeferred()
  abort.abort()
  observer?.disconnect()
  unsubscribe?.()
  surface?.removeEventListener('pointermove', move)
  surface?.removeEventListener('pointerleave', leave)
  handle?.dispose()
})
</script>
<style scoped>
.hero-avatar { position:absolute!important; inset:0; z-index:0!important; border-radius:inherit; overflow:hidden; pointer-events:none; background:radial-gradient(ellipse at 54% 28%,#59316a55,transparent 70%),#09060e; }
.hero-avatar__poster,.hero-avatar__fallback,.hero-avatar__canvas,.hero-avatar__veil { position:absolute; inset:0; width:100%; height:100%; }
.hero-avatar__poster,.hero-avatar__fallback { object-fit:cover; object-position:58% 28%; }
.hero-avatar__poster { opacity:1; transition:opacity .5s ease; }
.is-ready .hero-avatar__poster { opacity:0; }
.hero-avatar__canvas { opacity:0; transition:opacity .65s ease; }
.is-ready .hero-avatar__canvas { opacity:1; }
.hero-avatar__canvas :deep(canvas) { display:block; width:100%; height:100%; }
.hero-avatar__veil { background:linear-gradient(180deg,#08050d00 25%,#08050d33 50%,#08050de8 91%); }
.hero-avatar__credit { position:absolute; top:24px; right:20px; color:#c9aadc; font-size:10px; opacity:.65; pointer-events:auto; text-decoration:none; }
.hero-avatar__credit:hover,.hero-avatar__credit:focus-visible { opacity:1; }
@media(prefers-reduced-motion:reduce) { .hero-avatar__poster,.hero-avatar__canvas { transition:none; } }
</style>
