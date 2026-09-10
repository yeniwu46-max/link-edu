<template>
  <div class="page-dashboard">
    <div class="dash-grid">
      <section class="welcome">
        <p>{{ greeting.kicker || greeting.periodEn }}</p>
        <h1>{{ greeting.title || `${greeting.periodZh}，${greeting.name}` }}</h1>
        <span>{{ greeting.subtitle }}</span>
        <div>
          <LearnMoreButton @click="router.push('/training')">开始新训练</LearnMoreButton>
          <button type="button" @click="router.push('/courses')">浏览课程</button>
        </div>
      </section>

      <section
        v-if="dashboardStatus !== 'ready'"
        class="dashboard-status"
        :class="{ 'is-loading': dashboardStatus === 'loading' }"
        :role="dashboardStatus === 'error' ? 'alert' : 'status'"
      >
        <template v-if="dashboardStatus === 'loading'">
          <strong>正在加载工作台</strong>
          <p>正在读取你的训练数据。</p>
        </template>
        <template v-else>
          <strong>工作台数据未加载</strong>
          <p>{{ dashboardError }}</p>
          <button type="button" @click="loadDashboard">重新加载</button>
        </template>
      </section>

      <section class="glass weekly" role="button" @click="openPanel('weekly')">
        <h3>本周训练</h3>
        <strong>{{ weekly.sessions }}<small> 次</small></strong>
        <span>累计 {{ weekly.total_minutes }} 分钟 · 点开看热力图</span>
        <div class="spark">
          <i v-for="(height, index) in weekly.sparkline" :key="index" :style="{ height: `${height}px` }"></i>
        </div>
      </section>

      <section class="glass continue" v-if="continueTraining">
        <video
          ref="continueVideo"
          class="continue-media"
          src="/assets/hero-hair.mp4"
          poster="/assets/hero-clean.png"
          autoplay
          muted
          loop
          playsinline
          preload="auto"
          aria-hidden="true"
          @canplay="playContinueVideo"
        ></video>
        <h3>继续训练</h3>
        <div class="course">
          <small>{{ continueTraining.category }}</small>
          <h2>{{ continueTraining.course_title }}</h2>
          <b>{{ continueTraining.status_label }}</b>
          <div class="progress"><i :style="{ width: `${continueTraining.progress_percent}%` }"></i></div>
          <span>上次训练：{{ formatLastTrained(continueTraining.last_trained_at) }}</span>
        </div>
        <LearnMoreButton @click="resumeTraining">继续训练</LearnMoreButton>
      </section>

      <section class="glass feedback" v-if="aiFeedback" role="button" @click="openPanel('feedback')">
        <h3>反馈摘要 · 演示 / 规则评分</h3>
        <div class="score">{{ aiFeedback.overall_score }}</div>
        <ul>
          <li v-for="item in (aiFeedback.dimensions || []).slice(0, 3)" :key="item.key">
            {{ item.label }} <b>{{ item.score }}</b>
          </li>
        </ul>
        <p>{{ aiFeedback.suggestion }}</p>
      </section>

      <section class="glass entries">
        <h3>课程与训练入口</h3>
        <div>
          <article v-for="entry in quickEntries" :key="entry.title">
            <i>{{ entry.icon }}</i>
            <h3>{{ entry.title }}</h3>
            <p>{{ entry.description }}</p>
            <button type="button" @click="router.push(entry.route || '/courses')">›</button>
          </article>
          <p v-if="!quickEntries.length" class="dashboard-empty">暂无可用入口。</p>
        </div>
      </section>

      <section class="glass growth" role="button" @click="openPanel('growth')">
        <h3>成长轨迹 · 历史演示</h3>
        <div class="chart">
          <i v-for="(score, index) in growthTrajectory" :key="index" :style="{ height: `${score}%` }">
            <b>{{ score }}</b>
          </i>
        </div>
      </section>
    </div>

    <div v-if="panel" class="help-mask" @click="panel = null"></div>
    <aside v-if="panel && panel !== 'growth'" class="dash-sheet" :class="{ wide: panel === 'feedback' }" role="dialog">
      <header>
        <h2>{{ sheetTitle }}</h2>
        <button type="button" class="close-x" aria-label="关闭" @click="panel = null">×</button>
      </header>

      <div v-if="panel === 'weekly'">
        <div class="range-switch">
          <button type="button" :class="{ active: heatRange === 'week' }" @click="heatRange = 'week'">本周</button>
          <button type="button" :class="{ active: heatRange === 'month' }" @click="heatRange = 'month'">本月</button>
        </div>
        <div class="heat-grid" :class="heatRange">
          <button
            v-for="cell in heatCells"
            :key="cell.date"
            type="button"
            :class="{ on: cell.count, pick: cell.date === pickedDay }"
            :title="`${cell.date} ${cell.count} 次`"
            @click="pickedDay = cell.date"
          >
            <i :data-level="cell.level"></i>
            <em>{{ cell.label }}</em>
          </button>
        </div>
        <p v-if="!heatCells.length" class="dashboard-empty">暂无训练记录。</p>
        <p class="dock-hint">{{ dayHint }}</p>
        <form class="journal-form" @submit.prevent="submitJournal">
          <textarea v-model="journalBody" rows="3" placeholder="手动写一条训练日志，比如今天候答停够了。"></textarea>
          <button class="primary" type="submit" :disabled="journalSaving">写下日志</button>
        </form>
        <p v-if="journalError" class="dashboard-inline-error" role="alert">{{ journalError }}</p>
        <ul class="journal-list">
          <li v-for="item in weekly.journals || []" :key="item.id">
            <em>{{ item.entry_date }}</em>
            <span>{{ item.body }}</span>
          </li>
        </ul>
        <p v-if="!(weekly.journals || []).length" class="dashboard-empty">暂无训练日志。</p>
        <div class="summary-cards">
          <SummaryCard v-for="item in weekly.summaries || []" :key="item.id" :item="item" />
        </div>
        <p v-if="!(weekly.summaries || []).length" class="dashboard-empty">暂无训练摘要。</p>
      </div>

      <div v-else-if="panel === 'feedback' && aiFeedback" class="feedback-sheet">
        <p class="dock-hint">{{ aiFeedback.course_title || '最近一次片段教学' }} · {{ feedbackReport.mode_label || '评课报告' }}</p>
        <div class="feedback-sheet__hero">
          <b>{{ aiFeedback.overall_score }}</b>
          <div>
            <strong>综合分</strong>
            <p>{{ feedbackReport.next_action || aiFeedback.suggestion }}</p>
          </div>
        </div>
        <p v-if="regenOk" class="dock-hint">已按勾选重写本份报告。</p>
        <p v-if="regenError" class="dashboard-inline-error" role="alert">{{ regenError }}</p>

        <h3>六个维度</h3>
        <ul class="dim-list dim-list--brief">
          <li v-for="item in feedbackDims" :key="item.key">
            <div>
              <span>{{ item.label }}</span>
              <em>{{ item.brief }}</em>
            </div>
            <b>{{ item.score }}</b>
          </li>
        </ul>

        <article v-for="section in feedbackSections" :key="section.title" class="sheet-section">
          <h3>{{ section.title }}</h3>
          <p>{{ section.body }}</p>
        </article>

        <div class="review-lists">
          <div>
            <h3>已稳住</h3>
            <ul>
              <li v-for="item in feedbackReport.strengths || []" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div>
            <h3>下次改这三处</h3>
            <ul>
              <li v-for="item in feedbackReport.fixes || []" :key="item">{{ item }}</li>
            </ul>
          </div>
        </div>

        <div class="sheet-actions">
          <button type="button" @click="showCorrect = !showCorrect">校对不准，重新生成</button>
          <button type="button" class="ghost-link" @click="router.push({ path: '/ai-review', query: { feedbackId: aiFeedback.id } })">去 AI 评课看图表</button>
        </div>
        <div v-if="showCorrect" class="correct-box">
          <p>勾选你认为评课误判的点，可多选，再生成一版。</p>
          <div class="correction-options">
            <div v-for="item in corrections" :key="item.id" class="correction-option">
              <input
                :id="`correction-${item.id}`"
                v-model="pickedNotes"
                type="checkbox"
                :value="item.id"
              />
              <label :for="`correction-${item.id}`">{{ item.label }}</label>
            </div>
          </div>
          <button class="primary" type="button" :disabled="regenSaving" @click="doRegenerate">按校正点重写</button>
        </div>
      </div>
    </aside>

    <section v-if="panel === 'growth'" class="dash-modal" role="dialog" aria-labelledby="growth-modal-title" @click.stop>
      <header>
        <div>
          <p class="dock-hint">近 30 天回放</p>
          <h2 id="growth-modal-title">成长轨迹</h2>
        </div>
        <button type="button" class="close-x" aria-label="关闭" @click="panel = null">×</button>
      </header>
      <p class="page-lead">按日期或时间点查看每一次模拟课堂。点折线上的节点或下方列表，即可回放当时的评课。</p>
      <VChart
        v-if="growthLineRows.length"
        class="growth-modal-line"
        :option="growthLineOption"
        autoresize
        @click="onGrowthChartClick"
      />
      <p v-else class="dashboard-empty">暂无成长轨迹。</p>
      <div class="range-switch growth-dates">
        <button type="button" :class="{ active: !growthDay }" @click="growthDay = ''">全部</button>
        <button
          v-for="day in growthDates"
          :key="day"
          type="button"
          :class="{ active: growthDay === day }"
          @click="growthDay = day"
        >{{ day }}</button>
      </div>
      <ol class="replay-list">
        <li v-for="item in visibleGrowth" :key="item.id">
          <button type="button" :class="{ active: item.id === growthFocus }" @click="openGrowthReplay(item)">
            <strong>{{ item.date }} {{ item.time }}</strong>
            <span>{{ item.course_title }} · {{ item.overall_score }} 分 · {{ item.mode_label || '评课' }}</span>
            <em>{{ item.suggestion }}</em>
          </button>
        </li>
      </ol>
      <p v-if="!visibleGrowth.length" class="dock-hint">这 30 天还没有评课记录。完成一次训练后会出现在这里。</p>
      <p v-else class="dock-hint">最多保留近 30 天。点一条打开当时的 AI 评课。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { addJournal, fetchDashboardOverview, regenerateFeedback } from '../services/dashboard'
