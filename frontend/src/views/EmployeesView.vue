<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const list = ref([]), q = ref(''), msg = ref(''), err = ref('')
const modal = ref(false), editId = ref(null), photo = ref(null), preview = ref('')
const today = new Date().toLocaleDateString('sv-SE')
const blank = () => ({ employee_code: '', name: '', gender: '', dob: '', position: '', department: '', role: 'employee', password: '', active: true, reset_device: false })
const f = ref(blank()), editing = ref(null)
const imp = ref(false), impResult = ref(null), impErr = ref(''), impBusy = ref(false)

const rows = computed(() => list.value.filter(u => u.role !== 'admin' &&
  (u.name + u.employee_code + (u.position || '') + (u.department || '')).toLowerCase().includes(q.value.toLowerCase())))
const depts = computed(() => [...new Set(list.value.map(u => u.department).filter(Boolean))])
const load = async () => (list.value = (await api.get('/admin/users')).data)

function openNew() { editId.value = null; editing.value = null; f.value = blank(); photo.value = null; preview.value = ''; err.value = ''; modal.value = true }
function openEdit(u) {
  editId.value = u.id; editing.value = u; err.value = ''
  f.value = { employee_code: u.employee_code, name: u.name, gender: u.gender || '', dob: u.dob || '', position: u.position || '',
    department: u.department || '', role: u.role, password: '', active: u.active, reset_device: false }
  photo.value = null; preview.value = u.photo || ''; modal.value = true
}
function pick(e) { photo.value = e.target.files[0] || null; if (photo.value) preview.value = URL.createObjectURL(photo.value) }
async function save() {
  err.value = ''
  const fd = new FormData()
  Object.entries(f.value).forEach(([k, v]) => fd.append(k, typeof v === 'boolean' ? (v ? '1' : '0') : v ?? ''))
  if (photo.value) fd.append('photo', photo.value)
  try {
    if (editId.value) await api.put(`/admin/users/${editId.value}`, fd); else await api.post('/admin/users', fd)
    modal.value = false; msg.value = 'បានរក្សាទុក ✔'; await load()
  } catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function toggle(u) { const fd = new FormData(); fd.append('active', u.active ? '0' : '1'); await api.put(`/admin/users/${u.id}`, fd); await load() }
async function remove(u) {
  if (!confirm(`លុប "${u.name}" ជាអចិន្ត្រៃយ៍?\n\nប្រវត្តិវត្តមាន សំណើសុំច្បាប់ និងកំណត់ត្រាស្កេនរបស់គាត់នឹងត្រូវលុបទាំងអស់។\n(បើគ្រាន់តែឈប់ធ្វើការ សូមប្រើ "ផ្អាក" ជំនួស)`)) return
  try { await api.delete(`/admin/users/${u.id}`); msg.value = 'បានលុបរួចរាល់'; await load() }
  catch (e) { msg.value = e.response?.data?.error || 'បរាជ័យ' }
}
// ---- Excel import ----
async function template() {
  const r = await api.get('/admin/users/import-template', { responseType: 'blob' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = 'employees_template.xlsx'; a.click()
}
async function doImport(e) {
  const file = e.target.files[0]; if (!file) return
  impErr.value = ''; impResult.value = null; impBusy.value = true
  const fd = new FormData(); fd.append('file', file)
  try { impResult.value = (await api.post('/admin/users/import', fd)).data; await load() }
  catch (er) { impErr.value = er.response?.data?.error || 'នាំចូលមិនបាន' }
  impBusy.value = false; e.target.value = ''
}
function downloadCreds() {
  const csv = '\ufeffcode,name,password\n' + impResult.value.created.map(c => `${c.code},"${c.name}",${c.password}`).join('\n')
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'new_employees_passwords.csv'; a.click()
}
const sex = g => (g === 'M' ? 'ប្រុស' : g === 'F' ? 'ស្រី' : '-')
onMounted(load)
</script>

<template>
  <main class="max-w-6xl mx-auto p-4 space-y-4">
    <div class="card flex flex-wrap items-center gap-3">
      <h2 class="text-royal">គ្រប់គ្រងបុគ្គលិក ({{ rows.length }})</h2>
      <input v-model="q" class="input !w-64" placeholder="🔍 ស្វែងរក ឈ្មោះ / លេខកូដ / តួនាទី / ផ្នែក" />
      <span class="flex-1"></span>
      <button class="btn bg-slate-600" @click="imp = true; impResult = null; impErr = ''">⬆ នាំចូល Excel</button>
      <button class="btn btn-gold" @click="openNew">＋ បន្ថែមបុគ្គលិក</button>
    </div>
    <p v-if="msg" class="text-green-700">{{ msg }}</p>

    <div class="card overflow-x-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-slate-500 border-b">
          <th class="py-2">រូប</th><th>លេខកូដ</th><th>ឈ្មោះ</th><th>ភេទ</th><th>ផ្នែក</th><th>តួនាទី</th><th>ស្ថានភាព</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in rows" :key="u.id" class="border-b last:border-0" :class="{ 'opacity-50': !u.active }">
            <td class="py-2"><img v-if="u.photo" :src="u.photo" class="w-10 h-10 rounded-full object-cover" /><div v-else class="w-10 h-10 rounded-full bg-slate-200"></div></td>
            <td>{{ u.employee_code }}</td><td class="font-medium">{{ u.name }}</td><td>{{ sex(u.gender) }}</td>
            <td>{{ u.department || '-' }}</td><td>{{ u.position || '-' }}</td>
            <td class="space-x-1 whitespace-nowrap">
              <span :class="['px-2 py-0.5 rounded-full', u.active ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-600']">{{ u.active ? 'សកម្ម' : 'ផ្អាក' }}</span>
              <span v-if="u.role === 'manager'" class="px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">ប្រធានផ្នែក</span>
              <span v-if="u.device_bound" title="ភ្ជាប់ទូរស័ព្ទមួយ">📱</span>
              <span v-if="u.telegram_linked" title="ភ្ជាប់ Telegram">✈️</span></td>
            <td class="whitespace-nowrap space-x-1 text-right">
              <button class="btn !py-1 !px-3" @click="openEdit(u)">កែប្រែ</button>
              <button class="btn !py-1 !px-3 bg-slate-500" @click="toggle(u)">{{ u.active ? 'ផ្អាក' : 'បើកវិញ' }}</button>
              <button class="btn !py-1 !px-3 bg-red-600" @click="remove(u)">លុប</button></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="text-slate-400 text-center py-6">មិនទាន់មានបុគ្គលិក</p>
    </div>

    <!-- add / edit -->
    <div v-if="modal" class="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div class="bg-white rounded-3xl p-6 w-full max-w-md pop my-8">
        <h3 class="text-royal mb-4">{{ editId ? 'កែប្រែបុគ្គលិក' : 'បន្ថែមបុគ្គលិក' }}</h3>
        <label class="flex flex-col items-center mb-4 cursor-pointer">
          <div class="w-24 h-24 rounded-full border-4 border-gold overflow-hidden bg-slate-100 flex items-center justify-center text-slate-400"><img v-if="preview" :src="preview" class="w-full h-full object-cover" /><span v-else>📷</span></div>
          <span class="text-sm text-royal underline mt-1">ប្ដូររូបថត</span><input type="file" accept="image/*" class="hidden" @change="pick" /></label>
        <div class="grid grid-cols-2 gap-3">
          <input v-model="f.employee_code" class="input" placeholder="លេខកូដ" /><input v-model="f.name" class="input" placeholder="ឈ្មោះពេញ" />
          <select v-model="f.gender" class="input"><option value="">ភេទ</option><option value="M">ប្រុស</option><option value="F">ស្រី</option></select>
          <input v-model="f.dob" type="date" :max="today" class="input" />
          <input v-model="f.position" class="input col-span-2" placeholder="តួនាទី" />
          <input v-model="f.department" list="deptlist" class="input" placeholder="ផ្នែក / ក្រុម" /><datalist id="deptlist"><option v-for="d in depts" :key="d" :value="d" /></datalist>
          <select v-model="f.role" class="input"><option value="employee">បុគ្គលិក</option><option value="manager">ប្រធានផ្នែក (អនុម័តច្បាប់ផ្នែកខ្លួន)</option></select>
          <input v-model="f.password" type="password" class="input col-span-2" :placeholder="editId ? 'ពាក្យសម្ងាត់ថ្មី (ទុកទទេបើមិនប្ដូរ)' : 'ពាក្យសម្ងាត់ (≥ 6 តួអក្សរ)'" />
          <label v-if="editId" class="col-span-2 flex items-center gap-2"><input type="checkbox" v-model="f.active" class="w-5 h-5" /> គណនីសកម្ម</label>
          <label v-if="editing?.device_bound" class="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" v-model="f.reset_device" class="w-5 h-5" /> 📱 ដោះការភ្ជាប់ទូរស័ព្ទចាស់ (អនុញ្ញាតប្ដូរទូរស័ព្ទ)</label>
        </div>
        <p v-if="err" class="text-red-600 text-sm mt-3">{{ err }}</p>
        <div class="flex gap-2 mt-5"><button class="btn bg-slate-500 flex-1" @click="modal = false">បោះបង់</button><button class="btn btn-gold flex-1" @click="save">រក្សាទុក</button></div>
      </div>
    </div>

    <!-- import -->
    <div v-if="imp" class="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div class="bg-white rounded-3xl p-6 w-full max-w-lg pop my-8">
        <h3 class="text-royal mb-2">នាំចូលបុគ្គលិកពី Excel</h3>
        <p class="text-sm text-slate-500 mb-3">ជួរ៖ employee_code, name, gender (ប្រុស/ស្រី), dob (YYYY-MM-DD), position, department, password។ ទុក password ទទេ ប្រព័ន្ធបង្កើតឲ្យដោយស្វ័យប្រវត្តិ។</p>
        <button class="text-royal underline text-sm" @click="template">⬇ ទាញយកគំរូ Excel</button>
        <input type="file" accept=".xlsx" class="input mt-3" :disabled="impBusy" @change="doImport" />
        <p v-if="impErr" class="text-red-600 text-sm mt-2">{{ impErr }}</p>
        <div v-if="impResult" class="mt-4 text-sm">
          <p class="text-green-700 font-medium">✔ បានបន្ថែម {{ impResult.created.length }} នាក់</p>
          <button v-if="impResult.created.length" class="btn !py-1 mt-1" @click="downloadCreds">⬇ ទាញយកបញ្ជីពាក្យសម្ងាត់ (CSV)</button>
          <div v-if="impResult.skipped.length" class="mt-3"><p class="text-amber-700 font-medium">រំលង {{ impResult.skipped.length }} ជួរ</p>
            <p v-for="s in impResult.skipped" :key="s.row" class="text-slate-600">ជួរ {{ s.row }} {{ s.code }} — {{ s.reason }}</p></div>
        </div>
        <button class="btn bg-slate-500 w-full mt-5" @click="imp = false">បិទ</button>
      </div>
    </div>
  </main>
</template>
