import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = await readFile(new URL('../src/views/ProfileView.vue', import.meta.url), 'utf8')

test('profile actions show success only after the real request succeeds', () => {
  assert.match(view, /saved\.value = false/)
  assert.match(view, /saveError\.value = error\?\.response\?\.data\?\.message/)
  assert.doesNotMatch(view, /catch \{\s*saved\.value = true/)
})

test('copy and contact actions expose real failure states', () => {
  assert.match(view, /copyError/)
  assert.match(view, /navigator\.clipboard\?\.writeText/)
  assert.match(view, /journalSubmitErrorMessage\(error\)/)
  assert.match(view, /messageError/)
  assert.doesNotMatch(view, /纯前端成功态也算完成演示/)
})

test('settings are loaded and saved through the persistent browser preference helpers', () => {
  assert.match(view, /reactive\(loadSettings\(\)\)/)
  assert.match(view, /saveSettings\(\{ \.\.\.settings \}\)/)
  assert.match(view, /resetSettings\(\)/)
})
