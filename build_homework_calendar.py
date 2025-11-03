import os, hashlib, datetime
from pathlib import Path
from argofamiglia import ArgoFamiglia  # pip install argofamiglia

# --- Config ---
DAYS_AHEAD = 14                 # orizzonte in giorni
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"

# Orario lezioni per materia (opzionale). Se assente -> evento "tutto il giorno".
# Giorni: "Lun","Mar","Mer","Gio","Ven","Sab","Dom"
TIMETABLE = {
    # "Matematica": {"Lun": ("10:00","11:00"), "Gio": ("09:00","10:00")},
    # "Italiano":   {"Mar": ("08:00","09:00")}
}
WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

# --- Util ---
def uid_for(date_str, subject, text):
    raw = f"{date_str}|{subject}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24] + "@compiti-argo"

def dt_d(date):
    return date.strftime("%Y%m%d")

def dt_dt(date, hhmm):
    return date.strftime("%Y%m%d") + "T" + hhmm.replace(":", "") + "00"

def ics_header():
    return (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//Compiti Argo//Devis//IT\r\n"
        "VERSION:2.0\r\n"
        "CALSCALE:GREGORIAN\r\n"
        f"X-WR-CALNAME:{CAL_NAME}\r\n"
        "METHOD:PUBLISH\r\n"
    )

def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def ics_event(date_obj, subject, text):
    date_str = date_obj.strftime("%Y-%m-%d")
    uid = uid_for(date_str, subject, text)
    weekday = WEEKDAY_IT[date_obj.weekday()]
    times = TIMETABLE.get(subject, {}).get(weekday)

    summary = esc(f"{subject} — Compiti") if subject else "Compiti"
    description = esc(text) if text else ""

    if times:
        start = dt_dt(date_obj, times[0])
        end   = dt_dt(date_obj, times[1])
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
        start = dt_d(date_obj)
        end = dt_d(date_obj + datetime.timedelta(days=1))  # DTEND esclusivo
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

def main():
    # Credenziali dai Secrets di GitHub
    school = os.environ["ARGO_SCHOOL_CODE"]
    user   = os.environ["ARGO_USERNAME"]
    pwd    = os.environ["ARGO_PASSWORD"]

    session = ArgoFamiglia(school, user, pwd)

    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=DAYS_AHEAD)
    all_events = []

    # Scarica una volta sola. Alcune versioni accettano start/end, altre no.
    try:
        all_data = session.getCompitiByDate(
            start_date=today.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
    except TypeError:
        all_data = session.getCompitiByDate()

    # Debug opzionale:
    # print("Date compiti:", ", ".join(sorted(all_data.keys())))

    for date_str, compiti in sorted(all_data.items()):
        try:
            d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if not (today <= d <= end_date):
            continue

        materie = compiti.get("materie", []) or []
        testi   = compiti.get("compiti", []) or []

        for subject, text in zip(materie, testi):
            subject = str(subject).strip()
            text    = str(text).strip()
            if subject or text:
                all_events.append(ics_event(d, subject, text))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in all_events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

if __name__ == "__main__":
    main()
