const KEY = 'link_settings'

export const SETTING_DEFAULTS = {
  cameraDefault: false,
  mode: 'fragment',
  scene: '导入',
  greetingLang: 'both',
  showDemoBadge: true,
}

export function loadSettings() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { ...SETTING_DEFAULTS, ...raw }
  } catch {
    return { ...SETTING_DEFAULTS }
  }
}

export function saveSettings(partial) {
  const next = { ...loadSettings(), ...partial }
  localStorage.setItem(KEY, JSON.stringify(next))
  window.dispatchEvent(new CustomEvent('link-settings'))
  return next
}

export function resetSettings() {
  localStorage.removeItem(KEY)
  window.dispatchEvent(new CustomEvent('link-settings'))
  return { ...SETTING_DEFAULTS }
}

export function openHelpChat(mode = 'bot') {
  window.dispatchEvent(new CustomEvent('link-help', { detail: { mode } }))
}
