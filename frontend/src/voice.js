// Khmer text-to-speech helper (browser speechSynthesis; falls back to Google TTS audio when no Khmer voice exists).
let queue = [], playing = false

export function khmerVoice() {
  if (!('speechSynthesis' in window)) return null
  return speechSynthesis.getVoices().find(v => /^km/i.test(v.lang)) || null
}

function playNext() {
  if (playing || !queue.length) return
  playing = true
  const { text, rate, url } = queue.shift()
  const done = () => { playing = false; playNext() }
  if (url) {                                   // a real recorded clip
    const a = new Audio(url); a.onended = a.onerror = done
    a.play().catch(done); return
  }
  const v = khmerVoice()
  if (v) {
    const u = new SpeechSynthesisUtterance(text)
    u.voice = v; u.lang = v.lang; u.rate = rate
    u.onend = u.onerror = done
    speechSynthesis.speak(u)
  } else {
    const a = new Audio(`https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=km&q=${encodeURIComponent(text)}`)
    a.playbackRate = rate; a.onended = a.onerror = done
    a.play().catch(done)
  }
}

// parts = [{type:'tts', text} | {type:'audio', url}] played one after another
export function speakParts(parts, rate = 0.9) {
  parts.forEach(p => queue.push(p.type === 'audio' ? { url: p.url } : { text: p.text, rate: Number(rate) || 0.9 }))
  playNext()
}
export function speak(text, rate = 0.9) { queue.push({ text, rate: Number(rate) || 0.9 }); playNext() }
if ('speechSynthesis' in window) speechSynthesis.getVoices()   // warm up the voice list
