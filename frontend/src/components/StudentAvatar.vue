<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue';
import { createBubbleRetention } from '../services/classroomBubble.js';
import { studentPresentation } from '../services/classroomStudent.js';
const props = defineProps({
  student: Object, raised: Boolean, speaking: Boolean, level: Number,
  understanding: String, reply: Object, compact: Boolean, interactionState: String, modelState: String, instructionsId: String,
});
defineEmits(['select']);
const bubble = ref(null), visibleReply = ref(null);
const retention = createBubbleRetention(value => { visibleReply.value = value; });
watch(() => props.reply, value => retention.update(value), { immediate: true });
onUnmounted(retention.clear);
const presentation = computed(() => studentPresentation(props.student.id, props));
const colors = { ming: '#ba98eb', yu: '#ffa26d', lin: '#92b9e7' };
watch(() => visibleReply.value?.text, async () => {
  await nextTick();
  if (bubble.value) bubble.value.scrollTop = bubble.value.scrollHeight;
});
</script>

<template>
  <div class="student-interaction" :class="{ compact, 'has-reply': visibleReply, speaking, 'is-3d': modelState === 'ready' }"
    :data-student="student.id" :data-renderer="modelState"
    :style="{ '--student-accent': colors[student.id] || colors.lin }">
    <button type="button" class="student-card"
      :class="{ speaking, raised: presentation.pose === 'raised', thinking: reply?.phase === 'thinking' }"
      :aria-label="student.name + (raised ? '举手了，点击点名' : '，可用语音点名')"
      :aria-describedby="modelState === 'ready' ? instructionsId : undefined"
      @click="$emit('select', student.id)">
      <span class="student-sprite-wrap" :data-student-viewport="modelState ? student.id : undefined">
        <!-- Preload both poses so the first reply cannot flash a missing image. -->
        <img v-for="pose in ['listening', 'raised']" :key="pose"
          class="student-sprite" :class="{ visible: presentation.pose === pose }"
          :src="studentPresentation(student.id, { raised: pose === 'raised' }).src"
          alt="" aria-hidden="true" width="1254" height="1254" draggable="false" />
        <span v-if="presentation.pose === 'raised'" class="student-attention" aria-hidden="true">!</span>
      </span>
      <span class="student-name"><strong>{{ student.name }}</strong>
        <span v-if="speaking" class="student-equalizer" aria-hidden="true"><i /><i /><i /><i /></span>
      </span>
      <span class="student-status">{{ presentation.label }}</span>
    </button>
    <div class="student-response-slot">
      <Transition name="bubble-pop">
        <div v-if="visibleReply" ref="bubble" class="student-bubble" :class="visibleReply.phase">
          <span v-if="visibleReply.phase === 'thinking'" class="bubble-thinking">思考中<span class="thinking-dots" aria-hidden="true">…</span></span>
          <span v-else-if="visibleReply.phase === 'failed'">{{ visibleReply.error }}</span>
          <p v-else>{{ visibleReply.text || '正在准备回答…' }}<span v-if="visibleReply.phase === 'generating'" class="stream-caret" aria-hidden="true" /></p>
        </div>
      </Transition>
      <div v-if="!visibleReply" class="student-idle-mark" aria-hidden="true"><span /><span /><span /></div>
    </div>
    <span class="sr-only" role="status">{{ reply?.phase === 'queued' ? student.name + '：' + reply.text : reply?.phase === 'thinking' ? student.name + '正在思考' : '' }}</span>
  </div>
</template>

