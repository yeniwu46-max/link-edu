import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const view=await readFile(new URL('../src/components/HelpChat.vue',import.meta.url),'utf8')
test('FAQ search gives explicit no-result guidance',()=>{assert.match(view,/没有找到匹配的帮助内容/);assert.match(view,/下方提问/);assert.match(view,/matches/);assert.doesNotMatch(view,/我先按主路径回答/)})
test('human mode submits a real journal and reports API failures',()=>{assert.match(view,/await addJournal\(/);assert.match(view,/journalSubmitErrorMessage\(error\)/);assert.match(view,/问题已保存到你的训练日志/);assert.match(view,/问题保存失败/);assert.match(view,/draft.value\s*=\s*text/)})
test('assistant Q&A and explicit journal saving remain separate',()=>{assert.match(view,/client.send\('text'/);assert.match(view,/mode.value==='human'/);assert.match(view,/对话默认不保存/);assert.match(view,/保存本次问答到训练日志/);assert.match(view,/link:classroom-capture/);assert.match(view,/visibilitychange/)})
