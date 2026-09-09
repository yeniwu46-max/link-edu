<template>
  <div class="sparse-page review-page">
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">AI REVIEW</p>
        <SplitTitle text="AI 评课" />
        <p class="page-lead">{{ current?.course_title || '最近一次片段教学' }} · {{ report.mode_label || '评课报告' }}</p>
      </div>
      <span v-if="showDemoBadge" class="review-badge">演示评分</span>
    </header>

    <div v-if="loadError || aiError" class="review-alert" role="alert">
      <p>{{ loadError || aiErrorMessage }}</p>
      <button v-if="loginExpired" type="button" class="ghost-link" @click="goToLogin">返回登录</button>
      <button v-else-if="loadError" type="button" class="ghost-link" @click="loadReviewData">重新加载</button>
    </div>

    <section v-if="showAiReviewGenerator && current" class="review-generator">
      <div>
        <h3>{{ generatorTitle }}</h3>
        <p>点击生成后，系统会自动读取本次训练数据并交给 DeepSeek，生成本次课程的结构化评课报告。</p>
      </div>
      <p v-if="generationStatus === 'generating'" class="review-generator__status">
        DeepSeek 正在生成。可以暂时离开此页，恢复后系统会自动核对结果。
      </p>
      <p v-else-if="generationStatus === 'failed'" class="review-generator__status is-failed">
        上一次生成没有完成，课堂材料已保留，可以直接重试。
      </p>
      <div class="review-generator__actions">
        <span>此按钮只负责生成本次评课报告</span>
        <button
          type="button"
          class="primary"
          :disabled="!canGenerateAiReview"
          @click="runAiReview"
        >
          {{ generateButtonLabel }}
        </button>
      </div>
      <p v-if="aiGenerateError" class="error">{{ aiGenerateError }}</p>
    </section>

    <section v-if="current" class="review-generator review-followup">
      <div>
        <h3>继续追问本次评课</h3>
        <p>报告生成成功后，可以针对评分、问题和改进建议继续提问。</p>
      </div>
      <p v-if="!followupReady" class="review-generator__status">
        {{ followupDisabledMessage }}
      </p>
      <textarea
        v-model="questionDraft"
        rows="6"
        placeholder="例如：为什么这次提问质量较低？下次应该怎么练习？"
        :disabled="!followupReady || questionLoading"
      ></textarea>
      <div class="review-generator__actions">
        <span>本次问题不会修改原评课报告和评分</span>
        <button
          type="button"
          class="primary"
          :disabled="!canAskQuestion"
          @click="askQuestion"
        >
          {{ questionLoading ? 'DeepSeek 正在回答' : '发送问题' }}
        </button>
      </div>
      <p v-if="questionError" class="error">{{ questionError }}</p>
      <article v-if="questionAnswer" class="review-followup__answer">
        <div class="review-generator__actions">
          <span>你的问题：{{ questionAsked }}</span>
          <strong>{{ questionScope === 'history' ? '近 30 天趋势' : '本次评课' }}</strong>
        </div>
        <p>{{ questionAnswer }}</p>
      </article>
    </section>

    <section v-if="!current && !isLoading && !loadError" class="review-empty">
      <h3>暂无可生成的训练记录</h3>
      <p>请先完成一次训练，系统才有可读取的课程、时长和训练状态数据。</p>
      <button type="button" class="ghost-link" @click="router.push('/training')">去完成一次训练</button>
    </section>

    <section v-if="current && insufficientEvidence" class="review-empty">
      <h3>当前材料暂时无法评分</h3>
      <p>这份内容没有提供可核实的课堂过程，因此不会计入六维评分或历史趋势。请补充课堂转写、教学动作、学生回应或观察记录后重新生成。</p>
    </section>

    <div class="review-layout" v-if="current && !insufficientEvidence">
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
        <button v-if="report.demo" type="button" class="ghost-link" @click="showCorrect = !showCorrect">校对不准，调整演示评分</button>
        <div v-if="showCorrect && report.demo" class="correct-box">
          <label v-for="item in corrections" :key="item.id">
            <input v-model="pickedNotes" type="checkbox" :value="item.id" />
            {{ item.label }}
          </label>
          <button class="primary" type="button" @click="doRegenerate">按校正点重写</button>
        </div>
      </section>
    </div>

    <div class="review-charts" v-if="current && !insufficientEvidence">
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
      <article v-if="report.summary && !(report.sections || []).some((section) => section.title === '综合判断')">
        <h3>本次总结</h3>
        <p>{{ report.summary }}</p>
      </article>
      <article v-if="report.problems?.length && !(report.sections || []).some((section) => section.title === '主要问题')">
        <h3>主要问题</h3>
        <p>{{ report.problems.join('；') }}</p>
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

    <div class="history-ticks" v-if="scorableItems.length">
      <button
        v-for="item in scorableItems.slice(0, 8)"
        :key="item.id"
        type="button"
        :class="{ active: item.id === current?.id }"
        @click="selectFeedback(item)"
      >
        <i :style="{ height: `${item.overall_score}%` }"></i>
        <em>{{ item.overall_score }}</em>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NumberFlow from '@number-flow/vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import SplitTitle from '../components/fx/SplitTitle.vue'
