export function speechProviderLabel(provider) {
  return ({ xfyun: '讯飞', bailian: '百炼' })[provider] || '尚未确认的语音服务（暂不可开始）';
}

export function classroomLoadError(error, fallback) {
  return [401, 422].includes(error?.response?.status)
    ? '登录已失效，请退出后重新登录；已有课堂记录不会删除。'
    : fallback;
}
