<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { conversationName, conversationStatus } from '../services/classroomConversation.js';
const props = defineProps({ messages: { type: Array, default: () => [] }, visible: Boolean });
const scroll = ref(null), following = ref(true);
let userScrollUntil = 0, resizeObserver;
function scrollIntent() { userScrollUntil = performance.now() + 1000; }
const time = ms => `${String(Math.floor((ms || 0) / 60000)).padStart(2, '0')}:${String(Math.floor((ms || 0) / 1000) % 60).padStart(2, '0')}`;
function onScroll() {
  const el = scroll.value;
  if (performance.now() > userScrollUntil) return;
  following.value = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
}
async function latest() {
  following.value = true;
  await nextTick();
  if (scroll.value) scroll.value.scrollTop = scroll.value.scrollHeight;
}
watch(() => props.messages, async (messages, previous) => {
  if (!messages.length || (previous?.length && previous[0].key !== messages[0]?.key)) following.value = true;
  if (following.value) await latest();
});
watch(() => props.visible, visible => { if (visible && following.value) latest(); });
onMounted(() => {
  resizeObserver = new ResizeObserver(() => { if (props.visible && following.value) latest(); });
  resizeObserver.observe(scroll.value);
});
onUnmounted(() => resizeObserver?.disconnect());
</script>
<template>
  <section class="classroom-conversation" aria-label="课堂对话">
    <header class="conversation-heading"><h2>课堂对话</h2><span>本节课堂 · 实时记录</span></header>
    <div ref="scroll" class="conversation-scroll" tabindex="0" aria-label="对话历史，向上滚动查看" @scroll="onScroll" @wheel.passive="scrollIntent" @touchmove.passive="scrollIntent" @pointerdown="scrollIntent" @pointermove.passive="event => { if (event.buttons) scrollIntent(); }" @keydown="scrollIntent">
      <div v-if="!messages.length" class="conversation-empty"><strong>每一次交流，都留在这里</strong><p>开始授课后，你的语音转写与学生回答会实时呈现。</p></div>
      <ol v-else class="conversation-messages">
        <li v-for="message in messages" :key="message.key" :class="['conversation-message', message.role]" :data-message-key="message.key">
          <div class="conversation-meta"><strong>{{ conversationName(message) }}</strong><time>{{ time(message.at) }}</time></div>
          <div class="conversation-bubble"><p v-if="message.text">{{ message.text }}</p><span v-else class="conversation-placeholder">{{ conversationStatus(message) || '等待回应' }}…</span></div>
          <small v-if="conversationStatus(message)" class="conversation-status">{{ conversationStatus(message) }}<template v-if="!message.eventId && ['failed','interrupted','disconnected','paused','ended'].includes(message.status)"> · 未完成</template></small>
          <small v-if="message.error" class="conversation-status">{{ message.error }}</small>
        </li>
      </ol>
    </div>
    <button v-if="!following" type="button" class="conversation-latest" @click="latest">↓ 回到最新</button>
  </section>
</template>
<style scoped>
.classroom-conversation { position:relative; display:flex; flex-direction:column; min-height:0; min-width:0; overflow:hidden; border:1px solid var(--line); border-radius:12px; background:var(--class-surface); color:var(--class-ink); }
.conversation-heading { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:4px 12px; padding:16px 20px; border-bottom:1px solid var(--line); }
.conversation-heading h2 { margin:0; font-size:15px; font-weight:600; }
.conversation-heading span,.conversation-meta time,.conversation-status { font-size:11px; color:var(--class-muted); }
.conversation-scroll { flex:1; min-height:0; overflow:auto; overscroll-behavior:contain; padding:20px; scrollbar-width:thin; overflow-anchor:none; }
.conversation-empty { display:flex; flex-direction:column; justify-content:center; height:100%; text-align:center; gap:12px; color:var(--class-muted); font-size:13px; }
.conversation-empty strong { color:var(--class-ink); font-weight:500; }
.conversation-empty p { margin:0; line-height:1.8; }
.conversation-messages { list-style:none; margin:0; padding:0 0 24px; display:flex; flex-direction:column; gap:24px; }
.conversation-message { max-width:90%; align-self:flex-start; min-width:96px; }
.conversation-message.teacher { align-self:flex-end; }
.conversation-meta { display:flex; align-items:center; gap:12px; margin-bottom:8px; }
.conversation-meta strong { font-size:12px; font-weight:500; }
.teacher .conversation-meta { justify-content:flex-end; }
.conversation-bubble { border:1px solid var(--line); border-radius:4px 12px 12px; padding:12px 16px; background:color-mix(in srgb,var(--class-muted) 7%,var(--class-surface)); }
.teacher .conversation-bubble { border-radius:12px 4px 12px 12px; background:color-mix(in srgb,var(--violet) 12%,var(--class-surface)); }
.conversation-bubble p { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font-size:14px; line-height:1.8; }
.conversation-placeholder { font-size:13px; color:var(--class-muted); }
.conversation-status { display:block; margin-top:6px; }
.conversation-latest { position:absolute; bottom:12px; left:50%; transform:translateX(-50%); padding:8px 16px; border:1px solid var(--line); border-radius:20px; background:var(--class-surface); color:var(--class-ink); box-shadow:0 4px 16px #0002; cursor:pointer; font-size:12px; }
@media(max-width:700px) { .conversation-heading { padding:12px; } .conversation-scroll { padding:12px; } }
</style>
