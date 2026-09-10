const DRAFT_PREFIX = 'link_ai_review_draft_'
const MATERIAL_PREFIX = 'link_ai_review_materials_'
const DRAFT_RETENTION_MS = 30 * 24 * 60 * 60 * 1000
export const GENERATION_TIMEOUT_MS = 90 * 1000

function draftKey(sessionId) {
  return `${DRAFT_PREFIX}${sessionId}`
}

function materialKey(sessionId) {
  return `${MATERIAL_PREFIX}${sessionId}`
}

export function saveAiReviewDraft(storage, sessionId, text, now = Date.now()) {
  if (!storage || !sessionId) return
  const key = draftKey(sessionId)
  if (!text) {
    storage.removeItem(key)
    return
  }
  storage.setItem(key, JSON.stringify({
    text,
    saved_at: now,
    expires_at: now + DRAFT_RETENTION_MS,
  }))
}

export function loadAiReviewDraft(storage, sessionId, now = Date.now()) {
  if (!storage || !sessionId) return ''
  const key = draftKey(sessionId)
  const raw = storage.getItem(key)
  if (!raw) return ''
  try {
    const draft = JSON.parse(raw)
    if (!draft || typeof draft.text !== 'string' || Number(draft.expires_at) <= now) {
      storage.removeItem(key)
      return ''
    }
    return draft.text
  } catch {
    storage.removeItem(key)
    return ''
  }
}

export function saveAiReviewMaterials(storage, sessionId, materials, now = Date.now()) {
  if (!storage || !sessionId) return
  const transcript = String(materials?.transcript || '')
  const teacherNotes = String(materials?.teacherNotes || '')
  const key = materialKey(sessionId)
  if (!transcript && !teacherNotes) {
    storage.removeItem(key)
    return
  }
  storage.setItem(key, JSON.stringify({
    transcript,
    teacherNotes,
    saved_at: now,
    expires_at: now + DRAFT_RETENTION_MS,
  }))
}

export function loadAiReviewMaterials(storage, sessionId, now = Date.now()) {
  const empty = { transcript: '', teacherNotes: '' }
  if (!storage || !sessionId) return empty
  const key = materialKey(sessionId)
  const raw = storage.getItem(key)
  if (!raw) return empty
  try {
    const materials = JSON.parse(raw)
    if (!materials || Number(materials.expires_at) <= now) {
      storage.removeItem(key)
      return empty
    }
    return {
      transcript: typeof materials.transcript === 'string' ? materials.transcript : '',
      teacherNotes: typeof materials.teacherNotes === 'string' ? materials.teacherNotes : '',
    }
  } catch {
    storage.removeItem(key)
    return empty
  }
}

export function isGenerationTimedOut(report, now = Date.now()) {
  if (report?.generation_status !== 'generating') return false
  const rawStartedAt = String(report?.generation_started_at || '')
  const normalizedStartedAt = rawStartedAt && /(?:Z|[+-]\d{2}:?\d{2})$/i.test(rawStartedAt)
    ? rawStartedAt
    : `${rawStartedAt}Z`
  const startedAt = Date.parse(normalizedStartedAt)
  return Number.isFinite(startedAt) && now - startedAt > GENERATION_TIMEOUT_MS
}

export function selectFeedbackForRoute(items, feedbackId, sessionId) {
  const wantedFeedbackId = Number(feedbackId)
  const wantedSessionId = Number(sessionId)
  if (wantedFeedbackId) {
    const feedback = items.find((item) => item.id === wantedFeedbackId)
    if (feedback) return feedback
  }
  if (wantedSessionId) {
    const feedback = items.find((item) => item.session_id === wantedSessionId)
    if (feedback) return feedback
  }
  return wantedFeedbackId || wantedSessionId ? null : items[0] || null
}

export function isInsufficientReport(report) {
  if (report?.insufficient_evidence === true) return true
  const dimensions = report?.source === 'deepseek' ? report.dimensions : null
  if (!Array.isArray(dimensions) || !dimensions.length) return false
  return dimensions.every((item) => (
    Number(item?.score || 0) === 0
    || String(item?.evidence || '').includes('证据不足')
  ))
}
