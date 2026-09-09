import test, { mock } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { transformSync } from 'esbuild'
import * as vue from 'vue'

import * as reviewErrors from '../src/utils/aiReviewErrors.js'
import * as reviewState from '../src/utils/aiReviewState.js'

const source = readFileSync(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const { code } = transformSync(compileScript(descriptor, { id: 'followup-test' }).content, {
  format: 'cjs',
})

test('AI 评课页面不显示底部历史评分条', () => {
  assert.doesNotMatch(source, /class="history-ticks"/)
  assert.match(source, /class="review-report"/)
})

function createReview() {
  const ask = mock.fn(async (feedbackId) => ({
    feedback_id: feedbackId,
    scope: 'current',
    answer: 'Add classroom observations before requesting a score.',
  }))
  const imports = {
    vue: { ...vue, onMounted() {}, onUnmounted() {}, watch() {} },
    'vue-router': { useRoute: () => ({ query: {} }), useRouter: () => ({}) },
    '@number-flow/vue': {},
    'echarts/core': { use() {} },
    'echarts/renderers': {},
    'echarts/charts': {},
    'echarts/components': {},
    'vue-echarts': {},
    '../components/fx/SplitTitle.vue': {},
    '../services/dashboard': { askAiReviewQuestion: ask },
    '../utils/aiReviewErrors': reviewErrors,
    '../utils/aiReviewState': reviewState,
    '../utils/settings': { loadSettings: () => ({ showDemoBadge: true }) },
  }
  const module = { exports: {} }
  // Execute the actual SFC setup, stubbing browser lifecycle and external services.
  new Function('require', 'module', 'exports', code)((name) => {
    assert.ok(Object.hasOwn(imports, name), `Unexpected import: ${name}`)
    return imports[name]
  }, module, module.exports)
  const state = module.exports.default.setup({}, { expose() {} })
  return { state, ask }
}

function completedReport(overrides = {}) {
  return {
    source: 'deepseek',
    demo: false,
    generation_status: 'succeeded',
    insufficient_evidence: true,
    overall_score: null,
    dimensions: [{ key: 'clarity', score: 0, evidence: 'No classroom evidence.' }],
    ...overrides,
  }
}

test('a completed report with insufficient evidence allows follow-up without changing scores', async () => {
  const { state, ask } = createReview()
  state.current.value = { id: 7, session_id: 3, overall_score: null, report: completedReport() }
  const originalFeedback = JSON.stringify(state.current.value)
  state.questionDraft.value = 'What classroom evidence should I provide?'

  assert.equal(state.insufficientEvidence.value, true)
  assert.equal(state.followupReady.value, true)
  assert.equal(state.canAskQuestion.value, true)
  await state.askQuestion()

  assert.equal(ask.mock.callCount(), 1)
  assert.deepEqual(ask.mock.calls[0].arguments, [7, state.questionDraft.value])
  assert.match(state.questionAnswer.value, /classroom observations/)
  assert.equal(state.questionError.value, '')
  assert.equal(JSON.stringify(state.current.value), originalFeedback)
  assert.equal(state.insufficientEvidence.value, true)
})

test('a completed scorable report still allows follow-up', () => {
  const { state } = createReview()
  state.current.value = {
    id: 7,
    report: completedReport({
      insufficient_evidence: false,
      overall_score: 82,
      dimensions: [{ key: 'clarity', score: 82, evidence: 'Classroom observations.' }],
    }),
  }

  assert.equal(state.followupReady.value, true)
})

test('missing, demo, generating and failed reports still reject follow-up', async () => {
  for (const report of [
    null,
    completedReport({ demo: true }),
    completedReport({ source: 'demo' }),
    completedReport({ generation_status: 'generating' }),
    completedReport({ generation_status: 'failed' }),
    completedReport({ generation_status: undefined }),
  ]) {
    const { state, ask } = createReview()
    state.current.value = report ? { id: 7, report } : null
    state.questionDraft.value = 'How should I improve?'

    assert.equal(state.followupReady.value, false)
    assert.equal(state.canAskQuestion.value, false)
    await state.askQuestion()
    assert.equal(ask.mock.callCount(), 0)
    assert.notEqual(state.questionError.value, '')
  }
})

test('regenerating a completed report disables follow-up', async () => {
  const { state, ask } = createReview()
  state.current.value = { id: 7, report: completedReport() }
  state.aiGenerating.value = true
  state.questionDraft.value = 'How should I improve?'

  assert.equal(state.followupReady.value, false)
  await state.askQuestion()
  assert.equal(ask.mock.callCount(), 0)
})

test('an empty question is still rejected for an insufficient-evidence report', async () => {
  const { state, ask } = createReview()
  state.current.value = { id: 7, report: completedReport() }
  state.questionDraft.value = '   '

  assert.equal(state.followupReady.value, true)
  await state.askQuestion()
  assert.equal(ask.mock.callCount(), 0)
  assert.notEqual(state.questionError.value, '')
})
