<script setup>
defineProps({ label: String, active: Boolean, disabled: Boolean, align: String });
</script>
<template>
  <button type="button" class="player-icon-button" :class="{ selected: active, 'tooltip-start': align === 'start' }"
    :aria-label="label" :title="label" :disabled="disabled">
    <slot />
    <span class="player-tooltip" aria-hidden="true">{{ label }}</span>
  </button>
</template>
<style scoped>
.player-icon-button { position:relative; display:inline-flex; align-items:center; justify-content:center; width:36px; height:36px; flex:none; padding:8px; border:0; border-radius:8px; background:transparent; color:var(--class-muted); cursor:pointer; transition:background .18s,color .18s; }
.player-icon-button :deep(svg) { width:20px; height:20px; flex:none; }
.player-icon-button:hover, .player-icon-button:focus-visible { color:var(--class-ink); background:var(--class-hover); }
.player-icon-button.selected { color:var(--class-orange-text); background:#ff7a1812; }
.player-icon-button:disabled { opacity:.4; cursor:not-allowed; }
.player-tooltip { display:none; position:absolute; bottom:calc(100% + 8px); right:0; padding:5px 9px; border:1px solid var(--line); border-radius:6px; background:var(--class-surface-raised); color:var(--class-ink); white-space:nowrap; font-size:11px; line-height:1.5; pointer-events:none; z-index:20; }
.tooltip-start .player-tooltip { left:0; right:auto; }
.player-icon-button:hover .player-tooltip, .player-icon-button:focus-visible .player-tooltip { display:block; }
</style>
