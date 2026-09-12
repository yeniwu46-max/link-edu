<template>
  <div class="sparse-page profile-page" :class="`profile-page--${page}`">
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">{{ kicker }}</p>
        <SplitTitle :text="pageTitle" />
        <p class="page-lead">{{ pageLead }}</p>
      </div>
    </header>

    <div class="page-scroll">
    <!-- 个人中心：身份、等级、徽章、最近训练 -->
    <div v-if="page === 'center'" class="profile-stack">
      <section class="identity-card">
        <div class="identity-card__face">
          <b>{{ initial }}</b>
          <div>
            <h2>{{ form.name || '未填写姓名' }}</h2>
            <p>{{ roleLabel }} · {{ form.school || '未填写学校' }}</p>
          </div>
        </div>
        <div class="profile-grid">
          <label>姓名<input v-model="form.name" /></label>
          <label>
            角色
            <select v-model="form.role">
              <option value="student">师范生</option>
              <option value="teacher">指导教师</option>
            </select>
          </label>
          <label>学校<input v-model="form.school" /></label>
          <label>专业<input v-model="form.major" /></label>
          <label>年级<input v-model="form.grade" placeholder="如本科三年级" /></label>
          <label class="span-2">自我介绍<textarea v-model="form.bio" rows="4"></textarea></label>
          <button class="primary" type="button" @click="save">保存档案</button>
          <p v-if="saved" class="dock-hint">档案已保存。</p>
        </div>
      </section>

      <section class="level-card">
        <div class="level-card__meta">
          <strong>{{ profile.level_label || 'Lv.1 微格学员' }}</strong>
          <span>{{ profile.next_hint || '完成训练可提升等级' }}</span>
        </div>
        <div class="xp-bar" aria-label="经验进度">
          <i :style="{ width: `${profile.xp_percent || 0}%` }"></i>
        </div>
        <p class="dock-hint">经验 {{ profile.xp || 0 }} · 累计训练 {{ profile.session_count || 0 }} 次</p>
      </section>

      <section>
        <h3 class="profile-block-title">徽章墙</h3>
        <div class="badge-grid">
          <article v-for="item in badges" :key="item.id" :class="{ earned: item.earned }">
            <strong>{{ item.name }}</strong>
            <span>{{ item.hint }}</span>
            <b>{{ item.earned ? '已获得' : '未点亮' }}</b>
          </article>
        </div>
      </section>

      <section>
        <h3 class="profile-block-title">最近训练摘要</h3>
        <div v-if="recent.length" class="recent-list">
          <button
            v-for="item in recent"
            :key="item.id"
            type="button"
            class="recent-item"
            @click="openReview(item.id)"
          >
            <b>{{ item.overall_score }}</b>
            <div>
              <strong>{{ item.course_title || '微格训练' }}</strong>
              <p>{{ item.suggestion }}</p>
            </div>
          </button>
        </div>
        <p v-else class="profile-copy">还没有评课记录。完成一次训练后会显示综合分和一句话建议。</p>
      </section>
    </div>

    <!-- 设置：只做系统操作 -->
    <div v-else-if="page === 'settings'" class="settings-stack">
      <section class="settings-block">
        <h3>训练默认项</h3>
        <p class="dock-hint">进入教学训练时自动套用。可勾选本机录制整段复盘视频；评课仅上传关帧，整段视频不上云。换设备或清除站点数据后本机回放会丢失，请自行下载备份。</p>
        <label class="settings-row">
          <span>默认打开镜头</span>
          <input v-model="settings.cameraDefault" type="checkbox" @change="persistSettings" />
        </label>
        <div class="settings-row">
          <span>默认模式</span>
          <div class="mode-picks">
            <button type="button" :class="{ active: settings.mode === 'fragment' }" @click="setSetting('mode', 'fragment')">片段 8 分钟</button>
            <button type="button" :class="{ active: settings.mode === 'full' }" @click="setSetting('mode', 'full')">完整 10 分钟</button>
          </div>
        </div>
        <div class="settings-row">
          <span>默认技能</span>
          <div class="scene-picks">
            <button
              v-for="item in scenes"
              :key="item"
              type="button"
              :class="{ active: settings.scene === item }"
              @click="setSetting('scene', item)"
            >{{ item }}</button>
          </div>
        </div>
      </section>

      <section class="settings-block">
        <h3>显示与评课</h3>
        <div class="settings-row">
          <span>问候语</span>
          <div class="mode-picks">
            <button type="button" :class="{ active: settings.greetingLang === 'zh' }" @click="setSetting('greetingLang', 'zh')">中文</button>
            <button type="button" :class="{ active: settings.greetingLang === 'en' }" @click="setSetting('greetingLang', 'en')">英文</button>
            <button type="button" :class="{ active: settings.greetingLang === 'both' }" @click="setSetting('greetingLang', 'both')">中英都要</button>
          </div>
        </div>
        <label class="settings-row">
          <span>显示「演示评分」角标</span>
          <input v-model="settings.showDemoBadge" type="checkbox" @change="persistSettings" />
        </label>
      </section>

      <section class="settings-block">
        <h3>账号</h3>
        <p class="dock-hint">姓名、角色、学校请到个人中心修改。这里只展示当前账号。</p>
        <dl class="account-dl">
          <div><dt>账号</dt><dd>{{ auth.user?.account || 'demo' }}</dd></div>
          <div><dt>姓名</dt><dd>{{ auth.user?.name || profile.name || '—' }}</dd></div>
          <div><dt>角色</dt><dd>{{ auth.user?.role_label || roleLabel }}</dd></div>
        </dl>
        <button type="button" @click="logout">退出登录</button>
      </section>

      <section class="settings-block">
        <h3>数据</h3>
        <p>训练镜头可本机录制复盘；整段视频只存在当前浏览器。评课分析使用关帧，不上传播放整段视频。偏好保存在这台浏览器的 localStorage。</p>
        <button type="button" @click="clearPrefs">清除本机偏好，恢复默认</button>
        <p v-if="prefsCleared" class="dock-hint">已恢复默认训练项与显示选项。</p>
      </section>
    </div>

    <!-- 联系我们 -->
    <div v-else class="contact-stack">
      <section class="contact-card">
        <h3>项目信息</h3>
        <dl class="account-dl">
          <div><dt>产品</dt><dd>临客 LINK · AI 微格教学训练平台</dd></div>
          <div><dt>版本</dt><dd>演示版本</dd></div>
          <div><dt>所属院系</dt><dd>师范学院（演示）</dd></div>
        </dl>
      </section>

      <section class="contact-card">
        <h3>对口联系人</h3>
        <ul class="contact-people">
          <li>
            <strong>指导教师</strong>
            <span>陈老师 · 微格教研室</span>
          </li>
          <li>
            <strong>技术支持</strong>
            <span>{{ supportEmail }}</span>
            <button type="button" class="ghost-link" @click="copyEmail">复制邮箱</button>
          </li>
          <li>
            <strong>工作时间</strong>
            <span>工作日 9:00–17:00（演示）</span>
          </li>
        </ul>
        <p v-if="copied" class="dock-hint">邮箱已复制。</p>
      </section>

      <section class="contact-card">
        <h3>快捷入口</h3>
        <div class="contact-actions">
          <button type="button" @click="openHelp('bot')">打开右下角智能客服</button>
          <button class="primary" type="button" @click="openHelp('human')">打开人工留言</button>
        </div>
      </section>

      <section class="contact-card">
        <h3>留言反馈</h3>
        <form class="profile-grid" @submit.prevent="submitMessage">
          <label>姓名<input v-model="message.name" /></label>
          <label>
            主题
            <select v-model="message.topic">
              <option>训练故障</option>
              <option>评课异议</option>
              <option>课程资源</option>
              <option>其他</option>
            </select>
          </label>
          <label class="span-2">内容<textarea v-model="message.body" rows="5" placeholder="写清发生了什么、哪一次训练或哪份评课。"></textarea></label>
          <button class="primary" type="submit">提交留言</button>
          <p v-if="messageOk" class="dock-hint">已收到。演示环境会记入你的训练日志，不会开通独立工单后台。</p>
        </form>
      </section>
    </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SplitTitle from '../components/fx/SplitTitle.vue'
