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


# Amendment keywords — appearing in a contract subject/title, these signal that
# the record is a CHILD of an earlier contract (extension/modification/supplement)
# rather than a fresh, independent contract. We tag but do NOT merge yet — user
# will observe how noisy this signal is on real data before we act on it.
AMENDMENT_KEYWORDS = [
    "παράταση", "παρατάσεως", "παρατάσεων", "παρατασεις",
    "τροποποίηση", "τροποποιήσεως", "τροποποιητικ",
    "συμπληρωματικ",
    "παράταση της σύμβασης", "τροποποίηση της σύμβασης",
]


def is_amendment(subject):
    if not subject:
        return False
    s = subject.lower()
    return any(k in s for k in AMENDMENT_KEYWORDS)


# ── Subject-vs-service check ──────────────────────────────────────────────
# The CPV alone can mislabel a contract (e.g. software-for-surgeries tagged as
# Internal Audit). When we have the contract title (subject), we cross-check it
# against the tagged service and annotate — WITHOUT deleting or changing the
# service. Readers show a badge so the user verifies before acting.
#
# Result stored on each record as `subject_check`:
#   "confirmed"  — subject contains a word that CONFIRMS the tagged service
#   "mismatch"   — subject contains a word that CONTRADICTS it (likely wrong CPV)
#   "unverified" — no positive and no negative signal (or no subject yet)

POSITIVE_KEYWORDS = {
    "Εσωτερικός έλεγχος": [
        "εσωτερικ", "ενδογεν", "δικλίδ", "δικλειδ", "μεε ", " μεε",
        "μονάδα ελέγχου", "μοναδα ελεγχου", "μονάδας ελέγχου", "μοναδας ελεγχου",
        "ν.4795", "ν. 4795", "4795/2021", "4795/21",
        "internal audit", "internal control",
    ],
    "Διαχείριση κινδύνων": [
        "κινδύν", "κινδυν", "μητρώο κινδ", "μητρωο κινδ",
        "ν.5013", "ν. 5013", "5013/2023", "5013/23",
        "risk management", "risk assessment", "διαχείριση κιν", "διαχειριση κιν",
    ],
    "Χαρτογράφηση / Οργάνωση": [
        "χαρτογράφ", "χαρτογραφ", "διαδικασ", "οργανωτικ", "οργάνωσ", "οργανωσ",
        "καταγραφή διαδ", "καταγραφη διαδ",
    ],
    "Οικονομικός έλεγχος / Ορκωτοί": [
        "οικονομικ έλεγχ", "οικονομικ ελεγχ", "ορκωτ", "χρηματοοικονομικ έλεγχ",
        "financial audit", "statutory audit", "ελεγκτικές υπηρεσίες",
        "ελεγκτικες υπηρεσιες", "ελεγκτ", "λογιστ",
    ],
    "DPO / Προστασία δεδομένων": [
        "dpo", "προστασία δεδομ", "προστασια δεδομ", "γκπδ", "gdpr",
        "προστασ προσωπικ", "υπεύθυν προστασ", "υπευθυν προστασ",
    ],
    "Συμμόρφωση / Whistleblowing": [
        "συμμόρφωσ", "συμμορφωσ", "καταγγελ", "whistleblow",
        "ν.4990", "ν. 4990", "4990/2022", "δίαυλοι", "διαυλοι",
    ],
    "Λογιστικές υπηρεσίες": [
        "λογιστ", "τήρηση βιβλί", "τηρηση βιβλι", "λογιστήρι", "λογιστηρι",
    ],
    "Φορολογικές υπηρεσίες": [
        "φορολογ", "φπα", "φ.π.α", "μισθοδοσ",
    ],
    "Επιχειρηματική / οικονομική συμβουλευτική": [
        "επιχειρηματικ σχ", "στρατηγικ", "επιχειρησιακ σχ",
        "business plan", "financial advis",
    ],
}

