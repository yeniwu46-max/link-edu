// Vite-only acceptance entry. It cannot access real devices or write backend data.
import {createApp} from 'vue'
import {createPinia} from 'pinia'
import Fixture from './ClassroomUIFixture.vue'
import {api} from '../src/services/api.js'
import '../src/styles.css'
import '../src/classroom.css'
import '../src/ambient-effects.css'
import '../src/functional-ui.css'
const originalMedia=window.matchMedia.bind(window), reduce=new EventTarget()
reduce.matches=false
let hidden=false,unavailable=false,created=0,lost=0
const originalContext=HTMLCanvasElement.prototype.getContext,seen=new WeakSet()
HTMLCanvasElement.prototype.getContext=function(type,...args){
  if(type==='webgl2'||type==='webgl'){
    if(unavailable)return null
    const context=originalContext.call(this,type,...args)
    if(context&&!seen.has(this)){
      seen.add(this);created++
      this.addEventListener('webglcontextlost',()=>{lost++})
    }
    return context
  }
  return originalContext.call(this,type,...args)
}
window.matchMedia=query=>query==='(prefers-reduced-motion: reduce)'?reduce:originalMedia(query)
Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>hidden?'hidden':'visible'})
api.defaults.adapter=async config=>{throw {config,response:{status:503,data:{message:'验收夹具：保存暂不可用'}}}}
createApp(Fixture,{
  setReduced(value){reduce.matches=value;reduce.dispatchEvent(new Event('change'))},
  setHidden(value){hidden=value;document.dispatchEvent(new Event('visibilitychange'))},
  setUnavailable(value){unavailable=value},
  contextCounts(){return {created,lost,live:created-lost}},
}).use(createPinia()).mount('#app')
