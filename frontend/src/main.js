import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import LandingView from './views/LandingView.vue'
const AppShell = () => import('./layouts/AppShell.vue')
const DashboardView = () => import('./views/DashboardView.vue')
const CoursesView = () => import('./views/CoursesView.vue')
import { classroomEntry } from './services/classroomEntry.js'
const ClassroomView = () => import('./views/ClassroomView.vue')
const AiReviewView = () => import('./views/AiReviewHub.vue')
const GrowthView = () => import('./views/GrowthView.vue')
const ResourcesView = () => import('./views/ResourcesView.vue')
const ProfileView = () => import('./views/ProfileView.vue')
const RagKnowledgeView = () => import('./views/RagKnowledgeView.vue')
import { useAuthStore } from './stores/auth'
import './styles.css'
import './ambient-effects.css'
import './functional-ui.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: LandingView },
    {
      path: '/',
      component: AppShell,
      meta: { auth: true },
      children: [
        { path: 'dashboard', component: DashboardView, meta: { crumb: '工作台  /  总览' } },
        { path: 'courses', component: CoursesView, meta: { crumb: '课程中心  /  选课' } },
        { path: 'training', redirect: classroomEntry },
        { path: 'classroom', component: ClassroomView, meta: { crumb: '教学训练  /  模拟课堂' } },
        { path: 'ai-review', component: AiReviewView, meta: { crumb: 'AI 评课  /  报告' } },
        { path: 'growth', component: GrowthView, meta: { crumb: '成长档案  /  轨迹' } },
        { path: 'resources', component: ResourcesView, meta: { crumb: '资源库  /  教案与素材' } },
        { path: 'knowledge', component: RagKnowledgeView, meta: { crumb: '知识库  /  检索与语料' } },
        { path: 'profile', component: ProfileView, meta: { crumb: '个人中心' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

const pinia = createPinia()
const auth = useAuthStore(pinia)

router.beforeEach(async (to) => {
  const requiresAuth = to.matched.some((record) => record.meta.auth)
  if (!requiresAuth) return true
  if (!auth.token) return '/'
  if (!auth.user || auth.sessionStatus === 'checking' || auth.sessionStatus === 'offline') {
    const result = await auth.hydrate()
    if (result.status !== 'authenticated') return '/'
  }
  return true
})

window.addEventListener('link:auth-expired', (event) => {
  auth.expire(event.detail?.message || '登录状态已失效，请重新登录')
  if (router.currentRoute.value.path !== '/') router.replace('/')
})

createApp(App).use(pinia).use(router).mount('#app')
