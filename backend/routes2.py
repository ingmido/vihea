"""Extra features: holidays, locations, scan log, manual edits + audit, leave balance/calendar, monthly report,
insights, in-app notifications, Telegram linking + background jobs, Excel import."""
import os, io, json, re, random, string
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required
from werkzeug.security import generate_password_hash
from models import db, User, Attendance, LeaveRequest, Holiday, Location, ScanLog, AuditLog, Notification, ScanEvent
from routes import (setting, set_setting, current_user, admin_only, staff_only, scope_dept, notify, build_report,
                    summarize, period_range, count_workdays, work_weekdays, sched, is_workday, STAFF, quota_of,
                    leave_days_used, remove_upload, LABEL, _hm, normalize_ip_list)
import telegram_service as tg

api2 = Blueprint("api2", __name__, url_prefix="/api")


# ---------- holidays ----------
FIXED_HOLIDAYS = [("01-01", "ទិវាចូលឆ្នាំសកល"), ("01-07", "ទិវាជ័យជម្នះលើរបបប្រល័យពូជសាសន៍"),
                  ("03-08", "ទិវានារីអន្តរជាតិ"), ("05-01", "ទិវាពលកម្មអន្តរជាតិ"),
                  ("05-14", "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្មព្រះមហាក្សត្រ"),
                  ("06-18", "ព្រះរាជពិធីបុណ្យចម្រើនព្រះជន្មព្រះវររាជមាតា"), ("09-24", "ទិវាប្រកាសរដ្ឋធម្មនុញ្ញ"),
                  ("10-15", "ទិវាគោរពព្រះវិញ្ញាណក្ខន្ធព្រះបរមរតនកោដ្ឋ"), ("10-29", "ព្រះរាជពិធីគ្រងរាជ្យសម្បត្តិ"),
                  ("11-09", "ពិធីបុណ្យឯករាជ្យជាតិ"), ("12-10", "ទិវាសិទ្ធិមនុស្សអន្តរជាតិ")]


def _hol(h):
    return dict(id=h.id, date=h.date.isoformat(), name=h.name)


@api2.get("/holidays")
@jwt_required()
def holidays_list():
    q = Holiday.query.order_by(Holiday.date)
    y = request.args.get("year", type=int)
    if y: q = q.filter(Holiday.date.between(date(y, 1, 1), date(y, 12, 31)))
    return jsonify([_hol(h) for h in q])


@api2.post("/admin/holidays")
@admin_only
def holiday_add():
    d = request.get_json() or {}
    try:
        s = date.fromisoformat(d["date"]); e = date.fromisoformat(d.get("end_date") or d["date"])
    except Exception:
        return jsonify(error="កាលបរិច្ឆេទមិនត្រឹមត្រូវ"), 400
    name = (d.get("name") or "").strip()[:120]
    if not name or e < s or (e - s).days > 30:
        return jsonify(error="សូមបញ្ចូលឈ្មោះ និងចន្លោះថ្ងៃ (≤ 31 ថ្ងៃ)"), 400
    n = 0
    while s <= e:
        if not Holiday.query.filter_by(date=s).first():
            db.session.add(Holiday(date=s, name=name)); n += 1
        s += timedelta(days=1)
    db.session.commit()
    return jsonify(added=n), 201


@api2.delete("/admin/holidays/<int:hid>")
@admin_only
def holiday_del(hid):
    db.session.delete(db.get_or_404(Holiday, hid)); db.session.commit()
    return jsonify(ok=True)


@api2.post("/admin/holidays/seed")
@admin_only
def holiday_seed():
    y = (request.get_json() or {}).get("year") or date.today().year
    n = 0
    for md, name in FIXED_HOLIDAYS:
        d = date.fromisoformat(f"{int(y)}-{md}")
        if not Holiday.query.filter_by(date=d).first():
            db.session.add(Holiday(date=d, name=name)); n += 1
    db.session.commit()
    return jsonify(added=n)


# ---------- locations (one QR per location) ----------
def _loc_fields(L, d):
    L.name = (d.get("name") or L.name or "").strip()[:120]
    if "wifi_ips" in d:
        txt, bad = normalize_ip_list(d.get("wifi_ips") or "")
        if bad: raise ValueError(bad)
        L.wifi_ips = txt or None
    if "active" in d: L.active = bool(d["active"])


@api2.get("/admin/locations")
@admin_only
def loc_list():
    return jsonify([L.to_dict() for L in Location.query.order_by(Location.id)])


