<script setup>
defineProps({
  student: Object,
  raised: Boolean,
  speaking: Boolean,
  level: Number,
  understanding: String,
  reply: Object,
});
const colors = { ming: "#9a75ce", yu: "#cd815b", lin: "#7889ae" };
</script>

<template>
  <div class="student-interaction">
    <button
      type="button"
      class="student-card"
      :class="{ speaking, raised, thinking: reply?.phase === 'thinking' }"
      :aria-label="`${student.name}${raised ? '举手了，点击点名' : '，可用语音点名'}`"
      @click="$emit('select', student.id)"
    >
      <span class="student-status">{{
        speaking
          ? "正在发言"
          : reply?.phase === "thinking"
            ? "思考中…"
            : reply?.phase === "generating"
              ? "正在组织回答…"
              : raised
                ? "我有问题"
                : reply?.phase === "queued"
                  ? "等待播放"
                  : reply?.phase === "failed"
                    ? "回复暂不可用"
                    : "认真听讲"
      }}</span>
      <svg
        viewBox="0 0 200 180"
        aria-hidden="true"
        :style="{ '--shirt': colors[student.id] }"
      >
        <ellipse
          cx="100"
          cy="169"
          rx="72"
          ry="8"
          fill="#344567"
          opacity=".08"
        />
        <g class="student-body" :class="{ nod: speaking }">
          <path d="M49 154Q49 108 99 108Q151 108 151 154" fill="var(--shirt)" />
          <path d="M89 108L100 126L111 108" fill="#fff8f4" />
          <g class="student-arm">
            <path
              :d="
                raised ? 'M139 123L159 96L161 51' : 'M139 123L158 149L172 151'
              "
              fill="none"
              stroke="var(--shirt)"
              stroke-width="19"
              stroke-linecap="round"
            />
            <circle
              :cx="raised ? 161 : 172"
              :cy="raised ? 43 : 151"
              r="10"
              fill="#f6d0b7"
            />
          </g>
          <rect x="91" y="96" width="19" height="19" rx="7" fill="#edbea1" />
          <ellipse cx="100" cy="68" rx="39" ry="43" fill="#f6d0b7" />
          <path
            d="M62 67Q48 26 85 19Q132 8 141 49L140 72L128 44Q114 59 85 44L71 71Z"
            fill="#39465c"
          />
          <path
            v-if="student.id === 'yu'"
            d="M65 53Q36 34 44 80L63 73M135 48Q159 30 157 79L137 73"
            fill="#39465c"
          />
          <g class="student-eyes">
            <ellipse cx="85" cy="73" rx="3" ry="4" fill="#39465c" />
            <ellipse cx="115" cy="73" rx="3" ry="4" fill="#39465c" />
          </g>
          <g
            v-if="student.id === 'lin'"
            fill="none"
            stroke="#58667b"
            stroke-width="2"
          >
            <rect x="74" y="63" width="23" height="19" rx="7" />
            <rect x="103" y="63" width="23" height="19" rx="7" />
            <path d="M97 71h6" />
          </g>
          <path
            v-if="raised"
            d="M78 60l10 -3M109 57l11 4"
            fill="none"
            stroke="#39465c"
            stroke-width="2"
          />
          <ellipse
            cx="100"
            cy="91"
            :rx="speaking ? 5 + level * 3 : 5"
            :ry="speaking ? 2 + level * 9 : 1.8"
            fill="#9f5b60"
          />
        </g>
        <path d="M23 155H177V171H23Z" fill="#eadfcf" />
        <path d="M72 148l26 3 32-3v7H72Z" fill="#fff" />
      </svg>
      <strong>{{ student.name }}</strong>
      <small>{{
        { ming: "爱问为什么", yu: "在尝试理解", lin: "安静思考中" }[student.id]
      }}</small>
      <span v-if="understanding" class="student-memory">{{
        understanding
      }}</span>
    </button>
    <div
      v-if="reply && reply.phase !== 'idle'"
      class="student-bubble"
      :class="reply.phase"
    >
      <span v-if="reply.phase === 'thinking'"
        >思考中<span class="thinking-dots" aria-hidden="true">…</span></span
      >
      <span v-else-if="reply.phase === 'failed'">{{ reply.error }}</span>
      <template v-else
        ><small v-if="reply.phase === 'generating'">回复生成中</small>
        <p>{{ reply.text || "正在准备回答…" }}</p></template
      >
    </div>
    <span class="sr-only" role="status">{{
      reply?.phase === "thinking"
        ? `${student.name}正在思考`
        : reply?.phase === "queued"
          ? `${student.name}：${reply.text}`
          : ""
    }}</span>
  </div>
