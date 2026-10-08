<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { subscribeMotionPreferences } from '../../utils/motionPreferences.js'
import { createModelDrag } from '../../utils/modelDrag.js'
const props = defineProps({ kind: {type:String,default:'book'}, label:String, active:Boolean, quiet:Boolean,
  interactive: {type:Boolean,default:true}, followParent:Boolean, reaction:Number })
const emit = defineEmits(['activate', 'reset'])
const root = ref(null), host = ref(null), status = ref('loading'), dragging = ref(false)
let handle, observer, unsubscribe, policy, visible = false, disposed = false, started = false, idle = 0, timer = 0, surface, angle = 0
const drag = createModelDrag((_, delta) => { angle += delta; handle?.setRotation(angle) })
function rotate(delta) { angle += delta; handle?.setRotation(angle) }
function reset() { angle = 0; handle?.setRotation(0); handle?.setPointer(0, 0); emit('reset') }
defineExpose({ rotate, reset, status })
async function start() {
  idle = timer = 0
  if (started || disposed || !visible || !policy?.visible) return
  started = true
  try {
    const { createInteractiveModel } = await import('./interactiveModelEngine.js')
    if (disposed) return
    handle = createInteractiveModel(host.value, { kind:props.kind, policy, onError:() => { status.value = 'fallback' } })
    handle.setState(props); handle.setPolicy(policy); handle.setVisible(visible); status.value = 'ready'
  } catch { if (!disposed) status.value = 'fallback' }
}
function sync() {
  handle?.setPolicy(policy); handle?.setVisible(visible)
  if (!visible || !policy?.visible) { cancelDeferred(); return }
  if (!started && !idle && !timer) {
    if (window.requestIdleCallback) idle = window.requestIdleCallback(start, {timeout:1200})
    else timer = window.setTimeout(start, 180)
  }
}
function cancelDeferred() { window.cancelIdleCallback?.(idle); clearTimeout(timer); idle = timer = 0 }
function move(event) {
  if (props.interactive && drag.move(event)) { dragging.value = true; return }
  if (!policy?.finePointer || policy.reducedMotion || event.pointerType === 'touch') return
  const r = surface.getBoundingClientRect()
  handle?.setPointer((event.clientX - r.left) / r.width * 2 - 1, 1 - (event.clientY - r.top) / r.height * 2)
}
function down(event) { if (props.interactive && status.value === 'ready') drag.down(event, root.value) }
function end(event) { drag.end(event); dragging.value = false }
function leave() { handle?.setPointer(0, 0) }
function activate(event) { if (props.interactive && !drag.suppress(event)) { handle?.react(); emit('activate') } }
watch(() => [props.active, props.quiet], () => handle?.setState(props))
watch(() => props.reaction, () => handle?.react())
onMounted(() => {
  surface = props.followParent ? root.value.closest('[data-model-surface]') || root.value : root.value
  surface.addEventListener('pointermove', move, {passive:true}); surface.addEventListener('pointerleave', leave)
  unsubscribe = subscribeMotionPreferences(next => { policy = next; sync() })
  observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; sync() }); observer.observe(root.value)
})
onUnmounted(() => { disposed = true; drag.cancel(); cancelDeferred(); observer?.disconnect(); unsubscribe?.(); surface?.removeEventListener('pointermove', move); surface?.removeEventListener('pointerleave', leave); handle?.dispose() })
</script>
<template>
  <span ref="root" class="interactive-model" :class="{ 'is-dragging':dragging, passive:!interactive }" :data-renderer="status" :data-kind="kind"
    :role="interactive ? 'button' : undefined" :tabindex="interactive ? 0 : undefined" :aria-label="interactive ? label + (status === 'ready' ? '，拖动或使用左右方向键旋转，回车切换，双击或 Home 复位' : '，回车展开静态预览') : undefined"
    :aria-pressed="interactive ? active : undefined" :aria-hidden="!interactive || undefined"
    @pointerdown="down" @pointerup="end" @pointercancel="end" @lostpointercapture="end" @click="activate" @dblclick.prevent="reset"
    @keydown.left.prevent="rotate(-.35)" @keydown.right.prevent="rotate(.35)" @keydown.home.prevent="reset" @keydown.enter.prevent="activate" @keydown.space.prevent="activate">
    <span class="interactive-model__fallback" :class="'fallback-' + kind" aria-hidden="true"><slot><span /><span /><span /></slot></span>
    <span ref="host" class="interactive-model__canvas" aria-hidden="true" />
  </span>
</template>
<style scoped>
.interactive-model { position:relative; display:block; width:100%; height:100%; min-height:0; outline-offset:-4px; cursor:grab; touch-action:pan-y; user-select:none; }
.interactive-model.is-dragging { cursor:grabbing; }
.interactive-model.passive { pointer-events:none; cursor:inherit; }
.interactive-model__canvas,.interactive-model__fallback { position:absolute; inset:0; display:block; }
.interactive-model__canvas :deep(canvas) { display:block; width:100%; height:100%; }
.interactive-model__canvas { opacity:0; transition:opacity .24s; }
[data-renderer=ready] .interactive-model__canvas { opacity:1; }
[data-renderer=ready] .interactive-model__fallback { opacity:0; }
.interactive-model__fallback { transition:opacity .24s; display:grid; place-items:center; pointer-events:none; }
.interactive-model__fallback > span { position:absolute; width:32%; height:52%; border:1px solid #d4a4ff80; border-radius:10px; transform:perspective(400px) rotateY(-25deg) rotateZ(-12deg); background:linear-gradient(145deg,#9258ac,#1e142a); box-shadow:8px 12px 30px #0005; }
.interactive-model__fallback > span:nth-child(2) { translate:12px -5px; opacity:.6; }
.interactive-model__fallback > span:nth-child(3) { translate:-12px 5px; opacity:.4; }
.interactive-model[aria-pressed=true] .interactive-model__fallback > span:nth-child(2) { translate:25px -7px; }
.interactive-model[aria-pressed=true] .interactive-model__fallback > span:nth-child(3) { translate:-25px 7px; }
.fallback-orbit > span,.fallback-prism > span { border-radius:50%; aspect-ratio:1; height:auto; background:transparent; }
@media(prefers-reduced-motion:reduce) { .interactive-model__canvas,.interactive-model__fallback { transition:none; } }
</style>
