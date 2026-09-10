import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

// Bundle only local production logic; replace external browser/API boundaries.
const compiled = await build({entryPoints:[fileURLToPath(new URL('../src/services/useClassroom.js',import.meta.url))],
  bundle:true,write:false,format:'cjs',platform:'node',logLevel:'silent',external:['vue'],
  define:{'import.meta.url':JSON.stringify(new URL('../src/services/useClassroom.js',import.meta.url).href)},
  plugins:[{name:'local-api-boundary',setup(b){b.onResolve({filter:/^\.\/api$/},()=>({path:'test-api',external:true}));}}]});

function fixture(t, denied=false, cameraDenied=false) {
  const contexts=[], tracks=[], posts=[], unmount=[], sockets=[], audioNodes=[], timers=new Map();
  let timerId=0;
  const api={post:async(path)=>{posts.push(path); return {data:path.endsWith('/ticket')?{ticket:'synthetic'}:{session_id:1}};},
    get:async()=>({data:{session_id:1,state:'active',events:[],elapsed:0}})};
  class AudioContext {
    constructor(){contexts.push(this); this.destination={}; this.currentTime=0; this.audioWorklet={addModule:async()=>{}};}
    async resume(){} async close(){this.closed=true;}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    createAnalyser(){return {connect(){},getByteTimeDomainData(a){a.fill(128);}};}
    createGain(){return {gain:{value:1,setTargetAtTime(){}},connect(){}};}
    createBuffer(channels,length,rate){return {duration:length/rate,getChannelData:()=>new Float32Array(length)};}
    createBufferSource(){const node={playbackRate:{value:1},connect(target){this.target=target;},disconnect(){},start(at){this.at=at;},stop(){}};audioNodes.push(node);return node;}
  }
  class Socket {static OPEN=1; constructor(){this.readyState=1;this.bufferedAmount=0;this.sent=[];sockets.push(this);} send(m){this.sent.push(JSON.parse(m));} close(){this.readyState=3;this.onclose?.();}}
  const module={exports:{}};
  const workers=[];
  const scope={module,exports:module.exports,AudioContext,WebSocket:Socket,performance,console,Uint8Array,URL,atob,btoa,
    Worker:class {constructor(){workers.push(this);}postMessage(){this.onmessage?.({data:{type:'ready'}});}terminate(){this.terminated=true;}},
    crypto:{randomUUID:()=>String(Math.random())},location:{protocol:'http:',host:'localhost'},
    navigator:{mediaDevices:{getUserMedia:async(options)=>{if(denied || (cameraDenied && options.video))throw new Error('NotAllowedError');
      const track={stop(){this.stopped=true;},settings:{width:1280,height:720},getSettings(){return this.settings;},
        async applyConstraints(c){this.settings={width:c.width.ideal,height:c.height.ideal};}};
      tracks.push(track);return {getTracks:()=>[track],getVideoTracks:()=>options.video?[track]:[]};}}},
    AudioWorkletNode:class {constructor(){this.port={};}connect(){}disconnect(){}},
    setInterval:()=>1,clearInterval(){},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
    require:(name)=>name==='vue'?{ref:(value)=>({value}),onUnmounted:fn=>unmount.push(fn)}:{api},
  };
  vm.runInNewContext(compiled.outputFiles[0].text,scope);
  const live=module.exports.useClassroom();
  live.camera.value={srcObject:null,play:async()=>{},videoWidth:640};
  return {live,api,contexts,tracks,posts,unmount,workers,sockets,audioNodes,timers};
}

test('capability refresh is bounded, non-blocking, deduplicated and clears a failed read on retry',async t=>{
  const f=fixture(t); let reject, options, count=0;
  f.api.get=(path,config)=>{count++;options=config;return new Promise((_,no)=>{reject=no;});};
  const refresh=f.live.refreshCapabilities();
  assert.equal(f.live.capabilitiesLoading?.value,true);
  assert.equal(options.timeout,10000); assert.equal(options.skipBusy,true);
  await f.live.refreshCapabilities(); assert.equal(count,1);
  reject({response:{status:500}}); await refresh;
  assert.equal(f.live.capabilitiesLoading.value,false);
  assert.match(f.live.capabilitiesError.value,/HTTP 500/);
  // Dismissing another alert must not erase the reason start is blocked.
  f.live.error.value=''; assert.match(f.live.capabilitiesError.value,/HTTP 500/);
  const data={services:{},budget:{}};
  f.api.get=async()=>({data}); await f.live.refreshCapabilities();
  assert.equal(f.live.capabilities.value,data); assert.equal(f.live.capabilitiesError.value,'');
  assert.equal(f.live.capabilitiesLoading.value,false);
});

test('standalone camera preview requires strict camera consent',async t=>{
  for (const consent of [false, undefined, 'true']) {
    const f=fixture(t); await f.live.previewCamera(consent);
    assert.equal(f.tracks.length,0); assert.equal(f.contexts.length,0);
    assert.equal(f.posts.length,0); assert.match(f.live.error.value,/同意摄像头开启/);
  }
});

