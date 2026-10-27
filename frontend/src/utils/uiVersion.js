import { computed, readonly, shallowRef } from 'vue'
export const UI_VERSIONS = Object.freeze([{ id:'studio', name:'备课桌版' }, { id:'original', name:'原版界面' }])
export const normalizeUiVersion = value => value === 'original' ? 'original' : 'studio'
const version = shallowRef('studio')
export function initializeUiVersion(target = window) {
  const sync = () => {
    try { version.value = normalizeUiVersion(target.localStorage.getItem('link-ui-version')) } catch { version.value = 'studio' }
    target.document.documentElement.dataset.uiVersion = version.value
  }
  const storage = event => { if (event.key === 'link-ui-version' || event.key === null) sync() }
  sync(); target.addEventListener('storage', storage)
  return () => target.removeEventListener('storage', storage)
}
export function useUiVersion() {
  return { version:readonly(version), isStudio:computed(() => version.value === 'studio'),
    setVersion(value) {
      const next = normalizeUiVersion(value)
      localStorage.setItem('link-ui-version', next)
      version.value = next; document.documentElement.dataset.uiVersion = next
    } }
}
