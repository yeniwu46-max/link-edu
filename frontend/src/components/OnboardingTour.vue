<script setup>
import { ref,computed,inject,onMounted,onUnmounted,nextTick,watch } from 'vue'
import { useRouter } from 'vue-router'
import { useEventListener,useResizeObserver } from '@vueuse/core'
import { useAuthStore } from '../stores/auth'
import { classroomHelpKey } from '../utils/classroomHelpContext.js'
import { tourSeen,saveTour,tourSteps } from '../utils/onboarding.js'
const router=useRouter(),auth=useAuthStore(),context=inject(classroomHelpKey,ref(null))
const visible=ref(false),welcome=ref(false),index=ref(0),rect=ref(null),dialog=ref(null),position=ref({}),pending=ref(false)
const step=computed(()=>tourSteps[index.value]);let previousFocus,frame=0,disposed=false,generation=0,timer
function locate(){cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{
 if(!visible.value)return
 const target=welcome.value?null:document.querySelector(step.value.target),r=target?.getBoundingClientRect()
 rect.value=r&&r.width&&r.height?{left:Math.max(8,r.left-6),top:Math.max(8,r.top-6),width:Math.min(r.width+12,innerWidth-16),height:Math.min(r.height+12,innerHeight-16)}:null
 const width=Math.min(352,innerWidth-32),height=dialog.value?.offsetHeight||220
 const top=r?(r.bottom+height+24<innerHeight?r.bottom+14:r.top-height-14):innerHeight/2-height/2
 position.value={width:width+'px',left:Math.max(16,Math.min(innerWidth-width-16,r?r.left:innerWidth/2-width/2))+'px',top:Math.max(16,Math.min(innerHeight-height-16,top))+'px'}
})}
async function focusStep(){await nextTick();locate();dialog.value?.focus();}
function finish(status='skipped'){generation++;saveTour(auth.user?.id,status);visible.value=false;pending.value=false;clearTimeout(timer);nextTick(()=>{if(previousFocus?.isConnected)previousFocus.focus()})}
async function navigate(value){if(pending.value)return;if(value>=tourSteps.length){finish('completed');return}const run=++generation;pending.value=true;index.value=Math.max(0,value);welcome.value=false;await router.push(step.value.path);await nextTick();let tries=0;const reveal=()=>{if(run!==generation||!visible.value)return;const element=document.querySelector(step.value.target);if(!element&&tries++<40){timer=setTimeout(reveal,50);return}element?.scrollIntoView({block:'nearest',behavior:'instant'});pending.value=false;focusStep()};timer=setTimeout(reveal,360)}
function begin(){if(context.value?.active)return;previousFocus=document.activeElement;visible.value=true;welcome.value=false;index.value=0;navigate(0)}
function keyboard(event){if(!visible.value)return;if(event.key==='Escape'){event.preventDefault();finish();return}if(event.key==='Tab'){const list=[...dialog.value.querySelectorAll('button:not(:disabled)')];const first=list[0],last=list.at(-1);if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.value)){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}}}
function offer(){if(disposed||!auth.user?.id||context.value?.active||tourSeen(auth.user.id))return;previousFocus=document.activeElement;welcome.value=true;visible.value=true;focusStep()}
watch(()=>auth.user?.id,()=>{visible.value=false;clearTimeout(timer);timer=setTimeout(offer,650)})
watch(()=>context.value?.active,active=>{if(active&&visible.value)finish('deferred')})
useEventListener(window,'link:tour-start',begin)
useEventListener(window,'resize',locate)
useEventListener(window,'scroll',locate,{capture:true,passive:true})
useEventListener(document,'keydown',keyboard,{capture:true})
useResizeObserver(document.body,locate)
onMounted(()=>{timer=setTimeout(offer,650)})
onUnmounted(()=>{disposed=true;generation++;clearTimeout(timer);cancelAnimationFrame(frame)})
</script>
<template><Teleport to="body"><div v-if="visible" class="tour-layer"><div class="tour-shade"/><div v-if="rect" class="tour-highlight" :style="{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'}"/><section ref="dialog" tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="tour-title" class="tour-card" :style="position"><span class="tour-progress">{{ welcome?'欢迎来到临客 LINK':`${index+1} / ${tourSteps.length}` }}</span><h2 id="tour-title">{{ welcome?'准备好开始你的第一堂课了吗？':step.title }}</h2><p>{{ welcome?'用一分钟了解训练、学生互动与课后复盘。你也可以随时在设置或数字人助手中重新查看。':step.text }}</p><footer><button @click="finish()">跳过</button><button v-if="!welcome&&index" :disabled="pending" @click="navigate(index-1)">上一步</button><button class="tour-next" :disabled="pending" @click="navigate(welcome?0:index+1)">{{ welcome?'开始导览':index===tourSteps.length-1?'完成':'下一步' }}</button></footer></section></div></Teleport></template>
<style scoped>
.tour-layer{position:fixed;inset:0;z-index:16000;color:#f7f0fc}.tour-shade{position:absolute;inset:0;background:#06040a70}.tour-highlight{position:fixed;box-shadow:0 0 0 9999px #05030865,0 0 30px #ae6cea38;border:1px solid #d3a1ff;border-radius:16px;pointer-events:none;box-sizing:border-box}.tour-card{position:fixed;padding:22px;border-radius:20px;background:linear-gradient(145deg,#2c1d36,#151019);border:1px solid #b880e266;box-shadow:0 20px 80px #0009;box-sizing:border-box;outline:none}.tour-progress{color:#e4b085;font-size:12px}.tour-card h2{font-size:20px;line-height:1.45;margin:10px 0}.tour-card p{font-size:14px;color:#d4c4df;line-height:1.8;margin:8px 0 20px}.tour-card footer{display:flex;gap:8px}.tour-card button{background:#ffffff08;border:1px solid #c492e533;border-radius:9px;color:#e4d4ee;padding:9px 12px;cursor:pointer}.tour-card .tour-next{margin-left:auto;background:#79419b;color:white}.tour-card button:focus-visible{outline:2px solid #ffbd8a;outline-offset:3px}.tour-card button:disabled{opacity:.4}
</style>
