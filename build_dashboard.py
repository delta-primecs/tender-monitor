"""
Tender Radar — build the public search platform (docs/index.html).
Pulls open public tenders from ΚΗΜΔΗΣ (which already includes ΕΣΗΔΗΣ) across
your professional categories, tags each one, and renders a branded, filterable
search page. Static + free + always-on. Public data, no login. (~daily refresh.)
"""
import os
import sys
import json
import time
from datetime import date, datetime, timezone, timedelta

import requests

NOTICE_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/notice"
OUT = "docs/index.html"

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

# ── YOUR BRAND ──  put your firm name here (or leave "" to hide it)
FIRM_NAME = ""

# ── WHAT TO WATCH ──  CPV codes grouped into categories users can filter by.
# Add your partners' verticals here anytime (e.g. IT: 72xxx, Legal: 79100000-5).
CPV_CATEGORIES = {
    "Έλεγχος": [
        "79212000-3", "79212100-4", "79212200-5",
        "79212300-6", "79212400-7", "79212500-8",
    ],
    "Λογιστικά & Φορολογικά": [
        "79200000-6", "79210000-9", "79211000-6", "79211100-7",
        "79220000-2", "79221000-9", "79222000-6",
    ],
    "Συμβουλευτική": [
        "79400000-8", "79410000-1", "79411000-8", "79411100-9",
        "79412000-5", "79413000-2", "79414000-9", "79418000-7", "79419000-4",
    ],
}

COMPETITIVE_PROCEDURES = {
    "Ανοιχτή διαδικασία", "Κλειστή διαδικασία",
    "Ανταγωνιστική διαδικασία με διαπραγμάτευση", "Ανταγωνιστικός διάλογος",
    "Διαπραγμάτευση με προηγούμενη προκήρυξη διαγωνισμού (αρ.266)",
    "Σύμπραξη καινοτομίας",
}


def fetch_notices(codes):
    body = {"cpvItems": codes,
            "dateFrom": (date.today() - timedelta(days=179)).isoformat()}
    out, page, fails = [], 0, 0
    while True:
        try:
            r = SESSION.post(f"{NOTICE_URL}?page={page}", json=body,
                             headers={"Accept": "application/json"}, timeout=90)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            fails += 1
            print(f"     page {page} failed ({type(e).__name__}); retry {fails}")
            if fails >= 3:
                print("     giving up on this category, keeping what we have")
                break               # skip category, DON'T crash the whole build
            time.sleep(8 * fails)
            continue
        fails = 0
        out.extend(data.get("content", []))
        if data.get("last", True):
            break
        page += 1
        if page > 30:
            break
        time.sleep(0.4)
    return out


def to_item(n):
    proc = (n.get("typeOfProcedure") or {}).get("value")
    return {
        "s": (n.get("title") or "").strip(),
        "adam": n.get("referenceNumber"),
        "deadline": n.get("finalSubmissionDate"),
        "amount": n.get("totalCostWithoutVAT"),
        "org": (n.get("organization") or {}).get("value"),
        "proc": proc,
        "kind": "competition" if proc in COMPETITIVE_PROCEDURES else "direct",
        "cats": [],
    }


def collect():
    by_adam = {}
    for cat, codes in CPV_CATEGORIES.items():
        for n in fetch_notices(codes):
            item = to_item(n)
            adam = item["adam"]
            if not adam:
                continue
            if adam not in by_adam:
                by_adam[adam] = item
            if cat not in by_adam[adam]["cats"]:
                by_adam[adam]["cats"].append(cat)
    today = date.today().isoformat()
    items = [t for t in by_adam.values()
             if t.get("deadline") and t["deadline"][:10] >= today]
    items.sort(key=lambda x: x["deadline"] or "9999")
    return items


def build_html(items):
    athens = datetime.now(timezone(timedelta(hours=3)))
    stamp = athens.strftime("%d/%m · %H:%M")
    firm = f" · {FIRM_NAME}" if FIRM_NAME else ""
    cats = json.dumps(list(CPV_CATEGORIES.keys()), ensure_ascii=False)
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp)
            .replace("__FIRM__", firm)
            .replace("__CATS__", cats))


