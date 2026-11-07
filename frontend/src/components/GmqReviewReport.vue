<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const durationMs = 593958
const reportData = ref(null)
const loadError = ref('')
const selectedDimension = ref('D1')
const player = ref(null)
const currentMs = ref(0)
const chartWidth = 1000

const dimensions = [
  { id: 'D1', short: '目标与内容', title: '目标与学科内容', criteria: ['C11', 'C12', 'C13'] },
  { id: 'D2', short: '教学实施', title: '教学实施与学科实践', criteria: ['C21', 'C22', 'C23'] },
  { id: 'D3', short: '互动与反馈', title: '互动与形成性反馈', criteria: ['C31', 'C32', 'C33'] },
  { id: 'D4', short: '技术与证据', title: '技术融合与学习证据', criteria: ['C41', 'C42', 'C43'] },
]

const evidenceAnchors = [
  { atMs: 0, title: '试讲开场', detail: '交代课题与学段' },
  { atMs: 37100, title: '说明学习目标', detail: '讲到采样、量化等目标' },
  { atMs: 90100, title: '进入试讲', detail: '从导入情境开始课堂讲授' },
  { atMs: 174400, title: '模拟采样活动', detail: '提出小组模拟任务' },
  { atMs: 231200, title: '邀请展示', detail: '请一位同学展示' },
  { atMs: 335700, title: '追问量化位数', detail: '提出“为什么是二百五十五”' },
  { atMs: 515000, title: '讨论图像压缩', detail: '联系画质与存储取舍' },
  { atMs: 584000, title: '课堂收束', detail: '进入本节课总结' },
]

const suggestions = [
  { id: 'C11', dimension: 'D1', title: '目标与课程要求对齐', atMs: 37100, evidence: '确定以下学习目标：理解采样、量化等步骤。', text: '开场说完学习目标后，可以再告诉学生这节课结束时要能解释什么。最后用同一句目标带大家回顾。' },
  { id: 'C12', dimension: 'D1', title: '学科内容准确与解释', atMs: 352400, evidence: '这八位呢就是量化的位数……', text: '讲到 8 位和 256 个颜色层级时，可以用同一张图对比 8 位和 10 位的颜色变化。学生会更容易看懂“位数变了，画面有什么不同”。' },
  { id: 'C13', dimension: 'D1', title: '任务与目标匹配', atMs: 174400, evidence: '那我们第一个环节呢就来模拟一下采样。', text: '布置小组模拟任务时，可以先说清楚每组最后要画出或展示什么，再点明这个结果对应采样的哪一步。' },
  { id: 'C21', dimension: 'D2', title: '教学结构与节奏', atMs: 297800, evidence: '那我们来看……', text: '从活动转到新概念时，可以用一句话收住前面的发现，再告诉学生接下来要解释什么。这样环节之间更好跟。' },
  { id: 'C22', dimension: 'D2', title: '讲解与示范可理解性', atMs: 269800, evidence: '分辨率……这样就会越……', text: '讲采样、分辨率和量化时，可以继续用同一张图一步步演示：网格怎么变、颜色层次怎么变，再解释这些变化分别叫什么。' },
  { id: 'C23', dimension: 'D2', title: '实践与问题解决机会', atMs: 184800, evidence: '请大家拿……可以在小组……', text: '这段已经安排了小组模拟。可以给学生留出完整的独立尝试时间，再请一组展示，让其他同学比较不同做法。' },
  { id: 'C31', dimension: 'D3', title: '问题设计与思维要求', atMs: 335700, evidence: '那为什么是二百五十五呢？', text: '这个“为什么”问题很适合让学生说理由。可以先让大家猜一猜，再追问“你是怎么推出来的”，把答案和思考过程都说出来。' },
  { id: 'C32', dimension: 'D3', title: '回应利用与教学调整', atMs: 231200, evidence: '好，我们请一位同学来展示一下。', text: '邀请学生展示后，可以先复述他做法里的关键一步，再根据展示内容追问或调整下一步讲解。当前转写没有区分说话人，建议回放确认师生回应的对应关系。' },
  { id: 'C33', dimension: 'D3', title: '反馈具体性与纠错', atMs: 515000, evidence: '对的，那手机厂商为什么要通过压……', text: '回应学生时，可以先具体指出哪一点说对了，再补一句原因；如果答案还不完整，就给一个提示让学生接着想。' },
  { id: 'C41', dimension: 'D4', title: '数字技术与目标的功能匹配', atMs: 98200, evidence: '最近呢有个手机发布会……一亿像素。', text: '用手机像素和照片压缩做情境时，可以顺手点明这个例子分别要帮大家理解哪个概念，避免情境讲完后和知识点断开。' },
  { id: 'C42', dimension: 'D4', title: '学习过程与成果证据', atMs: 504270, evidence: '“估算了一百三……”（课堂转写）', text: '学生估算图片信息后，可以把估算和实际数据并排展示，再请大家说说差异来自哪里。这样能留下看得见的学习过程证据。' },
  { id: 'C43', dimension: 'D4', title: '评价闭环与课堂收束', atMs: 584000, evidence: '好，这节课的内容就上到……', text: '结束前可以用一个小问题检查目标：采样、量化分别改变了图像的什么？听完回答后再接到下节课的编码内容。' },
]

