<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PaperTitle from '../components/PaperTitle.vue'
import CourseDesk from '../components/CourseDesk.vue'
import CourseModal from '../components/CourseModal.vue'
import { featuredMoocs, moocForCourse } from '../data/moocCourses'
import { fetchCourses } from '../services/dashboard'
import { DESK_SKILLS, courseSkill, deskCourses, preferredCourse } from '../services/courseDesk.js'
import { normalizeSearchQuery } from '../utils/navigation'
const route = useRoute(), router = useRouter()
const courses = ref([]), selectedId = ref(null), skillId = ref(null), loading = ref(true), courseError = ref('')
const query = ref(normalizeSearchQuery(route.query.q)), modal = ref(null), directoryFilter = ref('all')
const filtered = computed(() => deskCourses(courses.value, query.value))
const available = computed(() => [...new Set(filtered.value.map(courseSkill).filter(Boolean))])
const categoryCourses = computed(() => filtered.value.filter(course => courseSkill(course) === skillId.value))
const selected = computed(() => filtered.value.find(course => String(course.id) === String(selectedId.value)) || null)
const progress = computed(() => Math.min(100, Math.max(0, Number(selected.value?.progress_percent) || 0)))
const directoryCourses = computed(() => directoryFilter.value === 'all' ? filtered.value : filtered.value.filter(course => courseSkill(course) === directoryFilter.value))
const sourceLink = computed(() => safeUrl(selected.value?.source_url))
const mooc = computed(() => selected.value && moocForCourse(selected.value))
function safeUrl(url) { try { const u = new URL(url); return ['https:', 'http:'].includes(u.protocol) ? u.href : null } catch { return null } }
function reconcile() { const c = preferredCourse(filtered.value, selectedId.value); selectedId.value = c?.id ?? null; skillId.value = c ? courseSkill(c) : null }
function chooseSkill(id) { const c = preferredCourse(filtered.value.filter(c => courseSkill(c) === id), selectedId.value); if (c) { chooseCourse(c.id); modal.value = 'detail' } }
function chooseCourse(id) { const c = filtered.value.find(c => String(c.id) === String(id)); if (c) { selectedId.value = c.id; skillId.value = courseSkill(c) } }
function start(course) { if (course?.id) router.push({ path: '/training', query: { courseId: course.id } }) }
function chooseFromDirectory(course) { chooseCourse(course.id); modal.value = 'detail' }
function applyRoute() {
  const c = courses.value.find(c => String(c.id) === String(route.query.courseId))
  if (c) { query.value = ''; chooseCourse(c.id); modal.value = 'detail' }
  else if (route.query.skill && available.value.includes(route.query.skill)) chooseSkill(route.query.skill)
  else if (route.query.view === 'all') modal.value = 'directory'
}
async function loadCourses() {
  loading.value = true; courseError.value = ''
  try { courses.value = await fetchCourses(); reconcile(); applyRoute() }
  catch (error) { courses.value = []; courseError.value = error?.response?.data?.message || '课程加载失败，请重试。' }
  finally { loading.value = false }
}
watch(query, () => { reconcile(); if (!available.value.includes(directoryFilter.value)) directoryFilter.value = 'all' })
watch(() => route.query.q, value => { query.value = normalizeSearchQuery(value) })
watch(() => [route.query.courseId, route.query.skill, route.query.view], applyRoute)
onMounted(loadCourses)
</script>
<template>
  <div class="desk-page">
    <PaperTitle text="我的备课桌" />
    <div class="desk-page__tools">
      <div class="desk-heading"><h2>我的备课桌</h2><p>选一件桌上的物品，开始研习教学技能。</p></div>
      <label class="desk-search"><span aria-hidden="true">⌕</span><input v-model="query" type="search" placeholder="搜索课程" aria-label="搜索课程或桌面物件" /></label>
      <button type="button" class="desk-directory-toggle" @click="modal = 'directory'">全部课程<span v-if="!loading && !courseError">（{{ filtered.length }}）</span></button>
    </div>
    <CourseDesk :selected="skillId" :available="available" @select="chooseSkill" />
    <p v-if="loading" class="desk-feedback" role="status">正在加载课程…</p>
    <p v-else-if="courseError" class="desk-feedback" role="alert">{{ courseError }} <button @click="loadCourses">重新加载课程</button></p>
    <p v-else-if="!filtered.length" class="desk-feedback" role="status">{{ query ? '没有匹配的课程' : '暂无课程' }} <button v-if="query" @click="query = ''">清除搜索</button></p>
    <CourseModal v-if="modal" :title="modal === 'directory' ? '全部课程' : selected?.title || '课程详情'" @close="modal = null">
      <template v-if="modal === 'detail' && selected">
        <select v-if="categoryCourses.length > 1" aria-label="选择本类课程" :value="selectedId" @change="chooseCourse($event.target.value)"><option v-for="course in categoryCourses" :key="course.id" :value="course.id">{{ course.title }}</option></select>
        <div class="desk-progress"><span>{{ selected.status_label || '未开始' }} · {{ selected.lesson_count }} 课时</span><b>{{ progress }}%</b><progress :value="progress" max="100" aria-label="课程进度">{{ progress }}%</progress></div>
        <p v-if="selected.description">{{ selected.description }}</p><pre v-if="selected.outline">{{ selected.outline }}</pre>
        <div class="desk-sources"><span v-if="selected.source">{{ selected.source }}</span><a v-if="sourceLink" :href="sourceLink" target="_blank" rel="noopener noreferrer">查看出处 ↗</a><a v-if="mooc" :href="mooc.url" target="_blank" rel="noopener noreferrer">{{ mooc.label }} ↗</a></div>
      </template>
      <template v-else-if="modal === 'directory'">
        <select v-model="directoryFilter" aria-label="筛选课程分类"><option value="all">全部分类</option><option v-for="skill in DESK_SKILLS" :key="skill.id" :value="skill.id" :disabled="!available.includes(skill.id)">{{ skill.label }}</option></select>
        <p v-if="!directoryCourses.length">暂无匹配课程</p>
        <ul class="desk-directory"><li v-for="course in directoryCourses" :key="course.id"><button type="button" @click="chooseFromDirectory(course)"><small>{{ course.stage || course.category }}</small><strong>{{ course.title }}</strong><span>{{ course.status_label }} ↗</span></button></li></ul>
        <details class="desk-mooc"><summary>慕课延伸</summary><p v-for="item in featuredMoocs" :key="item.id"><a :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title }} · {{ item.platform }} ↗</a></p></details>
      </template>
      <template v-if="modal === 'detail' && selected" #footer><button class="desk-secondary" @click="modal = 'directory'">全部课程</button><button class="desk-start" @click="start(selected)">开始训练 ↗</button></template>
    </CourseModal>
  </div>