@api2.post("/admin/locations")
@admin_only
def loc_add():
    L = Location()
    try: _loc_fields(L, request.get_json() or {})
    except ValueError as e: return jsonify(error=str(e) or "ទិន្នន័យមិនត្រឹមត្រូវ"), 400
    if not L.name: return jsonify(error="សូមបញ្ចូលឈ្មោះទីតាំង"), 400
    db.session.add(L); db.session.commit()
    return jsonify(L.to_dict()), 201


@api2.put("/admin/locations/<int:lid>")
@admin_only
def loc_edit(lid):
    L = db.get_or_404(Location, lid)
    try: _loc_fields(L, request.get_json() or {})
    except ValueError as e: return jsonify(error=str(e) or "ទិន្នន័យមិនត្រឹមត្រូវ"), 400
    db.session.commit()
    return jsonify(L.to_dict())


@api2.delete("/admin/locations/<int:lid>")
@admin_only
def loc_del(lid):
    L = db.get_or_404(Location, lid)
    if Location.query.filter_by(active=True).count() <= 1 and L.active:
        return jsonify(error="ត្រូវមានទីតាំងយ៉ាងតិចមួយ"), 400
    if ScanLog.query.filter_by(location_id=lid).first(): L.active = False   # keep history
    else: db.session.delete(L)
    db.session.commit()
    return jsonify(ok=True)


# ---------- scan log ----------
@api2.get("/admin/scanlog")
@admin_only
def scanlog():
    day = date.fromisoformat(request.args.get("date") or date.today().isoformat())
    q = ScanLog.query.filter(ScanLog.ts >= datetime.combine(day, datetime.min.time()),
                             ScanLog.ts < datetime.combine(day + timedelta(days=1), datetime.min.time())).order_by(ScanLog.ts.desc())
    uid = request.args.get("user_id", type=int)
    if uid: q = q.filter_by(user_id=uid)
    return jsonify([dict(id=s.id, name=s.user.name, code=s.user.employee_code, time=s.ts.strftime("%H:%M:%S"),
                         slot=LABEL.get(s.slot, s.slot), location=s.location.name if s.location else None,
                         ip=s.ip, selfie=f"/api/uploads/{s.selfie}" if s.selfie else None) for s in q.limit(300)])


# ---------- manual attendance edit + audit ----------
def _t(v):
    v = (v or "").strip()
    return _hm(v).time() if v else None


def _fmt(a):
    f = lambda x: x.strftime("%H:%M") if x else "-"
    return "/".join(f(x) for x in (a.check_in, a.check_out, a.check_in2, a.check_out2)) if a else "គ្មាន"


@api2.get("/admin/attendance")
@admin_only
def att_get():
    uid, day = request.args.get("user_id", type=int), date.fromisoformat(request.args.get("date"))
    a = Attendance.query.filter_by(user_id=uid, date=day).first()
    f = lambda x: x.strftime("%H:%M") if x else ""
    return jsonify(exists=bool(a), in1=f(a.check_in) if a else "", out1=f(a.check_out) if a else "",
                   in2=f(a.check_in2) if a else "", out2=f(a.check_out2) if a else "", note=a.note if a else "")


@api2.put("/admin/attendance")
@admin_only
def att_put():
    d, admin = request.get_json() or {}, current_user()
    reason = (d.get("reason") or "").strip()
    u = db.session.get(User, d.get("user_id") or 0)
    try: day, ts = date.fromisoformat(d["date"]), [_t(d.get(k)) for k in ("in1", "out1", "in2", "out2")]
    except Exception: return jsonify(error="ទិន្នន័យមិនត្រឹមត្រូវ"), 400
    if not u or u.role not in STAFF: return jsonify(error="រកមិនឃើញបុគ្គលិក"), 404
    if len(reason) < 3: return jsonify(error="សូមបញ្ចូលមូលហេតុនៃការកែ"), 400
    a = Attendance.query.filter_by(user_id=u.id, date=day).first()
    before = _fmt(a)
    if all(t is None for t in ts):
        if a: db.session.delete(a)
        action, after = "delete", "លុប"
    else:
        if not a: a = Attendance(user_id=u.id, date=day); db.session.add(a)
        dt = lambda t: datetime.combine(day, t) if t else None
        a.check_in, a.check_out, a.check_in2, a.check_out2 = (dt(t) for t in ts)
        sc, grace = sched(), timedelta(minutes=int(setting("late_grace_min")))
        late = (ts[0] and datetime.combine(day, ts[0]) > datetime.combine(day, sc["in1"]) + grace) or \
               (ts[2] and datetime.combine(day, ts[2]) > datetime.combine(day, sc["in2"]) + grace)
        a.status, a.note = ("late" if late else "present"), reason[:255]
        action, after = "edit", _fmt(a)
    db.session.add(AuditLog(admin_id=admin.id, user_id=u.id, date=day, action=action,
                            detail=f"{before} → {after} | {reason}"))
    db.session.commit()
    notify(u, "✏️ Admin បានកែវត្តមាន", f"{day}: {after}\nមូលហេតុ: {reason}")
    return jsonify(ok=True)


