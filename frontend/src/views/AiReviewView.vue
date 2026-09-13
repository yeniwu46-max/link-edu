<template>
  <div class="sparse-page review-page">
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">AI REVIEW</p>
        <h1 class="split-title">AI 评课</h1>
        <p class="page-lead">{{ current?.course_title || '最近一次片段教学' }} · {{ report.mode_label || '评课报告' }}</p>
      </div>
      <span v-if="showDemoBadge" class="review-badge">演示评分</span>
    </header>

    <div class="page-scroll">
      <div v-if="loadError || aiError" class="review-alert" role="alert">
        <p>{{ loadError || aiErrorMessage }}</p>
        <button v-if="loginExpired" type="button" class="ghost-link" @click="goToLogin">返回登录</button>
        <button v-else-if="loadError" type="button" class="ghost-link" @click="loadReviewData">重新加载</button>
      </div>

      <p v-if="report.demo" class="review-alert">
        此份为历史演示 / 规则评分，不与真实课堂分数比较。
        <router-link to="/ai-review">查看模拟课堂评课 →</router-link>
      </p>

      <div class="review-dash">
        <div class="review-dash__main">
          <section class="review-stat-grid" aria-label="评课概览">
            <button
              type="button"
              class="review-stat review-stat--score glass"
              @click="openStatModal('score')"
            >
              <div class="review-stat__copy">
                <small>综合得分</small>
                <strong>
                  <NumberFlow v-if="statOverallScore !== null" :value="statOverallScore" />
                  <span v-else>—</span>
                </strong>
                <span>{{ current && !insufficientEvidence ? '本次评课' : '暂无有效评分' }}</span>
              </div>
              <VChart class="review-stat__chart" :option="miniBarOption" autoresize />
            </button>

            <button
              type="button"
              class="review-stat review-stat--trend glass"
              @click="openStatModal('trend')"
            >
              <div class="review-stat__copy">
                <small>历史趋势</small>
                <strong>{{ historyCountLabel }}</strong>
                <span>近 {{ historySpark.length || 0 }} 次综合分</span>
              </div>
              <VChart class="review-stat__chart" :option="miniLineOption" autoresize />
            </button>

            <button
              type="button"
              class="review-stat review-stat--dims glass"
              @click="openStatModal('dims')"
            >
              <div class="review-stat__copy">
                <small>六维摘要</small>
                <strong>{{ dimHighlight.label }}</strong>
                <span>{{ dimHighlight.detail }}</span>
              </div>
              <ul class="review-stat__dims" aria-label="六维得分">
                <li v-for="item in dimensions.slice(0, 4)" :key="item.key">
                  <em>{{ item.label }}</em>
                  <b>{{ item.score || 0 }}</b>
                </li>
              </ul>
            </button>

            <button
              type="button"
              class="review-stat review-stat--mode glass"
              @click="openStatModal('history')"
            >
              <div class="review-stat__copy">
                <small>训练场次</small>
                <strong>{{ modeStats.total }}</strong>
                <span>专项 {{ modeStats.special }} · 综合 {{ modeStats.full }}</span>
              </div>
              <ul class="review-stat__history" aria-label="近期历史记录">
                <li v-for="item in recentHistoryPreview" :key="item.id">
                  <em>{{ shortHistoryTitle(item) }}</em>
                  <b>{{ scoreLabel(item) }}</b>
                </li>
                <li v-if="!recentHistoryPreview.length" class="is-empty">暂无历史记录</li>
              </ul>
            </button>
          </section>

          <div
            v-if="statModal"
            class="review-stat-modal"
            role="dialog"
            aria-modal="true"
            :aria-label="statModalTitle"
            @click.self="closeStatModal"
          >
            <div class="review-stat-modal__panel glass">
              <header class="review-stat-modal__head">
                <div>
                  <p>{{ statModalKicker }}</p>
                  <h3>{{ statModalTitle }}</h3>
                </div>
                <button type="button" class="ghost-link" @click="closeStatModal">关闭</button>
              </header>

              <div v-if="statModal === 'score'" class="review-stat-modal__body">
                <div class="review-stat-modal__hero">
                  <NumberFlow v-if="statOverallScore !== null" :value="statOverallScore" />
                  <span v-else>—</span>
                  <span>综合得分</span>
                </div>
                <VChart class="review-stat-modal__chart" :option="detailBarOption" autoresize />
              </div>

              <div v-else-if="statModal === 'trend'" class="review-stat-modal__body">
                <div class="review-stat-modal__hero">
                  <strong>{{ historyCountLabel }}</strong>
                  <span>历史有效评分次数</span>
                </div>
                <VChart class="review-stat-modal__chart" :option="detailLineOption" autoresize />
              </div>

              <div v-else-if="statModal === 'dims'" class="review-stat-modal__body">
                <ul class="review-stat-modal__dims">
                  <li v-for="item in dimensions" :key="item.key">
                    <span>{{ item.label }}</span>
                    <b>{{ item.score || 0 }}</b>
                  </li>
                </ul>
                <VChart class="review-stat-modal__chart is-radar" :option="radarOption" autoresize />
              </div>

              <div v-else class="review-stat-modal__body">
                <p class="dock-hint">专项 {{ modeStats.special }} · 综合 {{ modeStats.full }} · 共 {{ modeStats.total }} 次</p>
                <ul class="review-stat-modal__history">
                  <li v-for="item in items" :key="item.id">
                    <button type="button" @click="openHistoryFromModal(item)">
                      <span>
                        <strong>{{ item.course_title || '未命名课程' }}</strong>
                        <em>{{ item.report?.mode_label || item.category || '评课' }} · {{ formatDateTime(item.created_at) }}</em>
                      </span>
                      <b>{{ scoreLabel(item) }}</b>
                    </button>
                  </li>
                  <li v-if="!items.length" class="is-empty">暂无历史评课记录</li>
                </ul>
              </div>
            </div>
          </div>

          <section v-if="!current && !isLoading && !loadError" class="review-empty">
            <h3>暂无可生成的训练记录</h3>
            <p>请先完成一次训练，系统才有可读取的课程、时长和训练状态数据。</p>
            <button type="button" class="ghost-link" @click="router.push('/training')">去完成一次训练</button>
          </section>

          <section v-if="current" class="review-master" aria-label="历史评课与详情">
            <div class="review-list-pane">
              <div class="review-list-pane__head">
                <h3>评课记录</h3>
                <button type="button" class="ghost-link" @click="clearDateFilter">
                  {{ selectedDateKey ? formatDateKey(selectedDateKey) : '全部' }}
                </button>
              </div>
              <ul v-if="filteredFeedbacks.length" class="review-list" aria-label="选择评课报告">
                <li
                  v-for="item in filteredFeedbacks"
                  :key="item.id"
                  :class="{ active: current?.id === item.id }"
                >
                  <button type="button" @click="selectFeedback(item)">
                    <span class="review-list__icon" aria-hidden="true">{{ listIcon(item) }}</span>
                    <span class="review-list__body">
                      <strong>{{ item.course_title || '未命名课程' }}</strong>
                      <em>{{ item.report?.mode_label || item.category || '评课' }}</em>
                    </span>
                    <span class="review-list__meta">
                      <b>{{ scoreLabel(item) }}</b>
                      <time>{{ formatClock(item.created_at) }}</time>
                    </span>
                  </button>
                </li>
              </ul>
              <p v-else class="dock-hint">该日暂无评课记录。</p>
            </div>

            <div class="review-detail glass">
              <div class="review-detail__head">
                <div>
                  <p class="review-detail__kicker">{{ report.mode_label || current.category || '评课详情' }}</p>
                  <h3>{{ current.course_title || '本次评课' }}</h3>
                </div>
                <div class="review-detail__score" v-if="!insufficientEvidence">
                  <NumberFlow :value="current.overall_score || 0" />
                  <small>综合</small>
                </div>
              </div>

              <section v-if="insufficientEvidence" class="review-empty">
                <h3>当前材料暂时无法评分</h3>
                <p>这份内容没有提供可核实的课堂过程，因此不会计入六维评分或历史趋势。请补充课堂转写、教学动作、学生回应或观察记录后重新生成。</p>
              </section>

              <div class="review-detail__tags">
                <span v-if="report.visual_evidence || report.visual_observations_used">关帧观察</span>
                <span v-if="isRealReport">DeepSeek</span>
                <span v-if="report.demo">演示</span>
                <span>{{ formatDateTime(current.created_at) }}</span>
              </div>

              <div class="review-detail__grid" v-if="!insufficientEvidence">
                <VChart class="review-detail__radar" :option="radarOption" autoresize />
                <ul class="review-detail__dims">
                  <li v-for="item in dimensions" :key="item.key">
                    <span>{{ item.label }}</span>
                    <b>{{ item.score }}</b>
                  </li>
                </ul>
              </div>

              <blockquote v-if="report.next_action || current.suggestion">
                {{ report.next_action || current.suggestion }}
              </blockquote>

              <section class="review-replay" aria-label="本次训练回放">
                <div class="review-replay__head">
                  <h4>本次训练回放</h4>
                  <button
                    v-if="replayUrl"
                    type="button"
                    class="ghost-link"
                    @click="downloadReplay"
                  >下载录像</button>
                </div>
                <video
                  v-if="replayUrl"
                  class="review-replay__video"
                  :src="replayUrl"
                  controls
                  playsinline
                ></video>
                <p v-else class="dock-hint">{{ replayHint }}</p>
              </section>

              <div class="review-detail__briefs">
                <article v-if="report.summary">
                  <h4>观察</h4>
                  <p>{{ report.summary }}</p>
                </article>
                <article v-if="report.problems?.length">
                  <h4>主要问题</h4>
                  <p>{{ report.problems.join('；') }}</p>
                </article>
                <article v-if="report.fixes?.length">
                  <h4>改进建议</h4>
                  <p>{{ report.fixes.slice(0, 3).join('；') }}</p>
                </article>
              </div>

              <div class="review-detail__actions">
                <button type="button" class="primary review-pill" @click="showFullReport = !showFullReport">
                  {{ showFullReport ? '收起完整报告' : '查看全部详情' }}
                </button>
                <router-link class="ghost-link" to="/classroom">真实课堂证据报告 →</router-link>
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
                <div v-if="showFullReport" class="review-lists">
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

              <section v-if="showAiReviewGenerator" class="review-followup review-materials">
                <h4>补充评课材料</h4>
                <p>本次材料将发送至 DeepSeek 生成评课，并产生模型调用费用；已上传的关键帧可能用于云端视觉分析。</p>
                <label>课堂转写
                  <textarea v-model="materialDraft.transcript" rows="5" @input="saveMaterials" placeholder="记录课堂原话、教师动作和学生回应"></textarea>
                </label>
                <label>教师备注
                  <textarea v-model="materialDraft.teacherNotes" rows="3" @input="saveMaterials" placeholder="补充希望 AI 核对的课堂证据"></textarea>
                </label>
                <p>材料按训练记录保存在本机，生成时只提交当前记录。</p>
                <p v-if="generationTimedOut" class="review-generator__status is-failed">生成超时，服务端状态仍在核对，可稍后重试。</p>
              </section>

              <section class="review-followup">
                <h4>继续追问本次评课</h4>
                <p v-if="!followupReady" class="review-generator__status">{{ followupDisabledMessage }}</p>
                <textarea
                  v-model="questionDraft"
                  rows="4"
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
            </div>
          </section>
        </div>

        <aside class="review-rail glass" aria-label="评课日程">
          <div class="review-cal">
            <div class="review-cal__head">
              <button type="button" class="ghost-link" @click="shiftMonth(-1)" aria-label="上一月">‹</button>
              <strong>{{ calendarTitle }}</strong>
              <button type="button" class="ghost-link" @click="shiftMonth(1)" aria-label="下一月">›</button>
            </div>
            <div class="review-cal__weekdays">
              <span v-for="day in weekdays" :key="day">{{ day }}</span>
            </div>
            <div class="review-cal__grid">
              <button
                v-for="cell in calendarCells"
                :key="cell.key"
                type="button"
                :disabled="!cell.inMonth"
                :class="{
                  muted: !cell.inMonth,
                  marked: cell.marked,
                  selected: cell.dateKey === selectedDateKey,
                  today: cell.dateKey === todayKey,
                }"
                @click="selectCalendarDate(cell)"
              >{{ cell.day }}</button>
            </div>
          </div>

          <div class="review-rail__actions">
            <p v-if="current" class="dock-hint">生成时将发送当前材料及已上传关键帧至云端，并产生模型调用费用。</p>
            <button
              v-if="showAiReviewGenerator && current"
              type="button"
              class="primary review-pill"
              :disabled="!canGenerateAiReview"
              @click="runAiReview"
            >
              {{ generateButtonLabel }}
            </button>
            <p v-if="generationStatus === 'generating'" class="review-generator__status">
              DeepSeek 正在生成，可暂时离开此页。
            </p>
            <p v-else-if="generationStatus === 'failed'" class="review-generator__status is-failed">
              上一次生成未完成，可直接重试。
            </p>
            <p v-if="aiGenerateError" class="error">{{ aiGenerateError }}</p>
            <button type="button" class="review-pill review-pill--ghost" @click="revealFullReport">
              查看全部详情
            </button>
          </div>

          <div class="review-timeline">
            <div class="review-list-pane__head">
              <h3>当日时间轴</h3>
              <span>{{ formatDateKey(timelineDateKey) }}</span>
            </div>
            <ol v-if="timelineItems.length">
              <li v-for="item in timelineItems" :key="item.id">
                <time>{{ formatClock(item.created_at) }}</time>
                <button type="button" @click="selectFeedback(item)">
                  <strong>{{ item.course_title || '评课' }}</strong>
                  <span>{{ item.report?.mode_label || item.category || '训练' }} · {{ scoreLabel(item) }}</span>
                </button>
              </li>
            </ol>
            <p v-else class="dock-hint">这一天还没有评课记录。</p>
          </div>
        </aside>
      </div>
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
import {
  askAiReviewQuestion,
  fetchFeedbacks,
  generateAiReview,
} from '../services/dashboard'
import { getRecording } from '../services/trainingReplayStore'
import {
  aiReviewErrorMessage,
  aiReviewQuestionErrorMessage,
  isUnauthorizedError,
} from '../utils/aiReviewErrors'
import {
  isGenerationTimedOut,
  isInsufficientReport,
  loadAiReviewMaterials,
  saveAiReviewMaterials,
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
const aiGenerating = ref(false)
const aiGenerateError = ref('')
const questionDraft = ref('')
const questionAsked = ref('')
const questionAnswer = ref('')
const questionScope = ref('current')
const questionLoading = ref(false)
const questionError = ref('')
const materialDraft = ref({ transcript: '', teacherNotes: '' })
const currentTime = ref(Date.now())
let questionRequestId = 0
let generationRequestId = 0
let statusPollTimer = null
let refreshPromise = null
let replayRequestId = 0
const replayUrl = ref('')
const replayMeta = ref(null)
const replayHint = ref('正在查找本机训练录像…')
const showFullReport = ref(false)
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const calendarCursor = ref(startOfMonth(new Date()))
const selectedDateKey = ref('')
const statModal = ref('')

function revokeReplayUrl() {
  if (replayUrl.value) {
    URL.revokeObjectURL(replayUrl.value)
    replayUrl.value = ''
  }
  replayMeta.value = null
}

async function loadLocalReplay() {
  const requestId = ++replayRequestId
  revokeReplayUrl()
  const sessionId = activeSessionId()
  if (!sessionId) {
    replayHint.value = '本机未找到录像（打开具体训练会话后可回放）。'
    return
  }
  try {
    const record = await getRecording(sessionId)
    if (requestId !== replayRequestId || sessionId !== activeSessionId()) return
    if (!record?.blob) {
      replayHint.value = '本机未找到录像（可能未勾选录制、换过浏览器，或站点数据已清除）。'
      return
    }
    replayMeta.value = record
    replayUrl.value = URL.createObjectURL(record.blob)
    replayHint.value = ''
  } catch {
    if (requestId !== replayRequestId) return
    replayHint.value = '本机未找到录像（可能未勾选录制、换过浏览器，或站点数据已清除）。'
  }
}

function downloadReplay() {
  if (!replayUrl.value || !replayMeta.value) return
  const anchor = document.createElement('a')
  anchor.href = replayUrl.value
  anchor.download = replayMeta.value.filename || `临客训练-${activeSessionId()}.webm`
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

const aiError = computed(() => Boolean(route.query.aiError))
const insufficientEvidence = computed(() => isInsufficientReport(report.value))
const generationStatus = computed(() => (
  aiGenerating.value ? 'generating' : report.value.generation_status || 'idle'
))
const generationTimedOut = computed(() => isGenerationTimedOut(report.value, currentTime.value))
const isRealReport = computed(() => report.value.source === 'deepseek' && report.value.demo !== true)
const showAiReviewGenerator = computed(() => Boolean(current.value))
const canGenerateAiReview = computed(() => (
  !aiGenerating.value
  && (generationStatus.value !== 'generating' || generationTimedOut.value)
))
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
  if (!current.value || insufficientEvidence.value) return []
  if (report.value.dimensions?.length) return report.value.dimensions
  return [
    { key: 'clarity', label: '表达清晰度', score: current.value?.clarity_score || 0 },
    { key: 'pace', label: '教学节奏', score: current.value?.pace_score || 0 },
    { key: 'interaction', label: '互动设计', score: current.value?.interaction_score || 0 },
  ]
})

