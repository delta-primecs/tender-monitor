"""
Diavgeia audit-tender monitor
------------------------------
Checks Diavgeia for new tender notices (type Δ.2.1) with CPV 79212200-5
and emails any that it hasn't seen before.

Designed to run on a schedule (e.g. GitHub Actions). The list of already-seen
tenders lives in seen_adas.json, which the workflow commits back to the repo
between runs so the memory survives.

Email credentials are read from environment variables (GitHub Actions Secrets):
  EMAIL_USER      -> the Gmail address that sends the alert
  EMAIL_PASSWORD  -> a Gmail *App Password* (NOT your normal password)
  EMAIL_TO        -> where the alert should be delivered
"""

import os
import json
import smtplib
from email.mime.text import MIMEText

import requests

# ── What to watch ──
BASE = "https://diavgeia.gov.gr/luminapi/opendata"
CPV = "79212200-5"                 # auditing services
DECISION_TYPE = "Δ.2.1"            # tender notice (ΠΕΡΙΛΗΨΗ ΔΙΑΚΗΡΥΞΗΣ / ΔΙΑΚΗΡΥΞΗ)
SEEN_FILE = "seen_adas.json"


def fetch_current(cpv, dtype, size=50):
    """Ask Diavgeia for the current matching tenders."""
    q = f'cpv:"{cpv}" AND decisionTypeUid:"{dtype}"'
    params = {"q": q, "size": size, "page": 0, "sort": "recent"}
    r = requests.get(f"{BASE}/search/advanced", params=params,
                     headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("decisions") or data.get("results") or []


def load_seen():
    """Return the set of ADAs we've already seen, or None on the very first run."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return None


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False)


def send_email(new_items):
    """Send one email listing all the new tenders."""
    user = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASSWORD"]
    to = os.environ["EMAIL_TO"]

    lines = [f"{len(new_items)} new audit tender(s) — CPV {CPV}:\n"]
    for d in new_items:
        ada = d.get("ada", "")
        subject = d.get("subject", "(no subject)")
        lines.append(f"* {subject}")
        lines.append(f"  https://diavgeia.gov.gr/doc/{ada}\n")
    body = "\n".join(lines)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"New audit tender(s): {len(new_items)}"
    msg["From"] = user
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.send_message(msg)


def main():
    current = fetch_current(CPV, DECISION_TYPE)
    current_by_ada = {d.get("ada"): d for d in current if d.get("ada")}

    seen = load_seen()

    # First ever run: remember everything currently there, but DON'T email a
    # big backlog of old tenders. We only alert on things published from now on.
    if seen is None:
        save_seen(set(current_by_ada))
        print(f"First run — seeded {len(current_by_ada)} existing tenders, no email sent.")
        return

    new_adas = [a for a in current_by_ada if a not in seen]
    print(f"Found {len(current_by_ada)} tenders, {len(new_adas)} new.")

    if new_adas:
        new_items = [current_by_ada[a] for a in new_adas]
        send_email(new_items)
        print(f"Emailed {len(new_items)} new tender(s).")

    seen.update(current_by_ada)
    save_seen(seen)


if __name__ == "__main__":
    main()