</template>

<style scoped>
.student-interaction {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.student-interaction .student-card {
  width: 100%;
}
.student-bubble {
  position: relative;
  padding: 12px;
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
  color: var(--class-ink, #f4f2f6);
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.6;
}
.student-bubble::before {
  content: "";
  position: absolute;
  top: -7px;
  left: 50%;
  width: 12px;
  height: 12px;
  transform: rotate(45deg);
  background: var(--class-raised, #1b1524);
  border-top: 1px solid var(--line);
  border-left: 1px solid var(--line);
}
.student-bubble p {
  margin: 0;
}
.student-bubble small {
  display: block;
  color: var(--class-violet-text, #d5a5ff);
  margin-bottom: 4px;
}
.student-bubble.failed {
  color: var(--class-danger, #ffaaa7);
}
.student-body {
  transform-origin: 100px 154px;
  animation: breathe 4s ease-in-out infinite;
}
.student-card.thinking {
  border-color: var(--violet);
}
.student-card.raised .student-arm {
  transform-origin: 140px 125px;
  animation: wave 1.2s ease-in-out infinite alternate;
}
@keyframes breathe {
  50% {
    transform: translateY(-2px);
  }
}
@keyframes wave {
  to {
    transform: rotate(-5deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .student-body,
  .student-card.raised .student-arm {
    animation: none !important;
  }
}
.student-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 14px 8px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--class-surface-raised);
  color: var(--class-ink);
  cursor: pointer;
  transition:
    transform 0.2s,
    border-color 0.2s;
  min-width: 0;
}
.student-card.speaking {
  border-color: var(--violet);
  box-shadow: 0 0 0 3px rgba(180, 92, 255, 0.12);
}
.student-card.raised {
  border-color: var(--orange);
  transform: translateY(-3px);
}
.student-card:hover {
  background: var(--class-hover);
}
svg {
  width: 100%;
  max-width: 160px;
}
.student-status {
  font-size: 11px;
  color: var(--class-muted);
  background: rgba(255, 255, 255, 0.05);
  border-radius: 20px;
  padding: 5px 10px;
}
.raised .student-status {
  background: rgba(255, 122, 24, 0.12);
  color: var(--class-orange-text);
}
.speaking .student-status {
  background: rgba(180, 92, 255, 0.14);
  color: var(--class-violet-text);
}
strong {
  font-size: 17px;
}
small {
  font-size: 12px;
  color: var(--class-muted);
  margin-top: 5px;
}
.student-memory {
  font-size: 11px;
  line-height: 1.6;
  margin-top: 10px;
  color: var(--class-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.student-arm {
  transform-origin: 140px 123px;
  transition: transform 0.6s;
}
.student-arm.up {
  transform: rotate(-115deg);
}
.student-eyes {
  animation: blink 6s infinite;
  transform-origin: 100px 73px;
}
.nod {
  animation: nod 1.8s ease-in-out infinite;
  transform-origin: 100px 150px;
}
@keyframes blink {
  0%,
  43%,
  46%,
  100% {
    transform: scaleY(1);
  }
  45% {
    transform: scaleY(0.1);
  }
}
@keyframes nod {
  50% {
    transform: rotate(1.5deg) translateY(1px);
  }
}
@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
@media (max-width: 600px) {
  .student-card {
    padding: 12px 4px;
    border-radius: 12px;
  }
  .student-status {
    font-size: 10px;
    padding: 4px;
  }
  strong {
    font-size: 14px;
  }
  small {
    font-size: 10px;
  }
  .student-memory {
    display: none;
  }
}
</style>
