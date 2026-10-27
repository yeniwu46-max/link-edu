import test from 'node:test';
import assert from 'node:assert/strict';
import { classroomEntry } from '../src/services/classroomEntry.js';

test('course entry retains the practice skill without auto-starting a classroom', () => {
  assert.deepEqual(classroomEntry({ query: { courseId: '9', start: '1' } }), { path: '/classroom', query: { courseId:'9' } });
});
test('explicit eight minute entry keeps the duration, not an autostart instruction', () => {
  assert.deepEqual(classroomEntry({ query: { mode: 'fragment', start: '1' } }), {
    path: '/classroom', query: { mode: 'fragment' },
  });
});
test('invalid or array mode falls back to the normal preparation screen', () => {
  for (const mode of ['bad', ['fragment'], undefined]) {
    assert.deepEqual(classroomEntry({ query: { mode } }), { path: '/classroom', query: {} });
  }
});
