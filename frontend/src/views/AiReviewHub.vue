<script setup>
import { computed, defineAsyncComponent } from 'vue';
import { useRoute } from 'vue-router';
import ClassroomReviewView from './ClassroomReviewView.vue';
const LegacyReview = defineAsyncComponent(() => import('./AiReviewView.vue'));
const route=useRoute();
// Explicit legacy links remain compatible; never silently substitute a demo report.
const legacy=computed(()=>!route.query.classroom && (route.query.legacy==='1' || Boolean(route.query.sessionId || route.query.feedbackId)));
</script>
<template>
  <template v-if="legacy"><router-link class="review-return" to="/ai-review">← 返回课堂 AI 评课</router-link><LegacyReview /></template>
  <ClassroomReviewView v-else />
</template>
<style scoped>.review-return {display:inline-block;color:var(--orange);margin:12px 0;}</style>
