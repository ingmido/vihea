import axios from 'axios'
import { ref } from 'vue'
export const userVersion = ref(0)  // bump to refresh header after profile edits

// Stable per-phone id (survives logout) — used for "one phone per account".
export function deviceId() {
  let d = localStorage.getItem('device_id')
  if (!d) {
    d = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`)
    localStorage.setItem('device_id', d)
  }
  return d
}
export const clearSession = () => { localStorage.removeItem('token'); localStorage.removeItem('user') }

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use(c => {
  const t = localStorage.getItem('token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  c.headers['X-Device-Id'] = deviceId()
  return c
})
api.interceptors.response.use(r => r, e => {
  if (e.response?.status === 401 || e.response?.status === 422) {
    clearSession(); if (!['/login', '/register'].includes(location.pathname)) location.href = '/login'
  }
  return Promise.reject(e)
})
export const user = () => JSON.parse(localStorage.getItem('user') || 'null')
export default api
