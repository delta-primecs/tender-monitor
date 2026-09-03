"""
Regulatory Radar — build docs/regulation.html
Watches ONLY the two authoritative bodies (resolved, not guessed):
    ΕΑΔ  (Εθνική Αρχή Διαφάνειας)  → 100051206
    ΥΠΕΣ (Υπουργείο Εσωτερικών)    → 100054492
for circulars / opinions / normative acts that create or clarify obligations
in your service lines. Legality-review / elections / πόθεν-έσχες noise excluded.

New requirement appears here → cross-reference the Account Map for every Δήμο
that doesn't have that service yet → those are your calls, with a real reason.
"""

import os
import json
import time
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://diavgeia.gov.gr/luminapi/opendata"
OUT = "docs/regulation.html"

# The bodies to watch. IDs resolved from Διαύγεια, verified against real records.
ORGS = {
    "100051206": "ΕΑΔ",       # Εθνική Αρχή Διαφάνειας — writes the standards
    "100054492": "ΥΠΕΣ",      # Υπουργείο Εσωτερικών — the starting-gun circulars
    "14065":     "Ελ.Συν.",   # Ελεγκτικό Συνέδριο — court decisions & procurement
}

# Bodies whose ENTIRE output is by mandate relevant to your services.
# For these we skip topic-filtering — trust the body, don't second-guess.
# ΕΑΔ is *the* authority for internal audit & integrity in Greek public sector,
# so filtering its output was silently dropping the most important source.
# NOTE: Ελ.Συν. is DELIBERATELY not here. Its Διαύγεια feed is mostly
# administrative housekeeping (travel, payments, procurement); its actual
# audit πορίσματα on Δήμοι live on elsyn.gr and need a separate scraper.
# The topic filter keeps this feed clean without silencing the source.
TRUST_ORGS = {"ΕΑΔ"}

# Regulatory decision types.
REG_TYPES = {
    "Α.3":   "Εγκύκλιος",
    "Α.4":   "Γνωμοδότηση",
    "Α.2":   "Κανονιστική πράξη",
    "2.4.1": "Κανονιστικό",
}

# For ΥΠΕΣ (which publishes across many fields — elections, personnel, etc.)
# keep only subjects touching your world OR the alliance's (tax/accounting).
TOPIC_HINTS = [
    # audit / risk / integrity
    "εσωτερικ", "έλεγχ", "ελεγκτ", "μονάδα εσωτερικ",
    "διαχείριση κινδύν", "διαχείρισης κινδύν", "κινδύν",
    "συμμόρφωσ", "ακεραιότ", "δικλίδ", "whistlebl", "διαύλ",
    "χαρτογράφησ", "ορκωτ", "δημοσιονομικ",
    # data protection
    "προστασία δεδομέν", "δεδομένων προσωπ", "gdpr", "dpo", "γκπδ",
    # financial / accounting / tax  (alliance)
    "λογιστ", "φορολογ", "μισθοδοσ", "προϋπολογισμ", "οικονομικ",
    "διπλογραφικ", "ισολογισμ", "απολογισμ",
    # laws we care about
    "4795", "4990", "5013", "4624",
]
# Explicit noise to drop even if a hint matches.
EXCLUDE = ["νομιμότητ", "εκλογ", "πόθεν", "πειθαρχ", "αντικαπν", "εμβολιασ"]

PAGES = 4     # per org+type; circulars are low-volume so this covers months
PAUSE = 0.5

SESSION = requests.Session()
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]))))
except Exception:
    pass


def search(q, page, size=100):
    params = {"q": q, "size": size, "page": page, "sort": "recent"}
    r = SESSION.get(f"{BASE}/search/advanced", params=params,
                    headers={"Accept": "application/json"}, timeout=45)
    r.raise_for_status()
    d = r.json()
    return d.get("decisions") or d.get("results") or []


def as_date(rec):
    for f in ("publishTimestamp", "issueDate", "submissionTimestamp"):
        v = rec.get(f)
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v / 1000).strftime("%Y-%m-%d")
    return None


def relevant(subject):
    s = (subject or "").lower()
    if any(x in s for x in EXCLUDE):
        return False
    return any(h in s for h in TOPIC_HINTS)


