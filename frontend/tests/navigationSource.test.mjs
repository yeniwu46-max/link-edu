import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const appShell = await readFile(new URL('../src/layouts/AppShell.vue', import.meta.url), 'utf8')
const courses = await readFile(new URL('../src/views/CoursesView.vue', import.meta.url), 'utf8')
const main = await readFile(new URL('../src/main.js', import.meta.url), 'utf8')

test('global search submits a normalized route and cleans its outside-click listener', () => {
  assert.match(appShell, /<form[^>]+class="cir-search"[^>]+@submit\.prevent="goSearch"/)
  assert.match(appShell, /buildSearchLocation\(search\.value\)/)
  assert.match(appShell, /onUnmounted\(\(\) =>/)
  assert.match(appShell, /window\.removeEventListener\('click', closeMenu\)/)
})

test('course search renders explicit hit and empty-result feedback', () => {
  assert.match(courses, /filterCourses\(courses\.value, query\.value, filter\.value\)/)
  assert.match(courses, /搜索“\{\{ query \}\}”/)
  assert.match(courses, /没有找到“\$\{query\}”相关课程/)
  assert.match(courses, /role="status"/)
})

test('router has a visible fallback for unknown deep links', () => {
  assert.match(main, /path:\s*'\/:pathMatch\(\.\*\)\*'/)
  assert.match(main, /redirect:\s*'\/'/)
})
