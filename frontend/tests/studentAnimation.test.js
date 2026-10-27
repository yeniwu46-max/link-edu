import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { createStudentAnimation } from '../src/services/studentAnimation.js'
const manifest=JSON.parse(fs.readFileSync(new URL('../public/assets/characters/pixel/v2/manifest.json',import.meta.url)))

test('every v2 animation atlas ships with frame rectangles inside its PNG bounds',()=>{
 for(const id of manifest.characters){
  const data=fs.readFileSync(new URL(`../public/assets/characters/pixel/v2/${id}.png`,import.meta.url))
  assert.equal(data.subarray(1,4).toString(),'PNG')
  const width=data.readUInt32BE(16),height=data.readUInt32BE(20)
  assert.equal(manifest.frames[id].length,manifest.columns*manifest.rows)
  assert.ok(manifest.frames[id].every(f=>f.x>=0&&f.y>=0&&f.width>0&&f.height>0&&f.x+f.width<=width&&f.y+f.height<=height))
 }
})
test('rise and sit are eight ordered frames; mouth follows real level',()=>{
 const a=createStudentAnimation(manifest)
 assert.deepEqual(Array.from({length:8},(_,i)=>a.sample(i*100,{speaking:true,level:0}).frame),manifest.clips.rise)
 assert.equal(a.sample(800,{speaking:true,level:0}).frame,40)
 assert.equal(a.sample(900,{speaking:true,level:.5}).frame,41)
 assert.deepEqual(Array.from({length:8},(_,i)=>a.sample(1000+i*100,{speaking:false}).frame),manifest.clips.sit)
 assert.notEqual(a.sample(1800,{}).action,'sit')
})
test('speech ending midway reverses only the completed rise',()=>{
 const a=createStudentAnimation(manifest)
 a.sample(0,{speaking:true});a.sample(200,{speaking:true})
 assert.equal(a.sample(200,{speaking:false}).frame,34)
 assert.equal(a.sample(300,{}).frame,33)
 assert.equal(a.sample(400,{}).frame,32)
})
test('ambient dozing never overlaps and semantic response overrides idle',()=>{
 const avatars=[0,1,2].map(i=>createStudentAnimation(manifest,i))
 for(let t=0;t<100000;t+=100)assert.ok(avatars.map(a=>a.sample(t,{})).filter(f=>f.action==='doze').length<=1)
 const a=createStudentAnimation(manifest);a.sample(2000,{})
 assert.equal(a.sample(2100,{raised:true},{legacy:5}).frame,5)
 assert.equal(a.sample(2200,{speaking:true},{reduced:true}).frame,40)
})
test('writing uses pickup, repeated strokes, putdown in order at 10fps',()=>{
 const a=createStudentAnimation(manifest,1)
 const frames=Array.from({length:20},(_,i)=>a.sample(i*100,{}, {force:'writing'}).frame)
 assert.deepEqual(frames,[...manifest.clips.pickup,...manifest.clips.write,...manifest.clips.write,...manifest.clips.write,...manifest.clips.putdown])
})
test('an out-of-order first RAF timestamp cannot select a negative frame',()=>{
 const a=createStudentAnimation(manifest);a.sample(100.2,{speaking:true});
 assert.equal(a.sample(100,{speaking:true}).frame,32);
})