@api2.get("/admin/audit")
@admin_only
def audit_list():
    q = AuditLog.query.order_by(AuditLog.id.desc()).limit(request.args.get("limit", 100, type=int))
    return jsonify([dict(id=x.id, when=x.created_at.strftime("%Y-%m-%d %H:%M"), admin=x.admin.name if x.admin else "-",
                         user=x.user.name if x.user else "-", date=x.date.isoformat() if x.date else None,
                         action=x.action, detail=x.detail) for x in q])


# ---------- leave balance + calendar ----------
@api2.get("/leaves/balance")
@jwt_required()
def leave_balance():
    u, y = current_user(), request.args.get("year", date.today().year, type=int)
    out = {}
    for t in ("Annual", "Sick", "Personal"):
        q, used = quota_of(t), leave_days_used(u.id, t, y)
        pend = leave_days_used(u.id, t, y, ("Pending",))
        out[t] = dict(quota=q, used=used, pending=pend, left=(max(q - used - pend, 0) if q else None))
    return jsonify(year=y, balance=out)


@api2.get("/admin/leave-calendar")
@staff_only
def leave_calendar():
    m = request.args.get("month") or date.today().strftime("%Y-%m")
    s = date.fromisoformat(m + "-01"); _, e = period_range("monthly", s)
    dept = scope_dept(current_user())
    q = LeaveRequest.query.filter(LeaveRequest.status == "Approved", LeaveRequest.start_date <= e,
                                  LeaveRequest.end_date >= s)
    if dept is not None: q = q.join(User, LeaveRequest.user_id == User.id).filter(User.department == dept)
    days = {}
    for l in q:
        d = max(l.start_date, s)
        while d <= min(l.end_date, e):
            days.setdefault(d.isoformat(), []).append(dict(name=l.user.name, type=l.leave_type))
            d += timedelta(days=1)
    hol = {h.date.isoformat(): h.name for h in Holiday.query.filter(Holiday.date.between(s, e))}
    return jsonify(month=m, first_weekday=s.isoweekday(), days_in_month=e.day, leaves=days, holidays=hol)


# ---------- monthly report (printable) ----------
def _mins(a, b):
    if not a or not b: return 0
    to = lambda t: int(t[:2]) * 60 + int(t[3:])
    return max(to(b) - to(a), 0)


@api2.get("/admin/departments")
@staff_only
def departments():
    dept = scope_dept(current_user())
    ds = {u.department for u in User.query.filter(User.role.in_(STAFF)) if u.department}
    return jsonify(sorted(ds if dept is None else {dept} & ds))


def _monthly(m, dept):
    s = date.fromisoformat(m + "-01"); _, e = period_range("monthly", s)
    per, detail = {}, build_report(s, e, dept=dept)
    for r in detail:
        x = per.setdefault(r["user_id"], dict(code=r["code"], name=r["name"], department=r["department"],
                                              present=0, late=0, absent=0, leave=0, minutes=0))
        x[r["status"]] += 1
        x["minutes"] += _mins(r["in1"], r["out1"]) + _mins(r["in2"], r["out2"])
    rows = sorted(per.values(), key=lambda x: x["name"])
    for x in rows:
        x["came"] = x["present"] + x["late"]; x["hours"] = round(x["minutes"] / 60, 1)
    pos = {u.employee_code: u.position for u in User.query.filter(User.role.in_(STAFF))}
    for x in rows: x["position"] = pos.get(x["code"])
    data = dict(org=setting("org_name"), month=m, dept=dept, rows=rows, workdays=count_workdays(s, e),
                totals={k: sum(x[k] for x in rows) for k in ("came", "late", "absent", "leave", "hours")})
    return data, detail


def _monthly_args():
    scope = scope_dept(current_user())
    m = request.args.get("month") or date.today().strftime("%Y-%m")
    return m, (scope if scope is not None else (request.args.get("dept") or None))


@api2.get("/admin/report/monthly")
@staff_only
def monthly_report():
    return jsonify(_monthly(*_monthly_args())[0])


