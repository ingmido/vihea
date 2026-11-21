<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '../api'

const tab = ref('edit'), users = ref([]), msg = ref(''), err = ref('')
const today = new Date().toLocaleDateString('sv-SE')
const f = ref({ user_id: '', date: today, in1: '', out1: '', in2: '', out2: '', reason: '' })
const logDate = ref(today), log = ref([]), audit = ref([])
const SLOT = [['in1', '🟢 ចូលព្រឹក'], ['out1', '🔴 ចេញព្រឹក'], ['in2', '🟢 ចូលរសៀល'], ['out2', '🔴 ចេញរសៀល']]
const ACT = { edit: '✏️ កែ', delete: '🗑 លុប', reset: '🔄 ស្កេនឡើងវិញ', test_clear: '🧪 CLS' }

async function loadRec() {
  if (!f.value.user_id || !f.value.date) return
  const { data } = await api.get('/admin/attendance', { params: { user_id: f.value.user_id, date: f.value.date } })
  Object.assign(f.value, { in1: data.in1, out1: data.out1, in2: data.in2, out2: data.out2 })
}
async function save() {
  msg.value = err.value = ''
  try { await api.put('/admin/attendance', f.value); msg.value = 'បានរក្សាទុក ហើយជូនដំណឹងបុគ្គលិក ✔'; f.value.reason = ''; loadAudit() }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function resetScan() {
  msg.value = err.value = ''
  const u = users.value.find(x => x.id === f.value.user_id)
  if (!confirm(`លុបវត្តមាន និងកំណត់ត្រាស្កេនថ្ងៃ ${f.value.date} របស់ "${u?.name}" ដើម្បីឲ្យស្កេនឡើងវិញ?`)) return
  try {
    await api.post('/admin/attendance/reset', { user_id: f.value.user_id, date: f.value.date, reason: f.value.reason })
    msg.value = 'បានលុប — បុគ្គលិកអាចស្កេនឡើងវិញបានហើយ ✔'; Object.assign(f.value, { in1: '', out1: '', in2: '', out2: '', reason: '' }); loadAudit()
  } catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
const loadLog = async () => (log.value = (await api.get('/admin/scanlog', { params: { date: logDate.value } })).data)
const loadAudit = async () => (audit.value = (await api.get('/admin/audit')).data)
watch(() => [f.value.user_id, f.value.date], loadRec)
watch(logDate, loadLog)
watch(tab, t => { if (t === 'log') loadLog(); if (t === 'audit') loadAudit() })
onMounted(async () => { users.value = (await api.get('/admin/users')).data.filter(u => u.role !== 'admin' && u.active) })
</script>

<template>
  <main class="max-w-3xl mx-auto p-4 space-y-4">
    <div class="card flex gap-2 flex-wrap">
      <button v-for="t in [['edit', '✏️ កែវត្តមានដោយដៃ'], ['log', '📍 កំណត់ត្រាស្កេន'], ['audit', '🧾 ប្រវត្តិការកែ']]" :key="t[0]" @click="tab = t[0]"
        :class="['px-4 py-2 rounded-xl', tab === t[0] ? 'bg-royal text-white' : 'bg-slate-100']">{{ t[1] }}</button>
    </div>

    <section v-if="tab === 'edit'" class="card">
      <div class="grid sm:grid-cols-2 gap-3 mb-4">
        <label class="text-sm">បុគ្គលិក
          <select v-model="f.user_id" class="input mt-1"><option value="" disabled>ជ្រើសរើស…</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }} ({{ u.employee_code }})</option></select></label>
        <label class="text-sm">ថ្ងៃ <input type="date" v-model="f.date" :max="today" class="input mt-1" /></label>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <label v-for="s in SLOT" :key="s[0]" class="text-sm">{{ s[1] }}<input type="time" v-model="f[s[0]]" class="input mt-1" /></label>
      </div>
      <p class="text-xs text-slate-400 mt-2">ទុកទទេ = មិនមានការស្កេន។ ទុកទទេទាំងបួន = លុបវត្តមានថ្ងៃនោះ។</p>
      <label class="block text-sm mt-3">មូលហេតុ (ចាំបាច់)
        <textarea v-model="f.reason" rows="2" class="input mt-1" placeholder="ឧ. ភ្លេចស្កេន / ទូរស័ព្ទខូច"></textarea></label>
      <p v-if="msg" class="text-green-700 mt-3">{{ msg }}</p><p v-if="err" class="text-red-600 mt-3">{{ err }}</p>
      <button class="btn btn-gold w-full mt-4" :disabled="!f.user_id" @click="save">រក្សាទុកការកែ</button>
      <div class="mt-4 rounded-xl border border-red-200 bg-red-50 p-3">
        <p class="text-sm text-red-700 font-medium">🔄 អនុញ្ញាតឲ្យស្កេនឡើងវិញ</p>
        <p class="text-xs text-slate-500 mt-1">ប្រើពេលបុគ្គលិកស្កេនគ្រប់ ៤ ដងហើយ តែត្រូវស្កេនថ្មី។ លុបវត្តមាន និងកំណត់ត្រាស្កេនរបស់ថ្ងៃដែលបានជ្រើស (ត្រូវបំពេញមូលហេតុខាងលើ)។</p>
        <button class="btn !py-1 mt-2 bg-red-600" :disabled="!f.user_id" @click="resetScan">លុបទិន្នន័យ · ស្កេនឡើងវិញ</button>
      </div>
    </section>

    <section v-if="tab === 'log'" class="card">
      <div class="flex items-center gap-3 mb-3"><h2 class="text-royal">កំណត់ត្រាស្កេន</h2><input type="date" v-model="logDate" class="input !w-auto" /></div>
      <p v-if="!log.length" class="text-slate-400 text-center py-6">មិនមានការស្កេនក្នុងថ្ងៃនេះ</p>
      <div v-for="s in log" :key="s.id" class="flex items-center gap-3 py-2 border-b last:border-0 text-sm">
        <a v-if="s.selfie" :href="s.selfie" target="_blank"><img :src="s.selfie" class="w-12 h-12 rounded-lg object-cover" /></a>
        <div v-else class="w-12 h-12 rounded-lg bg-slate-100 flex items-center justify-center text-slate-300">—</div>
        <div class="flex-1"><p class="font-medium">{{ s.name }} · {{ s.slot }}</p>
          <p class="text-slate-500">{{ s.time }} · 📍 {{ s.location || '-' }} · 📶 {{ s.ip || '-' }}</p></div>
      </div>
    </section>

    <section v-if="tab === 'audit'" class="card">
      <h2 class="text-royal mb-3">ប្រវត្តិការកែវត្តមាន (Audit)</h2>
      <p v-if="!audit.length" class="text-slate-400 text-center py-6">មិនទាន់មានការកែ</p>
      <div v-for="a in audit" :key="a.id" class="py-2 border-b last:border-0 text-sm">
        <p><b>{{ ACT[a.action] || a.action }}</b> · {{ a.user }} · {{ a.date }}</p>
        <p class="text-slate-600">{{ a.detail }}</p>
        <p class="text-xs text-slate-400">ដោយ {{ a.admin }} · {{ a.when }}</p>
      </div>
    </section>
  </main>
</template>
