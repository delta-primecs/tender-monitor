"""
Build the Audit Tender Desk dashboard — ΚΗΜΔΗΣ backbone.
Pulls the full audit CPV family from the ΚΗΜΔΗΣ open-data API, keeps only
tenders whose bidding deadline hasn't passed, and writes docs/index.html
for GitHub Pages. Public data, no login. (ΚΗΜΔΗΣ refreshes ~once a day.)
"""
import os
import json
from datetime import date, datetime, timezone, timedelta

import requests

NOTICE_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/notice"
DOC_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/notice/attachment/"
OUT = "docs/index.html"

# The audit CPV family to watch.
CPVS = [
    "79212100-4",  # Financial audit
    "79212200-5",  # Internal audit
    "79212000-3",  # Auditing
    "79212300-6",  # Statutory audit
    "79212400-7",  # Fraud audit
    "79212500-8",  # Accounting review
]


def fetch_open_notices():
    """Fetch recent audit notices, then keep only the ones still open to bid."""
    body = {
        "cpvItems": CPVS,
        # Proven-working filter: registration-date window (server caps it at 180 days).
        "dateFrom": (date.today() - timedelta(days=179)).isoformat(),
    }
    raw, page = [], 0
    while True:
        r = requests.post(f"{NOTICE_URL}?page={page}", json=body,
                          headers={"Accept": "application/json"}, timeout=60)
        r.raise_for_status()
        data = r.json()
        for n in data.get("content", []):
            raw.append(to_item(n))
        if data.get("last", True):
            break
        page += 1
        if page > 30:   # safety valve
            break
    # Keep only tenders whose deadline hasn't passed. We filter here in Python
    # (not via the API) because the server rejects the deadline parameter in
    # some date formats — this way is reliable.
    today = date.today().isoformat()
    return [t for t in raw if t.get("deadline") and t["deadline"][:10] >= today]


def to_item(n):
    obj = (n.get("objectDetails") or [{}])[0]
    cpvs = obj.get("cpvs") or []
    cpv_label = cpvs[0].get("value") if cpvs else None
    return {
        "s": (n.get("title") or "").strip(),
        "adam": n.get("referenceNumber"),
        "deadline": n.get("finalSubmissionDate"),          # ISO datetime string
        "amount": n.get("totalCostWithoutVAT"),
        "org": (n.get("organization") or {}).get("value"),
        "cpv": cpv_label,
    }


def build_html(items):
    # Sort by soonest deadline first (Python side, so the page is ready to show)
    items.sort(key=lambda x: x["deadline"] or "9999")
    athens = datetime.now(timezone(timedelta(hours=3)))
    stamp = athens.strftime("%d/%m · %H:%M")
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp))


