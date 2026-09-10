<template>
  <div class="training-page">
    <section class="stage stage--fill">
      <video
        v-show="!cameraOn"
        class="stage-video"
        src="/assets/login-bg.mp4"
        poster="/assets/login-bg.png"
        autoplay
        muted
        loop
        playsinline
      ></video>
      <video v-show="cameraOn" ref="camRef" class="stage-video" autoplay muted playsinline></video>
      <div class="scanline" :class="{ dim: cameraOn }" aria-hidden="true"></div>

      <header class="train-hud">
        <GlassSurface class="train-hud__glass">
          <div>
            <small>{{ cameraOn ? '镜头监测中' : '演示舞台' }}</small>
            <strong>{{ courseTitle }}</strong>
          </div>
          <div class="hud-meta">
            <span>{{ modeLabel }}</span>
            <span>{{ liveHint }}</span>
            <button type="button" class="hud-cam" @click="toggleCamera">
              {{ cameraOn ? '关闭镜头' : '打开镜头' }}
            </button>
          </div>
        </GlassSurface>
      </header>

      <div v-if="running" class="monitor-strip" aria-label="训练监测">
        <GlassSurface v-for="meter in meters" :key="meter.label" class="meter-pill">
          <em>{{ meter.label }}</em>
          <b>{{ meter.value }}</b>
        </GlassSurface>
      </div>

      <StageWave v-if="running" :active="running" :progress="progress" />

      <div v-if="running" class="train-dock train-dock--live">
        <GlassSurface class="train-live-bar">
          <div class="timer-block">
            <p>剩余</p>
            <div class="timer-digits">
              <NumberFlow :value="minutes" :format="{ minimumIntegerDigits: 2 }" />
              <span>:</span>
              <NumberFlow :value="seconds" :format="{ minimumIntegerDigits: 2 }" />
            </div>
          </div>
          <p class="live-prompt">{{ prompt }}</p>
          <Magnet>
            <button class="primary train-cta" type="button" :disabled="finishing" @click="finish">
              {{ finishing ? '正在生成评课' : '结束并生成评课' }}
            </button>
          </Magnet>
        </GlassSurface>
      </div>

      <div v-else class="train-setup">
        <GlassSurface class="train-setup__card" :radius="32">
          <p class="train-setup__kicker">开始上台</p>
          <router-link to="/classroom" class="primary train-cta" style="display:inline-flex;margin-bottom:16px">进入真实 AI 课堂 · 分数的初步认识 →</router-link>
          <p class="dock-hint">以下为原演示/规则训练入口，不包含真实语音互动；真实课堂请使用上方入口。</p>
          <h2>选阶段练习，或直接上完整课</h2>
          <SkillPills :items="modePills" v-model="mode" />
          <SkillPills
            v-if="mode === 'fragment'"
            :items="skillPills"
            :model-value="courseId"
            @update:model-value="pickSkill"
          />
          <p class="dock-hint">{{ setupHint }}</p>
          <div class="setup-actions">
            <button type="button" class="ghost-link" @click="toggleCamera">
              {{ cameraOn ? '关闭镜头' : '打开镜头观察教态' }}
            </button>
            <Magnet>
              <button class="primary train-cta" type="button" @click="begin">
                开始{{ mode === 'full' ? ' 10 分钟' : ' 8 分钟' }}
              </button>
            </Magnet>
          </div>
        </GlassSurface>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NumberFlow from '@number-flow/vue'
import { useUserMedia } from '@vueuse/core'
import GlassSurface from '../components/fx/GlassSurface.vue'
import Magnet from '../components/fx/Magnet.vue'
import SkillPills from '../components/fx/SkillPills.vue'
import StageWave from '../components/fx/StageWave.vue'
import { completeTraining, fetchCourses, patchTraining, startTraining } from '../services/dashboard'
import { loadSettings } from '../utils/settings'

