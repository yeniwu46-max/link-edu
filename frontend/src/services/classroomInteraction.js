export const emptyReply = () => ({
  id: null,
  studentId: null,
  text: "",
  phase: "idle",
  error: "",
  replyId: null,
});

export function reduceReply(current, message) {
  const m = message;
  if (m.type === "generation_started")
    return {
      ...emptyReply(),
      id: m.generation_id,
      studentId: m.student_id,
      phase: "thinking",
    };
  if (m.type === "reply")
    return {
      ...current,
      studentId: m.student_id,
      text: m.text,
      replyId: m.reply_id,
      action: m.action || current.action,
      phase: "queued",
    };
  if (m.type === "cancel" || m.type === "ended" || m.type === "disconnected")
    return emptyReply();
  if (m.type === "listening")
    return {
      ...current,
      phase: current.phase === "failed" ? "failed" : "done",
    };
  if (!current.id || current.id !== m.generation_id) return current;
  if (m.type === "generation_student")
    return { ...current, studentId: m.student_id };
  if (
    m.type === "reply_delta" &&
    ["thinking", "generating"].includes(current.phase) &&
    current.studentId === m.student_id
  )
    return {
      ...current,
      text: (current.text + m.delta).slice(0, 100),
      phase: "generating",
    };
  if (m.type === "generation_completed")
    return {
      ...current,
      studentId: m.student_id,
      text: m.text,
      action: m.action,
      phase: "queued",
    };
  if (m.type === "generation_failed")
    return { ...current, text: "", error: m.message, phase: "failed" };
  if (m.type === "generation_cancelled") return emptyReply();
  return current;
}

export const BODY_EDGES = [
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
  [11, 23],
  [12, 24],
  [23, 24],
  [23, 25],
  [25, 27],
  [24, 26],
  [26, 28],
  [27, 29],
  [29, 31],
  [28, 30],
  [30, 32],
];
export const HAND_EDGES = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 4],
  [0, 5],
  [5, 6],
  [6, 7],
  [7, 8],
  [5, 9],
  [9, 10],
  [10, 11],
  [11, 12],
  [9, 13],
  [13, 14],
  [14, 15],
  [15, 16],
  [13, 17],
  [0, 17],
  [17, 18],
  [18, 19],
  [19, 20],
];
export function containRect(width, height, videoWidth, videoHeight) {
  if (!videoWidth || !videoHeight) return { x: 0, y: 0, width: 0, height: 0 };
  const scale = Math.min(width / videoWidth, height / videoHeight);
  return {
    x: (width - videoWidth * scale) / 2,
    y: (height - videoHeight * scale) / 2,
    width: videoWidth * scale,
    height: videoHeight * scale,
  };
}
export function visiblePoint(point, body = false) {
  return (
    point &&
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= 0 &&
    point.x <= 1 &&
    point.y >= 0 &&
    point.y <= 1 &&
    (!body || point.visibility >= 0.6)
  );
}
