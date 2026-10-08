import test from 'node:test'
import assert from 'node:assert/strict'
import { createModelDrag } from '../src/utils/modelDrag.js'

function surface() {
  let captured = null
  return {clientWidth:200, setPointerCapture(id){captured=id}, hasPointerCapture(id){return captured===id}, releasePointerCapture(){captured=null}}
}
const point = (x,y=0) => ({button:0,isPrimary:true,pointerId:7,clientX:x,clientY:y})

test('rotation drag suppresses the trailing click but allows keyboard selection', () => {
  const deltas=[], element=surface(), drag=createModelDrag((id,value)=>deltas.push([id,value]))
  drag.down(point(10),element,'ming')
  assert.equal(drag.move(point(13)),false)
  assert.equal(drag.move(point(45)),true)
  assert.equal(deltas[0][0],'ming')
  assert.ok(deltas[0][1]>0)
  assert.equal(element.hasPointerCapture(7),true)
  drag.end(point(45))
  assert.equal(element.hasPointerCapture(7),false)
  let prevented=false
  assert.equal(drag.suppress({detail:1,preventDefault(){prevented=true},stopPropagation(){}}),true)
  assert.equal(prevented,true)
  assert.equal(drag.suppress({detail:0}),false)
})

test('a tap keeps selection, while a vertical touch gesture keeps scrolling', () => {
  const deltas=[], drag=createModelDrag((...args)=>deltas.push(args))
  drag.down(point(10),surface(),'yu'); drag.end(point(10))
  assert.equal(drag.suppress({detail:1}),false)
  drag.down(point(10),surface(),'yu')
  assert.equal(drag.move(point(12,20)),false)
  assert.equal(drag.move(point(60,21)),false)
  assert.deepEqual(deltas,[])
})

test('unmount or cancellation releases captured pointer and ends rotation', () => {
  const element=surface(), drag=createModelDrag(()=>{})
  drag.down(point(0),element); drag.move(point(20)); drag.cancel()
  assert.equal(element.hasPointerCapture(7),false)
  assert.equal(drag.move(point(50)),false)
})