test('standalone preview opens only video without starting a classroom or clock',async t=>{
  const f=fixture(t); await f.live.previewCamera(true);
  assert.equal(f.live.cameraEnabled.value,true); assert.equal(f.tracks.length,1);
  assert.equal(f.live.camera.value.srcObject.getVideoTracks().length,1);
  assert.equal(f.contexts.length,0); assert.equal(f.posts.length,0); assert.equal(f.sockets.length,0);
  assert.equal(f.live.state.value,'idle'); assert.equal(f.live.room.value,null);
  assert.equal(f.live.elapsed.value,0); assert.equal(f.live.busy.value,false);
  await f.live.previewCamera(true); // Repeated clicks must not toggle a preview off.
  assert.equal(f.tracks.length,1); assert.equal(f.live.cameraEnabled.value,true);
  f.live.pauseCapture();
  assert.ok(f.tracks[0].stopped); assert.ok(f.workers[0].terminated);
  assert.equal(f.live.cameraEnabled.value,false);
  f.unmount.forEach(fn=>fn());
});

test('begin reuses a pre-opened camera and only adds microphone capture',async t=>{
  const f=fixture(t); await f.live.previewCamera(true);
  const stream=f.live.camera.value.srcObject;
  await f.live.begin('full',true,true);
  assert.equal(f.live.camera.value.srcObject,stream); assert.equal(f.tracks.length,2);
  assert.equal(f.contexts.length,1); assert.equal(f.workers.length,1);
  assert.ok(!f.tracks[0].stopped); assert.ok(f.posts.includes('/classroom/sessions'));
  f.unmount.forEach(fn=>fn());
});

test('camera preview rejection can be retried and ended sessions cannot open it',async t=>{
  const f=fixture(t,false,true); await f.live.previewCamera(true);
  assert.equal(f.live.busy.value,false); assert.equal(f.live.state.value,'idle');
  assert.equal(f.live.cameraEnabled.value,false); assert.match(f.live.error.value,/摄像头不可用/);
  assert.equal(f.posts.length,0); assert.equal(f.contexts.length,0);
  const g=fixture(t); g.live.state.value='ended'; await g.live.previewCamera(true);
  assert.equal(g.tracks.length,0);
});

test('pending camera preview prevents duplicate device requests and classroom creation',async t=>{
  const f=fixture(t); let release, entered;
  const waiting=new Promise(resolve=>{entered=resolve;});
  f.live.camera.value.play=()=>{entered();return new Promise(resolve=>{release=resolve;});};
  const preview=f.live.previewCamera(true); await waiting;
  await f.live.previewCamera(true); await f.live.begin('full',true,true);
  assert.equal(f.tracks.length,1); assert.equal(f.contexts.length,0); assert.equal(f.posts.length,0);
  assert.equal(f.live.busy.value,true);
  release(); await preview; assert.equal(f.live.busy.value,false);
  f.unmount.forEach(fn=>fn());
});

test('microphone rejection never creates a classroom and releases AudioContext',async t=>{
  const f=fixture(t,true); await f.live.begin('full',true,true);
  assert.equal(f.live.state.value,'idle'); assert.match(f.live.error.value,/麦克风/);
  assert.equal(f.posts.length,0); assert.ok(f.contexts[0].closed);
});

test('reconnect releases previous microphone before preparing replacement',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true); await f.live.reconnect(true,true);
  assert.equal(f.contexts.length,2); assert.ok(f.contexts[0].closed);
  assert.ok(f.tracks[0].stopped); assert.ok(!f.tracks[2].stopped);
  f.unmount.forEach(fn=>fn()); await Promise.resolve();
  assert.ok(f.tracks[2].stopped);
});

test('camera rejection prevents classroom creation and releases microphone',async t=>{
  const f=fixture(t,false,true); await f.live.begin('full',true,true);
  assert.match(f.live.error.value,/摄像头不可用/);
  assert.equal(f.live.state.value,'idle'); assert.ok(f.tracks[0].stopped);
  assert.equal(f.posts.length,0);
  f.unmount.forEach(fn=>fn());
});

test('pausing camera stops its worker and microphone without generating a report',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  assert.equal(f.workers.length,1);
  await f.live.toggleCamera();
  assert.ok(f.workers[0].terminated); assert.ok(f.tracks[1].stopped);
  assert.ok(f.tracks[0].stopped); assert.equal(f.live.pose.value,null);
  assert.equal(f.live.state.value,'disconnected');
  assert.ok(!f.posts.some(p=>p.endsWith('/finish')));
  f.unmount.forEach(fn=>fn());
});

test('face status and raw landmarks are cleared on close; late worker replies are ignored',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  const worker=f.workers[0];
  worker.onmessage({data:{type:'face_status',status:'ready'}});
  worker.onmessage({data:{type:'pose',captured_at:performance.now(),face:[{x:.5,y:.5}],data:{motion_version:2}}});
  assert.equal(f.live.faceStatus.value,'ready');
  assert.equal(f.live.landmarks.value.face.length,1);
  await f.live.toggleCamera();
  worker.onmessage({data:{type:'face_status',status:'ready'}});
  assert.equal(f.live.faceStatus.value,'idle');assert.equal(f.live.landmarks.value,null);
  f.unmount.forEach(fn=>fn());
});

