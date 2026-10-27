import {createDigitalHuman} from '../src/components/fx/digitalHumanEngine.js'
const host=document.querySelector('#avatar'),result=document.querySelector('#result')
let engine,created=0,disposed=0,policy={finePointer:true,visible:true,reducedMotion:false}
async function mount(){engine=await createDigitalHuman(host,{policy,onError:()=>result.textContent='加载失败',onReady:()=>result.textContent='像素 LINK 助手已加载'});created++}
await mount()
document.querySelector('#measure').onclick=()=>{const before=engine.stats(),start=performance.now();result.textContent='测量中';setTimeout(()=>{const after=engine.stats(),seconds=(performance.now()-start)/1000;result.textContent=JSON.stringify({seconds,fps:(after.frames-before.frames)/seconds,averageRenderMs:(after.renderMs-before.renderMs)/(after.frames-before.frames),...after,created,disposed},null,2)},10000)}
document.querySelector('#reduced').onclick=()=>{policy={...policy,reducedMotion:!policy.reducedMotion};engine.setPolicy(policy);result.textContent=JSON.stringify(policy)}
document.querySelector('#hidden').onclick=()=>{policy={...policy,visible:!policy.visible};engine.setPolicy(policy);result.textContent=JSON.stringify(policy)}
document.querySelector('#remount').onclick=async()=>{for(let i=0;i<3;i++){engine.dispose();disposed++;await mount();await new Promise(r=>setTimeout(r,700))}result.textContent=JSON.stringify({created,disposed,live:created-disposed})}
document.querySelector('#poster').onclick=()=>{const a=document.querySelector('#download');a.href=engine.snapshot();a.hidden=false;a.download='pixel-assistant-poster.png';let image=document.querySelector('#poster-preview');if(!image){image=document.createElement('img');image.id='poster-preview';image.alt='像素助手透明封面';image.style.width='140px';document.body.append(image)}image.src=a.href}
for(const state of ['idle','listening','thinking','speaking']){const button=document.createElement('button');button.textContent=state;button.onclick=()=>engine.setState(state,state==='speaking'?.7:0);document.body.append(button)}
