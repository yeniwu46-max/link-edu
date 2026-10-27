import { createApp, h, ref } from 'vue'
import PixelSprite from '../src/components/PixelSprite.vue'
const names=['小明','小雨','小林','阿贝贝老师'],ids=['ming','yu','lin','assistant']
const actions=['听讲','眨眼','阅读','书写','思考','举手','回答','发言','点头','疑惑','开心','转头']
const helper=['待命','眨眼','聆听','思考','挥手','介绍','回答','发言','点头','疑惑','开心','转头']
createApp({setup(){const frame=ref(0);return()=>h('div',{class:'cast'},[
  h('header',[h('p','LINK · 像素课堂'),h('h1','今天，也一起认真上课。'),h('span','实际页面使用的透明动作图集')]),
  h('nav',actions.map((label,i)=>h('button',{'aria-pressed':frame.value===i,onClick:()=>frame.value=i},`${String(i+1).padStart(2,'0')} ${label}`))),
  h('section',{class:'characters'},ids.map((id,i)=>h('article',[h(PixelSprite,{character:id,frame:frame.value}),h('h2',names[i]),h('p',(i===3?helper:actions)[frame.value])]))),
  h('footer','三名学生坐席 · 一位随身助手 / 同一套像素画风')
])}}).mount('#app')
const style=document.createElement('style');style.textContent=`
*{box-sizing:border-box}body{margin:0;background:#f5eee2;color:#412e4c;font-family:system-ui,sans-serif}.cast{max-width:1320px;padding:50px 44px;margin:auto}header p{letter-spacing:.2em;color:#9475a4;font-size:13px}h1{font-size:40px;margin:15px 0}header span{color:#827987;font-size:13px}nav{display:flex;flex-wrap:wrap;gap:8px;margin:35px 0}button{background:#fff9;border:1px solid #d8c9df;color:#5f486a;padding:10px 14px;border-radius:8px;cursor:pointer}button[aria-pressed=true]{background:#6b4582;color:white}button:focus-visible{outline:3px solid #c58638}.characters{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}.characters article{text-align:center;border-bottom:3px solid #d4bbdf;background:linear-gradient(transparent,#e4d5ea66);border-radius:20px;padding:15px}.characters .pixel-sprite{height:auto;aspect-ratio:1}.characters h2{font-size:19px;margin-bottom:3px}.characters p{color:#7c6b82;font-size:13px;margin-top:0}footer{text-align:center;color:#97889b;font-size:12px;margin-top:44px}@media(max-width:700px){.cast{padding:24px 16px}h1{font-size:28px}.characters{grid-template-columns:repeat(2,1fr)}}`;document.head.append(style)
