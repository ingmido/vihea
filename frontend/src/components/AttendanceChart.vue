<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Array, default: () => [] } })

const KEYS = ['present', 'late', 'absent', 'leave']          // stack order, bottom to top
const COLORS = { present: '#16a34a', late: '#f59e0b', absent: '#ef4444', leave: '#3b82f6' }
const LABELS = { present: 'មកទាន់ម៉ោង', late: 'មកយឺត', absent: 'អវត្តមាន', leave: 'ច្បាប់' }
const H = 260, ML = 40, MR = 12, MT = 22, MB = 34
const plotH = H - MT - MB

const single = computed(() => props.data.length === 1)        // daily view: one column per status
const n = computed(() => (single.value ? 4 : props.data.length))
const total = d => KEYS.reduce((s, k) => s + (d[k] || 0), 0)
const peak = computed(() => Math.max(1, ...(single.value
  ? KEYS.map(k => props.data[0][k] || 0) : props.data.map(total))))
const step = computed(() => Math.max(1, Math.ceil(peak.value / 5)))
const top = computed(() => Math.ceil(peak.value / step.value) * step.value)
const ticks = computed(() => { const t = []; for (let v = 0; v <= top.value; v += step.value) t.push(v); return t })

const W = computed(() => Math.max(520, ML + MR + n.value * (single.value ? 110 : 34)))
const slot = computed(() => (W.value - ML - MR) / n.value)
const bw = computed(() => Math.min(single.value ? 64 : 24, slot.value * 0.62))
const y = v => MT + plotH * (1 - v / top.value)
const x = i => ML + slot.value * i + (slot.value - bw.value) / 2

const bars = computed(() => single.value
  ? KEYS.map((k, i) => ({ i, label: LABELS[k], value: props.data[0][k] || 0, color: COLORS[k] }))
  : [])
function segs(d) {                                             // stacked segments for one date
  let acc = 0
  return KEYS.filter(k => d[k]).map(k => {
    const s = { key: k, y: y(acc + d[k]), h: y(acc) - y(acc + d[k]), color: COLORS[k], v: d[k] }
    acc += d[k]; return s
  })
}
const tip = d => `${d.date}\n` + KEYS.map(k => `${LABELS[k]}: ${d[k] || 0}`).join('\n')
</script>

<template>
  <div v-if="!data.length" class="text-center text-slate-400 py-10">មិនទាន់មានទិន្នន័យក្នុងចន្លោះនេះ</div>
  <div v-else>
    <div class="flex flex-wrap gap-4 text-sm mb-2">
      <span v-for="k in KEYS" :key="k" class="flex items-center gap-1.5">
        <i class="w-3 h-3 rounded-sm inline-block" :style="{ background: COLORS[k] }"></i>{{ LABELS[k] }}</span>
    </div>
    <div class="overflow-x-auto">
      <svg :width="W" :height="H" role="img" aria-label="ក្រាហ្វសរសរវត្តមាន" class="block mx-auto">
        <!-- grid + y axis -->
        <g v-for="t in ticks" :key="t">
          <line :x1="ML" :x2="W - MR" :y1="y(t)" :y2="y(t)" :stroke="t === 0 ? '#94a3b8' : '#e2e8f0'" />
          <text :x="ML - 8" :y="y(t) + 4" text-anchor="end" font-size="11" fill="#64748b">{{ t }}</text>
        </g>

        <!-- daily: one bar per status -->
        <g v-if="single">
          <g v-for="b in bars" :key="b.i">
            <rect :x="x(b.i)" :y="y(b.value)" :width="bw" :height="y(0) - y(b.value)" :fill="b.color" rx="4">
              <title>{{ b.label }}: {{ b.value }}</title></rect>
            <text :x="x(b.i) + bw / 2" :y="y(b.value) - 6" text-anchor="middle" font-size="13" font-weight="700" fill="#334155">{{ b.value }}</text>
            <text :x="x(b.i) + bw / 2" :y="H - 12" text-anchor="middle" font-size="12" fill="#475569">{{ b.label }}</text>
          </g>
        </g>

        <!-- weekly / monthly: stacked bar per date -->
        <g v-else>
          <g v-for="(d, i) in data" :key="d.date">
            <rect v-for="s in segs(d)" :key="s.key" :x="x(i)" :y="s.y" :width="bw" :height="s.h" :fill="s.color">
              <title>{{ tip(d) }}</title></rect>
            <text v-if="total(d)" :x="x(i) + bw / 2" :y="y(total(d)) - 5" text-anchor="middle" font-size="10" fill="#475569">{{ total(d) }}</text>
            <text :x="x(i) + bw / 2" :y="H - 12" text-anchor="middle" font-size="11" fill="#475569">{{ d.date.slice(8) }}</text>
          </g>
        </g>
      </svg>
    </div>
    <p v-if="!single" class="text-xs text-slate-400 text-center mt-1">ថ្ងៃទី (ក្នុងខែ) · ចង្អុលលើសរសរដើម្បីមើលលម្អិត</p>
  </div>
</template>
