import { api } from './api'

export async function fetchRagStatus() {
  const { data } = await api.get('/rag/status')
  return data
}

export async function listRagDocuments(params = {}) {
  const { data } = await api.get('/rag/documents', { params })
  return data
}

export async function listRagChunks(documentId, params = {}) {
  const { data } = await api.get(`/rag/documents/${documentId}/chunks`, { params })
  return data
}

export async function uploadRagDocument(file, fields = {}, { asyncJob = true } = {}) {
  const form = new FormData()
  form.append('file', file)
  Object.entries(fields).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    form.append(key, Array.isArray(value) ? value.join(',') : String(value))
  })
  form.append('async', asyncJob ? '1' : '0')
  const { data, status } = await api.post('/rag/documents', form)
  return { data, status }
}

export async function fetchRagChunk(chunkId) {
  const { data } = await api.get(`/rag/chunks/${chunkId}`)
  return data
}

export async function trialRetrieve(body) {
  const { data } = await api.post('/rag/retrieve', body)
  return data
}

export async function deleteRagDocument(id) {
  const { data } = await api.delete(`/rag/documents/${id}`)
  return data
}

export async function patchRagDocument(id, body) {
  const { data } = await api.patch(`/rag/documents/${id}`, body)
  return data
}
