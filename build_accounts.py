"""
Account Map — build docs/accounts.html

Flips the data from "list of contracts" to "state of each organisation":

    Δήμος X · signed by [name, role] · region
      HAS   Internal audit — LEVER A.E. — 30.000€ — expires 31/07/2026
      HAS   Financial audit — [firm] — expires …
      GAP   Risk management · DPO · Compliance      ← what to sell
      CALL BY  01/03/2026   (lead time before the earliest expiry)

Sorted by call-by date, so the top of the list is who to contact this month.

Data: ΚΗΜΔΗΣ contracts (public, no login). Run from GitHub Actions or locally.
"""

import os
import json
import time
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta

import requests

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"
OUT = "docs/accounts.html"

MONTHS_BACK  = 36     # how far back to look for signed contracts
LEAD_MONTHS  = 5      # be in front of them this many months before expiry
PAGE_PAUSE   = 0.7
TIMEOUT      = 45

# ─────────────────────── The cleaned CPV pool (noise removed) ───────────────────────
# Derived from real Διαύγεια data, not guesswork. Edit freely — this is your map.
SERVICES = {
    "Εσωτερικός έλεγχος": [
        "79212200-5",   # internal audit  (the core code)
        "79212000-3",   # auditing services
    ],
    "Οικονομικός έλεγχος / Ορκωτοί": [
        "79212100-4",   # financial audit  (59 hits — the ορκωτοί code)
        "79212300-6",   # statutory audit
        "79210000-9",   # accounting & auditing
        "79200000-6",   # accounting / fiscal
    ],
    "Διαχείριση κινδύνων": [
        "71317000-3",   # ⭐ risk protection & control consultancy
        "79212400-7",   # fraud audit
    ],
    "Συμμόρφωση / Whistleblowing": [
        "79410000-1",   # ⭐ compliance officer + ΥΠΠΑ (ν.4990/2022)
    ],
    "DPO / Προστασία δεδομένων": [
        "79417000-0",   # ⭐ DPO + security officer
    ],
    "Χαρτογράφηση / Οργάνωση": [
        "79411000-8",   # general management consultancy
        "72221000-0",   # business analysis consultancy
    ],
    # Borderline — uncomment if you want cyber-compliance advisory in scope:
    # "Κυβερνοασφάλεια (συμβουλευτική)": ["72246000-1"],
}

# Everything else the discovery turned up was noise and is deliberately excluded:
# furniture (39xxx), stationery (30xxx), medical/lab (33xxx), construction (45xxx),
# hardware & licences (32420000-3, 48xxx, 72253200-5, 72268000-1), maintenance (50xxx),
# transport (60xxx), telecom (64xxx), insurance (66xxx), R&D (73xxx),
# legal representation (79112000-2), guarding (79713000-5), events (79952000-2),
# cleaning/environment (90xxx), media (92xxx), social/health (85xxx).

ALL_CODES = sorted({c for codes in SERVICES.values() for c in codes})
SERVICE_OF = {c: s for s, codes in SERVICES.items() for c in codes}

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


# ─────────────────────────────── fetch ───────────────────────────────

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
        except Exception as e:
            fails += 1
            if fails >= 3:
                print(f"     … giving up on this window ({type(e).__name__})")
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


def parse(c):
    """Pull the fields that matter out of one contract record."""
    det = c.get("contractingDataDetails") or {}
    members = det.get("contractingMembersDataList") or []
    signer = (det.get("signers") or {}).get("value")

    # which of OUR services this contract belongs to (first matching CPV wins)
    service = None
    for obj in (c.get("objectDetailsList") or []):
        for cp in (obj.get("cpvs") or []):
            s = SERVICE_OF.get(str(cp.get("key", "")).strip())
            if s:
                service = s
                break
        if service:
            break

    return {
        "org":     (c.get("organization") or {}).get("value"),
        "orgkey":  (c.get("organization") or {}).get("key"),
        "region":  (c.get("nutsCode") or {}).get("value"),
        "service": service,
        "holder":  " / ".join(m.get("name", "") for m in members) or None,
        "signer":  signer,
        "value":   c.get("contractBudget") or c.get("totalCostWithoutVAT") or 0,
        "end":     (c.get("endDate") or "")[:10] or None,
        "signed":  (c.get("contractSignedDate") or "")[:10] or None,
        "adam":    c.get("referenceNumber"),
        "noend":   bool(c.get("noEndDate")),
    }


