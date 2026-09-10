<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router";
import { api } from "../services/api";
import {
  speechProviderLabel,
  classroomLoadError,
  connectionSummary,
  budgetNotice,
} from "../services/classroomStatus.js";
import { useClassroom } from "../services/useClassroom";
import StudentAvatar from "../components/StudentAvatar.vue";
import ClassroomCamera from "../components/ClassroomCamera.vue";
import ClassroomReport from "../components/ClassroomReport.vue";
import ClassroomSettings from "../components/ClassroomSettings.vue";
import ClassroomTimeline from "../components/ClassroomTimeline.vue";
import SpecularButton from "../components/fx/SpecularButton.vue";
import "../classroom.css";
const route = useRoute(),
  router = useRouter(),
  live = useClassroom();
const {
  room,
  capabilities,
  events,
  error,
  state,
  partial,
  students,
  activeStudent,
  raised,
  mouth,
  pose,
  reply,
  playbackStudent,
  landmarks,
  motionStatus,
  handStatus,
  cameraEnabled,
  retryMotion,
  camera,
  elapsed,
  cloudVision,
  busy,
  send,
  refreshCapabilities,
  begin,
  reconnect,
  finish,
  load,
  regenerate,
  toggleCamera,
  setVision,
} = live;
const mode = ref("full"),
  consent = ref(false),
  history = ref([]),
  probing = ref(""),
  showHistory = ref(false),
  cameraOn = ref(false);
const settingsOpen = ref(false),
  timelineRef = ref(null),
  settingsToggle = ref(null);
const statusGroups = computed(() => [
  {
    key: "dialogue",
    title: "对话",
    ...connectionSummary(capabilities.value?.services, ["dialogue"]),
  },
  {
    key: "speech",
    title: "语音",
    ...connectionSummary(capabilities.value?.services, ["asr", "tts"]),
  },
  {
    key: "vision",
    title: "视觉",
    ...connectionSummary(capabilities.value?.services, ["vision"]),
  },
]);
const quotaNotice = computed(() => budgetNotice(capabilities.value?.budget));
const connectionIssue = computed(() =>
  statusGroups.value.some(
    (group) => group.tone === "failed" || group.tone === "warning",
  ),
);
function openSettings() {
  settingsOpen.value = true;
  settingsToggle.value?.focus();
}
const startHint = computed(() =>
  !capabilities.value
    ? "正在读取课堂状态…"
    : !ready.value
      ? "课堂暂不可开始，请查看课堂设置。"
      : !consent.value
        ? "请先同意语音识别与 AI 评课"
        : "",
);
const defaultStudents = [
  { id: "ming", name: "小明" },
  { id: "yu", name: "小雨" },
  { id: "lin", name: "小林" },
];
const asrProvider = computed(() => capabilities.value?.services?.asr?.provider);
watch(asrProvider, () => {
  consent.value = false;
});
const llmProvider = computed(
  () => capabilities.value?.services?.dialogue?.provider,
);
const llmLabel = computed(() =>
  llmProvider.value === "openai_next"
    ? "OpenAI Next（DeepSeek 模型）"
    : "DeepSeek",
);
watch(llmProvider, () => {
  consent.value = false;
});
const active = computed(() =>
  ["connecting", "listening", "speaking", "finishing"].includes(state.value),
);
const ready = computed(
  () =>
    ["dialogue", "asr", "tts"].every(
      (k) =>
        capabilities.value?.services[k].configured &&
        capabilities.value?.services[k].pricing_confirmed,
    ) &&
    capabilities.value?.budget.pricing_confirmed &&
    !capabilities.value?.budget.stopped,
);
const time = (sec) =>
  `${String(Math.floor(Math.max(0, sec) / 60)).padStart(2, "0")}:${String(Math.floor(Math.max(0, sec)) % 60).padStart(2, "0")}`;