const activeDimension = computed(() => dimensions.find((item) => item.id === selectedDimension.value) || dimensions[0])
const visibleSuggestions = computed(() => suggestions.filter((item) => item.dimension === selectedDimension.value))
const data = computed(() => reportData.value)
const actionSummary = computed(() => data.value?.actionCounts || {})
const acousticSummary = computed(() => data.value?.acousticCounts || {})
const duration = computed(() => data.value?.durationMs || durationMs)
const faceCoverageLabel = computed(() => `${((data.value?.faceCoverage || 0) * 100).toFixed(1)}%`)
const faceObservedCount = computed(() => data.value?.faceStatusCounts?.observed || 0)

function formatTime(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

function seekTo(ms) {
  if (!player.value) return
  player.value.currentTime = Math.max(0, ms / 1000)
  currentMs.value = ms
  void player.value.play().catch(() => {})
}

function onTimeUpdate() {
  currentMs.value = Math.round((player.value?.currentTime || 0) * 1000)
}

function setNormalPlaybackSpeed() {
  if (!player.value) return
  player.value.pause()
  player.value.currentTime = 0
  player.value.defaultPlaybackRate = 1
  player.value.playbackRate = 1
  currentMs.value = 0
}

function xFor(ms) {
  return Math.max(0, Math.min(chartWidth, (ms / duration.value) * chartWidth))
}

function laneItems(label) {
  if (!data.value) return []
  if (label === '讲解') return data.value.transcripts.map((item) => ({
    startMs: item.startMs,
    endMs: item.endMs,
    title: item.text,
    type: 'speech',
  }))
  return data.value.actions.filter((item) => item.label === label).map((item) => ({
    startMs: item.timeMs,
    endMs: Math.min(duration.value, item.timeMs + 333),
    title: `${item.label} · ${formatTime(item.timeMs)} · 采样置信度 ${item.confidence?.toFixed(2) ?? '—'}`,
    type: label === '书写' ? 'writing' : label === '指向' ? 'pointing' : 'normal',
  }))
}

function linePath(key) {
  if (!data.value) return ''
  const points = data.value.face
  const maxValue = 0.7
  let path = ''
  let previous = null
  for (const point of points) {
    const value = point.status === 'observed' ? point[key] : null
    if (value === null || value === undefined) {
      previous = null
      continue
    }
    const x = xFor(point.timeMs)
    const y = 100 - Math.min(1, value / maxValue) * 82
    path += `${previous ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)} `
    previous = point
  }
  return path.trim()
}

function voiceColor(label) {
  return ({ '中立': '#b45cff', '开心': '#ffad5c', '难过': '#67c8bb', '惊讶': '#f17a86' })[label] || '#8d8798'
}

function actionCount(label) {
  return actionSummary.value[label] || 0
}

onMounted(async () => {
  try {
    const response = await fetch('/local-demo/gmq/report.json')
    if (!response.ok) throw new Error('GMQ 本机分析数据未找到。')
    reportData.value = await response.json()
  } catch {
    loadError.value = '没有读到 GMQ 本机分析文件，请重新准备本机示例数据。'
  }
})

onUnmounted(() => {
  player.value?.pause()
})
</script>

<template>
  <main class="gmq-report" aria-label="GMQ 试讲报告">
    <header class="gmq-report__header">
      <div>
        <p>AI 评课 / 课堂复盘</p>
        <h1>GMQ <span>·</span> 信息科技试讲</h1>
      </div>
      <div class="gmq-report__header-actions">
        <span class="gmq-report__verified"><i></i> 分析记录已载入</span>
        <router-link to="/ai-review" class="gmq-report__back">返回评课列表</router-link>
      </div>
    </header>

    <section v-if="loadError" class="gmq-report__load-error" role="alert">
      {{ loadError }} <span>视频和分析文件保存在当前 E 盘工作副本中。</span>
    </section>

    <div v-else-if="data" class="gmq-report__grid">
      <section class="gmq-report__left" aria-label="课堂视频与行为记录">
        <article class="gmq-card gmq-video-card">
          <video
            ref="player"
            class="gmq-video"
            :src="data.videoUrl"
            controls
            playsinline
            preload="metadata"
            @timeupdate="onTimeUpdate"
            @loadedmetadata="setNormalPlaybackSpeed"
          ></video>
          <div class="gmq-event-strip" aria-label="可点击的课堂证据时间点">
            <button
              v-for="event in evidenceAnchors"
              :key="event.atMs"
              type="button"
              class="gmq-event"
              :class="{ active: currentMs >= event.atMs && currentMs < (evidenceAnchors[evidenceAnchors.indexOf(event) + 1]?.atMs || duration) }"
              :style="{ left: `${xFor(event.atMs) / 10}%` }"
              :aria-label="`回放 ${formatTime(event.atMs)} ${event.title}`"
              :title="`${formatTime(event.atMs)} · ${event.title} · ${event.detail}`"
              @click="seekTo(event.atMs)"
            >
              <time>{{ formatTime(event.atMs) }}</time><i></i>
            </button>
            <input
              class="gmq-event-track"
              type="range"
              min="0"
              :max="duration"
              :value="currentMs"
              aria-label="课堂录像进度，可拖动跳转"
              @input="seekTo(Number($event.target.value))"
            />
          </div>
        </article>

        <article class="gmq-card gmq-behavior-card">
          <header class="gmq-card__heading">
            <div><small>VIDEO EVIDENCE</small><h2>课堂行为记录</h2></div>
            <span>点选记录可回放 · 采样点</span>
          </header>
          <div class="gmq-time-axis"><span>00:00</span><span>02:00</span><span>04:00</span><span>06:00</span><span>08:00</span><span>09:53</span></div>
          <div class="gmq-lanes">
            <div v-for="lane in [
              { label: '讲解', type: 'speech' },
              { label: '常规动作', type: 'normal' },
              { label: '书写', type: 'writing' },
              { label: '指向', type: 'pointing' },
            ]" :key="lane.label" class="gmq-lane">
              <strong>{{ lane.label }}</strong>
              <div class="gmq-lane__track">
                <button
                  v-for="(item, index) in laneItems(lane.label)"
                  :key="`${lane.label}-${index}`"
                  type="button"
                  :class="['gmq-lane__mark', `is-${lane.type}`]"
                  :style="{ left: `${xFor(item.startMs) / 10}%`, width: `${Math.max(0.28, xFor(item.endMs - item.startMs) / 10)}%` }"
                  :title="item.title"
                  :aria-label="`回放 ${formatTime(item.startMs)} ${item.title}`"
                  @click="seekTo(item.startMs)"
                ></button>
              </div>
              <small v-if="lane.label !== '讲解'">{{ actionCount(lane.label) }} 点</small>
              <small v-else>{{ data.recordCounts.transcripts }} 段</small>
            </div>
          </div>
          <footer class="gmq-behavior-legend"><span><i class="is-speech"></i>转写片段</span><span><i class="is-normal"></i>常规动作</span><span><i class="is-writing"></i>书写</span><span><i class="is-pointing"></i>指向</span></footer>
        </article>
      </section>

      <section class="gmq-report__right" aria-label="声音、面部观察与建议">
        <article class="gmq-card gmq-modality-card">
          <header class="gmq-card__heading gmq-modality-heading">
            <div><small>MULTIMODAL RECORD</small><h2>语音与面部观察记录</h2></div>
            <span>数据与视频时间轴对应</span>
          </header>
          <div class="gmq-modality-grid">
            <section class="gmq-chart-block gmq-voice-block" aria-label="语音情绪记录">
              <div class="gmq-chart-title"><div><b>语音情绪记录</b><small>声学分类片段</small></div><small>{{ data.recordCounts.acousticSegments }} 段</small></div>
              <div class="gmq-voice-summary">
                <span v-for="item in Object.entries(acousticSummary)" :key="item[0]" :style="{ '--cue-color': voiceColor(item[0]) }">
                  <i></i>{{ item[0] }} <b>{{ item[1] }}</b>
                </span>
              </div>
              <svg class="gmq-voice-chart" viewBox="0 0 1000 112" preserveAspectRatio="none" role="img" aria-label="音频情绪分类在视频时间轴上的分布">
                <line x1="0" y1="90" x2="1000" y2="90" class="gmq-chart-axis" />
                <rect
                  v-for="(segment, index) in data.acoustic"
                  :key="`voice-${index}`"
                  :x="xFor(segment.startMs)"
                  :y="26 + (index % 2) * 4"
                  :width="Math.max(2, xFor(segment.endMs - segment.startMs))"
                  height="54"
                  rx="3"
                  :fill="voiceColor(segment.label)"
                  :opacity="0.48 + Math.max(0, Math.min(0.5, (segment.score || 0) * 0.5))"
                  tabindex="0"
                  role="button"
                  :aria-label="`${formatTime(segment.startMs)} ${segment.label}，点击回放`"
                  @click="seekTo(segment.startMs)"
                  @keydown.enter="seekTo(segment.startMs)"
                ><title>{{ formatTime(segment.startMs) }} · {{ segment.label }} · {{ segment.text }}</title></rect>
              </svg>
              <div class="gmq-chart-axis-labels"><span>00:00</span><span>03:18</span><span>06:36</span><span>09:53</span></div>
            </section>

            <section class="gmq-chart-block gmq-face-block" aria-label="面部动作记录">
              <div class="gmq-chart-title"><div><b>面部动作记录</b><small>可观测帧的动作系数</small></div><strong class="gmq-face-coverage">{{ faceCoverageLabel }}</strong></div>
              <div class="gmq-face-legend"><span><i class="smile"></i>嘴角动作</span><span><i class="brow"></i>眉部动作</span><span><i class="jaw"></i>口部开合</span></div>
              <svg class="gmq-face-chart" viewBox="0 0 1000 138" preserveAspectRatio="none" role="img" aria-label="面部动作系数时间曲线">
                <line v-for="y in [20, 60, 100]" :key="y" x1="0" :y1="y" x2="1000" :y2="y" class="gmq-chart-gridline" />
                <path :d="linePath('mouthSmile')" class="gmq-face-line smile" />
                <path :d="linePath('browInnerUp')" class="gmq-face-line brow" />
                <path :d="linePath('jawOpen')" class="gmq-face-line jaw" />
              </svg>
              <div class="gmq-chart-axis-labels"><span>00:00</span><span>03:18</span><span>06:36</span><span>09:53</span></div>
              <div class="gmq-coverage-line"><span>有效观察帧</span><div><i :style="{ width: faceCoverageLabel }"></i></div><b>{{ faceObservedCount }}/{{ data.recordCounts.faceSamples }}</b></div>
            </section>
          </div>
        </article>

        <article class="gmq-card gmq-suggestion-card">
          <header class="gmq-card__heading">
            <div><small>COACHING NOTES</small><h2>给你的练习建议</h2></div>
            <span>按四组指标整理 · 不显示评分</span>
          </header>
          <nav class="gmq-dimension-tabs" aria-label="建议一级指标">
            <button
              v-for="dimension in dimensions"
              :key="dimension.id"
              type="button"
              :class="{ active: selectedDimension === dimension.id }"
              :aria-pressed="selectedDimension === dimension.id"
              @click="selectedDimension = dimension.id"
            ><span>{{ dimension.short }}</span><small>3 条</small></button>
          </nav>
          <div class="gmq-suggestion-scroll" :key="selectedDimension" tabindex="0" :aria-label="`${activeDimension.title}的建议列表，可滚动查看`">
            <div v-for="item in visibleSuggestions" :key="item.id" class="gmq-suggestion">
              <div class="gmq-suggestion__top"><span>{{ item.id }}</span><strong>{{ item.title }}</strong><button type="button" @click="seekTo(item.atMs)">回看 {{ formatTime(item.atMs) }} ↗</button></div>
              <p>{{ item.text }}</p>
              <blockquote><time>{{ formatTime(item.atMs) }}</time><span>{{ item.evidence }}</span></blockquote>
            </div>
          </div>
        </article>
      </section>
    </div>
  </main>
