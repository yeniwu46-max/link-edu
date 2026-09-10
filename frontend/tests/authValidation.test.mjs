import test from 'node:test'
import assert from 'node:assert/strict'
import { authErrorMessage, validateAuthForm } from '../src/utils/authValidation.js'

test('validates the minimum login and register fields', () => {
  assert.equal(validateAuthForm({ mode: 'login', account: '', password: '' }), '请填写账号和密码')
  assert.equal(validateAuthForm({ mode: 'register', name: '', account: 'a', password: '123456', confirmPassword: '123456' }), '请输入姓名')
  assert.equal(validateAuthForm({ mode: 'register', name: '甲', account: 'a', password: '12345', confirmPassword: '12345' }), '密码至少需要 6 位')
  assert.equal(validateAuthForm({ mode: 'register', name: '甲', account: 'a', password: '123456', confirmPassword: '654321' }), '两次输入的密码不一致')
  assert.equal(validateAuthForm({ mode: 'register', name: '甲', account: 'a', password: '123456', confirmPassword: '123456' }), '')
})

test('maps network and API authentication failures to visible messages', () => {
  assert.equal(authErrorMessage({ request: {} }), '无法连接服务，请检查后端是否已启动')
  assert.equal(authErrorMessage({ response: { status: 409, data: { message: '该账号已经注册，请直接登录' } } }), '该账号已经注册，请直接登录')
  assert.equal(authErrorMessage({ response: { status: 401, data: { message: '账号或密码错误' } } }), '账号或密码错误')
})
