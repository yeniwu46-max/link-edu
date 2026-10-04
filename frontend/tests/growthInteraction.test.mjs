import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { transformSync } from 'esbuild'
import * as vue from 'vue'

const source = readFileSync(new URL('../src/views/GrowthView.vue', import.meta.url), 'utf8')

test('growth archive exposes real range loading and record navigation', () => {
  assert.match(source, /watch\(range, load\)/)
  assert.match(source, /@click="toggleHeatDay\(cell\)"/)
  assert.match(source, /router\.push\(/)
  assert.match(source, /query\.feedbackId = item\.id/)
  assert.doesNotMatch(source, /sum-demo/)
})

function createGrowth(fetchGrowth) {
  const { descriptor } = parse(source)
  const { code } = transformSync(compileScript(descriptor, { id: 'growth-sync-test' }).content, { format: 'cjs' })
  const navigation = []
  const imports = {
    vue: { ...vue, onMounted() {}, watch() {} },
    'vue-router': { useRouter: () => ({ push: target => navigation.push(target) }) },
    'echarts/core': { use() {} },
    'echarts/renderers': {}, 'echarts/charts': {}, 'echarts/components': {}, 'vue-echarts': {},
    '../services/dashboard': { fetchGrowth },
    '../services/api': { api: { get: async () => ({ data: { items: [] } }) } },
  }
  const module = { exports: {} }
  new Function('require', 'module', 'exports', code)(name => {
    assert.ok(Object.hasOwn(imports, name), `Unexpected import ${name}`)
    return imports[name]
  }, module, module.exports)
  return { state: module.exports.default.setup({}, { expose() {} }), navigation }
}

test('growth heatmap filters the real records and toggles the date off', async () => {
  const data = {
    heatmap: [{ date: '2026-09-13', count: 1, minutes: 8 }],
    records: [{ id: 7, session_id: 3, when: '2026-09-13T10:00:00' }, { id: 8, when: '2026-09-12T10:00:00' }],
    journals: [{ id: 1, body: '真实日志' }],
  }
  const { state, navigation } = createGrowth(async () => data)
  await state.load()
  state.toggleHeatDay(data.heatmap[0])
  assert.deepEqual(state.visibleRecords.value.map(item => item.id), [7])
  state.openRecord(data.records[0])
  assert.deepEqual(navigation[0], { path: '/ai-review', query: { sessionId: 3, feedbackId: 7 } })
  state.toggleHeatDay(data.heatmap[0])
  assert.equal(state.visibleRecords.value.length, 2)
  assert.equal(state.visibleJournals.value[0].body, '真实日志')
})

test('growth loading failure clears old data and never fabricates scores or journals', async () => {
  const { state } = createGrowth(async () => { throw new Error('offline') })
  state.points.value = [{ score: 80 }]
  state.records.value = [{ id: 7 }]
  state.journals.value = [{ id: 1 }]
  await state.load()
  assert.match(state.loadError.value, /加载失败/)
  for (const key of ['points', 'records', 'journals', 'heatmap', 'milestones', 'summaries']) {
    assert.deepEqual(state[key].value, [])
  }
})