const todayKey = computed(() => toDateKey(new Date()))
const markedDateKeys = computed(() => {
  const keys = new Set()
  for (const item of items.value) {
    const key = toDateKey(item.created_at)
    if (key) keys.add(key)
  }
  return keys
})
const calendarTitle = computed(() => {
  const date = calendarCursor.value
  return `${date.getFullYear()}年${date.getMonth() + 1}月`
})
const calendarCells = computed(() => {
  const cursor = calendarCursor.value
  const year = cursor.getFullYear()
  const month = cursor.getMonth()
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let index = 0; index < 42; index += 1) {
    const dayNumber = index - startOffset + 1
    const inMonth = dayNumber >= 1 && dayNumber <= daysInMonth
    const date = inMonth ? new Date(year, month, dayNumber) : new Date(year, month, dayNumber)
    const dateKey = toDateKey(date)
    cells.push({
      key: `${year}-${month}-${index}`,
      day: date.getDate(),
      inMonth,
      dateKey,
      marked: markedDateKeys.value.has(dateKey),
    })
  }
  return cells
})
const filteredFeedbacks = computed(() => {
  if (!selectedDateKey.value) return items.value
  return items.value.filter((item) => toDateKey(item.created_at) === selectedDateKey.value)
})
const timelineDateKey = computed(() => selectedDateKey.value || todayKey.value)
const timelineItems = computed(() => (
  items.value
    .filter((item) => toDateKey(item.created_at) === timelineDateKey.value)
    .slice()
    .sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')))
))
const historySpark = computed(() => [...scorableItems.value].slice(0, 8).reverse())
const historyCountLabel = computed(() => `${scorableItems.value.length} 次`)
const statOverallScore = computed(() => {
  if (!current.value || insufficientEvidence.value) return null
  return current.value.overall_score ?? null
})
const dimHighlight = computed(() => {
  const list = dimensions.value.filter((item) => Number.isFinite(Number(item.score)))
  if (!list.length || !current.value || insufficientEvidence.value) {
    return { label: '暂无', detail: '生成有效报告后显示' }
  }
  const ranked = [...list].sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
  const best = ranked[0]
  const worst = ranked[ranked.length - 1]
  return {
    label: best.label,
    detail: `最高 ${best.score} · 待提升 ${worst.label} ${worst.score}`,
  }
})
const modeStats = computed(() => {
  let special = 0
  let full = 0
  for (const item of items.value) {
    const label = `${item.report?.mode_label || ''} ${item.category || ''} ${item.course_title || ''}`
    if (/综合|10\s*分钟|完整/.test(label)) full += 1
    else special += 1
  }
  return { special, full, total: items.value.length }
})
const recentHistoryPreview = computed(() => items.value.slice(0, 4))
const statModalTitle = computed(() => ({
  score: '综合得分详情',
  trend: '历史趋势详情',
  dims: '六维评分详情',
  history: '训练历史记录',
}[statModal.value] || '详情'))
const statModalKicker = computed(() => ({
  score: 'SCORE',
  trend: 'TREND',
  dims: 'DIMENSIONS',
  history: 'HISTORY',
}[statModal.value] || 'DETAIL'))

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

