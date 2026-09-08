<template>
  <div class="sparse-page review-page">
    <p style="padding:14px;background:#edf3fc;border-radius:12px;color:#405b7f">此页为历史演示 / 规则评分，不与真实课堂分数比较。<router-link to="/classroom">查看真实课堂与证据报告 →</router-link></p>
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">AI REVIEW</p>
        <SplitTitle text="AI 评课" />
        <p class="page-lead">{{ current?.course_title || '最近一次片段教学' }} · {{ report.mode_label || '评课报告' }}</p>
      </div>
      <span v-if="showDemoBadge" class="review-badge">演示评分</span>
    </header>

    <div class="review-layout" v-if="current">
      <section class="review-hero">
        <div class="review-score">
          <NumberFlow :value="current.overall_score || 0" />
          <small>综合</small>
        </div>
        <VChart class="radar-chart" :option="radarOption" autoresize />
      </section>

      <section class="review-side">
        <ul>
          <li v-for="item in dimensions" :key="item.key">
            <span>{{ item.label }}</span>
            <b>{{ item.score }}</b>
          </li>
        </ul>
        <blockquote>{{ report.next_action || current.suggestion }}</blockquote>
        <p>旧演示报告仅供查看，不再通过勾选固定加分。</p>
        <router-link class="ghost-link" to="/classroom">前往真实课堂，基于证据提交评课异议 →</router-link>
      </section>
    </div>

    <div class="review-charts" v-if="current">
      <section>
        <h3>六维对比</h3>
        <VChart class="bar-chart" :option="barOption" autoresize />
      </section>
      <section>
        <h3>历史综合分</h3>
        <VChart class="bar-chart" :option="lineOption" autoresize />
      </section>
    </div>

    <div class="review-report" v-if="current">
      <article v-for="section in report.sections || []" :key="section.title">
        <h3>{{ section.title }}</h3>
        <p>{{ section.body }}</p>
      </article>
      <div class="review-lists">
        <div>
          <h3>已稳住</h3>
          <ul>
            <li v-for="item in report.strengths || []" :key="item">{{ item }}</li>
          </ul>
        </div>
        <div>
          <h3>下次改这三处</h3>
          <ul>
            <li v-for="item in report.fixes || []" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>

    <div class="history-ticks" v-if="items.length">
      <button
        v-for="item in items.slice(0, 8)"
        :key="item.id"
        type="button"
        :class="{ active: item.id === current?.id }"
        @click="current = item"
      >
        <i :style="{ height: `${item.overall_score}%` }"></i>
        <em>{{ item.overall_score }}</em>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import NumberFlow from '@number-flow/vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import SplitTitle from '../components/fx/SplitTitle.vue'
import { fetchFeedbacks } from '../services/dashboard'
import { loadSettings } from '../utils/settings'

use([CanvasRenderer, RadarChart, BarChart, LineChart, RadarComponent, GridComponent, TooltipComponent])

const route = useRoute()
const showDemoBadge = ref(loadSettings().showDemoBadge)
function syncDemoBadge() {
  showDemoBadge.value = loadSettings().showDemoBadge
}
const items = ref([])
const current = ref(null)

const report = computed(() => current.value?.report || {})
const dimensions = computed(() => {
  if (report.value.dimensions?.length) return report.value.dimensions
  return [
    { key: 'clarity', label: '表达清晰度', score: current.value?.clarity_score || 0 },
    { key: 'pace', label: '教学节奏', score: current.value?.pace_score || 0 },
    { key: 'interaction', label: '互动设计', score: current.value?.interaction_score || 0 },
  ]
})

const tooltip = {
  backgroundColor: '#120f16',
  borderColor: 'rgba(255,255,255,.16)',
  textStyle: { color: '#f4f2f6' },
}

const radarOption = computed(() => ({
  animationDuration: 700,
  radar: {
    indicator: dimensions.value.map((item) => ({ name: item.label.replace(/与|质量|设计|清晰度/g, ''), max: 100 })),
    shape: 'polygon',
    splitNumber: 4,
    axisName: { color: '#b9b3bd', fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,.12)' } },
    splitArea: { areaStyle: { color: ['rgba(255,255,255,.02)', 'rgba(255,255,255,.05)'] } },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
  },
  series: [
    {
      type: 'radar',
      symbol: 'rect',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#ff7a18' },
      areaStyle: { color: 'rgba(180,92,255,.22)' },
      itemStyle: { color: '#b45cff' },
      data: [{ value: dimensions.value.map((item) => item.score || 0) }],
    },
  ],
}))

const barOption = computed(() => ({
  animationDuration: 700,
  grid: { left: 8, right: 12, top: 24, bottom: 8, containLabel: true },
  tooltip,
  xAxis: {
    type: 'category',
    data: dimensions.value.map((item) => item.label),
    axisLabel: { color: '#b9b3bd', fontSize: 11, rotate: 18 },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
  },
  yAxis: {
    type: 'value',
    min: 50,
    max: 100,
    splitLine: { lineStyle: { color: 'rgba(255,255,255,.08)' } },
    axisLabel: { color: '#9d97a3' },
  },
  series: [
    {
      type: 'bar',
      barWidth: 18,
      data: dimensions.value.map((item) => item.score || 0),
      itemStyle: { color: '#ff7a18' },
    },
  ],
}))

const lineOption = computed(() => {
  const history = [...items.value].slice(0, 8).reverse()
  return {
    animationDuration: 700,
    grid: { left: 8, right: 12, top: 24, bottom: 8, containLabel: true },
    tooltip,
    xAxis: {
      type: 'category',
      data: history.map((item, index) => item.created_at?.slice(5, 10) || `#${index + 1}`),
      axisLabel: { color: '#b9b3bd' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
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
        smooth: false,
        symbol: 'rect',
        symbolSize: 8,
        data: history.map((item) => item.overall_score),
        lineStyle: { width: 2, color: '#b45cff' },
        itemStyle: { color: '#ff7a18' },
        areaStyle: { color: 'rgba(180,92,255,.12)' },
      },
    ],
  }
})

onMounted(async () => {
  syncDemoBadge()
  window.addEventListener('link-settings', syncDemoBadge)
  try {
    items.value = await fetchFeedbacks()
  } catch {
    items.value = [
      {
        id: 1,
        overall_score: 86,
        clarity_score: 90,
        pace_score: 82,
        interaction_score: 85,
        suggestion: '减少连续讲述，增加等待时间',
        course_title: '课堂导入与提问设计',
        report: {
          mode_label: '片段练习',
          next_action: '减少连续讲述，增加等待时间',
          dimensions: [
            { key: 'clarity', label: '表达清晰度', score: 90 },
            { key: 'pace', label: '教学节奏', score: 82 },
            { key: 'interaction', label: '互动设计', score: 85 },
            { key: 'posture', label: '教态与站位', score: 80 },
            { key: 'questioning', label: '提问质量', score: 84 },
            { key: 'structure', label: '课堂结构', score: 81 },
          ],
          sections: [
            { title: '综合判断', body: '本地演示数据。结束训练后会生成完整六维报告。' },
          ],
          strengths: ['表达清晰度相对最高。'],
          fixes: ['提问后增加等待。'],
        },
      },
    ]
  }
  const wanted = Number(route.query.feedbackId)
  current.value = items.value.find((item) => item.id === wanted) || items.value[0] || null
})
onUnmounted(() => {
  window.removeEventListener('link-settings', syncDemoBadge)
})
</script>
