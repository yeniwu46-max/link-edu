import { computed, readonly, shallowRef } from 'vue'
import { loadSettings, saveSettings } from './settings.js'

export const UI_THEMES = Object.freeze([
  { id: 'classic', name: '经典紫橙', description: '原有深色玻璃、动态背景与空间效果' },
  { id: 'academy', name: '银蓝学院', description: '钴蓝导航、银蓝底色与清晰的浅色面板' },
])
export const normalizeTheme = (value) => UI_THEMES.some(theme => theme.id === value) ? value : 'classic'
const theme = shallowRef('classic')
const isAcademy = computed(() => theme.value === 'academy')

// One application-level subscription; switching never changes a route/component key.
export function initializeTheme(target = window) {
  const sync = () => {
    theme.value = normalizeTheme(loadSettings().uiTheme)
    target.document.documentElement.dataset.uiTheme = theme.value
  }
  const storage = event => { if (event.key === 'link_settings' || event.key === null) sync() }
  sync()
  target.addEventListener('link-settings', sync)
  target.addEventListener('storage', storage)
  return () => {
    target.removeEventListener('link-settings', sync)
    target.removeEventListener('storage', storage)
  }
}

function setTheme(value) {
  // Persist before applying: denied storage leaves the active theme intact.
  saveSettings({ uiTheme: normalizeTheme(value) })
}

export function useUiTheme() {
  return { theme: readonly(theme), isAcademy, setTheme }
}

export const academyNaiveTheme = {
  common: {
    primaryColor: '#2851db', primaryColorHover: '#3865e6', primaryColorPressed: '#2044bd',
    primaryColorSuppl: '#2851db', textColorBase: '#203454', bodyColor: '#edf3fc',
    cardColor: '#ffffff', modalColor: '#ffffff', popoverColor: '#ffffff',
    borderColor: '#cbd8ec', borderRadius: '10px',
  },
}

// ECharts draws into canvas and cannot inherit CSS text colors. Preserve every
// original chart color in classic mode, map only presentation in academy mode.
export function useChartColors() {
  return (classicColor) => {
    if (!isAcademy.value) return classicColor
    const color = classicColor.toLowerCase().replaceAll(' ', '')
    const exact = {
      '#120f16': '#ffffff', '#f4f2f6': '#203454', '#9d97a3': '#617694',
      '#b9b3bd': '#617694', '#b45cff': '#2851db', '#ff7a18': '#198196',
      '#ffb45b': '#1257b0', '#ffb36a': '#1257b0', '#f0e9f4': '#203454',
      'rgba(255,255,255,.16)': '#cedbef', 'rgba(255,255,255,.08)': '#e6edf7',
      'rgba(255,255,255,.12)': '#d6e1f0', 'rgba(255,255,255,.02)': '#f8faff',
      'rgba(255,255,255,.05)': '#edf3fc',
    }
    if (exact[color]) return exact[color]
    if (color.startsWith('rgba(180,92,255,')) return color.replace('180,92,255', '40,81,219')
    if (color.startsWith('rgba(255,122,24,')) return color.replace('255,122,24', '25,129,150')
    return classicColor
  }
}
