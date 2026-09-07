<script setup>
import { ref, onUnmounted } from "vue";
import { api } from "../services/api";
const props = defineProps({ room: Object, busy: Boolean });
defineEmits(["regenerate", "jump"]);
const objection = ref(""),
  image = ref(""),
  imageError = ref("");
async function showImage(event) {
  imageError.value = "";
  try {
    const { data } = await api.get(
      `/classroom/sessions/${props.room.session_id}/evidence/${event.id}`,
      { responseType: "blob" },
    );
    if (image.value) URL.revokeObjectURL(image.value);
    image.value = URL.createObjectURL(data);
  } catch {
    imageError.value = "截图不可用或无访问权限";
  }
}
function closeImage() {
  URL.revokeObjectURL(image.value);
  image.value = "";
}
function jump(id) {
  const e = props.room.events.find((e) => e.id === id);
  if (e?.type === "vision") showImage(e);
  document
    .getElementById(`evidence-${id}`)
    ?.scrollIntoView({ behavior: "smooth", block: "center" });
}
const time = (ms) =>
  `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, "0")}`;
const sourceLink = (source) =>
  /^https?:\/\//.test(source.url || source.source)
    ? source.url || source.source
    : null;
onUnmounted(() => {
  if (image.value) URL.revokeObjectURL(image.value);
});
</script>

<template>
  <section class="class-report" aria-labelledby="report-heading">
    <header class="report-heading">
      <div>
        <p class="eyebrow">EVIDENCE, NOT IMPRESSION</p>
        <h2 id="report-heading">课堂证据与评课</h2>
      </div>
      <span class="soft-tag"
        >{{
          {
            idle: "待生成",
            running: "生成中",
            completed: "已生成",
            failed: "生成失败",
          }[room.report_state]
        }}
        · v{{ room.report_version }}</span
      >
    </header>
    <p v-if="room.report_state === 'running'" role="status">
      正在整理真实课堂证据。可留在此页等待，也可稍后从历史课堂查看。
    </p>
    <p v-if="room.report_state === 'failed'" class="class-alert" role="alert">
      {{ room.report_error }}。不会自动生成演示分数。
    </p>
    <template v-if="room.report">
      <p v-if="room.report_state !== 'completed'" class="class-alert">
        以下为上一版报告，本次尚未生成成功。
      </p>
      <div class="score-summary">
        <strong
          >{{ room.report.overall_score ?? "—" }}<small> / 100</small></strong
        >
        <div>
          证据覆盖 {{ room.report.coverage }}
          <p>{{ room.report.notice }}</p>
        </div>
      </div>
      <div class="report-dimensions">
        <article v-for="d in room.report.dimensions" :key="d.key">
          <header>
            <h3>{{ d.label }}</h3>
            <b>{{ d.score ?? "暂不评分" }}</b>
          </header>
          <p>{{ d.reason }}</p>
          <div class="evidence-links">
            <button
              v-for="id in d.event_ids"
              :key="id"
              type="button"
              @click="jump(id)"
            >
              ↗ {{ time(room.events.find((e) => e.id === id)?.at_ms || 0) }} ·
              #{{ id }}
            </button>
          </div>
          <small v-if="d.source_ids.length"
            >资料依据：{{ d.source_ids.join("、") }}</small
          >
        </article>
      </div>
      <details class="reference-list">
        <summary>教学依据与来源（{{ room.report.sources.length }}）</summary>
        <article v-for="s in room.report.sources" :key="s.id">
          <b>{{ s.title }}</b
          ><small>{{ s.type }} · {{ s.location }} · {{ s.id }}</small>
          <p>{{ s.text }}</p>
          <a
            v-if="sourceLink(s)"
            :href="sourceLink(s)"
            target="_blank"
            rel="noopener noreferrer"
            >查看来源 ↗</a
          ><span v-else>{{ s.source }}</span>
        </article>
      </details>
    </template>
    <div v-if="room.report_state !== 'running'" class="correction-form">
      <label for="objection">教师异议（可选，结合时间点说明）</label
      ><textarea
        id="objection"
        v-model="objection"
        maxlength="2000"
        rows="3"
        placeholder="例如：02:15 我已强调平均分，请结合该段重新核对。"
      /><button
        class="class-btn"
        :disabled="busy"
        @click="$emit('regenerate', objection)"
      >
        {{ room.report ? "保存异议并重新评课" : "重试生成真实报告" }}</button
      ><small>重新调用模型并保留异议，不固定加分；会计入云调用预算。</small>
    </div>
    <p v-if="imageError" role="alert">{{ imageError }}</p>
    <div
      v-if="image"
      class="evidence-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="课堂截图证据"
      @click.self="closeImage"
      @keydown.esc="closeImage"
    >
      <div>
        <button class="class-btn" autofocus @click="closeImage">关闭截图</button
        ><img :src="image" alt="此课堂时间点的分析截图" />
      </div>
    </div>
  </section>
</template>
