// Presentation-only transcript. Drafts never become classroom evidence.
const names = { ming: '小明', yu: '小雨', lin: '小林' };
const terminal = new Set(['done', 'interrupted', 'failed', 'disconnected', 'paused', 'ended']);

export function createConversation() {
  let rows = [], teacher = null, generation = null, activeKey = null, serial = 0;
  const seen = new Set();
  const snapshot = () => rows.map(row => ({ ...row }));
  const append = (role, at, extra = {}) => {
    const row = { key: `draft-${++serial}`, role, at, text: '', status: 'thinking', ...extra };
    rows.push(row);
    return row;
  };
  const active = () => rows.find(row => row.key === activeKey);
  function settle(status) {
    for (const row of [teacher, active()]) {
      if (row && !terminal.has(row.status)) row.status = status;
    }
    teacher = null;
    generation = null;
    activeKey = null;
  }
  function event(e) {
    if (!e || seen.has(e.id)) return;
    seen.add(e.id);
    if (!['transcript', 'student'].includes(e.type)) return;
    const d = e.data || {};
    const candidate = active();
    // The server emits the student event before its reply notification.
    let row = e.type === 'transcript' ? teacher :
      rows.find(r => d.reply_id && r.replyId === d.reply_id) ||
      rows.find(r => d.generation_id && r.generationId === d.generation_id) ||
      (!d.generation_id && candidate && !candidate.eventId && !terminal.has(candidate.status) && candidate.studentId === d.student_id ? candidate : null);
    if (!row) row = append(e.type === 'transcript' ? 'teacher' : 'student', e.at_ms);
    Object.assign(row, { eventId: e.id, at: e.at_ms, text: d.text || '',
      studentId: d.student_id, name: d.name, replyId: d.reply_id,
      generationId: d.generation_id ?? row.generationId,
      trigger: d.trigger, interactionKind: d.interaction_kind,
      status: e.type === 'transcript' ? 'done' : row.status === 'speaking' ? 'speaking' : 'ready' });
    if (e.type === 'transcript') teacher = null;
  }
  return {
    snapshot,
    restore(events, preserve = false) {
      if (!preserve) { rows = []; seen.clear(); teacher = null; generation = null; activeKey = null; }
      for (const e of events || []) event(e);
      // A restored student event is saved text, not an active playback.
      for (const row of rows) if (row.eventId && row.status === 'ready') row.status = 'done';
      rows.sort((a, b) => a.at - b.at);
      return snapshot();
    },
    receive(m, at = 0) {
      if (m.type === 'event') event(m.event);
      if (m.type === 'partial') {
        if (m.text) {
          teacher ||= append('teacher', at, { status: 'transcribing' });
          teacher.text = m.text;
        } else if (teacher) {
          // Explicit empty ASR revisions withdraw the provisional result.
          rows = rows.filter(row => row !== teacher); teacher = null;
        }
      }
      if (m.type === 'generation_started') {
        const previous = active();
        if (previous && previous.generationId !== m.generation_id && !terminal.has(previous.status)) previous.status = 'interrupted';
        generation = m.generation_id;
        const next = rows.find(row => row.generationId === generation) || append('student', at, { generationId: generation, studentId: m.student_id });
        activeKey = next.key;
      }
      let row = active();
      const matches = row && generation != null && m.generation_id === generation;
      if (matches && m.type === 'generation_student') row.studentId = m.student_id;
      if (matches && m.type === 'reply_delta' && !row.eventId && !terminal.has(row.status) && row.studentId === m.student_id) {
        row.text += m.delta;
        row.status = 'generating';
      }
      if (matches && m.type === 'generation_completed') Object.assign(row, {
        text: m.text, studentId: m.student_id, status: m.action === 'raise' ? 'waiting' : 'ready',
      });
      if (m.type === 'reply') {
        row = rows.find(r => r.generationId === m.generation_id && m.generation_id != null) ||
          rows.find(r => r.replyId === m.reply_id);
        const saved = rows.find(r => r.replyId === m.reply_id && r !== row);
        if (row && saved) {
          Object.assign(row, { eventId: saved.eventId, at: saved.at, name: saved.name, trigger: saved.trigger, interactionKind: saved.interactionKind });
          rows = rows.filter(r => r !== saved);
        }
        if (!row) row = append('student', at);
        Object.assign(row, { generationId: m.generation_id, replyId: m.reply_id,
          text: m.text, studentId: m.student_id, status: 'speaking' });
        generation = m.generation_id;
        activeKey = row.key;
      }
      if (matches && m.type === 'generation_failed') Object.assign(row, { status: 'failed', error: m.message });
      if (matches && m.type === 'generation_cancelled') {
        if (!terminal.has(row.status)) row.status = 'interrupted';
        generation = null;
        activeKey = null;
      }
      if (m.type === 'cancel') {
        const cancelled = m.reply_id ? rows.find(r => r.replyId === m.reply_id) : active();
        if (cancelled && !terminal.has(cancelled.status)) cancelled.status = 'interrupted';
        generation = null;
        activeKey = null;
      }
      if (m.type === 'listening' && row && !terminal.has(row.status)) row.status = 'done';
      if (['paused', 'disconnected', 'ended'].includes(m.type)) settle(m.type);
      return snapshot();
    },
  };
}

export const conversationName = row => row.role === 'teacher' ? '老师' : row.name || names[row.studentId] || '学生';
export const conversationStatus = row => ({
  transcribing: '正在转写', thinking: '正在思考', generating: '正在生成', waiting: '举手待回应',
  ready: '等待播放', speaking: '正在发言', interrupted: '已打断', failed: '生成失败',
  disconnected: '连接中断', paused: '已暂停', ended: '课堂已结束',
})[row.status] || '';
