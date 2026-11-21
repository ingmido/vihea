<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
const router = useRouter()
const f = ref({ employee_code: '', password: '' }), err = ref(''), busy = ref(false)
async function login() {
  busy.value = true; err.value = ''
  try {
    const { data } = await api.post('/auth/login', f.value)
    localStorage.setItem('token', data.token); localStorage.setItem('user', JSON.stringify(data.user))
    router.push('/')
  } catch (e) { err.value = e.response?.data?.error || 'មានបញ្ហា' }
  busy.value = false
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-royal to-royal-700 p-4">
    <div class="card w-full max-w-sm pop">
      <h1 class="text-2xl text-royal text-center mb-1">វិហសចំណាលើ</h1>
      <p class="text-center text-slate-500 mb-5 text-sm">ប្រព័ន្ធគ្រប់គ្រងវត្តមានបុគ្គលិក</p>
      <input v-model="f.employee_code" class="input mb-3" placeholder="លេខកូដបុគ្គលិក" />
      <input v-model="f.password" type="password" class="input mb-3" placeholder="ពាក្យសម្ងាត់" @keyup.enter="login" />
      <p v-if="err" class="text-red-600 text-sm mb-2">{{ err }}</p>
      <button class="btn btn-gold w-full" :disabled="busy" @click="login">ចូលប្រើប្រាស់</button>
      <p class="text-center text-sm mt-4">មិនទាន់មានគណនី? <router-link to="/register" class="text-royal font-semibold underline">ចុះឈ្មោះ</router-link></p>
    </div>
  </div>
</template>