const FRAGMENT = 8 * 60
const FULL = 10 * 60
const FULL_PHASES = [
  { id: '导入', until: 0.25 },
  { id: '提问', until: 0.5 },
  { id: '板书', until: 0.75 },
  { id: '互动', until: 1 },
]
const SKILL_PROMPTS = {
  导入: '同学们好。今天我们从生活里的一个问题开始——请先看黑板。',
  提问: '如果把这个现象反过来，会发生什么？请先想 8 秒，再举手。',
  板书: '请看左侧结构：目标 → 过程 → 结论。例子写在右侧。',
  演示: '先告诉学生看什么，再出示材料，最后核对观察结果。',
  讲解: '先给定义，再举正例和反例，请学生用自己的话复述。',
  强化: '对学生的回答给出具体反馈，不要只说「很好」。',
  结束: '回扣目标，请学生一句话总结，再布置能完成的作业。',
  组织: '给出清晰指令，活动后用 10 秒全班回收。',
  变化: '重点句放慢，视线扫到后排，写板书时侧身。',
  互动: '同桌讨论 30 秒。结束后请一组分享，我做 10 秒全班回收。',
  完整: '10 分钟连续上台：导入、提问、讲解板书、互动、收口。',
}

const route = useRoute()
const router = useRouter()
const camRef = ref(null)
const cameraOn = ref(false)
const scene = ref('导入')
const mode = ref('fragment')
const running = ref(false)
const remain = ref(FRAGMENT)
const sessionId = ref(null)
const courseId = ref(Number(route.query.courseId) || 0)
const courseTitle = ref('导入技能')
const courses = ref([])
let tick = null
let startedAt = 0
let sessionPromise = null
const finishing = ref(false)

const modePills = [
  { id: 'fragment', label: '阶段练习 8 分钟' },
  { id: 'full', label: '完整 10 分钟' },
]

const skillCourses = computed(() => courses.value.filter((item) => String(item.stage || '').startsWith('专项')))
const fullCourses = computed(() => courses.value.filter((item) => String(item.stage || '').startsWith('综合')))
const skillPills = computed(() => skillCourses.value.map((item) => ({
  id: item.id,
  label: shortSkill(item),
})))

const totalSeconds = computed(() => (mode.value === 'full' ? FULL : FRAGMENT))
const modeLabel = computed(() => (mode.value === 'full' ? '完整 10 分钟' : '阶段练习 8 分钟'))
const elapsedRatio = computed(() => {
  const spent = totalSeconds.value - remain.value
  return Math.min(1, Math.max(0, spent / totalSeconds.value))
})
const liveScene = computed(() => {
  if (mode.value !== 'full') return scene.value
  const ratio = elapsedRatio.value
  return FULL_PHASES.find((item) => ratio <= item.until)?.id || '互动'
})
const liveHint = computed(() => (mode.value === 'full' ? liveScene.value : shortSkill(currentCourse.value)))
const prompt = computed(() => {
  if (mode.value === 'full') {
    if (!running.value) return SKILL_PROMPTS.完整
    return SKILL_PROMPTS[liveScene.value] || SKILL_PROMPTS.完整
  }
  return SKILL_PROMPTS[scene.value] || SKILL_PROMPTS.导入
})
const setupHint = computed(() => {
  if (mode.value === 'full') return '10 分钟连续上台，开始后不再切换路径。适合综合模拟或教资试讲。'
  return '点一项技能做对应练习。开始后整屏监测教态，台上不再改走另一条路径。'
})
const minutes = computed(() => Math.floor(remain.value / 60))
const seconds = computed(() => remain.value % 60)
const progress = computed(() => Math.round(elapsedRatio.value * 100))
const elapsedMinutes = computed(() => Math.max(1, Math.round((totalSeconds.value - remain.value) / 60)))
const currentCourse = computed(() => courses.value.find((item) => item.id === courseId.value))
const meters = computed(() => [
  { label: '镜头', value: cameraOn.value ? '已开' : '演示' },
  { label: '进度', value: `${progress.value}%` },
  { label: '提示', value: liveHint.value || '跟进中' },
])

const { stream, start: startCam, stop: stopCam } = useUserMedia({
  constraints: { video: true, audio: false },
  enabled: false,
})

watch(stream, (value) => {
  if (camRef.value) camRef.value.srcObject = value || null
  cameraOn.value = Boolean(value)
})

watch(
  () => route.query.courseId,
  () => applyCourseFromQuery(),
)

watch(mode, (value) => {
  if (running.value) return
  remain.value = value === 'full' ? FULL : FRAGMENT
  if (value === 'full') pickFullCourse()
  else if (currentCourse.value && String(currentCourse.value.stage || '').startsWith('综合')) {
    pickSkill(skillCourses.value[0]?.id)
  }
})

