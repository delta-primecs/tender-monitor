"""
Contract Expiry Radar — build docs/expiry.html
Finds public contracts that are still running and shows when each one ENDS,
so you can approach the organisation before it goes back out to tender.
Data: ΚΗΜΔΗΣ contracts (Συμβάσεις), which carry an explicit endDate.
Public data, no login. Runs from GitHub Actions.
"""
import os
import json
from datetime import date, datetime, timezone, timedelta

import requests

CONTRACT_URL = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract"
OUT = "docs/expiry.html"

# How far back to look for SIGNED contracts (to catch long ones ending soon),
# and how far FORWARD an end date can be to still be worth showing.
MONTHS_BACK = 30
FORWARD_LIMIT_DAYS = 760   # ~25 months of future expiries

# Same categories as the tender radar — edit to match.
CPV_CATEGORIES = {
    "Audit": ["79212000-3", "79212100-4", "79212200-5", "79212300-6", "79212400-7", "79212500-8"],
    "Accounting & tax": ["79200000-6", "79210000-9", "79211000-6", "79211100-7", "79220000-2", "79221000-9", "79222000-6"],
    "Consulting": ["79400000-8", "79410000-1", "79411000-8", "79411100-9", "79412000-5", "79413000-2", "79414000-9", "79418000-7", "79419000-4"],
    "Legal": ["79100000-5", "79110000-8", "79111000-5", "79112000-2", "79140000-7"],
    "Marketing & research": ["79300000-7", "79310000-0", "79320000-3", "79340000-9", "79341000-6"],
    "HR & recruitment": ["79600000-0", "79610000-3"],
    "Projects & office support": ["79420000-4", "79421000-1", "79500000-9"],
}


def date_windows(months_back, window_days=175):
    end = date.today()
    start = end - timedelta(days=int(months_back * 30.4))
    windows, cur = [], start
    while cur < end:
        w_end = min(cur + timedelta(days=window_days), end)
        windows.append((cur.isoformat(), w_end.isoformat()))
        cur = w_end + timedelta(days=1)
    return windows


def fetch_contracts(codes, dfrom, dto):
    body = {"cpvItems": codes, "dateFrom": dfrom, "dateTo": dto}
    out, page = [], 0
    while True:
        r = requests.post(f"{CONTRACT_URL}?page={page}", json=body,
                          headers={"Accept": "application/json"}, timeout=90)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("content", []))
        if data.get("last", True):
            break
        page += 1
        if page > 25:
            break
    return out


def to_item(c):
    members = ((c.get("contractingDataDetails") or {}).get("contractingMembersDataList")) or []
    names = [m.get("name") for m in members if m.get("name")]
    return {
        "s": (c.get("title") or "").strip(),
        "adam": c.get("referenceNumber"),
        "end": c.get("endDate"),
        "amount": c.get("contractBudget") or c.get("totalCostWithoutVAT"),
        "org": (c.get("organization") or {}).get("value"),
        "region": (c.get("nutsCode") or {}).get("value") or c.get("nutsCity"),
        "holder": " / ".join(names) if names else None,
        "cats": [],
    }


def collect():
    today = date.today().isoformat()
    forward = (date.today() + timedelta(days=FORWARD_LIMIT_DAYS)).isoformat()
    windows = date_windows(MONTHS_BACK)
    by_adam = {}
    for cat, codes in CPV_CATEGORIES.items():
        for dfrom, dto in windows:
            for c in fetch_contracts(codes, dfrom, dto):
                if c.get("noEndDate"):
                    continue
                end = c.get("endDate")
                if not end or not (today <= end[:10] <= forward):
                    continue   # keep only contracts still running, ending within range
                adam = c.get("referenceNumber")
                if not adam:
                    continue
                if adam not in by_adam:
                    by_adam[adam] = to_item(c)
                if cat not in by_adam[adam]["cats"]:
                    by_adam[adam]["cats"].append(cat)
    items = list(by_adam.values())
    items.sort(key=lambda x: x["end"] or "9999")   # soonest to expire first
    return items


def build_html(items):
    athens = datetime.now(timezone(timedelta(hours=3)))
    stamp = athens.strftime("%d/%m · %H:%M")
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp)
            .replace("__CATS__", json.dumps(list(CPV_CATEGORIES.keys()), ensure_ascii=False)))


