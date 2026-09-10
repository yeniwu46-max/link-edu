export function sessionFailure(error) {
  if (error?.response?.status === 401) {
    return {
      status: 'expired',
      message: error.response.data?.message || '登录状态已失效，请重新登录',
    }
  }
  return {
    status: 'offline',
    message: '暂时无法验证登录状态，请检查后端服务后重试',
  }
}
