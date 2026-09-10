import test from 'node:test';
import assert from 'node:assert/strict';
import { classroomEntry } from '../src/services/classroomEntry.js';

test('legacy entry goes directly to the real classroom, without claiming another lesson is supported', () => {
  assert.deepEqual(classroomEntry({ query: { courseId: '9' } }), { path: '/classroom', query: {} });
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
