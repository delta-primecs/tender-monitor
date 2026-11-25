"""
ENRICH THE CONTRACT STORE — fill the gaps that made ORGS say "δεν βρέθηκε".

Every fix uses a public source (verified with tools/probe.py):

  A. CPV RESCAN 2020 → today  (ΚΗΜΔΗΣ /contract, our CPVs)
     • fills missing `subject` (the API does return the title — it was simply
       never stored for older records) and missing `end`
     • adds older contracts (2020–2022) that the 36-month store never had

  B. TITLE SAFETY NET  (ΚΗΜΔΗΣ /contract accepts a `title` filter)
     • finds contracts for OUR services filed under the WRONG CPV, e.g.
       "Παροχή υπηρεσιών εσωτερικού ελέγχου" with an IT or generic code
     • added only if the title positively confirms the service and nothing
       in it contradicts it (same subject_check as the ingester)

  C. END-DATE ESTIMATE FROM THE CONTRACT TEXT  (docs/contracts/<ΑΔΑΜ>.html)
     • ΚΗΜΔΗΣ leaves endDate empty for many contracts; the text often says
       "…έως 31/12/2025". Stored as `end_est` (≈90% accurate when validated),
       never as `end`.

No events are fired (historical data must not look "new" in What changed).
Every added/changed record is tagged so its origin is visible:
  backfill:true · source:"title" · end_est

Run:
  python enrich_store.py            full: A (from 2020) + B (from 2020) + C
  python enrich_store.py --full 2023        full, but starting from that year
  python enrich_store.py --full 2020 2021   full, only those years (resumable chunks)
  python enrich_store.py --recent   daily: A+B for the last 45 days, then C
  python enrich_store.py --text     only C (offline)
"""

import html as htmllib
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

import ingest_contracts as ing

FULL_FROM = date(2020, 1, 1)
RECENT_DAYS = 45
SPAN = 60          # small windows: ΚΗΜΔΗΣ pages are short, never truncate
TEXT_DIR = "docs/contracts"

# Title phrases per service (ΚΗΜΔΗΣ title search is case-insensitive).
# Kept specific on purpose: a broad word would drag in unrelated contracts.
TITLE_PHRASES = {
    "Εσωτερικός έλεγχος": ["εσωτερικού ελέγχου", "εσωτερικό έλεγχο", "εσωτερικός έλεγχος"],
    "Οικονομικός έλεγχος / Ορκωτοί": ["ορκωτού ελεγκτή", "ορκωτών ελεγκτών", "ορκωτό ελεγκτή",
                                       "ορκωτούς ελεγκτές"],
    "DPO / Προστασία δεδομένων": ["υπευθύνου προστασίας δεδομένων", "υπεύθυνου προστασίας δεδομένων",
                                  "προστασίας προσωπικών δεδομένων", "GDPR"],
    "Διαχείριση κινδύνων": ["διαχείρισης κινδύνων", "διαχείριση κινδύνων"],
    "Συμμόρφωση / Whistleblowing": ["κανονιστικής συμμόρφωσης", "αναφορών παραβάσεων",
                                    "whistleblowing"],
    "Χαρτογράφηση / Οργάνωση": ["χαρτογράφησης διαδικασιών", "χαρτογράφηση διαδικασιών"],
    "Κυβερνοασφάλεια": ["κυβερνοασφάλειας", "κυβερνοασφάλεια", "NIS2"],
    "Λογιστικές υπηρεσίες": ["λογιστικής υποστήριξης", "λογιστικών υπηρεσιών",
                             "λογιστικής παρακολούθησης"],
    "Φορολογικές υπηρεσίες": ["φορολογικής υποστήριξης", "φορολογικών υπηρεσιών"],
    "Μισθοδοσία": ["μισθοδοσίας"],
}

TITLE_URL = ing.CONTRACT_URL


END_AT = None   # optional upper bound (set by --full FROM TO)


def windows_from(start):
    out, cur, end = [], start, min(END_AT or date.today(), date.today())
    while cur <= end:
        w = min(cur + timedelta(days=SPAN), end)
        out.append((cur.isoformat(), w.isoformat()))
        cur = w + timedelta(days=1)
    return out


