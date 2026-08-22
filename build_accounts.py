"""
Account Map (reliability-hardened) — build docs/accounts.html

Fixes learned from a real miss (Δήμος Νισύρου renewed by direct award,
"1 year from signing", no explicit endDate — old logic couldn't see it end):

  1. EXPIRY = endDate if present, ELSE signedDate + contractDuration×unit.
  2. Always use the FRESHEST signed contract per service line.
  3. Flag accounts renewed within the lead window: they are NOT openings.
  4. Every card shows the newest-signed date + a one-click Διαύγεια verify,
     and the page carries a loud "data as of" stamp — because ΚΗΜΔΗΣ refreshes
     ~daily and a direct-award renewal can appear at any time. The tool arms
     the call; the 5-second verify before dialling is non-negotiable.

Data: ΚΗΜΔΗΣ contracts (public, no login).
"""

import os
import json
import time
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta

import requests

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"
OUT = "docs/accounts.html"

MONTHS_BACK = 36
LEAD_MONTHS = 5      # be in front of them this long before expiry
RENEWED_MONTHS = 6   # signed within this window ⇒ "recently renewed", not an opening
PAGE_PAUSE = 0.7
TIMEOUT = 45

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

ALL_CODES = sorted({c for codes in SERVICES.values() for c in codes})
SERVICE_OF = {c: s for s, codes in SERVICES.items() for c in codes}
UNIT_DAYS = {"1": 1.0, "2": 7.0, "3": 30.4, "4": 365.25}   # ημέρες/εβδ./μήνες/έτη

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
                             headers={"Accept": "application/json"}, timeout=TIMEOUT)
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
        time.sleep(PAGE_PAUSE)
    return out


def compute_end(signed, end_date, no_end, dur, unit_key):
    """Explicit endDate wins; otherwise signed + duration. None if unknowable."""
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


# Title keywords that clearly indicate a service line. Used only to FLAG (never
# override) contracts whose CPV disagrees with their title — because public
# bodies frequently put the wrong CPV on a contract (garbage in). The title
# often tells the truth when the CPV lies, so we surface the disagreement.
TITLE_HINTS = {
    "Εσωτερικός έλεγχος": ["εσωτερικού ελέγχ", "εσωτερικός έλεγχ", "μονάδα εσωτερικ",
                            "εσωτερικού ελεγκτ", "εσωτερικός ελεγκτ"],
    "Οικονομικός έλεγχος / Ορκωτοί": ["ορκωτ", "οικονομικών καταστάσεων",
                                       "οικονομικός έλεγχ", "λογιστικός έλεγχ"],
    "Διαχείριση κινδύνων": ["διαχείριση κινδύν", "διαχείρισης κινδύν"],
    "Συμμόρφωση / Whistleblowing": ["κανονιστικής συμμόρφωσ", "κανονιστική συμμόρφωσ",
                                     "υπεύθυν συμμόρφωσ", "εσωτερικών αναφορ", "4990", "υππα"],
    "DPO / Προστασία δεδομένων": ["προστασία δεδομέν", "προστασίας δεδομέν",
                                   "προσωπικών δεδομέν", "dpo", "υπεύθυν προστασίας"],
    "Χαρτογράφηση / Οργάνωση": ["χαρτογράφησ", "καταγραφή διαδικασ", "καταγραφής διαδικασ"],
}


def title_service(title):
    """The single service a title clearly indicates, else None if unclear/ambiguous."""
    t = (title or "").lower()
    hits = [svc for svc, keys in TITLE_HINTS.items() if any(k in t for k in keys)]
    return hits[0] if len(hits) == 1 else None


# ── SUSPICIOUS-CPV SET ─────────────────────────────────────────────
# Umbrella CPV codes that Greek public bodies notoriously mis-tag.
# We still map them to services (so tenders aren't invisible) BUT any row
# using them carries a warning flag so the user verifies before acting.
UMBRELLA_CPVS = {
    "79200000-6",   # τραπεζικές / επιχειρηματικές γενικά
    "79411000-8",   # management consulting generally
    "79220000-2",   # financial services generally
    "72221000-0",   # business analysis consulting generally
}

