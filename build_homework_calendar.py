import os, hashlib, datetime
from pathlib import Path
from argofamiglia import ArgoFamiglia  # pip install argofamiglia

DAYS_AHEAD = 14
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"

TIMETABLE = {}
WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

def esc(s: str) -> str:
    return s.replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")

def uid_for(date_str, subject, text):
    raw = f"{date_str}|{subject}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24] + "@compiti-argo"

def dt_d(date):  return date.strftime("%Y%m%d")
def dt_dt(date, hhmm):  return date.strftime("%Y%m%d") + "T" + hhmm.replace(":", "") + "00"

def ics_header():
    return (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//Compiti Argo//Devis//IT\r\n"
        "VERSION:2.0\r\n"
        "CALSCALE:GREGORIAN\r\n"
        f"X-WR-CALNAME:{CAL_NAME}\r\n"
        "METHOD:PUBLISH\r\n"
    )

def ics_event(date_obj, subject, text):
    subject = (subject or "").strip()
    text = (text or "").strip()
    uid = uid_for(date_obj.strftime("%Y-%m-%d"), subject, text)
    weekday = WEEKDAY_IT[date_obj.weekday()]
    times = TIMETABLE.get(subject, {}).get(weekday)
    summary = esc(f"{subject} — Compiti") if subject else "Compiti"
    description = esc(text)

    if times:
        start = dt_dt(date_obj, times[0]); end = dt_dt(date_obj, times[1])
        return (
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTSTART;TZID=Europe/Rome:{start}\r\n"
            f"DTEND;TZID=Europe/Rome:{end}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{description}\r\n"
            "END:VEVENT\r\n"
        )
    else:
        start = dt_d(date_obj); end = dt_d(date_obj + datetime.timedelta(days=1))
        return (
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTSTART;VALUE=DATE:{start}\r\n"
            f"DTEND;VALUE=DATE:{end}\r\n"
            f"SUMMARY:{summary}\r\n"
            f"DESCRIPTION:{description}\r\n"
            "END:VEVENT\r\n"
        )

def parse_date_key(k: str):
    k = (k or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(k, fmt).date()
        except ValueError:
            pass
    return None

def merge_day(data, date_obj, events):
    if not isinstance(data, dict):
        return
    materie = data.get("materie") or []
    testi   = data.get("compiti") or []
    for subject, text in zip(materie, testi):
        if subject or text:
            events.append(ics_event(date_obj, str(subject), str(text)))

def safe_get_compiti(session, **kwargs):
    try:
        return session.getCompitiByDate(**kwargs) or {}
    except TypeError:
        return session.getCompitiByDate() or {}
    except Exception:
        return {}

def main():
    session = ArgoFamiglia(
        os.environ["ARGO_SCHOOL_CODE"],
        os.environ["ARGO_USERNAME"],
        os.environ["ARGO_PASSWORD"],
    )

    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=DAYS_AHEAD)
    events = []

    # 1) Bulk
    all_data = safe_get_compiti(
        session,
        start_date=today.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    # Log sintetico per capire la forma senza dati sensibili:
    try:
        print("all_data type:", type(all_data).__name__)
        if isinstance(all_data, dict):
            sample_keys = list(all_data.keys())[:10]
            print("date keys sample:", sample_keys)
    except Exception:
        pass

    covered = set()
    if isinstance(all_data, dict):
        for k, v in all_data.items():
            d = parse_date_key(k)
            if d and today <= d <= end_date:
                merge_day(v, d, events)
                covered.add(d)

    # 2) Per-giorno per i buchi
    total_days = (end_date - today).days + 1
    for delta in range(total_days):
        d = today + datetime.timedelta(days=delta)
        if d in covered:
            continue
        daily = safe_get_compiti(session)
        if isinstance(daily, dict):
            hit = daily.get(d.strftime("%Y-%m-%d")) or daily.get(d.strftime("%d/%m/%Y"))
            merge_day(hit, d, events)

    # Scrivi ICS
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

    # Log finale minimale
    print("VEVENT count:", sum(1 for _ in events))
