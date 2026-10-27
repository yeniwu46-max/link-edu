import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue';

export function clampCameraPosition(position, bounds, size) {
  return { x: Math.max(0, Math.min(position.x, Math.max(0, bounds.width - size.width))),
    y: Math.max(0, Math.min(position.y, Math.max(0, bounds.height - size.height))) };
}

// Position belongs to this mounted classroom, not the media stream or persisted preferences.
export function useCameraWindow(workspace, frame, enabled) {
  const position = ref({ x: 0, y: 0 });
  let observer, drag = null, placed = false, mobile = window.innerWidth <= 700;
  function dimensions() {
    const area = workspace.value, camera = frame.value;
    if (!area || !camera) return null;
    const bounds = area.getBoundingClientRect();
    // On short screens constrain the window to the visible part of the workspace.
    return { bounds: { width: bounds.width, height: Math.min(bounds.height, Math.max(0, window.innerHeight - Math.max(0, bounds.top))) },
      size: { width: camera.offsetWidth, height: camera.offsetHeight } };
  }
  function move(point) {
    const d = dimensions();
    if (d) position.value = clampCameraPosition(point, d.bounds, d.size);
  }
  function reset() {
    const d = dimensions();
    if (!d) return;
    const chat = workspace.value?.querySelector('.classroom-conversation')?.getBoundingClientRect();
    const mobile = window.innerWidth <= 700;
    const top = mobile && chat ? chat.top - workspace.value.getBoundingClientRect().top + 52 : 64;
    move({ x: (mobile ? d.bounds.width : chat?.width || d.bounds.width / 2) - d.size.width - 12, y: top });
    placed = true;
  }
  function constrain() {
    const changed = mobile !== (window.innerWidth <= 700);
    mobile = window.innerWidth <= 700;
    if (enabled.value) placed && !changed ? move(position.value) : reset();
  }
  function end(e) {
    if (!drag || (e && drag.id !== e.pointerId)) return;
    const old = drag; drag = null;
    if (old.target.hasPointerCapture?.(old.id)) old.target.releasePointerCapture(old.id);
  }
  function down(e) {
    if (!enabled.value || !e.isPrimary || e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.focus();
    drag = { id: e.pointerId, target: e.currentTarget, x: e.clientX, y: e.clientY, start: { ...position.value } };
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function pointer(e) {
    if (!drag || drag.id !== e.pointerId) return;
    move({ x: drag.start.x + e.clientX - drag.x, y: drag.start.y + e.clientY - drag.y });
  }
  function keys(e) {
    const vectors = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (e.key === 'Home') { e.preventDefault(); e.stopPropagation(); reset(); }
    const vector = vectors[e.key];
    if (!vector) return;
    e.preventDefault(); e.stopPropagation();
    move({ x: position.value.x + vector[0] * (e.shiftKey ? 40 : 10), y: position.value.y + vector[1] * (e.shiftKey ? 40 : 10) });
  }
  watch(enabled, async () => { end(); await nextTick(); constrain(); });
  onMounted(() => {
    observer = new ResizeObserver(constrain);
    observer.observe(workspace.value); observer.observe(frame.value);
    window.addEventListener('resize', constrain);
    window.addEventListener('scroll', constrain, true);
    constrain();
  });
  onUnmounted(() => {
    end(); observer?.disconnect();
    window.removeEventListener('resize', constrain); window.removeEventListener('scroll', constrain, true);
  });
  return { position, reset, down, pointer, end, keys };
}
