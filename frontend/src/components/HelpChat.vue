<template>
  <button
    class="help-fab"
    type="button"
    :style="fabStyle"
    @pointerdown="onFabDown"
    @click="toggle"
    aria-label="打开帮助"
  >助</button>

  <section
    v-if="open"
    class="help-chat"
    :style="chatStyle"
    role="dialog"
    aria-label="帮助中心"
  >
    <header class="help-chat__bar" @pointerdown="onChatDown">
      <div>
        <p>HELP</p>
        <strong>{{ mode === 'human' ? '人工客服' : '智能客服' }}</strong>
      </div>
      <button type="button" class="close-x" aria-label="关闭" @click="open = false">×</button>
    </header>
    <div class="help-chat__tools">
      <input v-model="query" type="search" placeholder="搜索训练、评课、资源…" />
      <button type="button" :class="{ active: mode === 'bot' }" @click="switchMode('bot')">智能</button>
      <button type="button" :class="{ active: mode === 'human' }" @click="switchMode('human')">人工</button>
    </div>
    <div class="help-chat__log" ref="logRef">
      <article v-for="(item, index) in messages" :key="index" :class="item.role">
        <p>{{ item.text }}</p>
      </article>
    </div>
    <form class="help-chat__form" @submit.prevent="send">
      <input v-model="draft" type="text" :placeholder="mode === 'human' ? '给指导教师留言' : '问一句，比如如何开始训练'" />
      <button class="primary" type="submit" :disabled="sending">{{ sending ? '提交中…' : '发送' }}</button>
    </form>
  </section>
</template>

<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { addJournal } from '../services/dashboard'
import { journalSubmitErrorMessage } from '../utils/dashboardState'

const faqs = [
  { q: '如何开始一次微格训练？', a: '课程中心按大纲九项技能分项选课，再进入综合模拟或教资试讲。专项 8 分钟，综合 10 分钟。' },
  { q: 'AI 评课看哪些维度？', a: '表达、节奏、互动、教态、提问、结构六项，结束训练后生成书面报告。觉得不准可以勾选校正点让系统重写。' },
  { q: '一次训练要多久？', a: '片段练习 8 分钟，完整课 10 分钟。演示时可随时结束并生成评课。' },
  { q: '资源如何使用？', a: '资源库按教案、素材、报告、档案分类。点开即可对照说明使用。' },
  { q: '成长档案看什么？', a: '近 30 天回放、热力图和训练日志。工作台的本周训练、成长轨迹点开就是它的缩略版。' },
  { q: '个人中心有什么？', a: '个人中心改身份和徽章；设置只改训练默认项和显示；联系我们找指导教师或留言。都从右上角头像进。' },
]

const open = ref(false)
const mode = ref('bot')
const query = ref('')
const draft = ref('')
const sending = ref(false)
const messages = ref([{ role: 'bot', text: '你好，我是临客帮助。可以搜 FAQ，或切到人工客服留言。' }])
const logRef = ref(null)
const pos = ref({ x: null, y: null, chatX: null, chatY: null })
let drag = null

const fabStyle = ref({})
const chatStyle = ref({})

function toggle() {
  if (drag && drag.moved) return
  open.value = !open.value
}

function openFromEvent(event) {
  mode.value = event.detail?.mode === 'human' ? 'human' : 'bot'
  open.value = true
  const intro = mode.value === 'human'
    ? '已切到人工留言。写下训练故障、评课异议或课程资源问题，演示环境会记一条本地留言。'
    : '已打开智能客服。可以搜「训练」「评课」或「资源」。'
  messages.value.push({ role: 'bot', text: intro })
}

function matchFaq(text) {
  const key = (text || query.value || '').trim()
  if (!key) return faqs
  return faqs.filter((item) => `${item.q}${item.a}`.includes(key))
}

function switchMode(nextMode) {
  if (mode.value === nextMode) return
  mode.value = nextMode
  messages.value.push({
    role: 'bot',
    text: nextMode === 'human'
      ? '人工模式：留言会提交到当前账号的训练日志，不会直接连接外部坐席。'
      : '智能模式：只根据帮助中心 FAQ 回复，不会提交人工留言。',
  })
}

async function send() {
  const text = draft.value.trim() || query.value.trim()
  if (!text || sending.value) return
  messages.value.push({ role: 'user', text })
  draft.value = ''
  if (mode.value === 'human') {
    sending.value = true
    try {
      await addJournal({
        entry_date: new Date().toISOString().slice(0, 10),
        body: `[帮助/人工留言] ${text}`,
      })
      messages.value.push({ role: 'bot', text: '人工留言已保存到当前账号的训练日志；此入口不连接外部坐席。' })
    } catch (error) {
      messages.value.push({ role: 'bot', text: `人工留言保存失败：${journalSubmitErrorMessage(error)}` })
    } finally {
      sending.value = false
    }
  } else {
    const hits = matchFaq(text)
    messages.value.push({
      role: 'bot',
      text: hits[0]
        ? `${hits[0].q} ${hits[0].a}`
        : '没有找到匹配的帮助内容。请换个关键词，例如“训练”“评课”或“资源”，也可以切换到人工客服留言。',
    })
  }
  await nextTick()
  if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
}

function onFabDown(event) {
  drag = { kind: 'fab', moved: false, x: event.clientX, y: event.clientY, ox: pos.value.x, oy: pos.value.y }
}

function onChatDown(event) {
  if (event.target.tagName === 'BUTTON') return
  drag = { kind: 'chat', moved: false, x: event.clientX, y: event.clientY, ox: pos.value.chatX, oy: pos.value.chatY }
}

function onMove(event) {
  if (!drag) return
  const dx = event.clientX - drag.x
  const dy = event.clientY - drag.y
  if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true
  if (drag.kind === 'fab') {
    pos.value.x = (drag.ox ?? window.innerWidth - 72) + dx
    pos.value.y = (drag.oy ?? window.innerHeight - 72) + dy
    fabStyle.value = { left: `${pos.value.x}px`, top: `${pos.value.y}px`, right: 'auto', bottom: 'auto' }
  } else {
    pos.value.chatX = (drag.ox ?? window.innerWidth - 420) + dx
    pos.value.chatY = (drag.oy ?? window.innerHeight - 520) + dy
    chatStyle.value = { left: `${pos.value.chatX}px`, top: `${pos.value.chatY}px`, right: 'auto', bottom: 'auto' }
  }
}

function onUp() {
  drag = null
}

onMounted(() => {
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  window.addEventListener('link-help', openFromEvent)
})
onUnmounted(() => {
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
  window.removeEventListener('link-help', openFromEvent)
})
</script>
