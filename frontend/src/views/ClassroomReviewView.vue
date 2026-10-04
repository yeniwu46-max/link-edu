<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Refresh, Printer, ArrowUpRight, History } from '@vicons/tabler';
import { api } from '../services/api';
import { classroomDestination, formatReportDate, formatReportTime } from '../services/classroomReview.js';
import ClassroomReport from '../components/ClassroomReport.vue';
import '../classroom.css';
import '../classroom-review.css';
const route=useRoute(), router=useRouter();
const room=ref(null), history=ref([]), loading=ref(true), busy=ref(false), error=ref(''), historyError=ref('');
let disposed=false, controller=null, pollTimer=null, requestId=0;
const stateLabel=state=>({completed:'已评课',running:'评课中',insufficient:'数据不足',failed:'生成失败',idle:'待评课'}[state]||'待评课');
const endedHistory=computed(()=>history.value.filter(item=>item.state==='ended'));
const selectedId=computed(()=>String(room.value?.session_id||route.query.classroom||''));
function selectHistory(event){router.push({path:'/ai-review',query:{classroom:event.target.value}});}
function schedulePoll(){
  clearTimeout(pollTimer);
  if (!disposed && room.value?.report_state==='running') pollTimer=setTimeout(()=>{
    if (document.visibilityState==='hidden') schedulePoll();
    else loadRoom(room.value.session_id);
  },4000);
}
async function loadRoom(id){
  const current=++requestId;
  controller?.abort(); controller=new AbortController();
  try {
    const {data}=await api.get(`/classroom/sessions/${id}`,{timeout:15000,skipBusy:true,signal:controller.signal});
    if(disposed || current!==requestId)return;
    room.value=data;error.value='';
  } catch(e){
    if(disposed || current!==requestId)return;
    error.value=e.response?.status===404 ? '这节课堂不存在，或你没有查看权限。请选择其他课堂。' :
      e.response?.status===401 ? '登录已失效，请重新登录后查看报告。' : '报告读取失败，暂未取得最新结果。请重试。';
  } finally {if(!disposed && current===requestId){loading.value=false;schedulePoll();}}
}
async function initialize(){
  loading.value=true; error.value=''; historyError.value='';
  const id=route.query.classroom;
  if(id!==undefined && (typeof id!=='string' || !/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id)))){
    error.value='课堂编号无效，请从历史课堂重新进入。';loading.value=false;return;
  }
  const historyPromise=api.get('/classroom/sessions',{timeout:15000,skipBusy:true}).then(({data})=>{
    if(!disposed)history.value=data.items||[];
  }).catch(()=>{if(!disposed)historyError.value='历史列表读取失败，可刷新重试。';});
  if(id){await Promise.all([historyPromise,loadRoom(id)]);return;}
  await historyPromise;
  if(disposed)return;
  if(endedHistory.value.length){
    await router.replace(classroomDestination(endedHistory.value[0]));
  }else loading.value=false;
}
async function regenerate(objection){
  if(busy.value || !room.value || room.value.report_state==='running' ||
    (room.value.report_state==='insufficient' && !room.value.report_readiness?.eligible))return;
  busy.value=true;error.value='';
  try {
    const {data}=await api.post(`/classroom/sessions/${room.value.session_id}/report`,{objection},{timeout:20000,skipBusy:true});
    if(disposed)return;
    room.value={...room.value,...data};
    await loadRoom(room.value.session_id);
  } catch(e){if(!disposed)error.value=e.response?.data?.message||'评课请求未确认，请刷新状态后再决定是否重试。';}
  finally {if(!disposed)busy.value=false;}
}
function printReport(){window.print();}
let printFolds=[];
function preparePrint(){
  printFolds=[...document.querySelectorAll('.classroom-review-page .report-fold:not([open])')];
  printFolds.forEach(fold=>{fold.open=true;});
}
function restorePrint(){printFolds.forEach(fold=>{fold.open=false;});printFolds=[];}
onMounted(initialize);
onMounted(()=>{window.addEventListener('beforeprint',preparePrint);window.addEventListener('afterprint',restorePrint);});
onBeforeUnmount(()=>{disposed=true;requestId++;controller?.abort();clearTimeout(pollTimer);window.removeEventListener('beforeprint',preparePrint);window.removeEventListener('afterprint',restorePrint);});
</script>
<template>
  <div class="classroom-review-page">
    <header class="review-masthead">
      <div><p class="review-eyebrow">LINK / TEACHING REVIEW</p><h1>AI 评课<span>.</span></h1><p>把一节课，读成下一次进步的线索。</p></div>
      <div class="review-page-actions no-print">
        <router-link class="review-button" to="/classroom">模拟课堂<ArrowUpRight aria-hidden="true" /></router-link>
        <button class="review-button" :disabled="loading || busy" @click="initialize"><Refresh aria-hidden="true" />刷新</button>
        <button v-if="room?.report && room.report_state!=='insufficient'" class="review-button" @click="printReport"><Printer aria-hidden="true" />打印 / PDF</button>
      </div>
    </header>
    <div class="review-session-switch no-print">
      <label for="review-session"><History aria-hidden="true" />历史课堂</label>
      <select id="review-session" :value="selectedId" :disabled="busy || loading || !endedHistory.length" @change="selectHistory">
        <option v-if="!endedHistory.some(item=>String(item.session_id)===selectedId)" :value="selectedId">{{ selectedId ? '课堂 #'+selectedId : '选择已结束的课堂' }}</option>
        <option v-for="item in endedHistory" :key="item.session_id" :value="String(item.session_id)">{{ formatReportDate(item.created_at) }} · {{ item.topic }} · {{ stateLabel(item.report_state) }}</option>
      </select>
      <router-link to="/ai-review?legacy=1">旧训练记录 ↗</router-link>
    </div>
    <p v-if="historyError" class="review-inline-alert" role="alert">{{ historyError }}</p>
    <div v-if="error" class="review-inline-alert" role="alert">{{ error }}<button class="review-button" :disabled="loading || busy" @click="initialize">重新读取</button><router-link to="/">重新登录</router-link></div>
    <section v-if="loading && !room" class="review-empty-state" role="status"><span class="review-loading-line" />正在读取课堂证据…</section>
    <section v-else-if="!room && !error && !historyError" class="review-empty-state"><h2>你的第一份评课，等待一节真实课堂</h2><p>完成授课后，AI 结论与课堂证据会一起保存在这里。</p><router-link class="review-button primary" to="/classroom">进入模拟课堂<ArrowUpRight aria-hidden="true" /></router-link></section>
    <template v-if="room">
      <div class="review-session-meta"><span>课堂 #{{ room.session_id }} · {{ room.topic }}</span><span>{{ formatReportDate(room.created_at) }} · {{ formatReportTime(Number.isFinite(room.elapsed)?room.elapsed*1000:NaN) }}</span></div>
      <section v-if="['active','paused'].includes(room.state)" class="review-empty-state"><h2>这节课堂还未结束</h2><p>此处不会提前生成评分。</p><router-link class="review-button" :to="classroomDestination(room)">返回课堂</router-link></section>
      <ClassroomReport v-else :room="room" :busy="busy" @regenerate="regenerate" @plans-created="loadRoom(room.session_id)" />
    </template>
  </div>
</template>