def main():
    items = collect()
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html(items))
    print(f"Wrote {OUT}: {len(items)} running contracts with a future end date.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contract Expiry Radar</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#241a3a;--ink-2:#33265a;--page:#ecebf1;--card:#fff;--text:#14202b;
    --muted:#63748a;--hair:#dedbe8;--signal:#7a3fa0;--signal-bg:#efe6f6;
    --link:#5a3f9c;--link-ink:#48307f;--live:#b79cf0;
    --hot:#b23b2e;--hot-bg:#f7e0dc;--warn:#9a6a12;--warn-bg:#f6ecd2;
    --tag:#2c4a66;--tag-bg:#e7edf3;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter','Helvetica Neue',Arial,sans-serif;line-height:1.5;-webkit-font-smoothing:antialiased;padding:28px 16px 56px}
  .wrap{max-width:880px;margin:0 auto}
  .nav{max-width:880px;margin:0 auto 12px;display:flex;gap:8px;font-size:13px}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:#fff}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#efeaf7;border-radius:14px 14px 0 0;padding:22px 24px 20px;position:relative;overflow:hidden}
  .desk::after{content:"";position:absolute;inset:0;pointer-events:none;background:repeating-linear-gradient(0deg,rgba(255,255,255,.03) 0 1px,transparent 1px 6px);opacity:.5}
  .top{display:flex;align-items:center;gap:10px;position:relative;z-index:1}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--live);animation:pulse 2.4s ease-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(183,156,240,.5)}70%{box-shadow:0 0 0 9px rgba(183,156,240,0)}100%{box-shadow:0 0 0 0 rgba(183,156,240,0)}}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#c9b6f0;font-weight:600}
  h1{font-family:'Commissioner','Inter',sans-serif;font-weight:700;font-size:27px;letter-spacing:-.01em;margin:8px 0 2px;position:relative;z-index:1}
  .sub{position:relative;z-index:1;color:#bcb0d8;font-size:12.5px}
  .readout{display:flex;flex-wrap:wrap;gap:22px;margin-top:16px;position:relative;z-index:1}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#a99ec7;margin-top:4px}
  .stat .n.hot{color:#f0a79c}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);padding:12px 18px;border-bottom:1px solid var(--hair)}
  .controls.top{padding-bottom:6px}
  .search{position:relative;display:block}
  .search input{width:100%;padding:11px 12px 11px 36px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;color:var(--text);background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px;border-color:transparent}
  .search svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);opacity:.45}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  .fgroup{display:flex;align-items:center;gap:7px}
  .flabel{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-size:12.5px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:8px 11px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px;overflow:hidden}
  .row{display:block;padding:16px 18px 15px;border-top:1px solid var(--hair);text-decoration:none;color:inherit;transition:background .15s ease}
  .row:first-child{border-top:0}.row:hover{background:#faf9fc}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .exp{font-size:11.5px;font-weight:700;border-radius:5px;padding:3px 8px;color:var(--signal);background:var(--signal-bg)}
  .exp.hot{color:var(--hot);background:var(--hot-bg)}
  .exp.warn{color:var(--warn);background:var(--warn-bg)}
  .amount{font-family:'Commissioner',sans-serif;font-weight:700;font-size:13px;color:#8a5a11;background:#f6ecd2;border-radius:6px;padding:3px 9px}
  .amount.unknown{color:var(--muted);background:#eef1f4;font-weight:600}
  .cat{font-size:11.5px;font-weight:600;color:var(--tag);background:var(--tag-bg);border-radius:5px;padding:3px 8px}
  .subject{font-size:15px;font-weight:500;color:var(--text)}
  .holder{margin-top:8px;font-size:13px;color:var(--text)}
  .holder b{color:var(--link-ink)}
  .meta{display:flex;gap:14px;align-items:center;margin-top:7px;flex-wrap:wrap}
  .org{font-size:12.5px;color:var(--muted)}
  .open{font-size:13px;color:var(--link-ink);font-weight:600;display:inline-flex;align-items:center;gap:4px;margin-left:auto}
  .row:hover .open{text-decoration:underline}
  .empty{padding:34px 18px;text-align:center;color:var(--muted);font-size:14px;display:none}
  .foot{max-width:880px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text);font-weight:600}
  .row{opacity:0;transform:translateY(6px);animation:in .3s ease forwards}
  @media (prefers-reduced-motion:reduce){.row{opacity:1;transform:none;animation:none}.dot{animation:none}}
  @keyframes in{to{opacity:1;transform:none}}
  @media (max-width:520px){h1{font-size:22px}.readout{gap:16px}.open{margin-left:0}}
</style>
</head>
<body>
<nav class="nav">
  <a href="index.html">Open tenders</a>
  <a href="expiry.html" class="on">Expiry radar</a>
</nav>
<div class="wrap">
  <header class="desk">
    <div class="top"><span class="dot" aria-hidden="true"></span><span class="live-label">Contracts · ΚΗΜΔΗΣ</span></div>
    <h1>Contract Expiry Radar</h1>
    <div class="sub">Running contracts and when they end — reach the client before the re-tender</div>
    <div class="readout">
      <div class="stat"><div class="n" id="stat-shown">0</div><div class="l">Shown</div></div>
      <div class="stat"><div class="n hot" id="stat-soon">0</div><div class="l">Ending ≤ 90 days</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Updated (Athens)</div></div>
    </div>
  </header>
  <div class="controls top">
    <label class="search">
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Search — org, incumbent firm, keyword…" aria-label="Search contracts">
    </label>
  </div>
  <div class="controls filters">
    <div class="fgroup"><span class="flabel">Ends within</span>
      <div class="seg" role="group" aria-label="Time window">
        <button data-win="90" aria-pressed="false">3 mo</button>
        <button data-win="180" aria-pressed="false">6 mo</button>
        <button data-win="365" aria-pressed="false">12 mo</button>
        <button data-win="0" aria-pressed="true">All</button>
      </div>
    </div>
    <div class="fgroup"><span class="flabel">Area</span><div class="seg" id="seg-cat" role="group" aria-label="Category"></div></div>
    <div class="fgroup"><span class="flabel">Min €</span>
      <div class="seg" role="group" aria-label="Minimum value">
        <button data-min="0" aria-pressed="true">Any</button>
        <button data-min="10000" aria-pressed="false">10k+</button>
        <button data-min="30000" aria-pressed="false">30k+</button>
      </div>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">No contracts match these filters.</div>
</div>
<p class="foot">
  Running contracts from <b>ΚΗΜΔΗΣ</b> across your categories, with the official <b>end date</b> the organisation registered.
  Note: some contracts have <b>option-right extensions</b> that push the real end date later — always confirm in the document before acting.
  Refreshes daily. Very long (3-year+) contracts signed a while ago may not yet appear.
</p>
<script>
  const CONTRACTS = __DATA__;
  const CATS = __CATS__;
  const NOW=Date.now(),DAY=86400000;
  let win=0, catFilter='all', minValue=0;
  const listEl=document.getElementById('list'),emptyEl=document.getElementById('empty'),qEl=document.getElementById('q');
  const fmtMoney=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
  const catClass=c=>c.startsWith('Account')?'Accounting':(c.startsWith('Consult')?'Consulting':'Audit');
  function daysTo(iso){ if(!iso) return null; return Math.ceil((new Date(iso).getTime()-NOW)/DAY); }
  function fmtEnd(iso){
    const d=daysTo(iso); if(d===null) return {t:'—',c:''};
    const dt=new Date(iso).toLocaleDateString('el-GR',{day:'2-digit',month:'short',year:'numeric'});
    let c=''; if(d<=90)c='hot'; else if(d<=180)c='warn';
    const rel = d<=60 ? ('σε '+d+' ημ.') : ('σε ~'+Math.round(d/30)+' μήνες');
    return {t:'λήγει '+dt+' · '+rel, c};
  }
  function passes(t){
    const d=daysTo(t.end);
    if(win!==0 && (d===null || d>win)) return false;
    if(catFilter!=='all' && !(t.cats||[]).includes(catFilter)) return false;
    if((t.amount||0) < minValue) return false;
    return true;
  }
  function render(){
    const q=qEl.value.trim().toLowerCase();
    let rows=CONTRACTS.filter(passes);
    if(q)rows=rows.filter(t=>((t.s||'')+' '+(t.org||'')+' '+(t.holder||'')+' '+(t.adam||'')+' '+(t.cats||[]).join(' ')).toLowerCase().includes(q));
    rows.sort((a,b)=>(a.end||'9999').localeCompare(b.end||'9999'));
    listEl.innerHTML='';
    rows.forEach((t,idx)=>{
      const a=document.createElement('a');a.className='row';
      a.href='https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+t.adam;
      a.target='_blank';a.rel='noopener';a.style.animationDelay=Math.min(idx*12,260)+'ms';
      const e=fmtEnd(t.end);
      const exp='<span class="exp '+e.c+'">'+e.t+'</span>';
      const amt=t.amount!=null?'<span class="amount">'+fmtMoney(t.amount)+'</span>':'<span class="amount unknown">Value n/a</span>';
      const cats=(t.cats||[]).map(c=>'<span class="cat">'+c+'</span>').join('');
      const holder=t.holder?'<div class="holder">Ανάδοχος: <b>'+t.holder+'</b></div>':'';
      a.innerHTML='<div class="chips">'+exp+amt+cats+'</div><div class="subject">'+(t.s||'(χωρίς τίτλο)')+'</div>'+holder+
        '<div class="meta"><span class="org">'+(t.org||'')+(t.region?' · '+t.region:'')+'</span>'+
        '<span class="open">Open contract <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
    document.getElementById('stat-shown').textContent=rows.length;
    document.getElementById('stat-soon').textContent=CONTRACTS.filter(t=>{const d=daysTo(t.end);return d!==null&&d<=90;}).length;
  }
  document.getElementById('seg-cat').innerHTML='<button data-cat="all" aria-pressed="true">All</button>'+
    CATS.map(c=>'<button data-cat="'+c+'">'+c+'</button>').join('');
  function wire(sel, apply){
    document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
      apply(b); document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed', x===b)); render();
    }));
  }
  qEl.addEventListener('input',render);
  wire('[data-win]', b=>win=+b.dataset.win);
  wire('[data-cat]', b=>catFilter=b.dataset.cat);
  wire('[data-min]', b=>minValue=+b.dataset.min);
  render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
