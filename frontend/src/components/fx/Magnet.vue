<template>
  <div ref="rootRef" class="magnet" @mousemove="onMove" @mouseleave="onLeave">
    <slot />
  </div>
</template>
<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { clamp, subscribeMotionPreferences } from '../../utils/motionPreferences.js'
const props = defineProps({ strength: { type: Number, default: 0.22 } })
const rootRef = ref(null)
let policy, unsubscribe, frame = 0
function onMove(event) {
  if (!policy?.finePointer || policy.reducedMotion || !policy.visible) return
  const el = rootRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const x = clamp((event.clientX - rect.left - rect.width / 2) * props.strength, -4, 4)
  const y = clamp((event.clientY - rect.top - rect.height / 2) * props.strength, -4, 4)
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(() => {
    frame = 0
    el.style.transform = 'translate3d(' + x + 'px,' + y + 'px,0)'
  })
}
function onLeave() {
  cancelAnimationFrame(frame)
  frame = 0
  if (rootRef.value) rootRef.value.style.transform = ''
}
onMounted(() => {
  unsubscribe = subscribeMotionPreferences(next => {
    policy = next
    if (next.reducedMotion || !next.visible || !next.finePointer) onLeave()
  })
})
onUnmounted(() => { onLeave(); unsubscribe?.() })
</script>
