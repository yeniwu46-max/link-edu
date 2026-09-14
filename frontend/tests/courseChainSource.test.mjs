import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parseCourseId } from '../src/utils/navigation.js'
import { featuredMoocs, moocByStage, moocForCourse } from '../src/data/moocCourses.js'

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

test('course center wires curated MOOC extend links without the old mislabeled hardcode', () => {
  assert.match(courses, /featuredMoocs/)
  assert.match(courses, /moocForCourse/)
  assert.match(courses, /慕课延伸/)
  assert.doesNotMatch(courses, /延伸：智慧树微格课/)
  assert.doesNotMatch(courses, /const SMART_EDU/)
  assert.equal(featuredMoocs.length, 5)
  assert.equal(Object.keys(moocByStage).length, 11)
  assert.equal(
    moocForCourse({ stage: '专项01 · 导入' })?.url,
    'https://www.icourse163.org/course/icourse-1002419002',
  )
  assert.equal(
    moocForCourse({ stage: '综合10 · 模拟授课' })?.url,
    'https://higher.smartedu.cn/course/671ad61416d8a05eedca49d6',
  )
  assert.match(moocForCourse({ stage: '综合11 · 教资试讲' })?.label || '', /中国大学MOOC/)
})
