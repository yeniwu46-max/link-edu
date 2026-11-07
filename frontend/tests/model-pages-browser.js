// Dev-only visual acceptance. Real page components, in-memory identity, no API/device writes.
import {createApp} from 'vue'
import {createPinia} from 'pinia'
import {createRouter,createMemoryHistory} from 'vue-router'
import App from '../src/App.vue'
import AppShell from '../src/layouts/AppShell.vue'
import {useAuthStore} from '../src/stores/auth.js'
import {api} from '../src/services/api.js'
import '../src/styles.css'
import '../src/ambient-effects.css'
import '../src/functional-ui.css'
const pinia=createPinia(), auth=useAuthStore(pinia)
auth.$patch({token:'',user:{id:-1,name:'界面验收',role_label:'模拟数据'},hydrated:true,sessionStatus:'authenticated'})
navigator.mediaDevices.getUserMedia=async()=>{throw new Error('验收页面不访问真实设备')}
const service={configured:true,pricing_confirmed:true,status:'available',provider:'mock',model:'ui-fixture'}
api.defaults.adapter=async config=>{
  if(config.method!=='get')throw{config,response:{status:503,data:{message:'界面验收不写入数据'}}}
  const key=config.url.split('?')[0]
  let data={items:[]}
  if(key==='/classroom/capabilities')data={pose_assets:true,services:{dialogue:service,asr:service,tts:service,vision:service},budget:{pricing_confirmed:true,stopped:false,warning:false}}
  if(key==='/courses')data={items:['导入技能','板书板画技能','演示技能'].map((title,i)=>({id:i+1,title,stage:'专项0'+(i+1),category:'专项0'+(i+1),description:'从示例中理解教学方法，在模拟课堂中进行练习。',lesson_count:6,status:i===0?'in_progress':'not_started',status_label:i===0?'进行中':'未开始',progress_percent:i===0?40:0}))}
  if(key==='/growth')data={points:[],records:[],heatmap:[],milestones:[],summaries:[],journals:[]}
  return{config,status:200,statusText:'OK',headers:{},data}
}
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:AppShell,children:[
  {path:'profile',component:()=>import('../src/views/ProfileView.vue')},
  {path:'dashboard',component:()=>import('../src/views/DashboardView.vue')},
  {path:'knowledge',component:()=>import('../src/views/RagKnowledgeView.vue')},
  {path:'classroom',component:()=>import('../src/views/ClassroomView.vue'),meta:{crumb:'教学训练 / 模拟课堂'}},
  {path:'courses',component:()=>import('../src/views/CoursesView.vue'),meta:{crumb:'课程中心 / 选课'}},
  {path:'resources',component:()=>import('../src/views/ResourcesView.vue'),meta:{crumb:'资源库 / 教案与素材'}},
  {path:'growth',component:()=>import('../src/views/GrowthView.vue'),meta:{crumb:'成长档案 / 轨迹'}},
  {path:'ai-review',component:()=>import('../src/views/ClassroomReviewView.vue'),meta:{crumb:'AI 评课 / 报告'}},
  {path:':pathMatch(.*)*',redirect:'/classroom'},
]}]})
await router.push('/classroom')
createApp(App).use(pinia).use(router).mount('#app')
