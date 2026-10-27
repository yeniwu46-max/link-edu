<script setup>
import { computed } from 'vue'
import { useUiVersion } from '../utils/uiVersion.js'
const { isStudio } = useUiVersion()
const props = defineProps({ text: { type: String, required: true }, as: { type: String, default: 'h1' }, legacyText:String, legacyVisible:Boolean })
const glyphs = computed(() => Array.from(props.text))
</script>
<template>
  <component v-if="!isStudio || !legacyVisible" :is="as" :class="{ 'sr-only': isStudio && !legacyVisible }">{{ legacyText || text }}</component>
  <component v-else :is="as" class="paper-title" :aria-label="text" tabindex="0">
    <span class="paper-title__text" aria-hidden="true"><span v-for="(glyph, i) in glyphs" :key="i" class="paper-title__letter" :class="{ 'paper-title__accent': i > 0 && i % 5 === 0 }" :style="{ '--tilt': `${[-2, 1, -1, 2, 0][i % 5]}deg`, '--delay': `${Math.min(i * 23, 260)}ms` }">{{ glyph === ' ' ? '\u00a0' : glyph }}</span></span>
  </component>
</template>
<style scoped>
.paper-title { --paper-face:#fff1d8; --paper-edge:#9e81b5; position:relative; margin:0 0 24px; padding:6px 2px 10px; color:var(--paper-face); font-family:'Microsoft YaHei UI','PingFang SC',sans-serif; font-weight:900; font-size:clamp(40px,3.8vw,60px); line-height:1.28; letter-spacing:.025em; overflow-wrap:anywhere; text-wrap:balance; }
.paper-title:focus-visible { outline:2px solid #ffcb86; outline-offset:7px; border-radius:8px; }
.paper-title__text { position:relative; z-index:1; }
.paper-title__letter { position:relative; display:inline-block; white-space:pre; text-shadow:1px 1px var(--paper-edge),2px 2px var(--paper-edge),3px 3px #6d527f,4px 5px 0 #24162b40; transform:rotate(var(--tilt)); animation:paper-arrive .5s cubic-bezier(.2,.8,.2,1) backwards; animation-delay:var(--delay); transition:transform .24s cubic-bezier(.2,.8,.2,1); }
.paper-title__accent { color:#cdb3e4; }
.paper-title__accent::after { content:''; position:absolute; z-index:-1; height:18%; left:-3%; right:-7%; bottom:1%; background:#f6b76c; transform:rotate(-4deg); clip-path:polygon(0 0,100% 0,94% 75%,100% 100%,0 100%); }
.paper-title:hover .paper-title__letter:nth-child(3n),.paper-title:focus-visible .paper-title__letter:nth-child(3n) { transform:translateY(-3px) rotate(var(--tilt)); }
:global([data-ui-theme='academy']) .paper-title { --paper-face:#fbfdff; --paper-edge:#829bb9; color:#f8fbff; text-shadow:0 0 1px #3c546e; }
:global([data-ui-theme='academy']) .paper-title__accent { color:#c3dbef; }
@keyframes paper-arrive { from { opacity:0; transform:translateY(9px) rotate(-4deg); } to { opacity:1; transform:rotate(var(--tilt)); } }
@media(max-width:700px) { .paper-title { font-size:clamp(28px,7.5vw,36px); margin-bottom:16px; } }
@media(prefers-reduced-motion:reduce) { .paper-title__letter { animation:none; transition:none; } .paper-title:hover .paper-title__letter,.paper-title:focus-visible .paper-title__letter { transform:rotate(var(--tilt)); } }
</style>
