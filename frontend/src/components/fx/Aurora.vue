<template>
  <canvas ref="canvasRef" class="aurora" aria-hidden="true"></canvas>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { subscribeMotionPreferences } from '../../utils/motionPreferences.js'

const canvasRef = ref(null)
let raf = 0
let policy, unsubscribe, lastPaint = 0

function paint(ctx, width, height, t) {
  ctx.clearRect(0, 0, width, height)
  const blobs = [
    { x: 0.72 + Math.sin(t / 4200) * 0.08, y: 0.08, r: 0.42, color: 'rgba(180,92,255,0.16)' },
    { x: 0.18 + Math.cos(t / 5100) * 0.06, y: 0.78, r: 0.34, color: 'rgba(255,122,24,0.10)' },
    { x: 0.88 + Math.sin(t / 6300) * 0.04, y: 0.62, r: 0.28, color: 'rgba(180,92,255,0.08)' },
  ]
  blobs.forEach((blob) => {
    const x = blob.x * width
    const y = blob.y * height
    const radius = blob.r * Math.max(width, height)
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius)
    gradient.addColorStop(0, blob.color)
    gradient.addColorStop(1, 'rgba(5,4,7,0)')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, width, height)
  })
}

function loop(now) {
  raf = 0
  if (!policy?.visible || policy.reducedMotion) return
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (ctx && now - lastPaint >= 1000 / 30) {
    paint(ctx, canvas.width, canvas.height, now)
    lastPaint = now
  }
  raf = requestAnimationFrame(loop)
}

function resize() {
  const canvas = canvasRef.value
  if (!canvas) return
  const width = window.innerWidth
  const height = window.innerHeight
  const scale = Math.min(1, 960 / width)
  canvas.width = Math.floor(width * scale)
  canvas.height = Math.floor(height * scale)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  const ctx = canvas.getContext('2d')
  if (ctx && policy?.reducedMotion) paint(ctx, canvas.width, canvas.height, 0)
}

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
  unsubscribe = subscribeMotionPreferences(next => {
    policy = next
    cancelAnimationFrame(raf)
    raf = 0
    const canvas = canvasRef.value
    const ctx = canvas?.getContext('2d')
    if (!next.visible) return
    if (next.reducedMotion) {
      if (ctx && canvas) paint(ctx, canvas.width, canvas.height, 0)
    } else raf = requestAnimationFrame(loop)
  })
})

onUnmounted(() => {
  unsubscribe?.()
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
})
</script>