import { useAuthStore } from '../stores/auth'
import { formatGreeting } from '../utils/greeting'
import {
  dashboardLoadErrorMessage,
  journalSubmitErrorMessage,
  regenerateErrorMessage,
} from '../utils/dashboardState'
import LearnMoreButton from '../components/LearnMoreButton.vue'
import SummaryCard from '../components/SummaryCard.vue'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const router = useRouter()
const auth = useAuthStore()
const firstGreet = formatGreeting()
const panel = ref(null)
const continueVideo = ref(null)
const heatRange = ref('week')
const pickedDay = ref('')
const journalBody = ref('')
const showCorrect = ref(false)
const regenOk = ref(false)
const regenError = ref('')
const regenSaving = ref(false)
const pickedNotes = ref([])
const growthRecords = ref([])
const growthDay = ref('')
const growthFocus = ref(null)
const dashboardStatus = ref('loading')
const dashboardError = ref('')
const journalSaving = ref(false)
const journalError = ref('')

const greeting = ref({
  kicker: firstGreet.kicker,
  title: firstGreet.title,
  periodEn: firstGreet.periodEn,
  periodZh: firstGreet.periodZh,
  name: '林晓',
  subtitle: '准备好开始今天的模拟课堂了吗？',
  role_label: '师范生',
})
const weekly = ref({
  sessions: 0,
  total_minutes: 0,
  sparkline: [],
  heatmap: [],
  month_heatmap: [],
  journals: [],
  summaries: [],
})
const continueTraining = ref(null)
const aiFeedback = ref(null)
const quickEntries = ref([])
const growthTrajectory = ref([])
const corrections = [
  { id: 'pace_ok', label: '节奏其实正常，没有赶课' },
  { id: 'waited', label: '提问后已经等够了' },
  { id: 'had_interaction', label: '互动其实发生了' },
  { id: 'board_clear', label: '板书分区是清楚的' },
  { id: 'intro_enough', label: '导入并不短' },
  { id: 'posture_ok', label: '教态没有背对学生' },
]
const feedbackReport = computed(() => aiFeedback.value?.report || {})
const feedbackDims = computed(() => {
  const fromCard = aiFeedback.value?.dimensions || []
  if (fromCard.length) return fromCard
  return feedbackReport.value.dimensions || []
})
const feedbackSections = computed(() => feedbackReport.value.sections || [])

