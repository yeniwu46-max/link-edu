import test from 'node:test'
import assert from 'node:assert/strict'
import { createMotionPreferences, motionQuality, tiltFromPoint } from '../src/utils/motionPreferences.js'

function environment() {
  const media = new Map()
  const document = new EventTarget()
  document.visibilityState = 'visible'
  return {
    document,
    media,
    matchMedia(query) {
      if (!media.has(query)) {
        const target = new EventTarget()
        target.matches = query.includes('pointer: fine')
        target.listeners = 0
        const add = target.addEventListener.bind(target), remove = target.removeEventListener.bind(target)
        target.addEventListener = (...args) => { target.listeners++; add(...args) }
        target.removeEventListener = (...args) => { target.listeners--; remove(...args) }
        media.set(query, target)
      }
      return media.get(query)
    },
  }
}

test('effects share preference listeners and release them after the last consumer leaves', () => {
  const browser = environment(), preferences = createMotionPreferences(browser), first = [], second = []
  const off1 = preferences.subscribe(value => first.push(value))
  const off2 = preferences.subscribe(value => second.push(value))
  const reduce = browser.media.get('(prefers-reduced-motion: reduce)')
  assert.equal(reduce.listeners, 1)
  reduce.matches = true
  reduce.dispatchEvent(new Event('change'))
  assert.equal(first.at(-1).reducedMotion, true)
  assert.equal(second.at(-1).reducedMotion, true)
  browser.document.visibilityState = 'hidden'
  browser.document.dispatchEvent(new Event('visibilitychange'))
  assert.equal(first.at(-1).visible, false)
  off1()
  assert.equal(reduce.listeners, 1)
  off2()
  assert.equal(reduce.listeners, 0)
  assert.equal(browser.media.get('(hover: hover) and (pointer: fine)').listeners, 0)
})

test('remount reads current system preferences without stale subscriptions', () => {
  const browser = environment(), preferences = createMotionPreferences(browser)
  const off = preferences.subscribe(() => {})
  off()
  browser.media.get('(prefers-reduced-motion: reduce)').matches = true
  browser.document.visibilityState = 'hidden'
  const values = []
  const again = preferences.subscribe(value => values.push(value))
  assert.equal(values[0].reducedMotion, true)
  assert.equal(values[0].visible, false)
  again()
})

test('pointer tilt is bounded even after pointer capture or a card moves', () => {
  const rect = { left: 40, top: 60, width: 200, height: 100 }
  assert.deepEqual(tiltFromPoint(rect, 140, 110), { x: 0, y: 0, lightX: 50, lightY: 50 })
  assert.deepEqual(tiltFromPoint(rect, -1000, 2000, 6), { x: -6, y: -6, lightX: 0, lightY: 100 })
  assert.deepEqual(tiltFromPoint({ width: 0, height: 0 }, 2, 2), { x: 0, y: 0, lightX: 50, lightY: 50 })
})

test('touch and sustained slow rendering lower quality while retaining the 3D scene', () => {
  assert.deepEqual(motionQuality(true), { fps: 60, pixelRatio: 1.5 })
  assert.deepEqual(motionQuality(false), { fps: 30, pixelRatio: 1 })
  assert.deepEqual(motionQuality(true, true), { fps: 30, pixelRatio: 1 })
})