@api2.get("/admin/report/monthly/excel")
@staff_only
def monthly_report_excel():
    import export_service as ex
    try: m, dept = _monthly_args(); date.fromisoformat(m + "-01")
    except ValueError: return jsonify(error="ខែមិនត្រឹមត្រូវ"), 400
    data, detail = _monthly(m, dept)
    return send_file(ex.build_monthly_excel(data, detail), as_attachment=True, download_name=f"attendance_monthly_{m}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------- insights ----------
@api2.get("/admin/insights")
@staff_only
def insights():
    dept = scope_dept(current_user()); today = date.today()
    q = Attendance.query.filter_by(date=today).join(User, Attendance.user_id == User.id).filter(User.active == True)  # noqa: E712
    if dept is not None: q = q.filter(User.department == dept)
    here = []
    for a in q:
        since = a.check_in2 if (a.check_in2 and not a.check_out2) else (a.check_in if (a.check_in and not a.check_out and not a.check_in2) else None)
        if since:
            info = a.user.to_dict()
            here.append(dict(name=a.user.name, position=info["position"], photo=info["photo"], since=since.strftime("%H:%M")))
    s, e = period_range("monthly", today)
    per = {}
    for r in build_report(s, e, dept=dept):
        x = per.setdefault(r["user_id"], dict(name=r["name"], present=0, late=0, absent=0, leave=0))
        x[r["status"]] += 1
    lst = list(per.values())
    punctual = sorted([x for x in lst if x["present"] > 0], key=lambda x: (-x["present"], x["late"]))[:5]
    lates = sorted([x for x in lst if x["late"] > 0], key=lambda x: -x["late"])[:5]
    trend, ref = [], today.replace(day=1)
    months = []
    for _ in range(6):
        months.append(ref); ref = (ref - timedelta(days=1)).replace(day=1)
    for ms in reversed(months):
        _, me_ = period_range("monthly", ms)
        c = {"came": 0, "absent": 0}
        for r in build_report(ms, me_, dept=dept):
            if r["status"] in ("present", "late"): c["came"] += 1
            elif r["status"] == "absent": c["absent"] += 1
        tot = c["came"] + c["absent"]
        trend.append(dict(month=ms.strftime("%Y-%m"), rate=round(100 * c["came"] / tot) if tot else None))
    return jsonify(in_office=here, punctual=[dict(name=x["name"], count=x["present"]) for x in punctual],
                   late=[dict(name=x["name"], count=x["late"]) for x in lates], trend=trend)


# ---------- notifications + Telegram linking ----------
@api2.get("/notifications")
@jwt_required()
def notif_list():
    u = current_user()
    q = Notification.query.filter_by(user_id=u.id).order_by(Notification.id.desc())
    return jsonify(unread=q.filter_by(read=False).count(),
                   items=[dict(id=n.id, title=n.title, body=n.body, read=n.read,
                               when=n.created_at.strftime("%Y-%m-%d %H:%M")) for n in q.limit(30)])


@api2.post("/notifications/read")
@jwt_required()
def notif_read():
    Notification.query.filter_by(user_id=current_user().id, read=False).update({"read": True})
    db.session.commit()
    return jsonify(ok=True)


@api2.post("/profile/telegram-code")
@jwt_required()
def tg_code():
    u = current_user()
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        return jsonify(error="Admin មិនទាន់កំណត់ Telegram Bot"), 400
    u.tg_code = "".join(random.choices(string.digits, k=6)); u.tg_code_exp = datetime.now() + timedelta(minutes=10)
    db.session.commit()
    return jsonify(code=u.tg_code, bot=tg.bot_username(), minutes=10)


@api2.delete("/profile/telegram")
@jwt_required()
def tg_unlink():
    u = current_user(); u.telegram_chat_id = None; u.tg_code = None; db.session.commit()
    return jsonify(ok=True)


# ---------- Excel import ----------
IMPORT_COLS = ["employee_code", "name", "gender", "dob", "position", "department", "password"]


@api2.get("/admin/users/import-template")
@admin_only
def import_template():
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "Employees"
    ws.append(IMPORT_COLS)
    ws.append(["E001", "សុខ ចាន់ថា", "ប្រុស", "1995-05-20", "គ្រូបង្រៀន", "ផ្នែកគណិតវិទ្យា", ""])
    for c in "ABCDEFG": ws.column_dimensions[c].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="employees_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@api2.post("/admin/users/import")
@admin_only
def import_users():
    from openpyxl import load_workbook
    f = request.files.get("file")
    if not f: return jsonify(error="សូមជ្រើសរើសឯកសារ Excel"), 400
    try: ws = load_workbook(f, read_only=True, data_only=True).active
    except Exception: return jsonify(error="មិនអាចអានឯកសារ (ត្រូវជា .xlsx)"), 400
    created, skipped = [], []
    for n, row in enumerate(ws.iter_rows(min_row=2, max_col=7, values_only=True), start=2):
        if n > 501: skipped.append(dict(row=n, code="", reason="លើស ៥០០ ជួរ")); break
        code, name, g, dob, pos, dept, pw = [(str(c).strip() if c is not None else "") for c in (list(row) + [None] * 7)[:7]]
        if not code and not name: continue
        if not code or not name: skipped.append(dict(row=n, code=code, reason="ខ្វះលេខកូដ ឬឈ្មោះ")); continue
        if User.query.filter_by(employee_code=code).first(): skipped.append(dict(row=n, code=code, reason="លេខកូដមានរួចហើយ")); continue
        gender = {"ប្រុស": "M", "m": "M", "male": "M", "ស្រី": "F", "f": "F", "female": "F"}.get(g.lower())
        bd = None
        if dob:
            try: bd = (dob if isinstance(row[3], date) else date.fromisoformat(dob[:10]))
            except ValueError: skipped.append(dict(row=n, code=code, reason="ថ្ងៃកំណើតមិនត្រឹមត្រូវ (YYYY-MM-DD)")); continue
            if isinstance(bd, datetime): bd = bd.date()
        pw = pw if len(pw) >= 6 else "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        db.session.add(User(employee_code=code, name=name, role="employee", gender=gender, dob=bd, position=pos or None,
                            department=dept or None, password_hash=generate_password_hash(pw)))
        created.append(dict(code=code, name=name, password=pw))
    db.session.commit()
    return jsonify(created=created, skipped=skipped)


