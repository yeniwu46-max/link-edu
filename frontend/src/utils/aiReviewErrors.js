export function isUnauthorizedError(error) {
  return error?.response?.status === 401
}

export function aiReviewErrorMessage(error) {
  const status = error?.response?.status
  if (status === 401) return '登录状态已失效，请重新登录后再生成 AI 评课。'
  if (status === 409) return '当前评课正在生成或训练尚未完成，请稍后刷新页面。'
  if (status === 429) return '评课请求过于频繁，请稍后再试。'
  if (status === 502) return 'DeepSeek 暂时没有生成报告，请检查服务配置后重试。'
  return error?.response?.data?.message || 'AI 评课生成失败，请稍后重试。'
}
