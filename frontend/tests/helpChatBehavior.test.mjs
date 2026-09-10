import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = await readFile(new URL('../src/components/HelpChat.vue', import.meta.url), 'utf8')

test('FAQ search gives explicit no-result guidance', () => {
  assert.match(view, /没有找到匹配的帮助内容/)
  assert.match(view, /换个关键词/)
  assert.match(view, /切换到人工客服留言/)
  assert.doesNotMatch(view, /我先按主路径回答/)
})

test('human mode submits a real journal and reports API failures', () => {
  assert.match(view, /await addJournal\(/)
  assert.match(view, /journalSubmitErrorMessage\(error\)/)
  assert.match(view, /人工留言已保存到当前账号的训练日志/)
  assert.match(view, /人工留言保存失败/)
  assert.match(view, /不会直接连接外部坐席/)
})

test('bot and human modes have separate behavior and labels', () => {
  assert.match(view, /智能模式：只根据帮助中心 FAQ 回复/)
  assert.match(view, /人工模式：留言会提交到当前账号的训练日志/)
  assert.match(view, /mode === 'human' \? '人工客服' : '智能客服'/)
})
