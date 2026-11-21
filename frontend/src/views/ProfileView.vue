<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { userVersion, clearSession } from '../api'

const router = useRouter()
const today = new Date().toLocaleDateString('sv-SE')
const me = ref(null), stats = ref(null)
const sheet = ref('')                       // '' | 'edit' | 'password'
const f = ref({ name: '', gender: '', dob: '', position: '' })
const pw = ref({ current: '', new: '', confirm: '' }), showPw = ref(false)
const err = ref(''), toast = ref(''), busy = ref(false)
const tgInfo = ref(null), installEvt = ref(null)
const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent), standalone = window.matchMedia('(display-mode: standalone)').matches
let toastTimer

const say = t => { toast.value = t; clearTimeout(toastTimer); toastTimer = setTimeout(() => (toast.value = ''), 2600) }
const sex = g => (g === 'M' ? 'ប្រុស' : g === 'F' ? 'ស្រី' : '-')
const fmt = iso => (iso ? iso.split('-').reverse().join('/') : '-')
const age = computed(() => {
  if (!me.value?.dob) return null
  const b = new Date(me.value.dob), n = new Date()
  let a = n.getFullYear() - b.getFullYear()
  if (n < new Date(n.getFullYear(), b.getMonth(), b.getDate())) a--
  return a
})
const STATS = [['present', 'មកធ្វើការ', 'text-green-600'], ['late', 'ក្នុងនោះយឺត', 'text-amber-600'],
  ['absent', 'អវត្តមាន', 'text-red-600'], ['leave', 'ច្បាប់', 'text-blue-600']]

function syncUser(u) { localStorage.setItem('user', JSON.stringify(u)); userVersion.value++; me.value = u }
async function load() {
  me.value = (await api.get('/profile')).data
  if (me.value.role === 'employee') {
    try { stats.value = (await api.get('/my/report', { params: { period: 'monthly', date: today } })).data.summary } catch {}
  }
}

async function pickPhoto(e) {                // photo changes save immediately
  const file = e.target.files[0]; if (!file) return
  const fd = new FormData(); fd.append('photo', file)
  try { syncUser((await api.put('/profile', fd)).data); say('បានប្ដូររូបថត ✔') }
  catch (er) { say(er.response?.data?.error || 'ប្ដូររូបថតមិនបាន') }
  e.target.value = ''
}
function openEdit() {
  const u = me.value
  f.value = { name: u.name, gender: u.gender || '', dob: u.dob || '', position: u.position || '' }
  err.value = ''; sheet.value = 'edit'
}
async function save() {
  err.value = ''; busy.value = true
  const fd = new FormData()
  Object.entries(f.value).forEach(([k, v]) => fd.append(k, v ?? ''))
  try { syncUser((await api.put('/profile', fd)).data); sheet.value = ''; say('បានរក្សាទុក ✔') }
  catch (e) { err.value = e.response?.data?.error || 'រក្សាទុកមិនបាន' }
  busy.value = false
}
function openPw() { pw.value = { current: '', new: '', confirm: '' }; err.value = ''; showPw.value = false; sheet.value = 'password' }
async function changePw() {
  err.value = ''
  if (pw.value.new !== pw.value.confirm) { err.value = 'ពាក្យសម្ងាត់ថ្មីមិនដូចគ្នា'; return }
  busy.value = true
  try {
    await api.post('/profile/password', { current: pw.value.current, new: pw.value.new })
    sheet.value = ''; say('បានប្ដូរពាក្យសម្ងាត់ ✔')
  } catch (e) { err.value = e.response?.data?.error || 'ប្ដូរមិនបាន' }
  busy.value = false
}
async function linkTg() {
  try { tgInfo.value = (await api.post('/profile/telegram-code')).data } catch (e) { say(e.response?.data?.error || 'បង្កើតកូដមិនបាន') }
}
async function unlinkTg() { await api.delete('/profile/telegram'); tgInfo.value = null; await load(); say('បានផ្ដាច់ Telegram') }
async function install() { installEvt.value.prompt(); await installEvt.value.userChoice; installEvt.value = null }
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEvt.value = e })
const logout = () => { clearSession(); router.push('/login') }
onMounted(load)
</script>