def collect():
    found = {}
    for org_id, org_label in ORGS.items():
        for tuid, tlabel in REG_TYPES.items():
            q = f'organizationUid:"{org_id}" AND decisionTypeUid:"{tuid}"'
            for page in range(PAGES):
                try:
                    recs = search(q, page)
                except Exception:
                    break
                if not recs:
                    break
                for rec in recs:
                    # Trust ΕΑΔ's whole output; filter others by topic.
                    if org_label not in TRUST_ORGS and not relevant(rec.get("subject")):
                        continue
                    ada = rec.get("ada")
                    if not ada or ada in found:
                        continue
                    found[ada] = {
                        "date": as_date(rec),
                        "org": org_label,
                        "type": tlabel,
                        "subject": (rec.get("subject") or "").strip().replace("\n", " "),
                        "ada": ada,
                    }
                time.sleep(PAUSE)
    items = [v for v in found.values() if v["date"]]
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def main():
    items = collect()
    os.makedirs("docs", exist_ok=True)
    athens = datetime.now(timezone(timedelta(hours=3)))
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", athens.strftime("%d/%m/%Y %H:%M")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT}: {len(items)} regulatory items from ΕΑΔ + ΥΠΕΣ.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Regulatory Radar</title>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --page:#0a0e14;--panel:#0f141c;--panel-2:#131a24;--card:#0f141c;
    --text:#d4dae3;--bright:#f0f4f9;--muted:#5f6e82;--hair:#1c2530;--hair2:#26313f;
    --accent:#3ddc84;--accent-dim:#1f5f3f;--live:#3ddc84;
    --ink:#0f141c;--ink-2:#0f141c;
    --signal:#e8a13a;--signal-bg:#2a2010;--link:#5db0ff;--link-ink:#5db0ff;
    --hot:#ff5d52;--hot-bg:#2a1210;--warn:#e8a13a;--warn-bg:#2a2010;
    --has:#3ddc84;--has-bg:#0f2418;--gap-c:#ff5d52;--gap-bg:#2a1210;
    --c-audit:#3ddc84;--c-audit-bg:#0f2418;--c-acct:#5db0ff;--c-acct-bg:#12233a;
    --c-cons:#c58be0;--c-cons-bg:#241a2e;
    --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:var(--mono);line-height:1.5;padding:24px 16px 56px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:none;margin:0 auto}
  .nav{max-width:none;margin:0 auto 12px;display:flex;gap:8px;font-size:13px;flex-wrap:wrap}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:var(--card)}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:var(--panel);color:var(--text);border:1px solid var(--hair);padding:22px 24px 20px}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#d8c3a8;font-weight:600}
  h1{font-family:var(--mono);font-weight:700;font-size:27px;margin:8px 0 2px;letter-spacing:-.01em}
  .sub{color:#cdbfac;font-size:12.5px}
  .readout{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}
  .stat .n{font-family:var(--mono);font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#b7a68f;margin-top:4px}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:12px 18px}
  .search input{width:100%;padding:11px 12px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;background:var(--page)}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:10px}
  .flabel{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-size:12.5px;font-weight:500;color:var(--muted);background:var(--card);border:0;padding:8px 11px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;}
  .row{padding:14px 18px;border-top:1px solid var(--hair);display:flex;gap:12px;align-items:flex-start}
  .row:first-child{border-top:0}
  .row a.block{flex:1;text-decoration:none;color:inherit}
  .row:hover{background:#faf8f5}
  .chips{display:flex;gap:7px;margin-bottom:5px;flex-wrap:wrap}
  .b{font-size:11px;font-weight:700;border-radius:5px;padding:2px 8px}
  .b.ΕΑΔ{background:var(--ead-bg);color:var(--ead)}
  .b.ΥΠΕΣ{background:var(--ypes-bg);color:var(--ypes)}
  .t{font-size:11px;font-weight:600;border-radius:5px;padding:2px 8px;background:var(--type-bg);color:var(--type)}
  .subject{font-size:14px;font-weight:500}
  .open{font-size:12.5px;color:var(--link-ink);font-weight:600;margin-top:5px;display:inline-block}
  .date{font-size:12px;color:var(--muted);white-space:nowrap;margin-top:2px}
  .empty{padding:40px 24px;text-align:center;color:var(--muted);font-size:14px}
  .empty b{color:var(--text)}
  .foot{max-width:none;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text)}
</style>
</head>
<body>
<link rel="stylesheet" href="godel.css">
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <header class="desk">
    <div class="live-label">Regulation · ΕΑΔ + ΥΠΕΣ · Διαύγεια</div>
    <h1>Regulatory Radar</h1>
    <div class="sub">Εγκύκλιοι & γνωμοδοτήσεις που γεννούν υποχρεώσεις — η αφετηρία κάθε νέας σύμβασης</div>
    <div class="readout">
      <div class="stat"><div class="n" id="s-all">0</div><div class="l">Items</div></div>
      <div class="stat"><div class="n" id="s-90">0</div><div class="l">Last 90 days</div></div>
      <div class="stat"><div class="n" style="font-size:15px">__STAMP__</div><div class="l">Updated</div></div>
    </div>
  </header>
  <div class="controls">
    <label class="search"><input id="q" type="search" placeholder="Αναζήτηση θέματος…"></label>
    <div class="filters">
      <span class="flabel">Φορέας</span>
      <div class="seg">
        <button data-org="all" aria-pressed="true">Όλοι</button>
        <button data-org="ΕΑΔ" aria-pressed="false">ΕΑΔ</button>
        <button data-org="ΥΠΕΣ" aria-pressed="false">ΥΠΕΣ</button>
      </div>
      <span class="flabel">Διάστημα</span>
      <div class="seg">
        <button data-win="90" aria-pressed="false">90 ημ.</button>
        <button data-win="365" aria-pressed="false">1 έτος</button>
        <button data-win="0" aria-pressed="true">Όλα</button>
      </div>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty" style="display:none"></div>
</div>
<p class="foot">
  Μόνο από <b>ΕΑΔ</b> και <b>ΥΠΕΣ</b> · εγκύκλιοι/γνωμοδοτήσεις/κανονιστικά στους τομείς σου · εξαιρείται ο έλεγχος νομιμότητας, εκλογές, πόθεν έσχες.
  Μια νέα υποχρέωση εδώ = λόγος να καλέσεις κάθε Δήμο που δεν την έχει καλύψει ακόμη (δες Account map).
</p>
<script>
const REG = __DATA__;
const TODAY = new Date().toISOString().slice(0,10), DAY=86400000;
let orgFilter='all', win=0;
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
const dmy=s=>s?s.split('-').reverse().join('/'):'—';
const daysAgo=s=>s?Math.round((new Date(TODAY)-new Date(s))/DAY):null;

function passes(e){
  if(orgFilter!=='all' && e.org!==orgFilter) return false;
  if(win){ const d=daysAgo(e.date); if(d===null||d>win) return false; }
  return true;
}
function render(){
  const q=qEl.value.trim().toLowerCase();
  let rows=REG.filter(passes);
  if(q) rows=rows.filter(e=>(e.subject||'').toLowerCase().includes(q));
  listEl.innerHTML='';
  if(!REG.length){
    emptyEl.style.display='block';
    emptyEl.innerHTML='<b>Καμία εγγραφή.</b><br>Ίσως χρειάζεται προσαρμογή στα φίλτρα θεμάτων — πες μου τι λείπει.';
    return;
  }
  rows.slice(0,300).forEach(e=>{
    const el=document.createElement('div'); el.className='row';
    const d=daysAgo(e.date);
    const ago=d===0?'σήμερα':(d===1?'χθες':'πριν '+d+' ημ.');
    el.innerHTML='<a class="block" target="_blank" rel="noopener" href="https://diavgeia.gov.gr/doc/'+e.ada+'">'+
      '<div class="chips"><span class="b '+e.org+'">'+e.org+'</span><span class="t">'+e.type+'</span></div>'+
      '<div class="subject">'+(e.subject||'')+'</div>'+
      '<div class="open">Άνοιγμα στη Διαύγεια ↗</div></a>'+
      '<div class="date">'+dmy(e.date)+'<br>'+ago+'</div>';
    listEl.appendChild(el);
  });
  emptyEl.style.display=rows.length?'none':'block';
  if(rows.length===0) emptyEl.innerHTML='Καμία εγγραφή δεν ταιριάζει με τα φίλτρα.';
  document.getElementById('s-all').textContent=REG.length;
  document.getElementById('s-90').textContent=REG.filter(e=>{const d=daysAgo(e.date);return d!==null&&d<=90;}).length;
}
function wire(sel,fn){document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
  fn(b); document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed',x===b)); render();}));}
qEl.addEventListener('input',render);
wire('[data-org]', b=>orgFilter=b.dataset.org);
wire('[data-win]', b=>win=+b.dataset.win);
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
