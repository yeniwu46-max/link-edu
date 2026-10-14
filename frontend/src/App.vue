<template>
  <NConfigProvider :theme="academyActive ? null : darkTheme" :theme-overrides="academyActive ? academyNaiveTheme : undefined">
    <NMessageProvider>
      <ClickSpark
        spark-color="#ffffff"
        :spark-size="10"
        :spark-radius="15"
        :spark-count="academyActive ? 0 : 8"
        :duration="400"
      >
        <router-view />
      </ClickSpark>
      <div
        v-if="busy.visible"
        class="busy-overlay"
        role="status"
        aria-live="polite"
        aria-label="加载中"
      >
        <NewtonsCradle />
      </div>
    </NMessageProvider>
  </NConfigProvider>
</template>

<script setup>
import { darkTheme, NConfigProvider, NMessageProvider } from 'naive-ui'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useUiTheme, academyNaiveTheme } from './utils/uiTheme.js'
import ClickSpark from './components/ClickSpark.vue'
import NewtonsCradle from './components/NewtonsCradle.vue'
import { useBusyStore } from './stores/busy'

const busy = useBusyStore()
const { isAcademy } = useUiTheme()
const route = useRoute()
const academyActive = computed(() => isAcademy.value && route.path !== '/')
</script>
