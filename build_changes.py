"""
'What changed' feed — build docs/changes.html
Reads data/changes.jsonl (written by ingest_contracts.py) and shows every
RENEWAL / NEW / UPDATED event newest-first. This is the Νισύρου alarm made
visible: the moment a Δήμος re-signs, it appears here.

Starts empty (the backfill logs nothing on purpose) and fills as real changes
arrive over the coming days.
"""

import os
import json
from datetime import date, datetime, timezone, timedelta

CHANGES = "data/changes.jsonl"
OUT = "docs/changes.html"


def load_events():
    if not os.path.exists(CHANGES):
        return []
    out = []
    with open(CHANGES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                # REPUBLISH events are "same commercial contract, fresh ΑΔΑΜ"
                # — logged for audit trail but NOT actionable. Hide from feed.
                if ev.get("event") == "REPUBLISH":
                    continue
                out.append(ev)
    out.sort(key=lambda e: (e.get("date", ""), e.get("event", "")), reverse=True)
    return out


def services_in(events):
    return sorted({e.get("service") for e in events if e.get("service")})


def main():
    events = load_events()
    os.makedirs("docs", exist_ok=True)
    athens = datetime.now(timezone(timedelta(hours=3)))
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(events, ensure_ascii=False))
            .replace("__SERVICES__", json.dumps(services_in(events), ensure_ascii=False))
            .replace("__STAMP__", athens.strftime("%d/%m/%Y %H:%M")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    renew = sum(1 for e in events if e.get("event") == "RENEWAL")
    print(f"Wrote {OUT}: {len(events)} events ({renew} renewals).")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What changed</title>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#2a2140;--ink-2:#3a2d5a;--page:#eceaf1;--card:#fff;--text:#14202b;
    --muted:#63748a;--hair:#ded9e8;--gold:#8a5a11;--gold-bg:#f6ecd2;
    --link:#5a3f9c;--link-ink:#48307f;
    --renew:#b23b2e;--renew-bg:#f7e0dc;--new:#2f6b4f;--new-bg:#e2efe8;--upd:#8a6d1a;--upd-bg:#f6ecd2;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter',Arial,sans-serif;line-height:1.5;padding:24px 16px 56px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:880px;margin:0 auto}
  .nav{max-width:880px;margin:0 auto 12px;display:flex;gap:8px;font-size:13px;flex-wrap:wrap}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:#fff}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#efeaf7;border-radius:14px 14px 0 0;padding:22px 24px 20px}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#c9b6f0;font-weight:600}
  h1{font-family:'Commissioner',sans-serif;font-weight:700;font-size:27px;margin:8px 0 2px;letter-spacing:-.01em}
  .sub{color:#bcb0d8;font-size:12.5px}
  .readout{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#a99ec7;margin-top:4px}
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
  .row{padding:14px 18px;border-top:1px solid var(--hair);display:flex;gap:12px;align-items:flex-start}
  .row:first-child{border-top:0}
  .badge{font-size:11px;font-weight:700;border-radius:5px;padding:3px 8px;white-space:nowrap;margin-top:2px}
  .chk{display:inline-block;margin-left:8px;font-size:10.5px;font-weight:700;border-radius:5px;padding:2px 7px;white-space:nowrap;cursor:help;vertical-align:middle}
  .chk-bad{background:#f4d0cb;color:#8a1a10}
  .chk-warn{background:#f6ecd2;color:#8a5a11}
  .badge.RENEWAL{background:var(--renew-bg);color:var(--renew)}
  .badge.NEW{background:var(--new-bg);color:var(--new)}
  .badge.UPDATED{background:var(--upd-bg);color:var(--upd)}
  .body{flex:1}
  .org{font-size:15px;font-weight:600}
  .svc{font-size:12.5px;color:var(--muted)}
  .detail{font-size:13px;margin-top:5px}
  .detail b{color:var(--link-ink)}
  .meta{font-size:12.5px;color:var(--muted);margin-top:5px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
  .verify{color:var(--link-ink);text-decoration:none;font-weight:600}
  .verify:hover{text-decoration:underline}
  .date{font-size:12px;color:var(--muted);white-space:nowrap;margin-top:3px;text-align:right}
  .date-abs{font-weight:700;color:var(--text);font-size:12.5px}
  .date-ago{font-size:11.5px;color:var(--muted);margin-top:2px}
  .empty{padding:40px 24px;text-align:center;color:var(--muted);font-size:14px}
  .empty b{color:var(--text)}
  .foot{max-width:880px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text)}
</style>
</head>
<body>
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <header class="desk">
    <div class="live-label">Live feed · ΚΗΜΔΗΣ</div>
    <h1>What changed</h1>
    <div class="sub">Ανανεώσεις & νέες συμβάσεις στους τομείς σου — μόλις εμφανιστούν</div>
    <div class="readout">
      <div class="stat"><div class="n" id="s-all">0</div><div class="l">Events</div></div>
      <div class="stat"><div class="n hot" id="s-renew">0</div><div class="l">Renewals</div></div>
      <div class="stat"><div class="n" style="font-size:15px">__STAMP__</div><div class="l">Updated</div></div>
    </div>
  </header>
  <div class="controls">
    <label class="search"><input id="q" type="search" placeholder="Αναζήτηση — φορέας, ανάδοχος…"></label>
    <div class="filters">
      <span class="flabel">Τύπος</span>
      <div class="seg">
        <button data-ev="all" aria-pressed="true">Όλα</button>
        <button data-ev="RENEWAL" aria-pressed="false">Ανανεώσεις</button>
        <button data-ev="NEW" aria-pressed="false">Νέες</button>
      </div>
      <span class="flabel">Τομέας</span><div class="seg" id="seg-svc"></div>
      <span class="flabel">Διάστημα</span>
      <div class="seg">
        <button data-win="7" aria-pressed="false">7 ημ.</button>
        <button data-win="30" aria-pressed="false">30 ημ.</button>
        <button data-win="0" aria-pressed="true">Όλα</button>
      </div>
    </div>
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty" style="display:none"></div>
</div>
<p class="foot">
  Τροφοδοτείται από τη μνήμη του συστήματος (<b>data/changes.jsonl</b>). Η ροή <b>ξεκινά άδεια</b> και γεμίζει καθώς εμφανίζονται πραγματικές αλλαγές — μία <b>ΑΝΑΝΕΩΣΗ</b> σημαίνει ότι ο φορέας ξαναϋπέγραψε (δεν είναι πια ευκαιρία).
  Πάντα επιβεβαίωσε στο ΚΗΜΔΗΣ πριν ενεργήσεις.
</p>
<script>
const EV = __DATA__, SVCS = __SERVICES__;
const TODAY = new Date().toISOString().slice(0,10), DAY=86400000;
let evFilter='all', svcFilter='all', win=0;
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
const money=n=>n?new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n)+' €':'';
const dmy=s=>s?s.split('-').reverse().join('/'):'—';
const daysAgo=s=>s?Math.round((new Date(TODAY)-new Date(s))/DAY):null;
const kimdis='https://www.gov.gr/el/services/1001013/demosioteta-demosion-sumbaseon-kemdes';

document.getElementById('seg-svc').innerHTML =
  '<button data-svc="all" aria-pressed="true">Όλοι</button>' +
  SVCS.map(s=>'<button data-svc="'+s+'">'+s.split(' /')[0]+'</button>').join('');

function passes(e){
  if(evFilter!=='all' && e.event!==evFilter) return false;
  if(svcFilter!=='all' && e.service!==svcFilter) return false;
  if(win){ const d=daysAgo(e.date); if(d===null||d>win) return false; }
  return true;
}
const LABEL={RENEWAL:'ΑΝΑΝΕΩΣΗ', NEW:'ΝΕΑ', UPDATED:'ΑΛΛΑΓΗ'};
function render(){
  const q=qEl.value.trim().toLowerCase();
  let rows=EV.filter(passes);
  if(q) rows=rows.filter(e=>((e.org||'')+' '+(e.holder||'')+' '+(e.service||'')).toLowerCase().includes(q));
  listEl.innerHTML='';
  if(!EV.length){
    emptyEl.style.display='block';
    emptyEl.innerHTML='<b>Καμία αλλαγή ακόμη.</b><br>Το σύστημα μόλις έχτισε τη μνήμη του. '+
      'Μόλις υπογραφεί νέα ή ανανεωμένη σύμβαση στους τομείς σου, θα εμφανιστεί εδώ — έλεγξε ξανά σε λίγες μέρες.';
    document.getElementById('s-all').textContent='0';
    document.getElementById('s-renew').textContent='0';
    return;
  }
  rows.slice(0,500).forEach(e=>{
    const el=document.createElement('div'); el.className='row';
    const d=daysAgo(e.date);
    const ago = d===0 ? 'σήμερα' : (d===1 ? 'χθες' : 'πριν '+d+' ημ.');
    const sc = e.subject_check || 'unverified';
    const scBadge = sc==='mismatch'
      ? '<span class="chk chk-bad" title="'+((e.subject||'').replace(/"/g,'&quot;'))+'">⚠ τίτλος αντίθετος</span>'
      : (sc==='unverified'
          ? '<span class="chk chk-warn" title="Ο τίτλος δεν επιβεβαιώνει την υπηρεσία — έλεγξε τη σύμβαση πριν καλέσεις">⚠ προς επιβεβαίωση</span>'
          : '');
    el.innerHTML='<span class="badge '+e.event+'">'+(LABEL[e.event]||e.event)+'</span>'+
      '<div class="body"><div class="org">'+(e.org||'—')+'</div>'+
      '<div class="svc">'+(e.service||'')+scBadge+'</div>'+
      (e.holder?'<div class="detail">Ανάδοχος: <b>'+e.holder+'</b>'+(e.value?' · '+money(e.value):'')+'</div>':'')+
      '<div class="meta">'+(e.signed?'υπογραφή '+dmy(e.signed):'')+(e.end?' · λήγει '+dmy(e.end):'')+
      (e.adam?' <a class="verify" target="_blank" rel="noopener" href="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+e.adam+'">Άνοιγμα σύμβασης ↗</a>':'')+'</div></div>'+
      '<div class="date"><div class="date-abs">'+dmy(e.date)+'</div>'+
      '<div class="date-ago">καταγράφηκε '+ago+'</div></div>';
    listEl.appendChild(el);
  });
  emptyEl.style.display=rows.length?'none':'block';
  if(!rows.length) emptyEl.innerHTML='Καμία αλλαγή δεν ταιριάζει με τα φίλτρα.';
  document.getElementById('s-all').textContent=EV.length;
  document.getElementById('s-renew').textContent=EV.filter(e=>e.event==='RENEWAL').length;
}
function wire(sel,fn){document.querySelectorAll(sel).forEach(b=>b.addEventListener('click',()=>{
  fn(b); document.querySelectorAll(sel).forEach(x=>x.setAttribute('aria-pressed',x===b)); render();}));}
qEl.addEventListener('input',render);
wire('[data-ev]',  b=>evFilter=b.dataset.ev);
wire('[data-svc]', b=>svcFilter=b.dataset.svc);
wire('[data-win]', b=>win=+b.dataset.win);
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
