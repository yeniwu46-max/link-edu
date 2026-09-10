<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  item: { type: Object, required: true },
  active: { type: Boolean, default: false },
});

const emit = defineEmits(["activate", "open"]);
const cardRef = ref(null);
const offset = ref({ x: 0, y: 0 });
const dragging = ref(false);
let gesture = null;
let suppressClick = false;

const cardStyle = computed(() => ({
  left: `${props.item.position.left}%`,
  top: `${props.item.position.top}px`,
  zIndex: props.active ? 30 : props.item.position.z,
  transform: `translate3d(${offset.value.x}px, ${offset.value.y}px, 0) rotate(${dragging.value ? 0 : props.item.position.rotate}deg)`,
}));

function pointerDown(event) {
  if (event.button !== 0) return;
  const card = cardRef.value;
  const board = card?.parentElement;
  if (!card || !board) return;
  const rect = card.getBoundingClientRect();
  const boardRect = board.getBoundingClientRect();
  card.setPointerCapture(event.pointerId);
  emit("activate", props.item.id);
  dragging.value = true;
  gesture = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originX: offset.value.x,
    originY: offset.value.y,
    minX: boardRect.left + 12 - rect.left,
    maxX: boardRect.right - 12 - rect.right,
    minY: boardRect.top + 12 - rect.top,
    maxY: boardRect.bottom - 12 - rect.bottom,
    moved: false,
  };
}

function pointerMove(event) {
  if (!gesture || gesture.pointerId !== event.pointerId) return;
  const dx = event.clientX - gesture.startX;
  const dy = event.clientY - gesture.startY;
  if (Math.hypot(dx, dy) > 5) gesture.moved = true;
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  offset.value = {
    x: gesture.originX + clamp(dx, gesture.minX, gesture.maxX),
    y: gesture.originY + clamp(dy, gesture.minY, gesture.maxY),
  };
}

function pointerUp(event) {
  if (!gesture || gesture.pointerId !== event.pointerId) return;
  suppressClick = gesture.moved;
  gesture = null;
  dragging.value = false;
  cardRef.value?.releasePointerCapture?.(event.pointerId);
  if (suppressClick) window.setTimeout(() => (suppressClick = false), 0);
}

function openCard(event) {
  if (suppressClick) {
    event.preventDefault();
    return;
  }
  emit("open", props.item);
}
</script>

<template>
  <button
    ref="cardRef"
    type="button"
    class="draggable-resource-card"
    :class="{
      'is-dragging': dragging,
      'is-recommended': item.recommended,
      [`cover-${item.cover}`]: item.cover,
    }"
    :style="cardStyle"
    :aria-label="`查看${item.title}`"
    @pointerdown="pointerDown"
    @pointermove="pointerMove"
    @pointerup="pointerUp"
    @pointercancel="pointerUp"
    @click="openCard"
    @dragstart.prevent
  >
    <span class="resource-cover" :class="`theme-${item.coverTheme}`">
      <span class="cover-art" aria-hidden="true">
        <i>{{ item.coverLabel }}</i>
        <b>{{ item.coverMark }}</b>
        <strong>{{ item.coverTitle }}</strong>
        <span>{{ item.source }} / {{ item.year }}</span>
      </span>
      <small v-if="item.recommended">推荐</small>
    </span>
    <span class="resource-card-copy">
      <em>{{ item.category }}</em>
      <strong>{{ item.title }}</strong>
      <span>{{ item.source }} · {{ item.stage }}</span>
      <span class="resource-card-foot">
        {{ item.format }}<b>{{ item.pages ? `${item.pages} 页` : "点击阅读" }}</b>
      </span>
    </span>
  </button>
</template>

<style scoped>
.draggable-resource-card {
  position: absolute;
  width: clamp(176px, 17vw, 204px);
  min-height: 258px;
  padding: 8px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 14px;
  background: #17121e;
  color: #f4f2f6;
  box-shadow: 0 18px 50px rgba(4, 2, 8, 0.44);
  text-align: left;
  touch-action: none;
  user-select: none;
  cursor: grab;
  transition:
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.2s,
    box-shadow 0.2s;
  will-change: transform;
}

.draggable-resource-card:hover,
.draggable-resource-card:focus-visible {
  border-color: rgba(255, 154, 66, 0.72);
  box-shadow: 0 24px 68px rgba(4, 2, 8, 0.58);
}