const sheetTitle = computed(() => ({
  weekly: '本周训练',
  feedback: 'AI 反馈报告',
}[panel.value] || ''))

const growthDates = computed(() => {
  const seen = []
  for (const item of growthRecords.value) {
    if (item.date && !seen.includes(item.date)) seen.push(item.date)
  }
  return seen
})
const visibleGrowth = computed(() => {
  const rows = growthRecords.value || []
  if (!growthDay.value) return rows
  return rows.filter((item) => item.date === growthDay.value)
})
const growthLineRows = computed(() => [...visibleGrowth.value].slice().reverse())
const growthLineOption = computed(() => {
  const rows = growthLineRows.value
  return {
    animationDuration: 700,
    grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#120f16',
      borderColor: 'rgba(255,255,255,.16)',
      textStyle: { color: '#f4f2f6' },
    },
    xAxis: {
      type: 'category',
      data: rows.map((item) => (item.time ? `${item.date} ${item.time}` : item.date)),
      boundaryGap: false,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
      axisLabel: { color: '#9d97a3', hideOverlap: true },
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
        data: rows.map((item) => ({
          value: item.overall_score,
          itemStyle: { color: item.id === growthFocus.value ? '#ff7a18' : '#b45cff' },
        })),
        smooth: false,
        symbol: 'circle',
        symbolSize: 10,
        lineStyle: { width: 2, color: '#b45cff' },
        areaStyle: { color: 'rgba(180,92,255,.12)' },
      },
    ],
  }
})

