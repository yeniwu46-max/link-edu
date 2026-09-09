import test from 'node:test';
import assert from 'node:assert/strict';
import { bodyFeatures, faceFeatures, handFeatures } from '../src/services/motionFeatures.js';

function body() {
  const p=Array.from({length:33},()=>({x:.5,y:.5,visibility:0}));
  for(const [i,x,y] of [[11,.4,.3],[12,.6,.3],[15,.3,.15],[16,.7,.6],[23,.43,.7],[24,.57,.7]]) p[i]={x,y,visibility:.95};
  return p;
}
test('seated upper body retains raised-hand evidence, never invents torso angle',()=>{
  const p=body(); p[23].visibility=p[24].visibility=.1;
  const features=bodyFeatures([p]);
  assert.equal(features.scope,'upper_body'); assert.equal(features.status,'observed');
  assert.equal(features.left_raised,true); assert.equal(features.lean_degrees,null);
});
test('body geometry rejects occlusion and multiple people',()=>{
  const p=body(); assert.equal(bodyFeatures([p]).lean_degrees,0);
  assert.equal(bodyFeatures([p,p]).status,'multiple');
  p[11].visibility=.1; assert.equal(bodyFeatures([p]).status,'low_confidence');
  assert.equal(bodyFeatures([]).status,'no_detection');
});
test('only high-confidence recognized hand shapes are summarized',()=>{
  const r=handFeatures({landmarks:[Array(21).fill({x:.5,y:.5}),Array(21).fill({x:.6,y:.4})],
    gestures:[[{categoryName:'Open_Palm',score:.95}],[{categoryName:'Pointing_Up',score:.4}]]});
  assert.equal(r.count,2); assert.deepEqual(r.gestures,[{label:'Open_Palm',score:.95}]);
  assert.equal(JSON.stringify(r).includes('landmarks'),false);
});
test('face reports geometry, not emotion, identity or gaze target',()=>{
  const p=Array.from({length:478},()=>({x:.5,y:.5}));
  p[33]={x:.4,y:.4}; p[263]={x:.6,y:.4}; p[1]={x:.5,y:.5};
  const r=faceFeatures({faceLandmarks:[p],faceBlendshapes:[{categories:[{categoryName:'jawOpen',score:.7},{categoryName:'mouthSmileLeft',score:.9}]}]});
  assert.equal(r.status,'observed'); assert.equal(r.nose_offset_ratio,0); assert.equal(r.head_tilt_degrees,0);
  assert.equal(r.mouth_open,.7); assert.equal(r.emotion,undefined); assert.equal(r.confidence,undefined);
  assert.equal(faceFeatures({faceLandmarks:[p,p]}).status,'multiple');
  p[33].x=NaN; assert.equal(faceFeatures({faceLandmarks:[p]}).status,'low_confidence');
});
