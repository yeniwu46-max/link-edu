<script setup>
import { ref, nextTick, onUnmounted } from "vue";
import { api } from "../services/api";
const props = defineProps({ room: Object, busy: Boolean });
const emit = defineEmits(["regenerate", "jump"]);
const imageDialog = ref(null);
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
    await nextTick();
    imageDialog.value?.showModal();
  } catch {
    imageError.value = "截图不可用或无访问权限";
  }
}
function closeImage() {
  imageDialog.value?.close();
  URL.revokeObjectURL(image.value);
  image.value = "";
}
function jump(id) {
  emit("jump", id);
  const e = props.room.events.find((e) => e.id === id);
  if (e?.type === "vision") showImage(e);
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
        <h2 id="report-heading">课堂评课</h2>
      </div>
      <span class="soft-tag"
        >{{
          {
            idle: "待生成",
            running: "生成中",
            completed: "已生成",
            failed: "生成失败",
            insufficient: "数据不足 · 未生成",
          }[room.report_state]
        }}
      </span>
    </header>
    <p v-if="room.report_state === 'running'" role="status">
      正在生成报告，可稍后在历史课堂查看。
    </p>
    <p v-if="room.report_state === 'failed'" class="class-alert" role="alert">
      {{ room.report_error || "报告生成失败，请重试。" }}
    </p>
    <div v-if="room.report_state === 'insufficient'" class="report-blocked" role="status">
      <h3>本次课堂数据不足，未生成 AI 评课报告</h3>
      <p>没有调用评审 AI，也没有生成替代分数。以下缺项需要在下一次授课中补足：</p>
      <ul><li v-for="reason in room.report_readiness?.reasons || [room.report_error]" :key="reason">{{ reason }}</li></ul>
      <p class="subtle-note">{{ room.report_readiness?.notice }}</p>
    </div>
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
          <p>AI 辅助评价 · 仅对有证据的维度评分</p>
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
              ↗ {{ time(room.events.find((e) => e.id === id)?.at_ms || 0) }}
            </button>
          </div>
        </article>
      </div>
      <details v-if="room.report.motion_evidence?.sample_count" class="reference-list">
        <summary>教态动作证据 · 身体 / 手势 / 面部（{{ room.report.motion_evidence.observed_samples }} 个有效样本）</summary>
        <p v-if="room.report.motion_evidence.status !== 'observed'">有效动作证据不足，不能据此给出教态评分。</p>
        <p v-for="(m, name) in room.report.motion_evidence.modalities" :key="name">
          {{ {body:'身体', hands:'手势', face:'面部'}[name] }}：{{ m.observed_samples }}/{{ m.total_samples }} 个样本可观察
        </p>
        <article v-for="o in room.report.motion_evidence.observations" :key="o.code">
          <b>{{ o.description }}</b>
          <p>{{ o.matched_samples }}/{{ o.observed_samples }} 个有效样本出现该线索；连续采样跨度 {{ (o.longest_observed_span_ms / 1000).toFixed(1) }} 秒（非持续动作测量）。</p>
          <p>{{ o.suggestion }}</p>
          <div class="evidence-links"><button v-for="id in o.event_ids" :key="id" type="button" @click="jump(id)">
            ↗ {{ time(room.events.find(e => e.id === id)?.at_ms || 0) }}
          </button></div>
        </article>
        <p v-for="note in room.report.motion_evidence.limitations" :key="note">{{ note }}</p>
      </details>
      <details class="reference-list">
        <summary>教学依据与来源（{{ room.report.sources.length }}）</summary>
        <article v-for="s in room.report.sources" :key="s.id">
          <b>{{ s.title }}</b
          ><small>{{ s.type }} · {{ s.location }}</small>
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
    <div v-if="!['running','insufficient'].includes(room.report_state)" class="correction-form">
      <label for="objection">补充说明（可选）</label
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
        {{
          room.report
            ? "重新评课"
            : room.report_state === "failed"
              ? "重试生成"
              : "生成报告"
        }}</button
      ><small>生成报告会消耗授课额度</small>
    </div>
    <p v-if="imageError" role="alert">{{ imageError }}</p>
    <dialog
      v-if="image"
      ref="imageDialog"
      class="evidence-overlay"
      aria-label="课堂截图证据"
      @click.self="closeImage"
      @cancel.prevent="closeImage"
      @keydown.tab.prevent="imageDialog?.querySelector('button')?.focus()"
    >
      <div>
        <button class="class-btn" autofocus @click="closeImage">关闭截图</button
        ><img :src="image" alt="此课堂时间点的分析截图" />
      </div>
    </dialog>
  </section>
</template>

<style scoped>
.report-blocked { padding:16px; border:1px solid var(--line); border-radius:12px; background:var(--class-surface-raised); }
.report-blocked h3 { color:var(--class-orange-text); margin-bottom:8px; }
.report-blocked p, .report-blocked li { font-size:13px; line-height:1.8; }
.report-blocked ul { margin:12px 0; padding-left:20px; }
.report-blocked li + li { margin-top:8px; }
</style>