# ---------- background jobs ----------
def reminders_job():
    """Remind people who scanned in but forgot to scan out (30 min after the scheduled out time)."""
    now = datetime.now(); today = now.date()
    if not is_workday(today): return
    sc = sched()
    for out_key, fin, fout, label in (("out1", "check_in", "check_out", "ចេញព្រឹក"), ("out2", "check_in2", "check_out2", "ចេញរសៀល")):
        trig = datetime.combine(today, sc[out_key]) + timedelta(minutes=30)
        if not trig <= now < trig + timedelta(minutes=90): continue
        for a in Attendance.query.filter_by(date=today):
            if getattr(a, fin) and not getattr(a, fout) and a.user.active:
                notify(a.user, f"⏰ ភ្លេចស្កេន{label}", f"អ្នកមិនទាន់ស្កេន{label}ថ្ងៃនេះទេ។ សូមទាក់ទង Admin បើភ្លេច។", key=f"fo:{today}:{out_key}")


def summary_job():
    """Daily summary to the admin Telegram group (+ weekly totals on the last working day of the week)."""
    now = datetime.now(); today = now.date()
    if setting("daily_summary") != "1" or not is_workday(today) or setting("last_summary", "") == today.isoformat(): return
    trig = datetime.combine(today, sched()["out2"]) + timedelta(minutes=60)
    if not trig <= now < trig + timedelta(hours=3): return
    rows = build_report(today, today); s = summarize(rows)
    absent = [r["name"] for r in rows if r["status"] == "absent"]
    text = (f"📊 <b>សង្ខេបវត្តមាន {today}</b>\n✅ មកធ្វើការ {s['came']} (ក្នុងនោះយឺត {s['late']})\n"
            f"❌ អវត្តមាន {s['absent']}   📝 ច្បាប់ {s['leave']}")
    if absent: text += "\nអវត្តមាន: " + ", ".join(absent[:15])
    if today.isoweekday() == max(work_weekdays() or {5}):
        ws = summarize(build_report(today - timedelta(days=today.weekday()), today))
        text += f"\n\n🗓 <b>សរុបសប្ដាហ៍នេះ</b>\nមកធ្វើការ {ws['came']} · យឺត {ws['late']} · អវត្តមាន {ws['absent']} · ច្បាប់ {ws['leave']}"
    tg.send(text); set_setting("last_summary", today.isoformat())


def _remember_chat(chat):
    if chat.get("type") not in ("group", "supergroup", "channel"): return
    lst = json.loads(setting("tg_chats", "[]") or "[]")
    e = dict(id=str(chat["id"]), title=chat.get("title") or "", type=chat["type"])
    set_setting("tg_chats", json.dumps([e] + [x for x in lst if x["id"] != e["id"]][:9], ensure_ascii=False))


