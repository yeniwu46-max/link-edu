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

    <VChart class="growth-line" :option="lineOption" autoresize />

    <div class="heat-grid month growth-heat">
      <button v-for="cell in heatmap" :key="cell.date" type="button" :class="{ on: cell.count }">
        <i :data-level="cell.level"></i>
        <em>{{ cell.label }}</em>
      </button>
    </div>

    <div class="summary-cards">
      <SummaryCard v-for="item in summaries" :key="item.id" :item="item" />
    </div>

    <ol class="replay-list">
      <li v-for="item in records" :key="item.id">
        <strong>{{ item.date }} {{ item.time }}</strong>
        <span>{{ item.course_title }} · {{ item.overall_score }} 分</span>
        <em>{{ item.suggestion }}</em>
      </li>
    </ol>

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
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import SplitTitle from '../components/fx/SplitTitle.vue'
import SummaryCard from '../components/SummaryCard.vue'
import { fetchGrowth } from '../services/dashboard'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const range = ref('30d')
const points = ref([])
const milestones = ref([])
const heatmap = ref([])
const records = ref([])
const summaries = ref([])

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
    points.value = data.points || []
    milestones.value = data.milestones || []
    heatmap.value = data.heatmap || []
    records.value = data.records || []
    summaries.value = data.summaries || []
  } catch {
    points.value = [
      { date: '08/22', score: 72 },
      { date: '08/24', score: 79 },
      { date: '08/26', score: 84 },
      { date: '08/28', score: 86 },
    ]
    milestones.value = [
      { label: '首次训练', value: '08/22', hint: '从第一次模拟课堂算起' },
      { label: '最高分', value: 86, hint: 'AI 评课综合分' },
      { label: '本周次数', value: 3, hint: '近 7 日训练场次' },
    ]
    summaries.value = [
      {
        id: 'sum-demo',
        range: '08/26 – 08/28',
        title: '提问与候答',
        caption: '停 8 秒再叫人',
        accent: 'violet',
        image: 'ask',
        tag: '近 3 练战报',
        highlight: '高光 86',
        mood: '高光',
        body: '这 3 次里打出了 86 分高光。提问质量最亮。把「停 8 秒再叫人」再练成肌肉记忆。',
      },
    ]
  }
}

watch(range, load)
onMounted(load)
</script>
