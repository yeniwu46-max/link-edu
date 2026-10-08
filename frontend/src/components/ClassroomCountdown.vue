<script setup>
import { computed } from 'vue';
import NumberFlow, { NumberFlowGroup } from '@number-flow/vue';
import { useReducedMotion } from '../utils/useReducedMotion.js';
const reducedMotion = useReducedMotion();
const props = defineProps({ seconds: {type:Number, default:600} });
const remaining = computed(() => Math.max(0, Math.ceil(Number(props.seconds) || 0)));
const minutes = computed(() => Math.floor(remaining.value / 60));
const seconds = computed(() => remaining.value % 60);
const format = {minimumIntegerDigits:2, maximumFractionDigits:0, useGrouping:false};
const timing = computed(() => ({duration:reducedMotion.value ? 0 : 350, easing:'ease-out'}));
</script>
<template>
  <div class="classroom-countdown" :class="{urgent:remaining <= 30}" role="timer"
    :aria-label="`剩余时间 ${minutes} 分 ${seconds} 秒`" aria-live="off">
    <small>剩余时间</small>
    <div class="countdown-digits" aria-hidden="true">
      <NumberFlowGroup>
        <NumberFlow :value="minutes" :format="format" locales="en-US" :trend="-1" :transform-timing="timing" />
        <span>:</span>
        <NumberFlow :value="seconds" :format="format" :digits="{1:{max:5}}" locales="en-US" :trend="-1" :transform-timing="timing" />
      </NumberFlowGroup>
    </div>
  </div>
</template>
<style scoped>
.classroom-countdown { display:grid; justify-items:end; color:#fff; flex:none; }
.classroom-countdown small { font-size:10px; color:#d3ccd9; letter-spacing:.08em; }
.countdown-digits { display:flex; align-items:center; gap:2px; font:500 clamp(24px,3vw,40px)/1 ui-monospace,monospace; font-variant-numeric:tabular-nums; min-width:5ch; }
.urgent .countdown-digits { color:var(--class-orange-text,#ffb575); }
</style>