def poll_telegram():
    """Let employees link their private Telegram chat: they send  /link 123456  to the bot."""
    if not os.getenv("TELEGRAM_BOT_TOKEN"): return
    off = int(setting("tg_offset", "0") or 0)
    r = tg.api("getUpdates", offset=off, timeout=0, allowed_updates=["message", "my_chat_member"])
    if not r or not r.get("ok") or not r["result"]: return
    for up in r["result"]:
        off = up["update_id"] + 1
        m = up.get("message") or {}
        chat = m.get("chat") or (up.get("my_chat_member") or {}).get("chat") or {}
        _remember_chat(chat)                       # groups the bot has seen → shown in Settings so the admin can pick one
        if chat.get("type") != "private" or not m: continue
        parts, cid = (m.get("text") or "").split(), str(chat["id"])
        if parts and parts[0].startswith("/link"):
            u = User.query.filter(User.tg_code == parts[1], User.tg_code_exp > datetime.now()).first() if len(parts) > 1 else None
            if u:
                u.telegram_chat_id, u.tg_code = cid, None; db.session.commit()
                tg.send_to(cid, f"✅ ភ្ជាប់ជោគជ័យ! សួស្តី <b>{u.name}</b> — អ្នកនឹងទទួលការជូនដំណឹងនៅទីនេះ។")
            else:
                tg.send_to(cid, "❌ កូដមិនត្រឹមត្រូវ ឬផុតកំណត់។ សូមបង្កើតកូដថ្មីក្នុងទំព័រ Profile។")
        elif parts and parts[0].startswith("/unlink"):
            for u in User.query.filter_by(telegram_chat_id=cid): u.telegram_chat_id = None
            db.session.commit(); tg.send_to(cid, "បានផ្ដាច់ការភ្ជាប់។")
        else:
            tg.send_to(cid, "សួស្តី 👋 ដើម្បីទទួលការជូនដំណឹង សូមបើក Profile ក្នុងកម្មវិធី → \"ភ្ជាប់ Telegram\" ហើយផ្ញើ /link ជាមួយកូដ ៦ ខ្ទង់។")
    set_setting("tg_offset", str(off))


@api2.get("/health")
def health():
    """Used by uptime monitors / deploy checks."""
    try:
        db.session.execute(db.text("SELECT 1")); return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)[:120]), 500


# ---------- Telegram group picker ----------
@api2.get("/admin/telegram/chats")
@admin_only
def tg_chats():
    return jsonify(chats=json.loads(setting("tg_chats", "[]") or "[]"), current=tg.chat_id())


@api2.put("/admin/telegram/chat")
@admin_only
def tg_set_chat():
    cid = str((request.get_json() or {}).get("chat_id", "")).strip()
    if cid and not re.fullmatch(r"-?\d{5,20}|@[A-Za-z0-9_]{4,}", cid):
        return jsonify(error="Chat ID ត្រូវជាលេខ (ឧ. -1001234567890)"), 400
    set_setting("telegram_chat_id", cid); tg.configure(cid)
    return jsonify(ok=True, current=tg.chat_id())


# ---------- station voice announcements + admin test tools ----------
def voice_title(u):
    return {"M": "លោកគ្រូ", "F": "អ្នកគ្រូ"}.get(u.gender, "លោកគ្រូ/អ្នកគ្រូ")


AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".webm", ".oga"}


def _voice_dir():
    d = os.path.join(current_app.config["UPLOAD_DIR"], "voice")
    os.makedirs(d, exist_ok=True)
    return d


def voice_file(stem):
    """URL of an uploaded clip (voice/<stem>.<ext>) or None. ?v=mtime busts the browser cache after a re-upload."""
    d = _voice_dir()
    for fn in os.listdir(d):
        if os.path.splitext(fn)[0] == stem:
            return f"/api/uploads/voice/{fn}?v={int(os.path.getmtime(os.path.join(d, fn)))}"
    return None


def voice_parts(u, slot, ts):
    """Sequence the station plays. tts mode = one spoken sentence. file mode = recorded clips (employee name clip,
    then the shared 'attendance succeeded' clip), falling back to TTS for whichever clip is missing."""
    if setting("voice_mode") != "file":
        return [dict(type="tts", text=voice_text(u, slot, ts))]
    out = slot in ("out1", "out2")
    name_clip, ok_clip = voice_file(f"user_{u.id}"), voice_file("global_out" if out else "global")
    return [dict(type="audio", url=name_clip) if name_clip else dict(type="tts", text=f"{voice_title(u)} ឈ្មោះ {u.name}"),
            dict(type="audio", url=ok_clip) if ok_clip else dict(type="tts", text="ស្កេនចេញបានជោគជ័យ" if out else "ចុះវត្តមានបានជោគជ័យ")]