<style scoped>
.student-interaction { container:student-seat / inline-size; position:relative; min-width:0; min-height:0; display:flex; align-items:center; gap:8px; padding:8px; border:1px solid var(--line); border-radius:12px; background:var(--class-surface); }
.student-interaction.speaking { border-color:var(--student-accent); }
.student-interaction:not(.has-reply) .student-card { flex:1; }
.student-interaction:not(.has-reply) .student-response-slot { display:none; }
.student-card { position:relative; flex:0 0 120px; display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:0; height:100%; padding:0; background:none; border:0; color:var(--class-ink); cursor:pointer; border-radius:8px; }
.student-card:hover { background:var(--class-hover); }
.student-sprite-wrap { position:relative; display:block; width:148px; height:128px; flex-shrink:1; min-height:0; }
.student-sprite { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; opacity:0; transform-origin:50% 94%; pointer-events:none; }
.student-sprite.visible { opacity:1; animation:student-breathe 4s ease-in-out infinite; }
.is-3d .student-sprite { opacity:0 !important; animation:none !important; }
.raised .student-sprite.visible { animation:student-wave 2.4s ease-in-out infinite; }
.speaking .student-sprite.visible { animation:student-talk 1.2s ease-in-out infinite; }
.student-name { display:flex; align-items:center; gap:8px; height:20px; }
.student-name strong { font-size:13px; font-weight:600; }
.student-status { font-size:10px; line-height:18px; white-space:nowrap; color:var(--class-muted); }
.raised .student-status, .speaking .student-status { color:var(--student-accent); }
.student-attention { position:absolute; top:8px; right:4px; display:grid; place-items:center; width:20px; height:24px; border-radius:8px 8px 8px 2px; background:var(--student-accent); color:var(--class-surface); font:bold 18px/1 sans-serif; animation:attention-pop .3s ease-out; }
.student-response-slot { position:relative; flex:1; align-self:stretch; min-width:0; min-height:0; display:flex; align-items:center; }
.student-bubble { max-height:100%; width:100%; padding:12px; overflow:auto; overscroll-behavior:contain; scrollbar-width:thin; border:1px solid var(--line); border-radius:12px 12px 12px 2px; background:var(--class-surface-raised); color:var(--class-ink); font-size:13px; line-height:1.65; overflow-wrap:anywhere; }
.student-bubble p { margin:0; }
.student-bubble.failed { color:var(--class-danger); }
.bubble-thinking { color:var(--student-accent); }
.student-idle-mark { display:flex; gap:4px; margin:auto; opacity:.28; }
.student-idle-mark span { width:4px; height:4px; background:var(--student-accent); border-radius:50%; }
.stream-caret { display:inline-block; width:2px; height:1em; margin-left:3px; background:var(--student-accent); vertical-align:middle; animation:caret-pulse .8s infinite; }
.student-equalizer { display:flex; align-items:center; gap:2px; height:14px; }
.student-equalizer i { width:2px; height:10px; background:var(--student-accent); animation:equalize .65s ease-in-out infinite alternate; }
.student-equalizer i:nth-child(2) { animation-delay:-.2s; height:14px; }
.student-equalizer i:nth-child(3) { animation-delay:-.4s; height:7px; }
.bubble-pop-enter-active, .bubble-pop-leave-active { transition:opacity .2s, transform .2s; }
.bubble-pop-enter-from, .bubble-pop-leave-to { opacity:0; transform:translateY(4px); }
@keyframes student-breathe { 50% { transform:translateY(-2px) rotate(.5deg); } }
@keyframes student-wave { 50% { transform:rotate(-2deg) translateY(-2px); } }
@keyframes student-talk { 50% { transform:translateY(-2px) rotate(1deg); } }
@keyframes attention-pop { from { transform:scale(.6); opacity:0; } }
@keyframes caret-pulse { 50% { opacity:0; } }
@keyframes equalize { to { transform:scaleY(.3); } }
@container student-seat (max-width:220px) {
  .student-card { flex-basis:100%; height:112px; }
  .student-sprite-wrap { width:88px; height:80px; }
  .student-response-slot { position:absolute; inset:120px 4px 4px; }
  .student-bubble { padding:6px; font-size:11px; line-height:1.45; }
  .student-attention { top:0; right:0; width:16px; height:20px; font-size:14px; }
}
@media (max-width:900px) { .student-interaction { align-items:flex-start; } }
@media (max-height:600px) {
  .student-sprite-wrap { height:64px; width:88px; }
  .student-card { flex-basis:88px; }
  @container student-seat (max-width:220px) { .student-response-slot { inset-block-start:100px; } }
}
@media (prefers-reduced-motion:reduce) { *, *::before, *::after { animation:none !important; transition:none !important; } }
</style>