import {
  askAiReviewQuestion,
  fetchFeedbacks,
  generateAiReview,
  regenerateFeedback,
} from '../services/dashboard'
import { aiReviewErrorMessage, isUnauthorizedError } from '../utils/aiReviewErrors'
import {
  isInsufficientReport,
  selectFeedbackForRoute,
} from '../utils/aiReviewState'
import { loadSettings } from '../utils/settings'

use([CanvasRenderer, RadarChart, BarChart, LineChart, RadarComponent, GridComponent, TooltipComponent])

const route = useRoute()
const router = useRouter()
const items = ref([])
const current = ref(null)
const isLoading = ref(true)
const loadError = ref('')
const loginExpired = ref(false)
const report = computed(() => current.value?.report || {})
const showDemoSetting = ref(loadSettings().showDemoBadge)
const showDemoBadge = computed(() => showDemoSetting.value && report.value.demo === true)
function syncDemoBadge() {
  showDemoSetting.value = loadSettings().showDemoBadge
}
const showCorrect = ref(false)
const pickedNotes = ref([])
const aiGenerating = ref(false)
const aiGenerateError = ref('')
const questionDraft = ref('')
const questionAsked = ref('')
const questionAnswer = ref('')
const questionScope = ref('current')
const questionLoading = ref(false)
const questionError = ref('')
let questionRequestId = 0
let statusPollTimer = null
let refreshPromise = null
const corrections = [
  { id: 'pace_ok', label: '节奏其实正常，没有赶课' },
  { id: 'waited', label: '提问后已经等够了' },
  { id: 'had_interaction', label: '互动其实发生了' },
  { id: 'board_clear', label: '板书分区是清楚的' },
  { id: 'intro_enough', label: '导入并不短' },
  { id: 'posture_ok', label: '教态没有背对学生' },
]

const aiError = computed(() => Boolean(route.query.aiError))
const insufficientEvidence = computed(() => isInsufficientReport(report.value))
const generationStatus = computed(() => (
  aiGenerating.value ? 'generating' : report.value.generation_status || 'idle'
))
const isRealReport = computed(() => report.value.source === 'deepseek' && report.value.demo !== true)
const showAiReviewGenerator = computed(() => Boolean(current.value))
const canGenerateAiReview = computed(() => (
  !aiGenerating.value
  && generationStatus.value !== 'generating'
))
const generatorTitle = computed(() => {
  if (generationStatus.value === 'generating') return 'DeepSeek 正在评课'
  if (insufficientEvidence.value) return '补充课堂材料后重新生成'
  return '生成真实 AI 评课'
})
const generateButtonLabel = computed(() => {
  if (generationStatus.value === 'generating') return 'DeepSeek 正在评课'
  if (isRealReport.value) return '修改后重新生成'
  return '生成 DeepSeek 评课'
})
const scorableItems = computed(() => items.value.filter((item) => !isInsufficientReport(item.report)))
const aiErrorMessage = computed(() => (
  route.query.aiError === 'missingText'
    ? '本次训练已保存。补充课堂文字材料后即可生成真实 AI 评课。'
    : 'DeepSeek 暂时没有生成报告，当前保留的是训练完成时的演示结果，可以直接重试。'
))
const followupReady = computed(() => (
  isRealReport.value
  && generationStatus.value === 'succeeded'
))
const canAskQuestion = computed(() => followupReady.value && !questionLoading.value)
const followupDisabledMessage = computed(() => {
  if (generationStatus.value === 'generating') return 'DeepSeek 正在生成报告，完成后即可追问。'
  if (generationStatus.value === 'failed') return '请先重新生成成功的 DeepSeek 评课报告。'
  return '生成成功的 DeepSeek 评课报告后即可追问。'
})
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
  const history = [...scorableItems.value].slice(0, 8).reverse()
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

