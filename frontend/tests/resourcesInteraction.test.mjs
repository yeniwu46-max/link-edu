import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = await readFile(new URL('../src/components/CourseResourceCatalog.vue', import.meta.url), 'utf8')
const library = await readFile(new URL('../src/views/ResourcesView.vue', import.meta.url), 'utf8')

test('resource library reports load and link failures instead of fake success', () => {
  assert.match(view, /resourceError/)
  assert.match(view, /重新加载资源/)
  assert.match(view, /当前资源没有可用文件链接/)
  assert.match(view, /文件链接无效/)
  assert.doesNotMatch(view, /演示包暂无文件/)
})

test('resource actions validate real URLs and distinguish external links', () => {
  assert.match(view, /resolveResourceLink\(detail\.value\?\.file_url, window\.location\.origin\)/)
  assert.match(view, /v-if="!link.external"[^>]+download/)
  assert.match(view, /noopener noreferrer/)
  assert.match(library, /CourseResourceCatalog/)
  assert.match(library, /DraggableResourceCard/)
})
