<script setup>
import { computed, ref, onBeforeUnmount, watch } from 'vue';
import { ChartBar, ArrowUpRight, Focus2, ListDetails, ShieldCheck, Bulb, Photo, Refresh } from '@vicons/tabler';
import { api } from '../services/api';
import { buildReview, formatReportTime as time, formatReportDate } from '../services/classroomReview.js';
import { fetchRagChunk } from '../services/rag.js';
import { eventLabel, eventText } from '../services/classroomStatus.js';
import ClassroomDialog from './ClassroomDialog.vue';
import ClassroomReplay from './ClassroomReplay.vue';
const props=defineProps({room:Object,busy:Boolean});
const emit=defineEmits(['regenerate','plans-created']);
const view=computed(()=>buildReview(props.room));
const selectedKey=ref('clarity');
const selected=computed(()=>view.value.dimensions.find(d=>d.key===selectedKey.value)||view.value.dimensions[0]);
const status=computed(()=>({idle:'待评课',running:'评课进行中',completed:'已完成',failed:'生成失败',insufficient:'证据不足 · 未生成'}[props.room.report_state]||'待评课'));
const drawerOpen=ref(false), drawerTitle=ref('课堂证据'), evidence=ref([]), filter=ref('');
const playbackEvent=ref(null);
const reportStage=computed(()=>({checking:'检查最低证据',preparing:'整理课堂证据',judging:'AI 评审中',validating:'校验评审结果',completed:'完成',failed:'生成失败'}[props.room.report_stage]||'等待评审状态'));
const imageOpen=ref(false), image=ref(''), imageError=ref(''), imageLoading=ref(false), objection=ref('');
const kbOpen=ref(false), kbLoading=ref(false), kbError=ref(''), kbChunk=ref(null), kbDocument=ref(null);
let imageRequest=0;
const filtered=computed(()=>evidence.value.filter(e=>!filter.value || `${eventLabel(e)} ${eventText(e)} #${e.id} ${time(e.at_ms)}`.includes(filter.value.trim())));
const motion=computed(()=>props.room.report?.motion_evidence);
const sources=computed(()=>props.room.report?.sources||[]);
const behaviorLabels={teacher_question:'教师提问',student_response:'学生完整回应',question_response:'提问与回应',teacher_followup:'教师追问',teacher_feedback:'教师反馈',teacher_summary:'课堂小结',post_question_silence:'提问后的静默间隔',board_observation:'可见板书',board_speech_context:'板书与授课发言',motion_speech_context:'动作与授课发言'};
const behaviors=computed(()=>props.room.behavior_analysis?.segments||[]);
function behaviorEvents(segment){return view.value.events.filter(event=>segment.event_ids?.includes(event.id));}
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
async function showKbSource(source){
  const chunkId=source?.chunkId;
  if(!Number.isInteger(chunkId)){return;}
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
    <p v-if="view.hasReport && room.report?.data_readiness?.dimension_eligibility?.posture===false" class="review-inline-alert" role="status">动作或场景证据不足，本报告仅评价其他有证据的维度，教态不评分。</p>
    <p v-if="room.report_state==='failed'" class="review-inline-alert" role="alert">{{ room.report_error || '报告生成失败，可在下方重试。' }}</p>
    <section v-if="room.report_state==='insufficient'" class="report-blocked review-panel">
      <ShieldCheck aria-hidden="true" /><h2>这节课的证据，还不足以形成评课</h2><p>本次未生成 AI 评课报告，也不会用替代分数填补缺项。</p>
      <ul><li v-for="reason in room.report_readiness?.reasons || [room.report_error || '请核对课堂采集记录。']" :key="reason">{{ reason }}</li></ul>
      <p class="review-caption">{{ room.report_readiness?.notice }}</p>
    </section>
    <template v-if="view.hasReport">
      <p v-if="room.report_state!=='completed'" class="review-inline-alert">以下保留的是上一版报告，本次尚未生成成功。</p>
      <section class="report-overview review-panel" aria-labelledby="report-heading">
        <div class="report-intro"><p class="review-eyebrow">01 / LESSON PORTRAIT</p><h2 id="report-heading">一节课的教学剖面</h2><p>结论有出处，进步有线索。</p><span class="report-method-tag"><ShieldCheck aria-hidden="true" />AI 辅助评价 · 非标准化测评</span></div>
        <div class="report-score-block">
          <div :key="view.overall" class="report-score-ring" :style="{'--score':(view.overall??0)+'%'}"><div><strong>{{ view.overall ?? '—' }}</strong><span>综合参考分 / 100</span></div></div>
          <p><b>{{ view.scored }}</b> / 6 个维度已评分</p>
        </div>
        <div class="report-overview-note"><h3>如何读这份报告</h3><p>综合分沿用已保存报告，仅汇总有证据的维度。环形图使用 0–100 分量程，不表示达标率或置信概率。</p><p>未评分不等于 0 分；不同证据覆盖的课堂，不宜直接比较综合分。</p></div>
      </section>
      <div class="report-metrics" aria-label="课堂记录统计">
        <div><span>教师转写</span><strong>{{ view.metrics.transcripts }}<small>段</small></strong></div>
        <div><span>学生生成</span><strong>{{ view.metrics.replies }}<small>条</small></strong></div>
        <div><span>确认完整播放</span><strong>{{ view.metrics.completed }}<small>次</small></strong></div>
        <div><span>视觉采样记录</span><strong>{{ view.metrics.visual }}<small>条</small></strong></div>
      </div>
      <section class="review-panel report-profile" aria-labelledby="profile-heading">
        <div class="report-section-title"><div><p class="review-eyebrow">02 / DIMENSIONS</p><h2 id="profile-heading"><ChartBar aria-hidden="true" />六维证据解读</h2></div><span>点击维度，展开判断依据</span></div>
        <div class="report-profile-grid">
          <div class="dimension-chart" role="group" aria-label="六维评分，量程 0 至 100">
            <div class="dimension-axis" aria-hidden="true"><span>0</span><span>50</span><span>100</span></div>
            <button v-for="d in view.dimensions" :key="d.key" class="dimension-row" :class="{selected:selectedKey===d.key,unscored:d.score===null}" :aria-pressed="selectedKey===d.key" :aria-label="d.label+'：'+(d.score===null?'暂不评分':d.score+' 分')" @click="selectedKey=d.key">
              <span>{{ d.label }}</span><span class="dimension-track" aria-hidden="true"><i v-if="d.score!==null" :key="d.score" :style="{width:d.score+'%'}" /></span><b>{{ d.score ?? '—' }}</b>
            </button>
            <p class="review-caption">— 暂不评分 · 分数为 AI 判断，不是置信概率</p>
          </div>
          <div class="dimension-insight" :key="selected.key" aria-live="polite">
            <div class="dimension-insight-head"><span class="review-eyebrow">{{ String(view.dimensions.indexOf(selected)+1).padStart(2,'0') }} / 06</span><b>{{ selected.score===null?'暂不评分':selected.score+' / 100' }}</b></div>
            <h3>{{ selected.label }}</h3><p class="dimension-focus">{{ selected.focus }}</p>
            <span class="report-attribution">已保存的评课结论</span><p class="dimension-reason">{{ selected.reason }}</p>
            <div class="dimension-evidence-actions"><button class="review-button" :disabled="!selected.evidence.length" @click="showEvidence(selected.evidence,selected.label+' · 证据')"><Focus2 aria-hidden="true" />查看 {{ selected.evidence.length }} 条证据<ArrowUpRight aria-hidden="true" /></button><span>{{ selected.sources.length }} 项教学依据</span></div>
            <p v-if="selected.unresolved" class="review-inline-alert">{{ selected.unresolved }} 个引用无法对应本节记录，未补造时间点；请人工核对。</p>
            <details v-if="selected.sources.length" class="dimension-sources" open>
              <summary>本维度引用的教学依据</summary>
              <article v-for="source in selected.sources" :key="source.id" class="kb-source-card">
                <p>{{ source.title }}<small> · {{ source.location || source.type }}</small></p>
                <div class="kb-source-actions">
                  <button v-if="source.isKb" type="button" class="review-button" @click="showKbSource(source)">知识库原文</button>
                  <button type="button" class="review-button" :disabled="!selected.evidence.length" @click="jumpToEvidence(selected.evidence)">关联 {{ selected.evidence.length }} 条课堂事件</button>
                  <a v-if="sourceLink(source)" class="review-button" :href="sourceLink(source)" target="_blank" rel="noopener">外部来源</a>
                </div>
              </article>
            </details>
          </div>
        </div>
        <div class="report-print-dimensions"><section v-for="d in view.dimensions" :key="d.key"><h3>{{ d.label }} · {{ d.score ?? '暂不评分' }}</h3><p>{{ d.reason }}</p><small>事件引用：{{ d.evidence.map(e=>'#'+e.id+' '+time(e.at_ms)).join('；') || '无' }}</small></section></div>
      </section>
    </template>
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
        <p v-if="motion.status!=='observed'">有效动作证据不足，不能据此给出教态评分。</p>
        <article v-for="o in motion.observations" :key="o.code"><h3>{{ o.description }}</h3><p>{{ o.matched_samples }} / {{ o.observed_samples }} 个有效样本出现该线索；连续采样跨度 {{ (o.longest_observed_span_ms/1000).toFixed(1) }} 秒（非持续动作测量）。</p><p>启发式提示：{{ o.suggestion }}</p><p v-if="o.context_notice">{{o.context_notice}}</p><p v-for="c in o.context||[]" :key="c.event_id">#{{c.event_id}} · {{time(c.at_ms)}}：{{c.text}}</p><button class="review-button no-print" @click="showEvidence(view.events.filter(e=>o.event_ids?.includes(e.id)||o.context?.some(c=>c.event_id===e.id||c.playback_event_id===e.id)),o.description+' · 证据')">查看相关记录</button></article>
        <p v-for="note in motion.limitations" :key="note">{{ note }}</p>
      </details>
    </section>
    <section v-if="view.hasReport && view.reflections.length" class="report-reflections review-panel">
      <div class="report-section-title"><div><p class="review-eyebrow">05 / NEXT PRACTICE</p><h2><Bulb aria-hidden="true" />把报告带回下一节课</h2></div><span>复盘提示 · 非新增 AI 结论</span></div>
      <div class="reflection-grid"><article v-for="(d,index) in view.reflections" :key="d.key"><span class="reflection-number">0{{ index+1 }}</span><h3>{{ d.label }}</h3><p>{{ d.reflection }}</p><button class="reflection-link no-print" :disabled="!d.evidence.length" @click="showEvidence(d.evidence,d.label+' · 复盘证据')">带着证据复盘<ArrowUpRight aria-hidden="true" /></button></article></div>
      <p class="review-caption">按已评分维度从低到高选取最多 3 项，提供固定练习提示；需结合本课证据由教师判断是否适用，不等同于已发现的问题。</p>
    </section>
    <section v-if="view.hasReport" class="review-panel" aria-labelledby="practice-heading">
      <div class="report-section-title"><div><p class="review-eyebrow">NEXT PRACTICE</p><h2 id="practice-heading"><Bulb aria-hidden="true" />带着目标再练一次</h2></div><span>同一情境 · 同一行为识别规则</span></div>
      <p class="review-caption">任务依据已保存的报告与课堂事件生成。复练只核对目标行为是否被记录，不直接比较不同证据覆盖的综合分。</p>
      <p v-if="practiceError" class="review-inline-alert" role="alert">{{ practiceError }}</p>
      <button v-if="!plans.length && room.report_state==='completed'" type="button" class="review-button no-print" :disabled="generatingPractice" @click="generatePractice">{{ generatingPractice?'生成中…':'生成复练任务' }}</button>
      <ol v-if="plans.length" class="behavior-list">
        <li v-for="plan in plans" :key="plan.id">
          <strong>{{ plan.task_text }}</strong>
          <p>{{ plan.basis==='general'?'通用练习；本次报告没有足够证据指向个人弱项。':'关联已保存的评课维度与原始课堂证据。' }}</p>
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
      <details class="report-fold"><summary>这份评课如何形成</summary><p>课堂事件 → AI 六维判断 → 服务端引用及证据校验 → 本页可视化。此页面直接读取本节已保存的 AI 报告，不重新生成或改写结论。</p><p>分数不是标准化教育量表，尚无人工校准的信度、效度或常模支持；不提供排名、百分位、显著性或因果推断。</p><p>转写可能存在识别误差。应结合教师自我纠错和实际播放记录复核判断；无视觉证据不评价教态，动作不能推导心理状态。</p><p>报告生成：{{ formatReportDate(room.report.generated_at) }} · 模型标识：{{ room.report.model || '此历史报告未记录' }} · 当前展示版本：v{{ room.report_version || 1 }}</p><p>{{ room.report.notice }}</p></details>
      <details class="report-fold"><summary>教学依据与来源（{{ sources.length }}）</summary><p class="review-caption">以下为本次报告保存的检索资料，用于解释教学判断，不代表量表已获得科学验证。</p><article v-for="s in sources" :key="s.id"><h3>{{ s.title }}</h3><small>{{ s.type }} · {{ s.location }}</small><p>{{ s.text }}</p><a v-if="sourceLink(s)" :href="sourceLink(s)" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a><span v-else>{{ s.source }}</span></article><p v-if="!sources.length">本次报告未记录教学资料来源。</p></details>
    </section>
    <details v-if="room.report_state!=='running' && (room.report_state!=='insufficient' || room.report_readiness?.eligible)" class="review-panel report-correction no-print">
      <summary><Refresh aria-hidden="true" />补充证据 / 重新评课</summary>
      <div class="correction-form"><label for="report-objection">补充说明（可选，不会直接加分）</label><textarea id="report-objection" v-model="objection" maxlength="2000" rows="3" placeholder="例如：02:15 我已更正前面的表述，请结合该段重新核对。" /><button class="review-button" :disabled="busy" @click="regenerate">{{ busy?'请求中…':view.hasReport?'重新评课':room.report_state==='failed'?'重试生成':'生成报告' }}</button><small>仅主动确认后调用 AI，会消耗授课额度。成功后更新报告。</small></div>
    </details>
    <footer class="report-footer">LINK · 每一份判断，都应回到课堂本身。<span>教师自主复核 · AI 辅助成长</span></footer>
    <ClassroomDialog v-model="drawerOpen" :title="drawerTitle">
      <ClassroomReplay v-if="drawerOpen" :room="room" :event="playbackEvent" />
      <div class="report-evidence-drawer"><p class="review-caption">本节课堂原始记录 · {{ evidence.length }} 条</p><label class="evidence-search">查找证据<input v-model="filter" type="search" placeholder="关键词、事件编号或时间" /></label>
        <ol><li v-for="e in filtered" :key="e.id" :id="'review-evidence-'+e.id"><header><span>{{ eventLabel(e) }}</span><button class="review-button" :aria-label="'回放 '+time(e.at_ms)+' 的课堂证据'" @click="playbackEvent=e"><time>{{ time(e.at_ms) }}</time></button><small>#{{ e.id }}</small></header><p>{{ eventText(e) }}</p><small v-if="e.type==='student'">生成文字；是否完整播放请核对同一 reply_id 的播放记录。</small><button v-if="e.type==='vision'" class="review-button" @click="showImage(e)"><Photo aria-hidden="true" />查看截图</button><details><summary>原始事件数据</summary><pre>{{ JSON.stringify(e,null,2) }}</pre></details></li></ol>
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
        <button type="button" class="review-button" :disabled="!selected.evidence.length" @click="jumpToEvidence(selected.evidence)">跳转到本维度课堂事件</button>
      </article>
    </ClassroomDialog>
  </article>
</template>

<style scoped>
.kb-source-actions{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.35rem;}
.kb-chunk-view pre{white-space:pre-wrap;font-size:.85rem;max-height:40vh;overflow:auto;}
</style>
