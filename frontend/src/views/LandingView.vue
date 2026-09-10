<template>
  <main ref="landing" class="landing">
    <section ref="hero" class="hero" id="hero">
      <div class="hero-media" aria-hidden="true">
        <video
          ref="heroGreet"
          class="hero-bg-video hero-bg-greet is-active"
          src="/assets/hero-greet.mp4"
          poster="/assets/hero-clean.png"
          autoplay
          muted
          playsinline
          preload="auto"
        ></video>
        <video
          ref="heroHair"
          class="hero-bg-video hero-bg-hair"
          src="/assets/hero-hair.mp4"
          poster="/assets/hero-clean.png"
          muted
          loop
          playsinline
          preload="auto"
        ></video>
      </div>
      <header class="hero-nav">
        <div class="hero-nav-left">
          <BrandMark />
          <div class="menu-wrap">
            <button class="menu motion-control" aria-label="打开导航菜单" :aria-expanded="menuOpen" @click="toggleMenu">
              <span></span><span></span><span></span>
            </button>
            <Transition name="menu-pop">
              <nav v-if="menuOpen" class="nav-popover" aria-label="首屏导航">
                <button @click="goHome">首页</button>
                <button @click="goLogin">登录训练</button>
                <button @click="goLogin">平台介绍</button>
              </nav>
            </Transition>
          </div>
        </div>
        <div class="hero-nav-right">
          <button class="outline motion-control" @click="goLogin">进入临客</button>
        </div>
      </header>
      <div class="hero-copy hero-copy-left">
        <h1>
          <DepthText
            text="LINK"
            :layers="8"
            :depth="2.4"
            face-color="#f8fafc"
            depth-color="#7c3aed"
            :tilt="10"
            :pointer-tracking="true"
            track="hero"
            :smoothing="0.18"
            :perspective="900"
            :auto-orbit="false"
            font-size="clamp(3.75rem, 8.3vw, 9.375rem)"
            :font-weight="900"
            font-family='"Segoe UI", Inter, "Arial Black", sans-serif'
            :shear-x="0.34"
            :shear-y="0.34"
            shadow
          />
        </h1>
        <p class="hero-en">AI MICROTEACHING PLATFORM</p>
        <p class="hero-cn">面向师范生与职前教师的 AI 微格教学训练平台</p>
      </div>
      <div class="hero-copy hero-copy-right">
        <h2>
          <DepthText
            text="临客"
            :layers="8"
            :depth="2.4"
            face-color="#f8fafc"
            depth-color="#7c3aed"
            :tilt="10"
            :pointer-tracking="true"
            track="hero"
            :smoothing="0.18"
            :perspective="900"
            :auto-orbit="false"
            font-size="clamp(3.4rem, 8vw, 8.875rem)"
            :font-weight="900"
            font-family='"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif'
            letter-spacing="0.06em"
            :line-height="1"
            :shear-x="-0.34"
            :shear-y="0.34"
            shadow
          />
        </h2>
        <p>先临课，再上课</p>
      </div>
      <button class="scroll-cue motion-control" @click="goLogin" aria-label="向下滚动进入登录">
        <span>SCROLL TO LOGIN</span><i></i>
      </button>
    </section>

    <section ref="loginSection" class="login" id="login">
      <div class="login-bg" aria-hidden="true">
        <video
          ref="loginVideo"
          class="login-bg-video"
          src="/assets/login-bg.mp4"
          poster="/assets/login-bg.png"
          autoplay
          muted
          loop
          playsinline
          preload="metadata"
        ></video>
      </div>
      <div class="login-haze" aria-hidden="true"></div>
      <header class="login-nav">
        <div class="hero-nav-left">
          <BrandMark />
        </div>
        <div class="hero-nav-right">
          <button class="outline motion-control" @click="goHome">返回首页</button>
        </div>
      </header>

      <div class="login-shell">
        <div ref="loginCard" class="login-card" :class="{ 'is-register': authMode === 'register' }">
          <div class="login-card-shine" aria-hidden="true"></div>
          <div class="login-card-noise" aria-hidden="true"></div>
          <div class="login-card-inner">
          <div class="login-card-head">
            <img class="login-card-logo" src="/assets/brand-icon.png" alt="" width="28" height="28" draggable="false" />
            <h1>{{ authMode === 'login' ? '欢迎回来！' : '创建账号' }}</h1>
            <p class="login-desc">
              {{
                authMode === 'login'
                  ? '继续你的 AI 微格教学训练，先临课，再上课。'
                  : '建立属于你的临课训练档案，开启师范生成长路径。'
              }}
            </p>
          </div>

          <div class="roles">
            <button type="button" :class="{ active: role === 'student' }" @click="selectRole('student', $event)">师范生</button>
            <button type="button" :class="{ active: role === 'teacher' }" @click="selectRole('teacher', $event)">指导教师</button>
          </div>

          <form class="login-form" @submit.prevent="submit">
            <label v-if="authMode === 'register'" class="login-field">
              <span>姓名</span>
              <input v-model="name" type="text" autocomplete="name" placeholder="请输入真实姓名" />
            </label>
            <label class="login-field">
              <span>{{ authMode === 'login' ? '账号' : '手机号 / 学号' }}</span>
              <input v-model="account" type="text" autocomplete="username" placeholder="请输入手机号或学号" />
            </label>
            <label class="login-field">
              <span>密码</span>
              <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入登录密码" />
            </label>
            <label v-if="authMode === 'register'" class="login-field">
              <span>确认密码</span>
              <input v-model="confirmPassword" type="password" autocomplete="new-password" placeholder="请再次输入密码" />
            </label>
          </form>

          <div v-if="authMode === 'login'" class="form-row">
            <n-checkbox v-model:checked="remember">记住我</n-checkbox>
            <a href="#" @click.prevent="showForgotPassword">忘记密码？</a>
          </div>

          <button class="login-submit motion-control" type="button" :disabled="loading" @click="submit">
            {{ buttonLabel }}
          </button>

          <div class="login-divider" aria-hidden="true"><span>或</span></div>

          <div class="social-row">
            <button type="button" class="social-btn motion-control" aria-label="使用 Google 登录" @click="socialComingSoon">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#EA4335" d="M12 10.2v3.6h5.1c-.2 1.2-1.6 3.5-5.1 3.5-3.1 0-5.6-2.6-5.6-5.8S8.9 5.7 12 5.7c1.8 0 3 .8 3.7 1.4l2.5-2.4C16.8 3.3 14.6 2.4 12 2.4 6.9 2.4 2.8 6.5 2.8 11.6S6.9 20.8 12 20.8c6.9 0 8.6-4.8 8.6-7.3 0-.5 0-.9-.1-1.3H12z"/><path fill="#34A853" d="M3.4 7.5l3 2.2c.8-2.5 3-4.3 5.6-4.3 1.8 0 3 .8 3.7 1.4l2.5-2.4C16.8 3.3 14.6 2.4 12 2.4 8.5 2.4 5.5 6.3 4.3 7.5z"/><path fill="#4A90E2" d="M12 20.8c2.4 0 4.4-.8 5.9-2.1l-2.7-2.2c-.8.5-1.8.9-3.2.9-2.5 0-4.6-1.7-5.3-4l-3 2.3C5.5 18.9 8.5 20.8 12 20.8z"/><path fill="#FBBC05" d="M20.5 12.3c0-.5 0-.9-.1-1.3H12v3.6h5.1c-.2 1.2-1.6 3.5-5.1 3.5v0c0 0 0 0 0 0l0 0 0 0v0H12c0 0 0 0 0 0v0c6.9 0 8.6-4.8 8.6-7.3z"/></svg>
            </button>
            <button type="button" class="social-btn motion-control" aria-label="使用 Facebook 登录" @click="socialComingSoon">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#1877F2" d="M24 12a12 12 0 1 0-13.9 11.8v-8.4H7.9V12h2.2V9.8c0-2.2 1.3-3.4 3.3-3.4.9 0 1.9.2 1.9.2v2.1h-1.1c-1.1 0-1.4.7-1.4 1.4V12h2.4l-.4 2.4h-2v8.4A12 12 0 0 0 24 12z"/></svg>
            </button>
            <button type="button" class="social-btn motion-control" aria-label="使用 Apple 登录" @click="socialComingSoon">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#fff" d="M16.7 12.6c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.7.8-3.4.8-.7 0-1.8-.8-3-.8-1.5 0-3 .9-3.8 2.3-1.6 2.8-.4 6.9 1.2 9.2.8 1.1 1.7 2.4 2.9 2.3 1.2 0 1.6-.8 3-.8 1.4 0 1.8.8 3 .8 1.2 0 2-1.1 2.8-2.2.9-1.3 1.2-2.6 1.2-2.7-.1 0-2.3-.9-2.3-3.5zm-2.2-6.4c.7-.8 1.1-1.9 1-3-.9 0-2 .6-2.7 1.4-.6.7-1.2 1.9-1 3 1.1.1 2.2-.6 2.7-1.4z"/></svg>
            </button>
          </div>

          <p class="register">
            {{ authMode === 'login' ? '还没有账号？' : '已经有账号了？' }}
            <a href="#" @click.prevent="switchMode">{{ authMode === 'login' ? '注册' : '返回登录' }}</a>
          </p>
          <p v-if="success" class="success" role="status">{{ success }}</p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import BrandMark from '../components/BrandMark.vue'