const remaining = computed(() =>
  time(
    (room.value?.mode === "fragment" ||
    (!room.value && mode.value === "fragment")
      ? 480
      : 600) - elapsed.value,
  ),
);
const stateLabel = computed(
  () =>
    ({
      idle: "准备课堂",
      connecting: "连接语音服务",
      listening: "正在听老师讲课",
      speaking: "学生正在发言",
      disconnected: "连接已断开",
      finishing: "正在结束课堂…",
      ended: "课堂已结束",
    })[state.value],
);
const latestTeacher = computed(
  () => events.value.filter((e) => e.type === "transcript").at(-1)?.data.text,
);
const latestReply = computed(() =>
  events.value.filter((e) => e.type === "student").at(-1),
);
async function refreshHistory() {
  try {
    history.value = (await api.get("/classroom/sessions")).data.items;
  } catch (e) {
    error.value = classroomLoadError(e, "历史课堂暂时无法读取");
  }
}
async function probe(service) {
  probing.value = service;
  try {
    await api.post("/classroom/probe", { service });
    await refreshCapabilities();
  } catch {
    error.value = "连接检查失败，请稍后重试";
  } finally {
    probing.value = "";
  }
}
async function start() {
  await begin(mode.value, consent.value);
  if (room.value) router.replace({ query: { session: room.value.session_id } });
}
async function preview() {
  await toggleCamera();
  cameraOn.value = !!camera.value?.srcObject;
}
async function selectStudent(id) {
  if (raised.value === id) send("select_student", { student_id: id });
  else
    error.value = `请用麦克风点名${defaultStudents.find((s) => s.id === id).name}。`;
}
async function openSession(sid) {
  try {
    await load(sid);
    if (room.value.state === "active") state.value = "disconnected";
    showHistory.value = false;
  } catch {
    error.value = "课堂不存在或没有访问权限";
  }
}
watch(
  () => route.query.session,
  (sid) => {
    if (sid && Number(sid) !== room.value?.session_id && !active.value)
      openSession(sid);
  },
);
watch(state, (s) => {
  if (s === "ended") {
    cameraOn.value = false;
    refreshHistory();
    refreshCapabilities();
  }
});
onMounted(async () => {
  await refreshCapabilities();
  await refreshHistory();
  if (route.query.session) await openSession(route.query.session);
});
onBeforeRouteLeave(
  () =>
    !active.value ||
    window.confirm("离开会中断麦克风连接，记录将保留。确定离开吗？"),
);
</script>