function shortSkill(course) {
  const stage = String(course?.stage || '')
  const part = stage.split('·')[1]
  return (part || course?.title || '技能').trim()
}

function sceneFromCourse(course) {
  const hay = `${course?.stage || ''}${course?.title || ''}`
  if (hay.includes('提问')) return '提问'
  if (hay.includes('板书') || hay.includes('演示')) return '板书'
  if (hay.includes('组织') || hay.includes('强化') || hay.includes('结束') || hay.includes('互动')) return '互动'
  if (hay.includes('综合') || hay.includes('完整') || hay.includes('教资')) return '完整'
  return '导入'
}

function applyCourse(course) {
  if (!course) return
  courseId.value = course.id
  courseTitle.value = course.title
  const full = String(course.stage || '').startsWith('综合')
  mode.value = full ? 'full' : 'fragment'
  scene.value = full ? '导入' : sceneFromCourse(course)
  remain.value = full ? FULL : FRAGMENT
}

function applyCourseFromQuery() {
  const id = Number(route.query.courseId)
  const match = courses.value.find((item) => item.id === id)
  if (match) applyCourse(match)
}

function pickSkill(id) {
  const match = courses.value.find((item) => item.id === Number(id))
  if (match) applyCourse(match)
}

function pickFullCourse() {
  const preferred = fullCourses.value.find((item) => String(item.stage || '').includes('模拟')) || fullCourses.value[0]
  if (preferred) applyCourse(preferred)
}

async function loadCourses() {
  try {
    courses.value = await fetchCourses()
  } catch {
    courses.value = [
      { id: 1, title: '导入技能', stage: '专项01 · 导入' },
      { id: 10, title: '综合模拟授课（10 分钟）', stage: '综合10 · 模拟授课' },
    ]
  }
  applyCourseFromQuery()
  if (!currentCourse.value) {
    const prefs = loadSettings()
    if (prefs.mode === 'full') pickFullCourse()
    else pickSkill(skillCourses.value[0]?.id)
  }
}

onMounted(async () => {
  await loadCourses()
})

async function toggleCamera() {
  if (cameraOn.value) {
    stopCam()
    return
  }
  try {
    await startCam()
  } catch {
    cameraOn.value = false
  }
}

async function begin() {
  if (running.value || finishing.value) return
  if (!courseId.value && mode.value === 'full') pickFullCourse()
  if (!courseId.value) pickSkill(skillCourses.value[0]?.id)
  const prefs = loadSettings()
  if (prefs.cameraDefault && !cameraOn.value) {
    try {
      await startCam()
    } catch {
      cameraOn.value = false
    }
  }
  running.value = true
  remain.value = totalSeconds.value
  startedAt = Date.now()
  sessionPromise = startTraining(courseId.value)
    .then((session) => {
      sessionId.value = session.id
    })
    .catch(() => {
      sessionId.value = null
    })
  tick = setInterval(async () => {
    const spent = Math.floor((Date.now() - startedAt) / 1000)
    remain.value = Math.max(0, totalSeconds.value - spent)
    if (remain.value <= 0) {
      await finish()
      return
    }
    if (spent % 30 === 0 && sessionId.value) {
      patchTraining(sessionId.value, {
        progress_percent: progress.value,
        duration_minutes: elapsedMinutes.value,
      }).catch(() => {})
    }
  }, 1000)
}

async function finish() {
  if (!running.value || finishing.value) return
  finishing.value = true
  clearInterval(tick)
  tick = null
  stopCam()
  if (sessionPromise) await sessionPromise
  const payload = {
    duration_minutes: elapsedMinutes.value,
    scene: mode.value === 'full' ? '完整' : scene.value,
    mode: mode.value,
  }
  try {
    if (!sessionId.value) {
      router.push('/ai-review')
      return
    }
    const { feedback } = await completeTraining(sessionId.value, payload)
    router.push({ path: '/ai-review', query: { sessionId: sessionId.value, feedbackId: feedback?.id } })
  } catch {
    router.push('/ai-review')
  } finally {
    running.value = false
    finishing.value = false
  }
}

onUnmounted(() => {
  clearInterval(tick)
  stopCam()
})
</script>
