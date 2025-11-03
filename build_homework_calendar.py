import os, hashlib, datetime
from pathlib import Path
from argofamiglia import ArgoFamiglia  # pip install argofamiglia

# --- Configura qui ---
DAYS_AHEAD = 14                 # quanti giorni in avanti
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"

# Orario lezioni per materia (opzionale). Se assente -> evento "tutto il giorno".
# Giorni: "Lun","Mar","Mer","Gio","Ven","Sab","Dom"
TIMETABLE = {
    # "Matematica": {"Lun": ("10:00","11:00"), "Gio": ("09:00","10:00")},
}
WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

# --- Utility ---
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

def fetch_day(session, d: datetime.date):
    """
    Chiama l’endpoint come nel tuo snippet e pesca SOLO il giorno d.
    Prova entrambe le chiavi: 'YYYY-MM-DD' e 'DD/MM/YYYY'.
    """
    try:
        data = session.getCompitiByDate() or {}
    except Exception:
        return None
    k1 = d.strftime("%Y-%m-%d")
    k2 = d.strftime("%d/%m/%Y")
    return data.get(k1) or data.get(k2)

def main():
    session = ArgoFamiglia(
        os.environ["ARGO_SCHOOL_CODE"],
        os.environ["ARGO_USERNAME"],
        os.environ["ARGO_PASSWORD"],
    )

    today = datetime.date.today()
    events = []

    # Itera giorno per giorno come richiesto
    for delta in range(DAYS_AHEAD + 1):
        d = today + datetime.timedelta(days=delta)
        compiti = fetch_day(session, d)
        if not compiti:
            continue

        materie = compiti.get("materie") or []
        testi   = compiti.get("compiti") or []
        for subject, text in zip(materie, testi):
            if subject or text:
                events.append(ics_event(d, str(subject), str(text)))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

if __name__ == "__main__":
    main()