# ── FIRM-NAME vs SERVICE MISMATCH ──────────────────────────────────
# When a contractor's NAME contains these keywords, the firm is almost
# certainly not a real provider of the mapped service. E.g. a firm called
# "ΤΕΧΝΙΚΗ ΕΝΕΡΓΕΙΑΚΗ" doing "Εσωτερικός έλεγχος" is a Δήμος tagging error,
# not a real audit engagement. Deliberately conservative — only fire on
# STRONG negative signals to keep false positives low.
NAME_INCOMPATIBLE_HINTS = {
    "Εσωτερικός έλεγχος": [
        "τεχνικ", "ενεργειακ", "κατασκευ", "μηχανικ", "εκπαιδευτικ",
        "καθαρι", "τροφί", "εστιατ", "κατασκηνώσ",
    ],
    "Οικονομικός έλεγχος / Ορκωτοί": [
        "τεχνικ", "ενεργειακ", "κατασκευ", "εκπαιδευτικ", "καθαρι",
    ],
    "Διαχείριση κινδύνων": [
        "εκπαιδευτικ", "καθαρι", "κατασκευ", "τροφί", "εστιατ",
    ],
    "Συμμόρφωση / Whistleblowing": [
        "τεχνικ", "κατασκευ", "εκπαιδευτικ", "καθαρι",
    ],
    "DPO / Προστασία δεδομένων": [
        "κατασκευ", "εκπαιδευτικ", "καθαρι", "τροφί", "εστιατ",
    ],
    "Χαρτογράφηση / Οργάνωση": [
        "τεχνικ", "ενεργειακ", "κατασκευ", "εκπαιδευτικ", "καθαρι",
        "τροφί", "εστιατ", "μηχανικ",
    ],
    "Λογιστικές υπηρεσίες": [
        "τεχνικ", "κατασκευ", "εκπαιδευτικ", "καθαρι", "μηχανικ",
    ],
    "Φορολογικές υπηρεσίες": [
        "τεχνικ", "κατασκευ", "εκπαιδευτικ", "καθαρι", "μηχανικ",
    ],
    "Μισθοδοσία": [
        "τεχνικ", "κατασκευ", "εκπαιδευτικ", "καθαρι", "μηχανικ",
    ],
    "Επιχειρηματική / οικονομική συμβουλευτική": [
        "εκπαιδευτικ", "καθαρι", "τροφί", "εστιατ",
    ],
}


def firm_incompatible(holder, service):
    """Return True if the firm name strongly conflicts with the service."""
    if not holder or not service:
        return False
    hits = NAME_INCOMPATIBLE_HINTS.get(service, [])
    h = holder.lower()
    return any(k in h for k in hits)


def parse(c):
    det = c.get("contractingDataDetails") or {}
    members = det.get("contractingMembersDataList") or []
    signer = (det.get("signers") or {}).get("value")

    # Capture BOTH the matched service AND the CPV that triggered it,
    # so we can flag umbrella-CPV matches downstream.
    service = None
    matched_cpv = None
    for obj in (c.get("objectDetailsList") or []):
        for cp in (obj.get("cpvs") or []):
            code = str(cp.get("key", "")).strip()
            s = SERVICE_OF.get(code)
            if s:
                service = s
                matched_cpv = code
                break
        if service:
            break

    signed = (c.get("contractSignedDate") or "")[:10] or None
    end = compute_end(signed, c.get("endDate"), bool(c.get("noEndDate")),
                      c.get("contractDuration"),
                      (c.get("contractDurationUnitOfMeasure") or {}).get("key"))
    title = (c.get("title") or "").strip()
    ts = title_service(title)
    holder = " / ".join(m.get("name", "") for m in members) or None

    # Three independent warning signals — each surfaces its own tag:
    conflict     = ts if (ts and service and ts != service) else None
    umbrella     = matched_cpv in UMBRELLA_CPVS
    firm_bad_fit = firm_incompatible(holder, service)

    return {
        "org": (c.get("organization") or {}).get("value"),
        "orgkey": (c.get("organization") or {}).get("key"),
        "region": (c.get("nutsCode") or {}).get("value"),
        "service": service,
        "conflict": conflict,
        "umbrella": umbrella,
        "firm_bad_fit": firm_bad_fit,
        "holder": holder,
        "signer": signer,
        "value": c.get("contractBudget") or c.get("totalCostWithoutVAT") or 0,
        "signed": signed,
        "end": end,
        "adam": c.get("referenceNumber"),
    }