.draggable-resource-card.is-dragging {
  cursor: grabbing;
  transition: border-color 0.2s, box-shadow 0.2s;
  border-color: #ff9a42;
  box-shadow: 0 30px 84px rgba(4, 2, 8, 0.68);
}

.draggable-resource-card.is-recommended {
  border-color: rgba(255, 154, 66, 0.6);
}

.resource-cover {
  position: relative;
  display: grid;
  place-items: center;
  height: 136px;
  overflow: hidden;
  border-radius: 9px;
  background: #251a16;
}

.resource-cover::before,
.resource-cover::after {
  position: absolute;
  content: "";
  pointer-events: none;
}

.resource-cover::before {
  inset: 0;
  background:
    linear-gradient(115deg, transparent 0 48%, rgba(255, 255, 255, 0.1) 48.4% 49%, transparent 49.4%),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.045) 0 1px, transparent 1px 22px);
  opacity: 0.72;
}

.resource-cover::after {
  right: -24px;
  bottom: -32px;
  width: 112px;
  height: 112px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 50%;
  box-shadow: 0 0 0 18px rgba(255, 255, 255, 0.035);
}

.cover-art {
  position: relative;
  z-index: 1;
  display: grid;
  align-content: center;
  width: 100%;
  height: 100%;
  padding: 15px 16px;
  color: #fff;
}

.cover-art i {
  font-size: 9px;
  font-style: normal;
  letter-spacing: 0.14em;
  opacity: 0.72;
}

.cover-art b {
  position: absolute;
  top: 11px;
  right: 14px;
  color: rgba(255, 255, 255, 0.2);
  font-family: serif;
  font-size: 54px;
  font-weight: 700;
  line-height: 1;
}

.cover-art strong {
  max-width: 125px;
  margin-top: 25px;
  font-size: 15px;
  line-height: 1.35;
}

.cover-art span {
  margin-top: 10px;
  font-size: 8px;
  letter-spacing: 0.05em;
  opacity: 0.58;
}

.resource-cover.theme-orange {
  background: linear-gradient(145deg, #c94c13, #4a1d20 74%);
}

.resource-cover.theme-indigo {
  background: linear-gradient(145deg, #4354a8, #251a4c 74%);
}

.resource-cover.theme-rose {
  background: linear-gradient(145deg, #b84b6b, #4c183b 74%);
}

.resource-cover.theme-violet {
  background: linear-gradient(145deg, #7b3fa2, #301746 74%);
}

.resource-cover.theme-blue {
  background: linear-gradient(145deg, #237b99, #14324a 74%);
}

.resource-cover.theme-green {
  background: linear-gradient(145deg, #317d68, #173a36 74%);
}

.resource-cover.theme-amber {
  background: linear-gradient(145deg, #b7731e, #4b2b18 74%);
}

.resource-cover small {
  position: absolute;
  top: 9px;
  right: 9px;
  padding: 5px 8px;
  border-radius: 6px;
  background: #ff7a18;
  color: #211008;
  font-size: 10px;
  font-weight: 700;
}

.resource-card-copy {
  display: block;
  padding: 10px 4px 2px;
}

.resource-card-copy em {
  display: block;
  margin-bottom: 5px;
  color: #ffb67f;
  font-size: 10px;
  font-style: normal;
  letter-spacing: 0.12em;
}

.resource-card-copy strong {
  display: -webkit-box;
  min-height: 42px;
  overflow: hidden;
  font-size: 14px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.resource-card-copy > span:not(.resource-card-foot) {
  display: block;
  margin-top: 5px;
  color: #a9a1ae;
  font-size: 11px;
}

.resource-card-foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 9px;
  padding-top: 7px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: #8f8794;
  font-size: 10px;
}

.resource-card-foot b {
  color: #d8d1dc;
  font-weight: 500;
}

@media (prefers-reduced-motion: reduce) {
  .draggable-resource-card {
    transition: none;
  }
}

@media (max-width: 900px) {
  .draggable-resource-card {
    position: relative;
    inset: auto !important;
    width: 100%;
    min-height: 0;
    transform: none !important;
    will-change: auto;
    touch-action: manipulation;
  }
}
</style>
