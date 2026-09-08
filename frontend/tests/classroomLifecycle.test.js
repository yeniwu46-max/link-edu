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
  const contexts=[], tracks=[], posts=[], unmount=[];
  const api={post:async(path)=>{posts.push(path); return {data:path.endsWith('/ticket')?{ticket:'synthetic'}:{session_id:1}};},
    get:async()=>({data:{session_id:1,state:'active',events:[],elapsed:0}})};
  class AudioContext {
    constructor(){contexts.push(this); this.destination={}; this.currentTime=0; this.audioWorklet={addModule:async()=>{}};}
    async resume(){} async close(){this.closed=true;}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    createAnalyser(){return {connect(){},getByteTimeDomainData(a){a.fill(128);}};}
  }
  class Socket {static OPEN=1; constructor(){this.readyState=1;this.bufferedAmount=0;} send(){} close(){this.readyState=3;this.onclose?.();}}
  const module={exports:{}};
  const workers=[];
  const scope={module,exports:module.exports,AudioContext,WebSocket:Socket,performance,console,Uint8Array,URL,
    Worker:class {constructor(){workers.push(this);}postMessage(){this.onmessage?.({data:{type:'ready'}});}terminate(){this.terminated=true;}},
    crypto:{randomUUID:()=>String(Math.random())},location:{protocol:'http:',host:'localhost'},
    navigator:{mediaDevices:{getUserMedia:async(options)=>{if(denied || (cameraDenied && options.video))throw new Error('NotAllowedError');
      const track={stop(){this.stopped=true;}};tracks.push(track);return {getTracks:()=>[track]};}}},
    AudioWorkletNode:class {constructor(){this.port={};}connect(){}disconnect(){}},
    setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){},
    require:(name)=>name==='vue'?{ref:(value)=>({value}),onUnmounted:fn=>unmount.push(fn)}:{api},
  };
  vm.runInNewContext(compiled.outputFiles[0].text,scope);
  return {live:module.exports.useClassroom(),contexts,tracks,posts,unmount,workers};
}

test('microphone rejection never creates a classroom and releases AudioContext',async t=>{
  const f=fixture(t,true); await f.live.begin('full',true);
  assert.equal(f.live.state.value,'idle'); assert.match(f.live.error.value,/麦克风/);
  assert.equal(f.posts.length,0); assert.ok(f.contexts[0].closed);
});

test('reconnect releases previous microphone before preparing replacement',async t=>{
  const f=fixture(t); await f.live.begin('full',true); await f.live.reconnect();
  assert.equal(f.contexts.length,2); assert.ok(f.contexts[0].closed);
  assert.ok(f.tracks[0].stopped); assert.ok(!f.tracks[1].stopped);
  f.unmount.forEach(fn=>fn()); await Promise.resolve();
  assert.ok(f.tracks[1].stopped);
});

test('camera rejection keeps the voice session and microphone alive',async t=>{
  const f=fixture(t,false,true); await f.live.begin('full',true);
  await f.live.toggleCamera();
  assert.match(f.live.error.value,/摄像头不可用/);
  assert.equal(f.live.state.value,'connecting'); assert.ok(!f.tracks[0].stopped);
  f.unmount.forEach(fn=>fn());
});

test('closing the camera stops its worker but not microphone capture',async t=>{
  const f=fixture(t); await f.live.begin('full',true);
  f.live.camera.value={srcObject:null,play:async()=>{},videoWidth:640};
  await f.live.toggleCamera(); assert.equal(f.workers.length,1);
  await f.live.toggleCamera();
  assert.ok(f.workers[0].terminated); assert.ok(f.tracks[1].stopped);
  assert.ok(!f.tracks[0].stopped); assert.equal(f.live.pose.value,null);
  f.unmount.forEach(fn=>fn());
});
