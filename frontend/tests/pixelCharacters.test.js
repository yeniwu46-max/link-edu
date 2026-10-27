import test from 'node:test'
import assert from 'node:assert/strict'
import { studentPixelFrame, assistantPixelFrame, frameRect, pixelSource } from '../src/services/pixelCharacters.js'

test('student audio, acknowledgement and raised hand take priority over incidental motion', () => {
  assert.equal(studentPixelFrame({speaking:true,level:.6,raised:true,thinking:true}),7)
  assert.equal(studentPixelFrame({speaking:true,level:0,thinking:true}),6)
  assert.equal(studentPixelFrame({raised:true},{acknowledged:true}),8)
  assert.equal(studentPixelFrame({raised:true,thinking:true}),5)
  assert.equal(studentPixelFrame({thinking:true,level:1}),4)
  assert.equal(studentPixelFrame({failed:true}),9)
})
test('idle student actions are staggered, while reduced motion preserves meaningful states', () => {
  assert.equal(studentPixelFrame({}, {now:9000}),2)
  assert.equal(studentPixelFrame({}, {now:17000}),3)
  assert.equal(studentPixelFrame({}, {now:9000,offset:6000}),0)
  assert.equal(studentPixelFrame({}, {now:9000,reduced:true}),0)
  assert.equal(studentPixelFrame({thinking:true}, {reduced:true}),4)
  assert.equal(studentPixelFrame({}, {completed:true,reduced:true}),10)
  assert.equal(studentPixelFrame({}, {turn:.3,reduced:true}),11)
})
test('assistant follows conversation state and actual sound level', () => {
  assert.equal(assistantPixelFrame('speaking',.5),7)
  assert.equal(assistantPixelFrame('speaking',0),6)
  assert.equal(assistantPixelFrame('thinking',1),3)
  assert.equal(assistantPixelFrame('listening',0),2)
  assert.equal(assistantPixelFrame('error',0),9)
  assert.equal(assistantPixelFrame('idle',0,{reduced:true}),0)
})
test('atlas frame crops use actual source dimensions, including recording fallback Image dimensions', () => {
  assert.deepEqual(frameRect({width:1536,height:1152},7),{x:1152,y:384,width:384,height:384})
  assert.deepEqual(frameRect({naturalWidth:1440,naturalHeight:1080,width:1,height:1},11),{x:1080,y:720,width:360,height:360})
  assert.equal(pixelSource('../bad'),'/assets/characters/pixel/lin.png')
})
