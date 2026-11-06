<script setup>
import { computed, ref, onBeforeUnmount, watch } from 'vue';
import { ArrowUpRight, Focus2, ListDetails, ShieldCheck, Bulb, Photo, Refresh, Printer } from '@vicons/tabler';
import { api } from '../services/api';
import { buildReview, formatReportTime as time, formatReportDate } from '../services/classroomReview.js';
import { fetchRagChunk } from '../services/rag.js';
import { eventLabel, eventText } from '../services/classroomStatus.js';
import ClassroomDialog from './ClassroomDialog.vue';
import ClassroomReplay from './ClassroomReplay.vue';
const props=defineProps({room:Object,busy:Boolean});
const emit=defineEmits(['regenerate','plans-created','refresh','print']);
const view=computed(()=>buildReview(props.room));
const linkedCoachCount=computed(()=>view.value.coachingFocuses.filter(item=>item.evidence.length).length);
const status=computed(()=>({idle:'待评课',running:'评课进行中',completed:'已完成',failed:'生成失败',insufficient:'证据不足 · 未生成'}[props.room.report_state]||'待评课'));
const drawerOpen=ref(false), drawerTitle=ref('课堂证据'), evidence=ref([]), filter=ref('');
const playbackEvent=ref(null);
const reportStage=computed(()=>({checking:'检查最低证据',preparing:'整理课堂证据',judging:'AI 评审中',validating:'校验评审结果',completed:'完成',failed:'生成失败'}[props.room.report_stage]||'等待评审状态'));
const imageOpen=ref(false), image=ref(''), imageError=ref(''), imageLoading=ref(false), objection=ref('');
const kbOpen=ref(false), kbLoading=ref(false), kbError=ref(''), kbChunk=ref(null), kbDocument=ref(null), kbEvidence=ref([]);
let imageRequest=0;
const filtered=computed(()=>evidence.value.filter(e=>!filter.value || `${eventLabel(e)} ${eventText(e)} #${e.id} ${time(e.at_ms)}`.includes(filter.value.trim())));
const motion=computed(()=>props.room.report?.motion_evidence);
const sources=computed(()=>props.room.report?.sources||[]);
const behaviorLabels={teacher_question:'教师提问',student_response:'学生完整回应',question_response:'提问与回应',teacher_followup:'教师追问',teacher_feedback:'教师反馈',teacher_summary:'课堂小结',post_question_silence:'提问后的静默间隔',board_observation:'可见板书',board_speech_context:'板书与授课发言',motion_speech_context:'动作与授课发言'};
const behaviors=computed(()=>props.room.behavior_analysis?.segments||[]);
function behaviorEvents(segment){return view.value.events.filter(event=>segment.event_ids?.includes(event.id));}
function evidenceExplanation(event){
  const text=eventText(event);
  const messages={
    teacher:'这是一条教师课堂表达记录。下方教学话语标签由原话规则匹配生成，只用于定位可能的话语行为；声音线索是本机音量/基频描述，不代表情绪识别结论。请结合录像和上下文复核。',
    student:'这是一条学生回应记录，可用于判断学生是否有参与、回应是否完整，以及教师是否继续追问。',
    vision:'这是一条画面观察记录，用于说明该时刻检测到的可见板书、动作或课堂场景信息。',
    playback:'这是一条课堂播放记录，可用于核对学生回应是否被完整播放。',
    teacher_question:'这是一条教师提问事件，可用于分析问题设计和课堂互动。',
    student_state_transition:'这是一次模拟学生状态变化，表示课堂互动后虚拟学生的理解状态发生了更新。'
  };
  return messages[event.type]||'这是一条已保存的课堂事件，建议结合视频画面和前后文一起复核。';
}
const evidenceStatusLabel=status=>({supported:'有课堂证据',partial:'部分证据',insufficient:'证据不足'}[status]||'待复核');
const transitions=computed(()=>view.value.events.filter(event=>event.type==='student_state_transition'));
const studentNames={ming:'小明',yu:'小雨',lin:'小林'};
const plans=computed(()=>props.room.practice_plans||[]);
const activePractice=computed(()=>props.room.active_practice_plan);
const activePracticeEvidence=computed(()=>{
  const ids=new Set((activePractice.value?.comparison?.retest_event_ids||[]).flat());
  return view.value.events.filter(event=>ids.has(event.id));
});
const generatingPractice=ref(false), practiceError=ref('');
async function generatePractice(){
  if(generatingPractice.value)return;
  generatingPractice.value=true;practiceError.value='';
  try{await api.post(`/classroom/sessions/${props.room.session_id}/practice-plans`,{}, {skipBusy:true});emit('plans-created');}
  catch(e){practiceError.value=e.response?.data?.message||'复练任务生成失败，请稍后重试。';}
  finally{generatingPractice.value=false;}
}
const sourceLink=s=>/^https?:\/\//i.test(s.url||s.source||'')?(s.url||s.source):null;
const modalityLabels={body:'身体姿态',hands:'手势动作',face:'面部几何'};
const ratio=m=>m.total_samples>0?Math.max(0,Math.min(100,m.observed_samples/m.total_samples*100)):0;
function showEvidence(items,title){evidence.value=items;playbackEvent.value=items[0]||null;drawerTitle.value=title;filter.value='';drawerOpen.value=true;}
async function showKbSource(source, linkedEvidence=[]){
  const chunkId=source?.chunkId;
  if(!Number.isInteger(chunkId)){return;}
  kbEvidence.value=linkedEvidence;
  kbError.value='';kbLoading.value=true;kbOpen.value=true;kbChunk.value=null;kbDocument.value=null;
  try{
    const data=await fetchRagChunk(chunkId);
    kbChunk.value=data.chunk;kbDocument.value=data.document;
  }catch{
    kbError.value='无法加载知识库原文。';
  }finally{kbLoading.value=false;}
}
function jumpToEvidence(events){
  if(!events?.length)return;
  showEvidence(events,'维度关联课堂事件');
}
async function showImage(event){
  const request=++imageRequest;
  imageError.value='';imageLoading.value=true;imageOpen.value=true;
  if(image.value)URL.revokeObjectURL(image.value); image.value='';
  try {
    const {data}=await api.get(`/classroom/sessions/${props.room.session_id}/evidence/${event.id}`,{responseType:'blob',timeout:15000,skipBusy:true});
    if(request!==imageRequest)return;
    image.value=URL.createObjectURL(data);
  } catch {if(request===imageRequest)imageError.value='截图不可用或没有访问权限。';}
  finally {if(request===imageRequest)imageLoading.value=false;}
}
function releaseImage(){imageRequest++;if(image.value)URL.revokeObjectURL(image.value);image.value='';}
watch(imageOpen,open=>{if(!open)releaseImage();});
onBeforeUnmount(releaseImage);
function regenerate(){
  if(!props.busy && window.confirm('重新评课会调用 AI 并消耗授课额度；成功后更新本节报告。确认继续？'))emit('regenerate',objection.value.trim());
}
</script>
<template>
  <article class="evidence-report" aria-label="课堂 AI 评课报告">
    <div class="report-status-line"><span :class="['report-status',room.report_state]"><i aria-hidden="true" />{{ status }}</span><span>{{ view.hasReport ? '报告版本 v'+(room.report_version||1) : '记录已保留' }}</span></div>
    <div v-if="room.report_state==='running'" class="review-inline-alert" role="status" aria-live="polite">{{reportStage}}。可离开此页，稍后从历史课堂继续查看。</div>
    <button class="review-button no-print" @click="showEvidence(view.events,'录像与课堂记录')">录像与课堂记录</button>
    <p v-if="view.hasReport && room.report?.data_readiness?.dimension_eligibility?.posture===false" class="review-inline-alert" role="status">动作或场景证据不足，本节不形成非语言行为观察。</p>
    <p v-if="room.report_state==='failed'" class="review-inline-alert" role="alert">{{ room.report_error || '报告生成失败，可在下方重试。' }}</p>
    <section v-if="room.report_state==='insufficient'" class="report-blocked review-panel">
      <ShieldCheck aria-hidden="true" /><h2>这节课的证据还不足以形成教练反馈</h2><p>本次没有生成替代结论；请先补足课堂记录，再回看证据。</p>
      <ul><li v-for="reason in room.report_readiness?.reasons || [room.report_error || '请核对课堂采集记录。']" :key="reason">{{ reason }}</li></ul>
      <p class="review-caption">{{ room.report_readiness?.notice }}</p>
    </section>
    <div v-if="view.hasReport" class="report-workspace">
      <div class="report-main-column">
      <p v-if="room.report_state!=='completed'" class="review-inline-alert">以下保留的是上一版报告，本次尚未生成成功。</p>
      <section class="review-panel report-video-panel" aria-labelledby="report-video-heading">
        <ClassroomReplay :room="room" :event="null" />
      </section>
      <section class="report-overview review-panel" aria-labelledby="report-heading">
        <div class="report-intro"><p class="review-eyebrow">01 / CLASSROOM COACH</p><h2 id="report-heading">本节课堂教练反馈</h2><p>从可回看的课堂事实出发，整理观察与下一步练习。</p><span class="report-method-tag"><ShieldCheck aria-hidden="true" />CLASS-Secondary 相关观察主题 · LINK 辅助复盘</span></div>
        <div class="coach-summary"><strong>{{ view.coachingFocuses.length }}</strong><span>条观察反馈</span><small>{{ linkedCoachCount }} 条关联到课堂事件</small></div>
        <div class="report-overview-note"><h3>阅读说明</h3><p>这里呈现的是 LINK 基于课堂记录生成的教练建议，不是 CLASS 正式评分或验证结果。</p><p>虚拟学生回应会单独标明；证据不足时不推断教师或真实学生的状态。</p></div>
      </section>
      </div>
      <div class="report-detail-column">
      <div class="report-actions-panel no-print">
        <router-link class="review-button" to="/classroom">模拟课堂<ArrowUpRight aria-hidden="true" /></router-link>
        <button class="review-button" :disabled="busy" @click="emit('refresh')"><Refresh aria-hidden="true" />刷新</button>
        <button v-if="room?.report && room.report_state!=='insufficient'" class="review-button" @click="emit('print')"><Printer aria-hidden="true" />打印 / PDF</button>
      </div>
      <section class="review-panel report-profile" aria-labelledby="profile-heading">
        <div class="report-section-title"><div><p class="review-eyebrow">02 / OBSERVATION THEMES</p><h2 id="profile-heading"><Focus2 aria-hidden="true" />课堂观察与练习建议</h2></div><span>有证据才形成观察</span></div>
        <p class="review-caption">观察主题参考 CLASS-Secondary 的领域组织；LINK 未经过该量表的正式培训、认证或本地信效度验证。</p>
        <template v-if="view.hasCoaching">
          <section v-for="group in view.coachingGroups" :key="group.key" class="coach-domain-group">
            <h3>{{ group.label }}</h3>
            <article v-for="focus in group.focuses" :key="focus.key" class="coach-focus-card">
              <header><strong>{{ focus.label }}</strong><span>{{ evidenceStatusLabel(focus.evidence_status) }}</span></header>
              <p><b>课堂观察</b>{{ focus.observation }}</p>
              <small v-if="focus.validation_notice" class="review-caption">{{ focus.validation_notice }}</small>
              <small v-if="focus.evidence.some(event=>event.type==='student')" class="review-caption">本条引用含 LINK 虚拟学生生成的模拟回应，不代表真实学生表现。</small>
              <p><b>下一步练习</b>{{ focus.recommendation }}</p>
              <div class="kb-source-actions"><button type="button" class="review-button" :disabled="!focus.evidence.length" @click="showEvidence(focus.evidence,focus.label+' · 课堂证据')">查看 {{ focus.evidence.length }} 条课堂证据</button><span v-if="focus.sources.length">教学依据 {{ focus.sources.length }} 项</span></div>
              <details v-if="focus.sources.length" class="dimension-sources"><summary>查看依据原文</summary><article v-for="source in focus.sources" :key="source.id"><strong>{{ source.title }}</strong><p>{{ source.text }}</p><button v-if="source.isKb" type="button" class="review-button" @click="showKbSource(source,focus.evidence)">知识库原文</button></article></details>
            </article>
          </section>
          <p v-if="!view.coachingGroups.length" class="review-inline-alert">本节暂未形成有充分课堂证据支持的观察建议。可以回看时间线并补充课堂目标或教师说明。</p>
          <p class="review-caption">学生投入不根据 LINK 虚拟学生的回答推断；需要真实学生的可观察证据才能讨论该主题。</p>
        </template>
        <section v-else-if="view.legacyNotes.length" class="coach-domain-group legacy-coach-notes">
          <h3>历史报告中的旧版观察项</h3><p class="review-caption">这些内容保留自旧版 LINK 六维报告，仅隐藏旧分数；它们没有被重新验证或转换为 CLASS-Secondary 结论。重新生成后才会按新教练结构输出。</p>
          <article v-for="note in view.legacyNotes" :key="note.key" class="coach-focus-card"><header><strong>{{ note.label }}</strong><span>{{ evidenceStatusLabel(note.evidenceStatus) }}</span></header><p>{{ note.reason }}</p><button type="button" class="review-button" :disabled="!note.evidence.length" @click="showEvidence(note.evidence,note.label+' · 历史证据')">查看 {{ note.evidence.length }} 条课堂证据</button></article>
        </section>
        <p v-else class="review-caption">暂无教练反馈。完成课堂采集后可生成新的证据关联建议。</p>
      </section>
    <section class="review-panel report-evidence-map" aria-labelledby="evidence-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">{{ view.hasReport?'03':'01' }} / EVIDENCE MAP</p><h2 id="evidence-heading"><ListDetails aria-hidden="true" />课堂证据时间线</h2></div><button class="review-button no-print" @click="showEvidence(view.events,'全部课堂记录')">全部 {{ view.events.length }} 条<ArrowUpRight aria-hidden="true" /></button></div>
      <p class="review-caption">每个刻度是一条事件；密度不代表质量或持续时长。完整播放需关联学生回复，并排除失败、取消与打断。</p>
      <div class="evidence-map" aria-label="课堂事件分层时间线">
        <button v-for="lane in view.lanes" :key="lane.key" class="evidence-lane" :class="lane.key" :disabled="!lane.count" :aria-label="lane.label+'，'+lane.count+' 条，查看记录'" @click="showEvidence(lane.allEvents,lane.label+' · 记录')"><span>{{ lane.label }}</span><span class="lane-track" aria-hidden="true"><i v-for="event in lane.events" :key="event.id" :style="{left:event.position+'%'}" /></span><b>{{ lane.count }}</b></button>
        <div class="evidence-time-axis" aria-hidden="true"><span>0:00</span><span>{{ time(view.span/2) }}</span><span>{{ time(view.span) }}</span></div>
      </div>
      <p v-if="view.duration===null || view.untimed" class="review-caption">{{ view.duration===null?'课堂时长未记录，横轴为已知事件跨度。':'' }}{{ view.untimed ? view.untimed+' 条事件没有有效时间戳，仅在记录列表展示。' : '' }}</p>
    </section>
    <section class="review-panel report-behaviors" aria-labelledby="behavior-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">BEHAVIOR TRACE</p><h2 id="behavior-heading"><ListDetails aria-hidden="true" />可回放的教学行为</h2></div><span>规则识别 · 不代表教学质量评分</span></div>
      <p class="review-caption">只展示能关联到原始课堂事件的片段。提问到学生回应的间隔包含系统生成和语音播放时间，不是教师候答时间。</p>
      <p class="review-caption">可用记录：教师转写 {{ room.behavior_analysis?.coverage?.teacher_transcripts||0 }} 段，完整学生回应 {{ room.behavior_analysis?.coverage?.completed_student_replies||0 }} 次，画面采样 {{ room.behavior_analysis?.coverage?.vision_samples||0 }} 条，本地可观察动作样本 {{ room.behavior_analysis?.coverage?.observed_motion_samples||0 }} 条。</p>
      <ol v-if="behaviors.length" class="behavior-list">
        <li v-for="(segment,index) in behaviors" :key="segment.kind+'-'+segment.event_ids.join('-')+'-'+index">
          <time>{{ time(segment.start_ms) }}</time><strong>{{ behaviorLabels[segment.kind]||segment.kind }}</strong>
          <p>{{ segment.detail || '查看关联课堂记录' }}</p>
          <button type="button" class="review-button no-print" @click="showEvidence(behaviorEvents(segment),(behaviorLabels[segment.kind]||'教学行为')+' · 原始证据')">查看 {{ segment.event_ids.length }} 条证据</button>
        </li>
      </ol>
      <p v-else class="review-caption">暂无足够的已记录事件来识别教学行为片段。</p>
    </section>
    <section v-if="transitions.length" class="review-panel" aria-labelledby="student-change-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">SIMULATED STATE</p><h2 id="student-change-heading">模拟学生状态变化</h2></div><span>情境状态 · 可追溯教师证据</span></div>
      <p class="review-caption">状态只用于复盘虚拟学生如何响应本节教学，不代表真实儿童已掌握知识。</p>
      <ol class="behavior-list">
        <li v-for="transition in transitions" :key="transition.id">
          <time>{{ time(transition.at_ms) }}</time><strong>{{ studentNames[transition.data.student_id]||'虚拟学生' }}</strong>
          <p>{{ transition.data.after?.understanding || '模拟理解状态已更新' }}</p>
          <p>仍保留的误解：{{ transition.data.after?.misconceptions?.join('；') || '无记录' }}</p>
          <button type="button" class="review-button no-print" @click="showEvidence(view.events.filter(event=>transition.data.event_ids?.includes(event.id)),'状态变化 · 教师证据')">查看教师证据</button>
        </li>
      </ol>
    </section>
    <section v-if="view.hasReport && motion?.sample_count" class="review-panel report-motion">
      <div class="report-section-title"><div><p class="review-eyebrow">04 / OBSERVABILITY</p><h2><Focus2 aria-hidden="true" />先看证据质量，再谈教态</h2></div><span>动作摘要 · {{ motion.observed_samples }} 个可观察样本</span></div>
      <div class="modality-grid"><div v-for="(m,key) in motion.modalities" :key="key"><header><span>{{ modalityLabels[key] || key }}</span><b>{{ m.observed_samples }} / {{ m.total_samples }}</b></header><div class="modality-track" :aria-label="(modalityLabels[key]||key)+'可观察样本 '+m.observed_samples+' / '+m.total_samples"><i :key="ratio(m)" :style="{width:ratio(m)+'%'}" /></div><small>可观察样本 / 采样总数</small></div></div>
      <p class="review-caption">采样可观察率不是教态得分，也不是整课时长占比。面部几何不用于推断情绪、性格或自信程度。</p>
      <details class="report-fold"><summary>查看动作线索与检测边界</summary>
        <p v-if="motion.status!=='observed'">动作证据不足，本节不形成非语言行为观察。</p>
        <article v-for="o in motion.observations" :key="o.code"><h3>{{ o.description }}</h3><p>{{ o.matched_samples }} / {{ o.observed_samples }} 个有效样本出现该线索；连续采样跨度 {{ (o.longest_observed_span_ms/1000).toFixed(1) }} 秒（非持续动作测量）。</p><p>启发式提示：{{ o.suggestion }}</p><p v-if="o.context_notice">{{o.context_notice}}</p><p v-for="c in o.context||[]" :key="c.event_id">#{{c.event_id}} · {{time(c.at_ms)}}：{{c.text}}</p><button class="review-button no-print" @click="showEvidence(view.events.filter(e=>o.event_ids?.includes(e.id)||o.context?.some(c=>c.event_id===e.id||c.playback_event_id===e.id)),o.description+' · 证据')">查看相关记录</button></article>
        <p v-for="note in motion.limitations" :key="note">{{ note }}</p>
      </details>
    </section>
    <section v-if="view.hasReport && view.reflections.length" class="report-reflections review-panel">
      <div class="report-section-title"><div><p class="review-eyebrow">03 / NEXT PRACTICE</p><h2><Bulb aria-hidden="true" />本节优先练习</h2></div><span>来自有证据的观察主题</span></div>
      <div class="reflection-grid"><article v-for="(d,index) in view.reflections" :key="d.key"><span class="reflection-number">0{{ index+1 }}</span><h3>{{ d.label }}</h3><p>{{ d.reflection }}</p><button class="reflection-link no-print" :disabled="!d.evidence.length" @click="showEvidence(d.evidence,d.label+' · 复盘证据')">带着证据复盘<ArrowUpRight aria-hidden="true" /></button></article></div>
      <p class="review-caption">练习建议来自有课堂事件支持的观察主题；复练记录只核对目标行为是否出现，不代表能力分数变化。</p>
    </section>
    <section v-if="view.hasReport" class="review-panel" aria-labelledby="practice-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">NEXT PRACTICE</p><h2 id="practice-heading"><Bulb aria-hidden="true" />带着目标再练一次</h2></div><span>同一情境 · 同一行为识别规则</span></div>
      <p class="review-caption">任务关联已保存的观察主题与课堂事件。复练只核对目标行为是否被记录，不把次数解释为教学质量或能力分数。</p>
      <p v-if="practiceError" class="review-inline-alert" role="alert">{{ practiceError }}</p>
      <button v-if="!plans.length && room.report_state==='completed'" type="button" class="review-button no-print" :disabled="generatingPractice" @click="generatePractice">{{ generatingPractice?'生成中…':'生成复练任务' }}</button>
      <ol v-if="plans.length" class="behavior-list">
        <li v-for="plan in plans" :key="plan.id">
          <strong>{{ plan.task_text }}</strong>
          <p>{{ plan.basis==='general'?'通用练习；本次报告没有足够证据指向特定练习主题。':'关联本节观察建议与原始课堂事件。' }}</p>
          <p>完成判据：在复练课堂中至少记录 {{ plan.criteria?.minimum_observed||1 }} 次目标行为（{{ behaviorLabels[plan.target_kind]||plan.target_kind }}）。</p>
          <button v-if="plan.source_event_ids?.length" type="button" class="review-button no-print" @click="showEvidence(view.events.filter(event=>plan.source_event_ids.includes(event.id)),'复练任务 · 来源证据')">查看来源证据</button>
          <router-link v-if="plan.status==='suggested'" class="review-button primary no-print" :to="{path:'/classroom',query:{practice:String(plan.id)}}">开始这项复练</router-link>
          <router-link v-if="plan.retest_session_id" class="review-button no-print" :to="{path:'/ai-review',query:{classroom:String(plan.retest_session_id)}}">查看复练课堂 #{{ plan.retest_session_id }}</router-link>
          <p v-if="plan.comparison">对照结果：{{ {observed:'已记录到目标行为',not_observed:'本次未观察到目标行为',insufficient:'证据不足，无法判断'}[plan.comparison.status]||'待核对' }}。{{ plan.comparison.notice||plan.comparison.reason }}</p>
        </li>
      </ol>
    </section>
    <section v-if="activePractice" class="review-panel" aria-labelledby="active-practice-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">PRACTICE ATTEMPT</p><h2 id="active-practice-heading">本节的复练目标</h2></div><span>来源课堂 #{{ activePractice.source_session_id }}</span></div>
      <p>{{ activePractice.task_text }}</p>
      <p class="review-caption">判据：至少记录 {{ activePractice.criteria?.minimum_observed||1 }} 次“{{ behaviorLabels[activePractice.target_kind]||activePractice.target_kind }}”。这只核对行为是否出现，不把次数当作教学质量评分。</p>
      <p v-if="activePractice.comparison" class="review-caption">{{ {observed:'已记录到目标行为',not_observed:'未观察到目标行为',insufficient:'证据不足，无法判断'}[activePractice.comparison.status]||'待核对' }}：{{ activePractice.comparison.notice||activePractice.comparison.reason }}</p>
      <div class="kb-source-actions no-print">
        <router-link class="review-button" :to="{path:'/ai-review',query:{classroom:String(activePractice.source_session_id)}}">查看来源课堂</router-link>
        <button v-if="activePracticeEvidence.length" type="button" class="review-button" @click="showEvidence(activePracticeEvidence,'复练目标 · 本节证据')">查看本节 {{ activePracticeEvidence.length }} 条目标证据</button>
      </div>
    </section>
    <section v-if="view.hasReport" class="report-methodology review-panel">
      <h2><ShieldCheck aria-hidden="true" />方法、来源与边界</h2>
      <details class="report-fold"><summary>这份反馈如何形成</summary><p>课堂事实 → CLASS-Secondary 相关观察主题 → AI 整理反馈与练习 → 服务端核对引用 → 本页关联录像和课堂原文。</p><p>LINK 不是 CLASS 正式评分工具；当前教练输出尚未在中文中学短时试讲上完成信度、效度或常模验证，不用于教师排名或绩效判断。</p><p>转写可能存在识别误差。建议结合原始录像复核；虚拟学生反馈只代表模拟情境，无真人学生证据时不评价真实学生投入。</p><p>报告生成：{{ formatReportDate(room.report.generated_at) }} · 模型标识：{{ room.report.model || '此历史报告未记录' }} · 当前展示版本：v{{ room.report_version || 1 }}</p><p>{{ room.report.notice }}</p></details>
      <details class="report-fold"><summary>教学依据与来源（{{ sources.length }}）</summary><p class="review-caption">以下为本次报告保存的检索资料，用于解释教学判断，不代表量表已获得科学验证。</p><article v-for="s in sources" :key="s.id"><h3>{{ s.title }}</h3><small>{{ s.type }} · {{ s.location }}</small><p>{{ s.text }}</p><a v-if="sourceLink(s)" :href="sourceLink(s)" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a><span v-else>{{ s.source }}</span></article><p v-if="!sources.length">本次报告未记录教学资料来源。</p></details>
    </section>
    <details v-if="room.report_state!=='running' && (room.report_state!=='insufficient' || room.report_readiness?.eligible)" class="review-panel report-correction no-print">
      <summary><Refresh aria-hidden="true" />补充证据 / 重新评课</summary>
      <div class="correction-form"><label for="report-objection">补充说明（可选，不会直接加分）</label><textarea id="report-objection" v-model="objection" maxlength="2000" rows="3" placeholder="例如：02:15 我已更正前面的表述，请结合该段重新核对。" /><button class="review-button" :disabled="busy" @click="regenerate">{{ busy?'请求中…':view.hasReport?'重新评课':room.report_state==='failed'?'重试生成':'生成报告' }}</button><small>仅主动确认后调用 AI，会消耗授课额度。成功后更新报告。</small></div>
    </details>
      </div>
    </div>
    <footer class="report-footer">LINK · 每一份判断，都应回到课堂本身。<span>教师自主复核 · AI 辅助成长</span></footer>
    <ClassroomDialog v-model="drawerOpen" :title="drawerTitle">
      <ClassroomReplay v-if="drawerOpen" :room="room" :event="playbackEvent" />
      <div class="report-evidence-drawer"><p class="review-caption">本节课堂原始记录 · {{ evidence.length }} 条</p><label class="evidence-search">查找证据<input v-model="filter" type="search" placeholder="关键词、事件编号或时间" /></label>
        <ol><li v-for="e in filtered" :key="e.id" :id="'review-evidence-'+e.id"><header><span>{{ eventLabel(e) }}</span><button class="review-button" :aria-label="'回放 '+time(e.at_ms)+' 的课堂证据'" @click="playbackEvent=e"><time>{{ time(e.at_ms) }}</time></button><small>#{{ e.id }}</small></header><p class="evidence-main-text">{{ eventText(e) }}</p><section v-if="e.type==='transcript'" class="evidence-explanation"><strong>教学话语候选分类</strong><div v-if="e.data.teaching_speech?.labels?.length"><p v-for="label in e.data.teaching_speech.labels" :key="label.key"><b>{{ label.label }}</b><span v-if="label.cues?.length"> · 匹配线索：{{ label.cues.join('、') }}</span></p></div><p v-else>当前原话未匹配到已配置的话语类型。</p><small>{{ e.data.teaching_speech?.notice || '此历史记录没有话语分类数据。' }}</small><div class="evidence-explanation"><strong>声音表达线索</strong><p>{{ e.data.voice_cues?.cue || '此历史记录没有本机声学特征。' }}</p><small>{{ e.data.voice_cues?.notice || '声音线索与文字含义分开保存；不据此判断正面或负面情绪。' }}</small></div></section><div class="evidence-explanation"><strong>这条证据说明</strong><p>{{ evidenceExplanation(e) }}</p><div class="evidence-facts"><span>课堂时间 {{ time(e.at_ms) }}</span><span>事件类型 {{ eventLabel(e) }}</span><span v-if="e.data?.student_id">对象 {{ e.data.student_id }}</span></div></div><button v-if="e.type==='vision'" class="review-button" @click="showImage(e)"><Photo aria-hidden="true" />查看课堂截图</button></li></ol>
        <p v-if="!filtered.length">没有匹配的记录。</p>
      </div>
    </ClassroomDialog>
    <ClassroomDialog v-model="imageOpen" title="课堂截图证据"><p v-if="imageLoading" role="status">正在读取截图…</p><p v-if="imageError" role="alert">{{ imageError }}</p><img v-if="image" :src="image" alt="此课堂时间点的分析截图" class="report-evidence-image" /></ClassroomDialog>
    <ClassroomDialog v-model="kbOpen" title="知识库依据原文">
      <p v-if="kbLoading" role="status">正在加载切片…</p>
      <p v-if="kbError" role="alert">{{ kbError }}</p>
      <article v-if="kbChunk" class="kb-chunk-view">
        <header><strong>{{ kbDocument?.title }}</strong><small>{{ kbChunk.section }} · #{{ kbChunk.id }}</small></header>
        <pre>{{ kbChunk.text }}</pre>
        <button type="button" class="review-button" :disabled="!kbEvidence.length" @click="jumpToEvidence(kbEvidence)">关联到本节课堂事件</button>
      </article>
    </ClassroomDialog>
  </article>
</template>

<style scoped>
.kb-source-actions{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.35rem;}
.kb-chunk-view pre{white-space:pre-wrap;font-size:.85rem;max-height:40vh;overflow:auto;}
</style>
