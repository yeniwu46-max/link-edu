import {createStudentStage} from '../src/components/fx/studentStageEngine.js'
const style=document.createElement('style');style.textContent='*{box-sizing:border-box}body{margin:0;padding:32px;background:#f5eee4;color:#49324e;font-family:system-ui}h1{font-size:30px}p{color:#856b8e}nav{display:flex;gap:10px;margin:24px 0}button{padding:10px 18px;background:#e1c9e9;border:0;border-radius:10px;color:#49324e;cursor:pointer}#stage{position:relative;width:900px;height:330px;max-width:100%;background:#fff8ef;border-radius:24px}#canvas{position:absolute;inset:0}canvas{width:100%;height:100%;image-rendering:pixelated}.seats{position:absolute;inset:0;display:flex;justify-content:space-around}article{flex:1;min-width:0;text-align:center}article>div{height:285px}output{display:block;margin:20px;color:#856b8e}';document.head.append(style)
const host=document.querySelector('#canvas'),abort=new AbortController()
const stage=await createStudentStage(host,{signal:abort.signal,policy:{visible:true,reducedMotion:false,finePointer:true},getSlots:()=>[...document.querySelectorAll('article')].map(e=>({id:e.dataset.id,element:e.firstElementChild})),onModelState:()=>{}})
let timer, state={}
function action(name){clearInterval(timer);state={previewAction:name};if(name==='speech'){let step=0;timer=setInterval(()=>{step++;state={playbackStudent:step<30?'yu':null,level:step%4<2?.6:0,reply:{phase:step<30?'speaking':'done',studentId:'yu'}};stage.setState(state);if(step>40)clearInterval(timer)},100)}stage.setState(state)}
for(const [key,name]of [['doze','打瞌睡'],['confused','疑惑'],['writing','拿笔写字'],['speech','起立发言 → 坐下'],[null,'自然听讲']]){const button=document.createElement('button');button.textContent=name;button.onclick=()=>action(key);document.querySelector('nav').append(button)}
stage.setVisible(true);stage.setCapture(true);window.__pixelPreview={stage,action}
window.addEventListener('pagehide',()=>{clearInterval(timer);abort.abort()})
const update=setInterval(()=>document.querySelector('output').textContent=['ming','yu','lin'].map(id=>id+': '+host.dataset[id+'Action']+' '+host.dataset[id+'Frame']).join(' / '),100)
window.addEventListener('pagehide',()=>clearInterval(update))
