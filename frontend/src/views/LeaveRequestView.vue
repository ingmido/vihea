<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import api from '../api'

const today = new Date().toLocaleDateString('sv-SE')
const f = ref({ leave_type: 'Sick', start_date: today, end_date: today, reason: '' })
const file = ref(null), list = ref([]), bal = ref({}), msg = ref(''), err = ref('')
const TYPE = { Sick: 'ច្បាប់ឈឺ', Personal: 'ច្បាប់ផ្ទាល់ខ្លួន', Annual: 'ច្បាប់ប្រចាំឆ្នាំ' }
const ST = { Pending: ['រង់ចាំ', 'bg-amber-100 text-amber-700'], Approved: ['អនុម័ត', 'bg-green-100 text-green-700'], Rejected: ['បដិសេធ', 'bg-red-100 text-red-700'] }

const load = async () => {
  list.value = (await api.get('/leaves', { params: { mine: 1 } })).data
  bal.value = (await api.get('/leaves/balance')).data.balance
}
async function submit() {
  msg.value = err.value = ''
  const fd = new FormData()
  Object.entries(f.value).forEach(([k, v]) => fd.append(k, v))
  if (file.value) fd.append('attachment', file.value)
  try {
    await api.post('/leaves', fd); msg.value = 'បានផ្ញើសំណើរួចរាល់'; f.value.reason = ''; await load()
  } catch (e) { err.value = e.response?.data?.error || 'មានបញ្ហា' }
}
let poll
onMounted(() => { load(); poll = setInterval(load, 15000) })  // pick up admin decisions automatically
onBeforeUnmount(() => clearInterval(poll))
</script>

<template>
  <main class="max-w-2xl mx-auto p-4 space-y-4">
    <section class="grid grid-cols-3 gap-3">
      <div v-for="(t, k) in TYPE" :key="k" class="card !p-3 text-center">
        <p class="text-xs text-slate-500">{{ t }}</p>
        <template v-if="bal[k]">
          <p class="text-2xl font-bold text-royal">{{ bal[k].quota ? bal[k].left : '∞' }}</p>
          <p class="text-[11px] text-slate-400">{{ bal[k].quota ? `នៅសល់ / ${bal[k].quota} ថ្ងៃ` : 'គ្មានកំណត់' }}</p>
          <p v-if="bal[k].pending" class="text-[11px] text-amber-600">រង់ចាំ {{ bal[k].pending }} ថ្ងៃ</p>
        </template>
      </div>
    </section>

    <section class="card">
      <h2 class="text-royal mb-4">មុខងារសុំច្បាប់</h2>
      <div class="grid sm:grid-cols-2 gap-3">
        <label class="sm:col-span-2">ប្រភេទច្បាប់
          <select v-model="f.leave_type" class="input mt-1"><option v-for="(t, k) in TYPE" :key="k" :value="k">{{ t }}</option></select>
        </label>
        <label>ចាប់ពីថ្ងៃ <input type="date" v-model="f.start_date" class="input mt-1" /></label>
        <label>ដល់ថ្ងៃ <input type="date" v-model="f.end_date" class="input mt-1" /></label>
        <label class="sm:col-span-2">មូលហេតុ <textarea v-model="f.reason" rows="3" class="input mt-1"></textarea></label>
        <label class="sm:col-span-2">ឯកសារភ្ជាប់ (មិនចាំបាច់)
          <input type="file" @change="file = $event.target.files[0]" class="input mt-1" /></label>
      </div>
      <p class="text-xs text-slate-400 mt-2">ចំនួនថ្ងៃរាប់តែថ្ងៃធ្វើការ (មិនរាប់ថ្ងៃឈប់សម្រាក និងថ្ងៃបុណ្យ)។</p>
      <p v-if="msg" class="text-green-700 mt-3">{{ msg }}</p>
      <p v-if="err" class="text-red-600 mt-3">{{ err }}</p>
      <button class="btn btn-gold mt-4 w-full" @click="submit">ផ្ញើសំណើ</button>
    </section>

    <section class="card">
      <div class="flex items-center justify-between mb-3"><h2 class="text-royal">ប្រវត្តិសុំច្បាប់</h2><button class="text-sm text-royal underline" @click="load">🔄 ផ្ទុកឡើងវិញ</button></div>
      <p v-if="!list.length" class="text-slate-400">មិនទាន់មានទិន្នន័យ</p>
      <div v-for="l in list" :key="l.id" class="border-b last:border-0 py-3 flex justify-between gap-2">
        <div>
          <p class="font-medium">{{ TYPE[l.leave_type] }} <span class="text-xs text-slate-400">({{ l.days }} ថ្ងៃ)</span></p>
          <p class="text-sm text-slate-500">{{ l.start_date }} → {{ l.end_date }}</p>
          <p class="text-sm">{{ l.reason }}</p>
        </div>
        <span :class="['h-fit px-3 py-1 rounded-full text-sm', ST[l.status][1]]">{{ ST[l.status][0] }}</span>
      </div>
    </section>
  </main>
</template>
