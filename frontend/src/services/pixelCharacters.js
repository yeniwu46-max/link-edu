export const PIXEL_CHARACTERS = ['ming', 'yu', 'lin', 'assistant']
export const PIXEL_BASE = '/assets/characters/pixel/'
export const STUDENT_ACTIONS = ['listening', 'blink', 'reading', 'writing', 'thinking', 'raised', 'answering', 'speaking', 'nod', 'confused', 'happy', 'turn']
export const ASSISTANT_ACTIONS = ['idle', 'blink', 'listening', 'thinking', 'wave', 'presenting', 'answering', 'speaking', 'nod', 'confused', 'happy', 'turn']

export function pixelSource(id) {
  return `${PIXEL_BASE}${PIXEL_CHARACTERS.includes(id) ? id : 'lin'}.png`
}
export function frameRect(image, index) {
  const width = (image.naturalWidth || image.width) / 4
  const height = (image.naturalHeight || image.height) / 3
  return { x: (index % 4) * width, y: Math.floor(index / 4) * height, width, height }
}
export function studentPixelFrame(motion = {}, { now = 0, offset = 0, acknowledged = false, completed = false, turn = 0, reduced = false } = {}) {
  // Only actual audio opens the mouth. Generating text is a thinking pose.
  if (motion.speaking) return motion.level > .08 ? 7 : 6
  if (acknowledged) return 8
  if (motion.raised) return 5
  if (motion.thinking) return 4
  if (motion.failed || motion.confused) return 9
  if (completed) return 10
  if (Math.abs(turn) > .12) return 11
  if (reduced) return 0
  const t = (now + offset) % 24000
  if (t > 8000 && t < 11200) return 2
  if (t > 16000 && t < 19200) return 3
  return (now + offset) % 4300 < 150 ? 1 : 0
}
export function assistantPixelFrame(state, level, { now = 0, reduced = false, pointer = 0 } = {}) {
  if (state === 'speaking') return level > .08 ? 7 : 6
  if (state === 'thinking' || state === 'connecting') return 3
  if (state === 'listening') return 2
  if (state === 'error') return 9
  if (state === 'wave') return 4
  if (state === 'happy') return 10
  if (state === 'presenting') return 5
  if (state === 'nod') return 8
  if (Math.abs(pointer) > .5) return 11
  if (reduced) return 0
  if (now < 1600) return 4
  return now % 4300 < 150 ? 1 : 0
}