def dup_parts(u):
    if setting("voice_mode") != "file":
        return [dict(type="tts", text=setting("voice_template_dup").format_map(_Safe(title=voice_title(u), name=u.name, label="", time="")))]
    name_clip, dup_clip = voice_file(f"user_{u.id}"), voice_file("global_dup")
    return [dict(type="audio", url=name_clip) if name_clip else dict(type="tts", text=f"{voice_title(u)} ឈ្មោះ {u.name}"),
            dict(type="audio", url=dup_clip) if dup_clip else dict(type="tts", text="បានស្កេនរួចហើយ")]


class _Safe(dict):
    def __missing__(self, k): return ""


def voice_text(u, slot, ts):
    """Spoken sentence for one scan. Template (editable in Settings) placeholders: {title} {name} {label} {time}."""
    tpl = setting("voice_template_out" if slot in ("out1", "out2") else "voice_template")
    try:
        return tpl.format(title=voice_title(u), name=u.name, label=LABEL.get(slot, ""), time=ts.strftime("%H:%M"))
    except (KeyError, IndexError, ValueError):
        return f"{voice_title(u)} ឈ្មោះ {u.name} " + ("ស្កេនចេញបានជោគជ័យ" if slot in ("out1", "out2") else "ចុះវត្តមានបានជោគជ័យ")


@api2.get("/admin/station/recent")
@admin_only
def station_recent():
    """Polled by the station (monitor) page. after=-1 → just return the latest ids (nothing is spoken on page load).
    `after` follows successful scans, `after_dup` follows refused 'already scanned' attempts."""
    after, loc = request.args.get("after", -1, type=int), request.args.get("loc", type=int)
    after_dup = request.args.get("after_dup", -1, type=int)
    q, qd = ScanLog.query, ScanEvent.query
    if loc: q, qd = q.filter(ScanLog.location_id == loc), qd.filter(ScanEvent.location_id == loc)
    cfg = dict(enabled=setting("voice_enabled") == "1", rate=float(setting("voice_rate") or 0.9))
    newest = lambda qq, M: (qq.order_by(M.id.desc()).first() or M(id=0)).id or 0
    if after < 0 or after_dup < 0:
        return jsonify(last_id=newest(q, ScanLog), last_dup_id=newest(qd, ScanEvent), scans=[], dups=[], **cfg)
    fresh = datetime.now() - timedelta(minutes=2)
    rows = q.filter(ScanLog.id > after, ScanLog.ts >= fresh).order_by(ScanLog.id).limit(10).all()
    dups = qd.filter(ScanEvent.id > after_dup, ScanEvent.ts >= fresh).order_by(ScanEvent.id).limit(10).all()
    # jump past stale rows so they are never announced late
    last_id = max([after] + [r.id for r in rows]) if rows else max(after, newest(q, ScanLog))
    last_dup = max([after_dup] + [r.id for r in dups]) if dups else max(after_dup, newest(qd, ScanEvent))
    return jsonify(last_id=last_id, last_dup_id=last_dup, **cfg,
                   scans=[dict(id=r.id, name=r.user.name, text=voice_text(r.user, r.slot, r.ts),
                               parts=voice_parts(r.user, r.slot, r.ts)) for r in rows],
                   dups=[dict(id=r.id, name=r.user.name, parts=dup_parts(r.user)) for r in dups])


@api2.post("/admin/test/clear")
@admin_only
def test_clear_today():
    """Admin testing helper: wipe TODAY's attendance + scan logs of one employee so they can scan again."""
    d, admin = request.get_json() or {}, current_user()
    u = db.session.get(User, d.get("user_id") or 0)
    if not u or u.role not in STAFF: return jsonify(error="រកមិនឃើញបុគ្គលិក"), 404
    today = date.today()
    a = Attendance.query.filter_by(user_id=u.id, date=today).first()
    before = _fmt(a)
    if a: db.session.delete(a)
    n = ScanLog.query.filter(ScanLog.user_id == u.id, ScanLog.ts >= datetime.combine(today, datetime.min.time())).delete()
    db.session.add(AuditLog(admin_id=admin.id, user_id=u.id, date=today, action="test_clear",
                            detail=f"CLS សាកល្បង: {before} → លុប (scan log {n})"))
    db.session.commit()
    return jsonify(ok=True, scans_removed=n, had_record=bool(a))


