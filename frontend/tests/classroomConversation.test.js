import test from 'node:test';
import assert from 'node:assert/strict';
import { createConversation } from '../src/services/classroomConversation.js';
import { clampCameraPosition } from '../src/services/useCameraWindow.js';

const teacher = (id, text, at = 1000) => ({ id, type: 'transcript', at_ms: at, data: { text } });
const student = (id, text, replyId = 'r1', at = 2000) => ({ id, type: 'student', at_ms: at, data: { text, student_id: 'ming', reply_id: replyId } });
function start(c, id = 'g1') {
  c.receive({ type: 'generation_started', generation_id: id }, 1500);
  c.receive({ type: 'generation_student', generation_id: id, student_id: 'ming' });
}
const delta = (text, id = 'g1') => ({ type: 'reply_delta', generation_id: id, student_id: 'ming', delta: text });
const reply = (id = 'g1', replyId = 'r1') => ({ type: 'reply', generation_id: id, reply_id: replyId, student_id: 'ming', text: '二分之一' });

test('ASR revisions replace one draft and final transcript keeps its visual identity', () => {
  const c = createConversation();
  c.receive({ type: 'partial', text: '把一' }, 500);
  const key = c.snapshot()[0].key;
  c.receive({ type: 'partial', text: '把一个整体平均分成两份' }, 800);
  c.receive({ type: 'event', event: teacher('t1', '把一个整体平均分成两份。') });
  c.receive({ type: 'partial', text: '' });
  assert.equal(c.snapshot().length, 1);
  assert.equal(c.snapshot()[0].key, key);
  assert.equal(c.snapshot()[0].status, 'done');
  assert.equal(c.snapshot()[0].text, '把一个整体平均分成两份。');
});
test('streaming reply merges event-before-reply and duplicate event deliveries', () => {
  const c = createConversation(); start(c);
  c.receive(delta('二分')); c.receive(delta('之一'));
  const key = c.snapshot()[0].key;
  c.receive({ type: 'generation_completed', generation_id: 'g1', student_id: 'ming', text: '二分之一', action: 'answer' });
  c.receive({ type: 'event', event: student('s1', '二分之一') });
  c.receive(reply());
  c.receive({ type: 'event', event: student('s1', '二分之一') });
  c.receive({ type: 'listening' });
  assert.equal(c.snapshot().length, 1);
  assert.deepEqual([c.snapshot()[0].key, c.snapshot()[0].text, c.snapshot()[0].status, c.snapshot()[0].eventId], [key, '二分之一', 'done', 's1']);
});
test('reply-before-event is reconciled by reply ID, repeated spoken text is not deduplicated', () => {
  const c = createConversation(); start(c);
  c.receive(reply()); c.receive({ type: 'event', event: student('s1', '二分之一') });
  c.receive({ type: 'listening' }); start(c, 'g2');
  c.receive(reply('g2', 'r2')); c.receive({ type: 'event', event: student('s2', '二分之一', 'r2', 4000) });
  assert.equal(c.snapshot().length, 2);
  assert.deepEqual(c.snapshot().map(r => r.replyId), ['r1', 'r2']);
});
test('old generation chunks cannot change the current reply, failure retains visible draft', () => {
  const c = createConversation(); start(c); c.receive(delta('二分'));
  c.receive({ type: 'generation_failed', generation_id: 'g1', message: '请求中断' });
  c.receive(delta('迟到片段'));
  start(c, 'g2'); c.receive(delta('旧片段')); c.receive(delta('新的回答', 'g2'));
  assert.deepEqual(c.snapshot().map(r => [r.text, r.status]), [['二分', 'failed'], ['新的回答', 'generating']]);
});
test('cancelled drafts remain presentation-only and survive reconnect within this page', () => {
  const c = createConversation();
  c.receive({ type: 'event', event: teacher('t1', '提问') }); start(c); c.receive(delta('二分'));
  c.receive({ type: 'generation_cancelled', generation_id: 'g1' }); c.receive(delta('之一'));
  c.receive({ type: 'disconnected' });
  c.restore([teacher('t1', '提问')], true);
  assert.equal(c.snapshot().length, 2);
  assert.equal(c.snapshot()[1].status, 'interrupted');
  assert.equal(c.snapshot()[1].eventId, undefined);
  c.restore([teacher('other', '另一节课')]);
  assert.equal(c.snapshot().length, 1);
  assert.equal(c.snapshot()[0].text, '另一节课');
});
test('pause and disconnect mark active drafts; historical restore uses only saved speech', () => {
  const c = createConversation();
  c.receive({ type: 'partial', text: '尚未说完' }); c.receive({ type: 'paused' });
  start(c); c.receive(delta('正在回答')); c.receive({ type: 'disconnected' });
  assert.deepEqual(c.snapshot().map(r => r.status), ['paused', 'disconnected']);
  c.restore([student('s1', '已保存的回答'), { id: 'tech', type: 'latency', data: {} }, teacher('t1', '提问')]);
  assert.deepEqual(c.snapshot().map(r => r.text), ['提问', '已保存的回答']);
  assert.ok(c.snapshot().every(r => r.status === 'done'));
});
test('empty ASR revisions retract a provisional draft; empty conversation stays empty', () => {
  const c = createConversation(); c.receive({ type: 'partial', text: '暂定' });
  c.receive({ type: 'partial', text: '' });
  assert.deepEqual(c.snapshot(), []);
});
test('a deferred hand-raised reply without a generation ID still finishes and is deduplicated', () => {
  const c = createConversation();
  c.receive({ type: 'event', event: student('question', '老师，我有问题', 'raised-reply') });
  c.receive({ ...reply(null, 'raised-reply'), text: '老师，我有问题' });
  assert.equal(c.snapshot().length, 1);
  assert.equal(c.snapshot()[0].status, 'speaking');
  c.receive({ type: 'listening' });
  assert.equal(c.snapshot()[0].status, 'done');
});
test('generation IDs keep late formal events separate from a newer reply', () => {
  const c = createConversation(); start(c); c.receive(delta('旧回答'));
  start(c, 'g2'); c.receive(delta('新的回答', 'g2'));
  const e = student('late', '旧回答');
  e.data.generation_id = 'g1'; e.data.trigger = 'manual_click'; e.data.interaction_kind = 'challenge';
  c.receive({ type: 'event', event: e });
  assert.equal(c.snapshot().length, 2);
  assert.equal(c.snapshot()[0].eventId, 'late');
  assert.equal(c.snapshot()[0].interactionKind, 'challenge');
  assert.equal(c.snapshot()[1].text, '新的回答');
  assert.equal(c.snapshot()[1].eventId, undefined);
});
test('formal events arriving before generation notifications retain one authoritative row', () => {
  const c = createConversation(); const e = student('early', '已保存');
  e.data.generation_id = 'g1'; c.receive({ type: 'event', event: e });
  start(c); c.receive(delta('迟到重复片段'));
  assert.equal(c.snapshot().length, 1);
  assert.equal(c.snapshot()[0].text, '已保存');
  c.receive(reply()); c.receive({ type: 'event', event: {...e,id:'another-id'} });
  assert.equal(c.snapshot()[0].status, 'speaking');
});
test('camera window remains inside resized bounds, including an area smaller than itself', () => {
  assert.deepEqual(clampCameraPosition({ x: 900, y: -10 }, { width: 800, height: 500 }, { width: 240, height: 167 }), { x: 560, y: 0 });
  assert.deepEqual(clampCameraPosition({ x: 400, y: 400 }, { width: 120, height: 100 }, { width: 160, height: 122 }), { x: 0, y: 0 });
});
