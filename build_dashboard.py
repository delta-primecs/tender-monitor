"""
Build the Audit Tender Desk dashboard — with real dates and real amounts.
Watches the auditing CPV family, dedupes by ADA, tags each tender with the
CPV(s) it matched, reads the official estimated budget and publish date,
and writes docs/index.html for GitHub Pages. Public data only; no secrets.
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://diavgeia.gov.gr/luminapi/opendata"
DECISION_TYPE = "Δ.2.1"
OUT = "docs/index.html"

# The CPV codes to watch, each with a short tag shown on the dashboard.
CPVS = {
    "79212100-4": "Financial audit",
    "79212200-5": "Internal audit",
    "79212000-3": "Auditing",
    "79212300-6": "Statutory audit",
    "79212400-7": "Fraud audit",
    "79212500-8": "Accounting review",
    # Broad parents — uncomment if you also want accounting/tax/payroll work:
    # "79210000-9": "Acct & audit",
    # "79200000-6": "Acct/fiscal",
}


def fetch_one(cpv, size=100):
    q = f'cpv:"{cpv}" AND decisionTypeUid:"{DECISION_TYPE}"'
    params = {"q": q, "size": size, "page": 0, "sort": "recent"}
    r = requests.get(f"{BASE}/search/advanced", params=params,
                     headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("decisions") or data.get("results") or []


AMOUNT_RE = re.compile(r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*€')


def parse_amount_from_text(subject):
    values = []
    for m in AMOUNT_RE.finditer(subject or ""):
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            values.append(float(num))
        except ValueError:
            pass
    return max(values) if values else None


def get_amount(d, subject):
    # Prefer the official structured estimated value; fall back to text.
    efv = d.get("extraFieldValues") or {}
    est = efv.get("estimatedAmount") or {}
    amt = est.get("amount")
    if isinstance(amt, (int, float)) and amt > 0:
        return float(amt)
    return parse_amount_from_text(subject)


def get_timestamp(d):
    for f in ("publishTimestamp", "submissionTimestamp", "issueDate"):
        v = d.get(f)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def collect():
    """Fetch every CPV, dedupe by ADA, keep real amount + publish time + tags."""
    by_ada = {}
    for cpv, label in CPVS.items():
        for d in fetch_one(cpv):
            ada = d.get("ada")
            if not ada:
                continue
            if ada not in by_ada:
                subject = (d.get("subject") or "").strip()
                by_ada[ada] = {
                    "s": subject,
                    "ada": ada,
                    "amount": get_amount(d, subject),
                    "ts": get_timestamp(d),   # epoch milliseconds
                    "tags": [],
                }
            if label not in by_ada[ada]["tags"]:
                by_ada[ada]["tags"].append(label)
    items = list(by_ada.values())
    items.sort(key=lambda x: (x["ts"] or 0), reverse=True)   # newest first
    return items


def build_html(items):
    athens = datetime.now(timezone(timedelta(hours=3)))
    stamp = athens.strftime("%d/%m · %H:%M")
    families = " · ".join(CPVS.values())
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp)
            .replace("__FAMILIES__", families))


def main():
    items = collect()
    os.makedirs("docs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_html(items))
    print(f"Wrote {OUT}: {len(items)} unique tenders across {len(CPVS)} CPV codes.")


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
    --new:#0f6b45;--new-bg:#d6f2e4;
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
  .sub{position:relative;z-index:1;color:#a9bed0;font-size:12.5px;line-height:1.4}
  .readout{display:flex;flex-wrap:wrap;gap:22px;margin-top:16px;position:relative;z-index:1}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8ba3b8;margin-top:4px}
  .stat .n.green{color:#7ee0b4}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);padding:14px 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--hair)}
  .search{flex:1;min-width:170px;position:relative}
  .search input{width:100%;padding:10px 12px 10px 34px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14px;color:var(--text);background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px;border-color:transparent}
  .search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.45}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden}
  .seg button{font:inherit;font-size:13px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:9px 12px;cursor:pointer}
  .seg button+button{border-left:1px solid var(--hair)}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .seg button:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .seg-label{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-right:2px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px;overflow:hidden}
  .row{display:block;padding:16px 18px 15px;border-top:1px solid var(--hair);text-decoration:none;color:inherit;transition:background .15s ease}
  .row:first-child{border-top:0}.row:hover{background:#f7f9fb}
  .row:focus-visible{outline:2px solid var(--link);outline-offset:-2px}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .new-badge{font-size:11px;font-weight:700;color:var(--new);background:var(--new-bg);border-radius:5px;padding:3px 8px;letter-spacing:.02em}
  .amount{font-family:'Commissioner',sans-serif;font-weight:700;font-size:13px;color:var(--signal);background:var(--signal-bg);border-radius:6px;padding:3px 9px}
  .amount.unknown{color:var(--muted);background:#eef1f4;font-weight:600}
  .tag{font-size:11.5px;font-weight:600;color:var(--tag);background:var(--tag-bg);border-radius:5px;padding:3px 8px}
  .subject{font-size:15.5px;font-weight:500;color:var(--text)}
  .meta{display:flex;gap:14px;align-items:center;margin-top:9px;flex-wrap:wrap}
  .date{font-size:12.5px;color:var(--text);font-weight:600}
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
    <div class="sub">__FAMILIES__ · type Δ.2.1</div>
    <div class="readout">
      <div class="stat"><div class="n" id="stat-shown">0</div><div class="l">Showing</div></div>
      <div class="stat"><div class="n green" id="stat-new">0</div><div class="l">New · 48h</div></div>
      <div class="stat"><div class="n" style="font-size:16px">__STAMP__</div><div class="l">Updated (Athens)</div></div>
    </div>
  </header>
  <div class="controls">
    <label class="search">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      <input id="q" type="search" placeholder="Filter — keyword or CPV…" aria-label="Filter tenders">
    </label>
    <div class="seg" role="group" aria-label="Time window">
      <button data-win="7" aria-pressed="false">7 days</button>
      <button data-win="30" aria-pressed="true">30 days</button>
      <button data-win="0" aria-pressed="false">All</button>
    </div>
    <div class="seg" role="group" aria-label="Sort">
      <button data-sort="date" aria-pressed="true">Newest</button>
      <button data-sort="value" aria-pressed="false">Value</button>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty">No tenders in this window. Try “All”.</div>
</div>
<p class="foot">
  Live from Διαύγεια across the audit CPV family · type Δ.2.1 · refreshes hourly.
  <b>“New” = recently published</b> (no bidding-deadline field exists, so recency is the proxy).
  Amounts are the official estimated value where Διαύγεια provides it, otherwise read from the notice text — always open the document to confirm.
</p>
<script>
  const TENDERS = __DATA__;
  const NOW = Date.now(), DAY = 86400000;
  let win = 30, sortMode = 'date';
  const listEl=document.getElementById('list'),emptyEl=document.getElementById('empty'),qEl=document.getElementById('q');
  const fmtMoney=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €';
  const fmtDate=ts=>ts?new Date(ts).toLocaleDateString('el-GR',{day:'2-digit',month:'short'}):'—';
  const ageDays=ts=>ts?(NOW-ts)/DAY:Infinity;
  const inWin=t=>win===0?true:ageDays(t.ts)<=win;

  function render(){
    const q=qEl.value.trim().toLowerCase();
    let rows=TENDERS.filter(inWin);
    const windowCount=rows.length;
    if(q)rows=rows.filter(t=>(t.s+' '+t.ada+' '+(t.tags||[]).join(' ')).toLowerCase().includes(q));
    if(sortMode==='value')rows=rows.slice().sort((a,b)=>(b.amount||-1)-(a.amount||-1));
    else rows=rows.slice().sort((a,b)=>(b.ts||0)-(a.ts||0));

    listEl.innerHTML='';
    rows.forEach((t,idx)=>{
      const a=document.createElement('a');a.className='row';
      a.href='https://diavgeia.gov.gr/doc/'+t.ada;a.target='_blank';a.rel='noopener';
      a.style.animationDelay=Math.min(idx*22,300)+'ms';
      const isNew=ageDays(t.ts)<=2;
      const badge=isNew?'<span class="new-badge">🆕 NEW</span>':'';
      const amt=t.amount!=null?'<span class="amount">'+fmtMoney(t.amount)+'</span>':'<span class="amount unknown">Value n/a</span>';
      const tags=(t.tags||[]).map(x=>'<span class="tag">'+x+'</span>').join('');
      a.innerHTML='<div class="chips">'+badge+amt+tags+'</div><div class="subject">'+t.s+'</div>'+
        '<div class="meta"><span class="date">'+fmtDate(t.ts)+'</span><span class="ada">ΑΔΑ '+t.ada+'</span>'+
        '<span class="open">Open document <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
    document.getElementById('stat-shown').textContent=windowCount;
    document.getElementById('stat-new').textContent=TENDERS.filter(t=>ageDays(t.ts)<=2).length;
  }

  qEl.addEventListener('input',render);
  document.querySelectorAll('[data-win]').forEach(b=>b.addEventListener('click',()=>{
    win=+b.dataset.win;
    document.querySelectorAll('[data-win]').forEach(x=>x.setAttribute('aria-pressed', x===b));
    render();
  }));
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