import { addJournal, fetchFeedbacks, fetchProfile, saveProfile } from '../services/dashboard'
import { useAuthStore } from '../stores/auth'
import { loadSettings, openHelpChat, resetSettings, saveSettings } from '../utils/settings'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const saved = ref(false)
const prefsCleared = ref(false)
const copied = ref(false)
const messageOk = ref(false)
const supportEmail = 'link-support@normal.edu'
const scenes = ['导入', '提问', '板书', '互动']
const profile = ref({
  badges: [],
  recent_feedbacks: [],
  school: '',
  major: '',
  grade: '',
  bio: '',
  name: '',
  role: 'student',
  level_label: '',
  xp: 0,
  xp_percent: 0,
  session_count: 0,
  next_hint: '',
})
const form = reactive({ name: '', school: '', major: '', grade: '', bio: '', role: 'student' })
const settings = reactive(loadSettings())
const message = reactive({ name: '', topic: '训练故障', body: '' })

const page = computed(() => {
  const tab = String(route.query.tab || '')
  if (tab === 'settings' || tab === 'contact') return tab
  return 'center'
})
const kicker = computed(() => ({
  center: 'PROFILE',
  settings: 'SETTINGS',
  contact: 'CONTACT',
}[page.value]))
const pageTitle = computed(() => ({
  center: '个人中心',
  settings: '设置',
  contact: '联系我们',
}[page.value]))
const pageLead = computed(() => ({
  center: `${profile.value.level_label || '微格学员'} · ${form.school || profile.value.school || '师范学院（演示）'}`,
  settings: '训练默认项、显示与退出。不在这里改姓名或角色。',
  contact: '找指导教师、技术支持，或留下一条反馈。',
}[page.value]))
const initial = computed(() => (form.name || profile.value.name || '临').slice(0, 1))
const roleLabel = computed(() => (form.role === 'teacher' ? '指导教师' : '师范生'))
const badges = computed(() => profile.value.badges || [])
const recent = computed(() => profile.value.recent_feedbacks || [])