def fetch(body, stats=None, label=""):
    """All pages for one search body, checked against ΚΗΜΔΗΣ's own total."""
    out, page, fails, total = [], 0, 0, None
    while page <= 400:
        try:
            r = ing.SESSION.post(f"{TITLE_URL}?page={page}", json=body,
                                 headers={"Accept": "application/json"}, timeout=45)
            r.raise_for_status()
            data = r.json()
        except Exception:
            fails += 1
            if fails >= 3:
                break
            time.sleep(8 * fails)
            continue
        fails = 0
        total = data.get("totalElements", total)
        out.extend(data.get("content", []))
        if data.get("last", True):
            break
        page += 1
        time.sleep(0.4)
    if total is not None and len(out) < total:
        print(f"   ⚠ {label}: got {len(out)} of {total} (incomplete)")
        if stats is not None:
            stats.inc("windows incomplete")
    return out


def checkpoint(store, msg):
    """Save, and in GitHub Actions (ENRICH_COMMIT=1) commit+push the progress
    so a timeout never throws away finished work."""
    ing.save_store(store)
    if os.environ.get("ENRICH_COMMIT") != "1":
        return
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    g("config", "user.name", "tender-bot")
    g("config", "user.email", "tender-bot@users.noreply.github.com")
    g("add", "data/")
    if g("diff", "--staged", "--quiet").returncode == 0:
        return
    g("commit", "-m", f"Enrich store: {msg}")
    for _ in range(3):
        if g("pull", "--rebase", "origin", "main").returncode == 0 and g("push").returncode == 0:
            print(f"   [saved & pushed: {msg}]")
            return
        time.sleep(8)
    print(f"   [WARN: push failed for '{msg}' — will retry at next checkpoint]")


def fingerprint(r):
    return (r.get("holder"), str(r.get("orgkey")), r.get("value"), r.get("signed"), r.get("end"))


class Stats(dict):
    def inc(self, k, n=1):
        self[k] = self.get(k, 0) + n


def merge(store, p, fps, stats, *, source=None):
    """Enrich an existing record or add a new one. Returns True if changed."""
    adam = p.get("adam")
    if not adam or not p.get("service"):
        return False
    old = store.get(adam)
    if old:
        changed = False
        if not old.get("subject") and p.get("subject"):
            old["subject"] = p["subject"]
            old["amendment"] = p.get("amendment", False)
            old["subject_check"] = ing.subject_check(p["subject"], old.get("service"))
            stats.inc("subject filled"); changed = True
        if not old.get("end") and p.get("end"):
            old["end"] = p["end"]; old["end_source"] = "khmdhs"
            stats.inc("end filled (ΚΗΜΔΗΣ)"); changed = True
        for k in ("signer", "region", "holder"):
            if not old.get(k) and p.get(k):
                old[k] = p[k]; changed = True
        return changed
    if fingerprint(p) in fps:            # republication of something we have
        stats.inc("skipped republication")
        return False
    rec = dict(p)
    rec["first_seen"] = date.today().isoformat()
    rec["backfill"] = True
    if source:
        rec["source"] = source
    store[adam] = rec
    fps.add(fingerprint(rec))
    stats.inc("added (title net)" if source == "title" else "added (older contract)")
    return True


def phase_a(store, fps, start, stats):
    wins = windows_from(start)
    print(f"A · CPV rescan: {len(wins)} windows from {start}")
    t0 = time.time()
    for i, (a, b) in enumerate(wins, 1):
        batch = fetch({"cpvItems": ing.ALL_CODES, "dateFrom": a, "dateTo": b}, stats, f"CPV {a}")
        for c in batch:
            merge(store, ing.parse(c), fps, stats)
        print(f"   [{i}/{len(wins)}] {a} → {b}: {len(batch)} contracts  ({time.time()-t0:.0f}s)", flush=True)
        if i % 8 == 0:
            checkpoint(store, f"CPV rescan up to {b}")
        time.sleep(0.6)


