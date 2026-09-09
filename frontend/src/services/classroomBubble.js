// Presentation-only retention: never mutates audio acknowledgements or classroom evidence.
export function createBubbleRetention(show, {schedule = setTimeout, cancel = clearTimeout} = {}) {
  let timer, current = null, terminalKey = '';
  function clear() { cancel(timer); timer = null; current = null; show(null); }
  function update(reply) {
    if (!reply || reply.phase === 'idle') {
      if (!['done', 'failed'].includes(current?.phase)) clear();
      return;
    }
    const terminal = ['done', 'failed'].includes(reply.phase);
    const key = `${reply.id || reply.replyId}:${reply.phase}:${reply.text}:${reply.error}`;
    if (terminal && terminalKey === key) return;
    cancel(timer);
    current = {...reply};
    show(current);
    if (terminal) {
      terminalKey = key;
      timer = schedule(clear, 15000);
    } else terminalKey = '';
  }
  return {update, clear};
}
