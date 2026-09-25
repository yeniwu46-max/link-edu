<template>
  <div class="page-rag">
    <section class="glass rag-hero">
      <h1>知识库</h1>
      <p v-if="status">
        已索引 {{ status.indexed_chunks }} 条切片 · 混合检索
        {{ status.hybrid_enabled ? '开' : '关' }} · 精排 {{ status.rerank_enabled ? '开' : '关' }}
      </p>
      <p v-else-if="loadError" class="rag-error">{{ loadError }}</p>
    </section>

    <div class="rag-columns" v-if="canManage">
      <section class="glass rag-panel">
        <h2>上传资料</h2>
        <form class="rag-form" @submit.prevent="onUpload">
          <label>
            文件
            <input type="file" accept=".pdf,.docx,.txt,.md" @change="onFile" />
          </label>
          <label>
            标题
            <input v-model="upload.title" type="text" placeholder="可选" />
          </label>
          <label>
            分类
            <select v-model="upload.category">
              <option v-for="(label, key) in categories" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
          <label>
            失效日
            <input v-model="upload.valid_until" type="date" />
          </label>
          <label>
            授权说明
            <input v-model="upload.license_note" type="text" placeholder="校内使用 / 公开许可等" />
          </label>
          <button type="submit" :disabled="!upload.file || uploading">
            {{ uploading ? '上传中…' : '异步入库' }}
          </button>
          <p v-if="uploadMessage" class="rag-hint">{{ uploadMessage }}</p>
        </form>
      </section>

      <section class="glass rag-panel">
        <h2>试检索</h2>
        <form class="rag-form" @submit.prevent="onRetrieve">
          <label>
            问句
            <textarea v-model="trialQuery" rows="3" placeholder="例如：提问后应留多少候答时间？" />
          </label>
          <button type="submit" :disabled="!trialQuery.trim() || retrieving">检索</button>
        </form>
        <ul v-if="trialHits.length" class="rag-hits">
          <li v-for="hit in trialHits" :key="hit.chunk_id">
            <strong>{{ hit.document?.title }}</strong>
            <span>{{ hit.section }} · {{ hit.similarity }}</span>
            <p>{{ hit.text.slice(0, 180) }}…</p>
          </li>
        </ul>
      </section>
    </div>

    <section class="glass rag-panel">
      <h2>资料列表</h2>
      <table class="rag-table" v-if="documents.length">
        <thead>
          <tr>
            <th>标题</th>
            <th>分类</th>
            <th>状态</th>
            <th>切片</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="doc in documents" :key="doc.id">
            <td>{{ doc.title }}</td>
            <td>{{ doc.category_label }}</td>
            <td>{{ doc.status }}</td>
            <td>{{ doc.chunk_count }}</td>
            <td>
              <button type="button" @click="preview(doc)">切片</button>
              <button v-if="canManage" type="button" class="danger" @click="remove(doc)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="rag-hint">暂无资料{{ canManage ? '，请上传' : '' }}。</p>
    </section>

    <dialog ref="chunkDialog" class="rag-dialog">
      <header>
        <h3>{{ previewDoc?.title }}</h3>
        <button type="button" @click="closePreview">关闭</button>
      </header>
      <ul v-if="previewChunks.length">
        <li v-for="chunk in previewChunks" :key="chunk.id">
          <small>#{{ chunk.ordinal }} {{ chunk.section }}</small>
          <p>{{ chunk.text }}</p>
          <pre v-if="chunk.extra?.parent_summary">{{ chunk.extra.parent_summary }}</pre>
        </li>
      </ul>
    </dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  deleteRagDocument,
  fetchRagStatus,
  listRagChunks,
  listRagDocuments,
  trialRetrieve,
  uploadRagDocument,
} from '../services/rag'

const status = ref(null)
const categories = ref({})
const canManage = ref(false)
const documents = ref([])
const loadError = ref('')
const upload = ref({ file: null, title: '', category: 'other', valid_until: '', license_note: '' })
const uploading = ref(false)
const uploadMessage = ref('')
const trialQuery = ref('')
const trialHits = ref([])
const retrieving = ref(false)
const previewDoc = ref(null)
const previewChunks = ref([])
const chunkDialog = ref(null)

async function refresh() {
  try {
    const data = await fetchRagStatus()
    status.value = data
    categories.value = data.categories || {}
    canManage.value = Boolean(data.can_manage)
  } catch (error) {
    loadError.value = error.response?.data?.message || '无法加载知识库状态'
  }
  try {
    const list = await listRagDocuments({ page_size: 50 })
    documents.value = list.items || []
  } catch {
    /* 只读用户可能仅有检索权限时仍展示试检索 */
  }
}

function onFile(event) {
  upload.value.file = event.target.files?.[0] || null
}

async function onUpload() {
  if (!upload.value.file) return
  uploading.value = true
  uploadMessage.value = ''
  try {
    const { data, status: code } = await uploadRagDocument(upload.value.file, {
      title: upload.value.title,
      category: upload.value.category,
      valid_until: upload.value.valid_until,
      license_note: upload.value.license_note,
    })
    uploadMessage.value = data.message || (code === 202 ? '已排队' : '已入库')
    await refresh()
  } catch (error) {
    uploadMessage.value = error.response?.data?.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function onRetrieve() {
  retrieving.value = true
  trialHits.value = []
  try {
    const data = await trialRetrieve({ query: trialQuery.value.trim(), top_k: 5 })
    trialHits.value = data.hits || []
  } catch (error) {
    loadError.value = error.response?.data?.message || '检索失败'
  } finally {
    retrieving.value = false
  }
}

async function preview(doc) {
  previewDoc.value = doc
  const data = await listRagChunks(doc.id, { limit: 30 })
  previewChunks.value = data.items || []
  chunkDialog.value?.showModal()
}

function closePreview() {
  chunkDialog.value?.close()
}

async function remove(doc) {
  if (!window.confirm(`删除「${doc.title}」？`)) return
  await deleteRagDocument(doc.id)
  await refresh()
}

onMounted(refresh)
</script>

<style scoped>
.page-rag {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.5rem 0 2rem;
}
.rag-hero h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}
.rag-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
}
.rag-panel {
  padding: 1.25rem;
}
.rag-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.rag-form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
}
.rag-form input,
.rag-form select,
.rag-form textarea {
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(0, 0, 0, 0.2);
  color: inherit;
}
.rag-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.rag-table th,
.rag-table td {
  padding: 0.5rem;
  text-align: left;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.rag-hits {
  list-style: none;
  padding: 0;
  margin: 1rem 0 0;
}
.rag-hits li {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.rag-hint,
.rag-error {
  font-size: 0.85rem;
  opacity: 0.85;
}
.rag-dialog {
  max-width: 640px;
  width: 90%;
  border: none;
  border-radius: 12px;
  padding: 1rem;
  background: #1a1f2e;
  color: #e8ecf4;
}
.rag-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
button.danger {
  color: #f87171;
}
</style>
