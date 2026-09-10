import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parseCourseId } from '../src/utils/navigation.js'

const courses = await readFile(new URL('../src/views/CoursesView.vue', import.meta.url), 'utf8')
const training = await readFile(new URL('../src/views/TrainingView.vue', import.meta.url), 'utf8')

test('course id parser rejects malformed and non-positive ids', () => {
  assert.equal(parseCourseId('12'), 12)
  assert.equal(parseCourseId(12), 12)
  assert.equal(parseCourseId('0'), null)
  assert.equal(parseCourseId('-1'), null)
  assert.equal(parseCourseId('not-a-number'), null)
  assert.equal(parseCourseId(''), null)
})

test('course page exposes an actionable load failure instead of fake courses', () => {
  assert.match(courses, /courseError/)
  assert.match(courses, /重新加载课程/)
  assert.match(courses, /role="alert"/)
  assert.doesNotMatch(courses, /\[Courses\] fallback/)
  assert.doesNotMatch(courses, /courses\.value = \[\s*\{\s*id: 1/)
})

test('training page does not silently replace an invalid course query', () => {
  assert.match(training, /parseCourseId\(rawId\)/)
  assert.match(training, /courseError/)
  assert.match(training, /课程参数无效|课程不存在/)
  assert.doesNotMatch(training, /\[?\{\s*id: 1,\s*title: '导入技能'/)
})
