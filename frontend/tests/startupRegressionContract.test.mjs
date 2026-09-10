import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const startup = await readFile(new URL('../../scripts/start-classroom.ps1', import.meta.url), 'utf8')
const regression = await readFile(new URL('../../scripts/run-regression.ps1', import.meta.url), 'utf8')

test('startup script performs environment, port, health, and demo-account preflight', () => {
  assert.ok(startup.includes('backend/.env'))
  assert.match(startup, /RequireEnv/)
  assert.match(startup, /sqlite:\/\//)
  assert.match(startup, /local SQLite fallback/i)
  assert.ok(startup.includes('frontend/node_modules/vite'))
  assert.match(startup, /api\/health/)
  assert.match(startup, /api\/auth\/login/)
  assert.match(startup, /DemoAccount = 'demo'/)
  assert.match(startup, /Frontend healthy/)
})

test('regression script records each check and blockers', () => {
  assert.match(regression, /backend-tests/)
  assert.match(regression, /frontend-tests/)
  assert.match(regression, /frontend-build/)
  assert.match(regression, /blockers/)
  assert.match(regression, /ConvertTo-Json/)
})
