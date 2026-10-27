<script setup>
import { computed, ref, useId } from 'vue'
import { DESK_SKILLS } from '../services/courseDesk.js'
const props = defineProps({ selected: String, available: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
const hovered = ref(null), failed = ref(false), uid = useId().replace(/[^a-z0-9]/gi,'')
const enabled = id => props.available.includes(id)
const illuminated = computed(() => hovered.value || props.selected)
const select = id => { if (enabled(id)) emit('select', id) }
function move(event, index) {
  if (!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key)) return
  event.preventDefault()
  const buttons = [...event.currentTarget.parentElement.querySelectorAll('button:not(:disabled)')]
  const i = buttons.indexOf(event.currentTarget)
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (i + (['ArrowLeft','ArrowUp'].includes(event.key) ? -1 : 1) + buttons.length) % buttons.length
  buttons[next]?.focus()
}
</script>
<template>
  <div class="course-desk" :class="{'course-desk--fallback': failed}" data-testid="course-desk">
    <img class="course-desk__texture" src="/assets/desk/prep-desk.png" width="1672" height="941" alt="铺有教案本、黑板、投影仪和教学文具的备课桌" fetchpriority="high" @error="failed = true" />
    <svg v-if="!failed" class="course-desk__objects" viewBox="0 0 1000 563" preserveAspectRatio="none" aria-hidden="true">
      <defs><filter :id="`${uid}-glow`"><feGaussianBlur stdDeviation="2" /></filter>
        <clipPath v-for="skill in DESK_SKILLS" :id="`${uid}-${skill.id}`" :key="skill.id"><polygon :points="skill.points" /></clipPath>
      </defs>
      <g v-for="skill in DESK_SKILLS" :key="skill.id" :class="{ 'is-lit': illuminated === skill.id && enabled(skill.id), 'is-disabled': !enabled(skill.id) }">
        <image class="desk-object-light" href="/assets/desk/prep-desk.png" width="1000" height="563" :clip-path="`url(#${uid}-${skill.id})`" />
        <polygon class="desk-object-halo" :points="skill.points" :filter="`url(#${uid}-glow)`" />
        <polygon class="desk-object-edge" :points="skill.points" />
        <polygon class="desk-object-hit" :points="skill.points" @pointerenter="hovered = enabled(skill.id) ? skill.id : null" @pointerleave="hovered = null" @click="select(skill.id)" />
      </g>
    </svg>
    <div class="course-desk__labels" role="group" aria-label="选择教学技能">
      <button v-for="(skill,i) in DESK_SKILLS" :key="skill.id" type="button" :style="{'--x':`${skill.x}%`, '--y':`${skill.y}%`}" :class="{'is-selected':selected === skill.id}" :disabled="!enabled(skill.id)" :aria-pressed="selected === skill.id" :aria-label="`${skill.label} · ${skill.object}${enabled(skill.id) ? '' : '（暂无匹配课程）'}`" @focus="hovered = skill.id" @blur="hovered = null" @pointerenter="hovered = skill.id" @pointerleave="hovered = null" @keydown="move($event, i)" @click="select(skill.id)">{{ skill.label }}</button>
    </div>
  </div>
</template>
<style scoped>
.course-desk { position:relative; isolation:isolate; aspect-ratio:1000/563; overflow:hidden; border-radius:22px; background:#3b2c2a; }
.course-desk__texture,.course-desk__objects { position:absolute; inset:0; width:100%; height:100%; object-fit:fill; }
.course-desk__objects { pointer-events:none; }
.desk-object-light { opacity:0; filter:brightness(1.22) saturate(1.08); transition:opacity .22s; }
.desk-object-edge,.desk-object-halo { fill:none; stroke:#ffd18a; stroke-width:1.5; stroke-linejoin:round; opacity:0; transition:opacity .22s; }
.desk-object-halo { stroke-width:5; }
.desk-object-hit { fill:transparent; pointer-events:all; cursor:pointer; }
.is-disabled .desk-object-hit { pointer-events:none; }
.is-lit .desk-object-light { opacity:.7; }
.is-lit .desk-object-edge,.is-lit .desk-object-halo { opacity:1; }
.course-desk__labels { position:absolute; inset:0; pointer-events:none; }
.course-desk__labels button { position:absolute; left:var(--x); top:var(--y); transform:translate(-50%,-50%); pointer-events:auto; border:0; color:#fff4df; background:#261b2bce; border-radius:20px; padding:7px 14px; font-size:clamp(12px,1.3vw,18px); font-weight:650; min-height:36px; box-shadow:0 2px 12px #1d12132b; transition:transform .22s cubic-bezier(.2,.8,.2,1),background .22s; }
.course-desk__labels button:hover,.course-desk__labels button:focus-visible { background:#f8c07f; color:#34213e; transform:translate(-50%,calc(-50% - 3px)); }
.course-desk__labels button:focus-visible { outline:3px solid white; outline-offset:3px; }
.course-desk__labels button.is-selected { background:#f6bd7e; color:#302033; }
.course-desk__labels button:disabled { opacity:.42; cursor:default; }
.course-desk--fallback { min-height:240px; aspect-ratio:auto; }
.course-desk--fallback .course-desk__texture { display:none; }
.course-desk--fallback .course-desk__labels { position:relative; display:flex; flex-wrap:wrap; gap:12px; padding:30px; }
.course-desk--fallback .course-desk__labels button { position:static; transform:none; }
@media(max-width:700px) {
 .course-desk { overflow:visible; border-radius:14px; padding-bottom:104px; aspect-ratio:auto; }
 .course-desk__texture { position:relative; display:block; aspect-ratio:1000/563; height:auto; border-radius:14px 14px 0 0; }
 .course-desk__objects { height:auto; aspect-ratio:1000/563; }
 .course-desk__labels { inset:auto 10px 10px; display:grid; grid-template-columns:repeat(5,1fr); gap:5px; }
 .course-desk__labels button { position:static; transform:none!important; min-height:42px; padding:4px 0; font-size:13px; border-radius:8px; }
}
@media(prefers-reduced-motion:reduce) { .course-desk * { transition:none!important; } }
</style>
