<script setup>
import { defineAsyncComponent } from 'vue'
import { useUiVersion } from '../utils/uiVersion.js'
const { isStudio } = useUiVersion()
const CourseDeskView = defineAsyncComponent(() => import('./CourseDeskView.vue'))
const OriginalCoursesView = defineAsyncComponent(() => import('./OriginalCoursesView.vue'))
</script>
<template><KeepAlive><component :is="isStudio ? CourseDeskView : OriginalCoursesView" /></KeepAlive></template>