# Negative keywords: if the subject is clearly about something unrelated
# (IT, vehicles, construction, events, medical), the service tag is suspect.
# NOTE: "καθαρισμ"/"καθαριστ" intentionally NOT included — they false-match
# "εκκαθαριστής" (liquidator), a legitimate accounting role. Left out on purpose.
NEGATIVE_KEYWORDS = [
    # IT / software / hardware
    "λογισμικ", "software", "hardware", "εφαρμογ πληροφορικ",
    "πληροφοριακό σύστημα", "πληροφοριακο συστημα", "μηχανογραφ",
    # Vehicles / fuel / transport of goods
    "οχήματ", "οχηματ", "καύσιμ", "καυσιμ", "στόλου οχ", "στολου οχ",
    # Medical / clinical / surgical
    "χειρουργεί", "χειρουργει", "νοσηλευτικ", "εμβολιασμ",
    # Construction / civil works
    "κατασκευ", "ανακαίν", "ανακαιν", "οδοποιί", "οδοποιι", "φράγμα", "φραγμα",
    # Events / marketing
    "διαφήμισ", "διαφημισ", "εκδήλωσ", "εκδηλωσ", "εγκαινί", "εγκαινι",
    # Building maintenance (specific, to avoid catching "συντήρηση λογισμικού"→already caught)
    "συντήρησ κτιρι", "συντηρησ κτιρι",
]


