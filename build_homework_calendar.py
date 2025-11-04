import os, hashlib, datetime, time
from pathlib import Path
from argofamiglia import ArgoFamiglia  # pip install argofamiglia

# ---- Config ----
DAYS_AHEAD = 21
CAL_NAME = "Compiti"
OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "compiti.ics"
WEEKDAY_IT = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]

# ---- Utils ----
def esc(s: str) -> str:
    return s.replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")

def uid_for(date_str, subject, text):
    raw = f"{date_str}|{subject}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24] + "@compiti-argo"

def dt_d(date):  return date.strftime("%Y%m%d")

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
    summary = esc(f"{subject} — Compiti") if subject else "Compiti"
    description = esc(text)
    start = dt_d(date_obj)
    end   = dt_d(date_obj + datetime.timedelta(days=1))  # all-day, DTEND esclusivo
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

# ---- Fetch helpers ----
def safe_get_compiti(session, **kwargs):
    """Prova con intervallo, fallback a default; mai solleva eccezioni."""
    try:
        return session.getCompitiByDate(**kwargs) or {}
    except TypeError:
        try:
            return session.getCompitiByDate() or {}
        except Exception:
            return {}
    except Exception:
        return {}

def extract_day_from_dict(data: dict, d: datetime.date):
    """Ritorna dict {'materie':[], 'compiti':[]} per il giorno d, se presente."""
    if not isinstance(data, dict):
        return None
    k1 = str(d)                        # 'YYYY-MM-DD'
    k2 = d.strftime("%Y-%m-%d")
    k3 = d.strftime("%d/%m/%Y")
    return data.get(k1) or data.get(k2) or data.get(k3)

def fetch_day_with_retry(session, d: datetime.date, retries=3, sleep_s=0.8):
    """Chiama getCompitiByDate più volte, indicizzato per giorno."""
    for _ in range(retries):
        try:
            data = session.getCompitiByDate() or {}
            hit = extract_day_from_dict(data, d)
            if hit:
                return hit
        except Exception:
            pass
        time.sleep(sleep_s)
    return None

# ---- Main ----
def main():
    session = ArgoFamiglia(
        os.environ["ARGO_SCHOOL_CODE"],
        os.environ["ARGO_USERNAME"],
        os.environ["ARGO_PASSWORD"],
    )

    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=DAYS_AHEAD)

    # 1) Bulk su intervallo
    bulk = safe_get_compiti(
        session,
        start_date=today.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    # 2) Costruisci eventi
    events = []
    per_day_counts = {}  # solo conteggi per log

    for delta in range((end_date - today).days + 1):
        d = today + datetime.timedelta(days=delta)
        compiti = extract_day_from_dict(bulk, d)
        if not compiti:
            compiti = fetch_day_with_retry(session, d)

        if not isinstance(compiti, dict):
            continue

        materie = compiti.get("materie") or []
        testi   = compiti.get("compiti") or []
        n = 0
        for subject, text in zip(materie, testi):
            if subject or text:
                events.append(ics_event(d, str(subject), str(text)))
                n += 1
        if n:
            per_day_counts[str(d)] = n

    # 3) Scrivi ICS
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write(ics_header())
        for ev in events:
            f.write(ev)
        f.write("END:VCALENDAR\r\n")

    # 4) Log sintetico per Actions
    print("VEVENT count:", len(events))
    if per_day_counts:
        print("Copertura per data:", per_day_counts)
    else:
        print("Nessun compito trovato nell'intervallo.")

if __name__ == "__main__":
    main()
