<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'
import api from '../api'

const result = ref(null), err = ref(''), camErr = ref('')
const today = ref({ in1: null, out1: null, in2: null, out2: null, next: null, config: {} })
const selfie = ref(null), selfieUrl = ref('')
const CELLS = [['in1', '🟢 ចូលព្រឹក'], ['out1', '🔴 ចេញព្រឹក'], ['in2', '🟢 ចូលរសៀល'], ['out2', '🔴 ចេញរសៀល']]
const cfg = computed(() => today.value.config || {})
let scanner, busy = false

const loadToday = async () => { try { today.value = (await api.get('/attendance/today')).data } catch {} }

// ---- feedback: sound + voice ----
function beep() {
  try {
    const c = new (window.AudioContext || window.webkitAudioContext)()
    ;[880, 1175].forEach((f, i) => {
      const o = c.createOscillator(), g = c.createGain(), t = c.currentTime + i * 0.15
      o.frequency.value = f; o.connect(g); g.connect(c.destination)
      g.gain.setValueAtTime(0.25, t); o.start(t); o.stop(t + 0.12)
    })
  } catch {}
}
function speak(text) {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(text); u.lang = 'km-KH'; speechSynthesis.speak(u)
}
function playSuccess(d) {
  const a = new Audio('/sounds/success.mp3')
  a.play().catch(() => { beep(); speak(`${d.label} ជោគជ័យ`) })  // fallback: Web Audio beep + speechSynthesis
}

function takeSelfie(e) {
  selfie.value = e.target.files[0] || null
  selfieUrl.value = selfie.value ? URL.createObjectURL(selfie.value) : ''
}

async function onScan(text) {
  if (busy) return
  busy = true
  if (cfg.value.selfie_required && !selfie.value) {
    err.value = '📸 សូមថតរូប selfie ជាមុន ទើបស្កេន QR'; return setTimeout(() => { err.value = ''; busy = false }, 3000)
  }
  const fd = new FormData(); fd.append('token', text)
  if (selfie.value) fd.append('selfie', selfie.value)
  try {
    const { data } = await api.post('/attendance/scan', fd)
    result.value = data; playSuccess(data); selfie.value = null; selfieUrl.value = ''; loadToday()
  } catch (e) {
    err.value = e.response?.data?.error || 'ស្កេនមិនបានសម្រេច'
    setTimeout(() => { err.value = ''; busy = false }, 3500)
  }
}
const close = () => { result.value = null; busy = false }

onMounted(async () => {
  await loadToday()
  scanner = new Html5Qrcode('reader')
  try {
    await scanner.start({ facingMode: 'environment' }, { fps: 10, qrbox: 250 }, onScan, () => {})
  } catch { camErr.value = 'មិនអាចបើកកាមេរ៉ា — សូមអនុញ្ញាតកាមេរ៉ា និងប្រើ HTTPS' }
})
onBeforeUnmount(() => { scanner?.isScanning && scanner.stop().catch(() => {}) })
</script>

<template>
  <main class="max-w-md mx-auto p-4">
    <div class="card">
      <h2 class="text-royal text-center mb-3">ស្កេនវត្តមាន</h2>
      <p v-if="today.workday === false" class="mb-3 rounded-xl bg-blue-50 text-blue-700 text-sm text-center p-2">ថ្ងៃនេះជាថ្ងៃឈប់សម្រាក — បើអ្នកធ្វើការ នៅតែស្កេនបាន</p>
      <p v-if="cfg.wifi_required && !cfg.network_ok" class="mb-3 rounded-xl bg-red-50 text-red-700 text-sm p-3">📶 អ្នកមិនបានភ្ជាប់ WiFi របស់ការិយាល័យទេ — សូមភ្ជាប់ WiFi (បិទ Mobile data / VPN) ហើយ refresh ទំព័រ។
        <span class="block text-xs opacity-70 mt-1">IP របស់អ្នក៖ {{ cfg.ip }}</span></p>
      <p v-else-if="cfg.wifi_required" class="mb-2 text-xs text-center text-green-700">📶 បានភ្ជាប់ WiFi ការិយាល័យ ✔</p>
      <div class="grid grid-cols-2 gap-2 mb-3 text-center text-sm">
        <div v-for="c in CELLS" :key="c[0]"
          :class="['rounded-xl p-2', today[c[0]] ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
          {{ c[1] }}<br /><b class="text-lg">{{ today[c[0]] || '--:--' }}</b></div>
      </div>
      <p class="text-center text-xs text-slate-500 mb-2">
        {{ today.next ? `ស្កេនលើកបន្ទាប់ = ${today.next}` : '✔ ថ្ងៃនេះស្កេនគ្រប់ ៤ ដងហើយ' }}</p>

      <div v-if="cfg.selfie_required" class="mb-3 rounded-xl border-2 border-dashed border-gold p-3 flex items-center gap-3">
        <img v-if="selfieUrl" :src="selfieUrl" class="w-16 h-16 rounded-full object-cover border-2 border-gold" />
        <div class="flex-1 text-sm">
          <p class="font-medium">{{ selfie ? '✔ បានថតរូប — ស្កេន QR ឥឡូវ' : '📸 ត្រូវថតរូប selfie មុនស្កេន' }}</p>
          <label class="inline-block mt-1 text-royal underline cursor-pointer">{{ selfie ? 'ថតម្ដងទៀត' : 'ថតរូប' }}
            <input type="file" accept="image/*" capture="user" class="sr-only" @change="takeSelfie" /></label>
        </div>
      </div>

      <div id="reader" class="rounded-xl overflow-hidden"></div>
      <p v-if="camErr" class="text-red-600 text-sm mt-2">{{ camErr }}</p>
      <p v-if="err" class="mt-3 p-3 rounded-xl bg-red-50 text-red-700 text-center">{{ err }}</p>
      <p class="text-center text-sm text-slate-500 mt-3">ដាក់កាមេរ៉ាទៅរក QR នៅលើម៉ូនីទ័រ</p>
    </div>

    <div v-if="result" class="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div class="bg-white rounded-3xl p-8 text-center w-full max-w-sm pop">
        <img v-if="result.photo" :src="result.photo" class="w-20 h-20 rounded-full object-cover border-4 border-gold mx-auto mb-2" />
        <svg viewBox="0 0 64 64" class="w-28 h-28 mx-auto" fill="none" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
          <circle class="circle" cx="32" cy="32" r="30" stroke="#16a34a" />
          <path class="check" d="M18 33 l9 9 l19 -20" stroke="#16a34a" />
        </svg>
        <h3 class="text-xl font-bold text-green-700 mt-3">ស្កេនជោគជ័យ!</h3>
        <p class="text-slate-500 text-sm">({{ result.label }})</p>
        <p class="mt-4 text-lg font-semibold text-royal">{{ result.name }}</p>
        <p v-if="result.position" class="text-sm text-slate-500">{{ result.position }}</p>
        <p class="text-slate-600">{{ result.time }}</p>
        <p v-if="result.location" class="text-xs text-slate-400">📍 {{ result.location }}</p>
        <p v-if="result.late" class="text-gold font-medium mt-1">⏰ យឺត</p>
        <p v-if="result.early" class="text-gold font-medium mt-1">⚠️ ចេញមុនម៉ោង</p>
        <button class="btn btn-gold mt-5 w-full" @click="close">យល់ព្រម</button>
      </div>
    </div>
  </main>
</template>