<template>
  <div class="classroom-page">
    <header class="classroom-heading">
      <div>
        <h1>模拟课堂<span class="heading-dot" aria-hidden="true">.</span></h1>
        <p>小学数学 · 分数的初步认识</p>
      </div>
      <button
        class="class-btn secondary"
        :disabled="active"
        :aria-expanded="showHistory"
        aria-controls="classroom-history"
        @click="
          showHistory = !showHistory;
          refreshHistory();
        "
      >
        {{ showHistory ? "收起历史" : "历史课堂" }}
      </button>
    </header>
    <section
      v-if="showHistory"
      id="classroom-history"
      class="class-panel history-panel"
    >
      <h2>我的课堂</h2>
      <p v-if="!history.length" class="empty-state">暂无课堂记录</p>
      <router-link
        v-for="item in history"
        :key="item.session_id"
        :to="{ path: '/classroom', query: { session: item.session_id } }"
        @click="openSession(item.session_id)"
      >
        <span
          >{{ item.topic
          }}<small>{{
            new Date(item.created_at + "Z").toLocaleString()
          }}</small></span
        >
        <b>{{
          item.state === "active"
            ? "可继续"
            : {
                completed: "查看报告",
                failed: "待重试",
                running: "评课中",
                idle: "待评课",
              }[item.report_state]
        }}</b>
      </router-link>
    </section>
    <p v-if="error" class="class-alert" role="alert">
      {{ error }} <button aria-label="关闭提示" @click="error = ''">×</button>
    </p>
    <div class="connection-strip" aria-label="课堂连接状态">
      <div class="status-items">
        <span
          v-for="group in statusGroups"
          :key="group.key"
          class="status-item"
          :class="group.tone"
          ><i aria-hidden="true" />{{ group.title
          }}<b>{{ group.label }}</b></span
        >
      </div>
      <button
        type="button"
        class="text-action"
        @click="settingsOpen = !settingsOpen"
        :aria-expanded="settingsOpen"
        aria-controls="classroom-settings"
      >
        课堂设置 <span aria-hidden="true">{{ settingsOpen ? "−" : "+" }}</span>
      </button>
    </div>
    <div
      v-if="quotaNotice || connectionIssue"
      class="class-notice"
      role="status"
    >
      <span>{{ quotaNotice || "部分服务待处理，请检查连接设置。" }}</span
      ><button type="button" class="text-action" @click="openSettings">
        {{ quotaNotice ? "查看额度" : "查看设置" }} ↗
      </button>
    </div>
    <div class="live-grid">
      <section class="class-panel class-stage">
        <header class="stage-heading">
          <span class="connection-label" :class="state"
            ><i aria-hidden="true" />{{ stateLabel }}</span
          ><span class="class-timer" aria-label="剩余时间">{{
            remaining
          }}</span>
        </header>
        <div class="lesson-note">
          <span>今天的探索</span><strong>一块蛋糕，怎样公平地分享？</strong>
          <p>平均分 · 几分之一 · 分子与分母 · 同一整体</p>
        </div>
        <div class="student-grid">
          <StudentAvatar
            v-for="s in students.length ? students : defaultStudents"
            :key="s.id"
            :student="s"
            :raised="raised === s.id"
            :speaking="playbackStudent === s.id"
            :reply="reply.studentId === s.id ? reply : null"
            :level="mouth"
            :understanding="room?.students?.[s.id]?.understanding"
            @select="selectStudent"
          />
        </div>
        <p
          v-if="!reply.studentId && reply.phase === 'thinking'"
          class="thinking-notice"
          role="status"
        >
          学生正在思考<span class="thinking-dots" aria-hidden="true">…</span>
        </p>
        <div v-if="reply.phase === 'failed'" class="class-notice" role="status">
          <span>{{ reply.error }}</span
          ><button
            v-if="!reply.replyId"
            class="text-action"
            type="button"
            :disabled="state !== 'listening'"
            @click="send('retry_generation')"
          >
            重新生成回复
          </button>
        </div>
        <div class="live-caption" role="log" aria-live="polite">
          <span>老师<span v-if="partial"> · 识别中…</span></span>
          <p :class="{ 'caption-empty': !partial && !latestTeacher }">
            {{ partial || latestTeacher || "等待授课…" }}
          </p>
        </div>
        <div v-if="latestReply" class="student-caption">
          <span
            >{{ latestReply.data.name }} ·
            {{ latestReply.data.action === "followup" ? "追问" : "回应" }}</span
          >
          <p>{{ latestReply.data.text }}</p>
        </div>
        <div v-if="state !== 'ended'" class="consent-row">
          <label
            ><input
              type="checkbox"
              v-model="consent"
              :disabled="active"
            />同意语音识别与 AI 评课</label
          >
          <details class="disclosure privacy-details">
            <summary>数据使用说明</summary>
            <p>
              麦克风音频上传{{
                speechProviderLabel(asrProvider)
              }}进行识别，文字提交{{
                llmLabel
              }}进行对话与评课。原始录音不保存，转写文本与课堂记录会保留。
            </p>
            <p>资料仅用于检索，不用于训练模型权重。</p>
          </details>
        </div>
        <div class="class-controls">
          <template v-if="!room"
            ><label for="class-mode" class="sr-only">训练时长</label
            ><select id="class-mode" v-model="mode">
              <option value="full">10 分钟完整课堂</option>
              <option value="fragment">8 分钟专项训练</option></select
            ><SpecularButton
              class="class-btn"
              :disabled="!consent || !ready || busy"
              aria-describedby="class-start-hint"
              @click="start"
            >
              {{ busy ? "准备中…" : "开始课堂" }}
              <span aria-hidden="true">→</span>
            </SpecularButton></template
          >
          <template v-else-if="state !== 'ended'"
            ><button
              v-if="state === 'disconnected'"
              class="class-btn"
              :disabled="busy || !consent || !ready"
              aria-describedby="class-start-hint"
              @click="reconnect"
            >
              重新连接</button
            ><button
              v-if="
                activeStudent ||
                ['thinking', 'generating', 'queued'].includes(reply.phase)
              "
              class="class-btn secondary"
              @click="send('cancel')"
            >
              打断学生</button
            ><button
              class="class-btn"
              :disabled="busy || state === 'finishing'"
              @click="finish"
            >
              {{ state === "finishing" ? "结束处理中…" : "结束并评课" }}
            </button></template
          >
          <button
            v-else
            class="class-btn"
            @click="router.push('/classroom').then(() => router.go(0))"
          >
            开始下一节 →
          </button>
        </div>
        <p
          v-if="!room || state === 'disconnected'"
          id="class-start-hint"
          class="subtle-note start-hint"
        >
          {{ startHint
          }}<button
            v-if="capabilities && !ready"
            type="button"
            class="text-action"
            @click="openSettings"
          >
            查看设置
          </button>
        </p>
      </section>
      <aside class="class-sidebar">
        <section class="class-panel camera-panel">
          <ClassroomCamera
            :enabled="cameraEnabled"
            :disabled="state === 'ended'"
            :landmarks="landmarks"
            :motion-status="motionStatus"
            :hand-status="handStatus"
            :teacher-text="partial || latestTeacher"
            :reply="reply"
            @video="camera = $event"
            @toggle="preview"
            @retry="retryMotion"
          />
          <details v-if="pose?.present" class="disclosure">
            <summary>动作详情</summary>
            <dl>
              <div>
                <dt>检测置信度</dt>
                <dd>{{ Math.round(pose.confidence * 100) }}%</dd>
              </div>
              <div>
                <dt>抬手</dt>
                <dd>
                  {{
                    pose.left_raised || pose.right_raised ? "已抬手" : "未抬手"
                  }}
                </dd>
              </div>
              <div>
                <dt>躯干倾斜</dt>
                <dd>{{ pose.lean_degrees?.toFixed(1) }}°</dd>
              </div>
            </dl>
          </details>
          <div class="vision-option">
            <label
              ><input
                type="checkbox"
                v-model="cloudVision"
                :disabled="state === 'ended'"
                @change="setVision"
              />云端画面分析</label
            >
            <details class="disclosure">
              <summary>使用说明</summary>
              <p>
                开启后，截图提交{{ llmLabel }}分析，每 15 秒最多 1 张、每课最多
                40
                张，私有保存用于评课证据。关闭后仅在浏览器内检测动作；不影响语音授课。
              </p>
            </details>
          </div>
        </section>
        <section class="class-panel settings-panel">
          <button
            ref="settingsToggle"
            type="button"
            class="settings-toggle"
            :aria-expanded="settingsOpen"
            aria-controls="classroom-settings"
            @click="settingsOpen = !settingsOpen"
          >
            <span>课堂设置</span
            ><span aria-hidden="true">{{ settingsOpen ? "−" : "+" }}</span>
          </button>
          <div id="classroom-settings" v-show="settingsOpen">
            <ClassroomSettings
              :capabilities="capabilities"
              :probing="probing"
              :active="active"
              @probe="probe"
              @refresh="refreshCapabilities"
            />
          </div>
          <p v-if="!settingsOpen" class="subtle-note">连接与额度</p>
        </section>
      </aside>
    </div>
    <ClassroomReport
      v-if="room?.state === 'ended'"
      :room="room"
      :busy="busy"
      @regenerate="regenerate"
      @jump="timelineRef?.reveal($event)"
    />
    <ClassroomTimeline
      v-if="events.length"
      ref="timelineRef"
      :events="events"
    />
  </div>
</template>
