import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Scene, Group, Mesh, BoxGeometry, MeshStandardMaterial } from 'three'
import { prepareStudentAvatar, poseStudent } from '../src/components/fx/studentAvatarScene.js'
import { disposeScene } from '../src/components/fx/heroAvatarScene.js'
import { STUDENT_MODELS, studentMotionState, studentRenderQuality } from '../src/services/studentStageState.js'
import { boundHelpPosition } from '../src/utils/useHelpPosition.js'
import { createClassroomPainter } from '../src/services/classroomCompositor.js'

test('student speech is driven by active audio, independently of generated reply text', () => {
  assert.deepEqual(studentMotionState('ming', { raised:'ming', reply:{studentId:'ming',phase:'generating'}, level:.9 }),
    { raised:true, thinking:true, speaking:false, level:0 })
  assert.equal(studentMotionState('yu', { playbackStudent:'ming',level:1 }).speaking, false)
  assert.equal(studentMotionState('ming', { playbackStudent:'ming',level:3 }).level, 1)
  assert.equal(studentMotionState('ming', { playbackStudent:'ming',level:-3 }).level, 0)
  assert.equal(studentMotionState('ming', { reply:{studentId:'ming',phase:'done'} }).thinking, false)
})
test('student quality keeps a 30 fps ceiling and bounded pixel ratio', () => {
  assert.deepEqual(studentRenderQuality(true), {fps:30,pixelRatio:1.25})
  assert.deepEqual(studentRenderQuality(false), {fps:30,pixelRatio:1})
  assert.deepEqual(studentRenderQuality(true,true), {fps:20,pixelRatio:1})
})
test('selected local models retain idle animation and valid buffers only', () => {
  const dir = new URL('../public/assets/models/students/', import.meta.url)
  for (const file of [...Object.values(STUDENT_MODELS).map(x=>x.file),'aid-glasses.glb']) {
    const bytes=readFileSync(new URL(file,dir))
    assert.equal(bytes.toString('ascii',0,4),'glTF')
    assert.equal(bytes.readUInt32LE(8),bytes.length)
    const jsonLength=bytes.readUInt32LE(12)
    const data=JSON.parse(bytes.toString('utf8',20,20+jsonLength).trim())
    const binLength=bytes.readUInt32LE(20+jsonLength)
    for(const view of data.bufferViews) assert.ok((view.byteOffset||0)+view.byteLength<=binLength)
    for(const image of data.images||[]) if(image.uri) assert.equal(image.uri,'Textures/colormap.png')
    if(file.startsWith('character')) assert.deepEqual(data.animations.map(x=>x.name),['static','idle','emote-yes'])
  }
  assert.match(readFileSync(new URL('LICENSE.txt',dir),'utf8'),/CC0/)
  assert.equal(JSON.parse(readFileSync(new URL('credits.json',dir),'utf8')).license,'CC0-1.0')
})
test('bone overlays never accumulate and reduced motion preserves static raised/thinking states', () => {
  const model=new Group(), head=new Group(), arm=new Group()
  head.name='head'; arm.name='arm-right'; head.position.y=1
  model.add(head,arm,new Mesh(new BoxGeometry(.6,1.5,.3),new MeshStandardMaterial()))
  const avatar=prepareStudentAvatar(new Scene(),{scene:model,animations:[]},'#ba98eb')
  const state={raised:true,thinking:true,speaking:false,level:0}
  poseStudent(avatar,state,100,1,true)
  const a=avatar.arm.quaternion.clone(),h=avatar.head.quaternion.clone()
  for(let i=0;i<100;i++) poseStudent(avatar,state,100+i,.03,true)
  assert.ok(a.angleTo(avatar.arm.quaternion)<1e-6)
  assert.ok(h.angleTo(avatar.head.quaternion)<1e-6)
  assert.equal(avatar.surface.time.value,0)
  assert.equal(avatar.surface.scan.value,0)
  poseStudent(avatar,{raised:false,thinking:false,speaking:false,level:0},0,0,true)
  assert.ok(avatar.armRest.angleTo(avatar.arm.quaternion)<1e-6)
  avatar.mixer.stopAllAction(); disposeScene(avatar.scene)
})
test('helper is kept inside viewport after dragging or resize', () => {
  assert.deepEqual(boundHelpPosition({x:-10,y:900},{width:375,height:812},{width:56,height:56}),{x:12,y:744})
  assert.deepEqual(boundHelpPosition({x:1200,y:500},{width:700,height:500},{width:360,height:490}),{x:328,y:12})
})
test('recording reuses cached 3D viewports and falls back independently per student', () => {
  const OriginalImage=globalThis.Image
  globalThis.Image=class {complete=true;naturalWidth=100;set src(x){this.source=x}}
  try {
    const frame={width:300,height:150}, draws=[]
    const ctx={fillRect(){},fillText(){},measureText(){return{width:10}},drawImage(...args){draws.push(args)}}
    const paint=createClassroomPainter(()=>({studentFrame:{canvas:frame,slots:{ming:{x:1,y:2,width:99,height:100}}}}))
    paint(ctx,{width:1280,height:720})
    assert.equal(draws[0][0],frame)
    assert.deepEqual(draws[0].slice(1,5),[1,2,99,100])
    assert.match(draws[1][0].source,/yu-listening/)
    assert.match(draws[2][0].source,/lin-listening/)
  } finally {globalThis.Image=OriginalImage}
})
