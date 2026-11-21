<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import api from '../api'
import { speak, khmerVoice } from '../voice'

const s = ref(null), locs = ref([]), msg = ref(''), err = ref('')
const chats = ref([]), chatInput = ref(''), myIp = ref(''), myIpPrivate = ref(false)
const BOOLS = ['allow_register', 'alert_count_late', 'wifi_required', 'device_binding', 'selfie_required', 'daily_summary', 'voice_enabled']

async function load() {
  const d = (await api.get('/admin/settings')).data
  BOOLS.forEach(k => (d[k] = d[k] === '1'))
  s.value = d; locs.value = (await api.get('/admin/locations')).data
  chatInput.value = d.telegram_chat || ''
  try { const r = (await api.get('/admin/my-ip')).data; myIp.value = r.ip; myIpPrivate.value = r.private } catch {}
  try { chats.value = (await api.get('/admin/telegram/chats')).data.chats } catch {}
}
async function save() {
  msg.value = err.value = ''
  const body = { ...s.value }; BOOLS.forEach(k => (body[k] = body[k] ? '1' : '0'))
  try { await api.put('/admin/settings', body); msg.value = 'បានរក្សាទុក ✔ (ជូនដំណឹង Telegram បើកែម៉ោង)'; await load() }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function testTg() {
  msg.value = err.value = ''
  try { await api.post('/admin/telegram/test'); msg.value = 'បានផ្ញើសារសាកល្បង — សូមមើលក្នុង Telegram Group' }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
  await load()
}
async function setChat(id) {
  msg.value = err.value = ''
  try { await api.put('/admin/telegram/chat', { chat_id: id }); msg.value = 'បានរក្សាទុក Chat ID ✔ — សាកល្បងផ្ញើសារ'; await load() }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
// ---- locations ----
async function saveLoc(l) {
  msg.value = err.value = ''
  try {
    if (l.id) await api.put(`/admin/locations/${l.id}`, l); else await api.post('/admin/locations', l)
    msg.value = 'បានរក្សាទុកទីតាំង ✔'; locs.value = (await api.get('/admin/locations')).data
  } catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
async function delLoc(l) {
  if (!confirm(`លុបទីតាំង "${l.name}"?`)) return
  try { await api.delete(`/admin/locations/${l.id}`); locs.value = (await api.get('/admin/locations')).data }
  catch (e) { err.value = e.response?.data?.error || 'បរាជ័យ' }
}
const addLoc = () => locs.value.push({ id: null, name: '', wifi_ips: '', active: true })
function addMyIp(l) {
  if (!myIp.value) return
  const cur = (l.wifi_ips || '').split(/[\s,;]+/).filter(Boolean)
  if (!cur.includes(myIp.value)) cur.push(myIp.value)
  l.wifi_ips = cur.join('\n')
  msg.value = `បានដាក់ ${myIp.value} — ចុច "រក្សាទុក" ដើម្បីបញ្ចប់`
}
const sample = (k = 'voice_template') => (s.value[k] || '').replace('{title}', 'លោកគ្រូ').replace('{name}', 'សុខ ចាន់').replace('{label}', 'ចូលព្រឹក').replace('{time}', '07:05')
const testVoice = k => speak(sample(k), s.value.voice_rate)
// ---- real voice clips (upload or record) ----
const vg = ref(null), vgo = ref(null), vgd = ref(null), vusers = ref([]), vuid = ref(''), vmsg = ref(''), rec = ref(null), recTarget = ref('')
const loadVoice = async () => { try { const d = (await api.get('/admin/voice')).data; vg.value = d.global_url; vgo.value = d.global_out_url; vgd.value = d.global_dup_url; vusers.value = d.users } catch {} }
async function uploadClip(target, file) {
  if (!file) return
  const fd = new FormData(); fd.append('file', file, file.name || 'record.webm')
  try { await api.post(['global', 'global_out', 'global_dup'].includes(target) ? `/admin/voice/${target}` : `/admin/voice/user/${target}`, fd); vmsg.value = '✔ បានរក្សាទុកសំឡេង'; await loadVoice() }
  catch (e) { vmsg.value = e.response?.data?.error || 'បរាជ័យ' }
}
const pickFile = (target, e) => { uploadClip(target, e.target.files[0]); e.target.value = '' }
async function delClip(target) {
  if (!confirm('លុបសំឡេងនេះ?')) return
  await api.delete(['global', 'global_out', 'global_dup'].includes(target) ? `/admin/voice/${target}` : `/admin/voice/user/${target}`); await loadVoice()
}
async function toggleRec(target) {
  if (rec.value) { rec.value.stop(); return }
  if (!navigator.mediaDevices?.getUserMedia) { vmsg.value = 'ត្រូវប្រើ HTTPS ដើម្បីថតសំឡេង'; return }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true }), chunks = []
    const r = new MediaRecorder(stream)
    r.ondataavailable = e => chunks.push(e.data)
    r.onstop = () => { stream.getTracks().forEach(t => t.stop()); rec.value = null; recTarget.value = ''
      uploadClip(target, new File([new Blob(chunks, { type: r.mimeType })], 'record.webm')) }
    r.start(); rec.value = r; recTarget.value = String(target)
  } catch { vmsg.value = 'មិនអាចបើកមីក្រូហ្វូន — សូមអនុញ្ញាត' }
}
onBeforeUnmount(() => rec.value?.stop())
const vuser = computed(() => vusers.value.find(u => u.id === vuid.value))
const copy = t => navigator.clipboard?.writeText(t)
onMounted(() => { load(); loadVoice() })
</script>