def phase_b(store, fps, start, stats):
    wins = windows_from(start)
    print(f"B · Title safety net: {sum(map(len, TITLE_PHRASES.values()))} phrases × {len(wins)} windows")
    for svc, phrases in TITLE_PHRASES.items():
        found = 0
        for ph in phrases:
            for a, b in wins:
                for c in fetch({"title": ph, "dateFrom": a, "dateTo": b}, stats, f"{ph} {a}"):
                    adam = c.get("referenceNumber")
                    if not adam or adam in store:
                        continue
                    p = ing.parse(c)
                    title = p.get("subject") or ""
                    # the TITLE decides the service here — require a positive
                    # confirmation and no contradicting word
                    if ing.subject_check(title, svc) != "confirmed":
                        stats.inc("title hits rejected (not confirmed)")
                        continue
                    p["service"] = svc
                    p["subject_check"] = "confirmed"
                    if merge(store, p, fps, stats, source="title"):
                        found += 1
                time.sleep(0.4)
        print(f"   {svc}: +{found} contracts found only by title", flush=True)
        checkpoint(store, f"title net · {svc}")


# ── C · end date ESTIMATE from the contract text ────────────────────────────
# Validated on 3,983 contracts whose real end date we know: only the explicit
# "…διάρκεια/ισχύς… έως 31/12/2025" pattern is ~90% right; "διάρκεια 12 μηνών"
# patterns are 76–83%. So we store ONLY the explicit pattern, and as an
# ESTIMATE (`end_est`) — never in `end`, which stays what ΚΗΜΔΗΣ says.
RE_UNTIL = re.compile(
    r"(?:διάρκει\w*|ισχ[υύ]\w*|λήγ\w*|ολοκλήρωσ\w*)[^.;\n]{0,90}?(?:έως|μέχρι|εως)\s*(?:και\s*)?(?:την\s*)?"
    r"(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})", re.I)


def end_from_text(text, signed):
    try:
        s = datetime.strptime(signed[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    m = RE_UNTIL.search(text)
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if s < d <= s + timedelta(days=6 * 366):
                return d.isoformat()
        except ValueError:
            pass
    return None


def page_text(path):
    raw = open(path, encoding="utf-8", errors="ignore").read()
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    txt = htmllib.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", txt)


def phase_c(store, stats):
    todo = [r for r in store.values()
            if not r.get("end") and not r.get("end_est") and r.get("signed")
            and not r.get("superseded_by")
            and os.path.exists(os.path.join(TEXT_DIR, f"{r['adam']}.html"))]
    print(f"C · end-date estimate from contract text: {len(todo)} candidates")
    for r in todo:
        e = end_from_text(page_text(os.path.join(TEXT_DIR, f"{r['adam']}.html")), r["signed"])
        if e:
            r["end_est"] = e
            stats.inc("end estimate from contract text")


def gaps(store):
    live = [r for r in store.values() if not r.get("superseded_by")]
    return {"records": len(live),
            "no subject": sum(1 for r in live if not r.get("subject")),
            "no end": sum(1 for r in live if not r.get("end")),
            "before 2023": sum(1 for r in live if (r.get("signed") or "9")[:4] < "2023")}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--full"
    store = ing.load_store()
    before = gaps(store)
    fps = {fingerprint(r) for r in store.values() if not r.get("superseded_by")}
    stats = Stats()

    if mode in ("--full", "--recent"):
        start = FULL_FROM if mode == "--full" else date.today() - timedelta(days=RECENT_DAYS)
        if mode == "--full" and len(sys.argv) > 2:
            start = date(int(sys.argv[2]), 1, 1)
        if mode == "--full" and len(sys.argv) > 3:
            global END_AT
            END_AT = date(int(sys.argv[3]), 12, 31)
        phase_a(store, fps, start, stats)
        checkpoint(store, "CPV rescan done")
        phase_b(store, fps, start, stats)
        checkpoint(store, "title net done")
    phase_c(store, stats)
    ing.save_store(store)

    after = gaps(store)
    print("\n" + "=" * 60)
    print("BEFORE:", before)
    print("AFTER: ", after)
    for k, v in sorted(stats.items()):
        print(f"  {k:40} {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
