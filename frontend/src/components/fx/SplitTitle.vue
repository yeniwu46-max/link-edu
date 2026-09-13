<template>
  <h1 class="split-title">{{ text }}</h1>
</template>

<script setup>
defineProps({
  text: { type: String, default: '' },
})
</script>
