import test from 'node:test';
import assert from 'node:assert/strict';
import { createBubbleRetention } from '../src/services/classroomBubble.js';

function fixture() {
  let shown, timer, delay;
  const bubble=createBubbleRetention(v=>{shown=v;}, {
    schedule:(fn,ms)=>{timer=fn;delay=ms;return 1;}, cancel:()=>{timer=null;}
  });
  return {bubble,get shown(){return shown;},get delay(){return delay;},expire:()=>timer?.()};
}
test('streaming and playback are live, completed text is retained for 15 seconds',()=>{
  const f=fixture();
  f.bubble.update({id:'one',phase:'thinking',text:''});
  f.bubble.update({id:'one',phase:'generating',text:'老师，'});
  assert.equal(f.shown.text,'老师，');
  f.bubble.update({id:'one',phase:'done',text:'老师，怎样平均分？'});
  assert.equal(f.delay,15000);
  f.bubble.update(null); assert.equal(f.shown.text,'老师，怎样平均分？');
  f.expire(); assert.equal(f.shown,null);
});
test('new turns cancel old expiry; unmount releases timers; cancelled thinking clears',()=>{
  const f=fixture();
  f.bubble.update({id:'one',phase:'done',text:'旧问题'});
  f.bubble.update({id:'two',phase:'thinking',text:''}); f.expire();
  assert.equal(f.shown.id,'two');
  f.bubble.update(null); assert.equal(f.shown,null);
  f.bubble.update({id:'three',phase:'done',text:'新问题'}); f.bubble.clear();
  assert.equal(f.shown,null);
});
test('duplicate terminal updates do not restart expiry or resurrect an expired bubble',()=>{
  const f=fixture(), r={id:'one',phase:'done',text:'问题'};
  f.bubble.update(r); f.expire(); f.bubble.update({...r});
  assert.equal(f.shown,null);
});
