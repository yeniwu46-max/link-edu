<template>
  <div class="theme-switcher" :class="{ 'theme-switcher--cards': cards }">
    <fieldset v-if="cards" class="theme-options">
      <legend class="sr-only">选择界面风格</legend>
      <label v-for="option in UI_THEMES" :key="option.id" class="theme-option" :class="{ selected: theme === option.id }">
        <input type="radio" name="ui-theme" :value="option.id" :checked="theme === option.id" @change="change(option.id, $event.target)" />
        <span class="theme-swatch" :class="`theme-swatch--${option.id}`" aria-hidden="true"><i></i><b></b></span>
        <span class="theme-option-copy"><strong>{{ option.name }}</strong><small>{{ option.description }}</small></span>
      </label>
    </fieldset>
    <label v-else class="theme-compact">
      <span class="sr-only">界面风格</span>
      <select aria-label="界面风格" :value="theme" @change="change($event.target.value, $event.target)">
        <option v-for="option in UI_THEMES" :key="option.id" :value="option.id">{{ option.name }}</option>
      </select>
    </label>
    <p v-if="error" class="theme-error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UI_THEMES, useUiTheme } from '../utils/uiTheme.js'
defineProps({ cards: Boolean })
const { theme, setTheme } = useUiTheme()
const error = ref('')
function change(value, select) {
  error.value = ''
  try { setTheme(value) } catch {
    error.value = '风格未保存，请检查浏览器存储权限后重试。'
    if (select?.tagName === 'SELECT') select.value = theme.value
    select?.closest('.theme-options')?.querySelectorAll('input').forEach(input => {
      input.checked = input.value === theme.value
    })
  }
}
</script>
