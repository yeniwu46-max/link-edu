export function dashboardLoadErrorMessage(error) {
  if (error?.response?.status === 401) return '登录状态已失效，请重新登录'
  return error?.response?.data?.message || '工作台暂时无法连接后端，请检查服务是否已启动'
}

export function journalSubmitErrorMessage(error) {
  return error?.response?.data?.message || '日志保存失败，请检查后端连接后重试'
}

export function regenerateErrorMessage(error) {
  return error?.response?.data?.message || '报告重写失败，请检查后端连接后重试'
}
