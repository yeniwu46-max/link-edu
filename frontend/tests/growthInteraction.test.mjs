import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/GrowthView.vue', import.meta.url), 'utf8')

test('growth archive exposes real range loading and record navigation', () => {
  assert.match(source, /watch\(range, load\)/)
  assert.match(source, /@click="selectedDate = cell\.date"/)
  assert.match(source, /router\.push\(/)
  assert.match(source, /feedbackId: item\.id/)
  assert.doesNotMatch(source, /sum-demo/)
})
