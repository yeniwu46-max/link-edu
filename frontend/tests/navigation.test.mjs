import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildSearchLocation,
  filterCourses,
  normalizeSearchQuery,
} from '../src/utils/navigation.js'

const courses = [
  {
    id: 1,
    title: '导入技能',
    category: '微格教学 · 专项',
    stage: '专项01 · 导入',
    description: '新课开始时把学生带进课题。',
  },
  {
    id: 2,
    title: '板书板画技能',
    category: '微格教学 · 专项',
    stage: '专项02 · 板书',
    description: '把教学信息留在黑板上。',
  },
]

test('normalizes search text and produces a routable location', () => {
  assert.equal(normalizeSearchQuery('  导入   技能  '), '导入 技能')
  assert.deepEqual(buildSearchLocation('  导入  '), {
    path: '/courses',
    query: { q: '导入' },
  })
  assert.deepEqual(buildSearchLocation('   '), { path: '/courses' })
})

test('filters course results case-insensitively across searchable fields', () => {
  assert.deepEqual(filterCourses(courses, '板书').map((item) => item.id), [2])
  assert.deepEqual(filterCourses(courses, '  导入  ').map((item) => item.id), [1])
  assert.deepEqual(filterCourses(courses, '不存在'), [])
})

