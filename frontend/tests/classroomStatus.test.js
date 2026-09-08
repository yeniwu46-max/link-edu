import test from 'node:test';
import assert from 'node:assert/strict';
import { speechProviderLabel, classroomLoadError } from '../src/services/classroomStatus.js';

test('consent names only the configured speech provider', () => {
  assert.equal(speechProviderLabel('xfyun'),'讯飞');
  assert.equal(speechProviderLabel('bailian'),'百炼');
  assert.equal(speechProviderLabel(undefined),'尚未确认的语音服务（暂不可开始）');
});
test('invalid login has an actionable error without exposing credentials', () => {
  assert.match(classroomLoadError({response:{status:401}},'其他错误'),/重新登录/);
  assert.match(classroomLoadError({response:{status:422}},'其他错误'),/重新登录/);
  assert.equal(classroomLoadError({response:{status:503}},'后端未连接'),'后端未连接');
});