@api2.post("/admin/attendance/reset")
@admin_only
def att_reset():
    """Let an employee scan again: wipe the attendance row + scan logs of one employee for one day (reason required, audited)."""
    d, admin = request.get_json() or {}, current_user()
    reason = (d.get("reason") or "").strip()
    u = db.session.get(User, d.get("user_id") or 0)
    try: day = date.fromisoformat(d.get("date") or date.today().isoformat())
    except ValueError: return jsonify(error="ទិន្នន័យមិនត្រឹមត្រូវ"), 400
    if not u or u.role not in STAFF: return jsonify(error="រកមិនឃើញបុគ្គលិក"), 404
    if day > date.today(): return jsonify(error="មិនអាចជ្រើសថ្ងៃអនាគត"), 400
    if len(reason) < 3: return jsonify(error="សូមបញ្ចូលមូលហេតុ"), 400
    a = Attendance.query.filter_by(user_id=u.id, date=day).first()
    before = _fmt(a)
    if a: db.session.delete(a)
    start = datetime.combine(day, datetime.min.time())
    n = ScanLog.query.filter(ScanLog.user_id == u.id, ScanLog.ts >= start, ScanLog.ts < start + timedelta(days=1)).delete()
    db.session.add(AuditLog(admin_id=admin.id, user_id=u.id, date=day, action="reset",
                            detail=f"អនុញ្ញាតស្កេនឡើងវិញ: {before} → លុប (scan log {n}) | {reason}"))
    db.session.commit()
    notify(u, "🔄 Admin បានកំណត់ឲ្យស្កេនឡើងវិញ", f"{day}: អ្នកអាចស្កេនវត្តមានម្ដងទៀត\nមូលហេតុ: {reason}")
    return jsonify(ok=True, scans_removed=n, had_record=bool(a))


# ---------- upload / record real voice clips ----------
def _save_voice(stem, file):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in AUDIO_EXT:
        raise ValueError("ប្រភេទសំឡេងមិនត្រឹមត្រូវ (ប្រើ MP3 / WAV / OGG / M4A / WEBM)")
    d = _voice_dir()
    for fn in os.listdir(d):                      # replace the previous clip, whatever its extension
        if os.path.splitext(fn)[0] == stem: os.remove(os.path.join(d, fn))
    file.save(os.path.join(d, stem + ext))


def _del_voice(stem):
    d = _voice_dir()
    for fn in os.listdir(d):
        if os.path.splitext(fn)[0] == stem: os.remove(os.path.join(d, fn))


@api2.get("/admin/voice")
@admin_only
def voice_list():
    users = User.query.filter(User.role.in_(STAFF), User.active == True).order_by(User.name).all()  # noqa: E712
    return jsonify(global_url=voice_file("global"), global_out_url=voice_file("global_out"), global_dup_url=voice_file("global_dup"),
                   users=[dict(id=u.id, name=u.name, code=u.employee_code, url=voice_file(f"user_{u.id}")) for u in users])


@api2.post("/admin/voice/global", defaults={"kind": "global"})
@api2.post("/admin/voice/global_out", defaults={"kind": "global_out"})
@api2.post("/admin/voice/global_dup", defaults={"kind": "global_dup"})
@admin_only
def voice_global_up(kind):
    f = request.files.get("file")
    if not f or not f.filename: return jsonify(error="សូមជ្រើសឯកសារសំឡេង"), 400
    try: _save_voice(kind, f)
    except ValueError as e: return jsonify(error=str(e)), 400
    return jsonify(url=voice_file(kind))


@api2.delete("/admin/voice/global", defaults={"kind": "global"})
@api2.delete("/admin/voice/global_out", defaults={"kind": "global_out"})
@api2.delete("/admin/voice/global_dup", defaults={"kind": "global_dup"})
@admin_only
def voice_global_del(kind):
    _del_voice(kind); return jsonify(ok=True)


@api2.post("/admin/voice/user/<int:uid>")
@admin_only
def voice_user_up(uid):
    u = db.session.get(User, uid)
    if not u or u.role not in STAFF: return jsonify(error="រកមិនឃើញបុគ្គលិក"), 404
    f = request.files.get("file")
    if not f or not f.filename: return jsonify(error="សូមជ្រើសឯកសារសំឡេង"), 400
    try: _save_voice(f"user_{uid}", f)
    except ValueError as e: return jsonify(error=str(e)), 400
    return jsonify(url=voice_file(f"user_{uid}"))


@api2.delete("/admin/voice/user/<int:uid>")
@admin_only
def voice_user_del(uid):
    _del_voice(f"user_{uid}"); return jsonify(ok=True)
