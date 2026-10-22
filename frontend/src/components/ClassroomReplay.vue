<script setup>
import {ref,watch,onBeforeUnmount,nextTick,computed} from 'vue';
import {useAuthStore} from '../stores/auth';
import {getClassroomRecording,listClassroomRecordings,deleteClassroomRecording,recordingTime} from '../services/classroomRecordingStore.js';
const props=defineProps({room:Object,event:Object});
const auth=useAuthStore(),video=ref(null),url=ref(''),record=ref(null),error=ref(''),notice=ref(''),loading=ref(false),items=ref([]),videoDuration=ref(0);
let revision=0;
const isDemo=computed(()=>props.room?.report?.demo===true);
const duration=computed(()=>videoDuration.value||record.value?.durationMs||props.room?.elapsed*1000||0);
const markers=computed(()=>{
  const span=duration.value;
  if(!span)return [];
  const events=(props.room?.events||[]).filter(e=>isDemo.value || (Number.isFinite(e.at_ms)&&e.at_ms>=0&&e.at_ms<=span)).slice(0,24);
  return events.map((e,index)=>{
    const at=isDemo.value ? (events.length===1 ? span/2 : span*index/(events.length-1)) : e.at_ms;
    return {id:e.id,at,left:`${Math.max(0,Math.min(100,at/span*100))}%`,label:`${Math.floor(at/60000)}:${String(Math.floor(at/1000)%60).padStart(2,'0')}`};
  });
});
function release(){video.value?.pause();if(url.value && !isDemo.value)URL.revokeObjectURL(url.value);url.value='';record.value=null;videoDuration.value=0;}
async function load(){
  const id=++revision;release();error.value='';items.value=[];
  if(!auth.user?.id || !props.room?.session_id)return;
  if(isDemo.value){
    record.value={demo:true,filename:'LINK-模拟课堂回放.mp4',byteLength:0,durationMs:18000,segments:[{wallStart:0,wallEnd:18000,videoStart:0}],mimeType:'video/mp4'};
    url.value='/assets/mock-classroom.mp4';
    await nextTick();seek();
    return;
  }
  loading.value=true;
  try {
    const [row,list]=await Promise.all([getClassroomRecording(location.origin,auth.user.id,props.room.session_id),listClassroomRecordings(location.origin,auth.user.id)]);
    if(id!==revision)return;
    record.value=row;items.value=list;if(row)url.value=URL.createObjectURL(row.blob);
    await nextTick();seek();
  } catch {if(id===revision)error.value='本机录像读取失败，可重试；报告仍可查看。';}
  finally{if(id===revision)loading.value=false;}
}
function seek(){
  notice.value='';
  if(!record.value || !props.event)return;
  const at=recordingTime(record.value.segments,props.event.at_ms);
  if(at===null){video.value?.pause();notice.value='该时段无录像，请查看下方原始事件。';return;}
  if(video.value?.readyState>=1){video.value.currentTime=at;video.value.play().catch(()=>{notice.value='已定位，点击播放查看。';});}
}
function jump(at){
  const player=video.value;
  if(!player)return;
  const target=Math.max(0,Number(at)/1000);
  player.pause();
  player.currentTime=target;
  player.play().catch(()=>{notice.value=`已跳转到 ${Math.floor(target/60)}:${String(Math.floor(target%60)).padStart(2,'0')}，点击播放器继续播放。`;});
}
function handleMetadata(){
  if(video.value){
    video.value.playbackRate=1;
    if(Number.isFinite(video.value.duration)&&video.value.duration>0)videoDuration.value=video.value.duration*1000;
  }
  seek();
}
async function remove(item){
  if(!window.confirm('删除这节课的本机录像？无法恢复；已下载副本不会被删除。'))return;
  try{await deleteClassroomRecording(location.origin,auth.user.id,item.sessionId);await load();}
  catch{error.value='删除失败，请重试。';}
}
function download(){if(!record.value)return;const a=document.createElement('a');a.href=url.value;a.download=record.value.filename;a.click();}
watch(()=>[props.room?.session_id,auth.user?.id],load,{immediate:true});
watch(()=>props.event,seek);
onBeforeUnmount(()=>{revision++;release();});
</script>
<template>
  <section class="classroom-replay no-print" aria-label="本机课堂录像">
    <p v-if="loading" role="status">正在读取本机录像…</p>
    <div v-if="url" class="replay-video-shell">
      <video ref="video" :src="url" controls controlsList="nodownload noplaybackrate" disablePictureInPicture playsinline preload="metadata" aria-label="课堂证据录像" @loadedmetadata="handleMetadata" @play="video.playbackRate=1" @ratechange="video.playbackRate=1" @error="error='此录像格式无法在当前浏览器播放，可下载后查看。'" />
    </div>
    <div v-if="url && markers.length" class="replay-timeline" aria-label="课堂事件进度条">
      <div class="replay-track"><i /></div>
      <button v-for="marker in markers" :key="marker.id" type="button" class="replay-marker" :style="{left:marker.left}" :title="`${marker.label} · 课堂事件 #${marker.id}`" :aria-label="`跳转到 ${marker.label}，课堂事件 ${marker.id}`" @click.stop.prevent="jump(marker.at)" />
    </div>
    <p v-else-if="!loading">当前浏览器没有本节录像。换设备或清理浏览器数据后，录像不会自动恢复。</p>
    <p v-if="notice" role="status">{{notice}}</p><p v-if="error" role="alert">{{error}} <button @click="load">重试</button></p>
    <button v-if="record && !record.demo" @click="download">下载本节录像 · {{(record.byteLength/1024/1024).toFixed(1)}} MiB</button>
    <details v-if="!record?.demo"><summary>管理本机录像（{{items.length}}）</summary><p>仅当前站点、当前账户可见。删除仅影响浏览器内副本，不删除已下载文件。</p>
      <ul><li v-for="item in items" :key="item.key">课堂 #{{item.sessionId}} · {{(item.byteLength/1024/1024).toFixed(1)}} MiB <button @click="remove(item)">删除</button></li></ul>
    </details>
  </section>
</template>
<style scoped>
.replay-video-shell{position:relative}.replay-video-shell video{display:block;width:100%;max-height:45vh;background:transparent;border-radius:8px}.replay-timeline{position:relative;height:22px;margin:8px 12px 14px}.replay-track{position:absolute;left:0;right:0;top:8px;height:4px;border-radius:4px;background:#3a3e46}.replay-track i{display:block;width:100%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#ffad6a,#a66cff)}.replay-marker{position:absolute;top:4px;width:11px;height:11px;padding:0;transform:translateX(-50%);border:2px solid #17191d;background:#ffad6a;border-radius:50%;box-shadow:0 0 0 1px #ffad6a;cursor:pointer}.replay-marker:hover{transform:translateX(-50%) scale(1.35);background:#fff}.classroom-replay{margin-bottom:1rem}button{color:inherit;background:transparent;border:1px solid var(--line);padding:.5rem .75rem;border-radius:8px;cursor:pointer}li{margin:.5rem 0}summary{cursor:pointer;margin:1rem 0}
</style>
