export function isUnauthorizedError(error) {
  return error?.response?.status === 401
}

export function aiReviewErrorMessage(error) {
  const status = error?.response?.status
  if (status === 401) return '登录状态已失效，请重新登录后再生成 AI 评课。'
  if (status === 404) return '评课记录不存在，请重新选择历史报告。'
  if (status === 409) return '当前评课正在生成或训练尚未完成，请稍后刷新页面。'
  if (status === 429) return '评课请求过于频繁，请稍后再试。'
  if (status === 502) return 'DeepSeek 暂时没有生成报告，请检查服务配置后重试。'
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    return '请求超时，正在核对服务端状态，请稍后刷新。'
  }
  if (!error?.response) return '网络暂时不可用，请检查连接后重试。'
  return error?.response?.data?.message || 'AI 评课生成失败，请稍后重试。'
}

export function aiReviewQuestionErrorMessage(error) {
  const status = error?.response?.status
  if (status === 401) return '登录状态已失效，请重新登录后再追问。'
  if (status === 404) return '评课记录不存在，请重新选择历史报告。'
  if (status === 409) return '请先生成成功的 DeepSeek 评课报告后再追问。'
  if (status === 429) return '追问请求过于频繁，请稍后再试。'
  if (status === 502) return 'DeepSeek 暂时没有回答，请稍后再试。'
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    return '追问请求超时，请稍后再试。'
  }
  if (!error?.response) return '网络暂时不可用，请检查连接后重试。'
  return error?.response?.data?.message || 'AI 追问失败，请稍后再试。'
}
