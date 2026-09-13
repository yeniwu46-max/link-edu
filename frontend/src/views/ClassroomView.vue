<script setup>
import { computed, onMounted, ref, watch, nextTick } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router";
import { api } from "../services/api";
import { speechProviderLabel, classroomLoadError, connectionSummary, budgetNotice, classroomStartBlockers } from "../services/classroomStatus.js";
import { useClassroom } from "../services/useClassroom";
import StudentAvatar from "../components/StudentAvatar.vue";
import ClassroomCamera from "../components/ClassroomCamera.vue";
import ClassroomCountdown from "../components/ClassroomCountdown.vue";
import ClassroomDialog from "../components/ClassroomDialog.vue";
import { classroomDestination, formatReportDate } from "../services/classroomReview.js";
import ClassroomSettings from "../components/ClassroomSettings.vue";
import ClassroomTimeline from "../components/ClassroomTimeline.vue";
import ClassroomIconButton from "../components/ClassroomIconButton.vue";
import ClassroomCalibration from '../components/ClassroomCalibration.vue';
import { useAuthStore } from '../stores/auth';
import { useClassroomRecording } from '../services/useClassroomRecording.js';
import { History, PlayerPlay, PlayerStop, PlayerPause, Video, VideoOff, Microphone, Wifi, Messages, HandStop, Refresh, ShieldCheck, AlertCircle } from '@vicons/tabler';
import "../classroom.css";

const route=useRoute(), router=useRouter(), live=useClassroom();
const {room, capabilities, events, error, state, partial, students, activeStudent, raised, mouth,
  pose, reply, playbackStudent, landmarks, motionStatus, handStatus, faceStatus, cameraEnabled,
  retryMotion, camera, elapsed, cloudVision, busy, send, refreshCapabilities, begin, reconnect,
  finish, load, regenerate, setVision, volume, setVolume, cameraResolution, cameraAdjusting,
  cameraNote, setCameraResolution, previewCamera, pauseCapture, capabilitiesLoading, capabilitiesError} = live;
const mode=ref(route.query.mode === 'fragment' ? 'fragment' : 'full'), consent=ref(false), cameraConsent=ref(false), history=ref([]), probing=ref("");
const showHistory=ref(false), timelineOpen=ref(false), timelineRef=ref(null), cameraRef=ref(null);
const auth=useAuthStore();
const recording=useClassroomRecording({state,room,getUserId:()=>auth.user?.id,
  snapshot:()=>({...cameraRef.value?.recordingSnapshot(),reply:reply.value,raised:raised.value,
    playbackStudent:playbackStudent.value,studentStates:room.value?.students,reducedMotion:window.matchMedia('(prefers-reduced-motion: reduce)').matches}),
  wallMs:()=>live.wallElapsed.value*1000,audioStream:()=>live.audioForRecording.value?.()});
const {enabled:recordEnabled,phase:recordPhase,previewOpen:recordPreview,url:recordUrl,result:recordResult,
  saved:recordSaved,saving:recordSaving,error:recordError}=recording;
const previewVideo=ref(null);
watch(recordPreview,open=>{if(!open)previewVideo.value?.pause();});
async function pauseLesson(){recording.pause();await pauseCapture();}
async function finishLesson(){if(elapsed.value>=10){recording.stop();await finish();}}
const defaultStudents=[{id:"ming",name:"小明"},{id:"yu",name:"小雨"},{id:"lin",name:"小林"}];
const statusGroups=computed(()=>[
  {key:"dialogue",title:"对话",keys:["dialogue"]},
  {key:"speech",title:"语音",keys:["asr","tts"]},
].map(group=>({...group,...(capabilitiesLoading.value ? {tone:"pending",label:"读取中…"} :
  capabilitiesError.value ? {tone:"failed",label:"状态读取失败"} : connectionSummary(capabilities.value?.services,group.keys))})));