async function doRegenerate() {
  if (!current.value?.id) return
  try {
    const next = await regenerateFeedback(current.value.id, pickedNotes.value)
    current.value = next
    items.value = items.value.map((item) => (item.id === next.id ? next : item))
    showCorrect.value = false
  } catch {
    current.value = {
      ...current.value,
      suggestion: '已按校正点重写演示评分。',
    }
  }
}

function activeSessionId() {
  return current.value?.session_id || Number(route.query.sessionId) || null
}

function goToLogin() {
  router.push('/')
}

function clearFollowupState() {
  questionRequestId += 1
  questionDraft.value = ''
  questionAsked.value = ''
  questionAnswer.value = ''
  questionScope.value = 'current'
  questionLoading.value = false
  questionError.value = ''
}

function questionErrorMessage(error) {
  if (isUnauthorizedError(error)) return '登录状态已失效，请重新登录后再追问。'
  if (error?.response?.status === 409) return '请先生成成功的 DeepSeek 评课报告后再追问。'
  if (error?.response?.status === 502) return 'DeepSeek 暂时没有回答，请稍后再试。'
  return error?.response?.data?.message || 'AI 追问失败，请稍后再试。'
}

function syncReviewRoute(item) {
  if (!item?.id || !item?.session_id) return
  const currentFeedbackId = Number(route.query.feedbackId)
  const currentSessionId = Number(route.query.sessionId)
  if (currentFeedbackId === item.id && currentSessionId === item.session_id) return
  router.replace({
    path: '/ai-review',
    query: { sessionId: item.session_id, feedbackId: item.id },
  })
}

function clearInvalidReviewRoute() {
  if (!route.query.feedbackId && !route.query.sessionId) return
  router.replace({ path: '/ai-review' })
}

function applyFeedbackItems(nextItems, { syncRoute = false } = {}) {
  const previousId = current.value?.id
  items.value = nextItems
  const nextCurrent = selectFeedbackForRoute(
    nextItems,
    route.query.feedbackId,
    route.query.sessionId,
  )
  current.value = nextCurrent
  if (previousId && previousId !== nextCurrent?.id) clearFollowupState()
  if (current.value) {
    if (syncRoute) syncReviewRoute(current.value)
  } else {
    clearInvalidReviewRoute()
  }
  return current.value
}

async function loadReviewData() {
  isLoading.value = true
  loadError.value = ''
  loginExpired.value = false
  try {
    const nextItems = await fetchFeedbacks()
    applyFeedbackItems(nextItems, { syncRoute: true })
  } catch (error) {
    items.value = []
    current.value = null
    if (isUnauthorizedError(error)) {
      localStorage.removeItem('link_token')
      loginExpired.value = true
    }
    loadError.value = aiReviewErrorMessage(error)
  } finally {
    isLoading.value = false
  }
}

function setCurrentFeedback(item) {
  if (!item) return
  current.value = item
  const exists = items.value.some((feedback) => feedback.id === item.id)
  items.value = exists
    ? items.value.map((feedback) => (feedback.id === item.id ? item : feedback))
    : [item, ...items.value]
}

