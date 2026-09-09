import test from 'node:test'
import assert from 'node:assert/strict'

import {
  isInsufficientReport,
  loadAiReviewDraft,
  saveAiReviewDraft,
  selectFeedbackForRoute,
} from '../src/utils/aiReviewState.js'

function createStorage() {
  const values = new Map()
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null
    },
    setItem(key, value) {
      values.set(key, String(value))
    },
    removeItem(key) {
      values.delete(key)
    },
  }
}

test('restores a draft for the same training session', () => {
  const storage = createStorage()
  const now = Date.UTC(2026, 8, 2)

  saveAiReviewDraft(storage, 11, '教师先提问，再等待学生回答。', now)

  assert.equal(loadAiReviewDraft(storage, 11, now + 1000), '教师先提问，再等待学生回答。')
  assert.equal(loadAiReviewDraft(storage, 12, now + 1000), '')
})

test('removes a draft after the 30 day retention period', () => {
  const storage = createStorage()
  const now = Date.UTC(2026, 8, 2)

  saveAiReviewDraft(storage, 11, '课堂转写内容', now)

  assert.equal(loadAiReviewDraft(storage, 11, now + 30 * 24 * 60 * 60 * 1000 - 1), '课堂转写内容')
  assert.equal(loadAiReviewDraft(storage, 11, now + 30 * 24 * 60 * 60 * 1000 + 1), '')
})

test('clearing the input removes the stored draft', () => {
  const storage = createStorage()
  const now = Date.UTC(2026, 8, 2)

  saveAiReviewDraft(storage, 11, '课堂转写内容', now)
  saveAiReviewDraft(storage, 11, '', now + 1000)

  assert.equal(loadAiReviewDraft(storage, 11, now + 2000), '')
})

test('restores the feedback for the requested session instead of the latest history item', () => {
  const items = [
    { id: 20, session_id: 2 },
    { id: 10, session_id: 1 },
  ]

  assert.equal(selectFeedbackForRoute(items, null, 1)?.id, 10)
  assert.equal(selectFeedbackForRoute(items, 20, 1)?.id, 20)
  assert.equal(selectFeedbackForRoute(items, 999, 1)?.id, 10)
})

test('recognizes a legacy all-zero DeepSeek report as insufficient evidence', () => {
  const report = {
    source: 'deepseek',
    dimensions: [
      { score: 0, evidence: '证据不足：没有课堂转写' },
      { score: 0, evidence: '证据不足' },
    ],
  }

  assert.equal(isInsufficientReport(report), true)
  assert.equal(isInsufficientReport({ source: 'deepseek', dimensions: [{ score: 80, evidence: '课堂提问记录' }] }), false)
})
