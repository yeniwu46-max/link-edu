// Presentation only: never generates, rescales or writes a classroom report.
export const REVIEW_DIMENSIONS = [
  ['clarity','表达清晰度','概念是否准确，表达是否易于理解','选一段概念解释，核对关键词，再用一个反例检验表述。'],
  ['pace','教学节奏','讲解、等待与回应是否衔接','复核一次提问后的等待与回应，判断是否需要调整节奏。'],
  ['interaction','互动设计','回应是否被听见并形成反馈','核对一次已播放的学生回应，记录自己如何承接并反馈。'],
  ['posture','教态与站位','可观察的非语言教学行为','先确认入镜与采样质量，再结合讲解情境复核动作线索。'],
  ['questioning','提问质量','问题是否推动解释与理解','选一个问题，尝试增加“为什么”或反例追问，再检查学生回应。'],
  ['structure','课堂结构','目标、展开与收束是否连贯','复看开头与结尾，核对本课目标是否得到回应。'],
];
const list=value=>Array.isArray(value)?value:[];
export const validScore=value=>typeof value==='number' && Number.isFinite(value) && value>=0 && value<=100 ? value : null;
const timed=e=>typeof e.at_ms==='number' && Number.isFinite(e.at_ms) && e.at_ms>=0;
const byTime=(a,b)=>(timed(a)?a.at_ms:Infinity)-(timed(b)?b.at_ms:Infinity) || a.id-b.id;
export function classroomDestination(room) {
  return room.state==='active' ? {path:'/classroom',query:{session:room.session_id}} :
    {path:'/ai-review',query:{classroom:String(room.session_id)}};
}
export function formatReportTime(ms) {
  if (!Number.isFinite(ms) || ms<0) return '时间未记录';
  return `${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
}
export function formatReportDate(value) {
  if (!value || typeof value!=='string') return '时间未记录';
  const date=new Date(/(?:Z|[+-]\d\d:\d\d)$/i.test(value)?value:`${value}Z`);
  return Number.isNaN(date.getTime())?'时间未记录':date.toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
}
export function buildReview(room={}) {
  const events=[...new Map(list(room.events).filter(e=>Number.isInteger(e?.id)).map(e=>[e.id,{...e,data:e.data||{}}])).values()].sort(byTime);
  const byId=new Map(events.map(e=>[e.id,e]));
  const report=room.report_state==='insufficient'?null:room.report;
  const sourceMap=new Map(list(report?.sources).map(s=>[s.id,s]));
  const dimensions=REVIEW_DIMENSIONS.map(([key,label,focus,reflection])=>{
    const item=list(report?.dimensions).find(d=>d.key===key)||{};
    const ids=[...new Set(list(item.event_ids))];
    return {key,label,focus,reflection,score:validScore(item.score),reason:item.reason||'此维度暂无可用结论。',
      evidence:ids.filter(id=>byId.has(id)).map(id=>byId.get(id)).sort(byTime),
      unresolved:ids.filter(id=>!byId.has(id)).length,
      sources:[...new Set(list(item.source_ids))].filter(id=>sourceMap.has(id)).map(id=>sourceMap.get(id))};
  });
  const replies=events.filter(e=>e.type==='student');
  const replyIds=new Set(replies.map(e=>e.data.reply_id).filter(Boolean));
  const interrupted=new Set(events.filter(e=>e.type==='interrupt'||(e.type==='playback' &&
    ['playback_failed','playback_cancelled','cancelled'].includes(e.data.status))).map(e=>e.data.reply_id));
  const completed=[...new Map(events.filter(e=>e.type==='playback' && e.data.status==='playback_completed' &&
    replyIds.has(e.data.reply_id) && !interrupted.has(e.data.reply_id)).map(e=>[e.data.reply_id,e])).values()];
  const transcript=events.filter(e=>e.type==='transcript');
  const visual=events.filter(e=>['pose','vision'].includes(e.type));
  const duration=typeof room.elapsed==='number' && Number.isFinite(room.elapsed) && room.elapsed>=0 ? room.elapsed*1000 : null;
  const span=Math.max(duration||0,...events.filter(timed).map(e=>e.at_ms),1);
  const lanes=[['teacher','教师转写',transcript],['student','学生生成',replies],['completed','完整播放',completed],['visual','视觉采样',visual]]
    .map(([key,label,items])=>({key,label,count:items.length,allEvents:items,events:items.filter(timed).map(e=>({...e,position:e.at_ms/span*100}))}));
  return {hasReport:Boolean(report),overall:validScore(report?.overall_score),dimensions,scored:dimensions.filter(d=>d.score!==null).length,
    events,lanes,duration,span,untimed:events.filter(e=>!timed(e)).length,
    metrics:{transcripts:transcript.length,replies:replies.length,completed:completed.length,visual:visual.length},
    reflections:dimensions.filter(d=>d.score!==null).sort((a,b)=>a.score-b.score).slice(0,3)};
}
