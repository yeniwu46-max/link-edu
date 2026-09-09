import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('merged AI review preserves real reports and cannot restore fixed-bonus corrections', () => {
  const source = readFileSync(new URL('../src/views/AiReviewView.vue', import.meta.url), 'utf8')
  assert.match(source, /v-if="report.demo" class="review-alert"/)
  assert.doesNotMatch(source, /@click="doRegenerate"|async function doRegenerate|regenerateFeedback,/)
  assert.match(source, /askAiReviewQuestion/)
  assert.match(source, /generateAiReview/)
})

test('merged dev server retains websocket proxy and collaborator realpath root', () => {
  const source = readFileSync(new URL('../vite.config.js', import.meta.url), 'utf8')
  assert.match(source, /root: realpathSync\(process.cwd\(\)\)/)
  assert.match(source, /ws: true/)
  assert.match(source, /LINK_BACKEND_URL/)
})
