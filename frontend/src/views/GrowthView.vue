<template>
  <div class="sparse-page">
    <p style="padding:14px;background:#edf3fc;border-radius:12px;color:#405b7f">以下轨迹保留旧演示 / 规则评分。真实 AI 课堂按证据覆盖评价，不与此分数直接比较。<router-link to="/classroom">查看真实课堂记录 →</router-link></p>
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">TRAJECTORY</p>
        <SplitTitle text="成长档案" />
        <p class="page-lead">工作台里点开的热力图和回放，完整版在这里。</p>
      </div>
      <div class="range-switch">
        <button type="button" :class="{ active: range === '7d' }" @click="range = '7d'">7 日</button>
        <button type="button" :class="{ active: range === '30d' }" @click="range = '30d'">30 日</button>
        <button type="button" :class="{ active: range === 'all' }" @click="range = 'all'">全部</button>
      </div>
    </header>

    <p v-if="loadError" class="dock-hint" role="alert">{{ loadError }}</p>
    <p v-else-if="!points.length" class="dock-hint">当前范围暂无真实评课数据。</p>
    <VChart v-else class="growth-line" :option="lineOption" autoresize />

    <div class="heat-grid month growth-heat">
      <button
        v-for="cell in heatmap"
        :key="cell.date"
        type="button"
        :class="{ on: cell.count, selected: selectedDate === cell.date }"
        :aria-pressed="selectedDate === cell.date"
        @click="selectedDate = cell.date"
      >
        <i :data-level="cell.level"></i>
        <em>{{ cell.label }}</em>
      </button>
    </div>

    <section v-if="selectedCell" class="growth-day-detail" aria-live="polite">
      <h3>{{ selectedCell.label }} · {{ selectedCell.count }} 次训练 · {{ selectedCell.minutes }} 分钟</h3>
      <ul v-if="selectedCell.sessions.length">
        <li v-for="session in selectedCell.sessions" :key="session.id">
          {{ session.course_title || '未命名课程' }} · {{ session.status_label }} · {{ session.progress_percent }}%
        </li>
      </ul>
      <p v-else class="dock-hint">当天没有训练记录。</p>
    </section>

    <div class="summary-cards">
      <SummaryCard v-for="item in summaries" :key="item.id" :item="item" />
    </div>

    <ol class="replay-list">
      <li v-for="item in records" :key="item.id">
        <strong>{{ item.date }} {{ item.time }}</strong>
        <span>{{ item.course_title }} · {{ item.overall_score }} 分</span>
        <em>{{ item.suggestion }}</em>
        <button type="button" @click="openRecord(item)">查看评课</button>
      </li>
    </ol>
    <p v-if="!loadError && !records.length" class="dock-hint">当前范围暂无可回放的真实评课记录。</p>

    <div class="milestones">
      <article v-for="item in milestones" :key="item.label">
        <p>{{ item.label }}</p>
        <strong>{{ item.value }}</strong>
        <span>{{ item.hint }}</span>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import SplitTitle from '../components/fx/SplitTitle.vue'
import SummaryCard from '../components/SummaryCard.vue'
import { fetchGrowth } from '../services/dashboard'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const router = useRouter()
const range = ref('30d')
const points = ref([])
const milestones = ref([])
const heatmap = ref([])
const records = ref([])
const summaries = ref([])
const loadError = ref('')
const selectedDate = ref('')

const selectedCell = computed(() => heatmap.value.find((item) => item.date === selectedDate.value) || null)

const lineOption = computed(() => ({
  animationDuration: 800,
  grid: { left: 8, right: 12, top: 28, bottom: 8, containLabel: true },
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#120f16',
    borderColor: 'rgba(255,255,255,.16)',
    textStyle: { color: '#f4f2f6' },
  },
  xAxis: {
    type: 'category',
    data: points.value.map((item) => item.date),
    boundaryGap: false,
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
      type: 'line',
      data: points.value.map((item) => item.score),
      smooth: false,
      symbol: 'rect',
      symbolSize: 8,
      lineStyle: { width: 2, color: '#b45cff' },
      itemStyle: { color: '#ff7a18' },
      areaStyle: { color: 'rgba(180,92,255,.12)' },
    },
  ],
}))

async function load() {
  try {
    const data = await fetchGrowth(range.value)
    loadError.value = ''
    points.value = data.points || []
    milestones.value = data.milestones || []
    heatmap.value = data.heatmap || []
    records.value = data.records || []
    summaries.value = data.summaries || []
    if (!selectedDate.value || !heatmap.value.some((item) => item.date === selectedDate.value)) {
      selectedDate.value = heatmap.value.at(-1)?.date || ''
    }
  } catch (error) {
    points.value = []
    milestones.value = []
    heatmap.value = []
    records.value = []
    summaries.value = []
    selectedDate.value = ''
    loadError.value = error?.response?.data?.message || '成长档案加载失败，请检查后端服务后重试。'
  }
}

function openRecord(item) {
  router.push({
    path: '/ai-review',
    query: { sessionId: item.session_id, feedbackId: item.id },
  })
}

watch(range, load)
onMounted(load)
</script>