def subject_check(subject, service):
    """Classify subject vs tagged service. Non-destructive annotation only."""
    if not subject:
        return "unverified"
    s = subject.lower()
    s = " ".join(s.split())
    # Negative signal wins — strongest indication the CPV mislabeled it
    for kw in NEGATIVE_KEYWORDS:
        if kw in s:
            return "mismatch"
    # Positive signal confirms
    for kw in POSITIVE_KEYWORDS.get(service, []):
        if kw in s:
            return "confirmed"
    return "unverified"


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
    subject = (c.get("title") or c.get("subject") or "").strip() or None
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
        "subject": subject,
        "amendment": is_amendment(subject),
        "subject_check": subject_check(subject, service),
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

    # One-time sweep: records filled by the earlier subject-backfill have a
    # `subject` but no `subject_check` yet. Compute it now. Idempotent — records
    # that already have the check are skipped.
    swept = 0
    for rec in store.values():
        if rec.get("subject") and "subject_check" not in rec:
            rec["subject_check"] = subject_check(rec["subject"], rec.get("service"))
            swept += 1
    if swept:
        print(f"Subject-check sweep: annotated {swept} previously-backfilled records")
    today = date.today().isoformat()

    # what does each org already hold per service? (to spot renewals)
    latest = {}   # (orgkey, service) -> newest signed date we already have
    for rec in store.values():
        if rec.get("superseded_by"):        # ignore records already flagged
            continue
        k = (rec.get("orgkey"), rec.get("service"))
        if rec.get("signed") and rec["signed"] > latest.get(k, ""):
            latest[k] = rec["signed"]

    # Fingerprint index for detecting REPUBLICATIONS — same commercial contract
    # re-uploaded to ΚΗΜΔΗΣ with a fresh ΑΔΑΜ (correction / re-attachment).
    # Safe 5-field key: holder + orgkey + value + signed + end. All must match.
    def fingerprint(r):
        return (
            (r.get("holder") or "").strip(),
            r.get("orgkey") or "",
            r.get("value") or 0,
            r.get("signed") or "",
            r.get("end") or "",
        )
    prints = {}    # fingerprint -> ΑΔΑΜ of the canonical (non-superseded) record

    # One-off backfill sweep: catch republications that entered the store
    # BEFORE this dedup logic existed. Idempotent — records already flagged
    # are skipped; if two active records share a fingerprint, keep the newest
    # ΑΔΑΜ canonical and mark the rest superseded_by.
    backfill_fp = {}
    for adam, rec in store.items():
        if rec.get("superseded_by"):
            continue
        fp = fingerprint(rec)
        backfill_fp.setdefault(fp, []).append(adam)
    backfilled = 0
    for fp, adams in backfill_fp.items():
        if len(adams) <= 1:
            prints[fp] = adams[0]
            continue
        adams.sort()   # ΑΔΑΜ lexicographic order ~= chronological
        canonical = adams[-1]
        for a in adams[:-1]:
            store[a] = {**store[a], "superseded_by": canonical}
            backfilled += 1
        # And record the canonical's supersedes chain (newest one wins)
        store[canonical] = {**store[canonical], "supersedes": adams[-2]}
        prints[fp] = canonical
    if backfilled:
        print(f"  backfill: marked {backfilled} historical republications")

    if first_run:
        print("First run — BACKFILL of", BACKFILL_MONTHS, "months …")
        wins = windows(BACKFILL_MONTHS)
    else:
        dto = today
        dfrom = (date.today() - timedelta(days=INCREMENTAL_DAYS)).isoformat()
        print(f"Incremental — scanning {dfrom} → {dto}")
        wins = [(dfrom, dto)]

    events, added, updated, republished = [], 0, 0, 0
    new_adams = []   # brand-new ΑΔΑΜs → generate full-text pages after save
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
                changed = False
                # Enrich existing records with new fields (subject / amendment)
                # if they lack them — one-time backfill via the incremental window.
                if "subject" not in old and p.get("subject"):
                    old = {**old, "subject": p["subject"], "amendment": p["amendment"],
                           "subject_check": p.get("subject_check", "unverified")}
                    changed = True
                if old.get("end") != p["end"] or old.get("value") != p["value"]:
                    old = {**old, "end": p["end"], "value": p["value"]}
                    updated += 1
                    if not first_run:
                        events.append({"date": today, "event": "UPDATED",
                                       "adam": adam, "org": p["org"],
                                       "service": p["service"],
                                       "detail": f"end {store[adam].get('end')}→{p['end']}, "
                                                 f"value {store[adam].get('value')}→{p['value']}"})
                    changed = True
                if changed:
                    store[adam] = old
                continue

            # New ΑΔΑΜ — but is it a republication of an existing contract?
            fp = fingerprint(p)
            older_adam = prints.get(fp)
            if older_adam and older_adam != adam:
                # REPUBLICATION: same commercial contract, fresh ΑΔΑΜ.
                # Keep the newer one canonical (it's the corrected version) and
                # flag the older with superseded_by so all readers can filter.
                # ΑΔΑΜ sorts lexicographically ~ chronologically for ΚΗΜΔΗΣ.
                if adam > older_adam:
                    p["first_seen"] = today
                    p["supersedes"] = older_adam
                    store[adam] = p
                    store[older_adam] = {**store[older_adam], "superseded_by": adam}
                    prints[fp] = adam
                else:
                    # Incoming ΑΔΑΜ is older than one we already trust — record
                    # it but mark it superseded so it never surfaces on pages.
                    p["first_seen"] = today
                    p["superseded_by"] = older_adam
                    store[adam] = p
                republished += 1
                if not first_run:
                    events.append({"date": today, "event": "REPUBLISH",
                                   "adam": adam, "org": p["org"],
                                   "service": p["service"],
                                   "detail": f"republication of {older_adam}"})
                # DO NOT touch latest[] or fire RENEWAL — this is one contract.
                continue

            # Truly brand-new contract
            p["first_seen"] = today
            store[adam] = p
            prints[fp] = adam
            added += 1
            new_adams.append(adam)
            k = (p["orgkey"], p["service"])
            had_before = k in latest
            if not first_run:
                events.append({"date": today,
                               "event": "RENEWAL" if had_before else "NEW",
                               "adam": adam, "org": p["org"], "service": p["service"],
                               "holder": p["holder"], "value": p["value"],
                               "signed": p["signed"], "end": p["end"],
                               "subject": p.get("subject"),
                               "subject_check": p.get("subject_check", "unverified"),
                               "detail": (f"replaces prior signed {latest.get(k)}"
                                          if had_before else "first contract seen")})
            if p.get("signed", "") > latest.get(k, ""):
                latest[k] = p.get("signed", "")

    save_store(store)
    log_changes(events)

    # Generate full-text contract pages for brand-new contracts so they open
    # instantly in the What Changed split-view. Best-effort: never let a PDF
    # download / OCR failure break the core ingest. Skipped on first_run
    # (that would be thousands of PDFs — use the separate backfill for history).
    if new_adams and not first_run:
        try:
            from contract_reader import generate_for_adam
            print(f"\nGenerating full-text pages for {len(new_adams)} new contract(s):")
            gen_ok = 0
            for a in new_adams:
                if generate_for_adam(a, skip_if_exists=True):
                    gen_ok += 1
            print(f"  → {gen_ok}/{len(new_adams)} pages ready")
        except Exception as e:
            print(f"  (text generation skipped: {type(e).__name__})")

    print(f"\nStore: {len(store)} contracts total  (+{added} new, "
          f"{updated} updated, {republished} republications)")
    if not first_run:
        renewals = sum(1 for e in events if e["event"] == "RENEWAL")
        print(f"Events this run: {len(events)}  ({renewals} RENEWALS)")
        for e in events[:15]:
            print(f"  {e['event']:<8} {e['org']} — {e['service']}")
    else:
        print("Backfill complete. Future runs will detect NEW / RENEWAL / UPDATED.")


if __name__ == "__main__":
    main()
