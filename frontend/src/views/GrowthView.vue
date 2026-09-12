<template>
  <div class="sparse-page page-growth">
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">TRAJECTORY</p>
        <h1 class="split-title">成长档案</h1>
        <p class="page-lead">工作台里点开的热力图和回放，完整版在这里。</p>
      </div>
      <router-link class="ghost-link growth-head__link" to="/ai-review">查看评课 →</router-link>
    </header>

    <div class="page-scroll">
      <p class="growth-alert">
        以下轨迹保留旧演示 / 规则评分。真实 AI 课堂按证据覆盖评价，不与此分数直接比较。
        <router-link to="/classroom">查看真实课堂记录 →</router-link>
      </p>

      <div class="growth-dash">
        <section class="growth-chart-panel glass" aria-label="得分趋势">
          <div class="growth-chart-panel__head">
            <div>
              <h2>得分趋势</h2>
              <p>{{ rangeLabel }}</p>
            </div>
            <div class="range-switch">
              <button type="button" :class="{ active: range === '7d' }" @click="range = '7d'">7 日</button>
              <button type="button" :class="{ active: range === '30d' }" @click="range = '30d'">30 日</button>
              <button type="button" :class="{ active: range === 'all' }" @click="range = 'all'">全部</button>
            </div>
          </div>
          <VChart class="growth-line" :option="lineOption" autoresize />
        </section>

        <section class="growth-heat-panel glass" aria-label="训练日历">
          <div class="growth-heat-panel__head">
            <div>
              <h2>训练日历</h2>
              <p>{{ heatSummaryText }}</p>
            </div>
            <div class="growth-heat-legend" aria-hidden="true">
              <span>少</span>
              <i data-level="0"></i>
              <i data-level="1"></i>
              <i data-level="2"></i>
              <i data-level="3"></i>
              <i data-level="4"></i>
              <span>多</span>
            </div>
          </div>

          <div class="growth-heat-weekdays" aria-hidden="true">
            <span v-for="day in heatWeekdays" :key="day">{{ day }}</span>
          </div>
          <div class="growth-heat-grid">
            <button
              v-for="cell in paddedHeatmap"
              :key="cell.key"
              type="button"
              :disabled="cell.placeholder"
              :class="{
                on: cell.count > 0,
                selected: cell.date && cell.date === selectedHeatDate,
                muted: cell.placeholder,
              }"
              :title="cell.placeholder ? '' : heatCellTitle(cell)"
              @click="toggleHeatDay(cell)"
            >
              <i :data-level="cell.level || 0"></i>
              <em v-if="!cell.placeholder">{{ cell.dayLabel }}</em>
            </button>
          </div>

          <p v-if="selectedHeatCell" class="growth-heat-detail">
            <strong>{{ selectedHeatCell.label || selectedHeatCell.date }}</strong>
            训练 {{ selectedHeatCell.count || 0 }} 次
            · 约 {{ selectedHeatCell.minutes || 0 }} 分钟
            <button type="button" class="ghost-link" @click="clearHeatFilter">清除筛选</button>
          </p>
        </section>

        <div class="growth-split">
          <section class="growth-records glass" aria-label="训练回放记录">
            <div class="growth-records__head">
              <div>
                <h2>训练记录</h2>
                <p v-if="selectedHeatDate">已按 {{ selectedHeatCell?.label || selectedHeatDate }} 筛选</p>
                <p v-else-if="featuredSummary">{{ featuredSummary.tag || '近期小结' }} · {{ featuredSummary.title }}</p>
              </div>
              <button
                v-if="filteredRecords.length > recordLimit"
                type="button"
                class="ghost-link"
                @click="showAllRecords = !showAllRecords"
              >
                {{ showAllRecords ? '收起' : '显示全部' }} →
              </button>
            </div>

            <p v-if="featuredSummary && !selectedHeatDate" class="growth-summary-strip">
              <strong>{{ featuredSummary.highlight || featuredSummary.caption }}</strong>
              <span>{{ featuredSummary.body }}</span>
            </p>

            <ol v-if="visibleRecords.length" class="growth-record-list">
              <li v-for="item in visibleRecords" :key="item.id">
                <button type="button" @click="openRecord(item)">
                  <span class="growth-record__mark" :data-tier="scoreTier(item.overall_score)" aria-hidden="true">
                    {{ scoreMark(item.overall_score) }}
                  </span>
                  <span class="growth-record__body">
                    <strong>{{ item.course_title || '未命名课程' }}</strong>
                    <em>{{ item.suggestion || '暂无改进建议' }}</em>
                  </span>
                  <span class="growth-record__meta">
                    <b :data-tier="scoreTier(item.overall_score)">{{ item.overall_score ?? '—' }} 分</b>
                    <time>{{ item.date }} {{ item.time }}</time>
                  </span>
                </button>
              </li>
            </ol>
            <p v-else class="dock-hint">{{ selectedHeatDate ? '这一天暂无评课记录。' : '该区间暂无训练记录。' }}</p>

            <div class="growth-journals">
              <div class="growth-records__head">
                <div>
                  <h2>训练日志</h2>
                  <p>接口已归档的短记，只读展示</p>
                </div>
              </div>
              <ul v-if="visibleJournals.length" class="growth-journal-list">
                <li v-for="item in visibleJournals" :key="item.id">
                  <time>{{ formatJournalDate(item.entry_date) }}</time>
                  <p>{{ item.body }}</p>
                </li>
              </ul>
              <p v-else class="dock-hint">暂无训练日志。完成训练后可在后续版本写入一句复盘。</p>
            </div>
          </section>

          <aside class="growth-side glass" aria-label="里程碑">
            <h2>成长里程碑</h2>
            <ul class="growth-side__milestones">
              <li v-for="item in milestones" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <em>{{ item.hint }}</em>
              </li>
            </ul>

            <div class="growth-skill">
              <h3>能力对比</h3>
              <p class="growth-skill__hint">末次评分 vs 区间均值</p>
              <ul v-if="skillCompare.length">
                <li v-for="item in skillCompare" :key="item.key">
                  <div class="growth-skill__row">
                    <span>{{ item.label }}</span>
                    <b>{{ item.latest }} · 均 {{ item.avg }}</b>
                  </div>
                  <div class="growth-skill__bars" aria-hidden="true">
                    <i class="is-avg" :style="{ width: `${item.avg}%` }"></i>
                    <i class="is-latest" :style="{ width: `${item.latest}%` }"></i>
                  </div>
                </li>
              </ul>
              <p v-else class="dock-hint">生成有效评课后可看能力对比。</p>
            </div>

            <p class="growth-side__note">把趋势里的薄弱点带回专项训练，下一轮再看曲线抬升。</p>
            <button type="button" class="primary growth-side__cta" @click="goTraining">去训练</button>
            <router-link class="ghost-link" to="/classroom">真实课堂证据报告 →</router-link>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { fetchGrowth } from '../services/dashboard'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const router = useRouter()
