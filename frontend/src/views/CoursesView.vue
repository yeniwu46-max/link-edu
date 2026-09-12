<template>
  <div class="sparse-page page-courses">
    <header class="page-head">
      <p class="shiny-kicker">COURSE DECK</p>
      <h1 class="split-title">课程中心</h1>
      <p class="page-lead">依据《教师职业技能训练大纲（试行）》九项课堂教学技能，先分项 8 分钟，再综合 10 分钟模拟授课。</p>
    </header>

    <div class="page-scroll">
    <div class="course-layout">
      <aside class="filter-rail glass" aria-label="课程分类">
        <button
          v-for="item in filters"
          :key="item.id"
          type="button"
          :class="{ active: filter === item.id }"
          @click="filter = item.id"
        >{{ item.label }}</button>
      </aside>

      <div class="course-main">
        <div class="featured-row">
          <SpotlightPane v-for="course in featured" :key="course.id" class="course-slab glass">
            <small>{{ course.stage || course.category }}</small>
            <h2>{{ course.title }}</h2>
            <p>{{ course.description }}</p>
            <div class="slab-meta">
              <span>{{ course.lesson_count }} 课时</span>
              <b>{{ course.status_label }}</b>
            </div>
            <div class="progress slim"><i :style="{ width: `${course.progress_percent || 0}%` }"></i></div>
            <div class="slab-actions">
              <Magnet>
                <button class="primary" type="button" @click="start(course)">开始训练</button>
              </Magnet>
              <button type="button" @click="open(course)">详情</button>
            </div>
          </SpotlightPane>
        </div>

        <ul class="course-strip">
          <li v-for="course in rest" :key="course.id" class="glare-row course-tile glass">
            <div>
              <strong>{{ course.title }}</strong>
              <span>{{ course.stage || course.category }}</span>
            </div>
            <button type="button" @click="start(course)">进入</button>
          </li>
        </ul>
      </div>
    </div>
    </div>

    <aside v-if="detail" class="detail-drawer glass" role="dialog">
      <button type="button" class="close-x" aria-label="关闭" @click="detail = null">×</button>
      <p>{{ detail.stage || detail.category }}</p>
      <h2>{{ detail.title }}</h2>
      <p>{{ detail.description }}</p>
      <p v-if="detail.source" class="course-source">
        <span>来源：{{ detail.source }}</span>
        <a
          v-if="detail.source_url"
          :href="detail.source_url"
          target="_blank"
          rel="noopener noreferrer"
        >查看出处</a>
        <a
          v-if="extendUrl(detail)"
          :href="extendUrl(detail)"
          target="_blank"
          rel="noopener noreferrer"
        >延伸：智慧树微格课</a>
      </p>
      <pre v-if="detail.outline" class="course-outline">{{ detail.outline }}</pre>
      <p>{{ detail.lesson_count }} 课时 · {{ detail.status_label }}</p>
      <Magnet>
        <button class="primary" type="button" @click="start(detail)">开始训练</button>
      </Magnet>
    </aside>
    <div v-if="detail" class="help-mask" @click="detail = null"></div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Magnet from '../components/fx/Magnet.vue'
import SpotlightPane from '../components/fx/SpotlightPane.vue'
import { fetchCourses } from '../services/dashboard'

const SMART_EDU = 'https://higher.smartedu.cn/course/671ad61416d8a05eedca49d6'

const route = useRoute()
const router = useRouter()
const courses = ref([])
const filter = ref('all')
const detail = ref(null)
const query = computed(() => String(route.query.q || '').trim())

const filters = [
  { id: 'all', label: '全部' },
  { id: '专项01', label: '导入' },
  { id: '专项02', label: '板书' },
  { id: '专项03', label: '演示' },
  { id: '专项04', label: '讲解' },
  { id: '专项05', label: '提问' },
  { id: '专项06', label: '强化' },
  { id: '专项07', label: '结束' },
  { id: '专项08', label: '组织' },
  { id: '专项09', label: '变化' },
  { id: '综合', label: '综合' },
]

const filtered = computed(() => {
  return courses.value.filter((course) => {
    const stage = course.stage || ''
    const hay = `${course.title}${course.category}${course.description}${stage}`
    const byFilter = filter.value === 'all' || stage.includes(filter.value)
    const byQuery = !query.value || hay.includes(query.value)
    return byFilter && byQuery
  })
})

const featured = computed(() => {
  const sorted = [...filtered.value].sort((a, b) => Number(b.status === 'in_progress') - Number(a.status === 'in_progress'))
  return sorted.slice(0, 3)
})

const rest = computed(() => {
  const ids = new Set(featured.value.map((item) => item.id))
  return filtered.value.filter((item) => !ids.has(item.id))
})

function extendUrl(course) {
  if (!course?.stage) return ''
  if (String(course.stage).startsWith('综合11')) return ''
  if (course.source_url === SMART_EDU) return ''
  return SMART_EDU
}

function start(course) {
  router.push({ path: '/training', query: { courseId: course.id } })
}

function open(course) {
  detail.value = course
}

watch(() => route.query.q, () => {
  if (query.value) filter.value = 'all'
})

onMounted(async () => {
  try {
    courses.value = await fetchCourses()
  } catch (error) {
    console.warn('[Courses] fallback', error)
    courses.value = [
      { id: 1, title: '导入技能', category: '微格教学 · 专项', stage: '专项01 · 导入', description: '新课开始时把学生带进课题。', lesson_count: 6, progress_percent: 68, status: 'in_progress', status_label: '进行中' },
      { id: 2, title: '板书板画技能', category: '微格教学 · 专项', stage: '专项02 · 板书', description: '用精炼文字和图表把教学信息留在黑板上。', lesson_count: 6, progress_percent: 100, status: 'completed', status_label: '已完成' },
      { id: 3, title: '综合模拟授课（10 分钟）', category: '微格教学 · 综合', stage: '综合10 · 模拟授课', description: '把导入到结束串成一节完整微格课。', lesson_count: 10, progress_percent: 0, status: 'idle', status_label: '未开始' },
    ]
  }
})
</script>
