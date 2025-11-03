import os, hashlib, datetime
from pathlib import Path
from argofamiglia import ArgoFamiglia  # pip install argofamiglia

DAYS_AHEAD = 14
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"

TIMETABLE = {}  # opzionale: {"Matematica":{"Lun":("08:00","09:00")}, ...}
WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

def esc(s: str) -> str:
    return s.replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")

def uid_for(date_str, subject, text):
    raw = f"{date_str}|{subject}|{text}".encode("utf-8")
    import hashlib
    return hashlib.sha256(raw).hexdigest()[:24] + "@compiti-argo"

def dt_d(date):  return date.strftime("%Y%m%d")
def dt_dt(date, hhmm):  return date.strftime("%Y%m%d") + "T" + hhmm.replace(":","") + "00"

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
    subject = subject.strip() if subject else ""
    text = text.strip() if text else ""
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
    # accetta 'YYYY-MM-DD' o 'DD/MM/YYYY'
    k = k.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(k, fmt).date()
        except ValueError:
            continue
    return None

def merge_day(data, date_obj, events):
    if not data: 
        return
    materie = data.get("materie", []) or []
    testi   = data.get("compiti", []) or []
    for subject, text in zip(materie, testi):
        if subject or text:
            events.append(ics_event(date_obj, str(subject), str(text)))

def main():
    session = ArgoFamiglia(
        os.environ["ARGO_SCHOOL_CODE"],
        os.environ["ARGO_USERNAME"],
        os.environ["ARGO_PASSWORD"],
    )

    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=DAYS_AHEAD)
    events = []

    # --- 1) tentativo bulk con intervallo ---
    all_data = {}
    try:
        all_data = session.getCompitiByDate(
            start_date=today.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        ) or {}
    except TypeError:
        try:
            all_data = session.getCompitiByDate() or {}
        except Exception:
            all_data = {}

    # usa tutto ciò che ha date parsabili nell'intervallo
    covered = set()
    for k, v in (all_data.items() if isinstance(all_data, dict) else []):
        d = parse_date_key(k)
        if d and today <= d <= end_date:
            merge_day(v, d, events)
            covered.add(d)

    # --- 2) integrazione “per-giorno” se mancano giorni ---
    for delta in range((end_date - today).days + 1):
        d = today + datetime.timedelta(days=delta)
        if d in covered:
            continue
        # fetch focalizzato
        try:
            daily = session.getCompitiByDate()  # alcune impl. ignorano parametri, ma rientriamo col dict
        except Exception:
            daily = None
        if isinstance(daily, dict):
            # prova con entrambe le chiavi
            hit = daily.get(d.strftime("%Y-%m-%d")) or daily.get(d.strftime("%d/%m/%Y"))
            merge_day(hit, d, events)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

if __name__ == "__main__":
    main()
