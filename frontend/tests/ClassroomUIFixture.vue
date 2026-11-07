<script setup>
import ModelShowcase from '../src/components/fx/ModelShowcase.vue'
import {ref,provide,shallowRef,nextTick,onUnmounted} from 'vue'
import StudentStage3D from '../src/components/StudentStage3D.vue'
import HelpChat from '../src/components/HelpChat.vue'
import ClassroomCamera from '../src/components/ClassroomCamera.vue'
import AmbientVideo from '../src/components/fx/AmbientVideo.vue'
import {classroomHelpKey} from '../src/utils/classroomHelpContext.js'
import {createClassroomPainter} from '../src/services/classroomCompositor.js'
import {ClassroomRecorder} from '../src/services/classroomRecorder.js'
const props=defineProps({setReduced:Function,setHidden:Function,setUnavailable:Function,contextCounts:Function})
const students=[{id:'ming',name:'小明'},{id:'yu',name:'小雨'},{id:'lin',name:'小林'}]
const mounted=ref(true),invalid=ref(false),reduced=ref(false),hidden=ref(false),unavailable=ref(false)
const stage=ref(null),preview=ref(null),raised=ref(null),reply=ref(null),playback=ref(null),level=ref(0)
const capturing=ref(false),recordState=ref('idle'),result=ref('待测'),url=ref(''),action=ref('无'),counts=ref({}),pixels=ref({})
const context=shallowRef({state:'idle',active:false,hint:'完成课前准备，再开始授课。',actions:{}})
provide(classroomHelpKey,context)
let cameraVideo,stream,oscillator,audio,recorder,paintRAF=0,measureRAF=0,autoStop=0,probeTimer=0,frameCount=0,pauseTimer=0,resumeTimer=0
function helpTarget(target){context.value={...context.value,target}}
context.value.actions=Object.fromEntries(['prepare','settings','captions','timeline'].map(key=>[key,()=>{action.value=key}]))
function setPose(kind){
  raised.value=kind==='raised'?'ming':null
  playback.value=kind==='speaking'?'yu':null
  reply.value=['thinking','speaking','done'].includes(kind)?{studentId:'yu',phase:kind==='speaking'?'speaking':kind,replyId:'fixture-1',text:kind==='thinking'?'': '把一个整体平均分成四份，每一份就是四分之一。'}:null
  level.value=kind==='speaking'?.65:0
}
async function remount(){mounted.value=false;await nextTick();mounted.value=true;setTimeout(()=>counts.value=props.contextCounts(),600)}
function reducedToggle(){reduced.value=!reduced.value;props.setReduced(reduced.value)}
function hiddenToggle(){hidden.value=!hidden.value;props.setHidden(hidden.value)}
async function webglToggle(){unavailable.value=!unavailable.value;props.setUnavailable(unavailable.value);await remount()}
function contextLoss(){document.querySelector('.student-stage canvas')?.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext();setTimeout(()=>counts.value=props.contextCounts(),100)}
async function record(pauseResume=false){
  if(capturing.value)return
  result.value='准备合成媒体';capturing.value=true;frameCount=0
  try {
    audio=new AudioContext();await audio.resume()
    const destination=audio.createMediaStreamDestination(),gain=audio.createGain();gain.gain.value=.05
    oscillator=audio.createOscillator();oscillator.frequency.value=220;oscillator.connect(gain);gain.connect(destination);oscillator.start()
    const source=document.createElement('canvas');source.width=640;source.height=360
    const ctx=source.getContext('2d'),paint=now=>{ctx.fillStyle='#100b1a';ctx.fillRect(0,0,640,360);ctx.fillStyle='#ff994b';ctx.fillRect((now/6)%580,80,60,100);ctx.font='26px sans-serif';ctx.fillStyle='#eee';ctx.fillText('合成授课画面 · 不使用摄像头',25,300);paintRAF=requestAnimationFrame(paint)}
    paint(performance.now());stream=source.captureStream(24);cameraVideo.srcObject=stream;await cameraVideo.play()
    const start=performance.now(),painter=createClassroomPainter(()=>{
      const studentFrame=stage.value?.recordingSnapshot();if(studentFrame)frameCount++
      return {...cameraVideoSnapshot(),raised:raised.value,playbackStudent:playback.value,reply:reply.value,studentFrame,reducedMotion:reduced.value}
    })
    let previous=start,frames=0,maximum=0
    function measure(now){frames++;maximum=Math.max(maximum,now-previous);previous=now;measureRAF=requestAnimationFrame(measure)}
    measureRAF=requestAnimationFrame(measure)
    recorder=new ClassroomRecorder({paint(ctx,canvas){painter(ctx,canvas);preview.value.getContext('2d').drawImage(canvas,0,0,640,360)},getWallMs:()=>performance.now()-start,getAudioStream:()=>destination.stream,
      onState:state=>recordState.value=state,onError:error=>result.value=error,onResult:recording=>{
        if(url.value)URL.revokeObjectURL(url.value);url.value=URL.createObjectURL(recording.blob)
        const host=document.querySelector('.student-stage__canvas')
        result.value=JSON.stringify({seconds:+(recording.durationMs/1000).toFixed(2),rafFps:+(frames*1000/(performance.now()-start)).toFixed(1),maxFrameMs:+maximum.toFixed(1),recordedBytes:recording.blob.size,studentFrames:frameCount,segments:recording.segments.length,audioTracks:recorder.stream.getAudioTracks().length,renderer:document.querySelector('.student-stage')?.dataset.renderer,quality:host?.dataset.quality,renderFps:host?.dataset.renderFps,renderMs:host?.dataset.renderMs,loadMs:host?.dataset.loadMs});cleanup()
      }})
    await recorder.start();setPose('speaking');result.value='录制中，10 秒自动结束'
    if(pauseResume){pauseTimer=setTimeout(()=>recorder.pause(),2000);resumeTimer=setTimeout(()=>recorder.resume(),4000)}
    autoStop=setTimeout(()=>recorder.stop(),10000)
  }catch(error){result.value=error.message;recorder?.dispose();cleanup()}
}
function cameraVideoSnapshot(){return{video:cameraVideo,captions:true,captionLabel:'老师',captionText:'合成授课与学生状态验收'}}
function cleanup(){clearTimeout(autoStop);clearTimeout(pauseTimer);clearTimeout(resumeTimer);cancelAnimationFrame(paintRAF);cancelAnimationFrame(measureRAF);stream?.getTracks().forEach(t=>t.stop());oscillator?.stop();audio?.close();if(cameraVideo)cameraVideo.srcObject=null;capturing.value=false;setPose('done')}
function inspectPixels(){
  const frame=stage.value?.recordingSnapshot(),out={}
  if(frame)for(const [id,slot] of Object.entries(frame.slots)){
    const data=frame.canvas.getContext('2d').getImageData(Math.max(0,Math.floor(slot.x)),Math.max(0,Math.floor(slot.y)),Math.floor(slot.width),Math.floor(slot.height)).data
    let filled=0;for(let i=3;i<data.length;i+=4)if(data[i])filled++
    out[id]={filled,total:data.length/4}
  }
  pixels.value=out
}
async function lifecycle(){
  for(let i=0;i<3;i++){mounted.value=false;await nextTick();await new Promise(r=>setTimeout(r,100));mounted.value=true;await nextTick();await new Promise(r=>setTimeout(r,1600))}
  counts.value=props.contextCounts()
}
function pause(){recorder?.pause()}
function resume(){recorder?.resume()}
onUnmounted(()=>{recorder?.dispose();cleanup();if(url.value)URL.revokeObjectURL(url.value);clearInterval(probeTimer)})
</script>
<template>
  <main class="app-shell classroom-fixture">
    <AmbientVideo class="app-shell-bg-video" source="/assets/login-bg-lite.mp4" poster="/assets/login-bg.png" />
    <section class="fixture-controls">
      <h1>教学训练验收夹具</h1><p>仅使用合成视频与音频，不访问摄像头、麦克风或后端数据。</p>
      <button v-for="pose in ['idle','raised','thinking','speaking','done']" :key="pose" @click="setPose(pose)">{{pose}}</button>
      <button @click="reducedToggle">减少动态：{{reduced?'开':'关'}}</button><button @click="hiddenToggle">页面可见：{{hidden?'否':'是'}}</button>
      <button @click="invalid=!invalid;remount()">模型：{{invalid?'缺失':'正常'}}</button><button @click="webglToggle">WebGL：{{unavailable?'不可用':'可用'}}</button>
      <button @click="contextLoss">上下文丢失</button><button @click="lifecycle" :disabled="capturing">重复卸载 3 次</button><button @click="counts=props.contextCounts()">检查上下文数量</button>
      <button @click="record(false)" :disabled="capturing">合成课堂录像 10 秒</button><button @click="record(true)" :disabled="capturing">录像暂停恢复验收</button><button @click="pause" :disabled="recordState!=='recording'">暂停录像</button><button @click="resume" :disabled="recordState!=='paused'">恢复录像</button><button @click="inspectPixels">检查缓存像素</button>
      <output data-testid="fixture-result">{{result}}</output><output data-testid="context-counts">{{JSON.stringify(counts)}}</output><output data-testid="frame-pixels">{{JSON.stringify(pixels)}}</output><output>助手动作：{{action}}</output>
    </section>
    <section class="classroom-page camera-first screen-first">
      <div class="camera-stage">
        <ClassroomCamera enabled camera-consent preview-allowed :landmarks="{body:[],hands:[],face:[],at:0}" :teacher-text="capturing?'合成授课验收中':''" :reply="reply" @video="cameraVideo=$event" @fullscreen-target="helpTarget">
          <template #students><StudentStage3D v-if="mounted" ref="stage" :students="students" :raised="raised" :reply="reply" :playback-student="playback" :level="level" :capturing="capturing" :model-base="invalid?'/assets/models/missing/':'/assets/models/students/'" @select="setPose('speaking')" /></template>
        </ClassroomCamera>
      </div>
    </section>
    <section class="fixture-preview"><canvas ref="preview" width="640" height="360" aria-label="录像合成预览" /><video v-if="url" :src="url" controls aria-label="本机录像回放" /><a v-if="url" :href="url" download="classroom-ui-acceptance.webm">下载验收录像</a></section>
    <section v-if="mounted" class="fixture-models" aria-label="交互模型验收">
      <ModelShowcase kind="book" label="立体课程书册" action-label="翻开书册" />
      <ModelShowcase kind="archive" label="立体资料卡片" action-label="展开档案" />
      <ModelShowcase kind="orbit" label="成长轨道模型" action-label="展开轨道" />
      <ModelShowcase kind="prism" label="多维评课棱镜" action-label="展开棱镜" />
    </section>
    <HelpChat v-if="mounted" />
  </main>
</template>
<style>
.fixture-models{display:flex;flex-wrap:wrap;position:relative;z-index:1;gap:20px;padding:20px;background:#100c17;}
.classroom-fixture{display:block!important;padding:16px;min-height:100dvh;height:auto!important;overflow:visible!important}.fixture-controls,.classroom-fixture .classroom-page,.fixture-preview{position:relative;z-index:1}
.fixture-controls h1{font-size:20px}.fixture-controls p{font-size:12px}.fixture-controls button{margin:3px;padding:7px 10px;background:#201525;border:1px solid #b45cff50;border-radius:9px;font-size:12px}
.fixture-controls output{display:block;font:12px/1.6 monospace;overflow-wrap:anywhere}.classroom-fixture .classroom-camera{height:570px!important}.fixture-preview{display:flex;gap:12px;margin-top:10px}.fixture-preview canvas,.fixture-preview video{width:48%;height:auto;object-fit:contain}
</style>