const miniBarOption = computed(() => ({
  animationDuration: 500,
  grid: { left: 2, right: 2, top: 6, bottom: 0 },
  xAxis: { type: 'category', show: false, data: dimensions.value.map((item) => item.label) },
  yAxis: { type: 'value', show: false, min: 0, max: 100 },
  series: [{
    type: 'bar',
    barWidth: '68%',
    barCategoryGap: '18%',
    data: dimensions.value.map((item) => item.score || 0),
    itemStyle: { color: 'rgba(255,122,24,.88)', borderRadius: [5, 5, 0, 0] },
  }],
}))

const miniLineOption = computed(() => ({
  animationDuration: 500,
  grid: { left: 2, right: 4, top: 8, bottom: 2 },
  xAxis: {
    type: 'category',
    show: false,
    data: historySpark.value.map((item, index) => item.created_at?.slice(5, 10) || `#${index + 1}`),
  },
  yAxis: { type: 'value', show: false, min: 50, max: 100 },
  series: [{
    type: 'line',
    smooth: true,
    symbol: 'none',
    data: historySpark.value.map((item) => item.overall_score || 0),
    lineStyle: { width: 2.5, color: '#b45cff' },
    areaStyle: { color: 'rgba(180,92,255,.22)' },
  }],
}))

const detailBarOption = computed(() => ({
  animationDuration: 500,
  grid: { left: 28, right: 12, top: 24, bottom: 40, containLabel: true },
  tooltip,
  xAxis: {
    type: 'category',
    data: dimensions.value.map((item) => item.label),
    axisLabel: { color: '#b9b3bd', fontSize: 11, rotate: 18 },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    splitLine: { lineStyle: { color: 'rgba(255,255,255,.08)' } },
    axisLabel: { color: '#9d97a3' },
  },
  series: [{
    type: 'bar',
    barWidth: 28,
    data: dimensions.value.map((item) => item.score || 0),
    itemStyle: { color: '#ff7a18', borderRadius: [6, 6, 0, 0] },
  }],
}))

