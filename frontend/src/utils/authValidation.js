export function validateAuthForm({ mode, name = '', account = '', password = '', confirmPassword = '' }) {
  if (!account.trim() || !password) return '请填写账号和密码'
  if (mode !== 'register') return ''
  if (!name.trim()) return '请输入姓名'
  if (password.length < 6) return '密码至少需要 6 位'
  if (password !== confirmPassword) return '两次输入的密码不一致'
  return ''
}

export function authErrorMessage(error) {
  if (!error?.response) return '无法连接服务，请检查后端是否已启动'
  return error.response.data?.message || '操作失败，请稍后重试'
}
