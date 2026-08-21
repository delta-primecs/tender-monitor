"""
FOUNDATION — contract ingester (git-scraping pattern)
=====================================================
Maintains a persistent store of ΚΗΜΔΗΣ contracts so the system has MEMORY:
it knows what it saw before, so it can tell you what CHANGED.

Files it maintains (plain text, versioned by Git = free history + backup):
    data/contracts.jsonl   one JSON object per contract, sorted by ΑΔΑΜ
    data/changes.jsonl     append-only log of events (NEW / RENEWAL / UPDATED)

Behaviour:
    • First run (empty store)  → BACKFILL 36 months, no event spam.
    • Every run after          → INCREMENTAL, only the last 45 days, and it
                                 classifies each new contract:
        NEW      – first contract we've ever seen for this org + service
        RENEWAL  – a NEW contract for an org+service that ALREADY had one
                   ← this is exactly the Νισύρου case: the moment the Δήμος
                     re-signs, it's logged, so nothing looks 'open' when it isn't
        UPDATED  – an existing contract whose end date or value changed

Run locally (first backfill) or let GitHub Actions do it.
"""

import os
import json
import time
from datetime import date, datetime, timedelta

import requests

DATA_DIR = "data"
STORE = os.path.join(DATA_DIR, "contracts.jsonl")
CHANGES = os.path.join(DATA_DIR, "changes.jsonl")

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"

BACKFILL_MONTHS = 36
INCREMENTAL_DAYS = 45      # daily runs only need a recent window

SERVICES = {
    # ── AUDIT & CONSULTING (Delta Prime) ─────────────────────────────
    "Εσωτερικός έλεγχος": ["79212200-5", "79212000-3"],
    "Οικονομικός έλεγχος / Ορκωτοί": ["79212100-4", "79212300-6"],
    "Διαχείριση κινδύνων": ["71317000-3", "71700000-5", "79212400-7"],
    "Συμμόρφωση / Whistleblowing": ["79410000-1"],
    "DPO / Προστασία δεδομένων": ["79417000-0"],
    "Χαρτογράφηση / Οργάνωση": ["79411000-8", "72221000-0"],
    # ── ACCOUNTING & TAX (alliance) ──────────────────────────────────
    "Λογιστικές υπηρεσίες": ["79210000-9", "79211000-6", "79211100-7", "79211110-3", "79211120-6"],
    "Φορολογικές υπηρεσίες": ["79221000-9", "79222000-6"],
    "Μισθοδοσία": ["79211110-0", "79631000-6"],
    "Επιχειρηματική / οικονομική συμβουλευτική": ["79200000-6", "79220000-2"],
}
ALL_CODES = sorted({c for v in SERVICES.values() for c in v})
SERVICE_OF = {c: s for s, v in SERVICES.items() for c in v}
UNIT_DAYS = {"1": 1.0, "2": 7.0, "3": 30.4, "4": 365.25}

SESSION = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4, connect=4, read=4, backoff_factor=2.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]))))
except Exception:
    pass


def windows(months_back, span=175):
    end, out = date.today(), []
    cur = end - timedelta(days=int(months_back * 30.4))
    while cur < end:
        w = min(cur + timedelta(days=span), end)
        out.append((cur.isoformat(), w.isoformat()))
        cur = w + timedelta(days=1)
    return out


def fetch_window(dfrom, dto):
    body = {"cpvItems": ALL_CODES, "dateFrom": dfrom, "dateTo": dto}
    out, page, fails = [], 0, 0
    while True:
        try:
            r = SESSION.post(f"{CONTRACT_URL}?page={page}", json=body,
                             headers={"Accept": "application/json"}, timeout=45)
            r.raise_for_status()
            data = r.json()
        except Exception:
            fails += 1
            if fails >= 3:
                break
            time.sleep(10 * fails)
            continue
        fails = 0
        out.extend(data.get("content", []))
        if data.get("last", True):
            break
        page += 1
        if page > 25:
            break
        time.sleep(0.6)
    return out


def compute_end(signed, end_date, no_end, dur, unit_key):
    if no_end:
        return None
    if end_date:
        return end_date[:10]
    if signed and dur:
        mult = UNIT_DAYS.get(str(unit_key))
        if mult:
            try:
                d = datetime.strptime(signed[:10], "%Y-%m-%d").date()
                return (d + timedelta(days=int(float(dur) * mult))).isoformat()
            except Exception:
                return None
    return None