const quotaNotice=computed(()=>budgetNotice(capabilities.value?.budget));
const connectionIssue=computed(()=>statusGroups.value.some(g=>["failed","warning"].includes(g.tone)));
const asrProvider=computed(()=>capabilities.value?.services?.asr?.provider);
const llmProvider=computed(()=>capabilities.value?.services?.dialogue?.provider);
const llmLabel=computed(()=>llmProvider.value==="openai_next" ? "OpenAI Next（DeepSeek 模型）" : "DeepSeek");
watch([asrProvider,llmProvider],()=>{consent.value=false;});
const active=computed(()=>["connecting","listening","speaking","finishing"].includes(state.value));
watch(cameraConsent,allowed=>{if(!allowed && cameraEnabled.value && !active.value) pauseCapture();});
const startBlockers=computed(()=>classroomStartBlockers({capabilities:capabilities.value,
  capabilitiesLoading:capabilitiesLoading.value,capabilitiesError:capabilitiesError.value,
  consent:consent.value,cameraConsent:cameraConsent.value,busy:busy.value,state:state.value}));
const startHint=computed(()=>startBlockers.value.length ? startBlockers.value.map(r=>r.message).join('\n') :
  '已就绪，点击开始授课');
const consentOnly=computed(()=>startBlockers.value.length>0 && startBlockers.value.every(r=>['audio_consent','camera_consent'].includes(r.code)));
const conciseHint=computed(()=>consentOnly.value ? '开始前，请勾选'+[!consent.value && '语音与评课',!cameraConsent.value && '摄像头'].filter(Boolean).join('、')+'授权' : startBlockers.value.find(r=>!['audio_consent','camera_consent'].includes(r.code))?.message || startHint.value);
const needsSettings=computed(()=>startBlockers.value.some(r=>r.action==='settings'));
const remaining=computed(()=>Math.max(0,((room.value?.mode || mode.value)==="fragment" ? 480 : 600)-elapsed.value));
const total=computed(()=>((room.value?.mode || mode.value)==='fragment' ? 480 : 600));
const progress=computed(()=>Math.min(100, elapsed.value/total.value*100));
const clockLabel=seconds=>`${Math.floor(seconds/60).toString().padStart(2,'0')}:${Math.floor(seconds%60).toString().padStart(2,'0')}`;
const timeLabel=computed(()=>`${clockLabel(elapsed.value)} / ${clockLabel(total.value)}`);
const finishWait=computed(()=>Math.max(0,Math.ceil(10-elapsed.value)));
const stateLabel=computed(()=>({
  idle:"准备中",connecting:"连接中",listening:"授课中",
  speaking:"学生发言中",paused:"课堂已暂停",disconnected:"连接已断开",finishing:"结束处理中",ended:"课堂已结束"
})[state.value]);
const latestTeacher=computed(()=>events.value.filter(e=>e.type==="transcript").at(-1)?.data.text);
function openSettings(){cameraRef.value?.openSettings();}
async function refreshHistory(){
  try {history.value=(await api.get("/classroom/sessions",{timeout:10000,skipBusy:true})).data.items;}
  catch(e){error.value=classroomLoadError(e,"历史课堂暂时无法读取");}
}
async function probe(service){
  probing.value=service;
  try {await api.post("/classroom/probe",{service});await refreshCapabilities();}
  catch {error.value="连接检查失败，请稍后重试";}
  finally {probing.value="";}
}
async function start(){
  if(startBlockers.value.length) return;
  await begin(mode.value,consent.value,cameraConsent.value);
  if(room.value) router.replace({query:{session:room.value.session_id}});
}
async function resume(){
  if(startBlockers.value.length) return;
  await reconnect(consent.value,cameraConsent.value);
}
function selectStudent(id){
  if(raised.value===id) send("select_student",{student_id:id});
  else error.value="请用麦克风点名"+defaultStudents.find(s=>s.id===id).name+"。";
}
async function openSession(sid){
  if(busy.value || active.value) return;
  if(cameraEnabled.value) pauseCapture();
  try {await load(sid);if(room.value.state==="active") state.value="disconnected";showHistory.value=false;}
  catch {error.value="课堂不存在或没有访问权限";}
}
async function jumpEvidence(id){
  timelineOpen.value=true;
  await nextTick();
  await nextTick();
  await timelineRef.value?.reveal(id);
}
watch(()=>route.query.session,sid=>{
  if(sid && Number(sid)!==room.value?.session_id && !active.value) openSession(sid);
});
watch(state,s=>{if(s==="ended"){refreshHistory();refreshCapabilities();}});
onMounted(async()=>{
  await refreshCapabilities();await refreshHistory();
  if(route.query.session) await openSession(route.query.session);
});
onBeforeRouteLeave(()=>{
  if(recording.hasUnsaved() && !window.confirm('录像尚未保存，离开会丢失。确定离开吗？'))return false;
  if(active.value && !window.confirm('离开会暂停课堂并停止采集，确定离开吗？'))return false;
  if(active.value)pauseCapture();
  return true;
});
</script>

