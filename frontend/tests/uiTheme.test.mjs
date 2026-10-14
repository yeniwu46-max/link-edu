import test from 'node:test'
import assert from 'node:assert/strict'
import { initializeTheme, useUiTheme, useChartColors } from '../src/utils/uiTheme.js'
import { loadSettings, resetSettings, saveSettings } from '../src/utils/settings.js'

function browser(value) {
  const previousWindow = globalThis.window
  const previousStorage = globalThis.localStorage
  const target = new EventTarget()
  target.document = { documentElement: { dataset: {} } }
  const values = new Map(value === undefined ? [] : [['link_settings', value]])
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, next) => values.set(key, next),
    removeItem: key => values.delete(key),
  }
  globalThis.window = target
  globalThis.localStorage = storage
  const dispose = initializeTheme(target)
  return {
    target, values, storage,
    close() { dispose(); globalThis.window = previousWindow; globalThis.localStorage = previousStorage },
  }
}

test('existing, corrupt and unknown preferences keep the original theme', () => {
  for (const raw of [undefined, '{', '{"greetingLang":"zh"}', '{"uiTheme":"unknown"}']) {
    const env = browser(raw)
    try {
      assert.equal(useUiTheme().theme.value, 'classic')
      assert.equal(env.target.document.documentElement.dataset.uiTheme, 'classic')
    } finally { env.close() }
  }
})

test('switch, unrelated preference edits, reload and reset preserve the intended theme', () => {
  const env = browser('{"cameraDefault":true,"greetingLang":"en"}')
  try {
    useUiTheme().setTheme('academy')
    assert.equal(env.target.document.documentElement.dataset.uiTheme, 'academy')
    assert.equal(loadSettings().cameraDefault, true)
    saveSettings({ greetingLang: 'zh' })
    assert.equal(loadSettings().uiTheme, 'academy')
    assert.equal(useUiTheme().isAcademy.value, true)
    const fresh = new EventTarget()
    fresh.document = { documentElement: { dataset: {} } }
    const dispose = initializeTheme(fresh)
    assert.equal(fresh.document.documentElement.dataset.uiTheme, 'academy')
    dispose()
    resetSettings()
    assert.equal(useUiTheme().theme.value, 'classic')
    assert.equal(env.target.document.documentElement.dataset.uiTheme, 'classic')
  } finally { env.close() }
})

test('storage changes from another tab apply, unrelated keys do not', () => {
  const env = browser()
  try {
    env.values.set('link_settings', '{"uiTheme":"academy"}')
    const unrelated = new Event('storage')
    unrelated.key = 'link_token'
    env.target.dispatchEvent(unrelated)
    assert.equal(useUiTheme().theme.value, 'classic')
    const changed = new Event('storage')
    changed.key = 'link_settings'
    env.target.dispatchEvent(changed)
    assert.equal(useUiTheme().theme.value, 'academy')
    env.values.clear()
    const cleared = new Event('storage')
    cleared.key = null
    env.target.dispatchEvent(cleared)
    assert.equal(useUiTheme().theme.value, 'classic')
  } finally { env.close() }
})

test('denied persistence never applies a theme that was not saved', () => {
  const env = browser()
  try {
    env.storage.setItem = () => { throw new Error('Storage denied') }
    assert.throws(() => useUiTheme().setTheme('academy'), /Storage denied/)
    assert.equal(useUiTheme().theme.value, 'classic')
    assert.equal(env.target.document.documentElement.dataset.uiTheme, 'classic')
  } finally { env.close() }
})

test('charts restore exact original colors after a round trip', () => {
  const env = browser()
  try {
    const color = useChartColors()
    const palette = ['#b45cff', '#ff7a18', '#120f16', '#f4f2f6', 'rgba(255,255,255,.16)']
    assert.deepEqual(palette.map(color), palette)
    useUiTheme().setTheme('academy')
    assert.equal(color('#120f16'), '#ffffff')
    assert.equal(color('#f4f2f6'), '#203454')
    assert.equal(color('#b45cff'), '#2851db')
    useUiTheme().setTheme('classic')
    assert.deepEqual(palette.map(color), palette)
  } finally { env.close() }
})