test('resolution applies to the camera track and a rejected change retains the previous selection',async t=>{
  const f=fixture(t); f.live.camera.value={srcObject:null,play:async()=>{},videoWidth:1280};
  await f.live.toggleCamera();
  await f.live.setCameraResolution(360);
  assert.equal(f.live.cameraResolution.value,360);
  assert.equal(f.tracks[0].settings.height,360);
  f.tracks[0].applyConstraints=async()=>{throw new Error('unsupported');};
  await f.live.setCameraResolution(1020);
  assert.equal(f.live.cameraResolution.value,360);
  assert.ok(f.live.cameraNote.value.includes('未切换'));
  assert.equal(f.live.cameraEnabled.value,true);
  f.unmount.forEach(fn=>fn());
});

test('socket reply deltas drive the same student state as real PCM playback',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  const socket=f.sockets[0];let seq=0;
  const receive=async(type,fields={})=>socket.onmessage({data:JSON.stringify({type,session_id:1,seq:++seq,...fields})});
  await receive('ready');
  await receive('partial',{text:'小林，什么是平均分？'});
  await receive('generation_started',{generation_id:'g',student_id:'lin'});
  await receive('reply_delta',{generation_id:'g',student_id:'lin',delta:'老师，'});
  await receive('reply_delta',{generation_id:'g',student_id:'lin',delta:'每份要一样大。'});
  assert.equal(f.live.reply.value.text,'老师，每份要一样大。');
  assert.equal(f.live.reply.value.phase,'generating');
  await receive('reply',{generation_id:'g',student_id:'lin',reply_id:'r',text:'老师，每份要一样大。'});
  await receive('audio',{reply_id:'r',audio:Buffer.alloc(4800).toString('base64'),sample_rate:24000});
  assert.equal(f.audioNodes.length,1);
  assert.ok(f.audioNodes[0].target.gain); // Output gain, never microphone input.
  [...f.timers.values()].at(-1)();
  assert.equal(f.live.playbackStudent.value,'lin');
  await receive('audio_end',{reply_id:'r',ok:true});
  [...f.timers.values()].at(-1)();
  assert.equal(f.live.reply.value.phase,'done');
  assert.equal(socket.sent.at(-1).type,'playback_done');
  await receive('listening');
  assert.equal(f.live.state.value,'listening');
  assert.equal(f.live.playbackStudent.value,null);
  f.unmount.forEach(fn=>fn());
});

test('both strict consents are checked before touching either device',async t=>{
  for (const [audio,camera] of [[false,true],[true,false],[true,'true'],['true',true]]) {
    const f=fixture(t); await f.live.begin('full',audio,camera);
    assert.equal(f.tracks.length,0); assert.equal(f.posts.length,0);
    assert.match(f.live.error.value,/同意/);
  }
});

test('early finish does not stop devices, send finish or call REST',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  await f.live.finish();
  assert.match(f.live.error.value,/10 秒/);
  assert.ok(f.tracks.every(t=>!t.stopped));
  assert.ok(!f.posts.some(p=>p.endsWith('/finish')));
  assert.ok(!f.sockets[0].sent.some(m=>m.type==='finish'));
  f.unmount.forEach(fn=>fn());
});

test('external camera removal pauses capture and offers reconnection',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  f.tracks[1].onended(); await Promise.resolve();
  assert.equal(f.live.cameraEnabled.value,false);
  assert.equal(f.live.state.value,'disconnected');
  assert.ok(f.tracks[0].stopped);
  assert.match(f.live.error.value,/摄像头/);
  f.unmount.forEach(fn=>fn());
});

test('a delayed old socket close cannot tear down devices prepared for reconnection',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  const old=f.sockets[0]; old.close=()=>{old.readyState=3;};
  let release, entered;
  const waiting=new Promise(resolve=>{entered=resolve;});
  const originalPost=f.api.post;
  f.api.post=async(path)=>{
    if(path.endsWith('/ticket')) {entered(); await new Promise(resolve=>{release=resolve;});}
    return originalPost(path);
  };
  const reconnect=f.live.reconnect(true,true);
  await waiting;
  old.onclose();
  const cameraAlive=f.live.cameraEnabled.value;
  const microphoneAlive=!f.tracks.at(-1).stopped;
  release(); await reconnect;
  assert.equal(cameraAlive,true); assert.equal(microphoneAlive,true);
  f.unmount.forEach(fn=>fn());
});

test('failed reconnection returns to retryable state and releases both devices',async t=>{
  const f=fixture(t); await f.live.begin('full',true,true);
  f.api.post=async()=>{throw new Error('synthetic ticket failure');};
  await f.live.reconnect(true,true);
  assert.equal(f.live.state.value,'disconnected');
  assert.ok(f.tracks.every(track=>track.stopped));
  assert.equal(f.live.busy.value,false);
  f.unmount.forEach(fn=>fn());
});
