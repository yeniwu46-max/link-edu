<script setup>
import { ref,onMounted,onUnmounted,watch } from 'vue'
import { subscribeMotionPreferences } from '../utils/motionPreferences.js'
const props=defineProps({state:{type:String,default:'idle'},level:{type:Number,default:0},quiet:Boolean})
const host=ref(null),ready=ref(false)
let engine,disposed=false,observer,unsubscribe,policy,visible=false,starting=false,timer
async function load(){if(starting||disposed||!visible||!policy?.visible)return;starting=true;try{const {createDigitalHuman}=await import('./fx/digitalHumanEngine.js');if(disposed)return;engine=await createDigitalHuman(host.value,{policy,onError:()=>{ready.value=false},onReady:()=>{ready.value=true}});if(disposed){engine.dispose();return}sync()}catch{ready.value=false}}
function sync(){engine?.setPolicy({...policy,reducedMotion:policy?.reducedMotion||props.quiet});engine?.setVisible(visible);engine?.setState(props.state,props.level);if(!engine&&!starting&&visible&&policy?.visible){clearTimeout(timer);timer=setTimeout(load,120)}}
watch(()=>[props.state,props.level],()=>engine?.setState(props.state,props.level))
watch(()=>props.quiet,sync)
onMounted(()=>{unsubscribe=subscribeMotionPreferences(p=>{policy=p;sync()});observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync()});observer.observe(host.value)})
onUnmounted(()=>{disposed=true;clearTimeout(timer);unsubscribe?.();observer?.disconnect();engine?.dispose()})
</script>
<template><span class="digital-human" aria-hidden="true" @pointermove="engine?.setPointer(($event.offsetX / Math.max(1,host?.clientWidth)-.5)*2)" @pointerleave="engine?.setPointer(0)"><img v-show="!ready" src="/assets/models/assistant/olivia-poster.webp" alt="" /><span ref="host" class="digital-human__canvas" :class="{ready}" /></span></template>
<style scoped>
.digital-human{display:block;position:relative;width:100%;height:100%;mask-image:linear-gradient(#000 82%,transparent 99%);pointer-events:none;filter:drop-shadow(0 0 9px #af75df36)}
.digital-human img,.digital-human__canvas{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.digital-human__canvas{opacity:0}.digital-human__canvas.ready{opacity:1}.digital-human__canvas :deep(canvas){display:block;width:100%;height:100%}
</style>
