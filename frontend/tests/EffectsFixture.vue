<script setup>
import { nextTick, onUnmounted, ref } from 'vue'
import HeroAvatar3D from '../src/components/fx/HeroAvatar3D.vue'
import AmbientVideo from '../src/components/fx/AmbientVideo.vue'
import Aurora from '../src/components/fx/Aurora.vue'
import ClickSpark from '../src/components/ClickSpark.vue'
import ClassroomCamera from '../src/components/ClassroomCamera.vue'
import ClassroomCountdown from '../src/components/ClassroomCountdown.vue'
import { ambientUi as vAmbientUi } from '../src/utils/ambientUi.js'
const props = defineProps({setReduced:Function,setHidden:Function,setUnavailable:Function})
const key = ref(0), mounted = ref(true), invalid = ref(false), reduced = ref(false), hidden = ref(false)
const recording = ref(false), result = ref('待测'), elapsed = ref(0)
const unavailable = ref(false)
let video, stream, recorder, paintFrame = 0, benchmarkFrame = 0, stopTimer = 0
function attachVideo(element) { video = element }
function reduceMotion() { reduced.value = !reduced.value; props.setReduced(reduced.value) }
function hide() { hidden.value = !hidden.value; props.setHidden(hidden.value) }
async function remount() { mounted.value = false; await nextTick(); mounted.value = true; key.value++ }
async function toggleWebGL() { unavailable.value = !unavailable.value; props.setUnavailable(unavailable.value); await remount() }
function contextLoss() {
  const canvas = document.querySelector('.hero-avatar canvas')
  const context = canvas?.getContext('webgl2')
  context?.getExtension('WEBGL_lose_context')?.loseContext()
}
async function recordSynthetic() {
  if (recording.value) return
  if (typeof MediaRecorder === 'undefined' || !HTMLCanvasElement.prototype.captureStream) { result.value = '当前浏览器不支持合成流录制'; return }
  const source = document.createElement('canvas')
  source.width = 640; source.height = 360
  const context = source.getContext('2d')
  const paint = now => {
    context.fillStyle = '#100b1a'; context.fillRect(0,0,640,360)
    context.fillStyle = '#b45cff'; context.fillRect((now/8)%580,80,60,120)
    context.fillStyle = '#ff9a42'; context.font = '24px sans-serif'; context.fillText('合成授课画面',36,300)
    paintFrame = requestAnimationFrame(paint)
  }
  paint(performance.now())
  stream = source.captureStream(24)
  video.srcObject = stream
  await video.play()
  recorder = new MediaRecorder(stream, {mimeType:'video/webm',videoBitsPerSecond:800000})
  let bytes = 0, frames = 0, start = performance.now(), previous = start, maximum = 0
  recorder.ondataavailable = event => { bytes += event.data.size }
  recorder.onstop = () => {
    result.value = JSON.stringify({seconds:Number(((performance.now()-start)/1000).toFixed(2)),rafFps:Number((frames*1000/(performance.now()-start)).toFixed(1)),maxFrameMs:Number(maximum.toFixed(1)),recordedBytes:bytes,avatar:document.querySelector('.hero-avatar')?.dataset.renderer})
    cleanup()
  }
  const measure = now => {
    frames++; maximum = Math.max(maximum,now-previous); previous = now
    elapsed.value = Math.floor((now-start)/1000)
    benchmarkFrame = requestAnimationFrame(measure)
  }
  benchmarkFrame = requestAnimationFrame(measure)
  recording.value = true
  result.value = '合成视频录制中，10 秒后自动停止'
  recorder.start(1000)
  stopTimer = setTimeout(() => recorder?.state === 'recording' && recorder.stop(),10000)
}
function cleanup() {
  clearTimeout(stopTimer); cancelAnimationFrame(paintFrame); cancelAnimationFrame(benchmarkFrame)
  stream?.getTracks().forEach(track=>track.stop())
  if (video) video.srcObject = null
  recording.value = false
}
onUnmounted(() => { if (recorder?.state === 'recording') recorder.stop(); cleanup() })
</script>

<template>
  <ClickSpark>
    <main v-ambient-ui class="app-shell fixture">
      <AmbientVideo class="app-shell-bg-video" source="/assets/login-bg-lite.mp4" poster="/assets/login-bg.png" />
      <Aurora />
      <section class="fixture-controls">
        <h1>动效验收夹具</h1><p>仅合成媒体流；不访问摄像头、麦克风或后端接口。</p>
        <button @click="reduceMotion">减少动态效果：{{reduced?'开':'关'}}</button>
        <button @click="hide">页面可见：{{hidden?'否':'是'}}</button>
        <button @click="remount">卸载再挂载人物</button>
        <button @click="invalid=!invalid;key++">模型文件：{{invalid?'缺失':'正常'}}</button>
        <button @click="contextLoss">模拟 WebGL 上下文丢失</button>
        <button @click="toggleWebGL">WebGL：{{unavailable?'不可用':'可用'}}</button>
        <button :disabled="recording" @click="recordSynthetic">开始合成录制</button>
        <output data-testid="fixture-result">{{result}}</output>
      </section>
      <div class="fixture-columns">
        <section class="glass continue">
          <HeroAvatar3D v-if="mounted" :key="key" :model-src="invalid?'/assets/models/not-found.glb':'/assets/models/CesiumMan.glb'" />
          <h3>原主卡片中的真实 3D 人物</h3>
        </section>
        <section class="camera-first classroom-page">
          <div class="camera-stage">
            <ClassroomCamera :enabled="true" :camera-consent="true" :preview-allowed="true" :landmarks="{body:[],hands:[],face:[],at:0}" :teacher-text="recording?'合成授课录制中':'等待合成媒体流'" :progress="elapsed*10" :time-label="String(elapsed)" @video="attachVideo">
              <template #timer><ClassroomCountdown :seconds="Math.max(0,10-elapsed)" /></template>
            </ClassroomCamera>
          </div>
        </section>
      </div>
    </main>
  </ClickSpark>
</template>
<style>
.fixture { min-height:100dvh; padding:24px; }
.fixture-controls,.fixture-columns { position:relative;z-index:1; }
.fixture-controls h1 { font-size:24px; }.fixture-controls p { font-size:13px; }
.fixture-controls button { margin:4px; padding:10px; border:1px solid #b45cff66; border-radius:14px; background:#1c1423; }
.fixture-controls output { display:block; padding:12px; font:12px/1.6 monospace; overflow-wrap:anywhere; }
.fixture-columns { display:grid;grid-template-columns:1fr 1.4fr;gap:20px; }
.fixture-columns .continue { height:560px;display:block;padding:24px; }
.fixture-columns .continue h3 { position:relative;z-index:3; }
.fixture-columns .camera-stage { height:auto!important; }
.fixture-columns .motion-frame { height:430px!important; }
@media(max-width:800px) { .fixture-columns { grid-template-columns:1fr; } }
</style>