def collect():
    seen, rows = set(), []
    for dfrom, dto in windows(MONTHS_BACK):
        print(f"  scanning {dfrom} → {dto} …")
        batch = fetch_window(dfrom, dto)
        for c in batch:
            adam = c.get("referenceNumber")
            if not adam or adam in seen:
                continue
            seen.add(adam)
            p = parse(c)
            if p["org"] and p["service"]:
                rows.append(p)
        print(f"     … {len(batch)} records, {len(rows)} usable")
    return rows


def build_accounts(rows):
    today = date.today()
    renewed_before = (today - timedelta(days=int(RENEWED_MONTHS * 30.4))).isoformat()
    by_org = defaultdict(list)
    for r in rows:
        by_org[(r["orgkey"], r["org"])].append(r)

    accounts = []
    for (okey, oname), items in by_org.items():
        # freshest contract per service line (by signing date)
        per_service = {}
        for r in items:
            s = r["service"]
            cur = per_service.get(s)
            if cur is None or (r["signed"] or "") > (cur["signed"] or ""):
                per_service[s] = r

        signers = sorted((r for r in items if r["signer"]),
                         key=lambda r: r["signed"] or "", reverse=True)
        signer = signers[0]["signer"] if signers else None
        region = next((r["region"] for r in items if r["region"]), None)
        dated = sorted((r for r in items if r["signed"]),
                       key=lambda r: r["signed"], reverse=True)
        newest_signed = dated[0]["signed"] if dated else None
        newest_adam = dated[0]["adam"] if dated else None

        # earliest FUTURE end across service lines drives the call-by date
        future_ends = sorted(v["end"] for v in per_service.values()
                             if v["end"] and v["end"] >= today.isoformat())
        if future_ends:
            nxt = future_ends[0]
            call_by = (datetime.strptime(nxt, "%Y-%m-%d").date()
                       - timedelta(days=int(LEAD_MONTHS * 30.4))).isoformat()
        else:
            nxt = None
            call_by = today.isoformat()

        renewed = bool(newest_signed and newest_signed >= renewed_before)

        accounts.append({
            "org": oname, "region": region, "signer": signer,
            "newest": newest_signed, "newest_adam": newest_adam, "renewed": renewed,
            "next_end": nxt, "call_by": call_by,
            "has": [{"s": s, "holder": v["holder"], "v": v["value"],
                     "end": v["end"], "signed": v["signed"], "adam": v["adam"],
                     "conflict": v.get("conflict"),
                     "umbrella": v.get("umbrella"),
                     "firm_bad_fit": v.get("firm_bad_fit")}
                    for s, v in sorted(per_service.items(),
                                       key=lambda kv: kv[1]["end"] or "9999-99-99")],
            "gaps": [s for s in SERVICES if s not in per_service],
        })

    accounts.sort(key=lambda a: (a["call_by"], -sum(h["v"] or 0 for h in a["has"])))
    return accounts