const range = ref('30d')
const points = ref([])
const milestones = ref([])
const heatmap = ref([])
const records = ref([])
const summaries = ref([])
const journals = ref([])
const showAllRecords = ref(false)
const recordLimit = 6
const selectedPointIndex = ref(-1)
const selectedHeatDate = ref('')
const heatWeekdays = ['一', '二', '三', '四', '五', '六', '日']

const rangeLabel = computed(() => ({
  '7d': '近 7 日轨迹',
  '30d': '近 30 日轨迹',
  all: '全部训练轨迹',
}[range.value] || '训练轨迹'))

const featuredSummary = computed(() => summaries.value[0] || null)

const paddedHeatmap = computed(() => {
  const cells = heatmap.value || []
  if (!cells.length) return []
  const first = parseIsoDate(cells[0].date)
  const startPad = first ? (first.getDay() + 6) % 7 : 0
  const padded = []
  for (let index = 0; index < startPad; index += 1) {
    padded.push({ key: `pad-${index}`, placeholder: true, count: 0, level: 0 })
  }
  cells.forEach((cell) => {
    const day = parseIsoDate(cell.date)
    padded.push({
      ...cell,
      key: cell.date,
      placeholder: false,
      dayLabel: day ? String(day.getDate()) : (cell.label || '').replace(/^0/, ''),
    })
  })
  return padded
})

const selectedHeatCell = computed(() => (
  heatmap.value.find((cell) => cell.date === selectedHeatDate.value) || null
))

const heatSummaryText = computed(() => {
  const total = heatmap.value.reduce((sum, cell) => sum + (cell.count || 0), 0)
  const activeDays = heatmap.value.filter((cell) => cell.count > 0).length
  if (selectedHeatCell.value) {
    return `已选 ${selectedHeatCell.value.label || selectedHeatCell.value.date}`
  }
  return `${activeDays} 天有训 · 共 ${total} 次`
})

