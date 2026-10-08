// Keep rotation gestures separate from the click that selects a student or opens an object.
export function createModelDrag(rotate) {
  let drag = null, suppressUntil = 0
  return {
    down(event, element, key = '') {
      if (event.button !== 0 || !event.isPrimary) return
      drag = { id: event.pointerId, x: event.clientX, last: event.clientX, y: event.clientY, element, key, moved: false }
    },
    move(event) {
      if (!drag || event.pointerId !== drag.id) return false
      if (!drag.moved && Math.abs(event.clientY - drag.y) > Math.abs(event.clientX - drag.x) + 6) { drag = null; return false }
      if (!drag.moved && Math.abs(event.clientX - drag.x) < 6) return false
      drag.moved = true
      if (!drag.element.hasPointerCapture?.(drag.id)) drag.element.setPointerCapture?.(drag.id)
      rotate(drag.key, (event.clientX - drag.last) / Math.max(80, drag.element.clientWidth) * Math.PI)
      drag.last = event.clientX
      return true
    },
    end(event) {
      if (!drag || event.pointerId !== drag.id) return
      const ended = drag; drag = null
      if (ended.moved) suppressUntil = performance.now() + 350
      if (ended.element.hasPointerCapture?.(ended.id)) ended.element.releasePointerCapture(ended.id)
    },
    suppress(event) {
      if (event.detail > 0 && performance.now() < suppressUntil) { event.preventDefault(); event.stopPropagation(); return true }
      return false
    },
    cancel() { if (drag) this.end({ pointerId: drag.id }) },
  }
}
