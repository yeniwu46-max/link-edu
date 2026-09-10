<template>
  <main class="dashboard app-shell" :class="{ immersive: immersive, 'protected-shell': protectedShell }">
    <video
      v-if="!immersive && !protectedShell"
      class="app-shell-bg-video"
      src="/assets/login-bg.mp4"
      poster="/assets/login-bg.png"
      autoplay
      muted
      loop
      playsinline
      preload="metadata"
      aria-hidden="true"
    ></video>
    <div v-if="!immersive && !protectedShell" class="app-shell-bg-shade" aria-hidden="true"></div>
    <Aurora />
    <aside class="sidebar">
      <BrandMark />
      <nav>
        <router-link
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: isActive(item.to) }"
        >{{ item.label }}</router-link>
      </nav>
      <div class="side-bottom">
        <button type="button" @click="logout">退出登录</button>
      </div>
    </aside>

    <section class="workspace" :class="{ 'workspace--immersive': immersive }">
      <header v-if="!immersive" class="topbar">
        <span>{{ crumb }}</span>
        <label class="cir-search">
          <svg class="cir-search__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.8"/>
            <path d="M16.2 16.2L20 20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          <input
            v-model="search"
            class="cir-search__field"
            type="search"
            placeholder="搜索课程、训练或资源"
            aria-label="搜索课程、训练或资源"
            @keydown.enter="goSearch"
          />
          <kbd class="cir-search__kbd">Enter</kbd>
        </label>
        <div class="profile">
          <button class="profile-btn" type="button" :aria-expanded="menuOpen" @click.stop="menuOpen = !menuOpen">
            <b>{{ profileInitial }}</b>
            <span>{{ displayName }} · {{ roleLabel }}</span>
            <em :class="{ open: menuOpen }">▾</em>
          </button>
          <div v-if="menuOpen" class="profile-menu" role="menu" @click.stop>
            <button type="button" role="menuitem" @click="goProfile('archive')">个人中心</button>
            <button type="button" role="menuitem" @click="goProfile('settings')">设置</button>
            <button type="button" role="menuitem" @click="goProfile('contact')">联系我们</button>
          </div>
        </div>
      </header>

      <div class="page-frame">
        <router-view v-slot="{ Component }">
          <transition name="page-sweep" mode="out-in">
            <motion.div
              class="page-slot"
              :key="route.path === '/classroom' ? route.path : route.fullPath"
              :initial="route.path === '/classroom' ? { opacity: 1 } : { opacity: 0.2, filter: 'blur(6px)' }"
              :animate="{ opacity: 1, filter: route.path === '/classroom' ? 'none' : 'blur(0px)' }"
              :transition="{ duration: 0.35 }"
            >
              <component :is="Component" />
            </motion.div>
          </transition>
        </router-view>
      </div>
    </section>

    <HelpChat />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { motion } from 'motion-v'
import BrandMark from '../components/BrandMark.vue'
import HelpChat from '../components/HelpChat.vue'
import Aurora from '../components/fx/Aurora.vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const search = ref('')
const menuOpen = ref(false)

const nav = [
  { label: '工作台', to: '/dashboard' },
  { label: '课程中心', to: '/courses' },
  { label: '教学训练', to: '/classroom' },
  { label: 'AI 评课', to: '/ai-review' },
  { label: '成长档案', to: '/growth' },
  { label: '资源库', to: '/resources' },
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
// Keep the camera/player and evidence report outside the new console shell.
const protectedShell = computed(() => ['/classroom', '/ai-review'].includes(route.path))
const displayName = computed(() => auth.user?.name || '临客')
const roleLabel = computed(() => auth.user?.role_label || '师范生')
const profileInitial = computed(() => displayName.value.slice(0, 1))

function isActive(path) {
  return route.path === path
}

function goSearch() {
  const q = search.value.trim()
  router.push(q ? { path: '/courses', query: { q } } : '/courses')
}

function goProfile(tab) {
  menuOpen.value = false
  router.push({ path: '/profile', query: tab === 'archive' ? {} : { tab } })
}

function logout() {
  auth.logout()
  router.push('/')
}

onMounted(() => {
  auth.hydrate()
  window.addEventListener('click', () => { menuOpen.value = false })
})
</script>
