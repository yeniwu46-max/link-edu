<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PaperTitle from '../components/PaperTitle.vue'
import CourseDesk from '../components/CourseDesk.vue'
import { featuredMoocs, moocForCourse } from '../data/moocCourses'
import { fetchCourses } from '../services/dashboard'
import { DESK_SKILLS, courseSkill, deskCourses, preferredCourse } from '../services/courseDesk.js'
import { normalizeSearchQuery } from '../utils/navigation'
const route = useRoute(), router = useRouter()
const courses = ref([]), selectedId = ref(null), skillId = ref(null), loading = ref(true), courseError = ref('')
const query = ref(normalizeSearchQuery(route.query.q)), directory = ref(route.query.view === 'all'), detail = ref(false)
const directoryEl = ref(null), detailEl = ref(null)
const filtered = computed(() => deskCourses(courses.value, query.value))
const available = computed(() => [...new Set(filtered.value.map(courseSkill).filter(Boolean))])
const categoryCourses = computed(() => filtered.value.filter(course => courseSkill(course) === skillId.value))
const selected = computed(() => filtered.value.find(course => String(course.id) === String(selectedId.value)) || null)
const progress = computed(() => Math.min(100, Math.max(0, Number(selected.value?.progress_percent) || 0)))
const directoryFilter = ref('all')
const directoryCourses = computed(() => directoryFilter.value === 'all' ? filtered.value : filtered.value.filter(course => courseSkill(course) === directoryFilter.value))
const sourceLink = computed(() => safeUrl(selected.value?.source_url))
const mooc = computed(() => selected.value && moocForCourse(selected.value))
function safeUrl(url) { try { const u = new URL(url); return ['https:', 'http:'].includes(u.protocol) ? u.href : null } catch { return null } }
function reconcile() {
  const current = preferredCourse(filtered.value, selectedId.value)
  selectedId.value = current?.id ?? null
  skillId.value = current ? courseSkill(current) : null
}
function chooseSkill(id) {
  const list = filtered.value.filter(course => courseSkill(course) === id)
  const course = preferredCourse(list, selectedId.value)
  if (!course) return
  skillId.value = id; selectedId.value = course.id; detail.value = false
}
function chooseCourse(id) {
  const course = filtered.value.find(item => String(item.id) === String(id))
  if (course) { selectedId.value = course.id; skillId.value = courseSkill(course); detail.value = false }
}
function start(course) { if (course?.id) router.push({ path: '/training', query: { courseId: course.id } }) }
async function showDirectory() { directory.value = !directory.value; if (directory.value) { await nextTick(); directoryEl.value?.scrollIntoView({ behavior: 'auto', block: 'nearest' }); directoryEl.value?.focus() } }
async function toggleDetail() { detail.value = !detail.value; if (detail.value) { await nextTick(); detailEl.value?.focus() } }
function chooseFromDirectory(course) { chooseCourse(course.id); detail.value = true; nextTick(() => { detailEl.value?.scrollIntoView({ block:'nearest' }); detailEl.value?.focus() }) }
async function loadCourses() {
  loading.value = true; courseError.value = ''
  try {
    courses.value = await fetchCourses()
    const byRoute = courses.value.find(course => String(course.id) === String(route.query.courseId))
    const bySkill = courses.value.filter(course => courseSkill(course) === route.query.skill)
    const first = byRoute || preferredCourse(bySkill.length ? bySkill : filtered.value)
    selectedId.value = first?.id ?? null
    reconcile()
  } catch (error) {
    courses.value = []; selectedId.value = null; skillId.value = null
    courseError.value = error?.response?.data?.message || '课程加载失败，请重试。'
  } finally { loading.value = false }
}
watch(query, () => { reconcile(); if (!available.value.includes(directoryFilter.value)) directoryFilter.value = 'all' })
watch(() => route.query.q, value => { query.value = normalizeSearchQuery(value) })
onMounted(loadCourses)
</script>
<template>
  <div class="sparse-page page-courses desk-page">
    <div class="page-scroll">
      <header class="desk-page__header">
        <PaperTitle text="我的备课桌" />
        <div class="desk-page__tools">
          <label class="desk-search"><span aria-hidden="true">⌕</span><input v-model="query" type="search" placeholder="搜索课程" aria-label="搜索课程或桌面物件" /></label>
          <button type="button" class="desk-directory-toggle" :aria-expanded="directory" aria-controls="course-directory" @click="showDirectory">全部课程 <span aria-hidden="true">↗</span></button>
        </div>
      </header>
      <p v-if="loading" class="desk-feedback" role="status">正在加载课程…</p>
      <div v-else-if="courseError" class="desk-feedback" role="alert"><span>{{ courseError }}</span><button type="button" @click="loadCourses">重新加载课程</button></div>
      <template v-else>
        <CourseDesk :selected="skillId" :available="available" @select="chooseSkill" />
        <p v-if="!filtered.length" class="desk-feedback" role="status">{{ query ? '没有匹配的课程' : '暂无课程' }}<button v-if="query" type="button" @click="query = ''">清除搜索</button></p>
        <section v-if="selected" class="desk-selection" aria-label="当前课程" aria-live="polite" aria-atomic="true">
          <div class="desk-selection__title">
            <small>{{ selected.stage || selected.category }}</small>
            <h2>{{ selected.title }}</h2>
            <select v-if="categoryCourses.length > 1" aria-label="选择本类课程" :value="selectedId" @change="chooseCourse($event.target.value)"><option v-for="course in categoryCourses" :key="course.id" :value="course.id">{{ course.title }}</option></select>
          </div>
          <div class="desk-selection__progress">
            <span>{{ selected.status_label || '未开始' }}<b>{{ selected.lesson_count }} 课时 · {{ progress }}%</b></span>
            <progress :value="progress" max="100" aria-label="课程进度">{{ progress }}%</progress>
          </div>
          <button type="button" class="desk-secondary" :aria-expanded="detail" aria-controls="course-detail" @click="toggleDetail">详情</button>
          <button type="button" class="desk-start" @click="start(selected)">开始训练 <span aria-hidden="true">↗</span></button>
        </section>
        <section v-if="detail && selected" id="course-detail" ref="detailEl" class="desk-detail" tabindex="-1" aria-label="课程详情">
          <header><h2>{{ selected.title }}</h2><button type="button" aria-label="收起课程详情" @click="detail = false">×</button></header>
          <p v-if="selected.description">{{ selected.description }}</p>
          <pre v-if="selected.outline">{{ selected.outline }}</pre>
          <div class="desk-detail__sources"><span v-if="selected.source">{{ selected.source }}</span><a v-if="sourceLink" :href="sourceLink" target="_blank" rel="noopener noreferrer">查看出处 ↗</a><a v-if="mooc" :href="mooc.url" target="_blank" rel="noopener noreferrer">{{ mooc.label }} ↗</a></div>
        </section>
      </template>
      <section v-if="directory" id="course-directory" ref="directoryEl" class="desk-directory" tabindex="-1" aria-label="全部课程目录">
        <header><h2>全部课程 <small>{{ directoryCourses.length }}</small></h2><select v-model="directoryFilter" aria-label="筛选课程分类"><option value="all">全部分类</option><option v-for="skill in DESK_SKILLS" :key="skill.id" :value="skill.id" :disabled="!available.includes(skill.id)">{{ skill.label }}</option></select></header>
        <p v-if="!directoryCourses.length">暂无匹配课程</p>
        <ul><li v-for="course in directoryCourses" :key="course.id"><button class="desk-directory__name" type="button" @click="chooseFromDirectory(course)"><span>{{ course.stage || course.category }}</span><strong>{{ course.title }}</strong></button><span class="desk-directory__status">{{ course.status_label }}</span><button class="desk-directory__start" type="button" :aria-label="`开始训练：${course.title}`" @click="start(course)">开始训练 ↗</button></li></ul>
      </section>
      <details class="desk-mooc"><summary>慕课延伸 <span aria-hidden="true">↗</span></summary><ul><li v-for="item in featuredMoocs" :key="item.id"><a :href="item.url" target="_blank" rel="noopener noreferrer"><strong>{{ item.title }}</strong><span>{{ item.platform }} ↗</span></a></li></ul></details>
    </div>
  </div>
