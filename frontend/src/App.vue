<template>
  <n-config-provider :theme="darkTheme">
    <n-message-provider>
      <ClickSpark
        spark-color="#ffffff"
        :spark-size="10"
        :spark-radius="15"
        :spark-count="8"
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
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { darkTheme, NConfigProvider, NMessageProvider } from 'naive-ui'
import ClickSpark from './components/ClickSpark.vue'
import NewtonsCradle from './components/NewtonsCradle.vue'
import { useBusyStore } from './stores/busy'

const busy = useBusyStore()
</script>
