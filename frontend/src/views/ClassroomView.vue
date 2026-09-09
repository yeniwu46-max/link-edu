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
import ClassroomReport from "../components/ClassroomReport.vue";
import ClassroomSettings from "../components/ClassroomSettings.vue";
import ClassroomTimeline from "../components/ClassroomTimeline.vue";
import "../classroom.css";

const route=useRoute(), router=useRouter(), live=useClassroom();
const {room, capabilities, events, error, state, partial, students, activeStudent, raised, mouth,
  pose, reply, playbackStudent, landmarks, motionStatus, handStatus, faceStatus, cameraEnabled,
  retryMotion, camera, elapsed, cloudVision, busy, send, refreshCapabilities, begin, reconnect,
  finish, load, regenerate, setVision, volume, setVolume, cameraResolution, cameraAdjusting,
  cameraNote, setCameraResolution, previewCamera, pauseCapture, capabilitiesLoading, capabilitiesError} = live;
const mode=ref("full"), consent=ref(false), cameraConsent=ref(false), history=ref([]), probing=ref("");
const showHistory=ref(false), timelineOpen=ref(false), timelineRef=ref(null), cameraRef=ref(null);
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
  '已就绪。可先预览摄像头，也可直接点击开始授课；浏览器仍需允许设备权限。');