def main():
    items = fetch_open_notices()
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html(items))
    print(f"Wrote {OUT}: {len(items)} open audit tenders from ΚΗΜΔΗΣ.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit Tender Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#0f2537;--ink-2:#16344c;--page:#e9edf1;--card:#fff;--text:#14202b;
    --muted:#63748a;--hair:#dbe1e8;--signal:#b0791f;--signal-bg:#f7edd7;
    --link:#1f6f6b;--link-ink:#155551;--live:#5bd6a6;--tag:#2c4a66;--tag-bg:#e7edf3;
    --hot:#b23b2e;--hot-bg:#f7e0dc;--warn:#9a6a12;--warn-bg:#f6ecd2;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter','Helvetica Neue',Arial,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased;padding:28px 16px 56px}
  .wrap{max-width:860px;margin:0 auto}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#eaf1f7;border-radius:14px 14px 0 0;padding:22px 24px 20px;position:relative;overflow:hidden}
  .desk::after{content:"";position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.03) 0 1px,transparent 1px 6px);opacity:.5}
  .top{display:flex;align-items:center;gap:10px;position:relative;z-index:1}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--live);animation:pulse 2.4s ease-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(91,214,166,.5)}70%{box-shadow:0 0 0 9px rgba(91,214,166,0)}100%{box-shadow:0 0 0 0 rgba(91,214,166,0)}}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#9fd8c2;font-weight:600}
  h1{font-family:'Commissioner','Inter',sans-serif;font-weight:700;font-size:26px;letter-spacing:-.01em;margin:8px 0 2px;position:relative;z-index:1}
  .sub{position:relative;z-index:1;color:#a9bed0;font-size:12.5px;line-height:1.4}
  .readout{display:flex;flex-wrap:wrap;gap:22px;margin-top:16px;position:relative;z-index:1}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8ba3b8;margin-top:4px}
  .stat .n.hot{color:#f0a79c}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);padding:14px 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--hair)}
  .search{flex:1;min-width:180px;position:relative}
  .search input{width:100%;padding:10px 12px 10px 34px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14px;color:var(--text);background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px;border-color:transparent}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.45}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden}
  .seg button{font:inherit;font-size:13px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:9px 12px;cursor:pointer}
  .seg button+button{border-left:1px solid var(--hair)}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .seg button:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px;overflow:hidden}
  .row{display:block;padding:16px 18px 15px;border-top:1px solid var(--hair);text-decoration:none;color:inherit;transition:background .15s ease}
  .row:first-child{border-top:0}.row:hover{background:#f7f9fb}
  .row:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .clock{font-size:11.5px;font-weight:700;border-radius:5px;padding:3px 8px;letter-spacing:.01em;color:var(--tag);background:var(--tag-bg)}
  .clock.hot{color:var(--hot);background:var(--hot-bg)}
  .clock.warn{color:var(--warn);background:var(--warn-bg)}
  .amount{font-family:'Commissioner',sans-serif;font-weight:700;font-size:13px;color:var(--signal);background:var(--signal-bg);border-radius:6px;padding:3px 9px}
  .amount.unknown{color:var(--muted);background:#eef1f4;font-weight:600}
  .cpv{font-size:11.5px;font-weight:600;color:var(--tag);background:var(--tag-bg);border-radius:5px;padding:3px 8px}
  .subject{font-size:15.5px;font-weight:500;color:var(--text)}
  .meta{display:flex;gap:14px;align-items:center;margin-top:9px;flex-wrap:wrap}
  .org{font-size:12.5px;color:var(--muted)}
  .open{font-size:13px;color:var(--link-ink);font-weight:600;display:inline-flex;align-items:center;gap:4px;margin-left:auto}
  .row:hover .open{text-decoration:underline}
  .empty{padding:34px 18px;text-align:center;color:var(--muted);font-size:14px;display:none}
  .foot{max-width:860px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text);font-weight:600}
  .row{opacity:0;transform:translateY(6px);animation:in .34s ease forwards}
  @media (prefers-reduced-motion:reduce){.row{opacity:1;transform:none;animation:none}.dot{animation:none}}
  @keyframes in{to{opacity:1;transform:none}}
  @media (max-width:520px){h1{font-size:22px}.readout{gap:16px}.controls{flex-direction:column;align-items:stretch}.open{margin-left:0}}
</style>
</head>
<body>
<div class="wrap">
  <header class="desk">
    <div class="top"><span class="dot" aria-hidden="true"></span><span class="live-label">Live desk · ΚΗΜΔΗΣ</span></div>
    <h1>Audit Tender Desk</h1>
    <div class="sub">Open audit tenders · deadline not yet passed · sorted by what closes soonest</div>
    <div class="readout">
      <div class="stat"><div class="n" id="stat-open">0</div><div class="l">Open to bid</div></div>
      <div class="stat"><div class="n hot" id="stat-closing">0</div><div class="l">Closing ≤ 3 days</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Updated (Athens)</div></div>
    </div>
  </header>
  <div class="controls">
    <label class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Filter — δήμος, νοσοκομείο, keyword…" aria-label="Filter tenders">
    </label>
    <div class="seg" role="group" aria-label="Sort">
      <button data-sort="deadline" aria-pressed="true">Closing soon</button>
      <button data-sort="value" aria-pressed="false">Highest value</button>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">No open tenders match that filter.</div>
</div>
<p class="foot">
  Live from <b>ΚΗΜΔΗΣ</b> (Central Registry of Public Contracts) · audit CPV family · only tenders whose bidding deadline hasn't passed.
  ΚΗΜΔΗΣ refreshes about once a day. Amounts are the official estimated value ex-VAT — always open the document to confirm terms and deadline.
</p>
<script>
  const TENDERS = __DATA__;
  const NOW = Date.now(), DAY = 86400000;
  let sortMode='deadline';
  const listEl=document.getElementById('list'),emptyEl=document.getElementById('empty'),qEl=document.getElementById('q');
  const fmtMoney=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
  function daysLeft(iso){ if(!iso) return null; return Math.ceil((new Date(iso).getTime()-NOW)/DAY); }
  function clockLabel(iso){
    const d=daysLeft(iso); if(d===null) return {t:'—',c:''};
    if(d<=0) return {t:'κλείνει σήμερα', c:'hot'};
    if(d===1) return {t:'κλείνει αύριο', c:'hot'};
    if(d<=3) return {t:'σε '+d+' ημέρες', c:'hot'};
    if(d<=7) return {t:'σε '+d+' ημέρες', c:'warn'};
    return {t:'σε '+d+' ημέρες', c:''};
  }
  function render(){
    const q=qEl.value.trim().toLowerCase();
    let rows=TENDERS.slice();
    if(q)rows=rows.filter(t=>((t.s||'')+' '+(t.org||'')+' '+(t.adam||'')+' '+(t.cpv||'')).toLowerCase().includes(q));
    if(sortMode==='value')rows.sort((a,b)=>(b.amount||-1)-(a.amount||-1));
    else rows.sort((a,b)=>(a.deadline||'9999').localeCompare(b.deadline||'9999'));
    listEl.innerHTML='';
    rows.forEach((t,idx)=>{
      const a=document.createElement('a');a.className='row';
      a.href='https://cerpp.eprocurement.gov.gr/khmdhs-opendata/notice/attachment/'+t.adam;
      a.target='_blank';a.rel='noopener';
      a.style.animationDelay=Math.min(idx*18,300)+'ms';
      const ck=clockLabel(t.deadline);
      const clock='<span class="clock '+ck.c+'">'+ck.t+'</span>';
      const amt=t.amount!=null?'<span class="amount">'+fmtMoney(t.amount)+'</span>':'<span class="amount unknown">Value n/a</span>';
      const cpv=t.cpv?'<span class="cpv">'+t.cpv.slice(0,26)+'</span>':'';
      a.innerHTML='<div class="chips">'+clock+amt+cpv+'</div><div class="subject">'+(t.s||'(χωρίς τίτλο)')+'</div>'+
        '<div class="meta"><span class="org">'+(t.org||'')+'</span>'+
        '<span class="open">Open document <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
    document.getElementById('stat-open').textContent=TENDERS.length;
    document.getElementById('stat-closing').textContent=TENDERS.filter(t=>{const d=daysLeft(t.deadline);return d!==null&&d<=3;}).length;
  }
  qEl.addEventListener('input',render);
  document.querySelectorAll('[data-sort]').forEach(b=>b.addEventListener('click',()=>{
    sortMode=b.dataset.sort;
    document.querySelectorAll('[data-sort]').forEach(x=>x.setAttribute('aria-pressed', x===b));
    render();
  }));
  render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