# ─────────────────────────────── build ───────────────────────────────

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
        print(f"     … {len(batch)} records, {len(rows)} usable so far")
    return rows


def build_accounts(rows):
    today = date.today()
    by_org = defaultdict(list)
    for r in rows:
        by_org[(r["orgkey"], r["org"])].append(r)

    accounts = []
    for (okey, oname), items in by_org.items():
        # latest contract per service line
        per_service = {}
        for r in items:
            s = r["service"]
            cur = per_service.get(s)
            if cur is None or (r["signed"] or "") > (cur["signed"] or ""):
                per_service[s] = r

        # who signs for this organisation (most recent signer we saw)
        signers = [r for r in items if r["signer"]]
        signers.sort(key=lambda r: r["signed"] or "", reverse=True)
        signer = signers[0]["signer"] if signers else None

        region = next((r["region"] for r in items if r["region"]), None)
        spend = sum(r["value"] or 0 for r in items)

        # earliest future expiry drives the call-by date
        future_ends = sorted(r["end"] for r in per_service.values()
                             if r["end"] and r["end"] >= today.isoformat())
        if future_ends:
            nxt = future_ends[0]
            call_by = (datetime.strptime(nxt, "%Y-%m-%d").date()
                       - timedelta(days=int(LEAD_MONTHS * 30.4))).isoformat()
            status = "expiring"
        else:
            past = sorted((r["end"] for r in per_service.values() if r["end"]), reverse=True)
            nxt = past[0] if past else None
            call_by = today.isoformat()      # already lapsed — they must re-buy
            status = "lapsed" if past else "unknown"

        has = sorted(per_service.keys())
        gaps = [s for s in SERVICES if s not in per_service]

        accounts.append({
            "org": oname, "region": region, "signer": signer,
            "spend": spend, "next_end": nxt, "call_by": call_by, "status": status,
            "has": [{"s": s, "holder": per_service[s]["holder"],
                     "v": per_service[s]["value"], "end": per_service[s]["end"],
                     "adam": per_service[s]["adam"]} for s in has],
            "gaps": gaps,
        })

    accounts.sort(key=lambda a: (a["call_by"], -a["spend"]))
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
            .replace("__STAMP__", athens.strftime("%d/%m · %H:%M")))
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
    --link:#1f6f6b;--link-ink:#155551;--live:#7ee0b4;
    --gap:#b23b2e;--gap-bg:#f7e0dc;--has:#2f6b4f;--has-bg:#e2efe8;--hot:#b23b2e;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter',Arial,sans-serif;line-height:1.5;padding:24px 16px 56px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:900px;margin:0 auto}
  .nav{max-width:900px;margin:0 auto 12px;display:flex;gap:8px;font-size:13px}
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
  .signer{font-size:13px;margin-top:6px}
  .signer b{color:var(--link-ink)}
  .lines{margin-top:10px;display:flex;flex-direction:column;gap:5px}
  .line{font-size:13px;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
  .pill{font-size:11.5px;font-weight:600;border-radius:5px;padding:2px 8px;white-space:nowrap}
  .pill.has{background:var(--has-bg);color:var(--has)}
  .who{color:var(--text)}
  .when{color:var(--muted);font-size:12.5px}
  .gaps{margin-top:9px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .gaps .lbl{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--gap);font-weight:700}
  .pill.gap{background:var(--gap-bg);color:var(--gap)}
  .empty{padding:34px;text-align:center;color:var(--muted)}
  .foot{max-width:900px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text)}
  a.doc{font-size:12px;color:var(--link-ink);text-decoration:none}
  a.doc:hover{text-decoration:underline}
</style>
</head>
<body>
<nav class="nav">
  <a href="index.html">Open tenders</a>
  <a href="expiry.html">Expiry radar</a>
  <a href="accounts.html" class="on">Account map</a>
