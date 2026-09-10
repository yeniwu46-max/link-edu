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
        <p class="dock-hint">{{ dayHint }}</p>
        <form class="journal-form" @submit.prevent="submitJournal">
          <textarea v-model="journalBody" rows="3" placeholder="手动写一条训练日志，比如今天候答停够了。"></textarea>
          <button class="primary" type="submit">写下日志</button>
        </form>
        <ul class="journal-list">
          <li v-for="item in weekly.journals || []" :key="item.id">
            <em>{{ item.entry_date }}</em>
            <span>{{ item.body }}</span>
          </li>
        </ul>
        <div class="summary-cards">
          <SummaryCard v-for="item in weekly.summaries || []" :key="item.id" :item="item" />
        </div>
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
          <button class="primary" type="button" @click="doRegenerate">按校正点重写</button>
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
const pickedNotes = ref([])
const growthRecords = ref([])
const growthDay = ref('')
const growthFocus = ref(null)

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
  sessions: 3,
  total_minutes: 86,
  sparkline: [12, 18, 15, 22, 19, 24, 3],
  heatmap: [],
  month_heatmap: [],
  journals: [],
  summaries: [
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
  ],
})
const continueTraining = ref({
  course_id: 1,
  course_title: '课堂导入与提问设计',
  category: '教育学 · 微格教学',
  status_label: '进行中',
  progress_percent: 68,
  last_trained_at: null,
})
const aiFeedback = ref({
  id: 1,
  overall_score: 86,
  course_title: '课堂导入与提问设计',
  suggestion: '减少连续讲述，增加等待时间',
  dimensions: [
    { key: 'clarity', label: '表达清晰度', score: 90, brief: '指令和概念是否能被学生一次听懂。' },
    { key: 'pace', label: '教学节奏', score: 82, brief: '开场、等待、推进有没有挤在一起。' },
    { key: 'interaction', label: '互动设计', score: 85, brief: '提问、讨论之后有没有全班回收。' },
    { key: 'posture', label: '教态与站位', score: 80, brief: '面向学生、板书与巡视是否分开。' },
    { key: 'questioning', label: '提问质量', score: 84, brief: '问题是否具体，有没有追问。' },
    { key: 'structure', label: '课堂结构', score: 81, brief: '目标、过程、小结是否看得见。' },
  ],
  report: {
    mode_label: '片段练习',
    next_action: '减少连续讲述，增加等待时间',
    sections: [
      { title: '综合判断', body: '本次片段练习综合分 86。相对最稳的是表达清晰度，最该补的是教学节奏：提问后把等待做满。' },
      { title: '表达与语言', body: '开场请先给出本节课要解决的问题，再展开概念。关键指令只说一遍，说完停 1 秒。' },
      { title: '节奏与时间', body: '导入控制在总时长的前 1/4，提问后至少等待 8 秒。片段练习不必求全，把这一个技能做满即可。' },
      { title: '互动与提问', body: '问题要能指向黑板结构。学生回答后追问一次「为什么」，小组活动结束必须做 10 秒全班回收。' },
      { title: '教态与板书', body: '讲解时肩线对学生。板书左栏目标/过程/结论，右栏放例子。巡视时走下讲台一次。' },
    ],
    strengths: ['表达清晰度这一项最高，下次训练可以把它当稳定盘。', '能够按选定模式把训练走完，主路径没有断。'],
    fixes: ['优先改教学节奏：开场、等待、推进有没有挤在一起。', '减少连续讲述，增加等待时间', '结束前用一句话重述学习目标。'],
  },
})
const quickEntries = ref([
  { title: '我的课程', description: '11 门课程', icon: '▤', route: '/courses' },
  { title: '模拟课堂', description: '创建训练场景', icon: '◈', route: '/training' },
  { title: 'AI 评课', description: '查看分析报告', icon: '◔', route: '/ai-review' },
  { title: '资源中心', description: '教案与素材', icon: '▣', route: '/resources' },
])
const growthTrajectory = ref([72, 76, 79, 81, 80, 84, 86])
const corrections = [
  { id: 'pace_ok', label: '节奏其实正常，没有赶课', key: 'pace', delta: 6 },
  { id: 'waited', label: '提问后已经等够了', key: 'questioning', delta: 7 },
  { id: 'had_interaction', label: '互动其实发生了', key: 'interaction', delta: 7 },
  { id: 'board_clear', label: '板书分区是清楚的', key: 'structure', delta: 6 },
  { id: 'intro_enough', label: '导入并不短', key: 'clarity', delta: 5 },
  { id: 'posture_ok', label: '教态没有背对学生', key: 'posture', delta: 6 },
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
  if (item) growthFocus.value = item.id
}

