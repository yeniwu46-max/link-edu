<script setup>
import { computed } from "vue";
import { connectionSummary } from "../services/classroomStatus.js";
const props = defineProps({
  capabilities: Object,
  probing: String,
  active: Boolean,
});
defineEmits(["probe", "refresh"]);
const services = {
  dialogue: "对话与评课",
  asr: "语音识别",
  tts: "学生语音",
  vision: "画面理解",
};
const budget = computed(() => props.capabilities?.budget);
const accounts = computed(() =>
  ["dialogue", "vision", "test"]
    .map((key) => budget.value?.credits?.accounts?.[key])
    .filter(Boolean),
);
</script>

<template>
  <div class="settings-content">
    <div class="section-title">
      <h3>连接检查</h3>
      <button class="text-action" type="button" @click="$emit('refresh')">
        刷新状态
      </button>
    </div>
    <p class="subtle-note">{{ capabilities?.can_probe === false ? "服务状态由管理员维护，刷新不会发起付费检查。" : "检查会消耗少量额度" }}</p>
    <div class="service-grid">
      <article v-for="(label, key) in services" :key="key">
        <div class="service-heading">
          <span>{{ label }}</span
          ><b :class="connectionSummary(capabilities?.services, [key]).tone">{{
            connectionSummary(capabilities?.services, [key]).label
          }}</b>
        </div>
        <small
          >{{ capabilities?.services?.[key]?.provider || "—" }} ·
          {{ capabilities?.services?.[key]?.model || "—" }}</small
        >
        <p
          v-if="capabilities?.services?.[key]?.status === 'failed'"
          class="service-error"
        >
          {{ capabilities.services[key].message || "暂时无法连接，请重试。" }}
        </p>
        <button
          v-if="capabilities?.can_probe !== false"
          class="class-btn secondary"
          type="button"
          :aria-label="`检查${label}`"
          :disabled="
            active ||
            !!probing ||
            !capabilities?.services?.[key]?.configured ||
            !capabilities?.services?.[key]?.pricing_confirmed
          "
          @click="$emit('probe', key)"
        >
          {{ probing === key ? "检查中…" : "检查连接" }}
        </button>
      </article>
    </div>
    <p class="subtle-note">
      身体模型：{{ capabilities?.pose_assets ? "文件已安装" : "未安装" }} ·
      手势模型：{{ capabilities?.motion_assets?.hands ? "文件已安装" : "未安装" }} ·
      面部模型：{{ capabilities?.motion_assets?.face ? "文件已安装" : "未安装" }}。
      加载和检测结果以镜头状态为准。
    </p>
    <details class="disclosure technical-info">
      <summary>检查说明</summary>
      <p>
        连接检查不代表设备已启用。语音识别检查仅验证连接，识别效果需在授课时确认。
      </p>
      <p v-if="capabilities?.services?.dialogue?.provider === 'openai_next'">
        文字与视觉检查使用测试额度；课堂使用各自的授课与视觉额度。
      </p>
    </details>
    <h3 class="settings-subtitle">额度详情</h3>
    <template v-if="capabilities?.can_probe === false">
      <p>每日 {{ capabilities?.quota?.daily_limit }} 场，今日剩余 {{ capabilities?.quota?.remaining_today }} 场；每场最长10分钟。</p>
      <p>同时开放 {{ capabilities?.capacity?.limit }} 间课堂，当前空闲 {{ capabilities?.capacity?.available }} 间。</p>
      <p>{{ budget?.stopped ? '体验额度暂已用完，已有报告仍可查看。' : '体验额度由平台提供，以进入课堂时的检查结果为准。' }}</p>
    </template>
    <template v-else-if="budget">
      <div
        v-for="account in accounts"
        :key="account.label"
        class="budget-summary"
        :class="{ warning: account.warning }"
      >
        <div>
          <span>{{ account.label }}</span
          ><strong
            >${{ account.spent_and_reserved_usd.toFixed(4) }}
            <small>/ ${{ account.limit_usd }}</small></strong
          >
        </div>
        <progress
          :value="account.spent_and_reserved_usd"
          :max="account.limit_usd || 1"
          :aria-label="`${account.label}美元用量`"
        />
        <small
          >{{ account.stopped ? "已达停止线" : "美元估算" }} · ${{
            account.stop_usd
          }}
          停止新调用</small
        >
      </div>
      <div class="budget-summary">
        <div>
          <span>{{ accounts.length ? "语音及历史用量" : "调用用量" }}</span
          ><strong
            >¥{{ budget.spent_and_reserved_cny?.toFixed(3) || "0.000" }}
            <small>/ ¥{{ budget.limit_cny }}</small></strong
          >
        </div>
        <small>人民币估算 · ¥{{ budget.stop_cny }} 停止新调用</small>
      </div>
      <p class="subtle-note">
        含在途预留，80% 提醒、90% 停止。实际扣费以服务商账单为准。
      </p>
    </template>
    <p v-else class="subtle-note">额度暂不可用，请刷新状态。</p>
  </div>
</template>
