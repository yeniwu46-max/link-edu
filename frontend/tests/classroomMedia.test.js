import test from 'node:test';
import assert from 'node:assert/strict';
import { cameraConstraints, inferenceSize } from '../src/services/classroomMedia.js';

test('camera presets request 1020, 720 and 360 without forcing unsupported devices',()=>{
  for(const height of [1020,720,360]) {
    const c=cameraConstraints(height);
    assert.equal(c.height.ideal,height);
    assert.equal(c.frameRate.max,30);
    assert.equal(c.height.exact,undefined);
  }
  assert.equal(cameraConstraints('invalid').height.ideal,720);
});

test('inference images preserve aspect ratio and remain bounded at high resolution',()=>{
  assert.deepEqual(inferenceSize(1920,1080),{resizeWidth:640,resizeHeight:360});
  assert.deepEqual(inferenceSize(480,640),{resizeWidth:360,resizeHeight:480});
  assert.deepEqual(inferenceSize(320,240),{resizeWidth:320,resizeHeight:240});
});
