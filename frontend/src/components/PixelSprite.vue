<script setup>
import { computed } from 'vue'
import { pixelSource } from '../services/pixelCharacters.js'
const props = defineProps({ character: String, frame: { type: Number, default: 0 } })
const style = computed(() => ({ backgroundImage: `url("${pixelSource(props.character)}")`, backgroundPosition: `${(props.frame % 4) / 3 * 100}% ${Math.floor(props.frame / 4) / 2 * 100}%` }))
</script>
<template><span class="pixel-sprite" :style="style" aria-hidden="true" /></template>
<style scoped>
.pixel-sprite { display:block; width:100%; height:100%; aspect-ratio:1; background-size:400% 300%; background-repeat:no-repeat; image-rendering:pixelated; }
</style>
