<script setup>
import { onMounted, onUnmounted, ref, reactive, computed, watch, nextTick, useId } from 'vue'
import StudentAvatar from './StudentAvatar.vue'
import { subscribeMotionPreferences } from '../utils/motionPreferences.js'
import { createModelDrag } from '../utils/modelDrag.js'
const props = defineProps({ students: Array, raised: String, playbackStudent: String, reply: Object,
  level: Number, studentStates: Object, capturing: Boolean, presentation: { type:String, default:'row' },
  modelBase: { type: String, default: '/assets/characters/pixel/' } })
const emit = defineEmits(['select'])
const instructionId = useId(), closeView = ref(false), dragging = ref(false), turns = new Map()
const root = ref(null), host = ref(null), modelStates = reactive({ ming: 'loading', yu: 'loading', lin: 'loading' })
const rendererState = computed(() => {
  const states = Object.values(modelStates)
  return states.every(x => x === 'ready') ? 'ready' : states.every(x => x === 'fallback') ? 'fallback' : states.includes('ready') ? 'partial' : 'loading'
})
const state = () => ({ raised: props.raised, playbackStudent: props.playbackStudent, reply: props.reply, level: props.level, studentStates:props.studentStates })
const abort = new AbortController()
let handle, policy, inView = false, disposed = false, started = false, idle = 0, timer = 0, observer, resizeObserver, unsubscribe, pointerFrame = 0, pointerSample
function rotate(id, delta) { const value = Math.max(-.35, Math.min(.35, (turns.get(id) || 0) + delta)); turns.set(id, value); handle?.setRotation(id, value) }
const drag = createModelDrag(rotate)
function down(event) {
  const button = event.target.closest('.student-card'), id = button?.closest('[data-student]')?.dataset.student
  if (id && modelStates[id] === 'ready') drag.down(event, button, id)
}
function end(event) { drag.end(event); dragging.value = false }
function suppress(event) { if (event.target.closest('.student-card')) drag.suppress(event) }
function keys(event) {
  const id = event.target.closest('.student-card')?.closest('[data-student]')?.dataset.student
  if (!id || modelStates[id] !== 'ready') return
  if (['ArrowLeft','ArrowRight','Home'].includes(event.key)) {
    event.preventDefault(); event.stopPropagation()
    if (event.key === 'Home') { turns.set(id, 0); handle?.setRotation(id, 0) }
    else rotate(id, event.key === 'ArrowLeft' ? -.35 : .35)
  }
}
function reset() { turns.clear(); closeView.value = false; for (const id of Object.keys(modelStates)) handle?.setRotation(id, 0) }
function select(id) { if (props.raised === id) handle?.acknowledge(id); emit('select', id) }
function cancelDeferred() { window.cancelIdleCallback?.(idle); clearTimeout(timer); idle = timer = 0 }
async function start() {
  idle = timer = 0
  if (started || disposed || !inView || !policy?.visible) return
  started = true
  try {
    const { createStudentStage } = await import('./fx/studentStageEngine.js')
    if (disposed) return
    handle = await createStudentStage(host.value, { signal: abort.signal, policy, modelBase: props.modelBase,
      getSlots: () => [...root.value.querySelectorAll('[data-student-viewport]')].map(element => ({ id: element.dataset.studentViewport, element, clip: root.value.querySelector('.student-stage__seats') })),
      onModelState: (id, value) => { if (!disposed) modelStates[id] = value } })
    if (disposed) { handle.dispose(); return }
    handle.setState(state()); handle.setPolicy(policy); handle.setVisible(inView); handle.setCapture(props.capturing)
    handle.setView(closeView.value)
  } catch (error) { if (!disposed && error.name !== 'AbortError') for (const id of Object.keys(modelStates)) modelStates[id] = 'fallback' }
}
function sync() {
  handle?.setPolicy(policy); handle?.setVisible(inView)
  if (!policy?.visible || !inView) { cancelDeferred(); return }
  if (!started && !idle && !timer) {
    if (window.requestIdleCallback) idle = window.requestIdleCallback(start, { timeout: 1200 })
    else timer = window.setTimeout(start, 200)
  }
}
function pointer(event) {
  if (drag.move(event)) { dragging.value = true; return }
  if (!policy?.finePointer || policy.reducedMotion || event.pointerType === 'touch') return
  const seat = event.target.closest('[data-student]')
  if (!seat) return
  pointerSample = { seat, x: event.clientX }
  if (!pointerFrame) pointerFrame = requestAnimationFrame(() => {
    pointerFrame = 0
    const sample = pointerSample
    if (!sample?.seat.isConnected) return
    const rect = sample.seat.getBoundingClientRect()
    handle?.setPointer(sample.seat.dataset.student, Math.max(-1, Math.min(1, (sample.x - rect.left) / rect.width * 2 - 1)))
  })
}
function leave() { cancelAnimationFrame(pointerFrame); pointerFrame = 0; pointerSample = null; for (const id of Object.keys(modelStates)) handle?.setPointer(id, 0) }
watch(() => [props.raised, props.playbackStudent, props.reply?.phase, props.reply?.studentId, props.level, props.studentStates], () => handle?.setState(state()))
watch(() => props.capturing, next => handle?.setCapture(next))
watch(closeView, next => handle?.setView(next))
watch(() => [props.students, props.presentation, props.reply?.phase, props.reply?.text], async () => { await nextTick(); handle?.refreshSlots() })
defineExpose({ recordingSnapshot: () => handle?.snapshot() || null })
onMounted(() => {
  unsubscribe = subscribeMotionPreferences(next => { policy = next; sync() })
  observer = new IntersectionObserver(entries => { inView = entries[0].isIntersecting; sync() })
  observer.observe(root.value)
  resizeObserver = new ResizeObserver(() => handle?.refreshSlots())
  resizeObserver.observe(root.value)
  for (const viewport of root.value.querySelectorAll('[data-student-viewport]')) resizeObserver.observe(viewport)
})
onUnmounted(() => {
  disposed = true; drag.cancel(); leave(); cancelDeferred(); abort.abort(); observer?.disconnect(); resizeObserver?.disconnect(); unsubscribe?.(); handle?.dispose()
})
</script>
<template>
  <div ref="root" class="student-stage" :class="{'is-dragging':dragging, 'student-stage--column': presentation === 'column'}" :data-renderer="rendererState" @scroll.capture="handle?.refreshSlots()"
    @pointerdown="down" @pointermove.passive="pointer" @pointerleave="leave" @pointerup="end" @pointercancel="end" @lostpointercapture="end" @click.capture="suppress" @keydown="keys">
    <div class="student-stage__toolbar">
      <span class="student-stage__label"><i aria-hidden="true" />课堂学生 <small class="sr-only" v-if="rendererState === 'ready'">拖动转头 · 点击点名</small></span>
      <div class="student-stage__views" aria-label="学生视角">
        <button type="button" :disabled="rendererState === 'loading' || rendererState === 'fallback'" :aria-pressed="!closeView" @click="closeView=false">全身</button><button type="button" :disabled="rendererState === 'loading' || rendererState === 'fallback'" :aria-pressed="closeView" @click="closeView=true">近景</button><button type="button" :disabled="rendererState === 'loading' || rendererState === 'fallback'" aria-label="复位全部学生视角" @click="reset">↺</button>
      </div>
    </div>
    <div ref="host" class="student-stage__canvas" aria-hidden="true" />
    <div class="student-stage__seats">
    <StudentAvatar v-for="student in students" :key="student.id" compact :student="student"
      :instructions-id="instructionId"
      :model-state="modelStates[student.id] || 'fallback'" :raised="raised === student.id"
      :speaking="playbackStudent === student.id" :reply="reply?.studentId === student.id ? reply : null"
      :interaction-state="studentStates?.[student.id]?.interaction_state" :level="level" @select="select" />
    </div>
    <span :id="instructionId" class="sr-only">拖动学生可以小幅转头，左右方向键调整，Home 复位。举手后按回车点名；未举手时点击或按回车邀请提问或反驳。</span>
    <a class="sr-only" href="/assets/characters/pixel/credits.json" target="_blank" rel="noopener">LINK 像素课堂角色</a>
  </div>
