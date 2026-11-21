<script setup>
import { ref, onMounted, watch } from 'vue'
import api, { user } from '../api'

const month = ref(new Date().toLocaleDateString('sv-SE').slice(0, 7)), dept = ref(''), depts = ref([]), d = ref(null)
const isAdmin = user()?.role === 'admin'
const KM = ['មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']
const monthName = m => `ខែ${KM[+m.slice(5) - 1]} ឆ្នាំ ${m.slice(0, 4)}`
const load = async () => (d.value = (await api.get('/admin/report/monthly', { params: { month: month.value, dept: dept.value } })).data)
async function excel() {
  const r = await api.get('/admin/report/monthly/excel', { params: { month: month.value, dept: dept.value }, responseType: 'blob' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = `attendance_monthly_${month.value}.xlsx`; a.click()
  URL.revokeObjectURL(a.href)
}
watch([month, dept], load)
onMounted(async () => { depts.value = (await api.get('/admin/departments')).data; load() })
</script>

<template>
  <main class="max-w-5xl mx-auto p-4 print:p-0 print:max-w-none">
    <div class="card flex flex-wrap items-center gap-3 mb-4 print:hidden">
      <h2 class="text-royal">របាយការណ៍វត្តមានប្រចាំខែ</h2>
      <input type="month" v-model="month" class="input !w-auto" />
      <select v-if="isAdmin" v-model="dept" class="input !w-auto"><option value="">គ្រប់ផ្នែក</option><option v-for="x in depts" :key="x">{{ x }}</option></select>
      <span class="flex-1"></span>
      <button class="btn" @click="excel">⬇ Excel</button>
      <button class="btn btn-gold" @click="$el.ownerDocument.defaultView.print()">🖨 បោះពុម្ព / រក្សាទុកជា PDF</button>
    </div>
    <p class="text-xs text-slate-400 mb-3 print:hidden">ចុចប៊ូតុងខាងលើ ហើយជ្រើស "Save as PDF" ក្នុងបង្អួចបោះពុម្ព ដើម្បីបានឯកសារ PDF ភាសាខ្មែរ។</p>

    <article v-if="d" class="sheet bg-white rounded-2xl shadow p-8 print:shadow-none print:rounded-none print:p-0">
      <header class="text-center mb-5">
        <p class="font-moul text-royal text-lg">{{ d.org }}</p>
        <h1 class="mt-2 text-xl font-bold !font-khmer">របាយការណ៍វត្តមានបុគ្គលិក {{ monthName(d.month) }}</h1>
        <p class="text-sm text-slate-500">{{ d.dept ? 'ផ្នែក៖ ' + d.dept + ' · ' : '' }}ចំនួនថ្ងៃធ្វើការក្នុងខែ៖ {{ d.workdays }} ថ្ងៃ</p>
      </header>
      <table class="w-full text-sm border-collapse">
        <thead><tr class="bg-slate-100 print:bg-slate-100">
          <th v-for="h in ['ល.រ', 'លេខកូដ', 'ឈ្មោះ', 'តួនាទី', 'មកធ្វើការ', 'ក្នុងនោះយឺត', 'អវត្តមាន', 'ច្បាប់', 'ម៉ោងសរុប']" :key="h" class="border border-slate-300 px-2 py-2">{{ h }}</th></tr></thead>
        <tbody>
          <tr v-for="(r, i) in d.rows" :key="r.code" class="text-center">
            <td class="border border-slate-300 px-2 py-1.5">{{ i + 1 }}</td><td class="border border-slate-300 px-2">{{ r.code }}</td>
            <td class="border border-slate-300 px-2 text-left">{{ r.name }}</td><td class="border border-slate-300 px-2 text-left">{{ r.position || '-' }}</td>
            <td class="border border-slate-300 px-2">{{ r.came }}</td><td class="border border-slate-300 px-2">{{ r.late }}</td>
            <td class="border border-slate-300 px-2">{{ r.absent }}</td><td class="border border-slate-300 px-2">{{ r.leave }}</td>
            <td class="border border-slate-300 px-2">{{ r.hours }}</td></tr>
          <tr class="font-bold text-center bg-slate-50"><td colspan="4" class="border border-slate-300 px-2 py-2">សរុប</td>
            <td class="border border-slate-300">{{ d.totals.came }}</td><td class="border border-slate-300">{{ d.totals.late }}</td>
            <td class="border border-slate-300">{{ d.totals.absent }}</td><td class="border border-slate-300">{{ d.totals.leave }}</td><td class="border border-slate-300">{{ d.totals.hours }}</td></tr>
        </tbody>
      </table>
      <p v-if="!d.rows.length" class="text-center text-slate-400 py-6">មិនមានទិន្នន័យ</p>
      <footer class="grid grid-cols-2 gap-10 mt-12 text-center text-sm">
        <div><p>អ្នកធ្វើរបាយការណ៍</p><p class="mt-16">………………………………</p></div>
        <div><p>ថ្ងៃទី……… ខែ……… ឆ្នាំ………</p><p>ប្រធាន / នាយក</p><p class="mt-12">………………………………</p></div>
      </footer>
    </article>
  </main>
</template>

<style>
@media print {
  @page { size: A4 landscape; margin: 12mm; }
  body { background: #fff !important; }
  .sheet { color: #000; }
  tr { break-inside: avoid; }
}
</style>
