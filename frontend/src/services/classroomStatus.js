export function speechProviderLabel(provider) {
  return (
    { xfyun: "讯飞", bailian: "百炼" }[provider] ||
    "尚未确认的语音服务（暂不可开始）"
  );
}

export function classroomLoadError(error, fallback) {
  return [401, 422].includes(error?.response?.status)
    ? "登录已失效，请退出后重新登录；已有课堂记录不会删除。"
    : fallback;
}

export function connectionSummary(services, keys) {
  const items = keys.map((key) => services?.[key]);
  if (items.some((item) => item?.status === "failed"))
    return { tone: "failed", label: "连接异常" };
  if (
    items.some((item) => item && (!item.configured || !item.pricing_confirmed))
  )
    return { tone: "warning", label: "待设置" };
  if (items.some((item) => !item)) return { tone: "pending", label: "读取中…" };
  if (items.every((item) => item.status === "available"))
    return { tone: "available", label: "检查通过" };
  return { tone: "pending", label: "待检查" };
}

export function budgetNotice(budget) {
  if (!budget) return "";
  const accounts = Object.values(budget.credits?.accounts || {});
  const stopped = accounts
    .filter((account) => account.stopped)
    .map((account) => account.label);
  if (stopped.length)
    return `${stopped.join("、")}额度达到停止线，请查看额度详情。`;
  if (budget.stopped) return "调用额度达到停止线，请查看额度详情。";
  if (budget.warning || accounts.some((account) => account.warning))
    return "部分调用额度即将达到上限，请查看额度详情。";
  return "";
}

export const isTechnicalEvent = (event) =>
  ![
    "transcript",
    "student",
    "question",
    "vision",
    "pose",
    "interrupt",
    "correction",
    "error",
  ].includes(event.type);

export function eventLabel(event) {
  return (
    {
      transcript: "老师",
      student: event.data.name || "学生",
      question: "学生举手",
      vision: "画面观察",
      pose: "动作观察",
      interrupt: "已打断",
      correction: "评课补充",
      error: "课堂提醒",
      latency: "语音延迟",
      playback: "播放状态",
    }[event.type] || "连接记录"
  );
}

export function eventText(event) {
  const data = event.data;
  if (data.text || data.observations || data.objection || data.message)
    return data.text || data.observations || data.objection || data.message;
  if (event.type === "latency") return `${data.latency_ms} ms`;
  if (event.type === "pose")
    return data.present === null
      ? "画面暂不清晰"
      : data.present
        ? `人物在画面内${data.left_raised || data.right_raised ? " · 已抬手" : ""}`
        : "未检测到人物";
  return (
    {
      playback_completed: "播放完成",
      playback_failed: "播放失败",
      playback_started: "开始播放",
      playback_cancelled: "播放已取消",
      cancelled: "已取消",
    }[data.status] ||
    data.status ||
    "已记录"
  );
}
