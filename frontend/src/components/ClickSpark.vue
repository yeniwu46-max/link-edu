<template>
  <div class="click-spark" @click="handleClick">
    <canvas ref="canvasRef" class="click-spark__canvas" aria-hidden="true"></canvas>
    <slot />
  </div>
</template>

<script setup>
// Vue Bits ClickSpark adaptation: event-driven rendering, capped particles and
// shared motion/visibility preferences. See deploy/third-party/licenses/vue-bits.
import { onMounted, onUnmounted, ref } from 'vue'
import { subscribeMotionPreferences } from '../utils/motionPreferences.js'

const props = defineProps({
  sparkColor: { type: String, default: '#ffffff' },
  sparkSize: { type: Number, default: 10 },
  sparkRadius: { type: Number, default: 15 },
  sparkCount: { type: Number, default: 8 },
  duration: { type: Number, default: 400 },
  easing: { type: String, default: 'ease-out' },
  extraScale: { type: Number, default: 1 },
})
const canvasRef = ref(null)
let particles = [], frame = 0, unsubscribe, policy, context

function clear() {
  cancelAnimationFrame(frame)
  frame = 0
  particles = []
  if (context) context.clearRect(0, 0, window.innerWidth, window.innerHeight)
}
function resize() {
  clear()
  const canvas = canvasRef.value
  if (!canvas) return
  const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
  canvas.width = Math.round(window.innerWidth * ratio)
  canvas.height = Math.round(window.innerHeight * ratio)
  context = canvas.getContext('2d')
  context?.setTransform(ratio, 0, 0, ratio, 0, 0)
}
function ease(t) {
  if (props.easing === 'linear') return t
  if (props.easing === 'ease-in') return t * t
  if (props.easing === 'ease-in-out') return t < .5 ? 2 * t * t : -1 + (4 - 2 * t) * t
  return t * (2 - t)
}
function draw(now) {
  frame = 0
  if (!context || !policy?.visible || policy.reducedMotion) return clear()
  context.clearRect(0, 0, window.innerWidth, window.innerHeight)
  const duration = Math.max(1, props.duration)
  particles = particles.filter(particle => now - particle.start < duration)
  for (const particle of particles) {
    const progress = ease((now - particle.start) / duration)
    const distance = progress * props.sparkRadius * props.extraScale
    const length = props.sparkSize * (1 - progress)
    const x = particle.x + distance * Math.cos(particle.angle)
    const y = particle.y + distance * Math.sin(particle.angle)
    context.strokeStyle = props.sparkColor
    context.lineWidth = 1.5
    context.beginPath()
    context.moveTo(x, y)
    context.lineTo(x + length * Math.cos(particle.angle), y + length * Math.sin(particle.angle))
    context.stroke()
  }
  if (particles.length) frame = requestAnimationFrame(draw)
}
function handleClick(event) {
  if (!policy?.visible || policy.reducedMotion || !context) return
  const action = event.target.closest?.('button,a,[role="button"]')
  if (!action || action.disabled || action.getAttribute('aria-disabled') === 'true') return
  const rect = action.getBoundingClientRect()
  const x = event.detail === 0 ? rect.left + rect.width / 2 : event.clientX
  const y = event.detail === 0 ? rect.top + rect.height / 2 : event.clientY
  const start = performance.now()
  const count = Math.min(12, Math.max(0, Math.round(props.sparkCount)))
  for (let i = 0; i < count; i++) particles.push({ x, y, start, angle: Math.PI * 2 * i / count })
  particles = particles.slice(-96)
  if (!frame && particles.length) frame = requestAnimationFrame(draw)
}
onMounted(() => {
  resize()
  unsubscribe = subscribeMotionPreferences(next => {
    policy = next
    if (next.reducedMotion || !next.visible) clear()
  })
  window.addEventListener('resize', resize, { passive: true })
})
onUnmounted(() => {
  clear()
  unsubscribe?.()
  window.removeEventListener('resize', resize)
})
</script>

<style scoped>
.click-spark { position:relative; width:100%; min-height:100%; }
.click-spark__canvas { position:fixed; inset:0; width:100%; height:100%; pointer-events:none; z-index:9999; }
</style>