import DepthText from '../components/DepthText.vue'
import { useAuthStore } from '../stores/auth'
import { authErrorMessage, validateAuthForm } from '../utils/authValidation'

gsap.registerPlugin(ScrollTrigger)
const router = useRouter()
const auth = useAuthStore()
const landing = ref(null)
const hero = ref(null)
const loginSection = ref(null)
const loginCard = ref(null)
const loginVideo = ref(null)
const heroGreet = ref(null)
const heroHair = ref(null)
const menuOpen = ref(false)
const authMode = ref('login')
const role = ref('student')
const name = ref('')
const account = ref('demo')
const password = ref('link123')
const confirmPassword = ref('')
const remember = ref(true)
const loading = ref(false)
const error = ref('')
const success = ref('')
let media
let loginObserver
let onHeroGreetEnded = null
let hairKeepAlive = null
let greetWatchTimer = 0
const HERO_GREET_RATE = 0.9
const HERO_HAIR_RATE = 0.48

function prepHeroVideo(video, rate) {
  if (!video) return
  video.muted = true
  video.defaultMuted = true
  video.playsInline = true
  video.playbackRate = rate
}

function whenVideoReady(video) {
  if (!video) return Promise.reject(new Error('missing video'))
  if (video.readyState >= 2) return Promise.resolve(video)
  return new Promise((resolve, reject) => {
    const onReady = () => {
      cleanup()
      resolve(video)
    }
    const onError = () => {
      cleanup()
      reject(new Error('video load failed'))
    }
    const cleanup = () => {
      video.removeEventListener('loadeddata', onReady)
      video.removeEventListener('canplay', onReady)
      video.removeEventListener('error', onError)
    }
    video.addEventListener('loadeddata', onReady, { once: true })
    video.addEventListener('canplay', onReady, { once: true })
    video.addEventListener('error', onError, { once: true })
    // Do not call video.load() here — it aborts an in-flight autoplay.
  })
}

