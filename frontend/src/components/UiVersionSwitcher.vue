<script setup>
import { ref } from 'vue'
import { UI_VERSIONS, useUiVersion } from '../utils/uiVersion.js'
const { version, setVersion } = useUiVersion()
const error = ref('')
function change(event) {
  try { setVersion(event.target.value); error.value = '' }
  catch { error.value = '版本未保存，请检查浏览器存储权限。'; event.target.value = version.value }
}
</script>
<template>
  <label class="ui-version-switch"><span class="sr-only">UI 版本</span><select aria-label="UI 版本" :value="version" @change="change"><option v-for="item in UI_VERSIONS" :key="item.id" :value="item.id">{{ item.name }}</option></select><span v-if="error" role="alert">{{ error }}</span></label>
</template>
<style scoped>
.ui-version-switch { display:inline-flex; flex:none; align-items:center; gap:8px; }
.ui-version-switch select { max-width:120px; border:1px solid var(--line,#ac94bb66); border-radius:16px; padding:8px 12px; color:var(--text,#e9dced); background:var(--panel,#302636); font:inherit; font-size:12px; cursor:pointer; }
.ui-version-switch span[role=alert] { font-size:11px; max-width:180px; color:#d97763; }
:global([data-ui-theme=academy]) .ui-version-switch select { background:#eef3fa; color:#29496d; border-color:#b4c7df; }
</style>
