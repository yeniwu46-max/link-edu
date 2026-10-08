<script setup>
import { ref } from 'vue'
import InteractiveModel from './InteractiveModel.vue'
defineProps({ kind:String, label:String })
const expanded = ref(false)
</script>
<template><figure class="model-showcase" data-tour="model"><InteractiveModel :kind="kind" :label="label" :active="expanded" @activate="expanded=!expanded" @reset="expanded=false" /></figure></template>
<style scoped>
.model-showcase { flex:none; width:140px; height:116px; margin:0; position:relative; isolation:isolate; }
.model-showcase::before { content:''; position:absolute; inset:30% 5% 5%; z-index:-1; border-radius:50%; background:radial-gradient(ellipse,#a558cc18,transparent 65%); pointer-events:none; }
@media(max-width:700px) { .model-showcase { width:90px; height:86px; } }
@media print { .model-showcase { display:none; } }
</style>
