<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { motionLabels } from '../services/motionFeatures.js';
import ClassroomDialog from './ClassroomDialog.vue';
import {
  BODY_EDGES,
  HAND_EDGES,
  containRect,
  visiblePoint,
} from "../services/classroomInteraction.js";
const props = defineProps({
  enabled: Boolean,
  disabled: Boolean,
  cameraConsent: Boolean,
  cameraBusy: Boolean,
  previewAllowed: Boolean,
  landmarks: Object,
  motionStatus: String,
  handStatus: String,
  faceStatus: String,
  motion: Object,
  teacherText: String,
  reply: Object,
  volume: {type:Number, default:1},
  resolution: {type:Number, default:720},
  resolutionBusy: Boolean,
  cameraNote: String,
});
const emit = defineEmits(["video", "toggle", "retry", "volume", "resolution"]);
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
const settingsOpen = ref(false);
defineExpose({openSettings: () => { settingsOpen.value = true; }});
let prefs = {};
try {
  prefs =
    JSON.parse(localStorage.getItem("classroom-camera-prefs") || "{}") || {};
} catch {}
const captions = ref(true),
  captionSource = ref(prefs.source === "teacher" ? "teacher" : "all"),
  fontSize = ref([16, 20, 28, 36].includes(prefs.size) ? prefs.size : 28),
  captionWidth = ref(80);
function shrinkCaptions() {
  fontSize.value = [16,20,28,36][Math.max(0,[16,20,28,36].indexOf(fontSize.value)-1)];
  captionWidth.value = 60;
}
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
const observations = computed(() => fresh.value ? motionLabels(props.motion) : []);
const faceState = computed(() => !props.enabled ? '未开启' : props.faceStatus === 'loading' ? '加载中' :
  props.faceStatus === 'failed' ? '不可用' : fresh.value && props.landmarks.face?.length ? '已捕捉' : '未检测到');
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
  // A sparse outline avoids rendering/storing a dense biometric mesh in the UI.
  const facePoints = props.landmarks.face || [];
  const outline = [10,338,297,332,284,251,389,356,454,323,361,288,397,365,379,378,400,377,152,148,176,149,150,136,172,58,132,93,234,127,162,21,54,103,67,109];
  const sparse = outline.map(i=>facePoints[i]);
  paint(sparse, sparse.map((_,i)=>[i,(i+1)%sparse.length]), style.getPropertyValue('--mint').trim() || '#6ce4ca', false);
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
  // Native dialog owns Escape/Tab while open, including projected record windows.
  if (settingsOpen.value || e.target?.closest?.('dialog[open]')) return;
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
    <div class="motion-frame">
      <header class="camera-scene-heading"><div class="scene-label"><slot name="heading"><h2>教师授课画面</h2></slot></div><slot name="timer" /></header>
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
        <svg viewBox="0 0 48 48" aria-hidden="true"><rect x="5" y="12" width="27" height="24" rx="5"/><path d="m32 20 11-6v20l-11-6"/></svg>
        <strong>{{ disabled ? '本次课堂已结束' : '准备好，开始你的课堂' }}</strong>
        <span id="camera-preview-hint">{{ disabled ? '摄像头与麦克风已停止采集' : cameraConsent ? '先预览取景，不启动麦克风、课堂计时或 AI 评课' : '先勾选上方「同意摄像头开启」，即可单独预览' }}</span>
        <button v-if="!disabled" type="button" class="class-btn camera-open-button"
          :disabled="!cameraConsent || cameraBusy || !previewAllowed" :aria-busy="cameraBusy"
          aria-describedby="camera-preview-hint" @click="emit('toggle')">{{ cameraBusy ? '正在开启摄像头…' : '打开摄像头' }}</button>
      </div>
      <div
        v-if="captions && enabled"
        class="camera-captions"
        :style="{ '--subtitle-size': `${fontSize}px`, '--caption-width': `${captionWidth}%` }"
        aria-label="课堂字幕"
      >
        <span class="caption-speaker">{{ captionLabel }}</span>
        <div ref="captionBox" class="caption-lines">
          <p>{{ captionText }}</p>
        </div>
      </div>
    </div>
    <div class="fullscreen-students" aria-label="课堂学生"><slot name="students" /></div>
    <div class="camera-bar">
      <button type="button" class="text-action" :aria-expanded="settingsOpen" aria-haspopup="dialog" @click="settingsOpen = true">课堂设置</button>
      <button
        ref="expandButton"
        type="button"
        class="text-action"
        :disabled="!enabled"
        @click="fullscreen"
      >
        {{ expanded ? "退出全屏" : "全屏放大" }}
      </button>
      <slot name="actions" />
    </div>
    <p class="motion-statusbar" :title="[status, observations.join(' · '), cameraNote].filter(Boolean).join(' · ')">
      {{ status }} · 面部{{ faceState }}<span v-if="observations.length"> · {{ observations.join(' · ') }}</span>
    </p>
    <ClassroomDialog v-model="settingsOpen" title="课堂设置">
    <h3>画面与声音</h3>
    <div class="camera-tools">
      <label><input type="checkbox" v-model="skeleton" />骨架</label
      ><label><input type="checkbox" v-model="mirror" />镜像</label>
      <label><input type="checkbox" v-model="captions" />字幕</label>
      <template v-if="captions"
        ><select v-model="captionSource" aria-label="字幕内容">
          <option value="all">老师＋学生</option>
          <option value="teacher">仅老师</option></select
        ><select v-model.number="fontSize" aria-label="字幕字号">
          <option :value="16">更小</option>
          <option :value="20">小号</option>
          <option :value="28">中号</option>
          <option :value="36">大号</option>
        </select><select v-model.number="captionWidth" aria-label="字幕宽度">
          <option :value="60">窄字幕</option><option :value="80">中字幕</option><option :value="100">宽字幕</option>
        </select><button type="button" class="text-action" @click="shrinkCaptions">缩小字幕</button></template
      >
      <label class="resolution-control">画质<select aria-label="画面分辨率" :value="resolution" :disabled="resolutionBusy || disabled" @change="emit('resolution', $event.target.value)">
        <option :value="1020">1020p</option><option :value="720">720p</option><option :value="360">360p</option>
      </select></label>
      <label class="volume-control">音量<input type="range" aria-label="上课音量" min="0" max="1" step="0.05" :value="volume" @input="emit('volume', $event.target.value)" /><output>{{ Math.round(volume * 100) }}%</output></label>
    </div>
    <p class="pose-caption">
      {{ status
      }}<span v-if="enabled && handStatus === 'failed'"> · 手部检测不可用</span>
      <span> · 面部{{ faceState }}</span>
    </p>
    <p class="motion-observations">{{ observations.join(' · ') || '暂无清晰动作线索' }}</p>
    <p class="camera-resolution-note" :title="cameraNote">{{ cameraNote }}</p>
    <p class="camera-privacy pose-caption">开启镜头将在本机检测身体、手势和面部；仅动作摘要用于教态评课，不做人脸识别或情绪判断。云截图需另行开启。</p>
    <div class="motion-recovery">
    <button
      v-if="enabled && (motionStatus === 'failed' || handStatus === 'failed' || faceStatus === 'failed')"
      type="button"
      class="text-action"
      @click="emit('retry')"
    >
      重新加载动作模型
    </button>
    </div>
    <slot name="settings" />
    </ClassroomDialog>
    <slot name="windows" />
  </div>