<template>
  <div class="classroom-page camera-first">
    <header class="classroom-heading">
      <div><h1>模拟课堂<span class="heading-dot" aria-hidden="true">.</span></h1><p>小学数学 · 分数的初步认识</p></div>
      <nav class="classroom-window-actions" aria-label="课堂窗口">
        <button class="class-btn secondary" :disabled="active || busy" aria-haspopup="dialog" :aria-expanded="showHistory" @click="showHistory=true;refreshHistory()"><History aria-hidden="true" />历史课堂</button>
      </nav>
    </header>
    <p v-if="error" class="class-alert" role="alert">{{ error }}<button aria-label="关闭提示" @click="error=''">×</button></p>
    <div v-if="quotaNotice || connectionIssue" class="class-notice" role="status">
      <span>{{ quotaNotice || "部分服务待处理，请检查连接设置。" }}</span>
      <button class="text-action" @click="openSettings">查看设置 ↗</button>
    </div>
    <section class="classroom-launch" aria-label="授课申请">
      <div v-if="state!=='ended'" class="launch-permissions">
        <div class="consent-row">
          <ShieldCheck class="consent-shield" aria-hidden="true" />
          <label><input type="checkbox" v-model="consent" :disabled="active || busy" />同意语音识别与 AI 评课</label>
          <label><input type="checkbox" v-model="cameraConsent" :disabled="active || busy" />同意摄像头开启</label>
          <label><input type="checkbox" v-model="recordEnabled" :disabled="!!room || busy" />本机录像</label>
          <details class="disclosure privacy-details">
            <summary>隐私说明</summary>
            <p>麦克风音频上传{{ speechProviderLabel(asrProvider) }}识别；文字与本地动作摘要提交{{ llmLabel }}用于对话和评课。未选择录像时不保存原始录音，转写与课堂事件会保留。</p>
            <p>本机录像包含教师画面、学生、字幕和师生声音，不上传服务器；课后选择保存或放弃。清理浏览器数据会移除已保存录像，下载副本需自行保管。</p>
            <p>摄像头为授课必需条件，仍须浏览器授权。动作检测在本机运行，不做人脸识别或心理推断。云端截图分析需另行授权。</p>
            <p>暂停同时停止计时和录像。有效授课满 10 秒且转写、完整学生反馈充足才评课；动作或场景不足时教态不评分。</p>
          </details>
        </div>
      </div>
      <span v-else class="subtle-note">本节已结束 · 课堂记录已保留</span>
      <label v-if="!room" class="lesson-mode">
        <span class="sr-only">训练时长</span>
        <select id="class-mode" v-model="mode" :disabled="busy"><option value="full">10 分钟 · 完整课</option><option value="fragment">8 分钟 · 专项练习</option></select>
      </label>
      <div v-if="!room || ['paused','disconnected'].includes(state)" class="class-start-feedback" :class="{blocked:startBlockers.length && !consentOnly}">
        <span id="class-start-hint" role="status" aria-live="polite"><AlertCircle v-if="startBlockers.length" aria-hidden="true" />{{ conciseHint }}</span>
        <details v-if="startBlockers.length && !consentOnly" class="start-reasons">
          <summary>全部原因</summary>
          <ul><li v-for="reason in startBlockers" :key="reason.code">{{ reason.message }}</li></ul>
        </details>
        <button v-if="!consentOnly" class="text-action" :disabled="capabilitiesLoading || busy" @click="refreshCapabilities"><Refresh aria-hidden="true" />{{ capabilitiesLoading ? '读取中' : '刷新状态' }}</button>
        <button v-if="needsSettings" class="text-action" @click="openSettings">查看配置</button>
      </div>
    </section>
    <ClassroomCalibration :enabled="cameraEnabled" :active="active" :motion="pose" />
    <p v-if="recordEnabled" role="status" class="subtle-note">录像 · {{ {idle:'开课后录制',recording:'录制中',paused:'已暂停',preview:'可预览',failed:'不可用'}[recordPhase] }} <button v-if="recordResult" class="text-action" @click="recordPreview=true">预览录像</button></p>
    <p v-if="recordError" role="alert" class="class-alert">{{ recordError }}</p>
    <ClassroomDialog v-model="recordPreview" title="课后录像预览">
      <video v-if="recordUrl" ref="previewVideo" :src="recordUrl" controls playsinline style="width:100%;max-height:45vh" aria-label="课堂录像预览" />
      <p>仅保存在当前浏览器 · {{ ((recordResult?.blob.size||0)/1024/1024).toFixed(1) }} MiB</p>
      <div class="class-controls"><button class="class-btn" :disabled="recordSaving || recordSaved" @click="recording.save">{{recordSaved?'已保存到本机':'保存到本机'}}</button><button class="class-btn secondary" @click="recording.download">下载视频</button><button class="text-action" @click="recording.discard">{{recordSaved?'关闭预览':'放弃'}}</button></div>
      <p v-if="recordError" role="alert">{{ recordError }}</p>
    </ClassroomDialog>
    <section class="class-panel camera-stage" aria-label="授课主画面">
      <ClassroomCamera ref="cameraRef" :enabled="cameraEnabled" :disabled="state==='ended'" :landmarks="landmarks"
        :camera-consent="cameraConsent" :camera-busy="busy" :preview-allowed="!active"
        :motion="pose" :face-status="faceStatus" :motion-status="motionStatus" :hand-status="handStatus"
        :teacher-text="partial || latestTeacher" :reply="reply" :volume="volume" :resolution="cameraResolution"
        :resolution-busy="cameraAdjusting || busy" :camera-note="cameraNote" :progress="progress" :time-label="timeLabel"
        @volume="setVolume" @resolution="setCameraResolution" @video="camera=$event" @retry="retryMotion" @toggle="previewCamera(cameraConsent)">
        <template #heading><span class="connection-label" :class="state"><i aria-hidden="true" />{{ stateLabel }}</span><p class="scene-topic">分数的初步认识</p></template>
        <template #timer><ClassroomCountdown :seconds="remaining" /></template>
        <template #students>
          <StudentAvatar v-for="s in students.length ? students : defaultStudents" :key="(room?.session_id || 'new')+'-'+s.id"
            compact :student="s" :raised="raised===s.id" :speaking="playbackStudent===s.id"
            :interaction-state="room?.students?.[s.id]?.interaction_state"
            :reply="reply.studentId===s.id ? reply : null" :level="mouth" @select="selectStudent" />
        </template>
        <template #transport>
          <div class="class-controls">
            <button v-if="!room" class="class-btn player-start" :disabled="startBlockers.length>0" :title="startHint" aria-describedby="class-start-hint" @click="start"><PlayerPlay aria-hidden="true" />{{ busy ? '准备中…' : '开始授课' }}</button>
            <template v-else-if="state!=='ended'">
              <button v-if="['paused','disconnected'].includes(state)" class="class-btn player-start" :disabled="startBlockers.length>0" :title="startHint" aria-describedby="class-start-hint" @click="resume"><PlayerPlay aria-hidden="true" />继续授课</button>
              <button class="class-btn player-start" aria-label="结束并评课" :disabled="busy || state==='finishing' || finishWait>0" :title="finishWait ? '还需授课 '+finishWait+' 秒才能评课' : '结束课堂，检查证据并评课'" @click="finishLesson"><PlayerStop aria-hidden="true" />{{ state==='finishing' ? '处理中…' : finishWait>0 ? '结束（'+finishWait+'s）' : '结束并评课' }}</button>
            </template>
            <button v-else class="class-btn player-start" @click="router.push('/classroom').then(()=>router.go(0))"><PlayerPlay aria-hidden="true" />下一节课</button>
          </div>
        </template>
        <template #actions>
          <ClassroomIconButton v-if="reply.phase==='failed' && !reply.replyId" label="重试学生回答" :disabled="state!=='listening'" @click="send('retry_generation')"><Refresh /></ClassroomIconButton>
          <ClassroomIconButton label="打断学生" :disabled="!(activeStudent || ['thinking','generating','queued'].includes(reply.phase))" @click="send('cancel')"><HandStop /></ClassroomIconButton>
          <ClassroomIconButton :label="active ? '暂停课堂' : '关闭摄像头预览'" :disabled="!cameraEnabled || busy || state==='finishing'" @click="pauseLesson"><PlayerPause v-if="active" /><VideoOff v-else /></ClassroomIconButton>
        </template>
        <template #utilities>
          <ClassroomIconButton label="课堂记录" aria-haspopup="dialog" :aria-expanded="timelineOpen" @click="timelineOpen=true"><Messages /></ClassroomIconButton>
        </template>
        <template #settings>
          <div class="vision-option">
            <label><input type="checkbox" v-model="cloudVision" :disabled="state==='ended' || busy" @change="setVision" />云端画面分析</label>
            <p class="subtle-note">默认关闭。开启后最多每 15 秒上传 1 张截图，每课最多 40 张，消耗视觉额度并私有保存用于证据核对。画面证据不足时仅教态不评分，其他维度照常评审。关闭时只检查本地教师入镜，不识别背景语义。</p>
          </div>
          <ClassroomSettings :capabilities="capabilities" :probing="probing" :active="active" @probe="probe" @refresh="refreshCapabilities" />
        </template>
        <template #windows><ClassroomDialog v-model="timelineOpen" title="课堂记录"><ClassroomTimeline ref="timelineRef" :events="events" /></ClassroomDialog></template>
      </ClassroomCamera>
    </section>
    <div class="classroom-services" aria-label="课堂连接状态">
      <ClassroomIconButton align="start" :label="cameraEnabled ? '摄像头已开启（设置）' : '摄像头已关闭（设置）'" :active="cameraEnabled" @click="openSettings"><Video v-if="cameraEnabled" /><VideoOff v-else /></ClassroomIconButton>
      <ClassroomIconButton align="start" :label="['listening','speaking'].includes(state) ? '麦克风采集中（设置）' : '麦克风未采集（设置）'" :active="['listening','speaking'].includes(state)" @click="openSettings"><Microphone /></ClassroomIconButton>
      <ClassroomIconButton :label="'连接：'+stateLabel+'（设置）'" @click="openSettings"><Wifi /></ClassroomIconButton>
      <span v-for="group in statusGroups" :key="group.key" class="status-item" :class="group.tone"><i aria-hidden="true" />{{ group.title }} <b>{{ group.label }}</b></span>
      <span v-if="!reply.studentId && reply.phase==='thinking'" role="status">学生正在思考…</span>
    </div>
    <section v-if="room?.state==='ended'" class="class-panel classroom-review-entry">
      <div><h2>课堂已保存</h2><p>{{ {running:'AI 正在评课，可前往报告页查看进度。',completed:'AI 评课已就绪，查看维度分析与课堂证据。',insufficient:'课堂数据不足，查看具体缺项与补充建议。',failed:'评课未完成，前往报告页查看原因并重试。'}[room.report_state] || '前往 AI 评课页面查看本节课堂。' }}</p></div>
      <router-link class="class-btn" :to="classroomDestination(room)">查看 AI 评课 ↗</router-link>
    </section>
    <ClassroomDialog v-model="showHistory" title="历史课堂">
      <div class="history-panel">
        <p v-if="!history.length" class="empty-state">暂无课堂记录</p>
        <router-link v-for="item in history" :key="item.session_id" :to="classroomDestination(item)" @click="item.state==='active' && openSession(item.session_id)">
          <span>{{ item.topic }}<small>{{ formatReportDate(item.created_at) }}</small></span>
          <b>{{ ['active','paused'].includes(item.state) ? "可继续" : {completed:"查看报告",failed:"待重试",running:"评课中",idle:"待评课",insufficient:"数据不足"}[item.report_state] }}</b>
        </router-link>
      </div>
    </ClassroomDialog>
  </div>
</template>
