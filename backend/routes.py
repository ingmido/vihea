import hmac, hashlib, time, os, uuid, re, ipaddress
from functools import wraps
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, send_file, send_from_directory
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Attendance, LeaveRequest, QRToken, SystemSetting, Holiday, Location, ScanLog, Notification, ScanEvent
import telegram_service as tg
import export_service as ex

api = Blueprint("api", __name__, url_prefix="/api")
WINDOW, GRACE = 30, 10
STAFF = ("employee", "manager")          # roles that scan and appear in reports

DEFAULTS = {"morning_in": "07:00", "morning_out": "11:00", "afternoon_in": "14:00", "afternoon_out": "16:00",
            "late_grace_min": "15", "high_absence_threshold": "3", "allow_register": "1", "gsheet_id": "",
            "min_checkout_gap_min": "2", "alert_count_late": "1", "work_days": "1,2,3,4,5",
            "wifi_required": "0", "device_binding": "0", "selfie_required": "0",
            "leave_quota_annual": "18", "leave_quota_sick": "10", "leave_quota_personal": "5",
            "org_name": "វិហសចំណាលើ", "daily_summary": "1",
            "voice_enabled": "1", "voice_template": "{title} ឈ្មោះ {name} ចុះវត្តមានបានជោគជ័យ", "voice_rate": "0.9", "voice_mode": "tts",
            "voice_template_out": "{title} ឈ្មោះ {name} ស្កេនចេញបានជោគជ័យ",
            "voice_template_dup": "{title} ឈ្មោះ {name} បានស្កេនរួចហើយ"}
BOOL_KEYS = ("allow_register", "alert_count_late", "wifi_required", "device_binding", "selfie_required", "daily_summary", "voice_enabled")
TIME_KEYS = ("morning_in", "morning_out", "afternoon_in", "afternoon_out")


# ---------- helpers ----------
def setting(k, default=None):
    s = db.session.get(SystemSetting, k)
    return s.v if s else (DEFAULTS.get(k, "") if default is None else default)


def set_setting(k, v):
    s = db.session.get(SystemSetting, k)
    if s: s.v = v
    else: db.session.add(SystemSetting(k=k, v=v))
    db.session.commit()


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


def _role_guard(roles):
    def deco(fn):
        @wraps(fn)
        @jwt_required()
        def w(*a, **k):
            u = current_user()
            if not u or not u.active or u.role not in roles:
                return jsonify(error="អ្នកមិនមានសិទ្ធិប្រើមុខងារនេះ"), 403
            return fn(*a, **k)
        return w
    return deco


admin_only = _role_guard(("admin",))
staff_only = _role_guard(("admin", "manager"))   # admin + department managers


def scope_dept(u):
    """None = everyone (admin). A manager only sees their own department."""
    return None if u.role == "admin" else (u.department or "__none__")


def notify(u, title, body, key=None):
    """In-app notification (+ private Telegram if the person linked their account)."""
    if key and Notification.query.filter_by(user_id=u.id, key=key).first():
        return False
    db.session.add(Notification(user_id=u.id, title=title, body=body, key=key)); db.session.commit()
    if u.telegram_chat_id:
        tg.send_to(u.telegram_chat_id, f"<b>{title}</b>\n{body}")
    return True


ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp"}


def save_upload(file, allowed=None):
    ext = os.path.splitext(file.filename)[1].lower()
    if allowed and ext not in allowed:
        raise ValueError("ប្រភេទឯកសារមិនត្រឹមត្រូវ (ប្រើ JPG/PNG/WEBP)")
    fn = f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(current_app.config["UPLOAD_DIR"], fn))
    return fn


def remove_upload(name):
    if name:
        try: os.remove(os.path.join(current_app.config["UPLOAD_DIR"], name))
        except OSError: pass


def _form():
    return request.form if request.form else (request.get_json(silent=True) or {})


# ---------- WiFi check = the office's public IP ----------
def _trusted_proxy(addr):
    try:
        a = ipaddress.ip_address(addr)
        return a.is_loopback or a.is_private
    except ValueError:
        return False


def client_ip():
    """Public IP of the person. Proxy headers are trusted only when the request comes from our own proxy/tunnel."""
    remote = request.remote_addr or ""
    if _trusted_proxy(remote):
        for h in ("CF-Connecting-IP", "X-Real-IP"):
            v = request.headers.get(h, "").strip()
            if v: return v
        xff = request.headers.get("X-Forwarded-For", "")
        if xff: return xff.split(",")[0].strip()
    return remote