const filteredRecords = computed(() => {
  if (!selectedHeatDate.value) return records.value
  return records.value.filter((item) => recordMatchesHeatDate(item, selectedHeatDate.value))
})

const visibleRecords = computed(() => (
  showAllRecords.value ? filteredRecords.value : filteredRecords.value.slice(0, recordLimit)
))

const visibleJournals = computed(() => journals.value.slice(0, 5))

const skillCompare = computed(() => {
  const source = points.value.filter((item) => (
    Number.isFinite(Number(item.clarity))
    || Number.isFinite(Number(item.pace))
    || Number.isFinite(Number(item.interaction))
  ))
  if (!source.length) {
    const dims = records.value.find((item) => item.dimensions?.length)?.dimensions || []
    if (!dims.length) return []
    return dims.slice(0, 6).map((item) => ({
      key: item.key || item.label,
      label: item.label || item.key,
      latest: Math.round(Number(item.score) || 0),
      avg: Math.round(Number(item.score) || 0),
    }))
  }
  const latest = source[source.length - 1]
  const keys = [
    { key: 'clarity', label: '表达清晰度' },
    { key: 'pace', label: '教学节奏' },
    { key: 'interaction', label: '互动设计' },
  ]
  return keys.map((item) => {
    const values = source
      .map((row) => Number(row[item.key]))
      .filter((value) => Number.isFinite(value))
    const avg = values.length
      ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
      : 0
    return {
      key: item.key,
      label: item.label,
      latest: Math.round(Number(latest[item.key]) || 0),
      avg,
    }
  })
})

