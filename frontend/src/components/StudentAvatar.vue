<script setup>
defineProps({
  student: Object,
  raised: Boolean,
  speaking: Boolean,
  level: Number,
  understanding: String,
});
const colors = { ming: "#8aaee9", yu: "#ecacc7", lin: "#a6c6bc" };
</script>

<template>
  <button
    type="button"
    class="student-card"
    :class="{ speaking, raised }"
    :aria-label="`${student.name}${raised ? '举手了，点击点名' : '，点击点名'}`"
    @click="$emit('select', student.id)"
  >
    <span class="student-status">{{
      speaking ? "正在发言" : raised ? "我有问题" : "认真听讲"
    }}</span>
    <svg
      viewBox="0 0 200 180"
      aria-hidden="true"
      :style="{ '--shirt': colors[student.id] }"
    >
      <ellipse cx="100" cy="169" rx="72" ry="8" fill="#344567" opacity=".08" />
      <g class="student-body" :class="{ nod: speaking }">
        <path d="M49 154Q49 108 99 108Q151 108 151 154" fill="var(--shirt)" />
        <path d="M89 108L100 126L111 108" fill="#fff8f4" />
        <g class="student-arm">
          <path
            :d="raised ? 'M139 123L159 96L161 51' : 'M139 123L158 149L172 151'"
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
    <span v-if="understanding" class="student-memory">{{ understanding }}</span>
  </button>
</template>

<style scoped>
.student-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 15px 10px;
  border: 1px solid #dbe4f1;
  border-radius: 22px;
  background: #fff;
  color: #26374f;
  cursor: pointer;
  transition:
    transform 0.2s,
    border-color 0.2s;
  min-width: 0;
}
.student-card.speaking {
  border-color: #6793d8;
  box-shadow: 0 0 0 3px #7ca9e71f;
}
.student-card.raised {
  border-color: #dd94b1;
  transform: translateY(-5px);
}
svg {
  width: 100%;
  max-width: 210px;
}
.student-status {
  font-size: 11px;
  color: #65758b;
  background: #f1f5fa;
  border-radius: 20px;
  padding: 5px 10px;
}
.raised .student-status {
  background: #fcecf3;
  color: #a3426c;
}
strong {
  font-size: 17px;
}
small {
  font-size: 12px;
  color: #69798c;
  margin-top: 5px;
}
.student-memory {
  font-size: 11px;
  line-height: 1.6;
  margin-top: 10px;
  color: #65758b;
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
</style>