def _net(entry):
    e = entry.strip()
    if "/" in e:
        return ipaddress.ip_network(e, strict=False)
    a = ipaddress.ip_address(e)       # a lone IPv6 address = its /64 (phones rotate the last 64 bits)
    return ipaddress.ip_network(f"{e}/64", strict=False) if a.version == 6 else ipaddress.ip_network(f"{e}/32")


def normalize_ip_list(text):
    out = []
    for part in re.split(r"[,\s;]+", text or ""):
        if not part: continue
        try: n = _net(part)
        except ValueError: return "", f"IP មិនត្រឹមត្រូវ: {part}"
        if (n.version == 4 and n.prefixlen < 16) or (n.version == 6 and n.prefixlen < 48):
            return "", f"ជួរ IP ធំពេក (អាចឲ្យអ្នកក្រៅចូលបាន): {part}"
        if part not in out: out.append(part)
    return "\n".join(out), None


def ip_allowed(ip, text):
    try: a = ipaddress.ip_address((ip or "").strip())
    except ValueError: return False
    if a.version == 6 and a.ipv4_mapped: a = a.ipv4_mapped
    for part in re.split(r"[,\s;]+", text or ""):
        if not part: continue
        try:
            if a in _net(part): return True
        except ValueError: continue
    return False


def network_ok(ip):
    """True when the WiFi rule is off, no location has an IP list yet, or the IP matches any active location."""
    if setting("wifi_required") != "1": return True
    locs = [l for l in Location.query.filter_by(active=True) if l.wifi_ips]
    return True if not locs else any(ip_allowed(ip, l.wifi_ips) for l in locs)


@api.get("/admin/my-ip")
@admin_only
def my_ip():
    ip = client_ip()
    try: a = ipaddress.ip_address(ip); private = a.is_private or a.is_loopback
    except ValueError: private = True
    return jsonify(ip=ip, private=private)


def _hm(v):
    return datetime.strptime(v, "%H:%M")


# ---------- work days / holidays ----------
def work_weekdays():
    return {int(x) for x in setting("work_days").split(",") if x.strip().isdigit()}


def holiday_set(start, end):
    return {h.date for h in Holiday.query.filter(Holiday.date.between(start, end))}


def is_workday(d):
    return d.isoweekday() in work_weekdays() and not Holiday.query.filter_by(date=d).first()


def count_workdays(start, end):
    wd, hol, n, d = work_weekdays(), holiday_set(start, end), 0, start
    while d <= end:
        if d.isoweekday() in wd and d not in hol: n += 1
        d += timedelta(days=1)
    return n


# ---------- auth ----------
@api.post("/auth/login")
def login():
    d = request.get_json() or {}
    u = User.query.filter_by(employee_code=d.get("employee_code", "").strip(), active=True).first()
    if not u or not check_password_hash(u.password_hash, d.get("password", "")):
        return jsonify(error="លេខកូដ ឬពាក្យសម្ងាត់មិនត្រឹមត្រូវ"), 401
    return jsonify(token=create_access_token(identity=str(u.id)), user=u.to_dict())


@api.post("/auth/register")
def register():
    """Employee self-registration (form-data with photo). Optional REGISTER_CODE; disable via setting allow_register=0."""
    if setting("allow_register") != "1":
        return jsonify(error="ការចុះឈ្មោះត្រូវបានបិទ"), 403
    d = _form()
    need = os.getenv("REGISTER_CODE", "")
    if need and d.get("register_code", "") != need:
        return jsonify(error="កូដចុះឈ្មោះមិនត្រឹមត្រូវ"), 403
    code, name, pw = d.get("employee_code", "").strip(), d.get("name", "").strip(), d.get("password", "")
    position, gender = d.get("position", "").strip(), d.get("gender", "")
    if not code or not name or len(pw) < 6:
        return jsonify(error="សូមបំពេញទិន្នន័យឲ្យគ្រប់ (ពាក្យសម្ងាត់ ≥ 6 តួអក្សរ)"), 400
    if gender not in ("M", "F"):
        return jsonify(error="សូមជ្រើសរើសភេទ"), 400
    try:
        dob = date.fromisoformat(d.get("dob", ""))
        if dob >= date.today(): raise ValueError
    except ValueError:
        return jsonify(error="ថ្ងៃខែឆ្នាំកំណើតមិនត្រឹមត្រូវ"), 400
    if not position:
        return jsonify(error="សូមបញ្ចូលតួនាទី"), 400
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        return jsonify(error="សូមបញ្ចូលរូបថត"), 400
    if User.query.filter_by(employee_code=code).first():
        return jsonify(error="លេខកូដនេះមានរួចហើយ"), 409
    try:
        fn = save_upload(photo, ALLOWED_IMG)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    u = User(employee_code=code, name=name, role="employee", gender=gender, dob=dob, position=position,
             department=(d.get("department", "").strip()[:80] or None), photo=fn,
             password_hash=generate_password_hash(pw))
    db.session.add(u); db.session.commit()
    return jsonify(token=create_access_token(identity=str(u.id)), user=u.to_dict()), 201