async function playWithRetry(video, { attempts = 10, gap = 160 } = {}) {
  if (!video) return false
  for (let i = 0; i < attempts; i += 1) {
    try {
      video.muted = true
      await video.play()
      if (!video.paused) return true
    } catch (err) {
      if (err?.name === 'NotAllowedError') return false
    }
    await new Promise((r) => window.setTimeout(r, gap))
  }
  return !video.paused
}

function clearGreetWatch() {
  if (greetWatchTimer) {
    window.clearInterval(greetWatchTimer)
    greetWatchTimer = 0
  }
}

function startHeroHairLoop() {
  const greet = heroGreet.value
  const hair = heroHair.value
  clearGreetWatch()
  if (!hair) return
  prepHeroVideo(hair, HERO_HAIR_RATE)
  if (greet) {
    greet.pause()
    greet.classList.remove('is-active')
  }
  hair.classList.add('is-active')
  hair.loop = true
  try { hair.currentTime = 0 } catch {}
  void playWithRetry(hair)
}

async function startHeroSequence() {
  const greet = heroGreet.value
  const hair = heroHair.value
  if (!greet || !hair) return

  clearGreetWatch()
  prepHeroVideo(greet, HERO_GREET_RATE)
  prepHeroVideo(hair, HERO_HAIR_RATE)

  // Always show greet first; hair stays invisible until greet ends.
  hair.pause()
  hair.classList.remove('is-active')
  greet.classList.add('is-active')

  try {
    await whenVideoReady(greet)
  } catch {
    startHeroHairLoop()
    return
  }

  // Only rewind if greet is idle / finished — never interrupt an in-flight autoplay.
  if (greet.paused || greet.ended || greet.currentTime > 0.35) {
    try { greet.currentTime = 0 } catch {}
  }
  try { hair.currentTime = 0 } catch {}

  if (onHeroGreetEnded) greet.removeEventListener('ended', onHeroGreetEnded)
  onHeroGreetEnded = () => startHeroHairLoop()
  greet.addEventListener('ended', onHeroGreetEnded, { once: true })

  const kickGreet = () => {
    if (!greet.classList.contains('is-active') || greet.ended) return
    prepHeroVideo(greet, HERO_GREET_RATE)
    void playWithRetry(greet, { attempts: 4, gap: 120 })
  }

  // Never skip greeting early — keep retrying until it plays through.
  if (greet.paused) kickGreet()
  greetWatchTimer = window.setInterval(() => {
    if (!greet.classList.contains('is-active')) {
      clearGreetWatch()
      return
    }
    if (greet.ended) {
      clearGreetWatch()
      startHeroHairLoop()
      return
    }
    if (greet.paused) kickGreet()
  }, 700)
}

