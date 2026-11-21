<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QRCode from 'qrcode'
import api from '../api'
import { speak, speakParts } from '../voice'

const route = useRoute(), router = useRouter()
const canvas = ref(null), left = ref(30), interval = ref(30), err = ref('')
const locations = ref([]), loc = ref(Number(route.query.loc) || 0), locName = ref('')
let timer, poll, busy = false
// ---- voice announcements + admin test tools ----
const soundOn = ref(false), lastId = ref(-1), lastDup = ref(-1), voiceCfg = ref({ enabled: true, rate: 0.9 })
const users = ref([]), testUser = ref(''), toolMsg = ref('')
async function pollScans() {
  try {
    const { data } = await api.get('/admin/station/recent', { params: { after: lastId.value, after_dup: lastDup.value, ...(loc.value ? { loc: loc.value } : {}) } })
    voiceCfg.value = { enabled: data.enabled, rate: data.rate }
    if (soundOn.value && data.enabled) data.scans.forEach(s => speakParts(s.parts, data.rate))
    if (soundOn.value && data.enabled) data.dups.forEach(s => speakParts(s.parts, data.rate))
    lastId.value = data.last_id; lastDup.value = data.last_dup_id
  } catch {}
}
function toggleSound() {
  soundOn.value = !soundOn.value
  if (soundOn.value) speak('បើកសំឡេងប្រកាសហើយ', voiceCfg.value.rate)   // user click also unlocks browser autoplay
}
async function clearTest() {
  if (!testUser.value) { toolMsg.value = 'សូមជ្រើសរើសបុគ្គលិកជាមុន'; return }
  const u = users.value.find(x => x.id === testUser.value)
  if (!confirm(`CLS: លុបវត្តមាន និងកំណត់ត្រាស្កេនថ្ងៃនេះរបស់ "${u?.name}" ដើម្បីសាកល្បងស្កេនម្ដងទៀត?`)) return
  try { await api.post('/admin/test/clear', { user_id: testUser.value }); toolMsg.value = `✔ បាន CLS ${u?.name} — ស្កេនសាកល្បងបានម្ដងទៀត` }
  catch (e) { toolMsg.value = e.response?.data?.error || 'បរាជ័យ' }
  setTimeout(() => (toolMsg.value = ''), 4000)
}

async function refresh() {
  if (busy) return
  busy = true
  try {
    const { data } = await api.get('/qr/generate', { params: loc.value ? { loc: loc.value } : {} })
    interval.value = data.interval; left.value = data.expires_in; locName.value = data.location
    if (!loc.value) loc.value = data.location_id
    await QRCode.toCanvas(canvas.value, data.token, { width: 520, margin: 2, color: { dark: '#003366' } })
    err.value = ''
  } catch (e) { err.value = 'មិនអាចភ្ជាប់ម៉ាស៊ីនបម្រើបានទេ' }
  busy = false
}
function pick(e) { loc.value = Number(e.target.value); router.replace({ query: { loc: loc.value } }); lastId.value = lastDup.value = -1; refresh() }
onMounted(async () => {
  try { locations.value = (await api.get('/admin/locations')).data.filter(l => l.active) } catch {}
  try { users.value = (await api.get('/admin/users')).data.filter(u => u.active && ['employee', 'manager'].includes(u.role)) } catch {}
  await refresh()
  await pollScans()
  poll = setInterval(pollScans, 2000)
  timer = setInterval(() => { left.value--; if (left.value <= 0) refresh() }, 1000)
})
onBeforeUnmount(() => { clearInterval(timer); clearInterval(poll) })
const full = () => document.documentElement.requestFullscreen?.()
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-royal to-royal-700 flex flex-col items-center justify-center text-white p-6">
    <h1 class="text-3xl md:text-4xl text-gold-400 mb-1">វិហសចំណាលើ</h1>
    <p v-if="locName" class="text-lg opacity-90">📍 {{ locName }}</p>
    <p class="mb-5 opacity-90">សូមស្កេន QR ដើម្បីកត់ត្រាវត្តមាន</p>
    <div class="bg-white rounded-3xl p-4 shadow-2xl"><canvas ref="canvas"></canvas></div>
    <div class="w-full max-w-md mt-6">
      <div class="h-3 bg-white/20 rounded-full overflow-hidden">
        <div class="h-full bg-gold-400 transition-all duration-1000 ease-linear" :style="{ width: (left / interval) * 100 + '%' }"></div>
      </div>
      <p class="text-center mt-2">កូដថ្មីក្នុង {{ left }} វិនាទី</p>
    </div>
    <p v-if="err" class="mt-3 text-red-300">{{ err }}</p>
    <div class="mt-6 flex items-center gap-3 flex-wrap justify-center">
      <select v-if="locations.length > 1" :value="loc" @change="pick" class="bg-white/10 rounded-xl px-3 py-2 text-sm">
        <option v-for="l in locations" :key="l.id" :value="l.id" class="text-slate-800">{{ l.name }}</option>
      </select>
      <button @click="full" class="text-sm bg-white/10 px-4 py-2 rounded-xl hover:bg-white/20">ពេញអេក្រង់</button>
      <button @click="toggleSound" :class="['text-sm px-4 py-2 rounded-xl', soundOn ? 'bg-green-500/80' : 'bg-gold-400 text-slate-900 animate-pulse']">
        {{ soundOn ? '🔊 សំឡេងកំពុងបើក' : '🔇 ចុចបើកសំឡេងប្រកាស' }}</button>
    </div>
    <div class="mt-3 flex items-center gap-2 flex-wrap justify-center bg-white/10 rounded-xl px-3 py-2 text-sm">
      <span class="opacity-70">🧪 Admin test</span>
      <select v-model="testUser" class="bg-white/10 rounded-lg px-2 py-1">
        <option value="" class="text-slate-800">— ជ្រើសបុគ្គលិក —</option>
        <option v-for="u in users" :key="u.id" :value="u.id" class="text-slate-800">{{ u.name }}</option>
      </select>
      <button @click="clearTest" class="bg-red-500/80 hover:bg-red-500 px-3 py-1 rounded-lg font-medium">CLS</button>
      <span v-if="toolMsg" class="text-xs text-gold-400">{{ toolMsg }}</span>
    </div>
    <router-link to="/admin" class="mt-3 text-xs opacity-60">← ត្រឡប់ទៅផ្ទាំងគ្រប់គ្រង</router-link>
  </div>
</template>
