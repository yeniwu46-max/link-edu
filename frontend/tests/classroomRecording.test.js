import test from 'node:test';
import assert from 'node:assert/strict';
import { recordingKey, recordingTime, canStore, MAX_TOTAL_BYTES, MAX_RECORDING_BYTES } from '../src/services/classroomRecordingStore.js';
import { calibrationSummary } from '../src/services/classroomCalibration.js';
import { recordingMime } from '../src/services/classroomRecorder.js';

test('recordings are scoped by origin, account and session', () => {
  assert.notEqual(recordingKey('https://school.test', 1, 3), recordingKey('https://school.test', 2, 3));
  assert.notEqual(recordingKey('http://school.test', 1, 3), recordingKey('https://school.test', 1, 3));
  assert.throws(() => recordingKey('https://school.test', null, 3));
});
test('evidence lookup respects recording gaps instead of seeking an unrelated frame', () => {
  const segments = [{wallStart:2000, wallEnd:12000, videoStart:0}, {wallStart:42000, wallEnd:52000, videoStart:10000}];
  assert.equal(recordingTime(segments, 45000), 13);
  assert.equal(recordingTime(segments, 30000), null);
  assert.equal(recordingTime(segments, 1000), null);
});
test('quota rejection does not evict existing recordings', () => {
  assert.equal(canStore([{key:'a',byteLength:MAX_TOTAL_BYTES}], 'b', 1), false);
  assert.equal(canStore([{key:'a',byteLength:MAX_TOTAL_BYTES}], 'a', 100), true);
  assert.equal(canStore([], 'a', MAX_RECORDING_BYTES + 1), false);
  assert.equal(canStore([], 'a', 0), false);
});

test('codec probing degrades to MP4 or no recording without breaking a lesson', t => {
  const original=globalThis.MediaRecorder;
  t.after(()=>{if(original===undefined)delete globalThis.MediaRecorder;else globalThis.MediaRecorder=original;});
  delete globalThis.MediaRecorder;
  assert.equal(recordingMime(), '');
  globalThis.MediaRecorder={isTypeSupported:type=>type==='video/mp4'};
  assert.equal(recordingMime(), 'video/mp4');
  globalThis.MediaRecorder={isTypeSupported:()=>false};
  assert.equal(recordingMime(), '');
});
test('calibration reports each modality without penalizing missing hands', () => {
  const summary = calibrationSummary([{body:{status:'observed'},hands:{status:'no_detection'},face:{status:'failed'}}]);
  assert.equal(summary.body.observed, 1);
  assert.equal(summary.hands.status, 'no_detection');
  assert.equal(summary.face.status, 'failed');
});
