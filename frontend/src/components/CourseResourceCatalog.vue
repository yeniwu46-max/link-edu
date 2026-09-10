<script setup>
import { computed, onMounted, ref } from 'vue'
import ClassroomDialog from './ClassroomDialog.vue'
import { fetchResources } from '../services/dashboard'
import { resolveResourceLink } from '../utils/resourceLinks.js'

const items = ref([])
const tab = ref('全部')
const detail = ref(null)
const loading = ref(true)
const resourceError = ref('')
const tabs = ['全部', '教案', '素材', '报告', '档案']
const visible = computed(() => tab.value === '全部' ? items.value : items.value.filter(item => item.category === tab.value))
const link = computed(() => resolveResourceLink(detail.value?.file_url, window.location.origin))
const detailOpen = computed({ get: () => Boolean(detail.value), set: value => { if (!value) detail.value = null } })

async function loadResources() {
  loading.value = true
  resourceError.value = ''
  detail.value = null
  try {
    items.value = await fetchResources()
  } catch (error) {
    items.value = []
    resourceError.value = error?.response?.data?.message || '资源加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}
onMounted(loadResources)
</script>

<template>
  <section class="course-resource-catalog" aria-label="课程资源">
    <div class="resource-tabs" aria-label="资源分类">
      <button v-for="item in tabs" :key="item" type="button" :aria-pressed="tab === item" :class="{ active: tab === item }" @click="tab = item">{{ item }}</button>
    </div>
    <p v-if="loading" class="course-search-feedback" role="status">正在加载资源…</p>
    <div v-else-if="resourceError" class="course-search-feedback" role="alert">
      <span>{{ resourceError }}</span>
      <button type="button" class="text-action" @click="loadResources">重新加载资源</button>
    </div>
    <p v-else-if="!visible.length" class="course-search-feedback" role="status">当前分类暂无资源。</p>
    <ul v-else class="resource-list">
      <li v-for="item in visible" :key="item.id" class="glare-row">
        <div><em>{{ item.category }}</em><strong>{{ item.title }}</strong><span>{{ item.description }}</span></div>
        <button type="button" @click="detail = item">查看详情</button>
      </li>
    </ul>
    <ClassroomDialog v-model="detailOpen" title="资源详情">
      <template v-if="detail">
        <p>{{ detail.category }}</p>
        <h2>{{ detail.title }}</h2>
        <p>{{ detail.description || '暂无详细说明。' }}</p>
        <p v-if="link.status === 'missing'" role="status">当前资源没有可用文件链接。</p>
        <p v-else-if="link.status === 'invalid'" role="alert">文件链接无效，请联系管理员更新。</p>
        <div v-else class="resource-actions">
          <a :href="link.url" target="_blank" rel="noopener noreferrer">{{ link.external ? '访问来源网站' : '打开文件' }}</a>
          <a v-if="!link.external" :href="link.url" download>下载文件</a>
        </div>
      </template>
    </ClassroomDialog>
  </section>
</template>

<style scoped>
.course-resource-catalog { min-width:0; }
.resource-tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:18px; }
.resource-tabs button { padding:8px 18px; border:1px solid var(--line); border-radius:99px; }
.resource-tabs button.active { color:#ffd1ad; background:#ff7a181a; border-color:#ff974859; }
.resource-actions { display:flex; gap:16px; margin-top:20px; }
.resource-actions a { color:#ffd1ad; padding:10px 16px; border:1px solid #ff974859; border-radius:10px; }
.resource-list li>div { min-width:0; overflow-wrap:anywhere; }
</style>
