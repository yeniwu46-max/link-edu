<script setup>
import { useId } from 'vue'
const gradient = useId()
defineProps({ attentive:Boolean })
</script>
<template>
  <svg class="help-robot-icon" :class="{attentive}" viewBox="0 0 64 64" fill="none" aria-hidden="true">
    <defs><linearGradient :id="gradient" x1="8" y1="8" x2="58" y2="60" gradientUnits="userSpaceOnUse"><stop stop-color="#b98aff"/><stop offset="1" stop-color="#ff923c"/></linearGradient></defs>
    <path d="M32 9V5" stroke="#dfb5ff" stroke-width="2" stroke-linecap="round"/><circle cx="32" cy="4" r="2.5" fill="#ffac6a"/>
    <rect x="11" y="12" width="42" height="39" rx="14" :fill="`url(#${gradient})`"/>
    <rect x="16" y="18" width="32" height="25" rx="10" fill="#181020"/>
    <rect x="6" y="25" width="5" height="13" rx="2.5" fill="#b98aff"/><rect x="53" y="25" width="5" height="13" rx="2.5" fill="#ffa060"/>
    <g class="robot-eyes"><rect x="22" y="25" width="4" height="7" rx="2" fill="#dab7ff"/><rect x="38" y="25" width="4" height="7" rx="2" fill="#ffc594"/></g>
    <path d="M28 36Q32 40 36 36" stroke="#e9c7ff" stroke-width="2" stroke-linecap="round"/>
    <path d="M24 52H40L44 58H20L24 52Z" :fill="`url(#${gradient})`"/><circle cx="32" cy="55" r="1.5" fill="#21142a"/>
  </svg>
</template>
<style scoped>
.help-robot-icon { width:100%; height:100%; overflow:visible; }
.robot-eyes { transform-origin:32px 28px; transition:transform .2s; }
.attentive .robot-eyes { transform:translateY(-1px) scaleY(.8); }
@media(prefers-reduced-motion:reduce) { .robot-eyes { transition:none; } }
</style>