const lineOption = computed(() => {
  const scores = points.value.map((item) => item.score)
  const highlight = selectedPointIndex.value >= 0
    ? selectedPointIndex.value
    : Math.max(scores.length - 1, 0)
  return {
    animationDuration: 800,
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#9d97a3', fontSize: 11 },
      data: ['综合分'],
    },
    grid: { left: 8, right: 12, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#120f16',
      borderColor: 'rgba(255,255,255,.16)',
      textStyle: { color: '#f4f2f6' },
      formatter(params) {
        const point = params?.[0]
        if (!point) return ''
        return `${point.axisValue}<br/>综合分 <b>${point.data}</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: points.value.map((item) => item.date),
      boundaryGap: true,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
      axisLabel: { color: '#9d97a3' },
    },
    yAxis: {
      type: 'value',
      min: 60,
      max: 100,
      splitLine: { lineStyle: { color: 'rgba(255,255,255,.08)' } },
      axisLabel: { color: '#9d97a3' },
    },
    series: [
      {
        name: '综合分',
        type: 'line',
        data: scores,
        smooth: true,
        symbol: 'circle',
        symbolSize: (_value, params) => (params.dataIndex === highlight ? 12 : 7),
        lineStyle: { width: 2.5, color: '#b45cff' },
        itemStyle: {
          color: (params) => (params.dataIndex === highlight ? '#ffb45b' : '#ff7a18'),
        },
        areaStyle: { color: 'rgba(180,92,255,.14)' },
        markPoint: scores.length
          ? {
              symbol: 'circle',
              symbolSize: 10,
              data: [{ coord: [highlight, scores[highlight]], itemStyle: { color: '#ffb45b' } }],
              label: { show: false },
            }
          : undefined,
      },
    ],
  }
})

function parseIsoDate(value) {
  if (!value) return null
  const date = new Date(`${value}T00:00:00`)
  return Number.isNaN(date.getTime()) ? null : date
}

function recordMatchesHeatDate(item, isoDate) {
  if (!isoDate) return true
  if (item?.when) {
    return String(item.when).slice(0, 10) === isoDate
  }
  const stamp = parseIsoDate(isoDate)
  if (!stamp || !item?.date) return false
  const label = `${stamp.getMonth() + 1}月${stamp.getDate()}日`
  return item.date === label || item.date === stamp.toLocaleDateString('zh-CN')
}

function heatCellTitle(cell) {
  return `${cell.label || cell.date} · ${cell.count || 0} 次 · ${cell.minutes || 0} 分钟`
}

function toggleHeatDay(cell) {
  if (cell?.placeholder || !cell?.date) return
  selectedHeatDate.value = selectedHeatDate.value === cell.date ? '' : cell.date
  showAllRecords.value = false
}

function clearHeatFilter() {
  selectedHeatDate.value = ''
}

function formatJournalDate(value) {
  if (!value) return ''
  const date = parseIsoDate(value) || new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function scoreTier(score) {
  const value = Number(score)
  if (!Number.isFinite(value)) return 'mid'
  if (value >= 85) return 'high'
  if (value >= 75) return 'mid'
  return 'low'
}

function scoreMark(score) {
  const tier = scoreTier(score)
  if (tier === 'high') return '高'
  if (tier === 'low') return '弱'
  return '稳'
}

function openRecord(item) {
  const query = {}
  if (item?.session_id) query.sessionId = item.session_id
  if (item?.id) query.feedbackId = item.id
  router.push(Object.keys(query).length ? { path: '/ai-review', query } : '/ai-review')
}

function goTraining() {
  router.push('/training')
}

function demoHeatmap(days = 30) {
  const today = new Date()
  return Array.from({ length: days }, (_, index) => {
    const day = new Date(today)
    day.setDate(today.getDate() - (days - 1 - index))
    const count = index % 5 === 0 ? 3 : index % 3 === 0 ? 1 : 0
    return {
      date: day.toISOString().slice(0, 10),
      label: `${day.getMonth() + 1}/${day.getDate()}`,
      weekday: heatWeekdays[(day.getDay() + 6) % 7],
      count,
      minutes: count * 8,
      level: count === 0 ? 0 : Math.min(4, count + 1),
    }
  })
}

async function load() {
  showAllRecords.value = false
  selectedPointIndex.value = -1
  selectedHeatDate.value = ''
  try {
    const data = await fetchGrowth(range.value)
    points.value = data.points || []
    milestones.value = data.milestones || []
    heatmap.value = data.heatmap || []
    records.value = data.records || []
    summaries.value = data.summaries || []
    journals.value = data.journals || []
  } catch {
    points.value = [
      { date: '08/22', score: 72, clarity: 74, pace: 70, interaction: 71 },
      { date: '08/24', score: 79, clarity: 80, pace: 76, interaction: 78 },
      { date: '08/26', score: 84, clarity: 86, pace: 82, interaction: 83 },
      { date: '08/28', score: 86, clarity: 88, pace: 84, interaction: 85 },
    ]
    milestones.value = [
      { label: '首次训练', value: '08/22', hint: '从第一次模拟课堂算起' },
      { label: '最高分', value: 86, hint: 'AI 评课综合分' },
      { label: '本周次数', value: 3, hint: '近 7 日训练场次' },
    ]
    heatmap.value = demoHeatmap(range.value === '7d' ? 7 : 30)
    records.value = [
      {
        id: 1,
        when: '2026-08-28T14:20:00',
        date: '8月28日',
        time: '14:20',
        course_title: '导入技能',
        overall_score: 86,
        suggestion: '停 8 秒再叫人，把候答练成肌肉记忆。',
        session_id: 1,
      },
      {
        id: 2,
        when: '2026-08-26T10:05:00',
        date: '8月26日',
        time: '10:05',
        course_title: '提问技能',
        overall_score: 84,
        suggestion: '追问时先复述学生答案再推进。',
        session_id: 2,
      },
      {
        id: 3,
        when: '2026-08-24T16:40:00',
        date: '8月24日',
        time: '16:40',
        course_title: '板书板画技能',
        overall_score: 79,
        suggestion: '板书分区更清晰，关键词加粗。',
        session_id: 3,
      },
    ]
    summaries.value = [
      {
        id: 'sum-demo',
        range: '08/26 – 08/28',
        title: '提问与候答',
        caption: '停 8 秒再叫人',
        tag: '近 3 练战报',
        highlight: '高光 86',
        body: '这 3 次里打出了 86 分高光。提问质量最亮。把「停 8 秒再叫人」再练成肌肉记忆。',
      },
    ]
    journals.value = [
      { id: 1, entry_date: '2026-08-28', body: '今天导入更自然了，候答还要再稳 2 秒。' },
      { id: 2, entry_date: '2026-08-26', body: '提问后先复述学生答案，课堂节奏明显顺了。' },
    ]
  }
  if (points.value.length) selectedPointIndex.value = points.value.length - 1
}

watch(range, load)
onMounted(load)
</script>