@api.get("/auth/me")
@jwt_required()
def me():
    return jsonify(current_user().to_dict())


# ---------- admin: users ----------
def _apply_profile(u, d):
    """Validate + apply optional gender/dob/position/photo. Returns an error string or None."""
    if d.get("gender") not in (None, "", "M", "F"): return "ភេទមិនត្រឹមត្រូវ"
    if d.get("dob"):
        try:
            dob = date.fromisoformat(d["dob"])
            if dob >= date.today(): raise ValueError
            u.dob = dob
        except ValueError:
            return "ថ្ងៃខែឆ្នាំកំណើតមិនត្រឹមត្រូវ"
    if "gender" in d: u.gender = d.get("gender") or None
    if "position" in d: u.position = d.get("position", "").strip() or None
    photo = request.files.get("photo")
    if photo and photo.filename:
        try: fn = save_upload(photo, ALLOWED_IMG)
        except ValueError as e: return str(e)
        remove_upload(u.photo); u.photo = fn
    return None


def _apply_admin_fields(u, d):
    if "department" in d: u.department = (d.get("department") or "").strip()[:80] or None
    if d.get("role") in ("employee", "manager") and u.role != "admin": u.role = d["role"]
    if str(d.get("reset_device", "")).lower() in ("1", "true"): u.device_id = None


@api.get("/admin/users")
@staff_only
def users_list():
    q = User.query.order_by(User.role, User.name)
    me_ = current_user()
    if me_.role == "manager": q = q.filter_by(department=me_.department)
    return jsonify([u.to_dict() for u in q])


@api.post("/admin/users")
@admin_only
def users_create():
    d = _form()
    code, name, pw = d.get("employee_code", "").strip(), d.get("name", "").strip(), d.get("password", "")
    if not code or not name or len(pw) < 6:
        return jsonify(error="សូមបំពេញលេខកូដ ឈ្មោះ និងពាក្យសម្ងាត់ (≥ 6 តួអក្សរ)"), 400
    if User.query.filter_by(employee_code=code).first():
        return jsonify(error="លេខកូដនេះមានរួចហើយ"), 409
    u = User(employee_code=code, name=name, role="employee", password_hash=generate_password_hash(pw))
    err = _apply_profile(u, d)
    if err: return jsonify(error=err), 400
    _apply_admin_fields(u, d)
    db.session.add(u); db.session.commit()
    return jsonify(u.to_dict()), 201


@api.put("/admin/users/<int:uid>")
@admin_only
def users_update(uid):
    u, me_ = db.get_or_404(User, uid), current_user()
    d = _form()
    code, name = d.get("employee_code", u.employee_code).strip(), d.get("name", u.name).strip()
    if not code or not name:
        return jsonify(error="លេខកូដ និងឈ្មោះមិនអាចទទេ"), 400
    if code != u.employee_code and User.query.filter_by(employee_code=code).first():
        return jsonify(error="លេខកូដនេះមានរួចហើយ"), 409
    if d.get("password"):
        if len(d["password"]) < 6: return jsonify(error="ពាក្យសម្ងាត់ត្រូវ ≥ 6 តួអក្សរ"), 400
        u.password_hash = generate_password_hash(d["password"])
    if "active" in d:
        active = str(d["active"]).lower() in ("1", "true")
        if not active and (u.id == me_.id or u.role == "admin"):
            return jsonify(error="មិនអាចផ្អាកគណនី Admin បានទេ"), 400
        u.active = active
    err = _apply_profile(u, d)
    if err: return jsonify(error=err), 400
    _apply_admin_fields(u, d)
    u.employee_code, u.name = code, name
    db.session.commit()
    return jsonify(u.to_dict())


@api.delete("/admin/users/<int:uid>")
@admin_only
def users_delete(uid):
    u = db.get_or_404(User, uid)
    if u.role == "admin" or u.id == current_user().id:
        return jsonify(error="មិនអាចលុបគណនី Admin បានទេ"), 400
    from models import AuditLog
    for l in LeaveRequest.query.filter_by(user_id=uid):
        remove_upload(l.attachment)
    for s in ScanLog.query.filter_by(user_id=uid):
        remove_upload(s.selfie)
    ScanLog.query.filter_by(user_id=uid).delete()
    Notification.query.filter_by(user_id=uid).delete()
    AuditLog.query.filter((AuditLog.user_id == uid) | (AuditLog.admin_id == uid)).delete()
    LeaveRequest.query.filter_by(user_id=uid).delete()
    Attendance.query.filter_by(user_id=uid).delete()
    remove_upload(u.photo)
    db.session.delete(u); db.session.commit()
    return jsonify(ok=True)


