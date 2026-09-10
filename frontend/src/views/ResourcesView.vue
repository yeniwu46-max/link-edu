<template>
  <div class="sparse-page">
    <header class="page-head growth-head">
      <div>
        <p class="shiny-kicker">LIBRARY</p>
        <SplitTitle text="资源库" />
        <p class="page-lead">按教案、素材、报告、档案分类，对照师范技能训练使用。</p>
      </div>
    </header>

    <div class="resource-tabs">
      <button
        v-for="item in tabs"
        :key="item"
        type="button"
        :class="{ active: tab === item }"
        @click="tab = item"
      >{{ item }}</button>
    </div>

    <p v-if="loading" class="course-search-feedback" role="status">正在加载资源…</p>
    <div v-else-if="resourceError" class="course-search-feedback" role="alert">
      <span>{{ resourceError }}</span>
      <button type="button" class="text-action" @click="loadResources">重新加载资源</button>
    </div>
    <p v-else-if="!visible.length" class="course-search-feedback" role="status">当前分类暂无资源。</p>

    <ul v-else class="resource-list">
      <li v-for="item in visible" :key="item.id" class="glare-row">
        <div>
          <em>{{ item.category }}</em>
          <strong>{{ item.title }}</strong>
          <span>{{ item.description }}</span>
        </div>
        <button type="button" @click="detail = item">查看详情</button>
      </li>
    </ul>

    <aside v-if="detail" class="detail-drawer" role="dialog" aria-label="资源详情">
      <button type="button" class="close-x" aria-label="关闭" @click="detail = null">×</button>
      <p>{{ detail.category }}</p>
      <h2>{{ detail.title }}</h2>
      <p>{{ detail.description || '暂无详细说明。' }}</p>
      <p v-if="resourceUrl(detail) === ''" class="review-alert" role="status">
        当前资源没有可用文件链接，不能伪装成已打开或已下载。
      </p>
      <p v-else-if="linkError(detail)" class="review-alert" role="alert">
        当前资源链接无效，请联系管理员更新资源地址。
      </p>
      <div v-else class="resource-actions">
        <button class="primary" type="button" @click="open(detail)">打开链接</button>
        <button type="button" @click="download(detail)">下载文件</button>
        <a v-if="isExternal(detail)" :href="resourceUrl(detail)" target="_blank" rel="noopener noreferrer">打开外部链接</a>
      </div>
    </aside>
    <div v-if="detail" class="help-mask" @click="detail = null"></div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import SplitTitle from '../components/fx/SplitTitle.vue'
import { fetchResources } from '../services/dashboard'

const message = useMessage()
const items = ref([])
const tab = ref('全部')
const detail = ref(null)
const loading = ref(true)
const resourceError = ref('')
const tabs = ['全部', '教案', '素材', '报告', '档案']

const visible = computed(() => {
  if (tab.value === '全部') return items.value
  return items.value.filter((item) => item.category === tab.value)
})

function resourceUrl(item) {
  const raw = String(item?.file_url || '').trim()
  if (!raw) return ''
  try {
    const url = new URL(raw, window.location.origin)
    if (!['http:', 'https:'].includes(url.protocol)) return null
    return url.href
  } catch {
    return null
  }
}

function linkError(item) {
  return resourceUrl(item) === null
}

function isExternal(item) {
  const url = resourceUrl(item)
  return Boolean(url && new URL(url).origin !== window.location.origin)
}

function open(item) {
  const url = resourceUrl(item)
  if (!url) {
    message.error(url === '' ? `${item.title}：当前没有可用文件链接。` : `${item.title}：文件链接无效。`)
    return
  }
  const popup = window.open(url, '_blank', 'noopener,noreferrer')
  if (!popup) message.error('浏览器阻止了打开资源，请允许弹出窗口后重试。')
}

function download(item) {
  const url = resourceUrl(item)
  if (!url) {
    message.error(url === '' ? `${item.title}：当前没有可用文件链接。` : `${item.title}：文件链接无效。`)
    return
  }
  if (isExternal(item)) {
    open(item)
    return
  }
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = ''
  anchor.rel = 'noopener noreferrer'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  message.info(`${item.title}：已发起下载。`)
}

async function loadResources() {
  loading.value = true
  resourceError.value = ''
  detail.value = null
  try {
    items.value = await fetchResources()
  } catch (error) {
    items.value = []
    resourceError.value = error?.response?.data?.message || '资源加载失败，请检查服务后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(loadResources)
</script>
