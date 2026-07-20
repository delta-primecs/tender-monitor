"""
Build the Audit Tender Desk dashboard.
Fetches current tenders from Diavgeia and writes docs/index.html, which
GitHub Pages serves. Needs no email and no secrets — it only reads public data.
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://diavgeia.gov.gr/luminapi/opendata"
CPV = "79212200-5"
DECISION_TYPE = "Δ.2.1"
OUT = "docs/index.html"


def fetch(cpv, dtype, size=50):
    q = f'cpv:"{cpv}" AND decisionTypeUid:"{dtype}"'
    params = {"q": q, "size": size, "page": 0, "sort": "recent"}
    r = requests.get(f"{BASE}/search/advanced", params=params,
                     headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("decisions") or data.get("results") or []


# Reads euro amounts written in the notice text, e.g. "186.000,00 €"
AMOUNT_RE = re.compile(r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*€')


def parse_amount(subject):
    values = []
    for m in AMOUNT_RE.finditer(subject or ""):
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            values.append(float(num))
        except ValueError:
            pass
    return max(values) if values else None   # largest figure ≈ the budget


def build_html(tenders):
    items = []
    for d in tenders:
        subject = (d.get("subject") or "").strip()
        items.append({
            "s": subject,
            "ada": d.get("ada", ""),
            "amount": parse_amount(subject),
        })
    athens = datetime.now(timezone(timedelta(hours=3)))
    stamp = athens.strftime("%d/%m · %H:%M")
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp)
            .replace("__CPV__", CPV))


def main():
    tenders = fetch(CPV, DECISION_TYPE)
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html(tenders))
    print(f"Wrote {OUT} with {len(tenders)} tenders.")


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
    --link:#1f6f6b;--link-ink:#155551;--live:#5bd6a6;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter','Helvetica Neue',Arial,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased;padding:28px 16px 56px}
  .wrap{max-width:840px;margin:0 auto}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#eaf1f7;border-radius:14px 14px 0 0;padding:22px 24px 20px;position:relative;overflow:hidden}
  .desk::after{content:"";position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.03) 0 1px,transparent 1px 6px);opacity:.5}
  .top{display:flex;align-items:center;gap:10px;position:relative;z-index:1}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--live);animation:pulse 2.4s ease-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(91,214,166,.5)}70%{box-shadow:0 0 0 9px rgba(91,214,166,0)}100%{box-shadow:0 0 0 0 rgba(91,214,166,0)}}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#9fd8c2;font-weight:600}
  h1{font-family:'Commissioner','Inter',sans-serif;font-weight:700;font-size:26px;letter-spacing:-.01em;margin:8px 0 2px;position:relative;z-index:1}
  .sub{position:relative;z-index:1;color:#a9bed0;font-size:13.5px}
  .sub .cpv{color:#e7c987;font-weight:600}
  .readout{display:flex;flex-wrap:wrap;gap:22px;margin-top:16px;position:relative;z-index:1}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8ba3b8;margin-top:4px}
  .stat .n.gold{color:#e7c987}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);padding:14px 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--hair)}
  .search{flex:1;min-width:180px;position:relative}
  .search input{width:100%;padding:10px 12px 10px 34px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14px;color:var(--text);background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px;border-color:transparent}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.45}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden}
  .seg button{font:inherit;font-size:13px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:9px 13px;cursor:pointer}
  .seg button+button{border-left:1px solid var(--hair)}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .seg button:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px;overflow:hidden}
  .row{display:block;padding:16px 18px 15px;border-top:1px solid var(--hair);text-decoration:none;color:inherit;transition:background .15s ease}
  .row:first-child{border-top:0}.row:hover{background:#f7f9fb}
  .row:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .amount{font-family:'Commissioner',sans-serif;font-weight:700;font-size:13px;color:var(--signal);background:var(--signal-bg);border-radius:6px;padding:3px 9px}
  .amount.unknown{color:var(--muted);background:#eef1f4;font-weight:600}
  .subject{font-size:15.5px;font-weight:500;color:var(--text)}
  .meta{display:flex;gap:14px;align-items:center;margin-top:9px;flex-wrap:wrap}
  .ada{font-size:12px;color:var(--muted);letter-spacing:.06em}
  .open{font-size:13px;color:var(--link-ink);font-weight:600;display:inline-flex;align-items:center;gap:4px}
  .row:hover .open{text-decoration:underline}
  .empty{padding:34px 18px;text-align:center;color:var(--muted);font-size:14px;display:none}
  .foot{max-width:840px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text);font-weight:600}
  .row{opacity:0;transform:translateY(6px);animation:in .34s ease forwards}
  @media (prefers-reduced-motion:reduce){.row{opacity:1;transform:none;animation:none}.dot{animation:none}}
  @keyframes in{to{opacity:1;transform:none}}
  @media (max-width:520px){h1{font-size:22px}.readout{gap:16px}.controls{flex-direction:column;align-items:stretch}}
</style>
</head>
<body>
<div class="wrap">
  <header class="desk">
    <div class="top"><span class="dot" aria-hidden="true"></span><span class="live-label">Live desk · Διαύγεια</span></div>
    <h1>Audit Tender Desk</h1>
    <div class="sub"><span class="cpv">CPV __CPV__</span> · Υπηρεσίες εσωτερικού διαχειριστικού ελέγχου</div>
    <div class="readout">
      <div class="stat"><div class="n" id="stat-open">0</div><div class="l">Open now</div></div>
      <div class="stat"><div class="n gold" id="stat-valued">0</div><div class="l">With stated value</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Updated (Athens)</div></div>
    </div>
  </header>
  <div class="controls">
    <label class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Filter by keyword — e.g. Νοσοκομείο, Περιφέρεια…" aria-label="Filter tenders">
    </label>
    <div class="seg" role="group" aria-label="Sort order">
      <button id="sort-listed" aria-pressed="true">Newest first</button>
      <button id="sort-value" aria-pressed="false">Highest value</button>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">No tenders match that filter.</div>
</div>
<p class="foot">
  Live from Διαύγεια · CPV __CPV__ (type Δ.2.1) · refreshes automatically every hour.
  <b>Amounts are read from the notice text</b> and may be approximate — open the document for the exact figure.
</p>
<script>
  const TENDERS = __DATA__;
  const listEl=document.getElementById('list'),emptyEl=document.getElementById('empty'),qEl=document.getElementById('q');
  let sortMode='listed';
  const fmt=n=>new Intl.NumberFormat('el-GR').format(n)+' €';
  function render(){
    const q=qEl.value.trim().toLowerCase();
    let rows=TENDERS.map((t,i)=>({...t,i}));
    if(q)rows=rows.filter(t=>(t.s+' '+t.ada).toLowerCase().includes(q));
    if(sortMode==='value')rows.sort((a,b)=>(b.amount||-1)-(a.amount||-1));
    listEl.innerHTML='';
    rows.forEach((t,idx)=>{
      const a=document.createElement('a');a.className='row';
      a.href='https://diavgeia.gov.gr/doc/'+t.ada;a.target='_blank';a.rel='noopener';
      a.style.animationDelay=Math.min(idx*28,320)+'ms';
      const chip=t.amount!=null?'<span class="amount">'+fmt(t.amount)+'</span>':'<span class="amount unknown">Value not stated</span>';
      a.innerHTML='<div class="chips">'+chip+'</div><div class="subject">'+t.s+'</div>'+
        '<div class="meta"><span class="ada">ΑΔΑ '+t.ada+'</span><span class="open">Open document '+
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
  }
  qEl.addEventListener('input',render);
  const bL=document.getElementById('sort-listed'),bV=document.getElementById('sort-value');
  bL.addEventListener('click',()=>{sortMode='listed';bL.setAttribute('aria-pressed','true');bV.setAttribute('aria-pressed','false');render();});
  bV.addEventListener('click',()=>{sortMode='value';bV.setAttribute('aria-pressed','true');bL.setAttribute('aria-pressed','false');render();});
  document.getElementById('stat-open').textContent=TENDERS.length;
  document.getElementById('stat-valued').textContent=TENDERS.filter(t=>t.amount!=null).length;
  render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
