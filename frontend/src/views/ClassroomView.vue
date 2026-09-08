<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router";
import { api } from "../services/api";
import { useClassroom } from "../services/useClassroom";
import StudentAvatar from "../components/StudentAvatar.vue";
import ClassroomReport from "../components/ClassroomReport.vue";
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
const defaultStudents = [
  { id: "ming", name: "小明" },
  { id: "yu", name: "小雨" },
  { id: "lin", name: "小林" },
];
const active = computed(() =>
  ["connecting", "listening", "speaking", "finishing"].includes(state.value),
);
const ready = computed(
  () =>
    ["dialogue", "asr", "tts"].every(
      (k) => capabilities.value?.services[k].configured && capabilities.value?.services[k].pricing_confirmed,
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
      finishing: "保存末段转写",
      ended: "课堂已结束",
    })[state.value],
);
const timeline = computed(() =>
  events.value.filter((e) => e.type !== "pose" || e.data.present !== null),
);
const latestTeacher = computed(
  () => events.value.filter((e) => e.type === "transcript").at(-1)?.data.text,
);
const latestReply = computed(() =>
  events.value.filter((e) => e.type === "student").at(-1),
);
const services = {
  dialogue: "学生对话 / 评课",
  vision: "截图理解",
  asr: "实时语音识别",
  tts: "学生语音",
};
const serviceStatus = {
  unconfigured: "未配置",
  unverified: "已配置 · 待验证",
  available: "接口验证通过",
  failed: "验证失败",
};
async function refreshHistory() {
  try {
    history.value = (await api.get("/classroom/sessions")).data.items;
  } catch {
    error.value = "历史课堂暂时无法读取";
  }
}
async function probe(service) {
  probing.value = service;
  try {
    await api.post("/classroom/probe", { service });
    await refreshCapabilities();
  } catch {
    error.value = "验证请求失败，请确认后端连接";
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
    error.value = `请用麦克风点名${defaultStudents.find((s) => s.id === id).name}；不会把按钮点击伪装成授课转写。`;
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
        <p class="eyebrow">LINK · LIVE CLASSROOM</p>
        <h1>把讲解，变成对话。</h1>
        <p>
          小学数学 · 分数的初步认识 <span class="soft-tag">真实 AI 课堂</span>
        </p>
      </div>
      <button
        class="class-btn secondary"
        :disabled="active"
        @click="
          showHistory = !showHistory;
          refreshHistory();
        "
      >
        {{ showHistory ? "收起历史" : "历史课堂" }}
      </button>
    </header>
    <section v-if="showHistory" class="class-panel history-panel">
      <h2>我的课堂</h2>
      <p v-if="!history.length">还没有真实课堂记录。旧演示评分不会混入这里。</p>
      <router-link
        v-for="item in history"
        :key="item.session_id"
        :to="{ path: '/classroom', query: { session: item.session_id } }"
        @click="openSession(item.session_id)"
        ><span
          >#{{ item.session_id }} · {{ item.topic
          }}<small>{{
            new Date(item.created_at + "Z").toLocaleString()
          }}</small></span
        ><b>{{
          item.state === "active"
            ? "可继续"
            : {
                completed: "报告可查看",
                failed: "报告待重试",
                running: "评课中",
                idle: "待评课",
              }[item.report_state]
        }}</b></router-link
      >
    </section>
    <p v-if="error" class="class-alert" role="alert">
      {{ error }} <button aria-label="关闭提示" @click="error = ''">×</button>
    </p>
    <section
      v-if="!active && state !== 'ended'"
      class="class-panel service-panel"
    >
      <div class="section-title">
        <h2>课前连接检查</h2>
        <small>点击验证会产生少量实际调用费用</small>
      </div>
      <div class="service-grid">
        <article v-for="(label, key) in services" :key="key">
          <span>{{ label }}</span
          ><b :class="capabilities?.services[key].status">{{
            serviceStatus[capabilities?.services[key].status] || "读取中"
          }}</b
          ><small>{{ capabilities?.services[key].provider }} · {{ capabilities?.services[key].model }}</small>
          <small v-if="capabilities?.services[key].voices">音色：{{ Object.values(capabilities.services[key].voices).join(' / ') }}（权限以实际验证为准）</small>
          <p v-if="capabilities?.services[key].message">
            {{ capabilities.services[key].message }}
          </p>
          <button
            class="class-btn secondary"
            :disabled="!!probing || !capabilities?.services[key].configured || !capabilities?.services[key].pricing_confirmed"
            @click="probe(key)"
          >
            {{ probing === key ? "验证中…" : "验证接口" }}
          </button>
        </article>
      </div>
      <p class="service-note">
        本地动作检测：{{
          capabilities?.pose_assets
            ? "模型已就绪 · 摄像头开启后检测"
            : "模型文件未就绪"
        }}。接口通过不等于真实课堂已验收。
      </p>
    </section>
    <div class="live-grid">
      <section class="class-panel class-stage">
        <header class="stage-heading">
          <span class="connection-label" :class="state"
            ><i />{{ stateLabel }}</span
          ><span class="class-timer" aria-label="剩余时间">{{
            remaining
          }}</span>
        </header>
        <div class="lesson-note">
          <span>今天的探索</span><strong>一块蛋糕，怎样公平地分享？</strong>
          <p>平均分 → 几分之一 → 分子与分母 → 同一整体</p>
        </div>
        <div class="student-grid">
          <StudentAvatar
            v-for="s in students.length ? students : defaultStudents"
            :key="s.id"
            :student="s"
            :raised="raised === s.id"
            :speaking="activeStudent === s.id"
            :level="mouth"
            :understanding="room?.students?.[s.id]?.understanding"
            @select="selectStudent"
          />
        </div>
        <div class="live-caption" role="log" aria-live="polite">
          <span>老师 · {{ partial ? "临时字幕，不入档" : "最终转写" }}</span>
          <p>
            {{
              partial ||
              latestTeacher ||
              "戴上耳机，从“同学们好”开始。麦克风转写将在这里出现。"
            }}
          </p>
        </div>
        <div v-if="latestReply" class="student-caption">
          <span
            >{{ latestReply.data.name }} ·
            {{ latestReply.data.action === "followup" ? "追问" : "回应" }}</span
          >
          <p>{{ latestReply.data.text }}</p>
          <small>文字为模型生成；是否听到声音以语音播放状态为准。</small>
        </div>
        <div class="class-controls">
          <template v-if="!room"
            ><label for="class-mode" class="sr-only">训练时长</label
            ><select id="class-mode" v-model="mode">
              <option value="full">10 分钟完整课堂</option>
              <option value="fragment">8 分钟专项训练</option></select
            ><button
              class="class-btn"
              :disabled="!consent || !ready || busy"
              @click="start"
            >
              {{ busy ? "准备中…" : "开始真实课堂 →" }}
            </button></template
          ><template v-else-if="state !== 'ended'"
            ><button
              v-if="state === 'disconnected'"
              class="class-btn"
              :disabled="busy || !consent || !ready"
              @click="reconnect"
            >
              重新连接</button
            ><button
              v-if="activeStudent"
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
          ><button
            v-else
            class="class-btn secondary"
            @click="router.push('/classroom').then(() => router.go(0))"
          >
            准备下一节课堂
          </button>
        </div>
        <p v-if="!ready && !room" class="service-note">
          先完成对话、识别和合成的本机配置，再开始真实课堂。
        </p>
      </section>
      <aside class="class-sidebar">
        <section class="class-panel camera-panel">
          <div class="section-title">
            <h2>老师镜头</h2>
            <button
              class="text-action"
              :disabled="state === 'ended'"
              @click="preview"
            >
              {{ cameraOn ? "关闭" : "开启" }}
            </button>
          </div>
          <div class="camera-frame">
            <video ref="camera" autoplay muted playsinline /><span
              v-if="!cameraOn"
              >摄像头可选<br /><small>关闭镜头不影响语音课堂</small></span
            >
          </div>
          <p class="pose-caption">
            {{
              !pose
                ? "动作状态：无法判断"
                : pose.present === null
                  ? "置信度不足：无法判断"
                  : pose.present
                    ? "检测到人物"
                    : "未检测到人物"
            }}
          </p>
          <dl v-if="pose?.present">
            <div>
              <dt>检测置信度</dt>
              <dd>{{ Math.round(pose.confidence * 100) }}%</dd>
            </div>
            <div>
              <dt>抬手</dt>
              <dd>
                {{
                  pose.left_raised || pose.right_raised ? "观察到" : "未观察到"
                }}
              </dd>
            </div>
            <div>
              <dt>躯干倾斜</dt>
              <dd>{{ pose.lean_degrees?.toFixed(1) }}°</dd>
            </div>
          </dl>
          <small>只记录可观测动作，不推断真实情绪或教学质量。</small>
        </section>
        <section class="class-panel consent-panel">
          <h2>隐私与预算</h2>
          <label
            ><input
              type="checkbox"
              v-model="consent"
              :disabled="active"
            />我同意麦克风音频上传百炼识别、文字提交 DeepSeek
            对话及评课；原始录音不保存。</label
          ><label
            ><input
              type="checkbox"
              v-model="cloudVision"
              :disabled="state === 'ended'"
              @change="setVision"
            />开启云端截图分析（每 15 秒最多 1 张、每课最多 40
            张），截图私有保存用于证据查看。</label
          >
          <p>
            不开启此项，动作检测完全在浏览器运行。所有资料只用于检索，不用于训练模型权重。
          </p>
          <div
            class="budget-summary"
            :class="{ warning: capabilities?.budget.warning }"
          >
            <span>调用估算 + 在途预留</span
            ><strong
              >¥{{
                capabilities?.budget.spent_and_reserved_cny?.toFixed(3) ||
                "0.000"
              }}
              <small>/ 100</small></strong
            ><small
              >80 元提醒 · 预计达到 90 元停止<br />估算非平台账单，按已确认单价记账</small
            >
          </div>
        </section>
      </aside>
    </div>
    <ClassroomReport
      v-if="room?.state === 'ended'"
      :room="room"
      :busy="busy"
      @regenerate="regenerate"
    />
    <section v-if="events.length" class="class-panel timeline-panel">
      <div class="section-title">
        <h2>课堂时间轴</h2>
        <small>最终文本、交互、动作与截图观察 · 不含完整录像</small>
      </div>
      <ol>
        <li
          v-for="e in timeline"
          :key="e.id"
          :id="`evidence-${e.id}`"
          tabindex="-1"
        >
          <time>{{ time(e.at_ms / 1000) }}</time>
          <div>
            <span class="event-label"
              >{{
                {
                  transcript: "老师",
                  student: e.data.name,
                  question: "学生举手",
                  vision: "截图观察",
                  pose: "动作观察",
                  interrupt: "打断",
                  latency: "声音延迟",
                  correction: "教师异议",
                  error: "异常记录",
                  playback: "语音状态",
                }[e.type] || e.type
              }}
              · #{{ e.id }}</span
            >
            <p>
              {{
                e.data.text ||
                e.data.observations ||
                e.data.objection ||
                e.data.message ||
                (e.type === "latency"
                  ? `${e.data.latency_ms} ms（客户端观测）`
                  : e.type === "pose"
                    ? `人物${e.data.present ? "在画面内" : "未检测到"}；抬手：${e.data.left_raised || e.data.right_raised ? "是" : "否"}`
                    : e.data.status || "")
              }}
            </p>
          </div>
        </li>
      </ol>
    </section>
  </div>
</template>