async function refreshCurrentFeedback() {
  if (refreshPromise) return refreshPromise
  const feedbackId = current.value?.id || Number(route.query.feedbackId)
  const sessionId = activeSessionId()
  refreshPromise = fetchFeedbacks()
    .then((nextItems) => {
      items.value = nextItems
      const next = selectFeedbackForRoute(nextItems, feedbackId, sessionId)
      if (next) {
        if (current.value?.id && current.value.id !== next.id) clearFollowupState()
        current.value = next
      }
      return next
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

async function handleResume() {
  if (document.visibilityState === 'hidden') return
  try {
    await refreshCurrentFeedback()
  } catch {
    // 保留当前页面和草稿，等待下一次恢复或用户重试。
  }
}

function startStatusPolling() {
  if (statusPollTimer) return
  statusPollTimer = window.setInterval(handleResume, 4000)
}

function stopStatusPolling() {
  if (!statusPollTimer) return
  window.clearInterval(statusPollTimer)
  statusPollTimer = null
}

async function runAiReview() {
  const sessionId = activeSessionId()
  if (!sessionId) {
    aiGenerateError.value = '暂无可生成的训练记录，请先完成一次训练。'
    return
  }
  if (!canGenerateAiReview.value) return
  aiGenerating.value = true
  aiGenerateError.value = ''
  clearFollowupState()
  try {
    const next = await generateAiReview(sessionId, {
      regenerate: isRealReport.value,
    })
    setCurrentFeedback(next)
    await router.replace({
      path: '/ai-review',
      query: { sessionId, feedbackId: next.id },
    })
  } catch (error) {
    try {
      await refreshCurrentFeedback()
    } catch {
      // 使用原请求错误；课堂草稿仍保留在本地。
    }
    if (isUnauthorizedError(error)) {
      localStorage.removeItem('link_token')
      loginExpired.value = true
      loadError.value = aiReviewErrorMessage(error)
    } else {
      const recoveredStatus = report.value.generation_status
      if (!['succeeded', 'generating'].includes(recoveredStatus)) {
        aiGenerateError.value = report.value.generation_error
          || aiReviewErrorMessage(error)
          || 'AI 评课生成失败，请稍后重试。'
      }
    }
  } finally {
    aiGenerating.value = false
  }
}

async function askQuestion() {
  const feedbackId = current.value?.id
  const question = questionDraft.value.trim()
  if (!feedbackId) {
    questionError.value = '暂无可追问的评课报告。'
    return
  }
  if (!followupReady.value) {
    questionError.value = followupDisabledMessage.value
    return
  }
  if (!question) {
    questionError.value = '请输入问题后再发送。'
    return
  }

  questionLoading.value = true
  questionError.value = ''
  questionAnswer.value = ''
  const requestId = ++questionRequestId
  try {
    const result = await askAiReviewQuestion(feedbackId, question)
    if (requestId !== questionRequestId) return
    questionAsked.value = question
    questionScope.value = result?.scope === 'history' ? 'history' : 'current'
    questionAnswer.value = String(result?.answer || '').trim()
    if (!questionAnswer.value) questionError.value = 'DeepSeek 没有返回回答，请稍后再试。'
  } catch (error) {
    if (requestId !== questionRequestId) return
    questionError.value = questionErrorMessage(error)
    if (isUnauthorizedError(error)) {
      localStorage.removeItem('link_token')
      loginExpired.value = true
      loadError.value = questionError.value
    }
  } finally {
    if (requestId === questionRequestId) questionLoading.value = false
  }
}

function selectFeedback(item) {
  current.value = item
  const nextSessionId = item?.session_id
  aiGenerateError.value = ''
  showCorrect.value = false
  clearFollowupState()
  router.replace({
    path: '/ai-review',
    query: { sessionId: nextSessionId, feedbackId: item.id },
  })
}

watch(generationStatus, (status) => {
  if (status === 'generating') startStatusPolling()
  else stopStatusPolling()
})

onMounted(async () => {
  syncDemoBadge()
  window.addEventListener('link-settings', syncDemoBadge)
  window.addEventListener('online', handleResume)
  window.addEventListener('focus', handleResume)
  document.addEventListener('visibilitychange', handleResume)
  await loadReviewData()
})
onUnmounted(() => {
  stopStatusPolling()
  window.removeEventListener('link-settings', syncDemoBadge)
  window.removeEventListener('online', handleResume)
  window.removeEventListener('focus', handleResume)
  document.removeEventListener('visibilitychange', handleResume)
})
</script>