<template>
  <main v-if="s" class="max-w-2xl mx-auto p-4 space-y-4">
    <section class="card">
      <h2 class="text-royal mb-4">កំណត់ម៉ោងធ្វើការ</h2>
      <div class="grid sm:grid-cols-2 gap-3">
        <div class="rounded-xl bg-amber-50 p-3"><p class="font-medium mb-2">🌅 ពេលព្រឹក</p>
          <div class="grid grid-cols-2 gap-2">
            <label class="text-sm">🟢 ចូល <input type="time" v-model="s.morning_in" class="input mt-1" /></label>
            <label class="text-sm">🔴 ចេញ <input type="time" v-model="s.morning_out" class="input mt-1" /></label></div></div>
        <div class="rounded-xl bg-blue-50 p-3"><p class="font-medium mb-2">🌇 ពេលរសៀល</p>
          <div class="grid grid-cols-2 gap-2">
            <label class="text-sm">🟢 ចូល <input type="time" v-model="s.afternoon_in" class="input mt-1" /></label>
            <label class="text-sm">🔴 ចេញ <input type="time" v-model="s.afternoon_out" class="input mt-1" /></label></div></div>
        <label>⏰ អនុគ្រោះ (នាទី) <input type="number" min="0" max="180" v-model="s.late_grace_min" class="input mt-1" /></label>
        <label>⏱ ចន្លោះអប្បបរមារវាងការស្កេន (នាទី) <input type="number" min="0" max="60" v-model="s.min_checkout_gap_min" class="input mt-1" /></label>
      </div>
      <p class="text-sm text-slate-500 mt-3">បុគ្គលិកស្កេន <b>៤ ដង/ថ្ងៃ</b>៖ ចូលព្រឹក → ចេញព្រឹក → ចូលរសៀល → ចេញរសៀល។ ស្កេនចូលក្រោយ (ម៉ោង + អនុគ្រោះ) = យឺត (នៅតែរាប់ជាមកធ្វើការ)។ ថ្ងៃធ្វើការ និងថ្ងៃបុណ្យ កំណត់ក្នុងម៉ឺនុយ "ថ្ងៃឈប់សម្រាក"។</p>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">ការពារការស្កេនបន្លំ</h2>
      <label class="flex items-start gap-2 mb-2"><input type="checkbox" v-model="s.wifi_required" class="w-5 h-5 mt-0.5" /><span>📶 ត្រូវស្កេនពី WiFi របស់ការិយាល័យ <span class="block text-xs text-slate-400">ប្រព័ន្ធពិនិត្យ IP សាធារណៈ ដែលបានដាក់ក្នុងទីតាំងខាងក្រោម។ អ្នកប្រើ Mobile data នឹងស្កេនមិនបាន</span></span></label>
      <label class="flex items-start gap-2 mb-2"><input type="checkbox" v-model="s.device_binding" class="w-5 h-5 mt-0.5" /><span>📱 មួយគណនី ប្រើបានតែទូរស័ព្ទមួយ <span class="block text-xs text-slate-400">ភ្ជាប់នឹងទូរស័ព្ទក្នុងការស្កេនលើកដំបូង។ ប្ដូរទូរស័ព្ទ៖ Admin ដោះក្នុងទំព័របុគ្គលិក</span></span></label>
      <label class="flex items-start gap-2"><input type="checkbox" v-model="s.selfie_required" class="w-5 h-5 mt-0.5" /><span>🤳 ត្រូវថតរូប selfie មុនស្កេន <span class="block text-xs text-slate-400">រក្សាទុកក្នុងកំណត់ត្រាស្កេន ដើម្បី Admin ពិនិត្យ</span></span></label>
      <p class="text-xs text-slate-400 mt-3">ចំណាំ៖ វិធីទាំងនេះបង្កើនការពារ ប៉ុន្តែមិនអាចការពារបាន ១០០% ទេ (VPN ឬអ្នកនៅក្បែរការិយាល័យប្រើ WiFi ដូចគ្នា អាចស្កេនបាន)។ ត្រូវការ Server ដែលអាចឃើញ IP សាធារណៈពិតរបស់អ្នកប្រើ (Cloudflare Tunnel / Nginx)។</p>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">🔊 សំឡេងប្រកាសនៅម៉ាស៊ីនមេ (ទំព័រ QR ស្ថានី)</h2>
      <label class="flex items-center gap-2 mb-3"><input type="checkbox" v-model="s.voice_enabled" class="w-5 h-5" /> និយាយឈ្មោះអ្នកស្កេនពេលចុះវត្តមានជោគជ័យ</label>
      <label class="block text-sm">ប្រយោគពេលស្កេន<b>ចូល</b> (ចូលព្រឹក / ចូលរសៀល)
        <textarea v-model="s.voice_template" rows="2" maxlength="200" class="input mt-1"></textarea></label>
      <label class="block text-sm mt-3">ប្រយោគពេលស្កេន<b>ចេញ</b> (ចេញព្រឹក / ចេញរសៀល)
        <textarea v-model="s.voice_template_out" rows="2" maxlength="200" class="input mt-1"></textarea></label>
      <label class="block text-sm mt-3">ប្រយោគពេលបុគ្គលិក<b>ស្កេនរួចហើយ</b> (ស្កេនម្ដងទៀត / គ្រប់ ៤ ដងហើយ)
        <textarea v-model="s.voice_template_dup" rows="2" maxlength="200" class="input mt-1"></textarea></label>
      <p class="text-xs text-slate-400 mt-1">អាចប្រើ៖ <code>{title}</code> (លោកគ្រូ/អ្នកគ្រូ តាមភេទ) · <code>{name}</code> ឈ្មោះ · <code>{label}</code> (ចូលព្រឹក…) · <code>{time}</code> ម៉ោង</p>
      <label class="block text-sm mt-3">ល្បឿននិយាយ៖ <b>{{ s.voice_rate }}</b>
        <input type="range" min="0.5" max="1.5" step="0.1" v-model="s.voice_rate" class="w-full" /></label>
      <div class="flex gap-2 mt-2"><button class="btn !py-1" @click="testVoice('voice_template')">▶ សាកល្បង (ចូល)</button>
        <button class="btn !py-1" @click="testVoice('voice_template_out')">▶ សាកល្បង (ចេញ)</button>
        <button class="btn !py-1" @click="testVoice('voice_template_dup')">▶ សាកល្បង (ស្កេនរួច)</button></div>
      <p class="text-xs text-slate-400 mt-2">ឧទាហរណ៍៖ {{ sample() }} / {{ sample('voice_template_out') }} / {{ sample('voice_template_dup') }}</p>
      <div class="mt-4 pt-3 border-t">
        <p class="text-sm font-medium mb-2">របៀបសំឡេង</p>
        <label class="flex items-center gap-2 text-sm"><input type="radio" value="tts" v-model="s.voice_mode" /> 🤖 ម៉ាស៊ីននិយាយ (ប្រយោគខាងលើ)</label>
        <label class="flex items-center gap-2 text-sm mt-1"><input type="radio" value="file" v-model="s.voice_mode" /> 🎙 ប្រើសំឡេងផ្ទាល់ (upload / ថត)</label>
        <p class="text-xs text-slate-400 mt-1">រក្សាទុកការកំណត់ (ប៊ូតុងខាងក្រោម) ដើម្បីប្ដូររបៀប។ ក្នុងរបៀបសំឡេងផ្ទាល់ ប្រព័ន្ធចាក់ «សំឡេងឈ្មោះបុគ្គលិក» រួចចាក់ «សំឡេងទូទៅ»។ បើគ្មានឯកសារ នឹងប្រើម៉ាស៊ីននិយាយជំនួស។</p>

        <div class="rounded-xl bg-slate-50 p-3 mt-3">
          <p class="text-sm font-medium">សំឡេងទូទៅពេលស្កេន<b>ចូល</b> (ឧ. «ចុះវត្តមានបានជោគជ័យ»)</p>
          <audio v-if="vg" :src="vg" controls class="w-full mt-2"></audio>
          <p v-else class="text-xs text-slate-400 mt-1">មិនទាន់មាន</p>
          <div class="flex flex-wrap gap-2 mt-2 text-sm">
            <label class="btn !py-1 cursor-pointer">⬆ Upload<input type="file" accept="audio/*" class="sr-only" @change="pickFile('global', $event)" /></label>
            <button class="btn !py-1" :class="rec && recTarget === 'global' ? 'bg-red-600 animate-pulse' : 'bg-slate-600'" @click="toggleRec('global')">{{ rec && recTarget === 'global' ? '⏹ ឈប់ថត' : '🎙 ថតសំឡេង' }}</button>
            <button v-if="vg" class="btn !py-1 bg-red-600" @click="delClip('global')">លុប</button>
          </div>
        </div>

        <div class="rounded-xl bg-slate-50 p-3 mt-3">
          <p class="text-sm font-medium">សំឡេងទូទៅពេលស្កេន<b>ចេញ</b> (ឧ. «ស្កេនចេញបានជោគជ័យ»)</p>
          <audio v-if="vgo" :src="vgo" controls class="w-full mt-2"></audio>
          <p v-else class="text-xs text-slate-400 mt-1">មិនទាន់មាន</p>
          <div class="flex flex-wrap gap-2 mt-2 text-sm">
            <label class="btn !py-1 cursor-pointer">⬆ Upload<input type="file" accept="audio/*" class="sr-only" @change="pickFile('global_out', $event)" /></label>
            <button class="btn !py-1" :class="rec && recTarget === 'global_out' ? 'bg-red-600 animate-pulse' : 'bg-slate-600'" @click="toggleRec('global_out')">{{ rec && recTarget === 'global_out' ? '⏹ ឈប់ថត' : '🎙 ថតសំឡេង' }}</button>
            <button v-if="vgo" class="btn !py-1 bg-red-600" @click="delClip('global_out')">លុប</button>
          </div>
        </div>

        <div class="rounded-xl bg-slate-50 p-3 mt-3">
          <p class="text-sm font-medium">សំឡេងទូទៅពេល<b>ស្កេនរួចហើយ</b> (ឧ. «បានស្កេនរួចហើយ»)</p>
          <audio v-if="vgd" :src="vgd" controls class="w-full mt-2"></audio>
          <p v-else class="text-xs text-slate-400 mt-1">មិនទាន់មាន</p>
          <div class="flex flex-wrap gap-2 mt-2 text-sm">
            <label class="btn !py-1 cursor-pointer">⬆ Upload<input type="file" accept="audio/*" class="sr-only" @change="pickFile('global_dup', $event)" /></label>
            <button class="btn !py-1" :class="rec && recTarget === 'global_dup' ? 'bg-red-600 animate-pulse' : 'bg-slate-600'" @click="toggleRec('global_dup')">{{ rec && recTarget === 'global_dup' ? '⏹ ឈប់ថត' : '🎙 ថតសំឡេង' }}</button>
            <button v-if="vgd" class="btn !py-1 bg-red-600" @click="delClip('global_dup')">លុប</button>
          </div>
        </div>

        <div class="rounded-xl bg-slate-50 p-3 mt-3">
          <p class="text-sm font-medium">សំឡេងឈ្មោះបុគ្គលិក (ឧ. «លោកគ្រូ សុខ ចាន់»)</p>
          <select v-model="vuid" class="input mt-2"><option value="">— ជ្រើសបុគ្គលិក —</option>
            <option v-for="u in vusers" :key="u.id" :value="u.id">{{ u.url ? '🔊 ' : '' }}{{ u.name }} ({{ u.code }})</option></select>
          <template v-if="vuser">
            <audio v-if="vuser.url" :src="vuser.url" controls class="w-full mt-2"></audio>
            <div class="flex flex-wrap gap-2 mt-2 text-sm">
              <label class="btn !py-1 cursor-pointer">⬆ Upload<input type="file" accept="audio/*" class="sr-only" @change="pickFile(vuser.id, $event)" /></label>
              <button class="btn !py-1" :class="rec && recTarget === String(vuser.id) ? 'bg-red-600 animate-pulse' : 'bg-slate-600'" @click="toggleRec(vuser.id)">{{ rec && recTarget === String(vuser.id) ? '⏹ ឈប់ថត' : '🎙 ថតសំឡេង' }}</button>
              <button v-if="vuser.url" class="btn !py-1 bg-red-600" @click="delClip(vuser.id)">លុប</button>
            </div>
          </template>
          <p class="text-xs text-slate-400 mt-2">មានសំឡេងឈ្មោះ {{ vusers.filter(u => u.url).length }} / {{ vusers.length }} នាក់។ អ្នកដែលមិនទាន់មាន ម៉ាស៊ីននឹងនិយាយឈ្មោះជំនួស។</p>
        </div>
        <p v-if="vmsg" class="text-sm text-green-700 mt-2">{{ vmsg }}</p>
      </div>
      <p v-if="!khmerVoice()" class="text-xs text-amber-700 mt-1">⚠️ ឧបករណ៍/កម្មវិធីរុករកនេះមិនមាន voice ខ្មែរ — នឹងប្រើ Google TTS (ត្រូវការអ៊ីនធឺណិត)។ ណែនាំ Microsoft Edge ឬ Chrome លើ Android សម្រាប់សំឡេងខ្មែរល្អ។</p>
    </section>

    <section class="card">
      <div class="flex items-center justify-between mb-3"><h2 class="text-royal">ទីតាំង · WiFi · QR</h2><button class="btn !py-1" @click="addLoc">＋ ទីតាំង</button></div>
      <p class="text-sm text-slate-600 mb-3">IP សាធារណៈដែល server ឃើញពីអ្នក៖ <b class="text-royal">{{ myIp || '...' }}</b>
        <span v-if="myIpPrivate" class="block text-amber-700 text-xs">⚠️ នេះជា IP ក្នុងបណ្ដាញ (មិនមែន IP សាធារណៈ) — បើកតាម Tunnel/HTTPS ដើម្បីឃើញ IP ពិត</span></p>
      <div v-for="(l, i) in locs" :key="l.id || 'n' + i" :class="['rounded-xl border p-3 mb-3', l.active ? '' : 'opacity-50']">
        <input v-model="l.name" class="input mb-2" placeholder="ឈ្មោះទីតាំង (ឧ. ការិយាល័យកណ្ដាល)" />
        <textarea v-model="l.wifi_ips" rows="2" class="input font-mono text-sm" placeholder="IP របស់ WiFi ការិយាល័យ (មួយបន្ទាត់មួយ) ឧ. 203.0.113.7 ឬ 198.51.100.0/24"></textarea>
        <p v-if="s.wifi_required && !(l.wifi_ips || '').trim()" class="text-xs text-amber-700 mt-1">⚠️ មិនទាន់មាន IP — ទីតាំងនេះមិនត្រូវបានពិនិត្យ WiFi ទេ</p>
        <div class="flex flex-wrap gap-2 mt-2 text-sm">
          <button class="btn !py-1 bg-slate-600" @click="addMyIp(l)">📶 ដាក់ IP នៃ WiFi ដែលខ្ញុំកំពុងភ្ជាប់</button>
          <button class="btn !py-1" @click="saveLoc(l)">រក្សាទុក</button>
          <router-link v-if="l.id" :to="`/station?loc=${l.id}`" class="btn !py-1 bg-royal-700">បើក QR</router-link>
          <button v-if="l.id" class="btn !py-1 bg-red-600" @click="delLoc(l)">លុប</button>
        </div>
      </div>
      <p class="text-xs text-slate-400">របៀបដាក់៖ ភ្ជាប់ Admin ទៅ WiFi ការិយាល័យ (កុំប្រើ Mobile data) ហើយចុច "ដាក់ IP នៃ WiFi…" រួចរក្សាទុក។ ប្រសិនបើអ៊ីនធឺណិតការិយាល័យមានទាំង IPv4 និង IPv6 សូមដាក់ទាំងពីរ។ IP សាធារណៈអាចប្ដូរពេល router restart (ត្រូវអាប់ដេតវា) — សួរក្រុមហ៊ុនអ៊ីនធឺណិតរកសេវា Static IP ដើម្បីឲ្យថេរ។</p>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">ច្បាប់ និងការព្រមាន</h2>
      <div class="grid grid-cols-3 gap-3">
        <label class="text-sm">ច្បាប់ប្រចាំឆ្នាំ (ថ្ងៃ) <input type="number" min="0" v-model="s.leave_quota_annual" class="input mt-1" /></label>
        <label class="text-sm">ច្បាប់ឈឺ (ថ្ងៃ) <input type="number" min="0" v-model="s.leave_quota_sick" class="input mt-1" /></label>
        <label class="text-sm">ផ្ទាល់ខ្លួន (ថ្ងៃ) <input type="number" min="0" v-model="s.leave_quota_personal" class="input mt-1" /></label>
      </div>
      <p class="text-xs text-slate-400 mt-1">ដាក់ ០ = គ្មានកំណត់។ រាប់តែថ្ងៃធ្វើការ ក្នុងមួយឆ្នាំប្រតិទិន។</p>
      <label class="block mt-4">⚠️ ព្រមានបុគ្គលិកឈប់ច្រើន (អវត្តមាន+យឺត ≥ ប៉ុន្មានដង/ខែ)
        <input type="number" min="1" max="31" v-model="s.high_absence_threshold" class="input mt-1 !w-32" /></label>
      <label class="flex items-center gap-2 mt-3"><input type="checkbox" v-model="s.alert_count_late" class="w-5 h-5" /> រាប់ការមកយឺត ក្នុងការព្រមាន (មកយឺតនៅតែរាប់ជាមកធ្វើការ)</label>
      <label class="flex items-center gap-2 mt-3"><input type="checkbox" v-model="s.allow_register" class="w-5 h-5" /> អនុញ្ញាតឲ្យបុគ្គលិកចុះឈ្មោះខ្លួនឯង</label>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">ស្ថាប័ន និងរបាយការណ៍</h2>
      <label class="block text-sm">ឈ្មោះស្ថាប័ន (បង្ហាញលើរបាយការណ៍ PDF)<input v-model="s.org_name" class="input mt-1" /></label>
      <label class="flex items-center gap-2 mt-3"><input type="checkbox" v-model="s.daily_summary" class="w-5 h-5" /> ផ្ញើសង្ខេបវត្តមានប្រចាំថ្ងៃទៅ Telegram (១ ម៉ោងក្រោយម៉ោងចេញរសៀល)</label>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">Telegram</h2>
      <p :class="s.telegram_token ? 'text-green-700' : 'text-red-600'">{{ s.telegram_token ? '✔ មាន Bot Token ក្នុង backend/.env' : '✘ មិនទាន់មាន TELEGRAM_BOT_TOKEN ក្នុង backend/.env (ត្រូវ restart backend បន្ទាប់ពីកែ)' }}</p>
      <p :class="s.telegram_chat ? 'text-green-700' : 'text-red-600'">{{ s.telegram_chat ? '✔ Chat ID ដែលកំពុងប្រើ៖ ' + s.telegram_chat : '✘ មិនទាន់មាន Chat ID' }}</p>
      <p v-if="s.telegram_last" :class="['text-sm mt-1', s.telegram_last.ok ? 'text-green-700' : 'text-red-600']">
        សារចុងក្រោយ ({{ s.telegram_last.at }})៖ {{ s.telegram_last.ok ? 'ផ្ញើបានជោគជ័យ ✔' : '✘ ' + s.telegram_last.info }}</p>
      <div class="mt-3 flex gap-2">
        <input v-model="chatInput" class="input" placeholder="Chat ID (ឧ. -1001234567890)" inputmode="numeric" />
        <button class="btn !px-4" @click="setChat(chatInput)">រក្សាទុក</button>
      </div>
      <div v-if="chats.length" class="mt-3">
        <p class="text-sm text-slate-500 mb-1">ក្រុមដែល Bot ស្គាល់ (ជ្រើសរើស)៖</p>
        <button v-for="c in chats" :key="c.id" class="block w-full text-left rounded-xl border px-3 py-2 mb-1 hover:bg-royal-50 text-sm" @click="setChat(c.id)">
          {{ c.title || c.id }} <span class="text-slate-400">({{ c.id }})</span></button>
      </div>
      <p v-else class="text-xs text-slate-400 mt-2">បន្ថែម Bot ចូល Group (ឬដកចេញហើយបន្ថែមឡើងវិញ) ដើម្បីឲ្យវាបង្ហាញនៅទីនេះ — មិនចាំបាច់ប្រើ getUpdates ទេ។</p>
      <button class="btn mt-3" @click="testTg">ផ្ញើសារសាកល្បង</button>
      <p class="text-xs text-slate-400 mt-2">បុគ្គលិកអាចភ្ជាប់ Telegram ផ្ទាល់ខ្លួនក្នុងទំព័រ Profile ដើម្បីទទួលការជូនដំណឹងផ្ទាល់ (អនុម័តច្បាប់ ភ្លេចស្កេនចេញ…)។</p>
    </section>

    <section class="card">
      <h2 class="text-royal mb-3">Google Sheets</h2>
      <label>Link ឬ ID របស់ Google Sheet<input v-model="s.gsheet_id" class="input mt-1" placeholder="https://docs.google.com/spreadsheets/d/.../edit" /></label>
      <div class="text-sm mt-3 space-y-1">
        <p v-if="s.service_email" class="text-green-700">✔ ឃើញ credentials.json — Share Sheet ឲ្យ email នេះ (Editor)៖</p>
        <p v-else class="text-red-600">✘ រកមិនឃើញ backend/credentials.json (ទាញពី Google Cloud → Service Account → Keys → JSON)</p>
        <p v-if="s.service_email" class="bg-slate-100 rounded-lg p-2 break-all">{{ s.service_email }} <button class="underline text-royal ml-2" @click="copy(s.service_email)">ចម្លង</button></p>
        <p class="text-slate-500">ត្រូវបើក Google Sheets API និង Google Drive API ក្នុង Google Cloud ផងដែរ។</p>
      </div>
    </section>

    <p v-if="msg" class="text-green-700">{{ msg }}</p><p v-if="err" class="text-red-600">{{ err }}</p>
    <button class="btn btn-gold w-full sticky bottom-3 shadow-xl" @click="save">រក្សាទុកការកំណត់</button>
  </main>
</template>
