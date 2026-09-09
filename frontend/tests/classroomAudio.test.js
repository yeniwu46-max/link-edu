import test from 'node:test';
import assert from 'node:assert/strict';
import { ClassroomAudio } from '../src/services/classroomAudio.js';

function fixture(t) {
  const timers = new Map(), messages = [], nodes = [], buffers = [];
  let seq = 0;
  t.mock.method(globalThis, 'setTimeout', (fn) => { timers.set(++seq, fn); return seq; });
  t.mock.method(globalThis, 'clearTimeout', (id) => timers.delete(id));
  const audio = new ClassroomAudio((type, data) => messages.push({type, ...data}), () => {});
  audio.ctx = {
    currentTime: 0,
    createBuffer(channels, length, rate) {
      const buffer = {duration:length/rate, getChannelData:() => new Float32Array(length)};
      buffers.push(buffer); return buffer;
    },
    createBufferSource() {
      const node = {connect(){}, disconnect(){}, start(at){this.at=at;}, stop(){this.stopped=true;}};
      nodes.push(node); return node;
    },
    async close(){this.closed=true;},
  };
  const pcm = (samples) => Buffer.alloc(samples * 2).toString('base64');
  const flush = () => { const pending=[...timers.values()]; timers.clear(); pending.forEach(fn=>fn()); };
  return {audio, messages, nodes, buffers, pcm, flush, timers};
}

for (const rate of [16000, 24000]) test(`PCM ${rate} Hz retains duration and queues chunks`, t => {
  const f=fixture(t);
  f.audio.chunk('one',f.pcm(rate),rate); f.audio.chunk('one',f.pcm(rate/2),rate);
  assert.equal(f.buffers[0].duration,1); assert.equal(f.buffers[1].duration,.5);
  assert.equal(f.nodes[1].at,f.nodes[0].at+1);
  assert.equal(f.messages.filter(m=>m.type==='playback_started').length,1);
});

test('cancel stops nodes and discards late audio', t => {
  const f=fixture(t); f.audio.chunk('old',f.pcm(100),16000);
  f.audio.cancel('old'); f.audio.chunk('old',f.pcm(100),16000);
  assert.ok(f.nodes[0].stopped); assert.equal(f.nodes.length,1);
});

test('late cancelled end cannot clear the next reply completion', t => {
  const f=fixture(t); f.audio.chunk('old',f.pcm(100),16000); f.audio.cancel('old');
  f.audio.chunk('new',f.pcm(100),16000); f.audio.end('new'); f.audio.end('old'); f.flush();
  assert.deepEqual(f.messages.filter(m=>m.type==='playback_done').map(m=>m.reply_id),['new']);
});

test('failed synthesis without audio reports failure once', t => {
  const f=fixture(t); f.audio.end('failed',false); f.flush(); f.audio.end('failed',false); f.flush();
  assert.deepEqual(f.messages.map(m=>m.type),['playback_failed']);
});

test('completed reply cannot play again or finish twice', t => {
  const f=fixture(t); f.audio.chunk('one',f.pcm(100),16000); f.audio.end('one'); f.flush();
  f.audio.chunk('one',f.pcm(100),16000); f.audio.end('one'); f.flush();
  assert.equal(f.nodes.length,1);
  assert.equal(f.messages.filter(m=>m.type==='playback_done').length,1);
});

test('closing releases capture tracks and audio resources', async t => {
  const f=fixture(t); let stopped=0, disconnected=0;
  f.audio.stream={getTracks:()=>[{stop(){stopped++;}}]};
  f.audio.source={disconnect(){disconnected++;}};
  await f.audio.close();
  assert.equal(stopped,1); assert.equal(disconnected,1); assert.ok(f.audio.ctx.closed);
});

test('avatar playback waits for scheduled audio and cancel suppresses late animation',t=>{
  const f=fixture(t), phases=[]; f.audio.onPlayback=(id,phase)=>phases.push([id,phase]);
  f.audio.chunk('one',f.pcm(100),16000);
  assert.equal(phases.length,0); f.flush(); assert.deepEqual(phases,[['one','playing']]);
  f.audio.end('one');f.flush();assert.deepEqual(phases.at(-1),['one','done']);
  f.audio.chunk('two',f.pcm(100),16000);f.audio.cancel('two');f.flush();
  assert.equal(phases.some(([id])=>id==='two'),false);
});
