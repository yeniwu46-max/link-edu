<script setup>
import {ref,watch,onBeforeUnmount,nextTick} from 'vue';
import {useAuthStore} from '../stores/auth';
import {getClassroomRecording,listClassroomRecordings,deleteClassroomRecording,recordingTime} from '../services/classroomRecordingStore.js';
const props=defineProps({room:Object,event:Object});
const auth=useAuthStore(),video=ref(null),url=ref(''),record=ref(null),error=ref(''),notice=ref(''),loading=ref(false),items=ref([]);
let revision=0;
function release(){video.value?.pause();if(url.value)URL.revokeObjectURL(url.value);url.value='';record.value=null;}
async function load(){
  const id=++revision;release();error.value='';items.value=[];
  if(!auth.user?.id || !props.room?.session_id)return;
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
    <video v-if="url" ref="video" :src="url" controls playsinline preload="metadata" aria-label="课堂证据录像" @loadedmetadata="seek" @error="error='此录像格式无法在当前浏览器播放，可下载后查看。'" />
    <p v-else-if="!loading">当前浏览器没有本节录像。换设备或清理浏览器数据后，录像不会自动恢复。</p>
    <p v-if="notice" role="status">{{notice}}</p><p v-if="error" role="alert">{{error}} <button @click="load">重试</button></p>
    <button v-if="record" @click="download">下载本节录像 · {{(record.byteLength/1024/1024).toFixed(1)}} MiB</button>
    <details><summary>管理本机录像（{{items.length}}）</summary><p>仅当前站点、当前账户可见。删除仅影响浏览器内副本，不删除已下载文件。</p>
      <ul><li v-for="item in items" :key="item.key">课堂 #{{item.sessionId}} · {{(item.byteLength/1024/1024).toFixed(1)}} MiB <button @click="remove(item)">删除</button></li></ul>
    </details>
  </section>
</template>
<style scoped>
video{display:block;width:100%;max-height:45vh;background:#000;border-radius:8px}.classroom-replay{margin-bottom:1rem}button{color:inherit;background:transparent;border:1px solid var(--line);padding:.5rem .75rem;border-radius:8px;cursor:pointer}li{margin:.5rem 0}summary{cursor:pointer;margin:1rem 0}
</style>