</template>

<style scoped>
.classroom-camera {
  min-width: 0;
}
.camera-scene-heading { position:absolute; top:16px; left:20px; right:20px; z-index:2; display:flex; align-items:start; justify-content:space-between; gap:16px; pointer-events:none; color:#fff; text-shadow:0 2px 8px #000; }
.scene-label { padding:8px 12px; border-radius:8px; background:#08060ca8; }
.camera-bar { display:flex; align-items:center; flex-wrap:nowrap; gap:20px; height:44px; margin-top:8px; flex-shrink:0; overflow-x:auto; scrollbar-width:thin; }
.camera-bar :deep(button), .camera-bar :deep(.thinking-notice) { flex-shrink:0; white-space:nowrap; }
.motion-statusbar { height:24px; font-size:11px; line-height:24px; color:var(--class-muted); overflow:hidden; white-space:nowrap; text-overflow:ellipsis; flex-shrink:0; }
.motion-frame .camera-placeholder { inset:0; display:flex; align-items:center; justify-content:center; flex-direction:column; text-align:center; padding:88px 20px; gap:12px; }
.camera-placeholder strong { color:var(--class-ink); font-size:clamp(16px,2vw,24px); }
.motion-frame .camera-placeholder svg { width:48px; height:48px; margin-bottom:8px; }
.motion-observations { font-size: .875rem; line-height: 22px; height: 44px; overflow: hidden; overflow-wrap: anywhere; flex-shrink: 0; }
.camera-resolution-note { height: 20px; line-height: 20px; font-size: 12px; color: var(--class-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
.motion-frame {
  position: relative;
  height: clamp(320px, 60dvh, 840px);
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
  flex-shrink: 0;
}
.volume-control { flex: 0 1 200px; }
.volume-control input { width: 90px; min-width: 48px; accent-color: var(--orange); }
.volume-control output { min-width: 36px; text-align: end; font-variant-numeric: tabular-nums; }
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
  display: flex;
  flex-direction: column;
  max-height: calc(100% - 16px);
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  width: min(var(--caption-width, 80%), calc(100% - 24px));
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
  flex-shrink: 0;
  font-size: 14px;
  color: var(--class-violet-text, #d5a5ff);
  margin-bottom: 4px;
}
.caption-lines {
  height: 3em;
  min-height: 0;
  text-align: center;
  overflow: auto;
  overscroll-behavior: contain;
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
  overflow: hidden;
  contain: layout;
}
.expanded .camera-privacy { display: none; }
.expanded .pose-caption { height: 20px; line-height: 20px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; flex-shrink: 0; }
.expanded .motion-recovery { height: 36px; flex-shrink: 0; }
.motion-recovery { display: flex; align-items: center; gap: 16px; }
.fullscreen-students { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; height: 188px; flex-shrink: 0; margin-top: 8px; min-height: 0; }
.caption-speaker { text-align: center; }
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
  .camera-scene-heading {left:12px;right:12px;top:12px;gap:8px;}
  .scene-label {max-width:65%;font-size:11px;padding:4px 8px;}
  .fullscreen-students {gap:6px;}
  .expanded {
    padding: 8px !important;
  }
  .camera-tools {
    gap: 8px;
  }
}
@media (max-height: 600px) {
  .expanded { padding: 8px; }
  .expanded .motion-observations, .expanded .camera-resolution-note, .expanded .pose-caption { display: none; }
  .expanded .fullscreen-students { height: 132px; }
  .expanded .motion-statusbar { display:none; }
  .expanded .camera-tools { gap: 8px; margin-top: 4px; }
  .expanded .camera-captions { bottom: 4px; max-height: calc(100% - 8px); padding: 4px; line-height: 1.2; }
  .expanded .caption-speaker { display: none; }
}
</style>
