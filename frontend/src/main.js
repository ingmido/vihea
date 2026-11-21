import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { user } from './api'
import './style.css'

const isStaff = u => ['admin', 'manager'].includes(u?.role)
const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue') },
  { path: '/register', component: () => import('./views/RegisterView.vue') },
  { path: '/', redirect: () => (isStaff(user()) ? '/admin' : '/scan') },
  { path: '/admin', component: () => import('./views/AdminDashboard.vue'), meta: { staff: true } },
  { path: '/leaves-admin', component: () => import('./views/LeavesAdminView.vue'), meta: { staff: true } },
  { path: '/report', component: () => import('./views/ReportPrintView.vue'), meta: { staff: true } },
  { path: '/station', component: () => import('./views/StationQRView.vue'), meta: { admin: true } },
  { path: '/employees', component: () => import('./views/EmployeesView.vue'), meta: { admin: true } },
  { path: '/holidays', component: () => import('./views/HolidaysView.vue'), meta: { admin: true } },
  { path: '/attendance-edit', component: () => import('./views/AttendanceEditView.vue'), meta: { admin: true } },
  { path: '/settings', component: () => import('./views/SettingsView.vue'), meta: { admin: true } },
  { path: '/scan', component: () => import('./views/ScannerView.vue') },
  { path: '/my-report', component: () => import('./views/MyReportView.vue') },
  { path: '/profile', component: () => import('./views/ProfileView.vue') },
  { path: '/leave', component: () => import('./views/LeaveRequestView.vue') }
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(to => {
  const u = user()
  if (!['/login', '/register'].includes(to.path) && !u) return '/login'
  if (to.meta.admin && u?.role !== 'admin') return '/'
  if (to.meta.staff && !isStaff(u)) return '/'
})
createApp(App).use(router).mount('#app')

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
}
