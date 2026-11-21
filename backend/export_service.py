import os, re, json
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

HEADERS = ["កាលបរិច្ឆេទ", "លេខកូដ", "ឈ្មោះ", "ចូលព្រឹក", "ចេញព្រឹក", "ចូលរសៀល", "ចេញរសៀល", "ស្ថានភាព"]
STATUS_KH = {"present": "មកធ្វើការ", "late": "មកធ្វើការ (យឺត)", "absent": "អវត្តមាន", "leave": "ច្បាប់"}


def _data(rows):
    return [[r["date"], r["code"], r["name"], r["in1"] or "", r["out1"] or "", r["in2"] or "", r["out2"] or "",
             STATUS_KH.get(r["status"], r["status"])] for r in rows]


def build_excel(rows, title):
    wb = Workbook(); ws = wb.active; ws.title = "Attendance"
    ws.append([title]); ws["A1"].font = Font(bold=True, size=14, color="003366")
    ws.append(HEADERS)
    for c in ws[2]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="003366")
        c.alignment = Alignment(horizontal="center")
    for r in _data(rows):
        ws.append(r)
    for col, w in zip("ABCDEFGH", (14, 12, 28, 11, 11, 11, 11, 14)):
        ws.column_dimensions[col].width = w
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return buf


KM_MONTH = ['មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា', 'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ']


def _style_header(row):
    for c in row:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="003366")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def build_monthly_excel(d, detail):
    """Monthly report as .xlsx: sheet 1 = per-employee summary (same as the printed report), sheet 2 = day-by-day detail."""
    from openpyxl.styles import Border, Side
    thin = Side(style="thin", color="999999"); box = Border(left=thin, right=thin, top=thin, bottom=thin)
    wb = Workbook(); ws = wb.active; ws.title = "សង្ខេបប្រចាំខែ"
    y, mo = d["month"].split("-")
    ws.append([d["org"]]); ws.append([f"របាយការណ៍វត្តមានបុគ្គលិក ខែ{KM_MONTH[int(mo) - 1]} ឆ្នាំ {y}"])
    ws.append([(f"ផ្នែក៖ {d['dept']} · " if d["dept"] else "") + f"ចំនួនថ្ងៃធ្វើការក្នុងខែ៖ {d['workdays']} ថ្ងៃ"])
    for r in (1, 2): ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=9)
    ws["A1"].font = Font(bold=True, size=13, color="003366"); ws["A2"].font = Font(bold=True, size=14)
    for r in (1, 2, 3): ws.cell(r, 1).alignment = Alignment(horizontal="center")
    ws.append([])
    ws.append(["ល.រ", "លេខកូដ", "ឈ្មោះ", "តួនាទី", "មកធ្វើការ", "ក្នុងនោះយឺត", "អវត្តមាន", "ច្បាប់", "ម៉ោងសរុប"])
    _style_header(ws[5]); hdr = 5
    for i, r in enumerate(d["rows"], 1):
        ws.append([i, r["code"], r["name"], r.get("position") or "-", r["came"], r["late"], r["absent"], r["leave"], r["hours"]])
    t = d["totals"]
    ws.append(["សរុប", "", "", "", t["came"], t["late"], t["absent"], t["leave"], t["hours"]])
    ws.merge_cells(start_row=ws.max_row, start_column=1, end_row=ws.max_row, end_column=4)
    for c in ws[ws.max_row]: c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="EEF2F7")
    for row in ws.iter_rows(min_row=hdr, max_row=ws.max_row):
        for c in row:
            c.border = box
            if c.column in (1, 2, 5, 6, 7, 8, 9): c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=c.row == hdr)
    for col, w in zip("ABCDEFGHI", (7, 12, 28, 22, 12, 14, 11, 9, 12)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(hdr + 1, 1)

    w2 = wb.create_sheet("លម្អិតប្រចាំថ្ងៃ")
    w2.append(HEADERS); _style_header(w2[1])
    for r in _data(detail): w2.append(r)
    for col, w in zip("ABCDEFGH", (14, 12, 28, 11, 11, 11, 11, 18)):
        w2.column_dimensions[col].width = w
    w2.freeze_panes = "A2"; w2.auto_filter.ref = w2.dimensions
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return buf


def _creds_path():
    p = os.getenv("GOOGLE_CREDS", "credentials.json")
    return p if os.path.isabs(p) else os.path.join(os.path.dirname(os.path.abspath(__file__)), p)


def extract_sheet_id(v):
    m = re.search(r"/d/([\w-]+)", v or "")
    return m.group(1) if m else (v or "").strip()


def service_email():
    try:
        with open(_creds_path(), encoding="utf8") as f:
            return json.load(f).get("client_email")
    except Exception:
        return None


def push_gsheet(rows, title, sheet_id=None):
    import gspread
    from gspread.exceptions import SpreadsheetNotFound, APIError
    sid = extract_sheet_id(sheet_id or os.getenv("GSHEET_ID"))
    if not sid:
        raise ValueError("មិនទាន់កំណត់ Google Sheet — សូមចូលទំព័រ កំណត់ ហើយបញ្ចូល link ឬ ID")
    if not os.path.exists(_creds_path()):
        raise ValueError("រកមិនឃើញឯកសារ credentials.json ក្នុង folder backend")
    email = service_email()
    try:
        gc = gspread.service_account(filename=_creds_path())
        sh = gc.open_by_key(sid)
        try:
            ws = sh.worksheet("Attendance")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet("Attendance", 2000, 10)
        ws.clear()
        ws.update(values=[[title], HEADERS] + _data(rows), range_name="A1")
        try:
            ws.update_index(0)  # make the Attendance tab the first tab
        except Exception:
            pass
    except SpreadsheetNotFound:
        raise ValueError(f"រក Sheet មិនឃើញ — សូម Share ឲ្យ {email} ជា Editor")
    except APIError as e:
        t = str(e)
        if "permission" in t.lower():
            raise ValueError(f"គ្មានសិទ្ធិ — សូម Share Sheet ឲ្យ {email} ជា Editor")
        raise ValueError("សូមបើក Google Sheets API និង Google Drive API ក្នុង Google Cloud។ " + t[:160])
    return f"{sh.url}#gid={ws.id}", len(rows)
