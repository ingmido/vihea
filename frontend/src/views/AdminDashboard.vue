<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import api from '../api'
import AttendanceChart from '../components/AttendanceChart.vue'
import InsightsPanel from '../components/InsightsPanel.vue'

const tab = ref('daily'), day = ref(new Date().toLocaleDateString('sv-SE'))
const d = ref({ summary: {}, rows: [], chart: [], high_absence: [], threshold: 3, employees: 0, pending: 0, off_day: null, role: '' })
const leaves = ref([]), msg = ref('')
const TABS = [['daily', 'ប្រចាំថ្ងៃ'], ['weekly', 'ប្រចាំសប្ដាហ៍'], ['monthly', 'ប្រចាំខែ']]
const ST = { present: ['មកធ្វើការ', 'text-green-700 bg-green-100'], late: ['មកធ្វើការ (យឺត)', 'text-amber-700 bg-amber-100'],
  absent: ['អវត្តមាន', 'text-red-700 bg-red-100'], leave: ['ច្បាប់', 'text-blue-700 bg-blue-100'] }
const TYPE = { Sick: 'ឈឺ', Personal: 'ផ្ទាល់ខ្លួន', Annual: 'ប្រចាំឆ្នាំ' }
const params = computed(() => ({ period: tab.value, date: day.value }))
const count = k => k === 'present'
  ? (d.value.summary.came ?? ((d.value.summary.present || 0) + (d.value.summary.late || 0)))
  : (d.value.summary[k] || 0)

