<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '../api'

const list = ref([]), filter = ref('Pending'), msg = ref(''), busy = ref(0)
const month = ref(new Date().toLocaleDateString('sv-SE').slice(0, 7)), cal = ref(null)
const TYPE = { Sick: 'ច្បាប់ឈឺ', Personal: 'ច្បាប់ផ្ទាល់ខ្លួន', Annual: 'ច្បាប់ប្រចាំឆ្នាំ' }
const TABS = [['Pending', 'រង់ចាំ'], ['Approved', 'អនុម័តរួច'], ['Rejected', 'បដិសេធ'], ['All', 'ទាំងអស់'], ['Calendar', '📅 ប្រតិទិន']]
const ST = { Pending: ['រង់ចាំ', 'bg-amber-100 text-amber-700'], Approved: ['អនុម័ត', 'bg-green-100 text-green-700'], Rejected: ['បដិសេធ', 'bg-red-100 text-red-700'] }
const WD = ['ច', 'អ', 'ព', 'ព្រ', 'សុ', 'ស', 'អា']
const count = k => (k === 'All' ? list.value.length : list.value.filter(l => l.status === k).length)
const rows = computed(() => list.value.filter(l => filter.value === 'All' || l.status === filter.value))
const cells = computed(() => {
  if (!cal.value) return []
  const out = Array(cal.value.first_weekday - 1).fill(null)
  for (let d = 1; d <= cal.value.days_in_month; d++) {
    const iso = `${month.value}-${String(d).padStart(2, '0')}`
    out.push({ d, iso, names: cal.value.leaves[iso] || [], hol: cal.value.holidays[iso] })
  }
  return out
})

const load = async () => (list.value = (await api.get('/leaves')).data)
const loadCal = async () => (cal.value = (await api.get('/admin/leave-calendar', { params: { month: month.value } })).data)
async function decide(l, status) {
  msg.value = ''; busy.value = l.id
  try {
    await api.put(`/admin/leaves/${l.id}`, { status }); await load()
    msg.value = (status === 'Approved' ? '✅ បានអនុម័តសំណើរបស់ ' : '❌ បានបដិសេធសំណើរបស់ ') + l.user
  } catch (e) { msg.value = '⚠️ ' + (e.response?.data?.error || 'មានបញ្ហា សូមព្យាយាមម្ដងទៀត') }
  busy.value = 0
}
watch([filter, month], () => { if (filter.value === 'Calendar') loadCal() })
onMounted(load)
</script>

<template>
  <main class="max-w-3xl mx-auto p-4 space-y-4">
    <div class="card flex flex-wrap items-center gap-2">
      <h2 class="text-royal mr-2">សំណើសុំច្បាប់</h2>
      <button v-for="t in TABS" :key="t[0]" @click="filter = t[0]"
        :class="['px-3 py-1 rounded-xl text-sm', filter === t[0] ? 'bg-royal text-white' : 'bg-slate-100']">
        {{ t[1] }}<template v-if="t[0] !== 'Calendar'"> ({{ count(t[0]) }})</template></button>
      <span class="flex-1"></span>
      <button class="text-sm text-royal underline" @click="load">🔄</button>
    </div>
    <p v-if="msg" class="rounded-xl bg-white shadow p-3">{{ msg }}</p>

    <template v-if="filter !== 'Calendar'">
      <div v-for="l in rows" :key="l.id" class="card">
        <div class="flex justify-between gap-2 flex-wrap">
          <div>
            <p class="font-semibold text-royal">{{ l.user }} <span class="text-slate-400 text-sm">({{ l.code }})</span></p>
            <p>{{ TYPE[l.leave_type] }} · {{ l.start_date }} → {{ l.end_date }} <b class="text-royal">({{ l.days }} ថ្ងៃ)</b></p>
            <p class="text-sm text-slate-600 mt-1">មូលហេតុ: {{ l.reason || '-' }}</p>
            <a v-if="l.attachment" :href="l.attachment" target="_blank" class="text-sm text-royal underline">📎 មើលឯកសារភ្ជាប់</a>
            <p class="text-xs text-slate-400 mt-1">ដាក់ស្នើ: {{ l.created_at }}</p>
          </div>
          <span :class="['h-fit px-3 py-1 rounded-full text-sm', ST[l.status][1]]">{{ ST[l.status][0] }}</span>
        </div>
        <div class="flex gap-2 mt-3">
          <button v-if="l.status !== 'Approved'" :disabled="busy === l.id" class="btn bg-green-600 !py-1" @click="decide(l, 'Approved')">✔ អនុម័ត</button>
          <button v-if="l.status !== 'Rejected'" :disabled="busy === l.id" class="btn bg-red-600 !py-1" @click="decide(l, 'Rejected')">✘ បដិសេធ</button>
        </div>
      </div>
      <p v-if="!rows.length" class="text-slate-400 text-center py-8">មិនមានសំណើក្នុងប្រភេទនេះ</p>
    </template>

    <section v-else class="card">
      <div class="flex items-center gap-3 mb-3"><h2 class="text-royal">ប្រតិទិនច្បាប់ដែលបានអនុម័ត</h2><input type="month" v-model="month" class="input !w-auto" /></div>
      <div class="grid grid-cols-7 gap-1 text-center text-xs text-slate-500 mb-1"><span v-for="w in WD" :key="w">{{ w }}</span></div>
      <div class="grid grid-cols-7 gap-1">
        <template v-for="(c, i) in cells" :key="i">
          <div v-if="!c"></div>
          <div v-else :class="['min-h-[74px] rounded-lg p-1 text-left text-[11px] border', c.hol ? 'bg-slate-100' : 'bg-white', c.names.length ? 'border-blue-300' : 'border-slate-100']">
            <p class="font-semibold text-slate-600">{{ c.d }}</p>
            <p v-if="c.hol" class="text-slate-400 leading-tight">{{ c.hol }}</p>
            <p v-for="n in c.names.slice(0, 3)" :key="n.name" class="truncate rounded bg-blue-100 text-blue-700 px-1 mt-0.5">{{ n.name }}</p>
            <p v-if="c.names.length > 3" class="text-blue-600">+{{ c.names.length - 3 }}</p>
          </div>
        </template>
      </div>
    </section>
  </main>
</template>