async function submitJournal() {
  const body = journalBody.value.trim()
  if (!body) return
  try {
    const item = await addJournal({ entry_date: pickedDay.value || new Date().toISOString().slice(0, 10), body })
    weekly.value.journals = [item, ...(weekly.value.journals || [])]
    journalBody.value = ''
  } catch {
    weekly.value.journals = [{ id: Date.now(), entry_date: pickedDay.value || '今天', body }, ...(weekly.value.journals || [])]
    journalBody.value = ''
  }
}

function applyLocalCorrection(feedback, noteIds) {
  const report = { ...(feedback.report || {}) }
  const dims = (feedback.dimensions || report.dimensions || []).map((item) => ({ ...item }))
  const applied = []
  for (const id of noteIds) {
    const option = corrections.find((item) => item.id === id)
    if (!option) continue
    applied.push(option.label)
    const dim = dims.find((item) => item.key === option.key)
    if (dim) dim.score = Math.max(62, Math.min(98, Number(dim.score || 70) + option.delta))
  }
  const overall = dims.length
    ? Math.max(68, Math.min(96, Math.round(dims.reduce((sum, item) => sum + Number(item.score || 0), 0) / dims.length)))
    : feedback.overall_score
  const weak = [...dims].sort((a, b) => a.score - b.score)[0]
  const strong = [...dims].sort((a, b) => b.score - a.score)[0]
  const noteText = applied.join('、') || '你标记了校对不准，但没有勾选具体校正点'
  const nextAction = applied.length && weak
    ? `已吸收校正：${applied[0]}。优先改${weak.label}：${weak.brief || ''}`
    : (weak ? `优先改${weak.label}：${weak.brief || ''}` : '已按勾选重写演示评分。')
  const previous = (report.sections || []).filter((item) => item.title !== '校正说明')
  return {
    ...feedback,
    overall_score: overall,
    suggestion: nextAction,
    dimensions: dims,
    report: {
      ...report,
      overall_score: overall,
      dimensions: dims,
      corrected: true,
      corrections: applied,
      next_action: nextAction,
      suggestion: nextAction,
      sections: [
        {
          title: '校正说明',
          body: `已按你的勾选重写本份报告：${noteText}。分数仍是可解释的演示评分，不是外部大模型。`,
        },
        ...previous,
      ],
      strengths: strong
        ? [
          `${strong.label}这一项最高，下次训练可以把它当稳定盘。`,
          applied.length ? '已按你勾选的校正点调整了演示评分。' : '能够按选定模式把训练走完，主路径没有断。',
        ]
        : (report.strengths || []),
      fixes: weak
        ? [
          `优先改${weak.label}：${weak.brief || ''}`,
          nextAction,
          '结束前用一句话重述学习目标，让这节课有收口。',
        ]
        : (report.fixes || []),
    },
  }
}

async function doRegenerate() {
  if (!aiFeedback.value?.id) return
  try {
    aiFeedback.value = await regenerateFeedback(aiFeedback.value.id, pickedNotes.value)
  } catch {
    aiFeedback.value = applyLocalCorrection(aiFeedback.value, pickedNotes.value)
  }
  showCorrect.value = false
  regenOk.value = true
}

async function loadDashboard() {
  applyGreeting()
  try {
    const data = await fetchDashboardOverview()
    applyGreeting(data.greeting)
    weekly.value = { ...weekly.value, ...(data.weekly_training || {}) }
    continueTraining.value = data.continue_training || continueTraining.value
    aiFeedback.value = data.ai_feedback || aiFeedback.value
    quickEntries.value = data.quick_entries || quickEntries.value
    growthTrajectory.value = data.growth_trajectory || growthTrajectory.value
    growthRecords.value = data.growth_records || []
    if (data.greeting) auth.user = { ...auth.user, ...data.greeting }
  } catch (error) {
    console.warn('[Dashboard] 使用本地演示数据', error)
    if (!growthRecords.value.length) {
      growthRecords.value = [
        { id: 1, date: '08月28日', time: '14:20', course_title: '课堂导入与提问设计', overall_score: 86, suggestion: '减少连续讲述，增加等待时间', mode_label: '片段练习' },
        { id: 2, date: '08月27日', time: '09:10', course_title: '提问候答', overall_score: 82, suggestion: '追问一次为什么', mode_label: '片段练习' },
        { id: 3, date: '08月26日', time: '16:40', course_title: '板书结构', overall_score: 79, suggestion: '左栏写结构，右栏放例子', mode_label: '完整课' },
      ]
    }
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