</template>

<style scoped>
.gmq-report{--gmq-panel:rgba(14,13,20,.72);--gmq-line:rgba(225,218,238,.15);--gmq-muted:#a9a4b4;--gmq-violet:#b45cff;--gmq-orange:#ffad5c;display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden;color:#f5f1f8;padding:0 2px 8px;gap:10px}
.gmq-report *{box-sizing:border-box;min-width:0}
.gmq-report button{font:inherit;color:inherit;cursor:pointer}
.gmq-report__header{flex:none;min-height:40px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.gmq-report__header p,.gmq-card__heading small{margin:0;color:var(--gmq-muted);font-size:9px;font-weight:700;letter-spacing:.16em;text-transform:uppercase}
.gmq-report__header h1{margin:2px 0 0;font-size:clamp(17px,1.4vw,22px);line-height:1.2;font-weight:650}
.gmq-report__header h1 span{color:var(--gmq-orange)}
.gmq-report__header-actions{display:flex;align-items:center;gap:9px}
.gmq-report__verified,.gmq-report__back{display:inline-flex;align-items:center;gap:7px;min-height:30px;padding:0 11px;border:1px solid var(--gmq-line);border-radius:9px;background:rgba(12,10,17,.45);color:#e9e2f0;font-size:10px;text-decoration:none;white-space:nowrap}
.gmq-report__verified i{width:7px;height:7px;border-radius:50%;background:#82d2c5;box-shadow:0 0 9px #82d2c555}
.gmq-report__back:hover{border-color:var(--gmq-violet);color:#fff}
.gmq-report__grid{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1.02fr) minmax(0,.98fr);gap:12px}
.gmq-report__left,.gmq-report__right{min-height:0;display:grid;gap:10px;overflow:hidden}
.gmq-report__left{grid-template-rows:minmax(0,1.45fr) minmax(160px,.75fr)}
.gmq-report__right{grid-template-rows:minmax(0,1fr) minmax(0,1fr)}
.gmq-card{min-height:0;border:1px solid var(--gmq-line);border-radius:15px;background:linear-gradient(145deg,rgba(21,19,28,.82),rgba(9,8,13,.8));box-shadow:inset 0 1px rgba(255,255,255,.045);overflow:hidden}
.gmq-video-card{display:flex;flex-direction:column;padding:9px}
.gmq-video{display:block;flex:none;width:100%;height:auto;aspect-ratio:854/480;border-radius:10px;background:#06050a;object-fit:cover}
.gmq-event-strip{position:relative;flex:none;height:65px;margin:10px 8px 1px}
.gmq-event-track{position:absolute;z-index:0;left:0;right:0;top:9px;width:100%;height:10px;margin:0;padding:0;appearance:none;background:transparent;cursor:pointer}
.gmq-event-track::-webkit-slider-runnable-track{height:2px;border-radius:4px;background:linear-gradient(90deg,#ffad5c,#b45cff);opacity:.82}
.gmq-event-track::-moz-range-track{height:2px;border-radius:4px;background:linear-gradient(90deg,#ffad5c,#b45cff);opacity:.82}
.gmq-event-track::-webkit-slider-thumb{width:10px;height:10px;margin-top:-4px;appearance:none;border-radius:50%;background:#fff;border:2px solid var(--gmq-violet);box-shadow:0 0 9px #b45cff88}
.gmq-event-track::-moz-range-thumb{width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid var(--gmq-violet);box-shadow:0 0 9px #b45cff88}
.gmq-event{position:absolute;z-index:1;top:0;transform:translateX(-50%);display:flex;align-items:center;flex-direction:column;gap:2px;width:84px;padding:0;border:0;background:none;text-align:center;color:#d9d3e2;font-size:9px;white-space:nowrap}
.gmq-event i{order:1;width:9px;height:9px;margin-top:9px;border-radius:50%;border:2px solid #ffad5c;background:#211a20;box-shadow:0 0 7px #ffad5c55}
.gmq-event time{order:0;color:#d6cedf;font-size:9px;font-variant-numeric:tabular-nums}
.gmq-event span{order:2;max-width:84px;overflow:hidden;text-overflow:ellipsis;color:var(--gmq-muted)}
.gmq-event:hover span,.gmq-event.active span{color:#fff}
.gmq-event.active i{background:#ffad5c;box-shadow:0 0 10px #ffad5caa}
.gmq-card__heading{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px 8px}
.gmq-card__heading h2{margin:2px 0 0;font-size:15px;font-weight:650;line-height:1.2}
.gmq-card__heading>span{color:var(--gmq-muted);font-size:9px;text-align:right}
.gmq-behavior-card{display:flex;flex-direction:column;padding:0 8px 8px}
.gmq-behavior-card .gmq-card__heading{padding-inline:7px}
.gmq-time-axis{display:flex;justify-content:space-between;padding:0 38px 4px 69px;color:#898393;font-size:8px;font-variant-numeric:tabular-nums}
.gmq-lanes{display:grid;gap:5px;min-height:0;flex:1}
.gmq-lane{display:grid;grid-template-columns:58px minmax(0,1fr) 44px;gap:8px;align-items:center;min-height:17px}
.gmq-lane>strong{font-size:10px;font-weight:550;color:#ded8e6}
.gmq-lane>small{font-size:8px;color:var(--gmq-muted);text-align:right}
.gmq-lane__track{position:relative;height:13px;border-radius:4px;background:rgba(255,255,255,.035);overflow:hidden}
.gmq-lane__mark{position:absolute;top:2px;height:9px;min-width:2px;padding:0;border:0;border-radius:2px;opacity:.82}
.gmq-lane__mark:hover{opacity:1;filter:brightness(1.35)}
.gmq-lane__mark.is-speech{background:#b45cff}
.gmq-lane__mark.is-normal{background:#ffad5c}
.gmq-lane__mark.is-writing{background:#77c9be}
.gmq-lane__mark.is-pointing{background:#ee879a}
.gmq-behavior-legend{display:flex;gap:12px;align-items:center;padding:7px 0 0 64px;color:var(--gmq-muted);font-size:8px}
.gmq-behavior-legend span{display:flex;align-items:center;gap:4px}
.gmq-behavior-legend i{width:7px;height:7px;border-radius:2px}
.gmq-behavior-legend .is-speech{background:#b45cff}.gmq-behavior-legend .is-normal{background:#ffad5c}.gmq-behavior-legend .is-writing{background:#77c9be}.gmq-behavior-legend .is-pointing{background:#ee879a}
.gmq-modality-card{display:flex;flex-direction:column;padding:0 10px 8px}
.gmq-modality-heading{flex:none;padding-inline:5px}
.gmq-modality-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:9px;min-height:0;flex:1}
.gmq-chart-block{display:flex;flex-direction:column;min-height:0;padding:9px 10px;border:1px solid rgba(255,255,255,.1);border-radius:11px;background:rgba(255,255,255,.025);overflow:hidden}
.gmq-chart-title{display:flex;align-items:center;justify-content:space-between;gap:8px}
.gmq-chart-title>div{display:grid;gap:2px}
.gmq-chart-title b{font-size:11px;font-weight:650}
.gmq-chart-title small,.gmq-chart-title>small{color:var(--gmq-muted);font-size:8px}
.gmq-face-coverage{color:var(--gmq-orange);font-size:11px;font-variant-numeric:tabular-nums}
.gmq-voice-summary{display:flex;flex-wrap:wrap;gap:4px 8px;margin-top:7px}
.gmq-voice-summary span,.gmq-face-legend span{display:flex;align-items:center;gap:4px;color:#c6c0d0;font-size:8px;white-space:nowrap}
.gmq-voice-summary i{width:6px;height:6px;border-radius:50%;background:var(--cue-color)}
.gmq-voice-summary b{color:#eee8f3;font-weight:600}
.gmq-voice-chart{display:block;width:100%;height:clamp(56px,8vh,84px);flex:none;margin-top:auto}
.gmq-chart-axis{stroke:rgba(255,255,255,.24);stroke-width:1}
.gmq-chart-gridline{stroke:rgba(255,255,255,.09);stroke-width:1}
.gmq-chart-labels{fill:#858091;font-size:20px}
.gmq-chart-note{margin:4px 0 0;color:#918b9c;font-size:8px;line-height:1.35}
.gmq-face-legend{display:flex;flex-wrap:wrap;gap:4px 8px;margin-top:9px}
.gmq-face-legend i{width:11px;height:2px;border-radius:2px;background:var(--legend-color)}
.gmq-face-legend .smile{--legend-color:#b45cff}.gmq-face-legend .brow{--legend-color:#77c9be}.gmq-face-legend .jaw{--legend-color:#ffad5c}
.gmq-face-chart{display:block;width:100%;height:clamp(68px,10vh,98px);flex:none;margin-top:auto}
.gmq-face-line{fill:none;stroke-width:2.3;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
.gmq-face-line.smile{stroke:#b45cff}.gmq-face-line.brow{stroke:#77c9be}.gmq-face-line.jaw{stroke:#ffad5c}
.gmq-coverage-line{display:flex;align-items:center;gap:7px;margin-top:4px;color:var(--gmq-muted);font-size:8px}
.gmq-coverage-line>div{height:5px;flex:1;border-radius:9px;background:rgba(255,255,255,.1);overflow:hidden}
.gmq-coverage-line>div i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#b45cff,#ffad5c)}
.gmq-coverage-line b{color:#eee8f3;font-size:8px;font-weight:550;white-space:nowrap}
.gmq-suggestion-card{display:flex;flex-direction:column;padding:0 10px 9px}
.gmq-suggestion-card>.gmq-card__heading{flex:none;padding:10px 5px 7px}
.gmq-dimension-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;flex:none;padding-bottom:8px}
.gmq-dimension-tabs button{display:flex;flex-direction:column;align-items:flex-start;justify-content:center;min-height:38px;padding:5px 7px;border:1px solid rgba(255,255,255,.11);border-radius:8px;background:rgba(255,255,255,.035);text-align:left;transition:background .16s,border-color .16s}
.gmq-dimension-tabs button span{font-size:9px;font-weight:600;line-height:1.2;white-space:nowrap}
.gmq-dimension-tabs button small{margin-top:2px;color:var(--gmq-muted);font-size:7px}
.gmq-dimension-tabs button.active{border-color:rgba(180,92,255,.7);background:linear-gradient(105deg,rgba(180,92,255,.28),rgba(255,122,24,.1));box-shadow:inset 0 0 0 1px rgba(180,92,255,.12)}
.gmq-dimension-tabs button.active small{color:#e2c2ff}
.gmq-suggestion-scroll{min-height:0;flex:1;overflow-y:auto;overscroll-behavior:contain;padding-right:5px;scrollbar-width:thin;scrollbar-color:rgba(180,92,255,.68) rgba(255,255,255,.04)}
.gmq-suggestion-scroll::-webkit-scrollbar{width:6px}.gmq-suggestion-scroll::-webkit-scrollbar-thumb{background:rgba(180,92,255,.6);border-radius:9px}
.gmq-suggestion{padding:9px 10px;margin-bottom:7px;border:1px solid rgba(255,255,255,.095);border-radius:10px;background:rgba(255,255,255,.025)}
.gmq-suggestion__top{display:flex;align-items:center;gap:7px}
.gmq-suggestion__top>span{color:#d6b2fa;font-size:8px;font-weight:750;letter-spacing:.04em}
.gmq-suggestion__top strong{flex:1;color:#e8e2ec;font-size:9px;font-weight:600}
.gmq-suggestion__top button{flex:none;padding:4px 7px;border:1px solid rgba(180,92,255,.35);border-radius:7px;background:rgba(180,92,255,.12);color:#e4c5ff;font-size:8px;white-space:nowrap}
.gmq-suggestion__top button:hover{background:rgba(180,92,255,.26)}
.gmq-suggestion>p{margin:6px 0 0;color:#f3edf6;font-size:10px;line-height:1.55}
.gmq-suggestion blockquote{display:flex;align-items:flex-start;gap:7px;margin:7px 0 0;padding:6px 8px;border-left:2px solid rgba(255,173,92,.7);border-radius:0 6px 6px 0;background:rgba(255,173,92,.06);color:#bbb4c2;font-size:8px;line-height:1.45}
.gmq-suggestion blockquote time{flex:none;color:var(--gmq-orange);font-variant-numeric:tabular-nums}
:global(body:has(.gmq-report) .help-dock){display:none!important}
.gmq-report__load-error{margin:auto;padding:18px 22px;border:1px solid var(--gmq-line);border-radius:12px;background:var(--gmq-panel);color:#f2eaf7;font-size:14px}
.gmq-report__load-error span{display:block;margin-top:6px;color:var(--gmq-muted);font-size:11px}
@media(max-width:1050px){.gmq-report__grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px}.gmq-card__heading{padding-inline:10px}.gmq-chart-block{padding:7px}.gmq-dimension-tabs{gap:3px}.gmq-dimension-tabs button{padding-inline:5px}.gmq-dimension-tabs button span{font-size:8px}}
@media(max-width:760px){.gmq-report{height:auto;min-height:100%;overflow:visible}.gmq-report__header{align-items:flex-start}.gmq-report__header-actions{flex-direction:column;align-items:flex-end}.gmq-report__grid{grid-template-columns:1fr;overflow:visible}.gmq-report__left,.gmq-report__right{overflow:visible;grid-template-rows:auto auto}.gmq-video-card{min-height:300px}.gmq-behavior-card{min-height:190px}.gmq-modality-card{min-height:330px}.gmq-suggestion-card{min-height:420px}.gmq-suggestion-scroll{max-height:300px}.gmq-dimension-tabs button span{white-space:normal}}
@media(max-height:730px) and (min-width:761px){.gmq-report{gap:6px}.gmq-report__grid{gap:8px}.gmq-report__left,.gmq-report__right{gap:7px}.gmq-event-strip{height:57px;margin-top:6px}.gmq-modality-heading{padding-top:8px;padding-bottom:5px}.gmq-chart-block{padding-top:6px;padding-bottom:6px}.gmq-voice-chart{height:54px}.gmq-face-chart{height:64px}.gmq-suggestion-card>.gmq-card__heading{padding-top:7px;padding-bottom:5px}.gmq-dimension-tabs button{min-height:32px}.gmq-suggestion{padding:7px 8px;margin-bottom:5px}.gmq-suggestion>p{font-size:9px}}

/* Readable long-form report: let the document grow and use the browser page scroll. */
.gmq-report{height:auto;min-height:100%;overflow:visible;gap:18px;padding:0 4px 42px}
.gmq-report__header{min-height:58px}
.gmq-report__header p,.gmq-card__heading small{font-size:12px;letter-spacing:.12em}
.gmq-report__header h1{font-size:clamp(24px,2vw,32px)}
.gmq-report__verified,.gmq-report__back{min-height:38px;padding:0 14px;font-size:13px}
.gmq-report__grid{flex:none;min-height:0;align-items:start;grid-template-columns:minmax(0,1.06fr) minmax(0,.94fr);gap:22px}
.gmq-report__left,.gmq-report__right{display:flex;flex-direction:column;min-height:0;overflow:visible;gap:18px}
.gmq-card{border-radius:17px}
.gmq-video-card{flex:none;padding:12px}
.gmq-event-strip{height:82px;margin:14px 12px 3px}
.gmq-event{width:112px;font-size:12px;gap:4px}
.gmq-event time{font-size:12px}
.gmq-event span{max-width:112px}
.gmq-behavior-card{min-height:265px;padding:0 16px 14px}
.gmq-behavior-card .gmq-card__heading{padding:18px 4px 12px}
.gmq-card__heading h2{font-size:21px}
.gmq-card__heading>span{font-size:13px}
.gmq-time-axis{padding:0 58px 8px 100px;font-size:12px}
.gmq-lanes{gap:13px;flex:none;padding:8px 0}
.gmq-lane{grid-template-columns:84px minmax(0,1fr) 58px;gap:12px;min-height:25px}
.gmq-lane>strong{font-size:14px}
.gmq-lane>small{font-size:12px}
.gmq-lane__track{height:20px;border-radius:6px}
.gmq-lane__mark{top:3px;height:14px;min-width:3px;border-radius:3px}
.gmq-behavior-legend{gap:18px;padding:10px 0 0 96px;font-size:12px}
.gmq-behavior-legend i{width:10px;height:10px}
.gmq-modality-card{min-height:590px;padding:0 16px 16px}
.gmq-modality-heading{padding:18px 4px 14px}
.gmq-modality-grid{flex:none;min-height:0;align-items:stretch;gap:14px}
.gmq-chart-block{min-height:500px;padding:18px 16px;border-radius:14px}
.gmq-chart-title b{font-size:16px}
.gmq-chart-title small,.gmq-chart-title>small{font-size:12px}
.gmq-face-coverage{font-size:15px}
.gmq-voice-summary{gap:8px 12px;margin-top:14px}
.gmq-voice-summary span,.gmq-face-legend span{gap:7px;font-size:13px}
.gmq-voice-summary i{width:9px;height:9px}
.gmq-voice-chart{height:240px;margin-top:auto}
.gmq-chart-labels{font-size:28px}
.gmq-chart-note{margin-top:10px;font-size:12px;line-height:1.6}
.gmq-face-legend{gap:8px 14px;margin-top:15px}
.gmq-face-legend i{width:16px;height:3px}
.gmq-face-chart{height:250px;margin-top:auto}
.gmq-coverage-line{gap:10px;margin-top:10px;font-size:12px}
.gmq-coverage-line>div{height:8px}
.gmq-coverage-line b{font-size:12px}
.gmq-suggestion-card{padding:0 16px 18px}
.gmq-suggestion-card>.gmq-card__heading{padding:18px 4px 12px}
.gmq-dimension-tabs{gap:8px;padding-bottom:14px}
.gmq-dimension-tabs button{min-height:54px;padding:8px 12px;border-radius:11px}
.gmq-dimension-tabs button span{font-size:14px;white-space:normal}
.gmq-dimension-tabs button small{margin-top:5px;font-size:11px}
.gmq-suggestion-scroll{flex:none;overflow:visible;padding:0;scrollbar-width:none}
.gmq-suggestion{padding:16px 18px;margin-bottom:12px;border-radius:13px}
.gmq-suggestion__top{gap:10px}
.gmq-suggestion__top>span{font-size:12px}
.gmq-suggestion__top strong{font-size:15px;line-height:1.5}
.gmq-suggestion__top button{padding:7px 10px;font-size:12px}
.gmq-suggestion>p{margin-top:10px;font-size:16px;line-height:1.8}
.gmq-suggestion blockquote{gap:10px;margin-top:12px;padding:10px 12px;font-size:13px;line-height:1.65}
.gmq-suggestion blockquote time{font-size:12px}
.gmq-report__load-error{font-size:16px}
:global(.app-shell:has(.gmq-report)){height:auto;min-height:100dvh;overflow:visible;align-items:start}
:global(.app-shell:has(.gmq-report) .workspace){height:auto;min-height:calc(100dvh - 36px);overflow:visible}
:global(.app-shell:has(.gmq-report) .page-frame){flex:none;height:auto;min-height:0;overflow:visible}
:global(.app-shell:has(.gmq-report) .page-slot){display:block;flex:none;height:auto;min-height:0;overflow:visible}
:global(.app-shell:has(.gmq-report) .page-slot > *){flex:none;height:auto;min-height:0}
:global(body:has(.gmq-report)){overflow-y:auto}
@media(max-width:1200px){.gmq-modality-grid{grid-template-columns:1fr}.gmq-modality-card{min-height:0}.gmq-chart-block{min-height:390px}.gmq-voice-chart{height:180px}.gmq-face-chart{height:190px}}
@media(max-width:900px){.gmq-report__grid{grid-template-columns:1fr}.gmq-report__left,.gmq-report__right{gap:16px}.gmq-modality-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.gmq-report{gap:14px;padding-inline:0}.gmq-report__header{align-items:flex-start;flex-direction:column;gap:10px}.gmq-report__header-actions{flex-direction:row;align-items:center;flex-wrap:wrap}.gmq-modality-grid{grid-template-columns:1fr}.gmq-chart-block{min-height:0;padding:12px 15px}.gmq-voice-chart{height:165px}.gmq-face-chart{height:175px}.gmq-dimension-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}.gmq-suggestion>p{font-size:15px}.gmq-suggestion__top{align-items:flex-start;flex-wrap:wrap}.gmq-suggestion__top strong{flex-basis:calc(100% - 58px)}.gmq-event{width:88px}.gmq-event span{max-width:88px}.gmq-lane{grid-template-columns:72px minmax(0,1fr) 48px}.gmq-time-axis{padding-left:83px;padding-right:50px}.gmq-behavior-legend{padding-left:82px;gap:10px;font-size:10px}}
.gmq-report__left,.gmq-report__right,.gmq-modality-card,.gmq-modality-grid{display:contents}
.gmq-modality-heading{display:none}
.gmq-report__grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 20px}
.gmq-report__grid{row-gap:8px}
.gmq-video-card{grid-column:1;grid-row:1}
.gmq-behavior-card{grid-column:2;grid-row:1;min-height:100%}
.gmq-lanes{grid-template-rows:repeat(4,minmax(28px,1fr));align-content:stretch;gap:12px;flex:1;padding:8px 0}
.gmq-lane__track{height:26px}
.gmq-lane__mark{top:3px;height:20px}
.gmq-chart-block{min-height:0;padding-top:14px;padding-bottom:14px}
.gmq-voice-block{grid-column:1/-1;grid-row:2}
.gmq-face-block{grid-column:1/-1;grid-row:3}
.gmq-suggestion-card{grid-column:1/-1;grid-row:4}
.gmq-event-strip{height:40px;margin:10px 12px 0}
.gmq-event{width:58px;gap:0}
.gmq-event time{font-size:11px}
.gmq-event i{margin-top:7px}
.gmq-event-track{top:23px}
.gmq-event span{display:none}
.gmq-chart-axis-labels{display:flex;justify-content:space-between;color:#c2bbc9;font-size:12px;font-variant-numeric:tabular-nums}
.gmq-chart-block{min-height:440px}
.gmq-voice-chart{height:230px;margin-top:14px}
.gmq-face-chart{height:240px;margin-top:14px}
.gmq-suggestion-scroll{display:block}
@media(max-width:900px){.gmq-report__grid{grid-template-columns:1fr}.gmq-video-card,.gmq-behavior-card,.gmq-chart-block,.gmq-suggestion-card{grid-column:1;grid-row:auto}.gmq-behavior-card{min-height:265px}.gmq-chart-block{min-height:390px}}
@media(max-width:680px){.gmq-chart-block{min-height:350px}.gmq-voice-chart{height:165px}.gmq-face-chart{height:175px}}
</style>