def parse(c):
    det = c.get("contractingDataDetails") or {}
    members = det.get("contractingMembersDataList") or []
    service = None
    for obj in (c.get("objectDetailsList") or []):
        for cp in (obj.get("cpvs") or []):
            s = SERVICE_OF.get(str(cp.get("key", "")).strip())
            if s:
                service = s
                break
        if service:
            break
    signed = (c.get("contractSignedDate") or "")[:10] or None
    return {
        "adam": c.get("referenceNumber"),
        "org": (c.get("organization") or {}).get("value"),
        "orgkey": (c.get("organization") or {}).get("key"),
        "region": (c.get("nutsCode") or {}).get("value"),
        "service": service,
        "holder": " / ".join(m.get("name", "") for m in members) or None,
        "signer": (det.get("signers") or {}).get("value"),
        "value": c.get("contractBudget") or c.get("totalCostWithoutVAT") or 0,
        "signed": signed,
        "end": compute_end(signed, c.get("endDate"), bool(c.get("noEndDate")),
                           c.get("contractDuration"),
                           (c.get("contractDurationUnitOfMeasure") or {}).get("key")),
    }


def load_store():
    store = {}
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    store[rec["adam"]] = rec
    return store


def save_store(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STORE, "w", encoding="utf-8") as f:
        for adam in sorted(store):                    # stable order = tiny git diffs
            f.write(json.dumps(store[adam], ensure_ascii=False) + "\n")


def log_changes(events):
    if not events:
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CHANGES, "a", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def main():
    store = load_store()
    first_run = len(store) == 0
    today = date.today().isoformat()

    # what does each org already hold per service? (to spot renewals)
    latest = {}   # (orgkey, service) -> newest signed date we already have
    for rec in store.values():
        k = (rec.get("orgkey"), rec.get("service"))
        if rec.get("signed") and rec["signed"] > latest.get(k, ""):
            latest[k] = rec["signed"]

    if first_run:
        print("First run — BACKFILL of", BACKFILL_MONTHS, "months …")
        wins = windows(BACKFILL_MONTHS)
    else:
        dto = today
        dfrom = (date.today() - timedelta(days=INCREMENTAL_DAYS)).isoformat()
        print(f"Incremental — scanning {dfrom} → {dto}")
        wins = [(dfrom, dto)]

    events, added, updated = [], 0, 0
    for dfrom, dto in wins:
        if first_run:
            print(f"  {dfrom} → {dto}")
        for c in fetch_window(dfrom, dto):
            p = parse(c)
            adam = p["adam"]
            if not adam or not p["service"]:
                continue

            if adam in store:
                old = store[adam]
                if old.get("end") != p["end"] or old.get("value") != p["value"]:
                    store[adam] = {**old, "end": p["end"], "value": p["value"]}
                    updated += 1
                    if not first_run:
                        events.append({"date": today, "event": "UPDATED",
                                       "adam": adam, "org": p["org"],
                                       "service": p["service"],
                                       "detail": f"end {old.get('end')}→{p['end']}, "
                                                 f"value {old.get('value')}→{p['value']}"})
                continue

            # brand-new ΑΔΑΜ
            p["first_seen"] = today
            store[adam] = p
            added += 1
            k = (p["orgkey"], p["service"])
            had_before = k in latest
            if not first_run:
                events.append({"date": today,
                               "event": "RENEWAL" if had_before else "NEW",
                               "adam": adam, "org": p["org"], "service": p["service"],
                               "holder": p["holder"], "value": p["value"],
                               "signed": p["signed"], "end": p["end"],
                               "detail": (f"replaces prior signed {latest.get(k)}"
                                          if had_before else "first contract seen")})
            if p.get("signed", "") > latest.get(k, ""):
                latest[k] = p.get("signed", "")

    save_store(store)
    log_changes(events)

    print(f"\nStore: {len(store)} contracts total  (+{added} new, {updated} updated)")
    if not first_run:
        renewals = sum(1 for e in events if e["event"] == "RENEWAL")
        print(f"Events this run: {len(events)}  ({renewals} RENEWALS)")
        for e in events[:15]:
            print(f"  {e['event']:<8} {e['org']} — {e['service']}")
    else:
        print("Backfill complete. Future runs will detect NEW / RENEWAL / UPDATED.")


if __name__ == "__main__":
    main()
