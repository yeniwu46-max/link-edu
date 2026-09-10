import test from 'node:test'
import assert from 'node:assert/strict'
import { sessionFailure } from '../src/utils/authSession.js'

test('classifies a 401 as expired and other failures as offline', () => {
  assert.deepEqual(
    sessionFailure({ response: { status: 401, data: { message: '登录状态已失效，请重新登录' } } }),
    { status: 'expired', message: '登录状态已失效，请重新登录' },
  )
  assert.deepEqual(
    sessionFailure({ request: {} }),
    { status: 'offline', message: '暂时无法验证登录状态，请检查后端服务后重试' },
  )
})
