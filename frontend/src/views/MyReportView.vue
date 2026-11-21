<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'

const tab = ref('monthly'), day = ref(new Date().toLocaleDateString('sv-SE'))
const d = ref({ summary: {}, rows: [], range: [] })
const TABS = [['daily', 'ប្រចាំថ្ងៃ'], ['weekly', 'ប្រចាំសប្ដាហ៍'], ['monthly', 'ប្រចាំខែ']]
const ST = { present: ['មកធ្វើការ', 'text-green-700 bg-green-100'], late: ['មកធ្វើការ (យឺត)', 'text-amber-700 bg-amber-100'],
  absent: ['អវត្តមាន', 'text-red-700 bg-red-100'], leave: ['ច្បាប់', 'text-blue-700 bg-blue-100'] }

const count = k => k === 'present'
  ? (d.value.summary.came ?? ((d.value.summary.present || 0) + (d.value.summary.late || 0)))
  : (d.value.summary[k] || 0)
const load = async () => (d.value = (await api.get('/my/report', { params: { period: tab.value, date: day.value } })).data)
const mins = t => +t.slice(0, 2) * 60 + +t.slice(3)
function hours(r) {
  let m = 0
  if (r.in1 && r.out1) m += mins(r.out1) - mins(r.in1)
  if (r.in2 && r.out2) m += mins(r.out2) - mins(r.in2)
  return m > 0 ? `${Math.floor(m / 60)}ម៉ោង ${m % 60}នាទី` : '-'
}
watch([tab, day], load)
onMounted(load)
</script>

<template>
  <main class="max-w-3xl mx-auto p-4 space-y-4">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div v-for="(v, k) in ST" :key="k" class="card text-center"><p class="text-slate-500 text-sm">{{ k === 'late' ? 'ក្នុងនោះយឺត' : v[0] }}</p>
        <p class="text-3xl font-bold" :class="v[1].split(' ')[0]">{{ count(k) }}</p></div>
    </div>

    <div class="card flex flex-wrap items-center gap-3">
      <div class="flex bg-slate-100 rounded-xl p-1">
        <button v-for="t in TABS" :key="t[0]" @click="tab = t[0]"
          :class="['px-3 py-1 rounded-lg', tab === t[0] ? 'bg-royal text-white' : '']">{{ t[1] }}</button>
      </div>
      <input type="date" v-model="day" class="input !w-auto" />
    </div>

    <div class="card overflow-x-auto">
      <h2 class="text-royal mb-1">របាយការណ៍វត្តមានរបស់ខ្ញុំ</h2>
      <p class="text-xs text-slate-400 mb-3">{{ d.range[0] }} → {{ d.range[1] }}</p>
      <table class="w-full text-sm">
        <thead><tr class="text-left text-slate-500 border-b"><th class="py-2">ថ្ងៃ</th><th>ចូលព្រឹក</th><th>ចេញព្រឹក</th><th>ចូលរសៀល</th><th>ចេញរសៀល</th><th>រយៈពេល</th><th>ស្ថានភាព</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in d.rows" :key="i" class="border-b last:border-0">
            <td class="py-2">{{ r.date }}</td><td>{{ r.in1 || '-' }}</td><td>{{ r.out1 || '-' }}</td><td>{{ r.in2 || '-' }}</td><td>{{ r.out2 || '-' }}</td><td>{{ hours(r) }}</td>
            <td><span :class="['px-2 py-0.5 rounded-full', ST[r.status][1]]">{{ ST[r.status][0] }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!d.rows.length" class="text-slate-400 text-center py-6">មិនទាន់មានទិន្នន័យ</p>
    </div>
  </main>
</template>
