<script setup>
import PixelSprite from './PixelSprite.vue'
</script>
<template><div class="pixel-class-preview" aria-hidden="true"><PixelSprite character="ming" /><PixelSprite character="yu" :frame="5" /><PixelSprite character="lin" :frame="2" /></div></template>
<style scoped>
.pixel-class-preview { position:absolute; right:8px; bottom:18px; width:250px; height:100px; display:flex; align-items:flex-end; pointer-events:none; z-index:1; }
.pixel-class-preview .pixel-sprite { width:92px; height:92px; flex:none; margin-left:-10px; }
.pixel-class-preview .pixel-sprite:nth-child(2) { transform:translateY(-10px); }
@media(max-width:700px) { .pixel-class-preview { width:148px; height:72px; right:10px; bottom:18px; } .pixel-class-preview .pixel-sprite { width:56px; height:56px; margin-left:-5px; } }
</style>
