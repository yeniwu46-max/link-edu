import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import LandingView from './views/LandingView.vue'
import AppShell from './layouts/AppShell.vue'
import DashboardView from './views/DashboardView.vue'
import CoursesView from './views/CoursesView.vue'
import TrainingView from './views/TrainingView.vue'
import ClassroomView from './views/ClassroomView.vue'
import AiReviewView from './views/AiReviewView.vue'
import GrowthView from './views/GrowthView.vue'
import ResourcesView from './views/ResourcesView.vue'
import ProfileView from './views/ProfileView.vue'
import './styles.css'

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
        { path: 'training', component: TrainingView, meta: { crumb: '教学训练  /  微格课堂', immersive: true } },
        { path: 'classroom', component: ClassroomView, meta: { crumb: '教学训练  /  模拟课堂' } },
        { path: 'ai-review', component: AiReviewView, meta: { crumb: 'AI 评课  /  报告' } },
        { path: 'growth', component: GrowthView, meta: { crumb: '成长档案  /  轨迹' } },
        { path: 'resources', component: ResourcesView, meta: { crumb: '资源库  /  教案与素材' } },
        { path: 'profile', component: ProfileView, meta: { crumb: '个人中心' } },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const authed = Boolean(localStorage.getItem('link_token'))
  if (to.matched.some((record) => record.meta.auth) && !authed) {
    return '/'
  }
  return true
})

createApp(App).use(createPinia()).use(router).mount('#app')
