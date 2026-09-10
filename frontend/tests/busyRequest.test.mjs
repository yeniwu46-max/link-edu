import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import { shouldTrackBusy } from '../src/utils/busyRequest.js'
import {
  aiReviewErrorMessage,
  aiReviewQuestionErrorMessage,
  isUnauthorizedError,
} from '../src/utils/aiReviewErrors.js'

test('skips the global busy overlay for DeepSeek generation requests', () => {
  assert.equal(shouldTrackBusy({ skipBusy: true }), false)
  assert.equal(shouldTrackBusy({}), true)
})

test('AI review input has no browser character limit', async () => {
  const source = await readFile(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /<textarea[\s\S]*maxlength=/)
  assert.doesNotMatch(source, /aiDraft\.trim()\.length\/12000/)
})

test('training completion does not trigger DeepSeek before entering AI review', async () => {
  const source = await readFile(new URL('../src/views/TrainingView.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /generateAiReview/)
  assert.doesNotMatch(source, /课堂记录（可选）/)
})

test('maps AI review request failures to actionable messages', () => {
  assert.equal(isUnauthorizedError({ response: { status: 401 } }), true)
  assert.equal(aiReviewErrorMessage({ response: { status: 401 } }), '登录状态已失效，请重新登录后再生成 AI 评课。')
  assert.equal(aiReviewErrorMessage({ response: { status: 502 } }), 'DeepSeek 暂时没有生成报告，请检查服务配置后重试。')
  assert.equal(aiReviewErrorMessage({ code: 'ECONNABORTED' }), '请求超时，正在核对服务端状态，请稍后刷新。')
  assert.equal(aiReviewErrorMessage({}), '网络暂时不可用，请检查连接后重试。')
  assert.equal(aiReviewQuestionErrorMessage({ response: { status: 401 } }), '登录状态已失效，请重新登录后再追问。')
  assert.equal(aiReviewQuestionErrorMessage({ response: { status: 409 } }), '请先生成成功的 DeepSeek 评课报告后再追问。')
  assert.equal(aiReviewQuestionErrorMessage({ response: { status: 429 } }), '追问请求过于频繁，请稍后再试。')
  assert.equal(aiReviewQuestionErrorMessage({ response: { status: 502 } }), 'DeepSeek 暂时没有回答，请稍后再试。')
  assert.equal(aiReviewQuestionErrorMessage({ code: 'ETIMEDOUT' }), '追问请求超时，请稍后再试。')
  assert.equal(aiReviewQuestionErrorMessage({}), '网络暂时不可用，请检查连接后重试。')
})

test('AI review service sets explicit generation and follow-up timeouts', async () => {
  const source = await readFile(new URL('../src/services/dashboard.js', import.meta.url), 'utf8')
  assert.match(source, /ai-review[\s\S]*timeout: 75_000/)
  assert.match(source, /feedbacks[\s\S]*ask[\s\S]*timeout: 45_000/)
})

test('AI review page keeps the report visible when evidence is insufficient', async () => {
  const source = await readFile(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')

  assert.match(source, /class="review-report" v-if="current"/)
  assert.doesNotMatch(source, /class="review-report" v-if="current && !insufficientEvidence"/)
})

test('AI review page does not silently fall back to demo data after loading fails', async () => {
  const source = await readFile(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')

  assert.match(source, /isUnauthorizedError/)
  assert.match(source, /localStorage\.removeItem\('link_token'\)/)
  assert.doesNotMatch(source, /items\.value = \[\s*\{\s*id: 1/)
})

test('AI review page reports a missing session instead of silently returning', async () => {
  const source = await readFile(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')

  assert.match(source, /暂无可生成的训练记录/)
  assert.match(source, /router\.replace\(\{\s*path: '\/ai-review'/)
})

test('AI review page exposes history selection and material recovery controls', async () => {
  const source = await readFile(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')
  assert.match(source, /aria-label="选择评课报告"/)
  assert.match(source, /loadAiReviewMaterials/)
  assert.match(source, /saveAiReviewMaterials/)
  assert.match(source, /isGenerationTimedOut/)
  assert.match(source, /生成超时/)
})
