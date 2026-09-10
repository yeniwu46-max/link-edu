import test from 'node:test'
import assert from 'node:assert/strict'
import {
  dashboardLoadErrorMessage,
  journalSubmitErrorMessage,
} from '../src/utils/dashboardState.js'

test('dashboard load errors remain actionable instead of falling back to demo success', () => {
  assert.equal(
    dashboardLoadErrorMessage({ response: { status: 401 } }),
    '登录状态已失效，请重新登录',
  )
  assert.equal(
    dashboardLoadErrorMessage({ response: { status: 503, data: { message: '服务暂不可用' } } }),
    '服务暂不可用',
  )
  assert.equal(
    dashboardLoadErrorMessage({ request: {} }),
    '工作台暂时无法连接后端，请检查服务是否已启动',
  )
})

test('journal submission errors are never converted into a local success', () => {
  assert.equal(
    journalSubmitErrorMessage({ request: {} }),
    '日志保存失败，请检查后端连接后重试',
  )
  assert.equal(
    journalSubmitErrorMessage({ response: { data: { message: '请先登录' } } }),
    '请先登录',
  )
})
