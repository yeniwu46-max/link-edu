<script setup>
import { ref,onMounted,onUnmounted,watch } from 'vue'
import PixelSprite from './PixelSprite.vue'
import { subscribeMotionPreferences } from '../utils/motionPreferences.js'
const props=defineProps({state:{type:String,default:'idle'},level:{type:Number,default:0},quiet:Boolean})
const host=ref(null),ready=ref(false),abort=new AbortController()
let engine,disposed=false,observer,unsubscribe,policy,visible=false,starting=false,timer,pointerTarget
function pointerMove(event){const rect=host.value?.getBoundingClientRect();if(rect)engine?.setPointer((event.clientX-rect.left)/Math.max(1,rect.width)*2-1)}
function pointerLeave(){engine?.setPointer(0)}
async function load(){if(starting||disposed||!visible||!policy?.visible)return;starting=true;try{const {createDigitalHuman}=await import('./fx/digitalHumanEngine.js');if(disposed)return;engine=await createDigitalHuman(host.value,{policy,signal:abort.signal,onError:()=>{ready.value=false},onReady:()=>{ready.value=true}});if(disposed){engine.dispose();return}sync()}catch{ready.value=false}}
function sync(){engine?.setPolicy({...policy,reducedMotion:policy?.reducedMotion||props.quiet});engine?.setVisible(visible);engine?.setState(props.state,props.level);if(!engine&&!starting&&visible&&policy?.visible){clearTimeout(timer);timer=setTimeout(load,120)}}
watch(()=>[props.state,props.level],()=>engine?.setState(props.state,props.level))
watch(()=>props.quiet,sync)
onMounted(()=>{unsubscribe=subscribeMotionPreferences(p=>{policy=p;sync()});observer=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync()});observer.observe(host.value);pointerTarget=host.value.closest('button');pointerTarget?.addEventListener('pointermove',pointerMove,{passive:true});pointerTarget?.addEventListener('pointerleave',pointerLeave)})
onUnmounted(()=>{disposed=true;abort.abort();clearTimeout(timer);unsubscribe?.();observer?.disconnect();pointerTarget?.removeEventListener('pointermove',pointerMove);pointerTarget?.removeEventListener('pointerleave',pointerLeave);engine?.dispose()})
</script>
<template><span class="digital-human" aria-hidden="true"><PixelSprite v-show="!ready" character="assistant" /><span ref="host" class="digital-human__canvas" :class="{ready}" /></span></template>
<style scoped>
.digital-human{display:block;position:relative;width:100%;height:100%;pointer-events:none;filter:drop-shadow(0 5px 8px #40305a26)}
.digital-human > .pixel-sprite,.digital-human__canvas{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.digital-human__canvas{opacity:0}.digital-human__canvas.ready{opacity:1}.digital-human__canvas :deep(canvas){display:block;width:100%;height:100%;image-rendering:pixelated}
</style>
