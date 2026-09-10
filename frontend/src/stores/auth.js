import { defineStore } from 'pinia'
import { api } from '../services/api'
import { sessionFailure } from '../utils/authSession'

const TOKEN_KEY = 'link_token'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    user: null,
    sessionStatus: localStorage.getItem(TOKEN_KEY) ? 'checking' : 'anonymous',
    sessionNotice: '',
    hydrated: false,
  }),
  actions: {
    async login(payload) {
      const { data } = await api.post('/auth/login', payload, { timeout: 8000 })
      this.token = data.access_token
      this.user = data.user
      this.sessionStatus = 'authenticated'
      this.sessionNotice = ''
      this.hydrated = true
      localStorage.setItem(TOKEN_KEY, this.token)
      return { access_token: this.token, user: this.user }
    },
    async register(payload) {
      const { data } = await api.post('/auth/register', payload, { timeout: 8000 })
      return data
    },
    async hydrate() {
      if (this.hydrated) return { status: this.sessionStatus }
      if (!this.token) {
        this.sessionStatus = 'anonymous'
        this.hydrated = true
        return { status: 'anonymous' }
      }
      try {
        const { data } = await api.get('/auth/me', { timeout: 8000 })
        this.user = data
        this.sessionStatus = 'authenticated'
        this.sessionNotice = ''
        this.hydrated = true
        return { status: 'authenticated', user: data }
      } catch (error) {
        const failure = sessionFailure(error)
        if (failure.status === 'expired') {
          this.expire(failure.message)
          return { status: 'expired' }
        }
        this.sessionStatus = 'offline'
        this.sessionNotice = failure.message
        return { status: 'offline' }
      }
    },
    expire(message = '登录状态已失效，请重新登录') {
      this.token = ''
      this.user = null
      this.sessionStatus = 'expired'
      this.sessionNotice = message
      this.hydrated = true
      localStorage.removeItem(TOKEN_KEY)
    },
    logout() {
      this.token = ''
      this.user = null
      this.sessionStatus = 'anonymous'
      this.sessionNotice = ''
      this.hydrated = true
      localStorage.removeItem(TOKEN_KEY)
    },
  },
})