async function load() {
  d.value = (await api.get('/admin/dashboard', { params: params.value })).data
  leaves.value = (await api.get('/leaves')).data
}
const leaveMsg = ref('')
async function decide(l, status) {
  leaveMsg.value = ''
  try {
    await api.put(`/admin/leaves/${l.id}`, { status }); await load()
    leaveMsg.value = (status === 'Approved' ? '✅ បានអនុម័ត ' : '❌ បានបដិសេធ ') + l.user
  } catch (e) { leaveMsg.value = '⚠️ ' + (e.response?.data?.error || 'មានបញ្ហា សូមព្យាយាមម្ដងទៀត') }
}
async function excel() {
  const r = await api.get('/admin/export/excel', { params: params.value, responseType: 'blob' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(r.data)
  a.download = `attendance_${tab.value}_${day.value}.xlsx`; a.click()
}
async function gsheet() {
  msg.value = 'កំពុងផ្ញើ...'
  try { const r = await api.post('/admin/export/gsheet', params.value); msg.value = r.data.rows
      ? `បាន Sync ${r.data.rows} ជួរ ទៅ tab "Attendance" ✔`
      : 'Sync ជោគជ័យ ប៉ុន្តែគ្មានទិន្នន័យក្នុងចន្លោះនេះ (សាកល្បងជ្រើស "ប្រចាំខែ" ហើយពិនិត្យថាមានបុគ្គលិក)'
    window.open(r.data.url) }
  catch (e) { msg.value = e.response?.data?.error || 'បរាជ័យ' }
}
watch([tab, day], load)
onMounted(load)
</script>

<template>
  <main class="max-w-6xl mx-auto p-4 space-y-4">
    <div v-if="d.high_absence.length" class="rounded-2xl border-2 border-gold bg-amber-50 p-4">
      <h3 class="font-bold text-gold mb-2">⚠️ បុគ្គលិកឈប់ច្រើន (High Absence Alert) — ≥ {{ d.threshold }} ដង/ខែ</h3>
      <div class="flex flex-wrap gap-2">
        <span v-for="h in d.high_absence" :key="h.code" class="bg-white rounded-xl px-3 py-1 shadow text-sm">
          {{ h.name }} · អវត្តមាន {{ h.absent }} · យឺត {{ h.late }}</span>
      </div>
    </div>

    <div v-if="d.off_day" class="rounded-2xl bg-blue-50 border border-blue-200 text-blue-700 px-4 py-3">🗓 ថ្ងៃនេះជាថ្ងៃឈប់សម្រាក៖ <b>{{ d.off_day }}</b> — មិនរាប់ជាអវត្តមានទេ</div>
    <InsightsPanel />
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div class="card"><p class="text-slate-500 text-sm">បុគ្គលិកសរុប</p><p class="text-3xl text-royal font-bold">{{ d.employees }}</p></div>
      <div v-for="(v, k) in ST" :key="k" class="card"><p class="text-slate-500 text-sm">{{ k === 'late' ? 'ក្នុងនោះយឺត' : v[0] }}</p>
        <p class="text-3xl font-bold" :class="v[1].split(' ')[0]">{{ count(k) }}</p></div>
    </div>

    <div class="card flex flex-wrap items-center gap-3">
      <div class="flex bg-slate-100 rounded-xl p-1">
        <button v-for="t in TABS" :key="t[0]" @click="tab = t[0]"
          :class="['px-4 py-1 rounded-lg', tab === t[0] ? 'bg-royal text-white' : '']">{{ t[1] }}</button>
      </div>
      <input type="date" v-model="day" class="input !w-auto" />
      <span class="flex-1"></span>
      <button class="btn" @click="excel">⬇ Excel</button>
      <button v-if="d.role === 'admin'" class="btn btn-gold" @click="gsheet">⇪ Google Sheets</button>
      <router-link v-if="d.role === 'admin'" to="/station" class="btn bg-slate-700">QR ស្ថានី</router-link>
    </div>
    <p v-if="msg" class="text-royal">{{ msg }}
      <router-link v-if="msg.includes('Google')" to="/settings" class="underline font-semibold ml-2">→ ទៅទំព័រកំណត់</router-link></p>

    <div class="card">
      <h2 class="text-royal mb-3">ក្រាហ្វវត្តមាន</h2>
      <AttendanceChart :data="d.chart" />
    </div>

    <div class="grid lg:grid-cols-3 gap-4">
      <div class="card lg:col-span-2 overflow-x-auto">
        <h2 class="text-royal mb-3">តារាងវត្តមាន</h2>
        <table class="w-full text-sm">
          <thead><tr class="text-left text-slate-500 border-b"><th class="py-2">ថ្ងៃ</th><th>ឈ្មោះ</th><th>ចូលព្រឹក</th><th>ចេញព្រឹក</th><th>ចូលរសៀល</th><th>ចេញរសៀល</th><th>ស្ថានភាព</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in d.rows" :key="i" class="border-b last:border-0">
              <td class="py-2">{{ r.date }}</td><td>{{ r.name }}</td><td>{{ r.in1 || '-' }}</td><td>{{ r.out1 || '-' }}</td><td>{{ r.in2 || '-' }}</td><td>{{ r.out2 || '-' }}</td>
              <td><span :class="['px-2 py-0.5 rounded-full', ST[r.status][1]]">{{ ST[r.status][0] }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="!d.rows.length" class="text-slate-400 py-4 text-center">មិនទាន់មានទិន្នន័យ</p>
      </div>

      <div class="space-y-4">
        <div class="card">
          <h2 class="text-royal mb-3">សំណើសុំច្បាប់ <span v-if="d.pending" class="text-gold text-sm">({{ d.pending }} រង់ចាំ)</span></h2>
          <p v-if="leaveMsg" class="text-sm rounded-xl bg-slate-100 p-2 mb-2">{{ leaveMsg }}</p>
          <div v-for="l in leaves.slice(0, 8)" :key="l.id" class="border-b last:border-0 py-2 text-sm">
            <p class="font-medium">{{ l.user }} · {{ TYPE[l.leave_type] }}</p>
            <p class="text-slate-500">{{ l.start_date }} → {{ l.end_date }}</p>
            <p>{{ l.reason }} <a v-if="l.attachment" :href="l.attachment" target="_blank" class="text-royal underline">📎</a></p>
            <div v-if="l.status === 'Pending'" class="flex gap-2 mt-1">
              <button class="btn !py-1 bg-green-600" @click="decide(l, 'Approved')">អនុម័ត</button>
              <button class="btn !py-1 bg-red-600" @click="decide(l, 'Rejected')">បដិសេធ</button>
            </div>
            <span v-else class="text-xs">{{ l.status === 'Approved' ? '✅ អនុម័ត' : '❌ បដិសេធ' }}</span>
          </div>
          <router-link to="/leaves-admin" class="block text-center text-royal underline text-sm mt-3">មើលសំណើទាំងអស់ →</router-link>
        </div>
        <router-link v-if="d.role === 'admin'" to="/employees" class="card block text-center text-royal font-semibold hover:shadow-lg">👥 គ្រប់គ្រងបុគ្គលិក →</router-link>
      </div>
    </div>
  </main>
</template>
