<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { user, userVersion, clearSession } from './api'

const route = useRoute(), router = useRouter()
const u = computed(() => { route.path; userVersion.value; return user() })
const menu = computed(() => {
  const r = u.value?.role
  if (r === 'admin') return {
    main: [['/admin', 'ផ្ទាំងគ្រប់គ្រង'], ['/employees', 'បុគ្គលិក'], ['/leaves-admin', 'សុំច្បាប់']],
    more: [['/station', 'QR ស្ថានី'], ['/attendance-edit', 'កែវត្តមាន'], ['/holidays', 'ថ្ងៃឈប់សម្រាក'], ['/report', 'របាយការណ៍ប្រចាំខែ'], ['/settings', 'កំណត់']] }
  if (r === 'manager') return {
    main: [['/admin', 'ផ្ទាំងផ្នែក'], ['/leaves-admin', 'សុំច្បាប់'], ['/report', 'របាយការណ៍']],
    more: [['/scan', 'ស្កេន'], ['/my-report', 'វត្តមានខ្ញុំ'], ['/leave', 'ច្បាប់ខ្ញុំ']] }
  return { main: [['/scan', 'ស្កេន'], ['/my-report', 'របាយការណ៍'], ['/leave', 'សុំច្បាប់']], more: [] }
})
const open = ref(''), notifs = ref({ unread: 0, items: [] })
let timer
async function loadNotifs() { if (u.value) try { notifs.value = (await api.get('/notifications')).data } catch {} }
async function toggleBell() {
  open.value = open.value === 'bell' ? '' : 'bell'
  if (open.value === 'bell' && notifs.value.unread) { await api.post('/notifications/read'); setTimeout(loadNotifs, 1200) }
}
watch(() => route.path, () => { open.value = ''; loadNotifs() })
onMounted(() => { loadNotifs(); timer = setInterval(loadNotifs, 30000) })
onBeforeUnmount(() => clearInterval(timer))
const logout = () => { clearSession(); router.push('/login') }
const hide = computed(() => route.path === '/station' || ['/login', '/register'].includes(route.path))
</script>

<template>
  <header v-if="u && !hide" class="bg-royal text-white shadow-lg print:hidden relative z-40">
    <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
      <span class="font-moul text-gold-400 text-lg">វិហសចំណាលើ</span>
      <nav class="flex gap-1 flex-1 flex-wrap items-center">
        <router-link v-for="l in menu.main" :key="l[0]" :to="l[0]" class="px-3 py-1 rounded-lg hover:bg-white/10" active-class="bg-white/20">{{ l[1] }}</router-link>
        <div v-if="menu.more.length" class="relative">
          <button class="px-3 py-1 rounded-lg hover:bg-white/10" @click="open = open === 'more' ? '' : 'more'">ផ្សេងៗ ▾</button>
          <div v-if="open === 'more'" class="absolute left-0 mt-2 w-52 bg-white text-slate-700 rounded-2xl shadow-xl py-2">
            <router-link v-for="l in menu.more" :key="l[0]" :to="l[0]" class="block px-4 py-2 hover:bg-royal-50">{{ l[1] }}</router-link>
          </div>
        </div>
      </nav>

      <div class="relative">
        <button class="relative w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center" @click="toggleBell" aria-label="ការជូនដំណឹង">
          <svg viewBox="0 0 24 24" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
          <span v-if="notifs.unread" class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-gold text-[11px] font-bold flex items-center justify-center">{{ notifs.unread }}</span>
        </button>
        <div v-if="open === 'bell'" class="absolute right-0 mt-2 w-80 max-w-[85vw] bg-white text-slate-700 rounded-2xl shadow-xl overflow-hidden">
          <p class="px-4 py-3 font-semibold border-b">ការជូនដំណឹង</p>
          <div class="max-h-80 overflow-y-auto divide-y">
            <p v-if="!notifs.items.length" class="p-6 text-center text-slate-400 text-sm">មិនទាន់មានការជូនដំណឹង</p>
            <div v-for="n in notifs.items" :key="n.id" :class="['px-4 py-3 text-sm', n.read ? '' : 'bg-amber-50']">
              <p class="font-medium">{{ n.title }}</p><p class="text-slate-600 whitespace-pre-line">{{ n.body }}</p>
              <p class="text-xs text-slate-400 mt-1">{{ n.when }}</p></div>
          </div>
        </div>
      </div>

      <router-link to="/profile" class="flex items-center gap-2 hover:opacity-80" title="ប្រវត្តិរូបខ្ញុំ">
        <img v-if="u.photo" :src="u.photo" class="w-9 h-9 rounded-full object-cover border-2 border-gold" />
        <div class="text-sm leading-tight hidden sm:block"><p class="opacity-90">{{ u.name }}</p><p v-if="u.position" class="text-xs opacity-60">{{ u.position }}</p></div>
      </router-link>
      <button @click="logout" class="text-sm bg-gold px-3 py-1 rounded-lg">ចាកចេញ</button>
    </div>
  </header>
  <div v-if="open" class="fixed inset-0 z-30 print:hidden" @click="open = ''"></div>
  <router-view />
</template>
