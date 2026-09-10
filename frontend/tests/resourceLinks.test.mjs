import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveResourceLink } from '../src/utils/resourceLinks.js'

const origin = 'https://link.example'
test('resource links distinguish missing, invalid, local and external files', () => {
  assert.equal(resolveResourceLink('', origin).status, 'missing')
  for (const url of ['javascript:alert(1)', 'data:text/html,hi', 'file:///etc/passwd', 'https://user:pass@example.com/a']) {
    assert.equal(resolveResourceLink(url, origin).status, 'invalid')
  }
  assert.deepEqual(resolveResourceLink('/files/lesson.pdf', origin), {
    status: 'ready', url: 'https://link.example/files/lesson.pdf', external: false,
  })
  assert.equal(resolveResourceLink('https://university.example/lesson', origin).external, true)
})
