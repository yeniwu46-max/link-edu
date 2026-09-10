import test from 'node:test';
import assert from 'node:assert/strict';
import { studentPresentation } from '../src/services/classroomStudent.js';

test('each student has the supplied listening and raised artwork', () => {
  for (const id of ['ming', 'yu', 'lin']) {
    assert.equal(studentPresentation(id).src, `/assets/students/${id}-listening.png`);
    assert.equal(studentPresentation(id, { raised: true }).src, `/assets/students/${id}-raised.png`);
  }
});
test('thinking, generation, queued speech and actual playback all raise the hand', () => {
  for (const phase of ['thinking','generating','queued','playing']) {
    assert.equal(studentPresentation('ming', { reply: { phase } }).pose, 'raised');
  }
  assert.equal(studentPresentation('ming', { speaking: true }).label, '正在发言');
});
test('retained terminal text does not keep a student waving after playback', () => {
  for (const phase of ['done', 'failed', 'cancelled', 'interrupted']) {
    assert.equal(studentPresentation('yu', { reply: { phase, action: 'raise' } }).pose, 'listening');
  }
});
test('unknown student ids cannot turn into arbitrary image paths', () => {
  assert.equal(studentPresentation('../other').src, '/assets/students/lin-listening.png');
});
