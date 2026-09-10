<template>
  <div ref="container" class="liquid-ether" aria-hidden="true"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { createLiquidEtherFallback } from './liquidEtherFallback.js'

const props = defineProps({
  mouseForce: { type: Number, default: 20 },
  cursorSize: { type: Number, default: 100 },
  isViscous: { type: Boolean, default: false },
  viscous: { type: Number, default: 30 },
  iterationsViscous: { type: Number, default: 32 },
  iterationsPoisson: { type: Number, default: 32 },
  dt: { type: Number, default: 0.014 },
  BFECC: { type: Boolean, default: true },
  resolution: { type: Number, default: 0.5 },
  isBounce: { type: Boolean, default: false },
  colors: { type: Array, default: () => ['#5227FF', '#FF9FFC', '#B497CF'] },
  autoDemo: { type: Boolean, default: true },
  autoSpeed: { type: Number, default: 0.5 },
  autoIntensity: { type: Number, default: 2.2 },
  takeoverDuration: { type: Number, default: 0.25 },
  autoResumeDelay: { type: Number, default: 1000 },
  autoRampDuration: { type: Number, default: 0.6 },
  backgroundColor: { type: String, default: '#FFFFFF' },
  lightMode: { type: Boolean, default: false }
})

const container = ref(null)
let dispose
let preference
let generation = 0
let mouseDetected = false
let starting = false

function detectMouse() {
  if (mouseDetected) return
  mouseDetected = true
  if (!dispose && !starting) void syncEffect()
}

async function syncEffect() {
  const current = ++generation
  dispose?.()
  dispose = undefined
  starting = false
  if (!container.value) return
  if (!mouseDetected && !window.matchMedia('(any-pointer: fine)').matches) {
    container.value.dataset.renderer = 'waiting-for-mouse'
    return
  }
  starting = true
  try {
    // Keep Three.js out of the initial page bundle and touch-only devices.
    const { createLiquidEther } = await import('./liquidEtherEngine.js')
    if (current !== generation || !container.value) return
    dispose = createLiquidEther(container.value, {
      ...props,
      // Reduced-motion users still get an effect when they deliberately move
      // the pointer, but the autonomous driver remains disabled.
      autoDemo: props.autoDemo && !preference.matches
    })
    container.value.dataset.renderer = preference.matches ? 'webgl-manual' : 'webgl'
  } catch (error) {
    if (current !== generation || !container.value) return
    dispose = createLiquidEtherFallback(container.value)
    container.value.dataset.renderer = 'canvas2d'
    console.info('[LiquidEther] Using Canvas 2D fallback:', error.message)
  } finally {
    if (current === generation) starting = false
  }
}

onMounted(() => {
  preference = window.matchMedia('(prefers-reduced-motion: reduce)')
  window.addEventListener('mousemove', detectMouse, { passive: true })
  preference.addEventListener('change', syncEffect)
  void syncEffect()
})

watch(props, () => {
  if (container.value && preference) void syncEffect()
}, { deep: true })

onBeforeUnmount(() => {
  generation += 1
  preference?.removeEventListener('change', syncEffect)
  window.removeEventListener('mousemove', detectMouse)
  dispose?.()
})
</script>

<style scoped>
.liquid-ether {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow: hidden;
  pointer-events: none;
  opacity: .48;
  mix-blend-mode: screen;
}
</style>