</template>
<style scoped>
.desk-page { --desk-paper:#fff1dd; --desk-ink:#35293d; --desk-muted:#c9b8ce; --desk-line:#e0c7f02b; min-height:0; }
.desk-page > .page-scroll { padding:8px 12px 40px 2px; }
.desk-page :deep(.course-desk) { max-width:min(100%,calc((100dvh - 390px) * 1.776)); margin-inline:auto; }
.desk-page :deep(.course-desk--fallback) { max-width:100%; }
.desk-page__header { display:flex; align-items:center; justify-content:space-between; gap:24px; padding:0 0 10px; }
.desk-page__header :deep(.paper-title) { margin-bottom:10px; font-size:clamp(36px,3.5vw,58px); }
.desk-page__tools { display:flex; align-items:center; gap:12px; }
.desk-search { display:flex; align-items:center; gap:10px; border:1px solid #a28aae77; border-radius:30px; padding:0 16px; background:#241b2de0; color:#cdb9d9; }
.desk-search span { font-size:28px; }
.desk-search input { width:170px; min-width:0; padding:12px 0; border:0; background:none; color:#fff4e7; outline-offset:3px; }
.desk-directory-toggle,.desk-secondary { border:1px solid #bba4c766; border-radius:25px; padding:12px 20px; background:#2e2337; color:#f9e9da; white-space:nowrap; }
.desk-directory-toggle span { margin-left:10px; }
.desk-selection { position:relative; display:flex; align-items:center; gap:24px; margin:16px 0 0; padding:24px 100px 24px 28px; background:#2c2134f2; border:1px solid #dfc7ed3b; border-radius:22px; box-shadow:0 10px 35px #110e1922; color:#fff1dd; }
.desk-selection__title { flex:1; min-width:0; }
.desk-selection__title small { display:block; color:#c5afcd; margin-bottom:5px; font-size:12px; }
.desk-selection h2 { margin:0; font-size:clamp(20px,2vw,30px); font-weight:750; color:inherit!important; }
.desk-selection__title select { margin-top:10px; max-width:100%; padding:6px 10px; background:#382a41; border:1px solid #8f729c; border-radius:8px; color:inherit; }
.desk-selection__progress { min-width:170px; width:25%; }
.desk-selection__progress span { display:flex; justify-content:space-between; gap:14px; color:#d7c7dc; font-size:12px; }
.desk-selection__progress b { font-weight:400; }
.desk-selection progress { display:block; width:100%; height:7px; appearance:none; border:0; margin-top:12px; border-radius:8px; overflow:hidden; background:#63546c; }
.desk-selection progress::-webkit-progress-bar { background:#63546c; }
.desk-selection progress::-webkit-progress-value { background:#f8bf7b; border-radius:8px; }
.desk-selection progress::-moz-progress-bar { background:#f8bf7b; }
.desk-start { display:flex; align-items:center; justify-content:center; gap:24px; padding:15px 24px; border:0; border-radius:24px; background:#ffc376; color:#35233b; font-weight:750; white-space:nowrap; box-shadow:inset 0 1px #ffe9c4; transition:transform .2s; }
.desk-start:hover { transform:translateY(-2px); background:#ffd397; }
.desk-start:active { transform:scale(.98); }
.desk-feedback { display:flex; align-items:center; justify-content:center; gap:20px; min-height:90px; color:var(--desk-muted); }
.desk-feedback button { color:#ffc376; background:transparent; border:1px solid #ffc37677; padding:10px 16px; border-radius:12px; }
.desk-detail,.desk-directory { margin-top:24px; padding:28px; color:var(--desk-ink); background:var(--desk-paper); border-radius:16px 24px 24px 6px; box-shadow:4px 5px #9075a24d; }
.desk-detail header,.desk-directory header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:20px; }
.desk-detail h2,.desk-directory h2 { color:inherit; margin:0; font-size:22px; }
.desk-detail header button { border:0; background:transparent; color:inherit; font-size:24px; padding:6px 12px; }
.desk-detail p { line-height:1.9; max-width:80ch; }
.desk-detail pre { white-space:pre-wrap; font:inherit; line-height:1.8; }
.desk-detail__sources { display:flex; flex-wrap:wrap; gap:18px; margin-top:20px; font-size:13px; }
.desk-detail a { color:#68427c; text-decoration:underline; text-underline-offset:4px; }
.desk-directory select { background:#f6e8d7; color:#35293d; padding:8px 12px; border:1px solid #b6a1bc; border-radius:12px; }
.desk-directory ul,.desk-mooc ul { list-style:none; margin:0; padding:0; }
.desk-directory li { display:flex; align-items:center; gap:20px; padding:14px 0; border-top:1px solid #6c4e7722; }
.desk-directory__name { flex:1; display:flex; gap:18px; align-items:center; text-align:left; color:inherit; background:transparent; border:0; padding:8px 0; }
.desk-directory__name span { font-size:12px; color:#7c6586; min-width:80px; }
.desk-directory__name strong { font-size:16px; }
.desk-directory__status { font-size:12px; color:#7c6586; }
.desk-directory__start { padding:10px 16px; border:0; border-radius:18px; background:#dcc6eb; color:#35293d; white-space:nowrap; }
.desk-mooc { margin-top:24px; color:#cbb8d3; }
.desk-mooc summary { cursor:pointer; padding:16px 4px; width:max-content; }
.desk-mooc li { border-top:1px solid var(--desk-line); }
.desk-mooc a { display:flex; justify-content:space-between; gap:20px; padding:16px 4px; color:inherit; text-decoration:none; }
.desk-mooc strong { font-weight:500; }
.desk-mooc span { font-size:12px; }
:global([data-ui-theme="academy"]) .desk-page { --desk-paper:#f5f9ff; --desk-ink:#243a58; --desk-muted:#566c88; --desk-line:#9ab2ce50; }
:global([data-ui-theme="academy"]) .desk-search,:global([data-ui-theme="academy"]) .desk-directory-toggle { background:#eef4fd; color:#344e6e; border-color:#a6bddb; }
:global([data-ui-theme="academy"]) .desk-search input { color:#344e6e; }
:global([data-ui-theme="academy"]) .desk-mooc { color:#506883; }
@media(max-width:1100px) { .desk-page__header { align-items:flex-start; flex-direction:column; gap:4px; } .desk-page__tools { width:100%; margin-bottom:16px; } .desk-search { flex:1; } .desk-search input { width:100%; } .desk-selection { flex-wrap:wrap; gap:16px; padding:20px; } .desk-selection__title { flex-basis:50%; } }
@media(max-width:700px) { .desk-page > .page-scroll { padding:0 2px 32px; } .desk-page__header :deep(.paper-title) { font-size:36px; } .desk-directory-toggle { padding:12px 14px; } .desk-selection { display:grid; grid-template-columns:1fr 1fr; padding:18px; gap:18px 12px; border-radius:16px; } .desk-selection__title,.desk-selection__progress { grid-column:1/-1; width:100%; } .desk-selection h2 { font-size:24px; } .desk-start { padding:12px; gap:12px; } .desk-detail,.desk-directory { padding:20px 16px; } .desk-directory li { flex-wrap:wrap; gap:4px 12px; } .desk-directory__name { flex-basis:100%; } .desk-directory__name span { min-width:60px; } .desk-directory__status { flex:1; } }
@media(prefers-reduced-motion:reduce) { .desk-start { transition:none; transform:none!important; } }
@media(max-width:700px) { .desk-page :deep(.course-desk) { max-width:100%; } }
</style>
