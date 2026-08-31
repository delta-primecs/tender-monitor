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
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{
    /* Gödel-style terminal palette */
    --page:#0a0e14;        /* near-black background */
    --panel:#0f141c;       /* panel surface */
    --panel-2:#131a24;     /* alternate row */
    --card:#0f141c;
    --text:#d4dae3;        /* off-white body */
    --bright:#f0f4f9;      /* bright headings */
    --muted:#5f6e82;       /* dim labels */
    --hair:#1c2530;        /* hairline grid */
    --hair-2:#26313f;
    --accent:#3ddc84;      /* phosphor green — the "live" color */
    --accent-dim:#1f5f3f;
    --amber:#e8a13a;       /* warnings / updates */
    --amber-bg:#2a2010;
    --red:#ff5d52;         /* renewals / alerts */
    --red-bg:#2a1210;
    --green:#3ddc84;       /* new */
    --green-bg:#0f2418;
    --link:#5db0ff;        /* interactive blue */
    --mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:var(--mono);
       line-height:1.45;padding:14px 12px 40px;-webkit-font-smoothing:antialiased;
       font-size:13px}
  .wrap{max-width:1100px;margin:0 auto}
  .nav{max-width:1600px;margin:0 auto 8px;display:flex;gap:2px;font-size:12px;flex-wrap:wrap}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);
         background:var(--panel);text-transform:uppercase;letter-spacing:.05em;font-weight:500}
  .nav a:hover{color:var(--text);border-color:var(--hair-2)}
  .nav a.on{background:var(--accent-dim);color:var(--accent);border-color:var(--accent-dim)}

  /* Terminal header bar */
  .desk{background:var(--panel);color:var(--text);border:1px solid var(--hair);
        padding:12px 16px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  .live-label{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);
              font-weight:700;display:flex;align-items:center;gap:6px;padding-right:16px;
              border-right:1px solid var(--hair-2)}
  .live-label::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--accent);
              box-shadow:0 0 6px var(--accent);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  h1{font-family:var(--mono);font-weight:700;font-size:18px;margin:0;letter-spacing:.02em;
     color:var(--bright);text-transform:uppercase}
  .sub{color:var(--muted);font-size:11px;flex-basis:100%;order:5;margin-top:-2px}
  .readout{display:flex;gap:24px;margin-left:auto;align-items:center}
  .stat{text-align:right;padding-left:24px;border-left:1px solid var(--hair-2)}
  .stat:first-child{border-left:0;padding-left:0}
  .stat .n{font-family:var(--mono);font-size:20px;font-weight:700;line-height:1;color:var(--bright)}
  .stat .l{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:3px}
  .stat .n.hot{color:var(--red)}

  /* Controls strip */
  .controls{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:10px 16px}
  .search input{width:100%;padding:8px 10px;border:1px solid var(--hair-2);background:var(--page);
        font:inherit;font-size:13px;color:var(--text);font-family:var(--mono)}
  .search input::placeholder{color:var(--muted)}
  .search input:focus{outline:1px solid var(--accent);outline-offset:0;border-color:var(--accent)}
  .filters{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:9px}
  .flabel{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .seg{display:inline-flex;border:1px solid var(--hair-2);overflow:hidden;flex-wrap:wrap}
  .seg button{font:inherit;font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted);
        background:var(--page);border:0;padding:6px 10px;cursor:pointer;border-left:1px solid var(--hair-2);
        text-transform:uppercase;letter-spacing:.03em}
  .seg button:first-child{border-left:0}
  .seg button:hover{color:var(--text)}
  .seg button[aria-pressed="true"]{background:var(--accent-dim);color:var(--accent)}

  /* Data grid */
  .list{background:var(--card);border:1px solid var(--hair);border-top:0}
  .row{padding:9px 16px;border-top:1px solid var(--hair);display:flex;gap:14px;align-items:flex-start}
  .row:first-child{border-top:0}
  .row:nth-child(even){background:var(--panel-2)}
  .row:hover{background:#161d28}
  .badge{font-size:9.5px;font-weight:700;padding:3px 7px;white-space:nowrap;margin-top:1px;
         letter-spacing:.06em;text-transform:uppercase;border:1px solid transparent}
  .chk{display:inline-block;margin-left:8px;font-size:9.5px;font-weight:700;padding:2px 6px;
       white-space:nowrap;cursor:help;vertical-align:middle;letter-spacing:.04em;text-transform:uppercase}
  .chk-bad{background:var(--red-bg);color:var(--red);border:1px solid #4a1f1a}
  .chk-warn{background:var(--amber-bg);color:var(--amber);border:1px solid #4a3a17}
  .badge.RENEWAL{background:var(--red-bg);color:var(--red);border-color:#4a1f1a}
  .badge.NEW{background:var(--green-bg);color:var(--green);border-color:var(--accent-dim)}
  .badge.UPDATED{background:var(--amber-bg);color:var(--amber);border-color:#4a3a17}
  .body{flex:1;min-width:0}
  .org{font-size:13px;font-weight:700;color:var(--bright);letter-spacing:.01em}
  .svc{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-top:1px}
  .detail{font-size:12px;margin-top:4px;color:var(--text)}
  .detail b{color:var(--accent);font-weight:500}
  .meta{font-size:11px;color:var(--muted);margin-top:4px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
  .verify{color:var(--link);text-decoration:none;font-weight:500}
  .verify:hover{text-decoration:underline}
  .date{font-size:11px;color:var(--muted);white-space:nowrap;margin-top:1px;text-align:right}
  .date-abs{font-weight:700;color:var(--text);font-size:12px}
  .date-ago{font-size:10px;color:var(--muted);margin-top:2px}
  .empty{padding:40px 24px;text-align:center;color:var(--muted);font-size:13px}
  .empty b{color:var(--bright)}
  .foot{max-width:1600px;margin:12px auto 0;color:var(--muted);font-size:11px;line-height:1.55}
  .foot b{color:var(--text)}

  /* Split-view */
  .wrap{max-width:1600px}
  .split{display:flex;gap:2px;align-items:flex-start}
  .left{flex:1 1 46%;min-width:0}
  .right{flex:1 1 54%;position:sticky;top:12px;height:calc(100vh - 24px);
         background:var(--panel);border:1px solid var(--hair);border-top:0;
         display:flex;flex-direction:column;overflow:hidden}
  .row{cursor:pointer}
  .row.sel{background:var(--accent-dim) !important;box-shadow:inset 3px 0 0 var(--accent)}
  .detail-empty{margin:auto;text-align:center;color:var(--muted);font-size:13px;padding:40px}
  .de-icon{font-size:40px;color:var(--hair2);margin-bottom:14px}
  .detail-head{display:flex;align-items:center;gap:12px;padding:10px 14px;
       border-bottom:1px solid var(--hair);background:#0c1219}
  .dh-adam{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.04em}
  .dh-close{margin-left:auto;color:var(--muted);cursor:pointer;text-decoration:none;font-size:14px}
  .dh-close:hover{color:var(--red)}
  #detail-frame{flex:1;width:100%;border:0;background:var(--page)}
  .detail-missing{margin:auto;text-align:center;padding:40px 30px;max-width:420px}
  .dm-title{color:var(--amber);font-size:14px;font-weight:700;margin-bottom:10px}
  .dm-sub{color:var(--muted);font-size:12px;line-height:1.6;margin-bottom:20px}
  .dm-btn{display:inline-block;background:var(--accent-dim);color:var(--accent);
       border:1px solid var(--accent);padding:10px 18px;text-decoration:none;
       font-weight:700;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
  .dm-btn:hover{background:var(--accent);color:var(--page)}
  .dm-alt{display:block;margin-top:16px;color:var(--link);font-size:11px;text-decoration:none}
  .dm-alt:hover{text-decoration:underline}
  @media(max-width:900px){
    .split{flex-direction:column}
    .right{position:static;width:100%;height:70vh;border-top:1px solid var(--hair)}
  }
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
  <div class="split">
    <div class="left">
      <main class="list" id="list"></main>
      <div class="empty" id="empty" style="display:none"></div>
    </div>
    <div class="right" id="detail">
      <div class="detail-empty" id="detail-empty">
        <div class="de-icon">◧</div>
        <div>Διάλεξε μια σύμβαση αριστερά<br>για να δεις το πλήρες κείμενο εδώ.</div>
      </div>
      <div class="detail-head" id="detail-head" style="display:none">
        <span class="dh-adam" id="dh-adam"></span>
        <a class="dh-close" id="dh-close" title="Κλείσιμο">✕</a>
      </div>
      <iframe id="detail-frame" style="display:none"></iframe>
      <div class="detail-missing" id="detail-missing" style="display:none">
        <div class="dm-title">Το πλήρες κείμενο δεν έχει δημιουργηθεί ακόμα</div>
        <div class="dm-sub">Τρέξε το Contract Reader για αυτό το ΑΔΑΜ (μία φορά), και μετά θα ανοίγει εδώ αμέσως.</div>
        <a class="dm-btn" id="dm-btn" target="_blank" rel="noopener">▶ Δημιουργία κειμένου</a>
        <a class="dm-alt" id="dm-alt" target="_blank" rel="noopener">ή άνοιξε το πρωτότυπο PDF ↗</a>
      </div>
    </div>
  </div>
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

// ── Split-view detail pane ────────────────────────────────────────────────
const REPO_ACTIONS = "https://github.com/delta-primecs/tender-monitor/actions/workflows/contract_reader.yml";
const CONTRACT_BASE = "contracts/";  // relative to this page on GitHub Pages
const KHMDHS_PDF = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/";
let selectedRow=null;

function openDetail(e, rowEl){
  // highlight
  if(selectedRow) selectedRow.classList.remove('sel');
  rowEl.classList.add('sel'); selectedRow=rowEl;

  const adam=e.adam;
  const deEmpty=document.getElementById('detail-empty');
  const deHead=document.getElementById('detail-head');
  const deFrame=document.getElementById('detail-frame');
  const deMiss=document.getElementById('detail-missing');
  deEmpty.style.display='none';

  const url=CONTRACT_BASE+adam+'.html';
  // Check if the pre-generated contract text exists
  fetch(url, {method:'HEAD'}).then(r=>{
    if(r.ok){
      // exists → load in iframe
      deHead.style.display='flex';
      document.getElementById('dh-adam').textContent=adam;
      deFrame.style.display='block';
      deMiss.style.display='none';
      deFrame.src=url;
    } else {
      showMissing(adam);
    }
  }).catch(()=>showMissing(adam));

  function showMissing(adam){
    deHead.style.display='flex';
    document.getElementById('dh-adam').textContent=adam;
    deFrame.style.display='none';
    deMiss.style.display='flex';
    deMiss.style.flexDirection='column';
    document.getElementById('dm-btn').href=REPO_ACTIONS;
    document.getElementById('dm-alt').href=KHMDHS_PDF+adam;
  }
}

document.getElementById('dh-close').addEventListener('click', ()=>{
  document.getElementById('detail-head').style.display='none';
  document.getElementById('detail-frame').style.display='none';
  document.getElementById('detail-missing').style.display='none';
  document.getElementById('detail-empty').style.display='flex';
  if(selectedRow){selectedRow.classList.remove('sel');selectedRow=null;}
});

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
      (e.adam?' <span class="verify">Άνοιγμα κειμένου →</span>':'')+'</div></div>'+
      '<div class="date"><div class="date-abs">'+dmy(e.date)+'</div>'+
      '<div class="date-ago">καταγράφηκε '+ago+'</div></div>';
    if(e.adam){
      el.addEventListener('click', ()=>openDetail(e, el));
    }
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