const needsSettings=computed(()=>startBlockers.value.some(r=>r.action==='settings'));
const remaining=computed(()=>Math.max(0,((room.value?.mode || mode.value)==="fragment" ? 480 : 600)-elapsed.value));
const finishWait=computed(()=>Math.max(0,Math.ceil(10-elapsed.value)));
const stateLabel=computed(()=>({
  idle:"准备课堂",connecting:"正在开启设备与语音服务",listening:"正在听老师讲课",
  speaking:"学生正在发言",disconnected:"采集已暂停",finishing:"正在结束课堂…",ended:"课堂已结束"
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
onBeforeRouteLeave(()=>!active.value || window.confirm("离开会停止麦克风和摄像头采集，记录保留。确定离开吗？"));
</script>

<template>
  <div class="classroom-page camera-first">
    <header class="classroom-heading">
      <div><h1>模拟课堂<span class="heading-dot" aria-hidden="true">.</span></h1><p>小学数学 · 分数的初步认识</p></div>
      <nav class="classroom-window-actions" aria-label="课堂窗口">
        <button class="class-btn secondary" :disabled="active || busy" aria-haspopup="dialog" :aria-expanded="showHistory" @click="showHistory=true;refreshHistory()">历史课堂</button>
      </nav>
    </header>
    <p v-if="error" class="class-alert" role="alert">{{ error }}<button aria-label="关闭提示" @click="error=''">×</button></p>
    <div v-if="quotaNotice || connectionIssue" class="class-notice" role="status">
      <span>{{ quotaNotice || "部分服务待处理，请检查连接设置。" }}</span>
      <button class="text-action" @click="openSettings">查看设置 ↗</button>
    </div>
    <section class="classroom-launch" aria-label="授课申请">
      <div v-if="state!=='ended'" class="launch-permissions">
        <span class="launch-label">授课申请</span>
        <div class="consent-row">
          <label><input type="checkbox" v-model="consent" :disabled="active || busy" />同意语音识别与 AI 评课</label>
          <label><input type="checkbox" v-model="cameraConsent" :disabled="active || busy" />同意摄像头开启</label>
          <details class="disclosure privacy-details">
            <summary>数据使用说明</summary>
            <p>麦克风音频上传{{ speechProviderLabel(asrProvider) }}识别；文字与本地动作摘要提交{{ llmLabel }}用于对话和评课。原始录音不保存，转写与课堂事件会保留。</p>
            <p>摄像头为授课必需条件，仍须浏览器授权。身体、手势和面部检测在本机运行，不做人脸识别或心理推断。云端截图分析默认关闭，需在课堂设置另行授权。</p>
            <p>随时可暂停设备采集；至少授课 10 秒才能结束评课。报告需有 2 段且 80 字最终转写、1 次完整播放且不少于 10 字的学生反馈，以及至少 3 个有效动作和教师入镜样本、跨度 4 秒。不足时不调用评审 AI。</p>
          </details>
        </div>
        <p v-if="room && state!=='disconnected'" class="subtle-note">{{ finishWait ? '至少再授课 '+finishWait+' 秒才能结束评课；设备采集可随时暂停。' : '已满 10 秒，可结束；是否生成报告取决于实际证据量。' }}</p>
      </div>
      <div class="class-controls">
        <template v-if="!room">
          <label for="class-mode" class="sr-only">训练时长</label>
          <select id="class-mode" v-model="mode" :disabled="busy"><option value="full">10 分钟完整课堂</option><option value="fragment">8 分钟专项训练</option></select>
          <button class="class-btn" :disabled="startBlockers.length>0" :title="startHint" aria-describedby="class-start-hint" @click="start">{{ busy ? "准备中…" : "开始授课" }} <span aria-hidden="true">→</span></button>
        </template>
        <template v-else-if="state!=='ended'">
          <button v-if="state==='disconnected'" class="class-btn secondary" :disabled="startBlockers.length>0" :title="startHint" aria-describedby="class-start-hint" @click="resume">重新连接</button>
          <button class="class-btn" :disabled="busy || state==='finishing' || finishWait>0" @click="finish">{{ state==="finishing" ? "结束处理中…" : "结束并评课" }}</button>
        </template>
        <button v-else class="class-btn" @click="router.push('/classroom').then(()=>router.go(0))">开始下一节 →</button>
      </div>
      <div v-if="!room || state==='disconnected'" class="class-start-feedback" :class="{blocked:startBlockers.length}">
        <div id="class-start-hint" role="status" aria-live="polite" aria-atomic="true">
          <template v-if="startBlockers.length">
            <strong>{{ busy || capabilitiesLoading ? '正在准备，暂不可'+(room ? '重新连接' : '开始授课') : '暂不可'+(room ? '重新连接' : '开始授课')+'，请处理以下事项：' }}</strong>
            <ul><li v-for="reason in startBlockers" :key="reason.code">{{ reason.message }}</li></ul>
          </template>
          <p v-else>{{ startHint }}</p>
        </div>
        <div v-if="startBlockers.length" class="start-feedback-actions">
          <button type="button" class="text-action" :disabled="capabilitiesLoading || busy" @click="refreshCapabilities">{{ capabilitiesLoading ? '正在读取状态…' : '重新读取状态' }}</button>
          <button v-if="needsSettings" type="button" class="text-action" @click="openSettings">查看配置与额度</button>
        </div>
      </div>
    </section>
    <section class="class-panel camera-stage" aria-label="授课主画面">
      <ClassroomCamera ref="cameraRef" :enabled="cameraEnabled" :disabled="state==='ended'" :landmarks="landmarks"
        :camera-consent="cameraConsent" :camera-busy="busy" :preview-allowed="!active"
        :motion="pose" :face-status="faceStatus" :motion-status="motionStatus" :hand-status="handStatus"
        :teacher-text="partial || latestTeacher" :reply="reply" :volume="volume" :resolution="cameraResolution"
        :resolution-busy="cameraAdjusting || busy" :camera-note="cameraNote"
        @volume="setVolume" @resolution="setCameraResolution" @video="camera=$event" @retry="retryMotion" @toggle="previewCamera(cameraConsent)">
        <template #heading><span class="connection-label" :class="state"><i aria-hidden="true" />{{ stateLabel }}</span><p class="scene-topic">一块蛋糕，怎样公平地分享？</p></template>
        <template #timer><ClassroomCountdown :seconds="remaining" /></template>
        <template #students>
          <StudentAvatar v-for="s in students.length ? students : defaultStudents" :key="(room?.session_id || 'new')+'-'+s.id"
            compact :student="s" :raised="raised===s.id" :speaking="playbackStudent===s.id"
            :reply="reply.studentId===s.id ? reply : null" :level="mouth" @select="selectStudent" />
        </template>
        <template #actions>
          <button class="text-action" aria-haspopup="dialog" :aria-expanded="timelineOpen" @click="timelineOpen=true">课堂记录</button>
          <span v-if="!reply.studentId && reply.phase==='thinking'" class="thinking-notice" role="status">学生正在思考…</span>
          <button v-if="reply.phase==='failed' && !reply.replyId" class="text-action" :disabled="state!=='listening'" @click="send('retry_generation')">重试学生回答</button>
          <button v-if="activeStudent || ['thinking','generating','queued'].includes(reply.phase)" class="text-action" @click="send('cancel')">打断学生</button>
          <button v-if="cameraEnabled" class="text-action" :disabled="busy || state==='finishing'" @click="pauseCapture()">{{ active ? '暂停设备采集' : '关闭摄像头预览' }}</button>
        </template>
        <template #settings>
          <div class="vision-option">
            <label><input type="checkbox" v-model="cloudVision" :disabled="state==='ended' || busy" @change="setVision" />云端画面分析</label>
            <p class="subtle-note">默认关闭。开启后最多每 15 秒上传 1 张截图，每课最多 40 张，消耗视觉额度并私有保存用于证据核对。启用后还需至少 1 条有效画面观察才生成报告。关闭时只检查本地教师入镜，不识别课堂背景语义。</p>
          </div>
          <ClassroomSettings :capabilities="capabilities" :probing="probing" :active="active" @probe="probe" @refresh="refreshCapabilities" />
        </template>
        <template #windows><ClassroomDialog v-model="timelineOpen" title="课堂记录"><ClassroomTimeline ref="timelineRef" :events="events" /></ClassroomDialog></template>
      </ClassroomCamera>
    </section>
    <div class="classroom-services" aria-label="课堂连接状态">
      <span v-for="group in statusGroups" :key="group.key" class="status-item" :class="group.tone"><i aria-hidden="true" />{{ group.title }} <b>{{ group.label }}</b></span>
      <span>学生发言结束后，问题气泡保留 15 秒；完整内容可在课堂记录查看。</span>
    </div>
    <ClassroomReport v-if="room?.state==='ended'" :room="room" :busy="busy" @regenerate="regenerate" @jump="jumpEvidence" />
    <ClassroomDialog v-model="showHistory" title="历史课堂">
      <div class="history-panel">
        <p v-if="!history.length" class="empty-state">暂无课堂记录</p>
        <router-link v-for="item in history" :key="item.session_id" :to="{path:'/classroom',query:{session:item.session_id}}" @click="openSession(item.session_id)">
          <span>{{ item.topic }}<small>{{ new Date(item.created_at+"Z").toLocaleString() }}</small></span>
          <b>{{ item.state==="active" ? "可继续" : {completed:"查看报告",failed:"待重试",running:"评课中",idle:"待评课",insufficient:"数据不足"}[item.report_state] }}</b>
        </router-link>
      </div>
    </ClassroomDialog>
  </div>
</template>