<template>
  <main v-if="me" class="max-w-md mx-auto p-4 pb-24 space-y-4">

    <!-- Staff ID card -->
    <section class="pop rounded-3xl overflow-hidden bg-white shadow-xl">
      <div class="lattice h-32 px-5 pt-4 flex justify-between items-start text-white">
        <span class="font-moul text-gold-400 text-lg">វិហសចំណាលើ</span>
        <span class="text-xs bg-white/15 rounded-full px-3 py-1">ប័ណ្ណបុគ្គលិក</span>
      </div>

      <div class="px-5 -mt-14 flex flex-col items-center text-center">
        <div class="relative">
          <div class="w-28 h-28 rounded-full ring-4 ring-gold-400 border-4 border-white overflow-hidden bg-slate-100 flex items-center justify-center text-5xl text-slate-300">
            <img v-if="me.photo" :src="me.photo" alt="" class="w-full h-full object-cover" /><span v-else>👤</span>
          </div>
          <label class="absolute bottom-0 right-0 w-9 h-9 rounded-full bg-royal text-white shadow-lg flex items-center justify-center cursor-pointer hover:bg-royal-700 focus-within:ring-2 focus-within:ring-gold-400"
                 title="ប្ដូររូបថត">
            <svg viewBox="0 0 24 24" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>
            <input type="file" accept="image/*" class="sr-only" @change="pickPhoto" />
          </label>
        </div>
        <h1 class="mt-3 text-2xl font-bold text-royal !font-khmer">{{ me.name }}</h1>
        <p class="text-slate-500">{{ me.position || 'មិនទាន់បញ្ចូលតួនាទី' }}</p>
      </div>

      <div class="mt-5 h-1 bg-gradient-to-r from-gold via-gold-400 to-gold"></div>
      <dl class="grid grid-cols-3 text-center py-4 px-2 text-sm">
        <div><dt class="text-slate-400">លេខកូដ</dt><dd class="font-semibold text-royal mt-0.5">{{ me.employee_code }}</dd></div>
        <div class="border-x border-slate-100"><dt class="text-slate-400">ភេទ</dt><dd class="font-semibold text-royal mt-0.5">{{ sex(me.gender) }}</dd></div>
        <div><dt class="text-slate-400">អាយុ</dt><dd class="font-semibold text-royal mt-0.5">{{ age !== null ? age + ' ឆ្នាំ' : '-' }}</dd></div>
      </dl>
    </section>

    <!-- This month -->
    <section v-if="stats" class="card !p-4">
      <div class="flex items-center justify-between mb-3">
        <h2 class="!font-khmer font-semibold text-slate-700">វត្តមានខែនេះ</h2>
        <router-link to="/my-report" class="text-sm text-royal underline">មើលលម្អិត</router-link>
      </div>
      <div class="grid grid-cols-4 text-center">
        <div v-for="s in STATS" :key="s[0]">
          <p :class="['text-2xl font-bold', s[2]]">{{ s[0] === 'present' ? (stats.came ?? ((stats.present || 0) + (stats.late || 0))) : (stats[s[0]] || 0) }}</p>
          <p class="text-xs text-slate-500">{{ s[1] }}</p>
        </div>
      </div>
    </section>

    <!-- Personal info -->
    <section class="card !p-0 overflow-hidden">
      <div class="flex items-center justify-between px-5 py-3">
        <h2 class="!font-khmer font-semibold text-slate-700">ព័ត៌មានផ្ទាល់ខ្លួន</h2>
        <button class="text-sm font-medium text-white bg-royal hover:bg-royal-700 rounded-full px-4 py-1.5 focus-visible:ring-2 focus-visible:ring-gold-400" @click="openEdit">កែប្រែ</button>
      </div>
      <ul class="divide-y divide-slate-100 text-sm">
        <li class="flex justify-between px-5 py-3"><span class="text-slate-500">ឈ្មោះពេញ</span><span class="font-medium text-right">{{ me.name }}</span></li>
        <li class="flex justify-between px-5 py-3"><span class="text-slate-500">ថ្ងៃខែឆ្នាំកំណើត</span><span class="font-medium">{{ fmt(me.dob) }}</span></li>
        <li class="flex justify-between px-5 py-3"><span class="text-slate-500">តួនាទី</span><span class="font-medium text-right">{{ me.position || '-' }}</span></li>
        <li v-if="me.department" class="flex justify-between px-5 py-3"><span class="text-slate-500">ផ្នែក / ក្រុម</span><span class="font-medium text-right">{{ me.department }}</span></li>
        <li class="flex justify-between px-5 py-3"><span class="text-slate-500">ចុះឈ្មោះកាលពី</span><span class="font-medium">{{ fmt(me.joined) }}</span></li>
      </ul>
    </section>

    <!-- Notifications + app -->
    <section class="card !p-4 space-y-3">
      <div>
        <div class="flex items-center justify-between"><h2 class="!font-khmer font-semibold text-slate-700">✈️ ជូនដំណឹងតាម Telegram</h2>
          <span :class="['text-xs px-2 py-0.5 rounded-full', me.telegram_linked ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">{{ me.telegram_linked ? 'បានភ្ជាប់' : 'មិនទាន់ភ្ជាប់' }}</span></div>
        <p class="text-xs text-slate-500 mt-1">ទទួលសារពេលច្បាប់ត្រូវអនុម័ត ភ្លេចស្កេនចេញ ឬ Admin កែវត្តមាន។</p>
        <button v-if="me.telegram_linked" class="text-sm text-red-600 underline mt-2" @click="unlinkTg">ផ្ដាច់ការភ្ជាប់</button>
        <button v-else-if="!tgInfo" class="btn !py-1.5 mt-2" @click="linkTg">ភ្ជាប់ Telegram</button>
        <div v-if="tgInfo && !me.telegram_linked" class="mt-3 rounded-xl bg-blue-50 p-3 text-sm space-y-1">
          <p>១. បើក Telegram រក Bot <a v-if="tgInfo.bot" :href="`https://t.me/${tgInfo.bot}`" target="_blank" class="text-royal underline font-medium">@{{ tgInfo.bot }}</a></p>
          <p>២. ផ្ញើសារ៖ <b class="text-royal text-lg tracking-widest select-all">/link {{ tgInfo.code }}</b></p>
          <p class="text-xs text-slate-500">កូដមានសុពលភាព {{ tgInfo.minutes }} នាទី។ ក្រោយផ្ញើ សូមចុច <button class="underline" @click="load">ផ្ទុកឡើងវិញ</button>។</p>
        </div>
      </div>
      <div v-if="!standalone" class="border-t pt-3">
        <h2 class="!font-khmer font-semibold text-slate-700">📲 ដំឡើងជាកម្មវិធីលើទូរស័ព្ទ</h2>
        <button v-if="installEvt" class="btn btn-gold !py-1.5 mt-2" @click="install">ដំឡើងឥឡូវ</button>
        <p v-else-if="isIos" class="text-xs text-slate-500 mt-1">iPhone៖ ចុចប៊ូតុង Share ⬆️ ក្នុង Safari រួចជ្រើស "Add to Home Screen"។</p>
        <p v-else class="text-xs text-slate-500 mt-1">Chrome៖ ចុចម៉ឺនុយ ⋮ រួចជ្រើស "Add to Home screen" / "Install app" (ត្រូវបើកតាម HTTPS)។</p>
      </div>
    </section>

    <!-- Account -->
    <section class="card !p-0 overflow-hidden divide-y divide-slate-100">
      <button class="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 focus-visible:bg-slate-50" @click="openPw">
        <span>🔒 ប្ដូរពាក្យសម្ងាត់</span><span class="text-slate-300 text-xl">›</span></button>
      <router-link v-if="me.role === 'employee'" to="/leave" class="flex items-center justify-between px-5 py-4 hover:bg-slate-50">
        <span>📝 សុំច្បាប់</span><span class="text-slate-300 text-xl">›</span></router-link>
      <button class="w-full flex items-center justify-between px-5 py-4 text-red-600 hover:bg-red-50 focus-visible:bg-red-50" @click="logout">
        <span>↩ ចាកចេញ</span><span class="text-red-200 text-xl">›</span></button>
    </section>

    <!-- Bottom sheets -->
    <div v-if="sheet" class="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center" @click.self="sheet = ''">
      <div class="sheet bg-white w-full max-w-md rounded-t-3xl sm:rounded-3xl p-6 max-h-[90vh] overflow-y-auto">
        <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-4 sm:hidden"></div>

        <template v-if="sheet === 'edit'">
          <h3 class="text-lg font-semibold text-royal mb-4 !font-khmer">កែប្រែព័ត៌មាន</h3>
          <label class="block text-sm text-slate-600 mb-3">ឈ្មោះពេញ
            <input v-model="f.name" class="input mt-1" autocomplete="name" /></label>
          <p class="text-sm text-slate-600 mb-1">ភេទ</p>
          <div class="grid grid-cols-2 gap-2 mb-3">
            <button v-for="g in [['M', 'ប្រុស'], ['F', 'ស្រី']]" :key="g[0]" type="button" @click="f.gender = g[0]"
              :class="['py-2 rounded-xl border-2 font-medium', f.gender === g[0] ? 'border-royal bg-royal-50 text-royal' : 'border-slate-200 text-slate-500']">{{ g[1] }}</button>
          </div>
          <label class="block text-sm text-slate-600 mb-3">ថ្ងៃខែឆ្នាំកំណើត
            <input v-model="f.dob" type="date" :max="today" class="input mt-1" /></label>
          <label class="block text-sm text-slate-600 mb-1">តួនាទី
            <input v-model="f.position" class="input mt-1" /></label>
          <p class="text-xs text-slate-400 mt-2">លេខកូដបុគ្គលិកមិនអាចកែបានទេ សូមទាក់ទង Admin។</p>
          <p v-if="err" class="text-red-600 text-sm mt-3">{{ err }}</p>
          <div class="grid grid-cols-2 gap-2 mt-5">
            <button class="btn !bg-slate-100 !text-slate-600 hover:!bg-slate-200" @click="sheet = ''">បោះបង់</button>
            <button class="btn btn-gold" :disabled="busy" @click="save">រក្សាទុក</button>
          </div>
        </template>

        <template v-else>
          <h3 class="text-lg font-semibold text-royal mb-4 !font-khmer">ប្ដូរពាក្យសម្ងាត់</h3>
          <input v-model="pw.current" :type="showPw ? 'text' : 'password'" class="input mb-3" placeholder="ពាក្យសម្ងាត់បច្ចុប្បន្ន" autocomplete="current-password" />
          <input v-model="pw.new" :type="showPw ? 'text' : 'password'" class="input mb-3" placeholder="ពាក្យសម្ងាត់ថ្មី (យ៉ាងតិច ៦ តួអក្សរ)" autocomplete="new-password" />
          <input v-model="pw.confirm" :type="showPw ? 'text' : 'password'" class="input mb-3" placeholder="បញ្ជាក់ពាក្យសម្ងាត់ថ្មី" autocomplete="new-password" />
          <label class="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" v-model="showPw" class="w-4 h-4" /> បង្ហាញពាក្យសម្ងាត់</label>
          <p v-if="err" class="text-red-600 text-sm mt-3">{{ err }}</p>
          <div class="grid grid-cols-2 gap-2 mt-5">
            <button class="btn !bg-slate-100 !text-slate-600 hover:!bg-slate-200" @click="sheet = ''">បោះបង់</button>
            <button class="btn btn-gold" :disabled="busy" @click="changePw">ប្ដូរពាក្យសម្ងាត់</button>
          </div>
        </template>
      </div>
    </div>

    <div v-if="toast" role="status" class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] bg-royal text-white px-5 py-2.5 rounded-full shadow-xl text-sm">{{ toast }}</div>
  </main>
</template>

<style scoped>
/* Khmer-lattice style diamond pattern on the ID card header */
.lattice {
  background-color: #003366;
  background-image:
    repeating-linear-gradient(45deg, rgba(255,255,255,.07) 0 1.5px, transparent 1.5px 16px),
    repeating-linear-gradient(-45deg, rgba(255,255,255,.07) 0 1.5px, transparent 1.5px 16px),
    linear-gradient(135deg, #003366, #1e3a8a);
}
.sheet { animation: sheet-up .25s ease-out; }
@keyframes sheet-up { from { transform: translateY(24px); opacity: 0; } to { transform: none; opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .sheet { animation: none; } }
</style>
