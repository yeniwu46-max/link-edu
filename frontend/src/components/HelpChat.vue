<script setup>
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '../services/api.js'
import { addJournal } from '../services/dashboard'
import { AssistantClient } from '../services/assistantClient.js'
import { journalSubmitErrorMessage } from '../utils/dashboardState'
import { classroomHelpKey } from '../utils/classroomHelpContext.js'
import { useHelpPosition } from '../utils/useHelpPosition.js'
import { startTour } from '../utils/onboarding.js'
import { useAuthStore } from '../stores/auth.js'
import faqs from '../data/systemGuide.json'
import DigitalHuman from './DigitalHuman.vue'
import '../help-chat.css'
const context=inject(classroomHelpKey,ref(null)),auth=useAuthStore()
const fab=ref(null),panel=ref(null),logRef=ref(null),fullscreenTarget=ref(null)
const open=ref(false),mode=ref('bot'),query=ref(''),draft=ref(''),sending=ref(false),voice=ref(false),status=ref('idle'),level=ref(0),notice=ref(''),partial=ref('')
const messages=ref([{role:'bot',text:'我是 LINK 助手。可以帮你使用系统，也能依据知识库回答教学问题。'}])
const {fabStyle,panelStyle,onFabDown,onPanelDown,suppressClick,clampAll}=useHelpPosition(fab,panel)
const target=computed(()=>context.value?.target||fullscreenTarget.value||'body')
const inLesson=computed(()=>Boolean(context.value))
const guidance=computed(()=>context.value?.active?'授课中，文字帮助随时可用':context.value?.state==='ended'?'课堂已结束，可保存录像并查看评课报告。':'从一次训练开始，再用课堂证据安排复练。')
const statusText=computed(()=>({idle:'随时为你解答',connecting:'正在连接',listening:'正在聆听 · 停顿后自动发送',thinking:'正在查找依据',speaking:'正在回答 · 可说话打断',error:'暂时未连接'})[status.value]||'随时为你解答')
const shortcuts=[{key:'prepare',label:'课前准备'},{key:'settings',label:'设备检查'},{key:'call',label:'如何点名'},{key:'captions',label:'字幕设置'},{key:'timeline',label:'课堂记录'}]
const matches=computed(()=>{const key=query.value.trim();return faqs.filter(item=>!key||`${item.q}${item.a}`.includes(key))})
function eventReceived(event){
 if(event.type==='level'){level.value=event.level;return}
 if(event.type==='state')status.value=event.state
 if(event.type==='recognition'){partial.value=event.final?'':event.text;if(event.final){if(!messages.value.some(m=>m.turn===event.turn_id&&m.role==='user'))messages.value.push({role:'user',turn:event.turn_id,text:event.text})}}
 if(['answer_delta','answer'].includes(event.type)){
  let message=messages.value.find(m=>m.turn===event.turn_id&&m.role==='bot');if(!message){message={role:'bot',turn:event.turn_id,text:''};messages.value.push(message);message=messages.value.at(-1)}
  message.text=event.text;message.sources=event.sources||[];message.complete=event.type==='answer'
 }
 if(event.type==='cancel'){status.value=voice.value?'listening':'idle';level.value=0;const message=messages.value.find(m=>m.turn===event.cancelled_turn_id&&m.role==='bot');if(message&&!message.complete)message.text+='（已停止）'}
 if(event.type==='error'){notice.value=event.message;status.value='error';level.value=0;if(!client.session)voice.value=false}
 if(event.type==='closed'){voice.value=false;status.value='idle';notice.value=event.message;partial.value=''}
}
const client=new AssistantClient({api,onEvent:eventReceived})
function stopVoice(message=''){client.stop();voice.value=false;status.value='idle';level.value=0;partial.value='';notice.value=message}
function close(){stopVoice();open.value=false;nextTick(()=>fab.value?.focus())}
function toggle(event){if(!suppressClick(event))open.value?close():open.value=true}
function switchMode(value){stopVoice();mode.value=value;if(value==='human')notice.value='问题会保存到你的训练日志，不会发送给外部客服'}
function answer(item){messages.value.push({role:'bot',text:item.a,sources:[{id:'system:'+item.id,title:item.q,source:'LINK 功能说明'}]})}
function replay(){if(context.value?.active){notice.value='结束授课后可以重新查看导览';return}close();startTour()}
function runAction(key){if(key==='call'){answer(faqs.find(x=>x.id==='students'));return}const action=context.value?.actions?.[key];if(action){close();nextTick(action)}}
async function startVoice(){if(context.value?.active)return;notice.value='';voice.value=true;mode.value='bot';if(!await client.start('voice'))voice.value=false}
async function send(){
 const text=draft.value.trim();if(!text||sending.value||status.value==='connecting')return
 sending.value=true;draft.value='';notice.value=''
 try{
  if(mode.value==='human'){
   await addJournal({entry_date:new Date().toISOString().slice(0,10),body:`[帮助/问题记录] ${text}`});messages.value.push({role:'bot',text:'问题已保存到你的训练日志。'})
  }else{
   const ok=client.session||await client.start('text');if(!ok){draft.value=text;return}
   client.interrupt();client.send('text',{text})
  }
 }catch(error){draft.value=text;notice.value=mode.value==='human'?'问题保存失败：'+journalSubmitErrorMessage(error):'发送失败，请稍后重试'}finally{sending.value=false}
}
async function saveConversation(){
 if(sending.value)return;const lines=messages.value.filter(m=>m.turn&&m.complete!==false&&m.text).slice(-12).map(m=>`${m.role==='user'?'我':'LINK'}：${m.text}`)
 if(!lines.length){notice.value='暂无可保存的问答';return}sending.value=true
 try{await addJournal({entry_date:new Date().toISOString().slice(0,10),body:'[助手问答]\n'+lines.join('\n')});notice.value='问答已保存到训练日志'}catch(error){notice.value=journalSubmitErrorMessage(error)}finally{sending.value=false}
}
function openFromEvent(event){switchMode(event.detail?.mode==='human'?'human':'bot');open.value=true}
function fullscreenChanged(){fullscreenTarget.value=document.fullscreenElement;nextTick(clampAll)}
function escapePanel(event){if(open.value&&event.key==='Escape'){event.preventDefault();event.stopPropagation();close()}}
function hidden(){if(document.hidden)stopVoice('页面已隐藏，语音会话已停止')}
function captureStarted(){stopVoice('课堂采集中，请使用文字帮助')}
watch(open,async value=>{if(value){await nextTick();clampAll();panel.value?.querySelector('button')?.focus()}})
watch(()=>messages.value.map(m=>m.text).join(''),async()=>{await nextTick();if(logRef.value)logRef.value.scrollTop=logRef.value.scrollHeight})
watch(()=>context.value?.active,active=>{if(active)stopVoice('授课中，请使用文字助手')})
watch(()=>auth.user?.id,()=>{stopVoice();messages.value=[];open.value=false})
onMounted(()=>{window.addEventListener('link-help',openFromEvent);window.addEventListener('link:classroom-capture',captureStarted);document.addEventListener('visibilitychange',hidden);document.addEventListener('fullscreenchange',fullscreenChanged);document.addEventListener('keydown',escapePanel,true)})
onUnmounted(()=>{stopVoice();window.removeEventListener('link-help',openFromEvent);window.removeEventListener('link:classroom-capture',captureStarted);document.removeEventListener('visibilitychange',hidden);document.removeEventListener('fullscreenchange',fullscreenChanged);document.removeEventListener('keydown',escapePanel,true)})
</script>
<template>
<Teleport :to="target"><div class="help-dock" :class="{'in-lesson':inLesson,'lesson-active':context?.active}">
 <button ref="fab" class="help-fab digital-human-fab" type="button" :style="fabStyle" data-tour="assistant" @pointerdown="onFabDown" @click="toggle" aria-label="打开 LINK 数字人助手，可拖动调整位置" aria-controls="link-help-panel" :aria-expanded="open" aria-haspopup="dialog"><DigitalHuman :state="status" :level="level" :quiet="context?.active" /></button>
 <span v-if="!open&&!context?.active&&!fabStyle.left" class="help-fab__hint" aria-hidden="true">LINK 助手</span>
 <Transition name="assistant-panel"><section v-if="open" id="link-help-panel" ref="panel" class="help-chat" :style="panelStyle" role="dialog" aria-label="LINK 数字人助手" @keydown.esc.stop.prevent="close">
  <header class="help-chat__bar" @pointerdown="onPanelDown"><div><strong>LINK 助手</strong><p role="status">{{ statusText }}</p></div><button type="button" class="close-x" aria-label="关闭小助手" @click="close">×</button></header>
  <div class="help-chat__guide"><p>{{ guidance }}</p><div class="help-chat__shortcuts"><template v-if="inLesson"><button v-for="item in shortcuts" :key="item.key" type="button" @click="runAction(item.key)">{{ item.label }}</button></template><button type="button" :disabled="context?.active" @click="replay">新手引导</button></div></div>
  <div class="help-chat__tools"><input v-model="query" type="search" aria-label="搜索使用帮助" placeholder="查找使用帮助…"/><button type="button" :aria-pressed="mode==='bot'" @click="switchMode('bot')">问答</button><button type="button" :aria-pressed="mode==='human'" @click="switchMode('human')">记录问题</button></div>
  <div v-if="mode==='bot'" class="help-voice"><button v-if="!voice" type="button" :disabled="context?.active||status==='connecting'" @click="startVoice">开始语音对话</button><template v-else><button @click="stopVoice()">结束语音</button><button v-if="['speaking','thinking'].includes(status)" @click="client.interrupt()">停止回答</button></template><details><summary>语音与隐私</summary><p>点击开始后需授权麦克风，语音和问题将发送至系统已配置的语音及模型服务。默认中文，最多5分钟，静默60秒结束；对话默认不保存，可主动记录。授课期间仅支持文字。</p></details></div>
  <div v-if="query&&mode==='bot'" class="help-chat__matches"><button v-for="item in matches" :key="item.id" @click="answer(item)">{{ item.q }}</button><p v-if="!matches.length">没有找到匹配的帮助内容，可在下方提问。</p></div>
  <div ref="logRef" class="help-chat__log" aria-label="帮助对话"><article v-for="(item,index) in messages" :key="index" :class="item.role"><p>{{ item.text }}</p><details v-if="item.sources?.length" class="help-sources"><summary>依据 · {{ item.sources.length }}</summary><div v-for="source in item.sources" :key="source.id"><b>{{ source.title }}</b><span>{{ source.source }} {{ source.location }}</span></div></details></article></div>
  <p v-if="partial" class="help-partial">{{ partial }}</p><p v-if="notice" class="help-notice" role="status">{{ notice }}</p>
  <div v-if="mode==='bot'&&messages.some(m=>m.turn)" class="help-save"><button :disabled="sending" @click="saveConversation">保存本次问答到训练日志</button></div>
  <form class="help-chat__form" @submit.prevent="send"><input v-model="draft" maxlength="2000" type="text" aria-label="问题内容" :placeholder="mode==='human'?'记录到我的训练日志':'输入系统使用或教学问题'"/><button type="submit" :disabled="sending">{{ sending?'发送中…':mode==='human'?'保存':'发送' }}</button></form>
 </section></Transition>
</div></Teleport>
</template>
