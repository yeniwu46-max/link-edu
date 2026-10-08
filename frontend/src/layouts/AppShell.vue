<template>
  <main v-ambient-ui class="dashboard app-shell" :class="{ immersive: immersive, 'protected-shell': protectedShell }">
    <AmbientVideo
      v-if="!immersive && !protectedShell"
      class="app-shell-bg-video"
      source="/assets/login-bg-lite.mp4"
      fallback-source="/assets/login-bg.mp4"
      poster="/assets/login-bg.png"
      aria-hidden="true"
    />
    <div v-if="!immersive && !protectedShell" class="app-shell-bg-shade" aria-hidden="true"></div>
    <Aurora />
    <aside class="sidebar">
      <BrandMark />
      <nav aria-label="主导航">
        <router-link
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: isActive(item.to) }"
          :aria-current="isActive(item.to) ? 'page' : undefined"
        >{{ item.label }}</router-link>
      </nav>
      <div class="side-bottom">
        <button type="button" @click="logout">退出登录</button>
      </div>
    </aside>

    <section class="workspace" :class="{ 'workspace--immersive': immersive }">
      <header v-if="!immersive" class="topbar">
        <span class="page-crumb">{{ crumb }}</span>
        <select class="mobile-page-nav" aria-label="切换页面" :value="route.path" @change="router.push($event.target.value)">
          <option v-if="!nav.some(item => item.to === route.path)" :value="route.path" disabled>{{ crumb }}</option>
          <option v-for="item in nav" :key="item.to" :value="item.to">{{ item.label }}</option>
        </select>
        <form class="cir-search" role="search" @submit.prevent="goSearch">
          <svg class="cir-search__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.8"/>
            <path d="M16.2 16.2L20 20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <input
            v-model="search"
            class="cir-search__field"
            type="search"
            placeholder="搜索课程"
            aria-label="搜索课程"
          />
          <kbd class="cir-search__kbd">Enter</kbd>
        </form>
        <div class="profile">
          <button
            class="profile-btn"
            type="button"
            aria-haspopup="menu"
            aria-controls="profile-menu"
            :aria-expanded="menuOpen"
            @click.stop="menuOpen = !menuOpen"
          >
            <b>{{ profileInitial }}</b>
            <span>{{ displayName }} · {{ roleLabel }}</span>
            <em :class="{ open: menuOpen }">▾</em>
          </button>
          <div v-if="menuOpen" id="profile-menu" class="profile-menu" role="menu" @click.stop>
            <button type="button" role="menuitem" @click="goProfile('archive')">个人中心</button>
            <button type="button" role="menuitem" @click="goProfile('settings')">设置</button>
            <button type="button" role="menuitem" @click="goProfile('contact')">联系我们</button>
          </div>
        </div>
      </header>

      <div class="page-frame">
        <router-view v-slot="{ Component }">
          <transition name="page-sweep" mode="out-in">
            <div class="page-slot" :key="route.path === '/classroom' ? route.path : route.fullPath">
              <component :is="Component" />
            </div>
          </transition>
        </router-view>
      </div>
    </section>

    <HelpChat />
    <OnboardingTour />
  </main>
</template>

<script setup>
import { computed, onMounted, onUnmounted, provide, shallowRef, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BrandMark from '../components/BrandMark.vue'
import HelpChat from '../components/HelpChat.vue'
import OnboardingTour from '../components/OnboardingTour.vue'
import Aurora from '../components/fx/Aurora.vue'
import AmbientVideo from '../components/fx/AmbientVideo.vue'
import { ambientUi as vAmbientUi } from '../utils/ambientUi.js'
import { useAuthStore } from '../stores/auth'
import { buildSearchLocation } from '../utils/navigation'
import { classroomHelpKey } from '../utils/classroomHelpContext.js'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
provide(classroomHelpKey, shallowRef(null))
const search = ref('')
const menuOpen = ref(false)

const nav = [
  { label: '工作台', to: '/dashboard' },
  { label: '课程中心', to: '/courses' },
  { label: '教学训练', to: '/classroom' },
  { label: 'AI 评课', to: '/ai-review' },
  { label: '成长档案', to: '/growth' },
  { label: '资源库', to: '/resources' },
  { label: '知识库', to: '/knowledge' },
]

const crumb = computed(() => {
  if (route.path === '/profile') {
    if (route.query.tab === 'settings') return '设置'
    if (route.query.tab === 'contact') return '联系我们'
    return '个人中心'
  }
  return route.meta.crumb || '工作台  /  总览'
})
const immersive = computed(() => Boolean(route.meta.immersive))
// Keep console shell chrome (sidebar / workspace) consistent on every authenticated page.
const protectedShell = computed(() => false)
const displayName = computed(() => auth.user?.name || '临客')
const roleLabel = computed(() => auth.user?.role_label || '师范生')
const profileInitial = computed(() => displayName.value.slice(0, 1))

function isActive(path) {
  return route.path === path
}

function goSearch() {
  router.push(buildSearchLocation(search.value))
}

function goProfile(tab) {
  menuOpen.value = false
  router.push({ path: '/profile', query: tab === 'archive' ? {} : { tab } })
}

function logout() {
  auth.logout()
  router.push('/')
}

function closeMenu() {
  menuOpen.value = false
}

watch(() => route.query.q, (value) => {
  search.value = String(value || '')
}, { immediate: true })

onMounted(() => {
  auth.hydrate()
  window.addEventListener('click', closeMenu)
})

onUnmounted(() => {
  window.removeEventListener('click', closeMenu)
})
</script>
