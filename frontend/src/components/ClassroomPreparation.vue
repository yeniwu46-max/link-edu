<script setup>
import { computed } from 'vue'
import ClassroomDialog from './ClassroomDialog.vue'
import ClassroomCalibration from './ClassroomCalibration.vue'
import { speechProviderLabel } from '../services/classroomStatus.js'
const open = defineModel({ type: Boolean })
const consent = defineModel('consent', { type: Boolean })
const cameraConsent = defineModel('cameraConsent', { type: Boolean })
const recordEnabled = defineModel('recordEnabled', { type: Boolean })
const mode = defineModel('mode', { type: String })
const props = defineProps({ capabilities: Object, practicePlan: Object, room: Object, state: String,
  busy: Boolean, active: Boolean, cameraEnabled: Boolean, pose: Object, blockers: Array,
  hint: String, loading: Boolean, needsSettings: Boolean })
defineEmits(['start', 'preview', 'refresh', 'settings'])
const asr = computed(() => props.capabilities?.services?.asr?.provider)
const llm = computed(() => props.capabilities?.services?.dialogue?.provider === 'openai_next' ? 'OpenAI Next（DeepSeek 模型）' : 'DeepSeek')
</script>
<template>
  <ClassroomDialog v-model="open" title="课前准备">
    <div class="classroom-preparation">
      <div class="preparation-topic"><div><small>{{ capabilities?.scenario?.grade || '小学数学' }}</small><h3>{{ capabilities?.scenario?.topic || '分数的初步认识' }}</h3></div>
        <label v-if="!room" class="lesson-mode"><span class="sr-only">训练时长</span><select id="class-mode" v-model="mode" :disabled="busy"><option value="full">10 分钟 · 完整课</option><option value="fragment">8 分钟 · 专项练习</option></select></label>
      </div>
      <section v-if="state !== 'ended'" class="preparation-permissions" aria-label="设备与授权">
        <h3>设备与授权</h3>
        <label><input type="checkbox" v-model="consent" :disabled="active || busy" />同意语音识别与 AI 评课</label>
        <label><input type="checkbox" v-model="cameraConsent" :disabled="active || busy" />同意摄像头开启</label>
        <label><input type="checkbox" v-model="recordEnabled" :disabled="!!room || busy" />本机录像<span>课后选择保存或放弃</span></label>
        <button class="class-btn secondary" :disabled="!cameraConsent || busy || active" @click="$emit('preview')">{{ cameraEnabled ? '查看授课画面' : '开启摄像头预览' }}</button>
      </section>
      <details class="disclosure privacy-details"><summary>隐私与录像说明</summary>
        <p>麦克风音频上传{{ speechProviderLabel(asr) }}识别；文字与本地动作摘要提交{{ llm }}用于对话和评课。未选择录像时不保存原始录音，转写与课堂事件会保留。</p>
        <p>本机录像包含教师画面、学生、字幕和师生声音，不上传服务器；课后选择保存或放弃。清理浏览器数据会移除已保存录像，下载副本需自行保管。</p>
        <p>摄像头为授课必需条件，仍须浏览器授权。动作检测在本机运行，不做人脸识别或心理推断。云端截图分析需另行授权。</p>
        <p>暂停同时停止计时和录像。有效授课满 10 秒且转写、完整学生反馈充足才评课；动作或场景不足时教态不评分。</p>
      </details>
      <details v-if="capabilities?.scenario" class="disclosure preparation-scenario"><summary>训练目标与学生设定</summary>
        <p>{{ capabilities.scenario.objective }}</p>
        <ul><li v-for="(student,id) in capabilities.scenario.students" :key="id"><strong>{{ { ming:'小明', yu:'小雨', lin:'小林' }[id] }}</strong><span>{{ student.focus }}</span></li></ul>
        <p class="subtle-note">这些是模拟学生的初始设定，状态变化用于训练复盘，不代表真实儿童的学习测量。</p>
      </details>
      <section v-if="practicePlan" class="preparation-practice" aria-label="本次复练任务"><h3>本次复练任务</h3><p>{{ practicePlan.task_text }}</p><p>完成判据：本节至少记录 {{ practicePlan.criteria?.minimum_observed || 1 }} 次目标行为。</p><small>来自课堂 #{{ practicePlan.source_session_id }}，完成后可返回原报告核对。</small></section>
      <ClassroomCalibration :enabled="cameraEnabled" :active="active" :motion="pose" />
      <section v-if="!room || ['paused','disconnected'].includes(state)" class="preparation-readiness" aria-label="开课检查">
        <p role="status">{{ hint }}</p>
        <ul v-if="blockers?.length"><li v-for="reason in blockers" :key="reason.code">{{ reason.message }}</li></ul>
        <div class="preparation-actions"><button class="text-action" :disabled="loading || busy" @click="$emit('refresh')">{{ loading ? '读取中…' : '刷新设备与服务状态' }}</button><button v-if="needsSettings" class="text-action" @click="$emit('settings')">查看配置</button></div>
      </section>
      <footer class="preparation-footer"><button class="class-btn secondary" @click="open = false">返回课堂</button><button v-if="!active && state !== 'ended'" class="class-btn" :disabled="blockers?.length > 0 || busy" @click="$emit('start')">{{ room ? '继续授课' : '开始授课' }}</button></footer>
    </div>
  </ClassroomDialog>
</template>
<style scoped>
.classroom-preparation { display:grid; gap:16px; }
.preparation-topic { display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; }
.preparation-topic h3 { margin:4px 0 0; font-size:20px; }
.preparation-topic small { color:var(--class-muted); }
.preparation-permissions { display:grid; gap:8px; padding:16px; border:1px solid var(--line); border-radius:12px; background:linear-gradient(135deg,#b45cff0d,#ff7a1808); }
.preparation-permissions h3 { margin:0 0 4px; }
.preparation-permissions label { display:flex; align-items:center; gap:8px; min-height:32px; font-size:13px; flex-wrap:wrap; }
.preparation-permissions label span { font-size:11px; color:var(--class-muted); }
.preparation-permissions button { justify-self:start; }
.preparation-scenario ul { display:grid; gap:8px; padding:0; list-style:none; }
.preparation-scenario li { display:flex; gap:12px; font-size:12px; }
.preparation-scenario li strong { flex:none; color:var(--class-ink); }
.preparation-scenario li span { color:var(--class-muted); }
.preparation-readiness { border-top:1px solid var(--line); padding-top:12px; font-size:12px; }
.preparation-readiness ul { color:var(--class-muted); padding-left:20px; }
.preparation-actions,.preparation-footer { display:flex; flex-wrap:wrap; gap:12px; }
.preparation-footer { justify-content:flex-end; padding-top:8px; }
.preparation-practice { padding:12px; background:var(--class-surface-raised); border-radius:8px; font-size:13px; }
@media(max-width:480px) { .preparation-permissions { padding:12px; } }
</style>
