import { computed, onMounted, onUnmounted, ref } from 'vue'
export function boundHelpPosition(position, viewport, size, margin = 12) {
  return { x: Math.max(margin, Math.min(position.x, Math.max(margin, viewport.width - size.width - margin))),
    y: Math.max(margin, Math.min(position.y, Math.max(margin, viewport.height - size.height - margin))) }
}
export function useHelpPosition(fab, panel) {
  const positions = ref({ fab: null, panel: null })
  let drag, pending, frame = 0, suppressUntil = 0
  const viewport = () => ({ width: window.innerWidth, height: window.innerHeight })
  const style = key => computed(() => positions.value[key] ? { left: `${positions.value[key].x}px`, top: `${positions.value[key].y}px`, right: 'auto', bottom: 'auto' } : {})
  const fabStyle = style('fab'), panelStyle = style('panel')
  function apply() {
    frame = 0
    if (!drag || !pending || !drag.moved) return
    positions.value[drag.kind] = boundHelpPosition({ x: drag.start.x + pending.x - drag.x, y: drag.start.y + pending.y - drag.y }, viewport(), drag.size)
  }
  function down(event, kind) {
    if (event.button !== 0 || (kind === 'panel' && event.target.closest('button,input,a,select,textarea'))) return
    const element = kind === 'fab' ? fab.value : panel.value
    if (!element) return
    const rect = element.getBoundingClientRect()
    drag = { kind, x: event.clientX, y: event.clientY, start: { x: rect.left, y: rect.top }, size: { width: rect.width, height: rect.height }, moved: false }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  function move(event) {
    if (!drag) return
    pending = { x: event.clientX, y: event.clientY }
    if (Math.abs(pending.x - drag.x) + Math.abs(pending.y - drag.y) > 4) drag.moved = true
    if (!frame) frame = requestAnimationFrame(apply)
  }
  function up() {
    cancelAnimationFrame(frame)
    if (drag?.moved) { apply(); if (drag.kind === 'fab') suppressUntil = performance.now() + 400 }
    drag = pending = null; cancelAnimationFrame(frame); frame = 0
  }
  function clampAll() {
    up()
    for (const [key, element] of [['fab', fab.value], ['panel', panel.value]]) {
      if (!positions.value[key] || !element) continue
      const rect = element.getBoundingClientRect()
      positions.value[key] = boundHelpPosition(positions.value[key], viewport(), { width: rect.width, height: rect.height })
    }
    if (window.innerWidth < 600) positions.value.panel = null
  }
  onMounted(() => {
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up); window.addEventListener('resize', clampAll)
  })
  onUnmounted(() => {
    up(); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
    window.removeEventListener('pointercancel', up); window.removeEventListener('resize', clampAll)
  })
  return { fabStyle, panelStyle, clampAll, onFabDown: event => down(event, 'fab'), onPanelDown: event => down(event, 'panel'),
    suppressClick: event => event.detail !== 0 && performance.now() < suppressUntil }
}
