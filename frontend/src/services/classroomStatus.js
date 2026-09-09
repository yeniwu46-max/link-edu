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

export function classroomCapabilitiesError(error) {
  const status = error?.response?.status;
  if ([401, 422].includes(status)) return classroomLoadError(error, '');
  if (['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code) || status === 408)
    return '读取课堂状态超时，请检查后端服务或网络，再重新读取状态。';
  if (!status)
    return '无法连接课堂后端，请确认后端服务已启动、网络正常，再重新读取状态。';
  if (status >= 500)
    return `课堂后端暂不可用（HTTP ${status}），请确认后端服务已启动并检查运行日志，再重新读取状态。`;
  return `课堂状态读取失败（HTTP ${status}），请检查访问权限后重新读取状态。`;
}

// The start button and its explanation share one source of truth.
export function classroomStartBlockers({ capabilities, capabilitiesLoading = false, capabilitiesError = '',
  consent, cameraConsent, busy = false, state = 'idle' } = {}) {
  const blockers = [];
  const add = (code, message, action) => blockers.push({ code, message, action });
  if (busy) {
    add('devices_busy', ['idle', 'disconnected'].includes(state)
      ? '摄像头正在开启，请处理浏览器的摄像头授权弹窗，等待预览完成后再开始授课。'
      : '正在开启麦克风、摄像头并连接课堂，请允许浏览器设备权限，勿重复开始。');
  }
  if (consent !== true) add('audio_consent', '尚未勾选「同意语音识别与 AI 评课」，请先确认语音与文字的使用用途。');
  if (cameraConsent !== true) add('camera_consent', '尚未勾选「同意摄像头开启」，请先确认摄像头使用用途。');
  if (capabilitiesLoading) {
    add('capabilities_loading', '正在读取课堂服务与额度状态，请稍候（最长 10 秒）。');
  } else if (capabilitiesError) {
    add('capabilities_error', capabilitiesError, 'refresh');
  } else if (!capabilities) {
    add('capabilities_missing', '尚未读取到课堂服务状态，请重新读取状态。', 'refresh');
  } else {
    for (const [key, label] of [['dialogue', '对话与评课'], ['asr', '语音识别'], ['tts', '学生语音']]) {
      const service = capabilities.services?.[key];
      if (!service) {
        add(`${key}_missing`, `未读取到${label}配置，请重新读取状态。`, 'refresh');
        continue;
      }
      if (!service.configured) add(`${key}_config`, `${label}服务未配置完整，请在课堂设置查看，并联系管理员补齐配置。`, 'settings');
      if (!service.pricing_confirmed) add(`${key}_pricing`, `${label}的单价尚未确认，请在课堂设置查看，并联系管理员核对价格。`, 'settings');
    }
    const budget = capabilities.budget;
    if (!budget) add('budget_missing', '未读取到授课额度，请重新读取状态。', 'refresh');
    else {
      if (!budget.pricing_confirmed) add('budget_pricing', '授课费用与预算配置尚未确认，请联系管理员核对后刷新状态。', 'settings');
      if (budget.stopped) add('budget_stopped', '授课额度已达到停止线，请在课堂设置查看额度详情，处理后重新读取状态。', 'settings');
    }
  }
  return blockers;
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
  if (event.type === 'pose' && data.motion_version === 2)
    return motionLabels(data).join(' · ') || '动作证据不足（未检测到、遮挡或模型不可用）';
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
import { motionLabels } from './motionFeatures.js';