def main():
    items = collect()
    # SAFETY GUARD: never replace a good page with an empty one. If we got zero
    # tenders, something upstream is wrong (API hiccup/change) — keep the last
    # good page and fail loudly so the workflow goes red and alerts us.
    if not items:
        print("REFUSING to publish: 0 tenders returned. Keeping the last good page.")
        sys.exit(1)
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html(items))
    print(f"Wrote {OUT}: {len(items)} open tenders across {len(CPV_CATEGORIES)} categories.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tender Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --page:#0a0e14;--panel:#0f141c;--panel-2:#131a24;--card:#0f141c;
    --text:#d4dae3;--bright:#f0f4f9;--muted:#5f6e82;--hair:#1c2530;--hair2:#26313f;
    --accent:#3ddc84;--accent-dim:#1f5f3f;--live:#3ddc84;
    --signal:#e8a13a;--signal-bg:#2a2010;--link:#5db0ff;--link-ink:#5db0ff;
    --hot:#ff5d52;--hot-bg:#2a1210;--warn:#e8a13a;--warn-bg:#2a2010;
    --c-audit:#3ddc84;--c-audit-bg:#0f2418;--c-acct:#5db0ff;--c-acct-bg:#12233a;
    --c-cons:#c58be0;--c-cons-bg:#241a2e;
    --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:var(--mono);
       line-height:1.5;-webkit-font-smoothing:antialiased;padding:14px 12px 40px;font-size:13px}
  .wrap{max-width:none;margin:0 auto}
  .nav{max-width:none;margin:0 auto 8px}
  .desk{background:var(--panel);color:var(--text);border:1px solid var(--hair);
       padding:14px 18px;display:flex;align-items:center;gap:18px;flex-wrap:wrap;position:relative}
  .top{display:flex;align-items:center;gap:8px}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--live);
       box-shadow:0 0 6px var(--live);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  .live-label{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);font-weight:700}
  h1{font-family:var(--mono);font-weight:700;font-size:18px;letter-spacing:.02em;margin:0;
     color:var(--bright);text-transform:uppercase}
  .sub{color:var(--muted);font-size:11px;flex-basis:100%;order:5;margin-top:-6px}
  .readout{display:flex;flex-wrap:wrap;gap:24px;margin-left:auto;align-items:center}
  .stat{text-align:right;padding-left:24px;border-left:1px solid var(--hair2)}
  .stat:first-child{border-left:0;padding-left:0}
  .stat .n{font-family:var(--mono);font-size:20px;font-weight:700;line-height:1;color:var(--bright)}
  .stat .l{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:3px}
  .stat .n.hot{color:var(--hot)}
  .controls{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:12px 18px}
  .controls.top{padding-bottom:8px}
  .search{position:relative;display:block}
  .search input{width:100%;padding:9px 12px 9px 34px;border:1px solid var(--hair2);
       font:inherit;font-family:var(--mono);font-size:13px;color:var(--text);background:var(--page)}
  .search input::placeholder{color:var(--muted)}
  .search input:focus{outline:1px solid var(--accent);border-color:var(--accent)}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.4}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  .fgroup{display:flex;align-items:center;gap:7px}
  .flabel{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair2);overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);
       background:var(--page);border:0;padding:6px 11px;cursor:pointer;border-left:1px solid var(--hair2);
       text-transform:uppercase;letter-spacing:.03em}
  .seg button:first-child{border-left:0}
  .seg button:hover{color:var(--text)}
  .seg button[aria-pressed="true"]{background:var(--accent-dim);color:var(--accent)}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0}
  .row{display:block;padding:12px 18px;border-top:1px solid var(--hair);text-decoration:none;color:inherit}
  .row:first-child{border-top:0}
  .row:nth-child(even){background:var(--panel-2)}
  .row:hover{background:#161d28}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:6px;flex-wrap:wrap}
  .clock{font-size:10.5px;font-weight:700;padding:3px 8px;color:var(--muted);background:var(--panel-2);
       text-transform:uppercase;letter-spacing:.04em}
  .clock.hot{color:var(--hot);background:var(--hot-bg)}
  .clock.warn{color:var(--warn);background:var(--warn-bg)}
  .amount{font-family:var(--mono);font-weight:700;font-size:12.5px;color:var(--signal);
       background:var(--signal-bg);padding:3px 9px}
  .amount.unknown{color:var(--muted);background:var(--panel-2);font-weight:600}
  .cat{font-size:10.5px;font-weight:600;padding:3px 8px;text-transform:uppercase;letter-spacing:.03em}
  .cat.Audit{color:var(--c-audit);background:var(--c-audit-bg)}
  .cat.Accounting{color:var(--c-acct);background:var(--c-acct-bg)}
  .cat.Consulting{color:var(--c-cons);background:var(--c-cons-bg)}
  .proc{font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.02em;text-transform:uppercase}
  .proc.win{color:var(--c-audit)}
  .subject{font-size:14px;font-weight:500;color:var(--bright)}
  .meta{display:flex;gap:14px;align-items:center;margin-top:8px;flex-wrap:wrap}
  .org{font-size:11.5px;color:var(--muted)}
  .open{font-size:12px;color:var(--link);font-weight:600;display:inline-flex;align-items:center;gap:4px;margin-left:auto}
  .row:hover .open{text-decoration:underline}
  .empty{padding:34px 18px;text-align:center;color:var(--muted);font-size:13px;display:none}
  .foot{max-width:none;margin:12px auto 0;color:var(--muted);font-size:11px;line-height:1.55}
  .foot b{color:var(--text);font-weight:600}
  @media (max-width:520px){h1{font-size:16px}.readout{gap:16px}.open{margin-left:0}}
</style>
</head>
<body>
<link rel="stylesheet" href="godel.css">
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <header class="desk">
    <div class="top"><span class="dot" aria-hidden="true"></span><span class="live-label">Live · ΚΗΜΔΗΣ + ΕΣΗΔΗΣ</span></div>
    <h1>Tender Radar</h1>
    <div class="sub">Ανοιχτοί δημόσιοι διαγωνισμοί__FIRM__</div>
    <div class="readout">
      <div class="stat"><div class="n" id="stat-shown">0</div><div class="l">Εμφανίζονται</div></div>
      <div class="stat"><div class="n hot" id="stat-closing">0</div><div class="l">Closing ≤ 3 days</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Ενημερώθηκε</div></div>
    </div>
  </header>
  <div class="controls top">
    <label class="search">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Αναζήτηση — δήμος, νοσοκομείο, λέξη-κλειδί, ΑΔΑΜ…" aria-label="Αναζήτηση διαγωνισμών">
    </label>
  </div>
  <div class="controls filters">
    <div class="fgroup"><span class="flabel">Area</span><div class="seg" id="seg-cat" role="group" aria-label="Category"></div></div>
    <div class="fgroup"><span class="flabel">Type</span>
      <div class="seg" role="group" aria-label="Procedure">
        <button data-proc="all" aria-pressed="true">Όλα</button>
        <button data-proc="competition" aria-pressed="false">Competitions</button>
        <button data-proc="direct" aria-pressed="false">Direct</button>
      </div>
    </div>
    <div class="fgroup"><span class="flabel">Min €</span>
      <div class="seg" role="group" aria-label="Minimum value">
        <button data-min="0" aria-pressed="true">Οποιαδήποτε</button>
        <button data-min="10000" aria-pressed="false">10k+</button>
        <button data-min="30000" aria-pressed="false">30k+</button>
      </div>
    </div>
    <div class="fgroup"><span class="flabel">Ταξινόμηση</span>
      <div class="seg" role="group" aria-label="Sort">
        <button data-sort="deadline" aria-pressed="true">Closing</button>
        <button data-sort="value" aria-pressed="false">Αξία</button>
      </div>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">Καμία εγγραφή δεν ταιριάζει με τα φίλτρα.</div>
</div>
<p class="foot">
  Live from <b>ΚΗΜΔΗΣ</b> (which already includes ΕΣΗΔΗΣ tenders) · open tenders only, deadline not passed.
  <b>Competitions</b> = open/restricted procedures anyone can win; <b>Direct</b> = απευθείας ανάθεση, often pre-arranged.
  Refreshes ~daily; amounts are the official estimate ex-VAT — always open the document to confirm.
</p>
<script>
  const TENDERS = __DATA__;
  const CATS = __CATS__;
  const NOW=Date.now(),DAY=86400000;
  let catFilter='all', procFilter='all', minValue=0, sortMode='deadline';
  const listEl=document.getElementById('list'),emptyEl=document.getElementById('empty'),qEl=document.getElementById('q');
  const fmtMoney=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
  const catClass=c=>c.startsWith('Account')?'Accounting':(c.startsWith('Consult')?'Consulting':'Audit');
  function daysLeft(iso){ if(!iso) return null; return Math.ceil((new Date(iso).getTime()-NOW)/DAY); }
  function clockLabel(iso){
    const d=daysLeft(iso); if(d===null) return {t:'—',c:''};
    if(d<=0) return {t:'κλείνει σήμερα',c:'hot'};
    if(d===1) return {t:'κλείνει αύριο',c:'hot'};
    if(d<=3) return {t:'σε '+d+' ημέρες',c:'hot'};
    if(d<=7) return {t:'σε '+d+' ημέρες',c:'warn'};
    return {t:'σε '+d+' ημέρες',c:''};
  }
  function passes(t){
    if(catFilter!=='all' && !(t.cats||[]).includes(catFilter)) return false;
    if(procFilter!=='all' && t.kind!==procFilter) return false;
    if((t.amount||0) < minValue) return false;
    return true;
  }
  function render(){
    const q=qEl.value.trim().toLowerCase();
    let rows=TENDERS.filter(passes);
    if(q)rows=rows.filter(t=>((t.s||'')+' '+(t.org||'')+' '+(t.adam||'')+' '+(t.cats||[]).join(' ')).toLowerCase().includes(q));
    if(sortMode==='value')rows.sort((a,b)=>(b.amount||-1)-(a.amount||-1));
    else rows.sort((a,b)=>(a.deadline||'9999').localeCompare(b.deadline||'9999'));
    listEl.innerHTML='';
    rows.forEach((t,idx)=>{
      const a=document.createElement('a');a.className='row';
      a.href='https://cerpp.eprocurement.gov.gr/khmdhs-opendata/notice/attachment/'+t.adam;
      a.target='_blank';a.rel='noopener';a.style.animationDelay=Math.min(idx*14,280)+'ms';
      const ck=clockLabel(t.deadline);
      const clock='<span class="clock '+ck.c+'">'+ck.t+'</span>';
      const amt=t.amount!=null?'<span class="amount">'+fmtMoney(t.amount)+'</span>':'<span class="amount unknown">Χωρίς αξία</span>';
      const cats=(t.cats||[]).map(c=>'<span class="cat '+catClass(c)+'">'+c+'</span>').join('');
      const proc=t.proc?'<span class="proc'+(t.kind==='competition'?' win':'')+'">'+t.proc+'</span>':'';
      a.innerHTML='<div class="chips">'+clock+amt+cats+proc+'</div><div class="subject">'+(t.s||'(χωρίς τίτλο)')+'</div>'+
        '<div class="meta"><span class="org">'+(t.org||'')+'</span>'+
        '<span class="open">Άνοιγμα εγγράφου <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
    document.getElementById('stat-shown').textContent=rows.length;
    document.getElementById('stat-closing').textContent=rows.filter(t=>{const d=daysLeft(t.deadline);return d!==null&&d<=3;}).length;
  }
  // build category buttons
  const segCat=document.getElementById('seg-cat');
  segCat.innerHTML='<button data-cat="all" aria-pressed="true">Όλα</button>'+
    CATS.map(c=>'<button data-cat="'+c+'" aria-pressed="false">'+c+'</button>').join('');
  function wire(sel, apply){
    document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
      apply(b);
      document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed', x===b));
      render();
    }));
  }
  qEl.addEventListener('input',render);
  wire('[data-cat]',  b=>catFilter=b.dataset.cat);
  wire('[data-proc]', b=>procFilter=b.dataset.proc);
  wire('[data-min]',  b=>minValue=+b.dataset.min);
  wire('[data-sort]', b=>sortMode=b.dataset.sort);
  render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
