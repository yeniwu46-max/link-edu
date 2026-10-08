<script setup>
import InteractiveModel from './fx/InteractiveModel.vue'
import HelpRobotIcon from './HelpRobotIcon.vue'
defineProps({ attentive:Boolean, live:Boolean, quiet:Boolean, reaction:Number })
</script>
<template>
  <span class="help-avatar" :class="{'is-live':live}" aria-hidden="true">
    <InteractiveModel v-if="live" kind="robot" :interactive="false" follow-parent :active="attentive" :reaction="reaction" :quiet="quiet">
      <HelpRobotIcon :attentive="attentive" />
    </InteractiveModel>
    <HelpRobotIcon v-else :attentive="attentive" />
  </span>
</template>
<style scoped>
.help-avatar { display:block; width:100%; height:100%; flex:none; }
.help-avatar.is-live { filter:drop-shadow(0 4px 10px #b45cff22); }
</style>
