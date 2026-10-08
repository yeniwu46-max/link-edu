export const STUDENT_MODELS = Object.freeze({
  ming: { file: 'character-male-a.glb', color: '#ba98eb' },
  yu: { file: 'character-female-b.glb', color: '#ffa26d' },
  lin: { file: 'character-male-e.glb', color: '#92b9e7' },
})

export function studentMotionState(id, { raised, playbackStudent, reply, level = 0 } = {}) {
  const speaking = playbackStudent === id
  const phase = reply?.studentId === id ? reply.phase : 'idle'
  return {
    raised: raised === id,
    speaking,
    thinking: ['thinking', 'generating', 'queued'].includes(phase),
    level: speaking ? Math.min(1, Math.max(0, Number(level) || 0)) : 0,
  }
}

export function studentRenderQuality(finePointer, slow = false) {
  return { fps: slow ? 20 : 30, pixelRatio: finePointer && !slow ? 1.25 : 1 }
}