</template>
<style scoped>
.desk-page { position:relative; width:100%; height:100%; min-height:0; isolation:isolate; }
.desk-page__tools { position:absolute; top:18px; left:20px; z-index:3; display:flex; align-items:center; gap:8px; }
.desk-search { display:flex; gap:8px; align-items:center; color:#fff1dd; background:#241b2deb; border:1px solid #bba6c888; border-radius:24px; padding:0 14px; }
.desk-search input { color:inherit; background:transparent; border:0; width:clamp(100px,13vw,210px); height:42px; outline-offset:4px; }
.desk-directory-toggle,.desk-secondary { padding:12px 16px; color:#fff1dd; background:#241b2deb; border:1px solid #bba6c888; border-radius:24px; white-space:nowrap; }
.desk-feedback { position:absolute; left:50%; top:45%; transform:translate(-50%,-50%); padding:18px; border-radius:16px; color:#fff; background:#241b2deb; }
.desk-feedback button { padding:8px; margin:8px; }
.desk-progress { display:flex; flex-wrap:wrap; justify-content:space-between; gap:12px; margin:22px 0; font-size:14px; }
.desk-progress progress { width:100%; height:8px; accent-color:#9873b2; }
.desk-sources { display:flex; gap:16px; flex-wrap:wrap; margin-top:24px; font-size:14px; }
.desk-start { padding:12px 24px; border:0; border-radius:22px; background:#f5bc7a; color:#312038; font-weight:700; }
.desk-directory { list-style:none; padding:0; }
.desk-directory li { border-bottom:1px solid #94759b33; }
.desk-directory button { display:flex; width:100%; align-items:center; gap:16px; text-align:left; border:0; color:inherit; background:transparent; padding:18px 0; }
.desk-directory strong { flex:1; }.desk-directory small { min-width:60px; }.desk-directory span { font-size:12px; }
.desk-mooc { margin-top:24px; }
@media(max-width:700px) { .desk-page__tools { top:68px; left:12px; right:12px; }.desk-search { flex:1; min-width:0; }.desk-search input { width:100%; }.desk-directory button { flex-wrap:wrap; gap:8px; }.desk-directory strong { min-width:60%; } }
</style>
