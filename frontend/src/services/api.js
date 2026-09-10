import axios from 'axios'
import { useBusyStore } from '../stores/busy'
import { shouldTrackBusy } from '../utils/busyRequest'

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('link_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (shouldTrackBusy(config)) {
    try {
      useBusyStore().begin()
    } catch {
      /* pinia 尚未就绪时忽略 */
    }
  }
  return config
})

function releaseBusy() {
  try {
    useBusyStore().end()
  } catch {
    /* pinia 尚未就绪时忽略 */
  }
}

api.interceptors.response.use(
  (response) => {
    if (shouldTrackBusy(response.config)) releaseBusy()
    return response
  },
  (error) => {
    if (shouldTrackBusy(error.config)) releaseBusy()
    const requestUrl = error.config?.url || ''
    const isAuthRequest = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/register')
    if (error.response?.status === 401 && !isAuthRequest && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('link:auth-expired', {
        detail: { message: error.response.data?.message },
      }))
    }
    return Promise.reject(error)
  },
)
