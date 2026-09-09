const DRAFT_PREFIX = 'link_ai_review_draft_'
const DRAFT_RETENTION_MS = 30 * 24 * 60 * 60 * 1000

function draftKey(sessionId) {
  return `${DRAFT_PREFIX}${sessionId}`
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
