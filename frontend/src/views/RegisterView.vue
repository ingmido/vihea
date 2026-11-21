<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
const router = useRouter()
const today = new Date().toLocaleDateString('sv-SE')
const f = ref({ employee_code: '', name: '', gender: '', dob: '', position: '', department: '', password: '', confirm: '', register_code: '' })
const photo = ref(null), preview = ref(''), err = ref(''), busy = ref(false)

function pick(e) {
  const file = e.target.files[0]
  photo.value = file || null
  preview.value = file ? URL.createObjectURL(file) : ''
}
async function register() {
  err.value = ''
  if (f.value.password !== f.value.confirm) { err.value = 'ពាក្យសម្ងាត់មិនដូចគ្នា'; return }
  if (!photo.value) { err.value = 'សូមបញ្ចូលរូបថត'; return }
  const fd = new FormData()
  Object.entries(f.value).forEach(([k, v]) => k !== 'confirm' && fd.append(k, v))
  fd.append('photo', photo.value)
  busy.value = true
  try {
    const { data } = await api.post('/auth/register', fd)
    localStorage.setItem('token', data.token); localStorage.setItem('user', JSON.stringify(data.user))
    router.push('/')
  } catch (e) { err.value = e.response?.data?.error || 'មានបញ្ហា' }
  busy.value = false
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-royal to-royal-700 p-4 py-8">
    <div class="card w-full max-w-md pop">
      <h1 class="text-2xl text-royal text-center mb-1">ចុះឈ្មោះបុគ្គលិក</h1>
      <p class="text-center text-slate-500 mb-4 text-sm">វិហសចំណាលើ</p>

      <label class="flex flex-col items-center mb-4 cursor-pointer">
        <div class="w-28 h-28 rounded-full border-4 border-gold overflow-hidden bg-slate-100 flex items-center justify-center text-slate-400 text-sm text-center">
          <img v-if="preview" :src="preview" class="w-full h-full object-cover" />
          <span v-else>📷<br />រូបថត</span>
        </div>
        <span class="text-sm text-royal mt-2 underline">ជ្រើសរើស / ថតរូប</span>
        <input type="file" accept="image/*" class="hidden" @change="pick" />
      </label>

      <div class="grid grid-cols-2 gap-3">
        <input v-model="f.employee_code" class="input" placeholder="លេខកូដបុគ្គលិក" />
        <input v-model="f.name" class="input" placeholder="ឈ្មោះពេញ" />
        <select v-model="f.gender" class="input">
          <option value="" disabled>ភេទ</option><option value="M">ប្រុស</option><option value="F">ស្រី</option>
        </select>
        <input v-model="f.dob" type="date" :max="today" class="input" title="ថ្ងៃខែឆ្នាំកំណើត" />
        <input v-model="f.position" class="input col-span-2" placeholder="តួនាទី (ឧ. គ្រូបង្រៀន, ក្រឡាបញ្ជី)" />
        <input v-model="f.department" class="input col-span-2" placeholder="ផ្នែក / ក្រុម (បើមាន)" />
        <input v-model="f.password" type="password" class="input" placeholder="ពាក្យសម្ងាត់ (≥ 6)" />
        <input v-model="f.confirm" type="password" class="input" placeholder="បញ្ជាក់ពាក្យសម្ងាត់" />
        <input v-model="f.register_code" class="input col-span-2" placeholder="កូដចុះឈ្មោះ (បើមាន)" />
      </div>
      
      <p v-if="err" class="text-red-600 text-sm mt-3">{{ err }}</p>
      <button class="btn btn-gold w-full mt-4" :disabled="busy" @click="register">ចុះឈ្មោះ</button>
      <p class="text-center text-sm mt-4">មានគណនីរួចហើយ? <router-link to="/login" class="text-royal font-semibold underline">ចូលប្រើ</router-link></p>
    </div>
  </div>
</template>
