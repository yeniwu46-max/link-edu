import { ref, watch, onBeforeUnmount } from 'vue';
import { ClassroomRecorder } from './classroomRecorder.js';
import { createClassroomPainter } from './classroomCompositor.js';
import { saveClassroomRecording } from './classroomRecordingStore.js';

export function useClassroomRecording({state, room, getUserId, snapshot, wallMs, audioStream}) {
  const enabled=ref(false), phase=ref('idle'), result=ref(null), previewOpen=ref(false),
    error=ref(''), saved=ref(false), saving=ref(false), url=ref('');
  let recorder, starting=false, owner, disposed=false;
  function releaseUrl(){if(url.value)URL.revokeObjectURL(url.value);url.value='';}
  watch(state, async value=>{
    if (['paused','disconnected','connecting'].includes(value)) recorder?.pause();
    if (['finishing','ended'].includes(value)) recorder?.stop();
    if (!['listening','speaking'].includes(value) || !enabled.value || starting || disposed) return;
    if (recorder) {
      try {await recorder.resume();} catch {error.value='录像恢复失败，课堂可继续。';recorder.stop();}
      return;
    }
    starting=true; error.value='';
    owner={origin:location.origin,userId:getUserId(),sessionId:room.value.session_id};
    const current=recorder=new ClassroomRecorder({paint:createClassroomPainter(snapshot),getWallMs:wallMs,
      getAudioStream:audioStream,onState:value=>{phase.value=value;},onError:value=>{error.value=value;},
      onResult:value=>{if(disposed)return;result.value=value;releaseUrl();url.value=URL.createObjectURL(value.blob);previewOpen.value=true;}});
    try {
      await current.start();
      if(disposed)current.dispose();
      else if (!['listening','speaking'].includes(state.value)) {
        if(['finishing','ended'].includes(state.value))current.stop(); else current.pause();
      }
    } catch(e){error.value=e.message;current.dispose();phase.value='failed';}
    finally {starting=false;}
  });
  async function save() {
    if (!result.value || saving.value) return;
    if (getUserId()!==owner.userId) {error.value='登录用户已改变，不能保存到其他账户。';return;}
    saving.value=true;error.value='';
    try {
      const {blob,...meta}=result.value;
      await saveClassroomRecording(owner.origin,owner.userId,owner.sessionId,blob,meta);
      saved.value=true;
    } catch(e){error.value=e.name==='QuotaExceededError'?'浏览器存储空间不足，请下载视频或清理旧录像。':e.message;}
    finally {saving.value=false;}
  }
  function download() {
    if(!url.value)return;
    const a=document.createElement('a');a.href=url.value;a.download=result.value.filename;a.click();
  }
  function discard() {
    if(result.value && !saved.value && !window.confirm('放弃这段未保存录像？此操作无法恢复。'))return;
    releaseUrl();result.value=null;previewOpen.value=false;
  }
  const hasUnsaved=()=>Boolean((recorder && !['preview','failed'].includes(phase.value)) || (result.value && !saved.value));
  watch(getUserId,id=>{
    if(owner && id!==owner.userId){recorder?.dispose();releaseUrl();result.value=null;previewOpen.value=false;
      phase.value='failed';enabled.value=false;error.value='登录状态已改变，未保存录像已释放。';}
  });
  function beforeUnload(event){if(hasUnsaved()){event.preventDefault();event.returnValue='';}}
  window.addEventListener('beforeunload',beforeUnload);
  onBeforeUnmount(()=>{disposed=true;recorder?.dispose();releaseUrl();window.removeEventListener('beforeunload',beforeUnload);});
  return {enabled,phase,result,previewOpen,error,saved,saving,url,save,download,discard,hasUnsaved,
    pause:()=>recorder?.pause(),stop:()=>recorder?.stop()};
}
