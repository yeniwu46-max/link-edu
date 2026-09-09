<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import {
  BODY_EDGES,
  HAND_EDGES,
  containRect,
  visiblePoint,
} from "../services/classroomInteraction.js";
const props = defineProps({
  enabled: Boolean,
  disabled: Boolean,
  landmarks: Object,
  motionStatus: String,
  handStatus: String,
  teacherText: String,
  reply: Object,
});
const emit = defineEmits(["video", "toggle", "retry"]);
const container = ref(null),
  video = ref(null),
  canvas = ref(null),
  expandButton = ref(null),
  captionBox = ref(null);
const expanded = ref(false),
  fallback = ref(false),
  skeleton = ref(true),
  mirror = ref(false),
  now = ref(0);
let prefs = {};
try {
  prefs =
    JSON.parse(localStorage.getItem("classroom-camera-prefs") || "{}") || {};
} catch {}
const captions = ref(false),
  captionSource = ref(prefs.source === "teacher" ? "teacher" : "all"),
  fontSize = ref([20, 28, 36].includes(prefs.size) ? prefs.size : 28);
watch([captionSource, fontSize], () => {
  try {
    localStorage.setItem(
      "classroom-camera-prefs",
      JSON.stringify({ source: captionSource.value, size: fontSize.value }),
    );
  } catch {}
});
const fresh = computed(
  () =>
    props.enabled && props.landmarks && now.value - props.landmarks.at < 750,
);
const status = computed(() =>
  !props.enabled
    ? "镜头未开启"
    : props.motionStatus === "failed"
      ? "身体检测不可用"
      : props.motionStatus === "loading"
        ? "动作模型加载中…"
        : !fresh.value
          ? "等待清晰画面…"
          : `${props.landmarks.body?.some((p) => visiblePoint(p, true)) ? "身体已捕捉" : "身体未检测到"} · ${props.landmarks.hands?.length || 0} 只手`,
);
const studentCaption = computed(() => {
  const r = props.reply;
  if (!r?.text || ["failed", "idle"].includes(r.phase)) return "";
  const name = { ming: "小明", yu: "小雨", lin: "小林" }[r.studentId] || "学生";
  return `${name}${r.phase === "generating" ? " · 回复生成中" : ""}：${r.text}`;
});
const lastSpeaker = ref("teacher");
watch(
  () => props.teacherText,
  () => {
    lastSpeaker.value = "teacher";
  },
);
watch(studentCaption, (text) => {
  lastSpeaker.value = text ? "student" : "teacher";
});
const showStudent = computed(
  () =>
    captionSource.value === "all" &&
    lastSpeaker.value === "student" &&
    studentCaption.value,
);
const captionLabel = computed(() =>
  showStudent.value
    ? `${{ ming: "小明", yu: "小雨", lin: "小林" }[props.reply?.studentId] || "学生"}${props.reply?.phase === "generating" ? " · 回复生成中" : ""}`
    : "老师",
);
const captionText = computed(() =>
  showStudent.value ? props.reply.text : props.teacherText || "等待授课…",
);
watch(
  [() => props.teacherText, studentCaption, captions, fontSize],
  async () => {
    await nextTick();
    if (captionBox.value)
      captionBox.value.scrollTop = captionBox.value.scrollHeight;
  },
);
let observer, timer, previousFocus, previousOverflow;
function draw() {
  now.value = performance.now();
  const el = canvas.value,
    v = video.value;
  if (!el || !v) return;
  const { width, height } = el.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  if (
    el.width !== Math.round(width * dpr) ||
    el.height !== Math.round(height * dpr)
  ) {
    el.width = Math.round(width * dpr);
    el.height = Math.round(height * dpr);
  }
  const ctx = el.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  if (!fresh.value || !skeleton.value) return;
  const rect = containRect(width, height, v.videoWidth, v.videoHeight);
  if (!rect.width) return;
  const style = getComputedStyle(container.value);
  function paint(points, edges, color, body) {
    const xy = (p) => [
      rect.x + (mirror.value ? 1 - p.x : p.x) * rect.width,
      rect.y + p.y * rect.height,
    ];
    ctx.strokeStyle = ctx.fillStyle = color;
    ctx.lineWidth = body ? 3 : 2;
    for (const [a, b] of edges) {
      if (!visiblePoint(points[a], body) || !visiblePoint(points[b], body))
        continue;
      ctx.beginPath();
      ctx.moveTo(...xy(points[a]));
      ctx.lineTo(...xy(points[b]));
      ctx.stroke();
    }
    for (const p of points)
      if (visiblePoint(p, body)) {
        ctx.beginPath();
        ctx.arc(...xy(p), body ? 3 : 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
  }
  paint(
    props.landmarks.body || [],
    BODY_EDGES,
    style.getPropertyValue("--violet").trim() || "#b45cff",
    true,
  );
  for (const hand of props.landmarks.hands || [])
    paint(
      hand,
      HAND_EDGES,
      style.getPropertyValue("--orange").trim() || "#ff7a18",
      false,
    );
}
function restore() {
  expanded.value = fallback.value = false;
  if (previousOverflow !== undefined) {
    document.body.style.overflow = previousOverflow;
    previousOverflow = undefined;
  }
  previousFocus?.focus();
}
async function exit() {
  if (document.fullscreenElement === container.value)
    await document.exitFullscreen().catch(() => {});
  restore();
}
async function fullscreen() {
  if (expanded.value) return exit();
  previousFocus = document.activeElement;
  try {
    if (!container.value.requestFullscreen) throw new Error("unsupported");
    await container.value.requestFullscreen();
    expanded.value = true;
  } catch {
    fallback.value = expanded.value = true;
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  await nextTick();
  expandButton.value?.focus();
  draw();
}
function changed() {
  if (document.fullscreenElement !== container.value && !fallback.value)
    restore();
}
function keys(e) {
  if (!expanded.value) return;
  if (e.key === "Escape") {
    e.preventDefault();
    exit();
  }
  if (e.key === "Tab") {
    const controls = [
      ...container.value.querySelectorAll(
        "button:not(:disabled), input, select",
      ),
    ].filter((x) => x.getClientRects().length);
    const first = controls[0],
      last = controls.at(-1);
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }
}
watch(
  () => props.enabled,
  (value) => {
    if (!value && expanded.value) exit();
  },
);
onMounted(() => {
  emit("video", video.value);
  observer = new ResizeObserver(draw);
  observer.observe(container.value);
  timer = setInterval(draw, 100);
  document.addEventListener("fullscreenchange", changed);
});
onUnmounted(() => {
  clearInterval(timer);
  observer?.disconnect();
  document.removeEventListener("fullscreenchange", changed);
  if (document.fullscreenElement === container.value)
    document.exitFullscreen().catch(() => {});
  restore();
  emit("video", null);
});
</script>

<template>
  <div
    ref="container"
    class="classroom-camera"
    :class="{ expanded, fallback }"
    :role="fallback ? 'dialog' : undefined"
    :aria-modal="fallback ? 'true' : undefined"
    aria-label="老师镜头"
    @keydown="keys"
  >
    <div class="section-title">
      <h2>老师镜头 <small>可选</small></h2>
      <button
        type="button"
        class="text-action"
        :disabled="disabled"
        @click="emit('toggle')"
      >
        {{ enabled ? "关闭" : "开启" }}
      </button>
    </div>
    <div class="motion-frame">
      <video
        ref="video"
        autoplay
        muted
        playsinline
        :class="{ mirrored: mirror }"
        @loadedmetadata="draw"
      />
      <canvas ref="canvas" aria-hidden="true" />
      <div v-if="!enabled" class="camera-placeholder">
        <span>镜头未开启</span>
      </div>
      <div
        v-if="captions"
        class="camera-captions"
        :style="{ '--subtitle-size': `${fontSize}px` }"
        aria-label="课堂字幕"
      >
        <span class="caption-speaker">{{ captionLabel }}</span>
        <div ref="captionBox" class="caption-lines">
          <p>{{ captionText }}</p>
        </div>
      </div>
    </div>
    <div class="camera-tools">
      <button
        ref="expandButton"
        type="button"
        class="text-action"
        :disabled="!enabled"
        @click="fullscreen"
      >
        {{ expanded ? "退出全屏" : "全屏放大" }}
      </button>
      <label><input type="checkbox" v-model="skeleton" />骨架</label
      ><label><input type="checkbox" v-model="mirror" />镜像</label>
      <label><input type="checkbox" v-model="captions" />字幕</label>
      <template v-if="captions"
        ><select v-model="captionSource" aria-label="字幕内容">
          <option value="all">老师＋学生</option>
          <option value="teacher">仅老师</option></select
        ><select v-model.number="fontSize" aria-label="字幕字号">
          <option :value="20">小号</option>
          <option :value="28">中号</option>
          <option :value="36">大号</option>
        </select></template
      >
    </div>
    <p class="pose-caption">
      {{ status
      }}<span v-if="enabled && handStatus === 'failed'"> · 手部检测不可用</span>
    </p>
    <button
      v-if="enabled && (motionStatus === 'failed' || handStatus === 'failed')"
      type="button"
      class="text-action"
      @click="emit('retry')"
    >
      重新加载动作模型
    </button>
  </div>
</template>

<style scoped>
.classroom-camera {
  min-width: 0;
}
.motion-frame {
  position: relative;
  height: 240px;
  overflow: hidden;
  border-radius: 12px;
  background: #08060c;
}
.motion-frame video,
.motion-frame canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.motion-frame canvas {
  pointer-events: none;
}
.mirrored {
  transform: scaleX(-1);
}
.camera-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.camera-tools label {
  display: flex;
  gap: 4px;
  align-items: center;
  font-size: 13px;
}
.camera-tools select {
  max-width: 100%;
  padding: 6px;
}
.camera-captions {
  position: absolute;
  bottom: 12px;
  left: 12px;
  right: 12px;
  padding: 8px;
  background: rgba(8, 6, 12, 0.88);
  border-radius: 8px;
  color: #fff;
  font-size: var(--subtitle-size);
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.caption-speaker {
  display: block;
  font-size: 14px;
  color: var(--class-violet-text, #d5a5ff);
  margin-bottom: 4px;
}
.caption-lines {
  max-height: 4.5em;
  overflow: auto;
  scrollbar-width: thin;
}
.camera-captions p {
  margin: 0;
  font-size: inherit;
  line-height: inherit;
  color: inherit;
}
.classroom-camera.expanded {
  width: 100%;
  height: 100dvh;
  box-sizing: border-box;
  padding: 16px;
  background: var(--class-raised, #1b1524);
  display: flex;
  flex-direction: column;
}
.classroom-camera.fallback {
  position: fixed;
  inset: 0;
  z-index: 10000;
}
.expanded .motion-frame {
  flex: 1;
  min-height: 0;
  height: auto;
}
.expanded .section-title {
  flex-shrink: 0;
}
.expanded .pose-caption {
  margin-bottom: 0;
}
@media (max-width: 480px) {
  .expanded {
    padding: 8px !important;
  }
  .camera-tools {
    gap: 8px;
  }
}
</style>
