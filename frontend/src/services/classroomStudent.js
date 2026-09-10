export function studentPresentation(id, { raised = false, speaking = false, reply } = {}) {
  const studentId = ['ming', 'yu', 'lin'].includes(id) ? id : 'lin';
  const responding = ['thinking', 'generating', 'queued', 'playing'].includes(reply?.phase);
  const pose = raised || speaking || responding ? 'raised' : 'listening';
  const label = speaking ? '正在发言' : raised ? '我有问题' : {
    thinking: '思考中', generating: '组织回答', queued: '准备发言', failed: '回复暂不可用',
  }[reply?.phase] || '认真听讲';
  return { pose, label, src: `/assets/students/${studentId}-${pose}.png` };
}