</nav>
<div class="wrap">
  <header class="desk">
    <div class="live-label">Accounts · ΚΗΜΔΗΣ</div>
    <h1>Account Map</h1>
    <div class="sub">Τι έχει αγοράσει κάθε φορέας, από ποιον, πότε λήγει — και τι δεν έχει αγοράσει ποτέ</div>
    <div class="readout">
      <div class="stat"><div class="n" id="s-org">0</div><div class="l">Φορείς</div></div>
      <div class="stat"><div class="n hot" id="s-now">0</div><div class="l">Call now (≤30 ημ.)</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Updated</div></div>
    </div>
  </header>
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
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty" style="display:none">Κανένας φορέας δεν ταιριάζει.</div>
</div>
<p class="foot">
  Από <b>ΚΗΜΔΗΣ</b>. «Call by» = <b>__LEAD__ μήνες πριν</b> τη λήξη της πρώτης σύμβασης, ώστε να είσαι μπροστά όταν καταρτίζεται ο προϋπολογισμός.
  <b>Προσοχή:</b> «δεν έχει αγοράσει» σημαίνει ότι δεν βρέθηκε σύμβαση με αυτούς τους CPV στο διάστημα που σαρώθηκε — μπορεί να υπάρχει με άλλο CPV ή παλαιότερη.
  Ο «υπογράφων» είναι το πρόσωπο που υπέγραψε την τελευταία σύμβαση για τον φορέα.
</p>
<script>
const A = __DATA__, SERVICES = __SERVICES__;
const TODAY = new Date().toISOString().slice(0,10), DAY=86400000;
let gapFilter='all', win=0;
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
const money=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
const dmy=s=>s?s.split('-').reverse().join('/'):'—';
const daysTo=s=>s?Math.ceil((new Date(s)-new Date(TODAY))/DAY):null;

document.getElementById('seg-gap').innerHTML =
  '<button data-gap="all" aria-pressed="true">Όλα</button>' +
  SERVICES.map(s=>'<button data-gap="'+s+'">'+s.split(' /')[0]+'</button>').join('');

function passes(a){
  if(gapFilter!=='all' && !a.gaps.includes(gapFilter)) return false;
  if(win){ const d=daysTo(a.call_by); if(d===null||d>win) return false; }
  return true;
}
function render(){
  const q=qEl.value.trim().toLowerCase();
  let rows=A.filter(passes);
  if(q) rows=rows.filter(a=>((a.org||'')+' '+(a.region||'')+' '+(a.signer||'')+' '+
      a.has.map(h=>h.holder||'').join(' ')).toLowerCase().includes(q));
  listEl.innerHTML='';
  rows.slice(0,400).forEach(a=>{
    const d=daysTo(a.call_by), now=d!==null&&d<=30;
    const lines=a.has.map(h=>
      '<div class="line"><span class="pill has">'+h.s+'</span>'+
      '<span class="who">'+(h.holder||'—')+'</span>'+
      '<span class="when">'+(h.v?money(h.v):'')+(h.end?' · λήγει '+dmy(h.end):'')+'</span>'+
      (h.adam?' <a class="doc" target="_blank" rel="noopener" href="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+h.adam+'">σύμβαση ↗</a>':'')+
      '</div>').join('');
    const gaps=a.gaps.length?'<div class="gaps"><span class="lbl">Δεν έχει</span>'+
      a.gaps.map(g=>'<span class="pill gap">'+g+'</span>').join('')+'</div>':'';
    const el=document.createElement('div'); el.className='row';
    el.innerHTML='<div class="head"><span class="org">'+a.org+'</span>'+
      '<span class="region">'+(a.region||'')+'</span>'+
      '<span class="callby'+(now?' now':'')+'">Call by '+dmy(a.call_by)+'</span></div>'+
      (a.signer?'<div class="signer">Υπέγραψε: <b>'+a.signer+'</b></div>':'')+
      '<div class="lines">'+lines+'</div>'+gaps;
    listEl.appendChild(el);
  });
  emptyEl.style.display=rows.length?'none':'block';
  document.getElementById('s-org').textContent=rows.length;
  document.getElementById('s-now').textContent=A.filter(a=>{const d=daysTo(a.call_by);return d!==null&&d<=30;}).length;
}
function wire(sel,fn){document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
  fn(b); document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed',x===b)); render();}));}
qEl.addEventListener('input',render);
wire('[data-gap]', b=>gapFilter=b.dataset.gap);
wire('[data-win]', b=>win=+b.dataset.win);
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
