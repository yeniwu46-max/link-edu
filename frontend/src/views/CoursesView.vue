<template>
  <div class="sparse-page page-courses">
<h1 class="sr-only">课程中心</h1>

    <div class="page-scroll">
    <div class="course-layout">
      <aside class="filter-rail glass" aria-label="课程分类" data-tour="courses">
        <ModelShowcase kind="book" label="立体课程书册" />
        <button
          v-for="item in filters"
          :key="item.id"
          type="button"
          :class="{ active: filter === item.id }"
          @click="filter = item.id"
        >{{ item.label }}</button>
      </aside>

      <div class="course-main">
        <p v-if="query && !loading" class="course-search-status" role="status">搜索“{{ query }}” · {{ filtered.length }} 个结果</p>
        <p v-if="loading" class="course-search-feedback" role="status">正在加载课程…</p>
        <div v-else-if="courseError" class="course-search-feedback" role="alert">
          <span>{{ courseError }}</span>
          <button type="button" class="text-action" @click="loadCourses">重新加载课程</button>
        </div>
        <div v-else-if="!filtered.length" class="course-search-feedback" role="status">
          <span>{{ query ? `没有找到“${query}”相关课程，请换个关键词。` : '当前分类暂无课程。' }}</span>
          <button v-if="query" type="button" class="text-action" @click="clearSearch">清除搜索</button>
        </div>

        <div v-if="filtered.length" class="featured-row">
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

        <ul v-if="filtered.length" class="course-strip">
          <li v-for="course in rest" :key="course.id" class="glare-row course-tile glass">
            <div>
              <strong>{{ course.title }}</strong>
              <span>{{ course.stage || course.category }}</span>
            </div>
            <button type="button" @click="start(course)">进入</button>
          </li>
        </ul>

        <section class="mooc-extend" aria-label="慕课延伸">
          <header class="mooc-extend__head">
            <div>

              <h2>慕课延伸</h2>
            </div>
            <p>外链需平台账号 · 开课学期可能变化 · 非正式国标</p>
          </header>
          <div class="mooc-extend__grid">
            <a
              v-for="item in featuredMoocs"
              :key="item.id"
              class="mooc-card glass"
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
            >
              <em>{{ item.platform }}</em>
              <strong>{{ item.title }}</strong>
              <p>{{ item.summary }}</p>
              <span>{{ item.tags.join(' · ') }}</span>
            </a>
          </div>
        </section>
      </div>
    </div>
    </div>

    <aside v-if="detail" class="detail-drawer glass" role="dialog">
      <button type="button" class="close-x" aria-label="关闭" @click="detail = null">×</button>
      <p>{{ detail.stage || detail.category }}</p>
      <h2>{{ detail.title }}</h2>
      <p>{{ detail.description }}</p>
      <p v-if="detail.source || moocForCourse(detail)" class="course-source">
        <span v-if="detail.source">来源：{{ detail.source }}</span>
        <a
          v-if="detail.source_url"
          :href="detail.source_url"
          target="_blank"
          rel="noopener noreferrer"
        >查看出处</a>
        <a
          v-if="moocForCourse(detail)"
          :href="moocForCourse(detail).url"
          target="_blank"
          rel="noopener noreferrer"
        >{{ moocForCourse(detail).label }}</a>
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
import ModelShowcase from '../components/fx/ModelShowcase.vue'
import SpotlightPane from '../components/fx/SpotlightPane.vue'
import { featuredMoocs, moocForCourse } from '../data/moocCourses'
import { fetchCourses } from '../services/dashboard'
import { filterCourses, normalizeSearchQuery } from '../utils/navigation'

const route = useRoute()
const router = useRouter()
const courses = ref([])
const filter = ref('all')
const detail = ref(null)
const loading = ref(true)
const courseError = ref('')
const query = computed(() => normalizeSearchQuery(route.query.q))

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
  return filterCourses(courses.value, query.value, filter.value)
})

const featured = computed(() => {
  const sorted = [...filtered.value].sort((a, b) => Number(b.status === 'in_progress') - Number(a.status === 'in_progress'))
  return sorted.slice(0, 3)
})

const rest = computed(() => {
  const ids = new Set(featured.value.map((item) => item.id))
  return filtered.value.filter((item) => !ids.has(item.id))
})

function start(course) {
  router.push({ path: '/training', query: { courseId: course.id } })
}

function open(course) {
  detail.value = course
}

function clearSearch() {
  router.replace({ path: '/courses' })
}

async function loadCourses() {
  loading.value = true
  courseError.value = ''
  detail.value = null
  try {
    courses.value = await fetchCourses()
  } catch (error) {
    courses.value = []
    courseError.value = error?.response?.data?.message || '课程加载失败，请检查服务后重试。'
  } finally {
    loading.value = false
  }
}

watch(() => route.query.q, () => {
  if (query.value) filter.value = 'all'
})

onMounted(loadCourses)
</script>