# ---------- QR (30s rotation, 10s grace, one QR per location) ----------
def make_token(window, loc):
    h = hmac.new(current_app.config["QR_SECRET"].encode(), f"{loc}:{window}".encode(), hashlib.sha256).hexdigest()[:28]
    return f"{loc}.{h}"


@api.get("/qr/generate")
@admin_only
def qr_generate():
    loc = request.args.get("loc", type=int)
    L = db.session.get(Location, loc) if loc else Location.query.filter_by(active=True).order_by(Location.id).first()
    if not L or not L.active:
        return jsonify(error="រកមិនឃើញទីតាំង"), 404
    now = time.time(); t = make_token(int(now // WINDOW), L.id)
    if not QRToken.query.filter_by(token=t).first():
        db.session.add(QRToken(token=t)); db.session.commit()
    return jsonify(token=t, interval=WINDOW, expires_in=WINDOW - int(now % WINDOW), location=L.name, location_id=L.id)


def valid_token(t):
    """Returns the location id the token belongs to, or None."""
    try:
        loc = int(t.split(".", 1)[0])
    except (ValueError, AttributeError):
        return None
    now = time.time(); w = int(now // WINDOW)
    if hmac.compare_digest(t, make_token(w, loc)):
        return loc
    # previous token is accepted only during the first GRACE seconds of the new window
    if now % WINDOW <= GRACE and hmac.compare_digest(t, make_token(w - 1, loc)):
        return loc
    return None


# ---------- attendance: 4 scans per day ----------
SLOTS = [("in1", "check_in", "ចូលព្រឹក"), ("out1", "check_out", "ចេញព្រឹក"),
         ("in2", "check_in2", "ចូលរសៀល"), ("out2", "check_out2", "ចេញរសៀល")]
FIELD = {k: f for k, f, _ in SLOTS}
LABEL = {k: l for k, _, l in SLOTS}


def sched():
    g = lambda k: _hm(setting(k)).time()
    return dict(in1=g("morning_in"), out1=g("morning_out"), in2=g("afternoon_in"), out2=g("afternoon_out"))


def next_slot(rec, now):
    """Which of the 4 daily scans is next. After the lunch midpoint only the afternoon scans are offered."""
    sc, d = sched(), now.date()
    o1, i2 = datetime.combine(d, sc["out1"]), datetime.combine(d, sc["in2"])
    order = ["in2", "out2"] if now >= o1 + (i2 - o1) / 2 else [k for k, _, _ in SLOTS]
    for k in order:
        if rec is None or getattr(rec, FIELD[k]) is None:
            return k
    return None


@api.post("/attendance/scan")
@jwt_required()
def scan():
    u = current_user()
    if u.role not in STAFF:
        return jsonify(error="សម្រាប់បុគ្គលិកប៉ុណ្ណោះ"), 403
    d = _form()
    loc_id = valid_token(d.get("token", ""))
    loc = db.session.get(Location, loc_id) if loc_id else None
    if not loc or not loc.active:
        return jsonify(error="QR ផុតកំណត់ ឬមិនត្រឹមត្រូវ សូមស្កេនម្ដងទៀត"), 400

    # anti-spoofing: registered phone, office WiFi (public IP), selfie
    dev = request.headers.get("X-Device-Id", "")[:64]
    if setting("device_binding") == "1":
        if not dev: return jsonify(error="មិនអាចសម្គាល់ឧបករណ៍ សូម refresh ទំព័រ"), 400
        if u.device_id and u.device_id != dev:
            return jsonify(error="ទូរស័ព្ទនេះមិនមែនជាទូរស័ព្ទដែលបានចុះឈ្មោះទេ សូមទាក់ទង Admin"), 403
    ip = client_ip()
    if setting("wifi_required") == "1" and loc.wifi_ips and not ip_allowed(ip, loc.wifi_ips):
        return jsonify(error=f"សូមភ្ជាប់ WiFi របស់ {loc.name} (បិទ Mobile data / VPN) ហើយស្កេនម្ដងទៀត។ IP របស់អ្នក៖ {ip}"), 403
    selfie = request.files.get("selfie")
    if setting("selfie_required") == "1" and not (selfie and selfie.filename):
        return jsonify(error="សូមថតរូប selfie មុនស្កេន"), 400

    now = datetime.now(); today = now.date()
    rec = Attendance.query.filter_by(user_id=u.id, date=today).first()
    key = next_slot(rec, now)
    if key is None:
        db.session.add(ScanEvent(user_id=u.id, location_id=loc.id)); db.session.commit()
        return jsonify(error="អ្នកបានស្កេនគ្រប់ ៤ ដងរួចហើយថ្ងៃនេះ"), 409
    if rec:
        stamps = [getattr(rec, f) for _, f, _ in SLOTS if getattr(rec, f)]
        gap = int(setting("min_checkout_gap_min"))
        if stamps and now - max(stamps) < timedelta(minutes=gap):
            db.session.add(ScanEvent(user_id=u.id, location_id=loc.id)); db.session.commit()
            return jsonify(error=f"អ្នកទើបតែស្កេន សូមរង់ចាំ {gap} នាទី"), 409
    else:
        rec = Attendance(user_id=u.id, date=today, status="present"); db.session.add(rec)
    selfie_fn = None
    if selfie and selfie.filename:
        try: selfie_fn = save_upload(selfie, ALLOWED_IMG)
        except ValueError as e: return jsonify(error=str(e)), 400
    if not u.device_id and dev and setting("device_binding") == "1":
        u.device_id = dev                              # first scan binds this phone to the account
    sc, late, early = sched(), False, False
    setattr(rec, FIELD[key], now)
    if key in ("in1", "in2"):
        late = now > datetime.combine(today, sc[key]) + timedelta(minutes=int(setting("late_grace_min")))
        if late: rec.status = "late"
    else:
        early = now < datetime.combine(today, sc[key])
    db.session.add(ScanLog(user_id=u.id, ts=now, slot=key, location_id=loc.id, ip=ip,
                           device_id=dev or None, selfie=selfie_fn))
    db.session.commit()
    when = now.strftime("%Y-%m-%d %H:%M:%S")
    tg.notify_scan(u.name, LABEL[key], when, late, early)
    info = u.to_dict()
    return jsonify(action="check_in" if key.startswith("in") else "check_out", slot=key, label=LABEL[key],
                   name=u.name, time=when, status=rec.status, late=late, early=early, location=loc.name,
                   photo=info["photo"], position=info["position"])


@api.get("/attendance/today")
@jwt_required()
def my_today():
    a = Attendance.query.filter_by(user_id=int(get_jwt_identity()), date=date.today()).first()
    f = lambda x: x.strftime("%H:%M") if x else None
    nk = next_slot(a, datetime.now())
    return jsonify(in1=f(a.check_in) if a else None, out1=f(a.check_out) if a else None,
                   in2=f(a.check_in2) if a else None, out2=f(a.check_out2) if a else None,
                   status=a.status if a else None, next=LABEL.get(nk),
                   schedule={k: v.strftime("%H:%M") for k, v in sched().items()},
                   workday=is_workday(date.today()),
                   config=dict(wifi_required=setting("wifi_required") == "1", network_ok=network_ok(client_ip()),
                               ip=client_ip(),
                               selfie_required=setting("selfie_required") == "1",
                               device_binding=setting("device_binding") == "1"))


# ---------- reports ----------
def period_range(period, ref):
    if period == "weekly":
        s = ref - timedelta(days=ref.weekday()); return s, s + timedelta(days=6)
    if period == "monthly":
        s = ref.replace(day=1); n = (s + timedelta(days=32)).replace(day=1); return s, n - timedelta(days=1)
    return ref, ref


def build_report(start, end, user_id=None, dept=None):
    q = User.query.filter(User.role.in_(STAFF), User.active == True)  # noqa: E712
    if user_id: q = q.filter_by(id=user_id)
    if dept is not None: q = q.filter_by(department=dept)
    users = q.order_by(User.name).all()
    recs = {(a.user_id, a.date): a for a in Attendance.query.filter(Attendance.date.between(start, end))}
    leaves = LeaveRequest.query.filter(LeaveRequest.status == "Approved",
                                       LeaveRequest.start_date <= end, LeaveRequest.end_date >= start).all()
    wd, hol = work_weekdays(), holiday_set(start, end)
    rows, d, last = [], start, min(end, date.today())
    fmt = lambda x: x.strftime("%H:%M") if x else None
    while d <= last:
        workday = d.isoweekday() in wd and d not in hol
        for u in users:
            if u.created_at and d < u.created_at.date():
                continue  # do not count days before the employee registered
            a = recs.get((u.id, d))
            if not workday and not a:
                continue  # weekends / public holidays are not working days (unless someone scanned in)
            if a: st, t = a.status, [fmt(a.check_in), fmt(a.check_out), fmt(a.check_in2), fmt(a.check_out2)]
            elif any(l.user_id == u.id and l.start_date <= d <= l.end_date for l in leaves): st, t = "leave", [None] * 4
            else: st, t = "absent", [None] * 4
            rows.append(dict(date=d.isoformat(), code=u.employee_code, name=u.name, department=u.department,
                             in1=t[0], out1=t[1], in2=t[2], out2=t[3], status=st, user_id=u.id))
        d += timedelta(days=1)
    return rows


def high_absence():
    s, e = period_range("monthly", date.today())
    th = int(setting("high_absence_threshold")); acc = {}
    count_late = setting("alert_count_late") == "1"
    for r in build_report(s, e):
        if r["status"] == "absent" or (count_late and r["status"] == "late"):
            x = acc.setdefault(r["user_id"], dict(name=r["name"], code=r["code"], absent=0, late=0))
            x["absent" if r["status"] == "absent" else "late"] += 1
    items = [dict(x, total=x["absent"] + x["late"]) for x in acc.values() if x["absent"] + x["late"] >= th]
    return sorted(items, key=lambda i: -i["total"]), th


def check_and_alert():
    """Send the Telegram alert at most once per day."""
    items, th = high_absence()
    today = date.today().isoformat()
    if items and setting("last_alert", "") != today:
        tg.notify_high_absence(items, th); set_setting("last_alert", today)
    return items, th


def _params():
    p = request.args.get("period", "daily")
    ref = date.fromisoformat(request.args.get("date") or date.today().isoformat())
    return p, ref, *period_range(p, ref)


def summarize(rows):
    summary = dict(present=0, late=0, absent=0, leave=0)
    for r in rows:
        summary[r["status"]] += 1
    summary["came"] = summary["present"] + summary["late"]  # late staff still came to work
    return summary


@api.get("/admin/dashboard")
@staff_only
def dashboard():
    u = current_user(); dept = scope_dept(u)
    p, ref, s, e = _params()
    rows = build_report(s, e, dept=dept)
    chart = {}
    for r in rows:
        c = chart.setdefault(r["date"], dict(date=r["date"], present=0, late=0, absent=0, leave=0))
        c[r["status"]] += 1
    if u.role == "admin":
        items, th = check_and_alert()
    else:
        items, th = [i for i in high_absence()[0] if i["code"] in {r["code"] for r in rows}], int(setting("high_absence_threshold"))
    off = None
    if p == "daily":
        h = Holiday.query.filter_by(date=ref).first()
        off = h.name if h else (None if ref.isoweekday() in work_weekdays() else "ថ្ងៃឈប់សម្រាកប្រចាំសប្ដាហ៍")
    q = User.query.filter(User.role.in_(STAFF), User.active == True)  # noqa: E712
    if dept is not None: q = q.filter_by(department=dept)
    pend = LeaveRequest.query.filter_by(status="Pending")
    if dept is not None: pend = pend.join(User, LeaveRequest.user_id == User.id).filter(User.department == dept)
    return jsonify(summary=summarize(rows), rows=rows, chart=list(chart.values()), high_absence=items, threshold=th,
                   employees=q.count(), pending=pend.count(), off_day=off, role=u.role,
                   range=[s.isoformat(), e.isoformat()])


# ---------- leave ----------
def leave_dict(l):
    return dict(l.to_dict(), days=count_workdays(l.start_date, l.end_date))


def quota_of(t):
    return int(setting(f"leave_quota_{t.lower()}"))


def leave_days_used(uid, t, year, statuses=("Approved",)):
    qs = LeaveRequest.query.filter(LeaveRequest.user_id == uid, LeaveRequest.leave_type == t,
                                   LeaveRequest.status.in_(statuses),
                                   LeaveRequest.start_date >= date(year, 1, 1), LeaveRequest.start_date <= date(year, 12, 31))
    return sum(count_workdays(l.start_date, l.end_date) for l in qs)


@api.post("/leaves")
@jwt_required()
def leave_create():
    u, f = current_user(), request.form
    try:
        s, e = date.fromisoformat(f["start_date"]), date.fromisoformat(f["end_date"])
    except Exception:
        return jsonify(error="កាលបរិច្ឆេទមិនត្រឹមត្រូវ"), 400
    t = f.get("leave_type")
    if e < s or t not in ("Sick", "Personal", "Annual"):
        return jsonify(error="ទិន្នន័យមិនត្រឹមត្រូវ"), 400
    days = count_workdays(s, e)
    if days == 0:
        return jsonify(error="ថ្ងៃដែលជ្រើសរើសជាថ្ងៃឈប់សម្រាករួចហើយ មិនចាំបាច់សុំច្បាប់ទេ"), 400
    q = quota_of(t)
    if q > 0:
        used = leave_days_used(u.id, t, s.year, ("Approved", "Pending"))
        if used + days > q:
            return jsonify(error=f"លើសចំនួនថ្ងៃច្បាប់ដែលអនុញ្ញាត (សុំ {days} ថ្ងៃ នៅសល់ {max(q - used, 0)} ថ្ងៃ)"), 400
    fn, file = None, request.files.get("attachment")
    if file and file.filename:
        fn = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file.save(os.path.join(current_app.config["UPLOAD_DIR"], fn))
    l = LeaveRequest(user_id=u.id, leave_type=t, start_date=s, end_date=e, reason=f.get("reason", ""), attachment=fn)
    db.session.add(l); db.session.commit()
    tg.notify_leave(l)
    return jsonify(leave_dict(l)), 201


@api.get("/leaves")
@jwt_required()
def leave_list():
    u = current_user(); q = LeaveRequest.query.order_by(LeaveRequest.id.desc())
    if u.role == "admin" and not request.args.get("mine"):
        pass
    elif u.role == "manager" and not request.args.get("mine"):
        q = q.join(User, LeaveRequest.user_id == User.id).filter(User.department == u.department)
    else:
        q = q.filter(LeaveRequest.user_id == u.id)
    return jsonify([leave_dict(l) for l in q.limit(200)])


@api.put("/admin/leaves/<int:lid>")
@staff_only
def leave_decide(lid):
    u, l = current_user(), db.get_or_404(LeaveRequest, lid)
    if u.role == "manager" and (l.user.department != u.department or l.user_id == u.id):
        return jsonify(error="អ្នកអាចអនុម័តតែសំណើរបស់ផ្នែកខ្លួនប៉ុណ្ណោះ"), 403
    st = (request.get_json() or {}).get("status")
    if st not in ("Approved", "Rejected"): return jsonify(error="status?"), 400
    changed = l.status != st
    l.status = st; db.session.commit()
    if changed:
        tg.notify_leave_decision(l)
        ok = st == "Approved"
        notify(l.user, "✅ ច្បាប់ត្រូវបានអនុម័ត" if ok else "❌ ច្បាប់ត្រូវបានបដិសេធ", f"{l.start_date} → {l.end_date}")
    return jsonify(leave_dict(l))


@api.get("/uploads/<path:name>")
def uploads(name):
    return send_from_directory(current_app.config["UPLOAD_DIR"], name)


# ---------- export ----------
TITLES = {"daily": "របាយការណ៍ប្រចាំថ្ងៃ", "weekly": "របាយការណ៍ប្រចាំសប្ដាហ៍", "monthly": "របាយការណ៍ប្រចាំខែ"}


@api.get("/admin/export/excel")
@staff_only
def export_excel():
    p, ref, s, e = _params()
    buf = ex.build_excel(build_report(s, e, dept=scope_dept(current_user())), f"{TITLES[p]} {s} → {e}")
    return send_file(buf, as_attachment=True, download_name=f"attendance_{p}_{s}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@api.post("/admin/export/gsheet")
@admin_only
def export_gsheet():
    d = request.get_json() or {}
    p = d.get("period", "daily")
    s, e = period_range(p, date.fromisoformat(d.get("date") or date.today().isoformat()))
    try:
        url, n = ex.push_gsheet(build_report(s, e), f"{TITLES[p]} {s} → {e}", setting("gsheet_id", ""))
    except Exception as err:
        return jsonify(error=f"Google Sheets: {err}"), 500
    return jsonify(url=url, rows=n)


# ---------- admin settings ----------
@api.get("/admin/settings")
@admin_only
def settings_get():
    out = {k: setting(k) for k in DEFAULTS}
    out.update(service_email=ex.service_email(),
               telegram_ok=bool(os.getenv("TELEGRAM_BOT_TOKEN") and tg.chat_id()),
               telegram_token=bool(os.getenv("TELEGRAM_BOT_TOKEN")), telegram_chat=tg.chat_id(),
               telegram_last=tg.STATE["last"],
               gsheet_env=bool(os.getenv("GSHEET_ID")))
    return jsonify(out)


@api.put("/admin/settings")
@admin_only
def settings_put():
    d = request.get_json() or {}
    new = {k: str(d.get(k, setting(k))).strip() for k in DEFAULTS}
    try:
        ts = [_hm(new[k]) for k in TIME_KEYS]
        if any(ts[i] >= ts[i + 1] for i in range(3)):
            return jsonify(error="ម៉ោងត្រូវតាមលំដាប់៖ ចូលព្រឹក < ចេញព្រឹក < ចូលរសៀល < ចេញរសៀល"), 400
        if not 0 <= int(new["late_grace_min"]) <= 180 or not 1 <= int(new["high_absence_threshold"]) <= 31 \
                or not 0 <= int(new["min_checkout_gap_min"]) <= 60:
            raise ValueError
        for k in ("leave_quota_annual", "leave_quota_sick", "leave_quota_personal"):
            if not 0 <= int(new[k]) <= 366: raise ValueError
        days = sorted({int(x) for x in new["work_days"].split(",") if x.strip()})
        if not days or any(x < 1 or x > 7 for x in days): raise ValueError
        new["work_days"] = ",".join(map(str, days))
    except ValueError:
        return jsonify(error="ទិន្នន័យមិនត្រឹមត្រូវ (ម៉ោងទម្រង់ HH:MM)"), 400
    new["gsheet_id"] = ex.extract_sheet_id(new["gsheet_id"])
    new["org_name"] = new["org_name"][:120] or DEFAULTS["org_name"]
    for k in ("voice_template", "voice_template_out", "voice_template_dup"):
        new[k] = new[k][:200] or DEFAULTS[k]
    if new["voice_mode"] not in ("tts", "file"): new["voice_mode"] = "tts"
    try: new["voice_rate"] = str(min(1.5, max(0.5, float(new["voice_rate"]))))
    except ValueError: new["voice_rate"] = DEFAULTS["voice_rate"]
    for k in BOOL_KEYS:
        new[k] = "1" if new[k] in ("1", "true", "True") else "0"
    changed = {k for k in DEFAULTS if setting(k) != new[k]}
    for k, v in new.items():
        set_setting(k, v)
    if changed & (set(TIME_KEYS) | {"late_grace_min", "high_absence_threshold"}):
        tg.notify_settings(new)
    return jsonify(new)


@api.post("/admin/telegram/test")
@admin_only
def telegram_test():
    ok, info = tg.send_sync("✅ វិហសចំណាលើ — សារសាកល្បងពី Admin")
    return (jsonify(ok=True), 200) if ok else (jsonify(error=f"Telegram: {info}"), 400)


def absent_notice():
    """Once per workday, shortly after (morning_in + grace), tell Telegram who has not scanned in."""
    now = datetime.now(); today = now.date().isoformat()
    if not is_workday(now.date()) or setting("last_absent_notice", "") == today:
        return
    cutoff = _hm(setting("morning_in")) + timedelta(minutes=int(setting("late_grace_min")))
    cm, nm = cutoff.hour * 60 + cutoff.minute, now.hour * 60 + now.minute
    if not cm <= nm < cm + 60:
        return
    absent = [r["name"] for r in build_report(date.today(), date.today()) if r["status"] == "absent"]
    set_setting("last_absent_notice", today)
    if absent:
        tg.notify_absent_today(absent, cutoff.strftime("%H:%M"))


# ---------- own report / profile ----------
@api.get("/my/report")
@jwt_required()
def my_report():
    u = current_user()
    p, ref, s, e = _params()
    rows = build_report(s, e, u.id)
    rows.sort(key=lambda r: r["date"], reverse=True)
    return jsonify(summary=summarize(rows), rows=rows, range=[s.isoformat(), e.isoformat()])


@api.get("/profile")
@jwt_required()
def profile_get():
    return jsonify(current_user().to_dict())


@api.put("/profile")
@jwt_required()
def profile_update():
    u, d = current_user(), _form()
    name = d.get("name", u.name).strip()
    if not name:
        return jsonify(error="សូមបញ្ចូលឈ្មោះ"), 400
    err = _apply_profile(u, d)
    if err:
        db.session.rollback()
        return jsonify(error=err), 400
    u.name = name
    db.session.commit()
    return jsonify(u.to_dict())


@api.post("/profile/password")
@jwt_required()
def profile_password():
    u, d = current_user(), request.get_json() or {}
    if not check_password_hash(u.password_hash, d.get("current", "")):
        return jsonify(error="ពាក្យសម្ងាត់បច្ចុប្បន្នមិនត្រឹមត្រូវ"), 400
    if len(d.get("new", "")) < 6:
        return jsonify(error="ពាក្យសម្ងាត់ថ្មីត្រូវ ≥ 6 តួអក្សរ"), 400
    u.password_hash = generate_password_hash(d["new"]); db.session.commit()
    return jsonify(ok=True)