const detailLineOption = computed(() => ({
  animationDuration: 500,
  grid: { left: 28, right: 16, top: 24, bottom: 32, containLabel: true },
  tooltip,
  xAxis: {
    type: 'category',
    data: historySpark.value.map((item, index) => item.created_at?.slice(5, 10) || `#${index + 1}`),
    axisLabel: { color: '#b9b3bd' },
    axisLine: { lineStyle: { color: 'rgba(255,255,255,.16)' } },
  },
  yAxis: {
    type: 'value',
    min: 50,
    max: 100,
    splitLine: { lineStyle: { color: 'rgba(255,255,255,.08)' } },
    axisLabel: { color: '#9d97a3' },
  },
  series: [{
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 8,
    data: historySpark.value.map((item) => item.overall_score || 0),
    lineStyle: { width: 3, color: '#b45cff' },
    itemStyle: { color: '#ff7a18' },
    areaStyle: { color: 'rgba(180,92,255,.16)' },
  }],
}))

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function toDateKey(value) {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDateKey(key) {
  if (!key) return '全部'
  const [year, month, day] = key.split('-')
  return `${Number(month)}/${Number(day)}`
}

function formatClock(value) {
  if (!value) return '--:--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--'
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getMonth() + 1}/${date.getDate()} ${formatClock(value)}`
}

function scoreLabel(item) {
  if (isInsufficientReport(item?.report)) return '待补证据'
  const score = item?.overall_score
  return Number.isFinite(Number(score)) ? `${score} 分` : '未评分'
}

function listIcon(item) {
  const label = `${item?.report?.mode_label || ''} ${item?.category || ''}`
  if (/综合|完整|10/.test(label)) return '综'
  return '专'
}

function shortHistoryTitle(item) {
  const title = String(item?.course_title || '评课')
  return title.length > 6 ? `${title.slice(0, 6)}…` : title
}

function openStatModal(kind) {
  statModal.value = kind
}

function closeStatModal() {
  statModal.value = ''
}

function openHistoryFromModal(item) {
  closeStatModal()
  if (item) selectFeedback(item)
}

function shiftMonth(delta) {
  const cursor = calendarCursor.value
  calendarCursor.value = new Date(cursor.getFullYear(), cursor.getMonth() + delta, 1)
}

function selectCalendarDate(cell) {
  if (!cell?.inMonth) return
  const nextKey = selectedDateKey.value === cell.dateKey ? '' : cell.dateKey
  selectedDateKey.value = nextKey
  if (!nextKey) return
  const first = items.value.find((item) => toDateKey(item.created_at) === nextKey)
  if (first) selectFeedback(first)
}

function clearDateFilter() {
  selectedDateKey.value = ''
}

function revealFullReport() {
  showFullReport.value = true
  requestAnimationFrame(() => {
    document.querySelector('.review-report')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

function activeSessionId() {
  return current.value?.session_id || Number(route.query.sessionId) || null
}

function formatFeedbackDate(value) {
  if (!value) return '未记录日期'
  return String(value).slice(0, 10)
}

function feedbackStatusLabel(item) {
  const itemReport = item?.report || {}
  if (itemReport.generation_status === 'generating') return '生成中'
  if (itemReport.generation_status === 'failed') return '失败可重试'
  if (isInsufficientReport(itemReport)) return '证据不足'
  if (itemReport.source === 'deepseek' && itemReport.demo !== true) return '真实报告'
  if (itemReport.demo === true) return '演示'
  return '待生成'
}

function restoreMaterials(sessionId) {
  materialDraft.value = loadAiReviewMaterials(localStorage, sessionId)
}

function saveMaterials() {
  const sessionId = activeSessionId()
  if (!sessionId) return
  saveAiReviewMaterials(localStorage, sessionId, materialDraft.value)
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

function invalidateGenerationRequest() {
  generationRequestId += 1
  aiGenerating.value = false
}

function questionErrorMessage(error) {
  return aiReviewQuestionErrorMessage(error)
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
  const previousSessionId = current.value?.session_id
  items.value = nextItems
  const nextCurrent = selectFeedbackForRoute(
    nextItems,
    route.query.feedbackId,
    route.query.sessionId,
  )
  current.value = nextCurrent
  if (previousId && previousId !== nextCurrent?.id) {
    invalidateGenerationRequest()
    clearFollowupState()
  }
  if (nextCurrent && previousSessionId !== nextCurrent.session_id) {
    restoreMaterials(nextCurrent.session_id)
  }
  if (current.value) {
    if (syncRoute) syncReviewRoute(current.value)
  } else {
    clearInvalidReviewRoute()
  }
  void loadLocalReplay()
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
  const previousSessionId = current.value?.session_id
  current.value = item
  const exists = items.value.some((feedback) => feedback.id === item.id)
  items.value = exists
    ? items.value.map((feedback) => (feedback.id === item.id ? item : feedback))
    : [item, ...items.value]
  if (previousSessionId !== item.session_id) restoreMaterials(item.session_id)
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
        if (current.value?.id && current.value.id !== next.id) {
          invalidateGenerationRequest()
          clearFollowupState()
        }
        if (current.value?.session_id !== next.session_id) restoreMaterials(next.session_id)
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
  currentTime.value = Date.now()
  try {
    await refreshCurrentFeedback()
  } catch {
    // 保留当前页面和草稿，等待下一次恢复或用户重试。
  }
}

function startStatusPolling() {
  if (statusPollTimer) return
  currentTime.value = Date.now()
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
  const requestId = ++generationRequestId
  aiGenerateError.value = ''
  clearFollowupState()
  saveMaterials()
  try {
    const next = await generateAiReview(sessionId, {
      transcript_text: materialDraft.value.transcript.trim(),
      teacher_notes: materialDraft.value.teacherNotes.trim(),
      regenerate: isRealReport.value,
    })
    if (requestId !== generationRequestId || activeSessionId() !== sessionId) return
    setCurrentFeedback(next)
    saveAiReviewMaterials(localStorage, sessionId, { transcript: '', teacherNotes: '' })
    materialDraft.value = { transcript: '', teacherNotes: '' }
    await router.replace({
      path: '/ai-review',
      query: { sessionId, feedbackId: next.id },
    })
  } catch (error) {
    if (requestId !== generationRequestId) return
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
      if (['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code) && recoveredStatus !== 'succeeded') {
        aiGenerateError.value = '请求超时，正在核对服务端状态，请稍后刷新。'
      } else if (!['succeeded', 'generating'].includes(recoveredStatus)) {
        aiGenerateError.value = report.value.generation_error
          || aiReviewErrorMessage(error)
          || 'AI 评课生成失败，请稍后重试。'
      }
    }
  } finally {
    if (requestId === generationRequestId) aiGenerating.value = false
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
  invalidateGenerationRequest()
  current.value = item
  showFullReport.value = false
  const nextSessionId = item?.session_id
  aiGenerateError.value = ''
  restoreMaterials(nextSessionId)
  clearFollowupState()
  router.replace({
    path: '/ai-review',
    query: { sessionId: nextSessionId, feedbackId: item.id },
  })
  void loadLocalReplay()
}

function selectFeedbackById(event) {
  const item = items.value.find((feedback) => feedback.id === Number(event.target.value))
  if (item) selectFeedback(item)
}

watch(generationStatus, (status) => {
  if (status === 'generating') startStatusPolling()
  else stopStatusPolling()
})

function onStatModalKeydown(event) {
  if (event.key === 'Escape') closeStatModal()
}

watch(statModal, (value, _prev, onCleanup) => {
  if (!value) return
  window.addEventListener('keydown', onStatModalKeydown)
  onCleanup(() => window.removeEventListener('keydown', onStatModalKeydown))
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
  replayRequestId += 1
  invalidateGenerationRequest()
  clearFollowupState()
  stopStatusPolling()
  revokeReplayUrl()
  window.removeEventListener('link-settings', syncDemoBadge)
  window.removeEventListener('online', handleResume)
  window.removeEventListener('focus', handleResume)
  document.removeEventListener('visibilitychange', handleResume)
})
</script>

<style scoped>
.review-replay {
  margin: 16px 0 0;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  background: rgba(8, 6, 12, 0.35);
}
.review-replay__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.review-replay__head h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.review-replay__video {
  display: block;
  width: 100%;
  max-width: 100%;
  max-height: 180px;
  border-radius: 12px;
  background: #050407;
  object-fit: contain;
}
</style>
