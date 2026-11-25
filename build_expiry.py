"""
EXPIRY RADAR — contracts still running, soonest to expire first.

Rebuilt on the SAME contract store as ORGS / Contractors (data/contracts.jsonl),
so every page gives the same answer. Was: its own live ΚΗΜΔΗΣ crawl (~18 min
per run, its own logic). Now: seconds, no network.

Categories = our service lines. Contracts whose title contradicts the CPV
(subject_check == "mismatch") and republications are left out.

Run:  python build_expiry.py
"""

import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

STORE = "data/contracts.jsonl"
OUT = "docs/expiry.html"
FORWARD_LIMIT_DAYS = 760   # ~25 months of future expiries

SERVICE_ORDER = [
    "Εσωτερικός έλεγχος", "Οικονομικός έλεγχος / Ορκωτοί", "DPO / Προστασία δεδομένων",
    "Διαχείριση κινδύνων", "Συμμόρφωση / Whistleblowing", "Χαρτογράφηση / Οργάνωση",
    "Κυβερνοασφάλεια", "Λογιστικές υπηρεσίες", "Φορολογικές υπηρεσίες", "Μισθοδοσία",
    "Επιχειρηματική / οικονομική συμβουλευτική",
]


def collect():
    today = date.today().isoformat()
    forward = (date.today() + timedelta(days=FORWARD_LIMIT_DAYS)).isoformat()
    items = []
    with open(STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("superseded_by") or r.get("subject_check") == "mismatch":
                continue
            end = (r.get("end") or "")[:10]
            if not end or not (today <= end <= forward):
                continue
            items.append({
                "s": r.get("subject") or "",
                "adam": r.get("adam"),
                "end": end,
                "amount": r.get("value"),
                "org": r.get("org"),
                "region": r.get("region"),
                "holder": r.get("holder"),
                "cats": [r.get("service")] if r.get("service") else [],
            })
    items.sort(key=lambda x: x["end"])
    return items


def categories(items):
    present = {c for it in items for c in it["cats"]}
    return [s for s in SERVICE_ORDER if s in present] + sorted(present - set(SERVICE_ORDER))


def build_html(items):
    stamp = datetime.now(ZoneInfo("Europe/Athens")).strftime("%d/%m · %H:%M")
    return (TEMPLATE
            .replace("__DATA__", json.dumps(items, ensure_ascii=False))
            .replace("__STAMP__", stamp)
            .replace("__CATS__", json.dumps(categories(items), ensure_ascii=False)))


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
  body{background:var(--page);color:var(--text);font-family:var(--mono);line-height:1.5;-webkit-font-smoothing:antialiased;padding:14px 12px 40px}
  .wrap{max-width:none;margin:0 auto}
  .nav{max-width:none;margin:0 auto 12px;display:flex;gap:8px;font-size:13px}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:var(--card)}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:var(--panel);color:var(--text);border:1px solid var(--hair);padding:22px 24px 20px;position:relative;overflow:hidden}
  
  .top{display:flex;align-items:center;gap:10px;position:relative;z-index:1}
  .dot{width:9px;height:9px;border-radius:50%;background:var(--live);animation:pulse 2.4s ease-out infinite}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(183,156,240,.5)}70%{box-shadow:0 0 0 9px rgba(183,156,240,0)}100%{box-shadow:0 0 0 0 rgba(183,156,240,0)}}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#c9b6f0;font-weight:600}
  h1{font-family:var(--mono);font-weight:700;font-size:27px;letter-spacing:-.01em;margin:8px 0 2px;position:relative;z-index:1}
  .sub{position:relative;z-index:1;color:#bcb0d8;font-size:12.5px}
  .readout{display:flex;flex-wrap:wrap;gap:22px;margin-top:16px;position:relative;z-index:1}
  .stat .n{font-family:var(--mono);font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#a99ec7;margin-top:4px}
  .stat .n.hot{color:#f0a79c}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);padding:12px 18px;border-bottom:1px solid var(--hair)}
  .controls.top{padding-bottom:6px}
  .search{position:relative;display:block}
  .search input{width:100%;padding:11px 12px 11px 36px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;color:var(--text);background:var(--page)}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px;border-color:transparent}
  .search svg{position:absolute;left:12px;top:50%;transform:translateY(-50%);opacity:.45}
  .filters{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
  .fgroup{display:flex;align-items:center;gap:7px}
  .flabel{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:9px;overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-size:12.5px;font-weight:500;color:var(--muted);background:var(--card);border:0;padding:8px 11px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;;overflow:hidden}
  .row{display:block;padding:16px 18px 15px;border-top:1px solid var(--hair);text-decoration:none;color:inherit;transition:background .15s ease}
  .row:first-child{border-top:0}.row:hover{background:#faf9fc}
  .chips{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .exp{font-size:11.5px;font-weight:700;border-radius:5px;padding:3px 8px;color:var(--signal);background:var(--signal-bg)}
  .exp.hot{color:var(--hot);background:var(--hot-bg)}
  .exp.warn{color:var(--warn);background:var(--warn-bg)}
  .amount{font-family:var(--mono);font-weight:700;font-size:13px;color:#8a5a11;background:#f6ecd2;border-radius:6px;padding:3px 9px}
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
  .foot{max-width:none;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text);font-weight:600}
  .row{opacity:0;transform:translateY(6px);animation:in .3s ease forwards}
  @media (prefers-reduced-motion:reduce){.row{opacity:1;transform:none;animation:none}.dot{animation:none}}
  @keyframes in{to{opacity:1;transform:none}}
  @media (max-width:520px){h1{font-size:22px}.readout{gap:16px}.open{margin-left:0}}
</style>
</head>
<body>
<link rel="stylesheet" href="godel.css">
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <div class="deskbar">
    <span class="db-title">EXPIRY RADAR</span>
    <span class="db-sub">ΚΗΜΔΗΣ · running</span>
    <div class="db-filters">
      <div class="seg">
        <button data-win="90" aria-pressed="false">3μ</button>
        <button data-win="180" aria-pressed="false">6μ</button>
        <button data-win="365" aria-pressed="false">12μ</button>
        <button data-win="0" aria-pressed="true">Όλα</button>
      </div>
      <div class="seg" id="seg-cat" role="group" aria-label="Category"></div>
      <div class="seg">
        <button data-min="0" aria-pressed="true">€ όλα</button>
        <button data-min="10000" aria-pressed="false">10k+</button>
        <button data-min="30000" aria-pressed="false">30k+</button>
      </div>
    </div>
    <div class="db-stats">
      <span><b id="stat-shown">0</b> εμφαν.</span>
      <span><b class="hot" id="stat-soon">0</b> ≤90ημ</span>
      <span class="db-stamp">__STAMP__</span>
    </div>
    <input id="q" type="search" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none" tabindex="-1" aria-hidden="true">
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
      const amt=t.amount!=null?'<span class="amount">'+fmtMoney(t.amount)+'</span>':'<span class="amount unknown">Χωρίς αξία</span>';
      const cats=(t.cats||[]).map(c=>'<span class="cat">'+c+'</span>').join('');
      const holder=t.holder?'<div class="holder">Ανάδοχος: <b>'+t.holder+'</b></div>':'';
      a.innerHTML='<div class="chips">'+exp+amt+cats+'</div><div class="subject">'+(t.s||'(χωρίς τίτλο)')+'</div>'+holder+
        '<div class="meta"><span class="org">'+(t.org||'')+(t.region?' · '+t.region:'')+'</span>'+
        '<span class="open">Άνοιγμα σύμβασης <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M7 17L17 7M9 7h8v8"/></svg></span></div>';
      listEl.appendChild(a);
    });
    emptyEl.style.display=rows.length?'none':'block';
    document.getElementById('stat-shown').textContent=rows.length;
    document.getElementById('stat-soon').textContent=CONTRACTS.filter(t=>{const d=daysTo(t.end);return d!==null&&d<=90;}).length;
  }
  document.getElementById('seg-cat').innerHTML='<button data-cat="all" aria-pressed="true">Όλα</button>'+
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