def main():
    rows = collect()
    accounts = build_accounts(rows)
    os.makedirs("docs", exist_ok=True)
    athens = datetime.now(timezone(timedelta(hours=3)))
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(accounts, ensure_ascii=False))
            .replace("__SERVICES__", json.dumps(list(SERVICES.keys()), ensure_ascii=False))
            .replace("__LEAD__", str(LEAD_MONTHS))
            .replace("__STAMP__", athens.strftime("%d/%m/%Y %H:%M")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nWrote {OUT}: {len(accounts)} organisations from {len(rows)} contracts.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account Map</title>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#10322c;--ink-2:#17463c;--page:#eaefec;--card:#fff;--text:#14202b;
    --muted:#63748a;--hair:#dce3df;--gold:#8a5a11;--gold-bg:#f6ecd2;
    --link:#1f6f6b;--link-ink:#155551;--gap:#b23b2e;--gap-bg:#f7e0dc;
    --has:#2f6b4f;--has-bg:#e2efe8;--hot:#b23b2e;--warn-bg:#fbf3d6;--warn-ink:#8a6d1a;
    --fresh:#2f6b4f;--fresh-bg:#d9f0e4;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter',Arial,sans-serif;line-height:1.5;padding:24px 16px 56px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:900px;margin:0 auto}
  .nav{max-width:900px;margin:0 auto 12px;display:flex;gap:8px;font-size:13px;flex-wrap:wrap}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:#fff}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#e9f3ee;border-radius:14px 14px 0 0;padding:22px 24px 20px}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#9fd8c2;font-weight:600}
  h1{font-family:'Commissioner',sans-serif;font-weight:700;font-size:27px;margin:8px 0 2px;letter-spacing:-.01em}
  .sub{color:#a8c4b9;font-size:12.5px}
  .readout{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8fae9f;margin-top:4px}
  .stat .n.hot{color:#f0a79c}
  .verify-banner{background:var(--warn-bg);color:var(--warn-ink);border-left:1px solid var(--hair);border-right:1px solid var(--hair);
    padding:10px 18px;font-size:12.5px;font-weight:500}
  .verify-banner b{font-weight:700}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:12px 18px}
  .search input{width:100%;padding:11px 12px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:10px}
  .flabel{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-size:12.5px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:8px 11px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px}
  .row{padding:16px 18px;border-top:1px solid var(--hair)}
  .row:first-child{border-top:0}
  .head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
  .org{font-size:16px;font-weight:600;letter-spacing:-.005em}
  .region{font-size:12.5px;color:var(--muted)}
  .callby{margin-left:auto;font-family:'Commissioner',sans-serif;font-weight:700;font-size:12.5px;border-radius:6px;padding:4px 9px;background:var(--gold-bg);color:var(--gold)}
  .callby.now{background:var(--gap-bg);color:var(--hot)}
  .subline{font-size:12.5px;margin-top:6px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .subline b{color:var(--link-ink)}
  .renew{font-size:11px;font-weight:700;border-radius:5px;padding:2px 8px;background:var(--fresh-bg);color:var(--fresh)}
  .verify{color:var(--link-ink);text-decoration:none;font-weight:600}
  .verify:hover{text-decoration:underline}
  .lines{margin-top:10px;display:flex;flex-direction:column;gap:5px}
  .line{font-size:13px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
  .line.past{opacity:.55}
  .pill{font-size:11.5px;font-weight:600;border-radius:5px;padding:2px 8px;white-space:nowrap}
  .pill.has{background:var(--has-bg);color:var(--has)}
  .pill.warn{background:#f7e0dc;color:#b23b2e;font-weight:700}
  .pill.badfit{background:#f4d0cb;color:#8a1a10;font-weight:700;cursor:help}
  .pill.umbrella{background:#f6ecd2;color:#8a5a11;font-weight:600;cursor:help}
  .when{color:var(--muted);font-size:12.5px}
  .gaps{margin-top:9px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .gaps .lbl{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--gap);font-weight:700}
  .pill.gap{background:var(--gap-bg);color:var(--gap)}
  .empty{padding:34px;text-align:center;color:var(--muted);display:none}
  .foot{max-width:900px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text)}
  a.doc{font-size:12px;color:var(--link-ink);text-decoration:none}
  a.doc:hover{text-decoration:underline}
</style>
</head>
<body>
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <header class="desk">
    <div class="live-label">Accounts · ΚΗΜΔΗΣ</div>
    <h1>Account Map</h1>
    <div class="sub">Τι έχει αγοράσει κάθε φορέας, από ποιον, πότε λήγει — και τι δεν έχει αγοράσει ποτέ</div>
    <div class="readout">
      <div class="stat"><div class="n" id="s-org">0</div><div class="l">Φορείς</div></div>
      <div class="stat"><div class="n hot" id="s-now">0</div><div class="l">Call now (≤30 ημ.)</div></div>
      <div class="stat"><div class="n" style="font-size:15px">__STAMP__</div><div class="l">Δεδομένα έως</div></div>
    </div>
  </header>
  <div class="verify-banner">
    ⚠ <b>Πριν καλέσεις, επιβεβαίωσε.</b> Τα δεδομένα ΚΗΜΔΗΣ ανανεώνονται ~καθημερινά και μια απευθείας ανάθεση μπορεί να υπογραφεί οποτεδήποτε.
    Κάθε κάρτα δείχνει την <b>πιο πρόσφατη σύμβαση</b> και σύνδεσμο ελέγχου — πάτησέ τον πριν σηκώσεις το τηλέφωνο.
  </div>
  <div class="controls">
    <label class="search"><input id="q" type="search" placeholder="Αναζήτηση — φορέας, περιοχή, ανάδοχος, υπογράφων…"></label>
    <div class="filters">
      <span class="flabel">Λείπει</span><div class="seg" id="seg-gap"></div>
      <span class="flabel">Call by</span>
      <div class="seg">
        <button data-win="30" aria-pressed="false">30 ημ.</button>
        <button data-win="90" aria-pressed="false">90 ημ.</button>
        <button data-win="0" aria-pressed="true">Όλα</button>
      </div>
      <span class="flabel">Κατάσταση</span>
      <div class="seg">
        <button data-fresh="all" aria-pressed="true">Όλα</button>
        <button data-fresh="stable" aria-pressed="false">Χωρίς πρόσφατη ανανέωση</button>
      </div>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">Κανένας φορέας δεν ταιριάζει.</div>
</div>
<p class="foot">
  Από <b>ΚΗΜΔΗΣ</b>. «Call by» = <b>__LEAD__ μήνες πριν</b> τη λήξη της πιο πρόσφατης σύμβασης. Η λήξη υπολογίζεται από την <b>ημ. λήξης</b> ή, αν λείπει, από <b>ημ. υπογραφής + διάρκεια</b>.
  Το πράσινο <b>«ΑΝΑΝΕΩΘΗΚΕ»</b> σημαίνει ότι ο φορέας υπέγραψε πρόσφατα — <b>δεν</b> είναι ευκαιρία τώρα.
  «Δεν έχει» = δεν βρέθηκε σύμβαση με αυτούς τους CPV στο διάστημα που σαρώθηκε· επιβεβαίωσε πάντα στο έγγραφο/Διαύγεια.
</p>
<script>
const A = __DATA__, SERVICES = __SERVICES__;
const TODAY = new Date().toISOString().slice(0,10), DAY=86400000;
let gapFilter='all', win=0, freshMode='all';
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
const money=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
const dmy=s=>s?s.split('-').reverse().join('/'):'—';
const daysTo=s=>s?Math.ceil((new Date(s)-new Date(TODAY))/DAY):null;
const diavgeia=org=>'https://www.gov.gr/el/services/1001013/demosioteta-demosion-sumbaseon-kemdes';

document.getElementById('seg-gap').innerHTML =
  '<button data-gap="all" aria-pressed="true">Όλα</button>' +
  SERVICES.map(s=>'<button data-gap="'+s+'">'+s.split(' /')[0]+'</button>').join('');

function passes(a){
  if(gapFilter!=='all' && !a.gaps.includes(gapFilter)) return false;
  if(win){ const d=daysTo(a.call_by); if(d===null||d>win) return false; }
  if(freshMode==='stable' && a.renewed) return false;
  return true;
}
function render(){
  const q=qEl.value.trim().toLowerCase();
  let rows=A.filter(passes);
  if(q) rows=rows.filter(a=>((a.org||'')+' '+(a.region||'')+' '+(a.signer||'')+' '+
      a.has.map(h=>h.holder||'').join(' ')).toLowerCase().includes(q));
  listEl.innerHTML='';
  rows.slice(0,400).forEach(a=>{
    const d=daysTo(a.call_by), now=d!==null&&d<=30 && !a.renewed;
    const lines=a.has.map(h=>{
      const past = h.end && h.end < TODAY;
      return '<div class="line'+(past?' past':'')+'"><span class="pill has">'+h.s+'</span>'+
        (h.firm_bad_fit?'<span class="pill badfit" title="Το όνομα του αναδόχου δεν ταιριάζει με αυτή την υπηρεσία — επιβεβαίωσε στο ΚΗΜΔΗΣ πριν καλέσεις">⚠ ανάδοχος δεν ταιριάζει</span>':'')+
        (h.conflict?'<span class="pill warn">⚠ τίτλος: '+h.conflict+'</span>':'')+
        (h.umbrella?'<span class="pill umbrella" title="Ο CPV είναι γενικός (umbrella) — μπορεί να καλύπτει άλλη υπηρεσία, έλεγξε τη σύμβαση">⚠ CPV γενικός</span>':'')+
        '<span class="who">'+(h.holder||'—')+'</span>'+
        '<span class="when">'+(h.v?money(h.v):'')+(h.end?' · λήγει '+dmy(h.end):'')+(h.signed?' · υπ. '+dmy(h.signed):'')+'</span>'+
        (h.adam?' <a class="doc" target="_blank" rel="noopener" href="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+h.adam+'">σύμβαση ↗</a>':'')+
        '</div>';
    }).join('');
    const gaps=a.gaps.length?'<div class="gaps"><span class="lbl">Δεν έχει</span>'+
      a.gaps.map(g=>'<span class="pill gap">'+g+'</span>').join('')+'</div>':'';
    const renew=a.renewed?'<span class="renew">ΑΝΑΝΕΩΘΗΚΕ '+dmy(a.newest)+'</span>':'';
    const el=document.createElement('div'); el.className='row';
    el.innerHTML='<div class="head"><span class="org">'+a.org+'</span>'+
      '<span class="region">'+(a.region||'')+'</span>'+
      '<span class="callby'+(now?' now':'')+'">Call by '+dmy(a.call_by)+'</span></div>'+
      '<div class="subline">'+renew+
      (a.signer?'<span>Υπέγραψε: <b>'+a.signer+'</b></span>':'')+
      (a.newest?'<span>Τελευταία σύμβαση: '+dmy(a.newest)+'</span>':'')+
      (a.newest_adam?'<a class="verify" target="_blank" rel="noopener" href="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+a.newest_adam+'">Άνοιγμα τελευταίας σύμβασης ↗</a>':'')+'</div>'+
      '<div class="lines">'+lines+'</div>'+gaps;
    listEl.appendChild(el);
  });
  emptyEl.style.display=rows.length?'none':'block';
  document.getElementById('s-org').textContent=rows.length;
  document.getElementById('s-now').textContent=A.filter(a=>{const d=daysTo(a.call_by);return d!==null&&d<=30&&!a.renewed;}).length;
}
function wire(sel,fn){document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
  fn(b); document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed',x===b)); render();}));}
qEl.addEventListener('input',render);
wire('[data-gap]', b=>gapFilter=b.dataset.gap);
wire('[data-win]', b=>win=+b.dataset.win);
wire('[data-fresh]', b=>freshMode=b.dataset.fresh);
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