function emptyWeekly() {
  return {
    sessions: 0,
    total_minutes: 0,
    sparkline: [],
    heatmap: [],
    month_heatmap: [],
    journals: [],
    summaries: [],
  }
}

const heatCells = computed(() => (
  heatRange.value === 'month' ? (weekly.value.month_heatmap || []) : (weekly.value.heatmap || [])
))

const dayHint = computed(() => {
  const cell = heatCells.value.find((item) => item.date === pickedDay.value)
  if (!cell) return '点一个日期，查看当天训练。也可以在下方写日志。'
  return `${cell.date} 训练 ${cell.count} 次，共 ${cell.minutes} 分钟。`
})

function applyGreeting(data) {
  const name = data?.name || greeting.value.name || '林晓'
  const formatted = formatGreeting(name)
  greeting.value = {
    ...(data || greeting.value),
    name,
    kicker: formatted.kicker,
    title: formatted.title,
    periodZh: formatted.periodZh,
    periodEn: formatted.periodEn,
    period: formatted.periodEn,
  }
}

function formatLastTrained(value) {
  if (!value) return '暂无记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const now = new Date()
  const diffHours = Math.floor((now - date) / (1000 * 60 * 60))
  if (diffHours < 24) return `今天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
  if (diffHours < 48) return `昨天 ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function resumeTraining() {
  const courseId = continueTraining.value?.course_id
  router.push(courseId ? { path: '/training', query: { courseId } } : '/training')
}

function playContinueVideo() {
  const video = continueVideo.value
  if (!video || document.visibilityState !== 'visible') return
  video.muted = true
  const playback = video.play()
  if (playback && typeof playback.catch === 'function') playback.catch(() => {})
}

function openPanel(name) {
  panel.value = name
  showCorrect.value = false
  regenOk.value = false
  regenError.value = ''
  if (name === 'growth') {
    growthDay.value = ''
    growthFocus.value = visibleGrowth.value[0]?.id || null
  }
}

function openGrowthReplay(item) {
  growthFocus.value = item.id
  router.push({ path: '/ai-review', query: { feedbackId: item.id } })
}

function onGrowthChartClick(params) {
  const item = growthLineRows.value[params.dataIndex]
  if (!item) return
  growthFocus.value = item.id
  router.push({ path: '/ai-review', query: { feedbackId: item.id } })
}

async function submitJournal() {
  const body = journalBody.value.trim()
  journalError.value = ''
  if (!body) {
    journalError.value = '请先写一句训练日志'
    return
  }
  if (journalSaving.value) return
  journalSaving.value = true
  try {
    const item = await addJournal({ entry_date: pickedDay.value || new Date().toISOString().slice(0, 10), body })
    weekly.value.journals = [item, ...(weekly.value.journals || [])]
    journalBody.value = ''
  } catch (error) {
    journalError.value = journalSubmitErrorMessage(error)
  } finally {
    journalSaving.value = false
  }
}

async function doRegenerate() {
  if (!aiFeedback.value?.id) return
  if (regenSaving.value) return
  regenError.value = ''
  regenOk.value = false
  regenSaving.value = true
  try {
    aiFeedback.value = await regenerateFeedback(aiFeedback.value.id, pickedNotes.value)
  } catch (error) {
    regenError.value = regenerateErrorMessage(error)
    return
  } finally {
    regenSaving.value = false
  }
  showCorrect.value = false
  regenOk.value = true
}

async function loadDashboard() {
  dashboardStatus.value = 'loading'
  dashboardError.value = ''
  applyGreeting()
  try {
    const data = await fetchDashboardOverview()
    applyGreeting(data.greeting)
    weekly.value = { ...emptyWeekly(), ...(data.weekly_training || {}) }
    continueTraining.value = data.continue_training ?? null
    aiFeedback.value = data.ai_feedback ?? null
    quickEntries.value = data.quick_entries ?? []
    growthTrajectory.value = data.growth_trajectory ?? []
    growthRecords.value = data.growth_records || []
    if (data.greeting) auth.user = { ...auth.user, ...data.greeting }
    dashboardStatus.value = 'ready'
  } catch (error) {
    dashboardStatus.value = 'error'
    dashboardError.value = dashboardLoadErrorMessage(error)
    weekly.value = emptyWeekly()
    continueTraining.value = null
    aiFeedback.value = null
    quickEntries.value = []
    growthTrajectory.value = []
    growthRecords.value = []
  }
}

onMounted(() => {
  loadDashboard()
  playContinueVideo()
  document.addEventListener('visibilitychange', playContinueVideo)
  window.addEventListener('link-settings', refreshGreeting)
})
onUnmounted(() => {
  document.removeEventListener('visibilitychange', playContinueVideo)
  continueVideo.value?.pause()
  window.removeEventListener('link-settings', refreshGreeting)
})

function refreshGreeting() {
  applyGreeting({ name: greeting.value.name })
}
</script>