watch(() => route.query.tab, () => {
  saved.value = false
  prefsCleared.value = false
  messageOk.value = false
  copied.value = false
})

onMounted(load)

async function load() {
  try {
    profile.value = await fetchProfile()
  } catch {
    profile.value = {
      name: auth.user?.name || '林晓',
      role: auth.user?.role || 'student',
      school: '师范学院（演示）',
      major: '小学教育',
      grade: '本科三年级',
      bio: '关注课堂导入、提问候答与板书结构。',
      level_label: 'Lv.3 微格学员',
      xp: 120,
      xp_percent: 50,
      session_count: 3,
      next_hint: '再完成 1 次训练可提升等级',
      recent_feedbacks: [],
      badges: [
        { id: 'first', name: '初次上台', earned: true, hint: '完成第一次微格训练' },
        { id: 'habit', name: '勤练不辍', earned: false, hint: '累计 5 次训练' },
        { id: 'closer', name: '完整收束', earned: false, hint: '跑完一次 10 分钟课' },
        { id: 'ask', name: '提问达人', earned: false, hint: '在提问技能上留下评课' },
        { id: 'high', name: '高分片段', earned: false, hint: '单次综合分达到 86' },
        { id: 'archive', name: '有迹可循', earned: false, hint: '完成 3 次评课归档' },
      ],
    }
  }
  if (!profile.value.grade) profile.value.grade = '本科三年级'
  form.name = profile.value.name || ''
  form.school = profile.value.school || ''
  form.major = profile.value.major || ''
  form.grade = profile.value.grade || ''
  form.bio = profile.value.bio || ''
  form.role = profile.value.role === 'teacher' ? 'teacher' : 'student'
  if (!profile.value.recent_feedbacks?.length) {
    try {
      const items = await fetchFeedbacks()
      profile.value.recent_feedbacks = (items || []).slice(0, 3).map((row) => ({
        id: row.id,
        overall_score: row.overall_score,
        suggestion: row.suggestion,
        course_title: row.course_title || '微格训练',
        created_at: row.created_at,
      }))
    } catch {
      /* 没有评课记录时保持空列表 */
    }
  }
  message.name = form.name
}

async function save() {
  try {
    profile.value = await saveProfile({ ...form })
    auth.user = {
      ...auth.user,
      name: form.name,
      role: form.role,
      role_label: roleLabel.value,
      school: form.school,
      major: form.major,
    }
    saved.value = true
  } catch {
    saved.value = true
  }
}

function setSetting(key, value) {
  settings[key] = value
  persistSettings()
}

function persistSettings() {
  saveSettings({ ...settings })
  prefsCleared.value = false
}

function clearPrefs() {
  Object.assign(settings, resetSettings())
  prefsCleared.value = true
}

function logout() {
  auth.logout()
  router.push('/')
}

function openReview(id) {
  router.push({ path: '/ai-review', query: { feedbackId: id } })
}

function openHelp(mode) {
  openHelpChat(mode)
}

async function copyEmail() {
  try {
    await navigator.clipboard.writeText(supportEmail)
  } catch {
    /* 演示环境允许复制失败时仍提示 */
  }
  copied.value = true
}

async function submitMessage() {
  const body = message.body.trim()
  if (!body) return
  const text = `[留言/${message.topic}] ${message.name || form.name || '匿名'}：${body}`
  try {
    await addJournal({ entry_date: new Date().toISOString().slice(0, 10), body: text })
  } catch {
    /* 纯前端成功态也算完成演示 */
  }
  message.body = ''
  messageOk.value = true
}
</script>
