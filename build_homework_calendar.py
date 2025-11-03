import os, hashlib, datetime
from pathlib import Path

# pip install argofamiglia
from argofamiglia import ArgoFamiglia

# --- Configurazione di base ---
DAYS_AHEAD = 14               # quanti giorni in avanti
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"

# Opzionale: mappatura materia → orario lezione (ora locale di Milano)
# Se non definita per una materia, evento "tutto il giorno".
# Formato: "Lun","Mar","Mer","Gio","Ven","Sab","Dom"
TIMETABLE = {
    # Esempi:
    # "Matematica": {"Lun": ("10:00","11:00"), "Gio": ("09:00","10:00")},
    # "Italiano":   {"Mar": ("08:00","09:00")}
}

WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

def uid_for(date_str, subject, text):
    raw = f"{date_str}|{subject}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24] + "@compiti-argo"

def dt(date, t=None):
    if t is None:
        return date.strftime("%Y%m%d")
    return date.strftime("%Y%m%d") + "T" + t.replace(":","") + "00"

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
    date_str = date_obj.strftime("%Y-%m-%d")
    uid = uid_for(date_str, subject, text)
    weekday = WEEKDAY_IT[date_obj.weekday()]
    times = TIMETABLE.get(subject, {}).get(weekday)

    # Escape minimale per ICS
    def esc(s): 
        return s.replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")

    summary = esc(f"{subject} — Compiti")
    description = esc(text)

    if times:
        start = dt(date_obj, times[0])
        end   = dt(date_obj, times[1])
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
        # Evento "tutto il giorno"
        start = dt(date_obj)
        # DTEND esclusivo: giorno successivo
        end = dt(date_obj + datetime.timedelta(days=1))
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
    school = os.environ["ARGO_SCHOOL_CODE"]
    user   = os.environ["ARGO_USERNAME"]
    pwd    = os.environ["ARGO_PASSWORD"]

    session = ArgoFamiglia(school, user, pwd)

    today = datetime.date.today()
    all_events = []

    # La libreria espone getCompitiByDate(); iteriamo giorno per giorno
    for delta in range(DAYS_AHEAD + 1):
        d = today + datetime.timedelta(days=delta)
        key = d.strftime("%Y-%m-%d")
        try:
            compiti = session.getCompitiByDate().get(key)
        except Exception:
            compiti = None

        if not compiti:
            continue

        # Struttura attesa: compiti["materie"], compiti["compiti"]
        materie = compiti.get("materie", [])
        testi   = compiti.get("compiti", [])
        n = min(len(materie), len(testi))
        for i in range(n):
            subject = str(materie[i]).strip()
            text    = str(testi[i]).strip()
            all_events.append(ics_event(d, subject, text))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in all_events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

if __name__ == "__main__":
    main()