</template>
<style scoped>
.student-stage { position:relative; display:grid; grid-template-rows:26px minmax(0,1fr); gap:3px; height:100%; min-height:0; }
.student-stage__seats { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; min-height:0; }
.student-stage--column .student-stage__seats { grid-template-columns:1fr; grid-template-rows:repeat(3,minmax(0,1fr)); overflow:hidden; overscroll-behavior:contain; scrollbar-width:thin; gap:0; }
.student-stage--column :deep(.student-interaction) { border:0; border-bottom:1px solid var(--line); border-radius:0; background:transparent; box-shadow:none; padding:4px 0; display:block; }
.student-stage--column :deep(.student-card) { width:100%; display:grid; grid-template-columns:minmax(130px,1fr) 70px; grid-template-rows:1fr 1fr; height:100%; min-height:0; gap:0 2px; align-content:center; }
.student-stage--column :deep(.student-sprite-wrap) { grid-row:1/3; grid-column:1; width:100%; height:100%; max-width:none; }
.student-stage--column :deep(.student-name) { grid-row:1; grid-column:2; align-self:end; justify-content:center; }
.student-stage--column :deep(.student-status) { grid-row:2; grid-column:2; align-self:start; padding-top:4px; font-size:10px; }
.student-stage--column :deep(.student-response-slot) { display:none; }
.student-stage--column :deep(.student-interaction::before) { display:none; }
.student-stage__toolbar { position:relative; z-index:3; display:flex; align-items:center; justify-content:space-between; gap:8px; }
.student-stage__label { display:flex; align-items:center; gap:6px; color:#cfbfdb; font-size:10px; }
.student-stage__label i { width:5px; height:5px; border-radius:50%; background:#b689db; box-shadow:0 0 10px #b45cff77; }
.student-stage__label small { font-size:10px; color:#95899e; margin-left:8px; }
.student-stage__views { display:flex; gap:3px; }
.student-stage__views button { min-width:28px; height:24px; padding:0 8px; background:transparent; border:1px solid transparent; border-radius:7px; color:#aa99b7; font-size:10px; }
.student-stage__views button[aria-pressed=true] { background:#b45cff19; border-color:#b45cff36; color:#ead4f7; }
.student-stage__views button:hover { color:#ffd2b0; border-color:#ff9e6944; }
.student-stage__views button:disabled { opacity:.45; cursor:default; }
.student-stage :deep(.student-card) { touch-action:pan-y; cursor:grab; user-select:none; }
.student-stage.is-dragging :deep(.student-card) { cursor:grabbing; }
.student-stage :deep(.student-interaction::before) { content:''; position:absolute; inset:45% 8% 5%; border-radius:50%; pointer-events:none; background:radial-gradient(ellipse,color-mix(in srgb,var(--student-accent) 12%,transparent),transparent 68%); }
.student-stage :deep(.student-interaction) { transition:border-color .2s,box-shadow .2s; }
.student-stage :deep(.student-interaction:hover) { border-color:color-mix(in srgb,var(--student-accent) 55%,transparent); box-shadow:inset 0 1px color-mix(in srgb,var(--student-accent) 18%,transparent); }
.student-stage__canvas { position:absolute; inset:0; z-index:1; pointer-events:none; }
.student-stage__canvas :deep(canvas) { display:block; width:100%; height:100%; image-rendering:pixelated; }
.student-stage :deep(.student-card), .student-stage :deep(.student-response-slot) { z-index:2; }
.student-stage :deep(.student-card:hover) { background:transparent; }
.student-stage :deep(.student-interaction) { background:linear-gradient(145deg,#251a3240,#121016b8); box-shadow:inset 0 1px #ffffff08; }
.student-stage :deep(.student-interaction.speaking) { box-shadow:inset 0 0 24px color-mix(in srgb,var(--student-accent) 12%,transparent); }
@media(max-width:700px) {
 .student-stage--column .student-stage__seats { grid-template-columns:repeat(3,minmax(0,1fr)); grid-template-rows:minmax(0,1fr); }
 .student-stage--column :deep(.student-interaction) { padding:0; }
 .student-stage--column :deep(.student-card) { display:flex; flex-direction:column; justify-content:center; }
 .student-stage--column :deep(.student-sprite-wrap) { flex:1; min-height:0; width:100%; }
 .student-stage--column :deep(.student-name),.student-stage--column :deep(.student-status) { flex:none; align-self:center; padding:0; }
 .student-stage--column :deep(.student-status) { font-size:9px; }
 .student-stage--column :deep(.student-card), .student-stage--column :deep(.student-sprite-wrap) { height:100%; }
 .student-stage__seats { gap:6px; } .student-stage__label small { display:none; } .student-stage__views button { min-width:32px; } }
</style>