const buttonLabel = computed(() =>
  loading.value
    ? authMode.value === 'login'
      ? '正在登录...'
      : '正在创建...'
    : authMode.value === 'login'
      ? '登录'
      : '创建并登录'
)

const scrollTo = (target) => target.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
const goLogin = () => {
  menuOpen.value = false
  scrollTo(loginSection)
  nextTick(() => playLoginVideo())
}
const goHome = () => {
  menuOpen.value = false
  scrollTo(hero)
  void startHeroSequence()
}

function feedback(target) {
  if (!target || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  gsap.fromTo(target, { scale: 0.96 }, { scale: 1, duration: 0.32, ease: 'power3.out', overwrite: true })
}
function toggleMenu(event) { menuOpen.value = !menuOpen.value; feedback(event.currentTarget) }
function selectRole(nextRole, event) { role.value = nextRole; feedback(event.currentTarget) }
function switchMode(event) {
  authMode.value = authMode.value === 'login' ? 'register' : 'login'
  error.value = ''
  success.value = ''
  if (authMode.value === 'register') {
    account.value = ''
    password.value = ''
  }
  feedback(event?.currentTarget)
  nextTick(() => ScrollTrigger.refresh())
}

function socialComingSoon() {
  error.value = ''
  success.value = '第三方登录即将开放，请先使用账号密码登录。'
}

function playLoginVideo() {
  const video = loginVideo.value
  if (!video) return
  video.muted = true
  video.defaultMuted = true
  video.playbackRate = 0.85
  const run = video.play()
  if (run && typeof run.catch === 'function') run.catch(() => {})
}

onMounted(async () => {
  if (auth.sessionNotice) {
    error.value = auth.sessionNotice
    auth.sessionNotice = ''
  }
  await nextTick()
  if (!landing.value) return
  try {
    const video = loginVideo.value
    if (video && loginSection.value) {
      video.muted = true
      video.defaultMuted = true
      video.playsInline = true
      video.playbackRate = 0.85
      playLoginVideo()
      loginObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) playLoginVideo()
          else loginVideo.value?.pause()
        })
      }, { threshold: 0.12 })
      loginObserver.observe(loginSection.value)
      let scrollAt = 0
      const onLandingScroll = () => {
        const now = performance.now()
        if (now - scrollAt < 120) return
        scrollAt = now
        const rect = loginSection.value?.getBoundingClientRect()
        if (rect && rect.top < window.innerHeight * 0.75) playLoginVideo()
        else loginVideo.value?.pause()
      }
      landing.value.addEventListener('scroll', onLandingScroll, { passive: true })
    }

    void startHeroSequence()

    const keepHairAlive = () => {
      const hair = heroHair.value
      const greet = heroGreet.value
      if (document.visibilityState !== 'visible') return
      if (greet?.classList.contains('is-active') && greet.paused && !greet.ended) {
        prepHeroVideo(greet, HERO_GREET_RATE)
        void playWithRetry(greet, { attempts: 3 })
      }
      if (hair?.classList.contains('is-active') && hair.paused) {
        prepHeroVideo(hair, HERO_HAIR_RATE)
        void playWithRetry(hair, { attempts: 3 })
      }
    }
    document.addEventListener('visibilitychange', keepHairAlive)
    landing.value?.addEventListener('pointerdown', keepHairAlive)
    hairKeepAlive = keepHairAlive

    media = gsap.matchMedia()
    media.add({ desktop: '(min-width: 901px)', reduceMotion: '(prefers-reduced-motion: reduce)' }, ({ conditions }) => {
      const scope = landing.value
      if (!scope) return () => {}

      if (!conditions.reduceMotion) {
        const intro = gsap.timeline({ defaults: { ease: 'power2.out' } })
        const nav = scope.querySelector('.hero-nav')
        const left = scope.querySelector('.hero-copy-left')
        const right = scope.querySelector('.hero-copy-right')
        const cue = scope.querySelector('.scroll-cue')
        if (nav) intro.from(nav, { autoAlpha: 0, y: -12, duration: 0.4 })
        if (left) intro.from(left, { autoAlpha: 0, x: -24, duration: 0.45 }, '-=.18')
        if (right) intro.from(right, { autoAlpha: 0, x: 24, duration: 0.45 }, '-=.35')
        if (cue) intro.from(cue, { autoAlpha: 0, y: 8, duration: 0.3 }, '-=.2')
        const scrollConfig = { scroller: landing.value }
        gsap.to(scope.querySelectorAll('.hero-copy'), {
          autoAlpha: 0, y: -20, ease: 'none',
          scrollTrigger: { ...scrollConfig, trigger: hero.value, start: '60% top', end: '95% top', scrub: 1 }
        })
        if (loginCard.value) {
          gsap.from(loginCard.value, {
            autoAlpha: 0, y: 28, duration: 0.55, ease: 'power2.out',
            scrollTrigger: { ...scrollConfig, trigger: loginSection.value, start: 'top 70%', toggleActions: 'play none none reverse' }
          })
        }
      }

      return () => {}
    }, landing.value)
    ScrollTrigger.refresh()
  } catch (err) {
    console.error('[LandingView] init failed', err)
  }
})
onUnmounted(() => {
  loginObserver?.disconnect()
  loginVideo.value?.pause()
  clearGreetWatch()
  const greet = heroGreet.value
  const hair = heroHair.value
  if (greet && onHeroGreetEnded) greet.removeEventListener('ended', onHeroGreetEnded)
  if (hairKeepAlive) {
    document.removeEventListener('visibilitychange', hairKeepAlive)
    landing.value?.removeEventListener('pointerdown', hairKeepAlive)
  }
  greet?.pause()
  hair?.pause()
  onHeroGreetEnded = null
  hairKeepAlive = null
  media?.revert()
})

async function submit(event) {
  if (loading.value) return
  feedback(event?.currentTarget)
  error.value = ''
  success.value = ''
  const formError = validateAuthForm({
    mode: authMode.value,
    name: name.value,
    account: account.value,
    password: password.value,
    confirmPassword: confirmPassword.value,
  })
  if (formError) {
    error.value = formError
    return
  }

  loading.value = true
  const isRegister = authMode.value === 'register'
  try {
    if (isRegister) {
      await auth.register({ name:name.value.trim(), account:account.value.trim(), password:password.value, role:role.value })
    }
    await auth.login({ account: account.value.trim(), password: password.value, role: role.value })
    success.value = isRegister ? '账号创建成功，正在进入工作台…' : ''
    router.push('/dashboard')
  } catch (e) {
    error.value = authErrorMessage(e)
  } finally {
    loading.value = false
  }
}

function showForgotPassword() {
  error.value = ''
  success.value = '当前版本暂未接入短信/邮箱找回，请联系管理员重置密码。'
}
</script>
