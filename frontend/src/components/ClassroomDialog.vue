<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue';
const props=defineProps({modelValue:Boolean, title:String});
const emit=defineEmits(['update:modelValue']);
const dialog=ref(null);
let trigger;
watch(()=>props.modelValue, async value=>{
  if (value) trigger=document.activeElement;
  await nextTick();
  if (value && props.modelValue && !dialog.value?.open) dialog.value?.showModal();
  else if (!value) dialog.value?.close();
});
function close() { dialog.value?.close(); emit('update:modelValue',false); trigger?.focus(); }
onBeforeUnmount(()=>dialog.value?.close());
</script>
<template>
  <dialog ref="dialog" class="classroom-dialog" :aria-label="title" @cancel.prevent="close" @click.self="close" @close="emit('update:modelValue',false)">
    <header><h2>{{ title }}</h2><button class="dialog-close" :aria-label="`关闭${title}`" autofocus @click="close">×</button></header>
    <div class="dialog-content"><slot /></div>
  </dialog>
</template>
<style scoped>
.classroom-dialog { width:min(580px,calc(100vw - 32px)); max-height:85dvh; padding:0; border:1px solid var(--line,#413448); border-radius:16px; background:var(--class-surface-raised,#1b1524); color:var(--class-ink,#f4f2f6); box-shadow:0 24px 80px #0008; overflow:auto; overscroll-behavior:contain; }
.classroom-dialog::backdrop { background:#050407b8; }
.classroom-dialog header { position:sticky; top:0; display:flex; align-items:center; justify-content:space-between; padding:12px 20px; background:var(--class-surface-raised,#1b1524); border-bottom:1px solid var(--line); z-index:1; }
.dialog-content { padding:20px; }
.dialog-close { width:40px; height:40px; flex:none; background:none; color:inherit; border:1px solid var(--line); border-radius:8px; cursor:pointer; font-size:24px; }
@media(max-width:480px) { .dialog-content {padding:12px;} }
</style>
