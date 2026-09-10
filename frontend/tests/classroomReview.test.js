import test from 'node:test';
import assert from 'node:assert/strict';
import { classroomDestination, buildReview, validScore, formatReportDate } from '../src/services/classroomReview.js';

test('ended history opens its AI report; active history stays in classroom', () => {
  assert.deepEqual(classroomDestination({session_id:14,state:'ended'}), {path:'/ai-review',query:{classroom:'14'}});
  assert.deepEqual(classroomDestination({session_id:14,state:'active'}), {path:'/classroom',query:{session:14}});
});
test('missing scores never become zero or synthesized averages', () => {
  for (const score of [null,undefined,'80',false,NaN,Infinity,-1,101]) assert.equal(validScore(score),null);
  assert.equal(validScore(0),0);
  const view=buildReview({report_state:'completed',report:{dimensions:[{key:'clarity',score:0},{key:'posture',score:null}]}});
  assert.equal(view.overall,null);
  assert.equal(view.scored,1);
  assert.equal(view.dimensions.length,6);
  assert.equal(view.dimensions[3].score,null);
});
test('citations are unique, resolve to this classroom, and sort chronologically', () => {
  const view=buildReview({report_state:'completed',events:[
    {id:2,type:'vision',at_ms:2000,data:{}},{id:1,type:'transcript',at_ms:1000,data:{text:'平均分'}},
  ],report:{dimensions:[{key:'clarity',score:80,event_ids:[2,1,1,999,'2'],source_ids:['s1','bad','s1']}],sources:[{id:'s1'}]}});
  assert.deepEqual(view.dimensions[0].evidence.map(e=>e.id),[1,2]);
  assert.equal(view.dimensions[0].unresolved,2);
  assert.deepEqual(view.dimensions[0].sources.map(s=>s.id),['s1']);
});
test('generated, missing-reply, failed and interrupted speech cannot count as completed exchange', () => {
  const events=[
    {id:1,type:'student',at_ms:1,data:{reply_id:'a'}},
    {id:2,type:'student',at_ms:2,data:{reply_id:'b'}},
    {id:3,type:'student',at_ms:3,data:{reply_id:'c'}},
    {id:4,type:'student',at_ms:4,data:{reply_id:'d'}},
    ...['a','a','b','c','d','orphan',null].map((reply_id,i)=>({id:10+i,type:'playback',at_ms:10+i,data:{reply_id,status:'playback_completed'}})),
    {id:20,type:'playback',at_ms:20,data:{reply_id:'b',status:'playback_failed'}},
    {id:21,type:'interrupt',at_ms:21,data:{reply_id:'c'}},
    {id:22,type:'playback',at_ms:22,data:{reply_id:'d',status:'playback_cancelled'}},
  ];
  const view=buildReview({elapsed:30,events});
  assert.equal(view.metrics.replies,4);
  assert.equal(view.metrics.completed,1);
  assert.equal(view.lanes.find(l=>l.key==='completed').events.length,1);
});
test('unknown timestamps stay unknown; observed span is not fabricated as class duration', () => {
  const view=buildReview({events:[{id:1,type:'transcript',data:{}},{id:2,type:'pose',at_ms:5000,data:{}}]});
  assert.equal(view.duration,null);
  assert.equal(view.untimed,1);
  assert.equal(view.lanes[0].events.length,0);
  assert.equal(view.span,5000);
});
test('insufficient classroom suppresses even stale stored scores', () => {
  const view=buildReview({report_state:'insufficient',report:{overall_score:90,dimensions:[{key:'clarity',score:90}]}});
  assert.equal(view.hasReport,false);
  assert.equal(view.scored,0);
  assert.equal(view.overall,null);
});
test('date parser accepts UTC-naive backend dates and explicit offsets without appending a second Z', () => {
  assert.equal(formatReportDate('garbage'),'时间未记录');
  assert.equal(formatReportDate(null),'时间未记录');
  assert.equal(formatReportDate('2026-09-10T00:00:00'),formatReportDate('2026-09-10T00:00:00Z'));
});
