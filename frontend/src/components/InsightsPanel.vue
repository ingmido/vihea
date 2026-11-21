<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'

const d = ref(null)
const trend = computed(() => (d.value?.trend || []))
const W = 360, H = 120, PAD = 22
const pts = computed(() => trend.value.map((t, i) => ({ ...t, x: PAD + (i * (W - 2 * PAD)) / Math.max(trend.value.length - 1, 1),
  y: t.rate === null ? null : H - 24 - ((H - 44) * t.rate) / 100 })))
const bars = computed(() => pts.value.filter(p => p.y !== null))
onMounted(async () => { try { d.value = (await api.get('/admin/insights')).data } catch {} })
</script>

<template>
  <section v-if="d" class="grid lg:grid-cols-3 gap-4">
    <div class="card">
      <h2 class="text-royal mb-3">🏢 កំពុងនៅការិយាល័យ ({{ d.in_office.length }})</h2>
      <p v-if="!d.in_office.length" class="text-slate-400 text-sm">គ្មាននរណានៅការិយាល័យឥឡូវនេះទេ</p>
      <div v-for="p in d.in_office" :key="p.name" class="flex items-center gap-2 py-1.5 text-sm">
        <img v-if="p.photo" :src="p.photo" class="w-8 h-8 rounded-full object-cover" /><div v-else class="w-8 h-8 rounded-full bg-slate-200"></div>
        <div class="flex-1 min-w-0"><p class="truncate font-medium">{{ p.name }}</p><p class="text-xs text-slate-400">{{ p.position || '' }}</p></div>
        <span class="text-xs text-green-700 bg-green-100 rounded-full px-2 py-0.5">ចូល {{ p.since }}</span>
      </div>
    </div>

    <div class="card">
      <h2 class="text-royal mb-3">🏅 ចំណាត់ថ្នាក់ខែនេះ</h2>
      <p class="text-xs text-slate-500 mb-1">មកទាន់ម៉ោងច្រើនជាងគេ</p>
      <p v-if="!d.punctual.length" class="text-slate-400 text-sm mb-2">—</p>
      <div v-for="(p, i) in d.punctual" :key="p.name" class="flex justify-between text-sm py-0.5"><span>{{ i + 1 }}. {{ p.name }}</span><b class="text-green-700">{{ p.count }} ថ្ងៃ</b></div>
      <p class="text-xs text-slate-500 mt-3 mb-1">មកយឺតច្រើនជាងគេ</p>
      <p v-if="!d.late.length" class="text-slate-400 text-sm">គ្មាន 🎉</p>
      <div v-for="(p, i) in d.late" :key="p.name" class="flex justify-between text-sm py-0.5"><span>{{ i + 1 }}. {{ p.name }}</span><b class="text-amber-600">{{ p.count }} ដង</b></div>
    </div>

    <div class="card">
      <h2 class="text-royal mb-1">📈 អត្រាមកធ្វើការ ៦ ខែ</h2>
      <p class="text-xs text-slate-400 mb-2">មកធ្វើការ ÷ (មកធ្វើការ + អវត្តមាន) មិនរាប់ច្បាប់</p>
      <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" role="img" aria-label="និន្នាការអត្រាមកធ្វើការ">
        <line :x1="PAD" :x2="W - PAD" :y1="H - 24" :y2="H - 24" stroke="#cbd5e1" />
        <polyline v-if="bars.length > 1" :points="bars.map(p => `${p.x},${p.y}`).join(' ')" fill="none" stroke="#1e3a8a" stroke-width="2.5" stroke-linejoin="round" />
        <g v-for="p in pts" :key="p.month">
          <circle v-if="p.y !== null" :cx="p.x" :cy="p.y" r="4" fill="#d97706"><title>{{ p.month }}: {{ p.rate }}%</title></circle>
          <text v-if="p.y !== null" :x="p.x" :y="p.y - 8" text-anchor="middle" font-size="10" fill="#334155" font-weight="700">{{ p.rate }}%</text>
          <text :x="p.x" :y="H - 8" text-anchor="middle" font-size="10" fill="#64748b">{{ p.month.slice(5) }}</text>
        </g>
      </svg>
    </div>
  </section>
</template>
