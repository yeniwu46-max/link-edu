<script setup>
import { ref } from 'vue';
import { Volume, Volume3, Settings, Maximize, Minimize } from '@vicons/tabler';
import ClassroomIconButton from './ClassroomIconButton.vue';
defineProps({
  volume: Number, resolution: Number, resolutionBusy: Boolean, captions: Boolean,
  expanded: Boolean, settingsOpen: Boolean, progress: Number, timeLabel: String,
});
const emit = defineEmits(['volume','resolution','captions','settings','fullscreen']);
const rememberedVolume = ref(1);
// Mute is presentation-only and does not stop teacher microphone capture.
function toggleMute(volume) {
  if (volume > 0) rememberedVolume.value = volume;
  emit('volume', volume > 0 ? 0 : rememberedVolume.value);
}
</script>
<template>
  <div class="player-console">
    <div class="lesson-progress" aria-hidden="true"><span :style="{ width: `${progress}%` }" /></div>
    <div class="camera-bar" role="group" aria-label="课堂播放控制">
      <div class="player-session-controls">
        <slot name="transport" />
        <span class="player-time">{{ timeLabel }}</span>
        <slot name="actions" />
      </div>
      <div class="player-options">
        <div class="player-volume">
          <ClassroomIconButton align="start" :label="volume ? '静音学生声音' : '恢复学生声音'" @click="toggleMute(volume)"><Volume v-if="volume" /><Volume3 v-else /></ClassroomIconButton>
          <input type="range" aria-label="上课音量" :title="`音量 ${Math.round(volume*100)}%`" min="0" max="1" step="0.05" :value="volume" @input="emit('volume', $event.target.value)" />
        </div>
        <ClassroomIconButton label="课堂字幕" :active="captions" :aria-pressed="captions" @click="emit('captions', !captions)"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="3" stroke="currentColor" stroke-width="1.6"/><path d="M10 10a2.5 2.5 0 1 0 0 4m8-4a2.5 2.5 0 1 0 0 4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></ClassroomIconButton>
        <label class="player-resolution" title="画面分辨率">
          <select aria-label="画面分辨率" :value="resolution" :disabled="resolutionBusy" @change="emit('resolution', $event.target.value)">
            <option :value="1020">1020p</option><option :value="720">720p</option><option :value="360">360p</option>
          </select>
        </label>
        <span class="player-speed" title="学生语音以 1.2 倍速播放">1.2×</span>
        <slot name="utilities" />
        <ClassroomIconButton label="课堂设置" :active="settingsOpen" :aria-expanded="settingsOpen" aria-haspopup="dialog" @click="emit('settings')"><Settings /></ClassroomIconButton>
        <ClassroomIconButton :label="expanded ? '退出全屏' : '全屏放大'" @click="emit('fullscreen')"><Minimize v-if="expanded" /><Maximize v-else /></ClassroomIconButton>
      </div>
    </div>
  </div>
</template>
<style scoped>
.player-console { flex:none; position:relative; background:var(--class-surface); }
.lesson-progress { height:2px; overflow:hidden; background:var(--line); }
.lesson-progress span { display:block; height:100%; background:var(--orange); transition:width .35s linear; }
.camera-bar { display:flex; justify-content:space-between; align-items:center; gap:12px; height:56px; padding:0 12px; }
.player-session-controls, .player-options { display:flex; align-items:center; gap:4px; min-width:0; }
.player-session-controls { flex:1; }
.player-options { flex:none; }
.player-time { margin-inline:8px; white-space:nowrap; font:11px/1 ui-monospace,monospace; font-variant-numeric:tabular-nums; color:var(--class-muted); }
.player-volume { display:flex; align-items:center; }
.player-volume input { width:52px; height:20px; margin:0 8px 0 0; accent-color:var(--orange); cursor:pointer; }
.player-resolution select { width:72px; border:0; border-radius:6px; padding:6px 2px; background:var(--class-surface); color:var(--class-ink); font:12px/1.5 inherit; cursor:pointer; }
.player-speed { font:11px/1 ui-monospace,monospace; color:var(--class-muted); padding:0 8px; }
@media(max-width:1100px) { .player-time { display:none; } .player-speed { display:none; } .camera-bar { gap:4px; padding-inline:8px; } }
@media(max-width:700px) {
  .camera-bar { height:auto; min-height:100px; flex-direction:column; align-items:stretch; justify-content:center; gap:4px; padding:4px; }
  .player-session-controls { justify-content:space-between; flex:none; height:44px; }
  .player-time { display:block; margin-right:auto; }
  .player-options { justify-content:space-between; min-height:40px; height:auto; gap:0; flex-wrap:wrap; }
  .player-volume input { width:36px; margin-right:0; }
  .player-resolution select { width:64px; }
}
</style>
