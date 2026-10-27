import test from 'node:test'
import assert from 'node:assert/strict'
import { courseSkill, deskCourses, preferredCourse } from '../src/services/courseDesk.js'
import { classroomEntry } from '../src/services/classroomEntry.js'
const courses = [
  {id:11,title:'结构化讲授',stage:'专项04 · 讲解',status:'not_started'},
  {id:12,title:'讲解与举例',stage:'专项04',status:'in_progress'},
  {id:20,title:'黑板设计',stage:'专项02 · 板书'},
  {id:31,title:'完整课堂',stage:'综合11'},
  {id:40,title:'其他课程',stage:'拓展'},
]
test('desk maps stable stage ids, keeping uncategorized courses available in the directory', () => {
  assert.equal(courseSkill(courses[0]), '专项04')
  assert.equal(courseSkill(courses[3]), '综合')
  assert.equal(courseSkill(courses[4]), null)
  assert.equal(deskCourses(courses).length, 5)
})
test('search combines course text and physical object labels without duplicate courses', () => {
  assert.deepEqual(deskCourses(courses, '书本').map(c=>c.id), [11,12])
  assert.deepEqual(deskCourses(courses, '板书').map(c=>c.id), [20])
  assert.deepEqual(deskCourses(courses, '举例').map(c=>c.id), [12])
  assert.deepEqual(deskCourses(courses, '不存在'), [])
})
test('selection preserves the current course then prefers in-progress, never fabricates a course', () => {
  assert.equal(preferredCourse(courses)?.id, 12)
  assert.equal(preferredCourse(courses, '11')?.id, 11)
  assert.equal(preferredCourse([]), null)
})
test('course navigation preserves valid identity and duration but never auto-start or invalid ids', () => {
  assert.deepEqual(classroomEntry({query:{courseId:'12',mode:'fragment',start:'1'}}), {path:'/classroom',query:{courseId:'12',mode:'fragment'}})
  for(const courseId of ['0','bad',['12']]) assert.deepEqual(classroomEntry({query:{courseId}}), {path:'/classroom',query:{}})
})
