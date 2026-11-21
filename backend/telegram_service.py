import os, threading, time, requests

LEAVE_KH = {"Sick": "ឈឺ", "Personal": "ផ្ទាល់ខ្លួន", "Annual": "ប្រចាំឆ្នាំ"}


ON_MIGRATE = None   # set by app.py: saves the new chat id when Telegram upgrades the group to a supergroup
STATE = {"chat": None, "last": None}   # chat: id saved in the admin UI (overrides .env) · last: result of the latest group send


def configure(chat_id):
    STATE["chat"] = (chat_id or "").strip() or None


def chat_id():
    return STATE["chat"] or os.getenv("TELEGRAM_CHAT_ID") or None


def explain(desc, params=None):
    """Turn Telegram's English error into a Khmer hint that says what to fix."""
    d = (desc or "").lower()
    mig = (params or {}).get("migrate_to_chat_id")
    if mig:
        return f"Group ត្រូវបានប្ដូរជា supergroup — Chat ID ថ្មីគឺ {mig} (ដាក់ក្នុង កំណត់ → Telegram)"
    if "chat not found" in d:
        return "រក Chat មិនឃើញ — Chat ID ខុស ឬ Bot មិនទាន់នៅក្នុង Group (បន្ថែម Bot ចូល Group ហើយជ្រើសក្រុមពីបញ្ជី)"
    if "unauthorized" in d or d.strip() == "not found":
        return "Bot Token មិនត្រឹមត្រូវ — ពិនិត្យ TELEGRAM_BOT_TOKEN ក្នុង backend/.env (កុំមាន < > ឬចន្លោះ) ហើយ restart backend"
    if "kicked" in d or "not a member" in d or "forbidden" in d:
        return "Bot ត្រូវបានដកចេញពី Group ឬគ្មានសិទ្ធិផ្ញើ — បន្ថែម Bot ឡើងវិញ (ជា admin)"
    return desc or "Telegram error"


def _record(ok, info):
    STATE["last"] = {"ok": ok, "info": info, "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def _send(chat, text, record=True, _retry=True):
    tk = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tk or not chat:
        msg = "មិនទាន់កំណត់ TELEGRAM_BOT_TOKEN ឬ Chat ID (ក្នុង backend/.env ឬទំព័រ កំណត់)"
        if record: _record(False, msg)
        return False, msg
    try:
        j = requests.post(f"https://api.telegram.org/bot{tk}/sendMessage",
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=10).json()
    except Exception as e:
        msg = f"ភ្ជាប់ទៅ Telegram មិនបាន (បណ្ដាញ/Firewall ឬអ៊ីនធឺណិត): {e}"
        if record: _record(False, msg)
        print("Telegram error:", msg)
        return False, msg
    if j.get("ok"):
        if record: _record(True, "")
        return True, ""
    mig = (j.get("parameters") or {}).get("migrate_to_chat_id")
    if mig and _retry and record and ON_MIGRATE:      # group became a supergroup → adopt the new id and resend once
        new = str(mig)
        try: ON_MIGRATE(new)
        except Exception as e: print("Telegram migrate save error:", e)
        configure(new)
        return _send(new, text, record, _retry=False)
    msg = explain(j.get("description"), j.get("parameters"))
    if record: _record(False, msg)
    print("Telegram error:", msg)
    return False, msg


def _post(text):
    _send(chat_id(), text)


def send(text):
    """Non-blocking send to the admin group so API responses stay fast."""
    threading.Thread(target=_post, args=(text,), daemon=True).start()


def send_sync(text):
    """Blocking send that reports the result (used by the admin 'test Telegram' button)."""
    return _send(chat_id(), text)


def notify_scan(name, label, when, late=False, early=False):
    icon = "🟢" if label.startswith("ចូល") else "🔴"
    flag = " (⏰ យឺត)" if late else (" (⚠️ ចេញមុនម៉ោង)" if early else "")
    send(f"{icon} <b>{label}</b>{flag}\n👤 {name}\n🕒 {when}")


def notify_settings(s):
    send(f"⚙️ <b>Admin បានកែម៉ោងធ្វើការ</b>\n"
         f"🌅 ព្រឹក: ចូល {s['morning_in']} → ចេញ {s['morning_out']}\n"
         f"🌇 រសៀល: ចូល {s['afternoon_in']} → ចេញ {s['afternoon_out']}\n"
         f"⏰ អនុគ្រោះ: {s['late_grace_min']} នាទី | ⚠️ ព្រមានអវត្តមាន ≥ {s['high_absence_threshold']} ដង/ខែ")


def notify_leave(l):
    send(f"📝 <b>សំណើសុំច្បាប់ថ្មី</b>\n👤 {l.user.name}\n"
         f"ប្រភេទ: {LEAVE_KH.get(l.leave_type, l.leave_type)}\n"
         f"📅 {l.start_date} → {l.end_date}\nមូលហេតុ: {l.reason or '-'}")


def notify_high_absence(items, threshold):
    lines = "\n".join(f"• {i['name']}: អវត្តមាន {i['absent']} / យឺត {i['late']}" for i in items)
    send(f"⚠️ <b>បុគ្គលិកឈប់ច្រើន</b> (≥ {threshold} ដង/ខែ)\n{lines}")


def notify_leave_decision(l):
    ok = l.status == "Approved"
    send(f"{'✅ អនុម័ត' if ok else '❌ បដិសេធ'} សំណើសុំច្បាប់\n👤 {l.user.name}\n"
         f"📅 {l.start_date} → {l.end_date}")


def send_to(chat, text):
    """Message one person (private chat) without blocking."""
    threading.Thread(target=_send, args=(chat, text, False), daemon=True).start()


_BOT = {}


def api(method, **params):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return None
    try:
        return requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=12).json()
    except Exception:
        return None


def bot_username():
    if "u" not in _BOT:
        r = api("getMe")
        _BOT["u"] = (r or {}).get("result", {}).get("username")
    return _BOT.get("u")
