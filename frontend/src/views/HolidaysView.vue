<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '../api'

const year = ref(new Date().getFullYear()), list = ref([]), msg = ref(''), err = ref('')
const f = ref({ date: '', end_date: '', name: '' })
const DAYS = [[1, 'ច័ន្ទ'], [2, 'អង្គារ'], [3, 'ពុធ'], [4, 'ព្រហ'], [5, 'សុក្រ'], [6, 'សៅរ៍'], [7, 'អាទិត្យ']]
const days = ref([1, 2, 3, 4, 5])

const load = async () => (list.value = (await api.get('/holidays', { params: { year: year.value } })).data)
async function loadDays() { days.value = (await api.get('/admin/settings')).data.work_days.split(',').map(Number) }
async function saveDays() {
  msg.value = err.value = ''
  try { await api.put('/admin/settings', { work_days: days.value.slice().sort().join(',') }); msg.value = 'បានរក្សាទុកថ្ងៃធ្វើការ ✔' }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function add() {
  msg.value = err.value = ''
  try { const r = await api.post('/admin/holidays', f.value); msg.value = `បានបន្ថែម ${r.data.added} ថ្ងៃ`; f.value = { date: '', end_date: '', name: '' }; await load() }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function del(h) { await api.delete(`/admin/holidays/${h.id}`); await load() }
async function seed() {
  const r = await api.post('/admin/holidays/seed', { year: year.value }); msg.value = `បានបន្ថែមថ្ងៃបុណ្យជាតិថេរ ${r.data.added} ថ្ងៃ`; await load()
}
watch(year, load)
onMounted(() => { load(); loadDays() })
</script>

<template>
  <main class="max-w-2xl mx-auto p-4 space-y-4">
    <section class="card">
      <h2 class="text-royal mb-3">ថ្ងៃធ្វើការប្រចាំសប្ដាហ៍</h2>
      <div class="flex flex-wrap gap-2">
        <label v-for="d in DAYS" :key="d[0]" :class="['px-3 py-2 rounded-xl border-2 cursor-pointer', days.includes(d[0]) ? 'border-royal bg-royal-50 text-royal font-medium' : 'border-slate-200 text-slate-500']">
          <input type="checkbox" class="sr-only" :value="d[0]" v-model="days" />{{ d[1] }}</label>
      </div>
      <button class="btn mt-3" @click="saveDays">រក្សាទុកថ្ងៃធ្វើការ</button>
      <p class="text-xs text-slate-400 mt-2">ថ្ងៃដែលមិនធ្វើការ មិនរាប់ជាអវត្តមាន ហើយមិនរាប់ក្នុងចំនួនថ្ងៃច្បាប់។</p>
    </section>

    <section class="card">
      <div class="flex items-center gap-3 flex-wrap mb-3">
        <h2 class="text-royal">ថ្ងៃឈប់សម្រាក / ថ្ងៃបុណ្យ</h2>
        <input type="number" v-model.number="year" class="input !w-28" />
        <span class="flex-1"></span>
        <button class="btn btn-gold !py-1" @click="seed">＋ ថ្ងៃបុណ្យជាតិថេរ {{ year }}</button>
      </div>
      <p class="text-xs text-amber-700 bg-amber-50 rounded-lg p-2 mb-3">⚠️ ថ្ងៃបុណ្យតាមច័ន្ទគតិ (ចូលឆ្នាំខ្មែរ ភ្ជុំបិណ្ឌ វិសាខបូជា ព្រះរាជពិធីច្រត់ព្រះនង្គ័ល…) ប្ដូរជារៀងរាល់ឆ្នាំ — សូមបន្ថែមដោយដៃតាមប្រកាសផ្លូវការ។ សូមពិនិត្យថ្ងៃថេរតាមប្រកាសរដ្ឋាភិបាលផងដែរ។</p>
      <div class="grid grid-cols-2 gap-2 mb-2">
        <label class="text-sm">ចាប់ពីថ្ងៃ <input type="date" v-model="f.date" class="input mt-1" /></label>
        <label class="text-sm">ដល់ថ្ងៃ (បើច្រើនថ្ងៃ) <input type="date" v-model="f.end_date" class="input mt-1" /></label>
        <input v-model="f.name" class="input col-span-2" placeholder="ឈ្មោះថ្ងៃបុណ្យ (ឧ. ចូលឆ្នាំខ្មែរ)" />
      </div>
      <button class="btn w-full" @click="add">បន្ថែម</button>
      <p v-if="msg" class="text-green-700 mt-3">{{ msg }}</p><p v-if="err" class="text-red-600 mt-3">{{ err }}</p>
    </section>

    <section class="card">
      <p v-if="!list.length" class="text-slate-400 text-center py-4">មិនទាន់មានថ្ងៃឈប់សម្រាកក្នុងឆ្នាំ {{ year }}</p>
      <div v-for="h in list" :key="h.id" class="flex items-center justify-between py-2 border-b last:border-0 text-sm">
        <div><b class="text-royal">{{ h.date }}</b> · {{ h.name }}</div>
        <button class="text-red-600 hover:underline" @click="del(h)">លុប</button>
      </div>
    </section>
  </main>
</template>
