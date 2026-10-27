<script setup>
import { nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ title: String })
const emit = defineEmits(['close'])
const dialog = ref(null)
let previous
watch(() => props.title, async () => { await nextTick(); if (!dialog.value?.contains(document.activeElement)) dialog.value?.querySelector('button')?.focus() })
function close() { emit('close') }
function trap(event) {
  if (event.key !== 'Tab') return
  const items=[...dialog.value.querySelectorAll('button:not(:disabled),a[href],input,select,textarea,[tabindex="0"]')].filter(e=>e.getClientRects().length)
  const first=items[0],last=items.at(-1)
  if(event.shiftKey && (document.activeElement===first || !items.includes(document.activeElement))){event.preventDefault();last?.focus()}
  else if(!event.shiftKey && (document.activeElement===last || !items.includes(document.activeElement))){event.preventDefault();first?.focus()}
}
onMounted(async () => { previous = document.activeElement; await nextTick(); dialog.value.showModal() })
onBeforeUnmount(() => { dialog.value?.close(); if (previous?.isConnected) previous.focus() })
</script>
<template>
  <Teleport to="body">
    <dialog ref="dialog" class="course-modal" aria-labelledby="course-modal-title" @cancel.prevent="close" @keydown="trap" @click="event => { if (event.target === dialog) close() }">
      <section class="course-modal__sheet">
        <header><h2 id="course-modal-title">{{ title }}</h2><button type="button" aria-label="关闭课程弹窗" autofocus @click="close">×</button></header>
        <div class="course-modal__body"><slot /></div>
        <footer v-if="$slots.footer"><slot name="footer" /></footer>
      </section>
    </dialog>
  </Teleport>
</template>
<style>
.course-modal { padding:0; border:1px solid #b59ac4; border-radius:22px; width:min(760px,calc(100vw - 28px)); max-width:none; max-height:calc(100dvh - 32px); color:#392c42; background:#fff3e3; box-shadow:0 24px 100px #0009; }
.course-modal::backdrop { background:#120d20b8; backdrop-filter:blur(8px); }
.course-modal__sheet { display:flex; flex-direction:column; max-height:calc(100dvh - 34px); }
.course-modal header,.course-modal footer { display:flex; align-items:center; justify-content:space-between; gap:16px; padding:18px 24px; flex:none; }
.course-modal header { border-bottom:1px solid #b294bb40; }
.course-modal h2 { margin:0; font-size:22px; color:inherit; }
.course-modal header button { background:transparent; color:inherit; border:0; font-size:28px; min-width:44px; min-height:44px; }
.course-modal__body { overflow:auto; padding:22px 24px; min-height:0; overscroll-behavior:contain; }
.course-modal footer { border-top:1px solid #b294bb40; }
.course-modal button,.course-modal select { font:inherit; cursor:pointer; }
.course-modal select { max-width:100%; padding:10px; background:#fff9f0; color:#392c42; border:1px solid #b294bb; border-radius:10px; }
.course-modal p,.course-modal pre { white-space:pre-wrap; font:inherit; line-height:1.8; }
.course-modal a { color:#69458a; text-underline-offset:4px; }
.course-modal button:focus-visible,.course-modal a:focus-visible,.course-modal select:focus-visible { outline:3px solid #9160b3; outline-offset:3px; }
[data-ui-theme="academy"] .course-modal { color:#243e5f; background:#f3f8ff; border-color:#9eb4ce; }
[data-ui-theme="academy"] .course-modal select { background:white; color:#243e5f; }
@media(max-width:600px) { .course-modal header,.course-modal footer,.course-modal__body { padding:14px 16px; } .course-modal h2 { font-size:18px; } }
</style>
