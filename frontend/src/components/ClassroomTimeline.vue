<script setup>
import { computed, nextTick, ref } from "vue";
import {
  isTechnicalEvent,
  eventLabel,
  eventText,
} from "../services/classroomStatus.js";
const props = defineProps({ events: Array });
const showTechnical = ref(false);
const technicalCount = computed(
  () => props.events.filter(isTechnicalEvent).length,
);
const visibleEvents = computed(() =>
  props.events.filter(
    (event) => showTechnical.value || !isTechnicalEvent(event),
  ),
);
const time = (ms) =>
  `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;
async function reveal(id) {
  const event = props.events.find((event) => event.id === id);
  if (!event) return;
  if (isTechnicalEvent(event)) showTechnical.value = true;
  await nextTick();
  const target = document.getElementById(`evidence-${id}`);
  target?.focus({ preventScroll: true });
  target?.scrollIntoView({
    behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "instant"
      : "smooth",
    block: "center",
  });
}
defineExpose({ reveal });
</script>

<template>
  <section class="class-panel timeline-panel">
    <div class="section-title">
      <h2>课堂记录</h2>
      <button
        v-if="technicalCount"
        type="button"
        class="text-action"
        :aria-expanded="showTechnical"
        aria-controls="classroom-events"
        @click="showTechnical = !showTechnical"
      >
        {{ showTechnical ? "收起技术记录" : `技术记录 (${technicalCount})` }}
      </button>
    </div>
    <ol id="classroom-events">
      <li
        v-for="event in visibleEvents"
        :key="event.id"
        :id="`evidence-${event.id}`"
        tabindex="-1"
      >
        <time>{{ time(event.at_ms) }}</time>
        <div>
          <span class="event-label">{{ eventLabel(event) }}</span>
          <p>{{ eventText(event) }}</p>
        </div>
      </li>
    </ol>
    <p v-if="!visibleEvents.length" class="subtle-note">暂无课堂内容</p>
  </section>
</template>
