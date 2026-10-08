import test, { mock } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { transformSync } from 'esbuild'
import * as vue from 'vue'
import * as dashboardState from '../src/utils/dashboardState.js'
import { useReducedMotion } from '../src/utils/useReducedMotion.js'

const { descriptor } = parse(readFileSync(new URL('../src/views/DashboardView.vue', import.meta.url), 'utf8'))
const { code } = transformSync(compileScript(descriptor, { id: 'dashboard-test' }).content, { format: 'cjs' })

function createDashboard(overrides = {}) {
  const api = {
    fetchDashboardOverview: mock.fn(async () => ({})),
    addJournal: mock.fn(async (payload) => ({ id: 42, ...payload })),
    regenerateFeedback: mock.fn(async () => ({ id: 13, overall_score: 82 })),
    ...overrides,
  }
  const router = { push: mock.fn() }
  const imports = {
    vue: { ...vue, onMounted() {}, onUnmounted() {} },
    'vue-router': { useRouter: () => router },
    'echarts/core': { use() {} },
    'echarts/renderers': {},
    'echarts/charts': {},
    'echarts/components': {},
    'vue-echarts': {},
    '../services/dashboard': api,
    '../stores/auth': { useAuthStore: () => ({ user: { name: 'Test User' } }) },
    '../utils/greeting': { formatGreeting: () => ({ title: 'Hello', name: 'Test User' }) },
    '../utils/dashboardState': dashboardState,
    '../utils/useReducedMotion.js': { useReducedMotion },
    '../components/LearnMoreButton.vue': {},
    '../components/SummaryCard.vue': {},
  }
  const module = { exports: {} }
  new Function('require', 'module', 'exports', code)((name) => {
    assert.ok(Object.hasOwn(imports, name), `Unexpected import: ${name}`)
    return imports[name]
  }, module, module.exports)
  return { state: module.exports.default.setup({}, { expose() {} }), api, router }
}

const snapshot = {
  weekly_training: { sessions: 1, total_minutes: 8, journals: [{ id: 9, body: 'Saved journal' }] },
  continue_training: { id: 11, course_id: 7, course_title: 'Test Course' },
  ai_feedback: { id: 13, overall_score: 82 },
  quick_entries: [{ title: 'Courses', route: '/courses' }],
  growth_trajectory: [82],
  growth_records: [{ id: 13, date: '09/09', overall_score: 82 }],
}

test('initial dashboard never exposes demo training or scores', () => {
  const { state } = createDashboard()
  assert.equal(state.dashboardStatus.value, 'loading')
  assert.equal(state.continueTraining.value, null)
  assert.equal(state.aiFeedback.value, null)
  assert.deepEqual(state.growthTrajectory.value, [])
})

test('a successful empty response clears the previous overview', async () => {
  let result = snapshot
  const { state } = createDashboard({ fetchDashboardOverview: async () => result })
  await state.loadDashboard()
  assert.equal(state.continueTraining.value.course_id, 7)
  result = {}
  await state.loadDashboard()
  assert.equal(state.dashboardStatus.value, 'ready')
  assert.equal(state.continueTraining.value, null)
  assert.equal(state.aiFeedback.value, null)
  assert.equal(state.weekly.value.sessions, 0)
  assert.deepEqual(state.weekly.value.journals, [])
})

test('failed overview loads remain failures without fabricated data', async () => {
  const { state } = createDashboard({
    fetchDashboardOverview: async () => { throw { response: { status: 503, data: { message: 'Unavailable' } } } },
  })
  await state.loadDashboard()
  assert.equal(state.dashboardStatus.value, 'error')
  assert.equal(state.dashboardError.value, 'Unavailable')
  assert.equal(state.continueTraining.value, null)
  assert.deepEqual(state.growthRecords.value, [])
})

test('continue training uses the server course id', async () => {
  const { state, router } = createDashboard({ fetchDashboardOverview: async () => snapshot })
  await state.loadDashboard()
  state.resumeTraining()
  assert.deepEqual(router.push.mock.calls[0].arguments[0], { path: '/training', query: { courseId: 7 } })
})

test('heatmap selection uses the selected date count and minutes', () => {
  const { state } = createDashboard()
  state.weekly.value.heatmap = [{ date: '2026-09-09', count: 2, minutes: 16 }]
  state.pickedDay.value = '2026-09-09'
  assert.equal(state.dayHint.value, '2026-09-09 训练 2 次，共 16 分钟。')
})

test('journal failure preserves the draft and the saved journal list', async () => {
  const { state } = createDashboard({
    addJournal: async () => { throw new Error('offline') },
  })
  state.weekly.value.journals = [{ id: 9, body: 'Existing' }]
  state.journalBody.value = 'Unsaved draft'
  await state.submitJournal()
  assert.equal(state.journalBody.value, 'Unsaved draft')
  assert.deepEqual(state.weekly.value.journals, [{ id: 9, body: 'Existing' }])
  assert.notEqual(state.journalError.value, '')
  assert.equal(state.journalSaving.value, false)
})

test('journal requests are single-flight and use the selected date', async () => {
  let resolve
  const pending = new Promise((done) => { resolve = done })
  const { state, api } = createDashboard({ addJournal: mock.fn(() => pending) })
  state.journalBody.value = 'Saved draft'
  state.pickedDay.value = '2026-09-09'
  const first = state.submitJournal()
  await state.submitJournal()
  assert.equal(api.addJournal.mock.callCount(), 1)
  assert.deepEqual(api.addJournal.mock.calls[0].arguments[0], { entry_date: '2026-09-09', body: 'Saved draft' })
  resolve({ id: 42, entry_date: '2026-09-09', body: 'Saved draft' })
  await first
  assert.equal(state.weekly.value.journals[0].id, 42)
  assert.equal(state.journalBody.value, '')
})

test('failed regeneration preserves the original report and never reports success', async () => {
  const { state } = createDashboard({
    regenerateFeedback: async () => { throw { response: { status: 409, data: { message: 'Read-only report' } } } },
  })
  state.aiFeedback.value = { id: 13, overall_score: 82 }
  state.regenOk.value = true
  await state.doRegenerate()
  assert.deepEqual(state.aiFeedback.value, { id: 13, overall_score: 82 })
  assert.equal(state.regenOk.value, false)
  assert.equal(state.regenError.value, 'Read-only report')
})

test('repeated regeneration cannot issue concurrent requests', async () => {
  let resolve
  const pending = new Promise((done) => { resolve = done })
  const { state, api } = createDashboard({ regenerateFeedback: mock.fn(() => pending) })
  state.aiFeedback.value = { id: 13, overall_score: 82 }
  const first = state.doRegenerate()
  const second = state.doRegenerate()
  const calls = api.regenerateFeedback.mock.callCount()
  resolve({ id: 13, overall_score: 83 })
  await Promise.all([first, second])
  assert.equal(calls, 1)
})

test('growth chart nodes open the exact feedback record', () => {
  const { state, router } = createDashboard()
  state.growthRecords.value = [{ id: 13, date: '09/09', overall_score: 82 }]
  state.onGrowthChartClick({ dataIndex: 0 })
  assert.deepEqual(router.push.mock.calls[0]?.arguments[0], { path: '/ai-review', query: { feedbackId: 13 } })
})
