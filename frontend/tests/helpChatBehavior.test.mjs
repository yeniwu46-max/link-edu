import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = await readFile(new URL('../src/components/HelpChat.vue', import.meta.url), 'utf8')

test('FAQ search gives explicit no-result guidance', () => {
  assert.match(view, /没有找到匹配的帮助内容/)
  assert.match(view, /换个关键词/)
  assert.match(view, /切换到问题记录/)
  assert.doesNotMatch(view, /我先按主路径回答/)
})

test('human mode submits a real journal and reports API failures', () => {
  assert.match(view, /await addJournal\(/)
  assert.match(view, /journalSubmitErrorMessage\(error\)/)
  assert.match(view, /问题已保存到你的训练日志/)
  assert.match(view, /问题保存失败/)
  assert.match(view, /不会发送给外部客服/)
  assert.match(view, /draft.value = text/)
})

test('bot and human modes have separate behavior and labels', () => {
  assert.match(view, /帮助内容来自常见问题库/)
  assert.match(view, /问题会保存到你的训练日志/)
  assert.match(view, /mode === 'human' \? '问题记录' : '常见问题'/)
})
