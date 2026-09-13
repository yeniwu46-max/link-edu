import { MAX_RECORDING_BYTES } from './classroomRecordingStore.js';

// Wait for real audio frames before starting the canvas clock. A newly created
// Web Audio destination can otherwise begin encoding much later than video.
async function audioReady(stream, context) {
  const track=stream.getAudioTracks()[0];
  if (typeof MediaStreamTrackProcessor === 'function') {
    let clone,reader,timer;
    try {
      clone=track.clone();reader=new MediaStreamTrackProcessor({track:clone}).readable.getReader();
      const frame=await Promise.race([reader.read(),new Promise((_,reject)=>{
        timer=setTimeout(()=>reject(new Error('录像音轨准备超时；课堂可继续。')),3000);
      })]);
      if(!frame.value)throw new Error('录像音轨已关闭；课堂可继续。');
      frame.value.close();return;
    } catch(e) {
      // Some browsers expose a video-only processor. Fall back to the audio clock.
      if(e.name!=='TypeError')throw e;
    } finally {clearTimeout(timer);reader?.cancel().catch(()=>{});clone?.stop();}
  }
  const began=performance.now(),clock=context.currentTime;
  while(context.currentTime-clock<.25) {
    if(performance.now()-began>3000)throw new Error('录像音频时钟未就绪；课堂可继续。');
    await new Promise(resolve=>setTimeout(resolve,25));
  }
}

export function recordingMime() {
  if (typeof MediaRecorder === 'undefined') return '';
  return ['video/webm;codecs=vp8,opus','video/webm','video/mp4'].find(t=>MediaRecorder.isTypeSupported(t)) || '';
}

/** Owns only compositor/mixer resources. Classroom owns camera and microphone. */
export class ClassroomRecorder {
  constructor({paint, getWallMs, getAudioStream, onResult, onError, onState}) {
    Object.assign(this,{paint,getWallMs,getAudioStream,onResult,onError,onState});
    this.chunks=[]; this.segments=[]; this.bytes=0; this.videoMs=0;
  }
  async start() {
    const mimeType=recordingMime();
    if (!mimeType || !HTMLCanvasElement.prototype.captureStream) throw new Error('当前浏览器不支持课堂录像；可继续正常授课。');
    this.canvas=document.createElement('canvas'); this.canvas.width=1280; this.canvas.height=720;
    this.ctx=this.canvas.getContext('2d');
    this.mixer=new AudioContext(); await this.mixer.resume();
    this.destination=this.mixer.createMediaStreamDestination();
    await this.attachAudio();
    await audioReady(this.destination.stream,this.mixer);
    if(this.stopping)return;
    this.video=this.canvas.captureStream(24);
    this.stream=new MediaStream([...this.video.getVideoTracks(),...this.destination.stream.getAudioTracks()]);
    this.recorder=new MediaRecorder(this.stream,{mimeType,videoBitsPerSecond:2_500_000,audioBitsPerSecond:128_000});
    this.recorder.ondataavailable=({data})=>{
      if (!data?.size) return;
      this.chunks.push(data); this.bytes+=data.size;
      // Reserve room for the final chunk; never discard an encoded tail.
      if (this.bytes >= MAX_RECORDING_BYTES - 4*1024*1024 && !this.stopping) {
        this.onError('录像已达到单节容量上限，录制停止；课堂继续。'); this.stop();
      }
    };
    this.recorder.onerror=()=>{this.onError('录像中断，可预览已取得的片段；课堂不受影响。'); this.stop();};
    this.recorder.onstop=()=>this.finalize();
    this.draw(); if(this.stopping)return;
    this.recorder.start(1000); this.openSegment();
    this.timer=setInterval(()=>this.draw(),1000/24); this.onState('recording');
  }
  async attachAudio() {
    this.source?.disconnect();
    const stream=this.getAudioStream();
    if (!stream?.getAudioTracks().some(t=>t.readyState==='live')) throw new Error('无法取得师生混音，录像未开始；课堂可继续。');
    await audioReady(stream,this.mixer);
    if(this.stopping)return;
    this.source=this.mixer.createMediaStreamSource(stream); this.source.connect(this.destination);
  }
  draw() {
    if (this.stopping) return;
    try {this.paint(this.ctx,this.canvas);} catch {this.onError('录像合成失败，已停止录制；课堂可继续。'); this.stop();}
  }
  openSegment() {this.segment={wallStart:this.getWallMs(),videoStart:this.videoMs}; this.segmentAt=performance.now();}
  closeSegment() {
    if (!this.segment) return;
    const duration=Math.max(0,performance.now()-this.segmentAt);
    this.segments.push({...this.segment,wallEnd:this.segment.wallStart+duration});
    this.videoMs+=duration; this.segment=null;
  }
  pause() {
    if (this.recorder?.state!=='recording' || this.stopping) return;
    this.closeSegment(); this.recorder.pause(); clearInterval(this.timer);
    this.source?.disconnect(); this.onState('paused');
  }
  async resume() {
    if (this.recorder?.state!=='paused' || this.stopping) return;
    await this.mixer.resume(); await this.attachAudio();
    if(this.stopping)return;
    this.draw();
    if(this.stopping)return;
    this.recorder.resume(); this.openSegment(); this.timer=setInterval(()=>this.draw(),1000/24);
    this.onState('recording');
  }
  stop() {
    if (this.stopping) return;
    this.stopping=true; this.closeSegment(); clearInterval(this.timer);
    if (this.recorder && this.recorder.state!=='inactive') this.recorder.stop();
    else this.finalize();
  }
  finalize() {
    if (this.finalized) return; this.finalized=true;
    const blob=new Blob(this.chunks,{type:this.recorder?.mimeType || 'video/webm'});
    this.chunks=[]; this.release(); this.onState('preview');
    if (blob.size) this.onResult({blob,segments:this.segments,durationMs:this.videoMs,
      filename:`LINK-课堂-${new Date().toISOString().replace(/[:.]/g,'-')}.${blob.type.includes('mp4')?'mp4':'webm'}`});
    else this.onError('没有取得有效录像，课堂文字记录不受影响。');
  }
  release() {
    clearInterval(this.timer); this.source?.disconnect();
    this.stream?.getTracks().forEach(t=>t.stop()); this.mixer?.close().catch(()=>{});
    this.video?.getTracks().forEach(t=>t.stop());
    this.destination?.stream.getTracks().forEach(t=>t.stop());
  }
  dispose() {
    this.onResult=()=>{}; this.onState=()=>{}; this.stop(); this.release();
  }
}
