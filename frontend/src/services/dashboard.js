import { api } from './api'

export async function fetchDashboardOverview() {
  const { data } = await api.get('/dashboard/overview')
  return data
}

export async function fetchCourses() {
  const { data } = await api.get('/courses')
  return data.items
}

export async function fetchResources() {
  const { data } = await api.get('/resources')
  return data.items
}

export async function startTraining(courseId) {
  const { data } = await api.post('/training/sessions', { course_id: courseId })
  return data.session
}

export async function patchTraining(sessionId, payload) {
  const { data } = await api.patch(`/training/sessions/${sessionId}`, payload)
  return data.session
}

export async function completeTraining(sessionId, payload) {
  const { data } = await api.post(`/training/sessions/${sessionId}/complete`, payload)
  return data
}

export async function generateAiReview(sessionId, payload) {
  const { data } = await api.post(`/training/sessions/${sessionId}/ai-review`, payload, { skipBusy: true })
  return data.feedback
}

export async function uploadTrainingVisualEvidence(sessionId, frames) {
  const { data } = await api.post(`/training/sessions/${sessionId}/visual-evidence`, {
    frames,
  })
  return data
}

export async function askAiReviewQuestion(feedbackId, question) {
  const { data } = await api.post(
    `/feedbacks/${feedbackId}/ask`,
    { question },
    { skipBusy: true },
  )
  return data
}

export async function fetchFeedbacks() {
  const { data } = await api.get('/feedbacks')
  return data.items
}

export async function fetchGrowth(range = 'all') {
  const { data } = await api.get('/growth', { params: { range } })
  return data
}

export async function regenerateFeedback(feedbackId, notes) {
  const { data } = await api.post(`/feedbacks/${feedbackId}/regenerate`, { notes })
  return data.feedback
}

export async function fetchProfile() {
  const { data } = await api.get('/profile')
  return data
}

export async function saveProfile(payload) {
  const { data } = await api.patch('/profile', payload)
  return data
}

export async function addJournal(payload) {
  const { data } = await api.post('/journals', payload)
  return data.item
}
