"""
Contractors page — build docs/contractors.html
Sixth tab. Reads data/contracts.jsonl (the ingester's memory store), lets you
type a contractor name to see every contract they've ever signed across your
service lines, and downloads exactly that view as a CSV that opens in Excel.
"""

import os
import json
from datetime import datetime, timezone, timedelta

STORE = "data/contracts.jsonl"
OUT = "docs/contractors.html"


def load_store():
    if not os.path.exists(STORE):
        return []
    rows = []
    with open(STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("holder") and not r.get("superseded_by"):
                rows.append({
                    "holder": r.get("holder"),
                    "org": r.get("org"),
                    "region": r.get("region"),
                    "service": r.get("service"),
                    "value": r.get("value") or 0,
                    "signed": r.get("signed"),
                    "end": r.get("end"),
                    "adam": r.get("adam"),
                })
    # newest first
    rows.sort(key=lambda x: x.get("signed") or "", reverse=True)
    return rows


def main():
    rows = load_store()
    os.makedirs("docs", exist_ok=True)
    athens = datetime.now(timezone(timedelta(hours=3)))
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False))
            .replace("__STAMP__", athens.strftime("%d/%m/%Y %H:%M")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    holders = len({r["holder"] for r in rows})
    print(f"Wrote {OUT}: {len(rows)} contracts, {holders} distinct contractors.")


TEMPLATE = r"""<!doctype html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contractors</title>
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#1b3d3a;--ink-2:#265351;--page:#ebefee;--card:#fff;--text:#14202b;
    --muted:#63748a;--hair:#dce3e0;--link:#1f6f6b;--link-ink:#155551;
    --gold:#8a5a11;--gold-bg:#f6ecd2;--tag:#2c4a66;--tag-bg:#e7edf3;
  }
  *{box-sizing:border-box}html,body{margin:0}
  body{background:var(--page);color:var(--text);font-family:'Inter',Arial,sans-serif;line-height:1.5;padding:24px 16px 56px;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1100px;margin:0 auto}
  .nav{max-width:1100px;margin:0 auto 12px;display:flex;gap:8px;font-size:13px;flex-wrap:wrap}
  .nav a{text-decoration:none;color:var(--muted);padding:6px 12px;border:1px solid var(--hair);border-radius:8px;background:#fff}
  .nav a.on{background:var(--ink);color:#fff;border-color:var(--ink)}
  .desk{background:linear-gradient(160deg,var(--ink),var(--ink-2));color:#e8f2f0;border-radius:14px 14px 0 0;padding:22px 24px 20px}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#9fd0ca;font-weight:600}
  h1{font-family:'Commissioner',sans-serif;font-weight:700;font-size:27px;margin:8px 0 2px;letter-spacing:-.01em}
  .sub{color:#a7c3bd;font-size:12.5px}
  .readout{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}
  .stat .n{font-family:'Commissioner',sans-serif;font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8fae9f;margin-top:4px}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .search{flex:1;min-width:220px}
  .search input{width:100%;padding:11px 12px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;background:#fbfcfd}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px}
  .btn{font:inherit;font-size:13px;font-weight:600;color:#fff;background:var(--link);border:0;padding:10px 14px;border-radius:9px;cursor:pointer}
  .btn:hover{background:var(--link-ink)}
  .btn[disabled]{background:#b5c2c0;cursor:default}
  .profile{background:#f6f9f8;border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:14px 18px}
  .profile-head{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;padding-bottom:10px;border-bottom:1px solid var(--hair)}
  .profile-name{font-family:'Commissioner',sans-serif;font-weight:700;font-size:18px;color:var(--ink);letter-spacing:-.005em}
  .profile-stats{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-left:auto}
  .profile-stats b{color:var(--link-ink);font-family:'Commissioner',sans-serif;font-weight:700;font-size:13px}
  .profile-lines{padding:10px 0 4px;display:flex;flex-direction:column;gap:5px}
  .profile-line{font-size:13px;color:var(--muted)}
  .profile-line .p-label{color:var(--muted);font-weight:600;letter-spacing:.02em}
  .profile-line .p-value{color:var(--text)}
  .profile-line.hot .p-value{color:var(--gold);font-weight:700}
  .profile-tools{display:flex;align-items:center;gap:10px;margin-top:8px;padding-top:10px;border-top:1px solid var(--hair)}
  .p-label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:7px;overflow:hidden;background:#fff}
  .seg button{font:inherit;font-size:12px;font-weight:500;color:var(--muted);background:#fff;border:0;padding:5px 10px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  tr.group-head td{background:#f0f4f2;font-family:'Commissioner',sans-serif;font-weight:700;color:var(--ink);font-size:13px;padding-top:14px;padding-bottom:8px;letter-spacing:.005em}
  tr.group-head td .g-count{color:var(--muted);font-weight:500;font-size:12px;font-family:'Inter',sans-serif;margin-left:8px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;border-radius:0 0 14px 14px;overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:10px 12px;text-align:left;border-top:1px solid var(--hair);vertical-align:top}
  th{background:#f5f7f6;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700;cursor:pointer;user-select:none;position:sticky;top:0}
  th:hover{color:var(--text)}
  th .arr{display:inline-block;width:10px;color:var(--muted)}
  tr:hover td{background:#faf9f5}
  .holder{font-weight:600;color:var(--link-ink)}
  .org{color:var(--text)}
  .service{font-size:11.5px;font-weight:600;color:var(--tag);background:var(--tag-bg);border-radius:5px;padding:2px 8px;white-space:nowrap}
  .value{font-family:'Commissioner',sans-serif;font-weight:700;color:var(--gold);white-space:nowrap}
  .date{color:var(--muted);white-space:nowrap}
  .adam{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;color:var(--muted)}
  .doc{color:var(--link-ink);text-decoration:none;font-weight:600}
  .doc:hover{text-decoration:underline}
  .empty{padding:34px;text-align:center;color:var(--muted)}
  .foot{max-width:1100px;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .foot b{color:var(--text)}
</style>
</head>
<body>
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <header class="desk">
    <div class="live-label">Contractors · ΚΗΜΔΗΣ</div>
    <h1>Contractors</h1>
    <div class="sub">Πληκτρολόγησε όνομα αναδόχου — δες κάθε σύμβαση που έχει υπογράψει · κατέβασε σε CSV/Excel</div>
    <div class="readout">
      <div class="stat"><div class="n" id="s-rows">0</div><div class="l">Contracts shown</div></div>
      <div class="stat"><div class="n" id="s-sum">0 €</div><div class="l">Total value shown</div></div>
      <div class="stat"><div class="n" style="font-size:15px">__STAMP__</div><div class="l">Δεδομένα έως</div></div>
    </div>
  </header>
  <div class="controls">
    <div class="search"><input id="q" type="search" placeholder="Ανάδοχος — π.χ. EMERA, LEVER, AUDIT REVIEW…" autofocus></div>
    <button id="dl" class="btn" disabled>Download CSV</button>
  </div>
  <section id="profile" class="profile" style="display:none">
    <div class="profile-head">
      <div class="profile-name" id="p-name"></div>
      <div class="profile-stats">
        <span><b id="p-contracts">0</b> συμβάσεις</span>
        <span><b id="p-value">0 €</b> συνολική αξία</span>
        <span><b id="p-clients">0</b> διαφορετικοί φορείς</span>
        <span>μ.ό. <b id="p-avg">0 €</b> ανά σύμβαση</span>
      </div>
    </div>
    <div class="profile-lines">
      <div class="profile-line"><span class="p-label">Κυρίως δραστήρια σε:</span> <span id="p-topsvc" class="p-value">—</span></div>
      <div class="profile-line"><span class="p-label">Τελευταία υπογραφή:</span> <span id="p-latest" class="p-value">—</span></div>
      <div class="profile-line hot"><span class="p-label">Λήγουν στους επόμενους 6 μήνες:</span> <span id="p-expiring" class="p-value">—</span></div>
    </div>
    <div class="profile-tools">
      <span class="p-label">Ομαδοποίηση:</span>
      <div class="seg">
        <button data-grp="none" aria-pressed="true">Καμία</button>
        <button data-grp="service" aria-pressed="false">Ανά υπηρεσία</button>
        <button data-grp="org" aria-pressed="false">Ανά οργανισμό</button>
      </div>
    </div>
  </section>
  <main class="list">
    <table id="tbl">
      <thead><tr>
        <th data-k="holder">Ανάδοχος <span class="arr"></span></th>
        <th data-k="org">Οργανισμός <span class="arr"></span></th>
        <th data-k="service">Υπηρεσία <span class="arr"></span></th>
        <th data-k="value">Αξία <span class="arr"></span></th>
        <th data-k="signed">Υπογραφή <span class="arr"></span></th>
        <th data-k="end">Λήγει <span class="arr"></span></th>
        <th>ΑΔΑΜ</th>
      </tr></thead>
      <tbody id="body"></tbody>
    </table>
    <div class="empty" id="empty" style="display:none">Γράψε όνομα αναδόχου παραπάνω.</div>
  </main>
</div>
<p class="foot">
  Πηγή: <b>data/contracts.jsonl</b> (η μνήμη του συστήματος, ανανεώνεται 2×/ημέρα από τον ingester).
  Το CSV εξάγει ό,τι φαίνεται στην οθόνη με τα φίλτρα σου. Ανοίγει σε Excel — για ελληνικά χρησιμοποιεί UTF-8 με BOM.
</p>
<script>
const ROWS = __DATA__;
const qEl=document.getElementById('q'), body=document.getElementById('body'),
      empty=document.getElementById('empty'), dl=document.getElementById('dl');
const profile=document.getElementById('profile');
const money=n=>new Intl.NumberFormat('el-GR',{maximumFractionDigits:0}).format(n||0)+' €';
const dmy=s=>s?s.split('-').reverse().join('/'):'';
const TODAY = new Date().toISOString().slice(0,10);
const SIX_MO = (()=>{const d=new Date();d.setMonth(d.getMonth()+6);return d.toISOString().slice(0,10);})();
let sortKey='signed', sortDir=-1, current=[], grpMode='none';

function filtered(){
  const q=qEl.value.trim().toLowerCase();
  if(!q) return [];
  return dedupRepublications(ROWS.filter(r=>(r.holder||'').toLowerCase().includes(q)));
}

// Public bodies sometimes republish the SAME contract to ΚΗΜΔΗΣ with a fresh
// ΑΔΑΜ — typically to correct a typo, tax number, or attachment. Commercially
// it is ONE contract, but the ingester (correctly) sees two records because
// the ΑΔΑΜ differs. Collapse them here on the read side, keeping the newest
// ΑΔΑΜ (the corrected version). Match key: holder + org + value + signed + end.
// All five fields must agree — tight enough that genuine separate contracts
// (even between the same parties in the same week) don't collapse.
function dedupRepublications(rows){
  const groups = new Map();
  rows.forEach(r=>{
    const k = [r.holder||'', r.org||'', r.value||0, r.signed||'', r.end||''].join('|');
    (groups.get(k) || groups.set(k, []).get(k)).push(r);
  });
  const kept = [];
  groups.forEach(g=>{
    if(g.length === 1){ kept.push(g[0]); return; }
    // Multiple with identical business fingerprint → keep newest ΑΔΑΜ.
    // ΚΗΜΔΗΣ ΑΔΑΜ sort lexicographically in publication order, so max wins.
    g.sort((a,b)=>(a.adam||'').localeCompare(b.adam||''));
    kept.push(g[g.length-1]);
  });
  return kept;
}

function rowHTML(r){
  return '<tr>'+
    '<td class="holder">'+(r.holder||'')+'</td>'+
    '<td class="org">'+(r.org||'')+(r.region?' <span class="date">· '+r.region+'</span>':'')+'</td>'+
    '<td>'+(r.service?'<span class="service">'+r.service+'</span>':'')+'</td>'+
    '<td class="value">'+money(r.value)+'</td>'+
    '<td class="date">'+dmy(r.signed)+'</td>'+
    '<td class="date">'+dmy(r.end)+'</td>'+
    '<td class="adam">'+(r.adam?'<a class="doc" target="_blank" rel="noopener" href="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+r.adam+'">'+r.adam+' ↗</a>':'')+'</td>'+
  '</tr>';
}

function renderProfile(rows){
  if(!rows.length){ profile.style.display='none'; return; }
  // Dominant holder name (there may be minor spelling variants — pick the most common)
  const nameCount={};
  rows.forEach(r=>{ const n=r.holder||''; nameCount[n]=(nameCount[n]||0)+1; });
  const topName = Object.keys(nameCount).sort((a,b)=>nameCount[b]-nameCount[a])[0];

  const totalVal = rows.reduce((s,r)=>s+(r.value||0),0);
  const clients  = new Set(rows.map(r=>r.org).filter(Boolean)).size;
  const avg      = rows.length ? totalVal/rows.length : 0;

  // Top service
  const svcCount={};
  rows.forEach(r=>{ if(r.service){ svcCount[r.service]=(svcCount[r.service]||0)+1; }});
  const svcRanked = Object.entries(svcCount).sort((a,b)=>b[1]-a[1]);
  const topSvcText = svcRanked.length
    ? svcRanked.slice(0,3).map(([s,n])=>s+' ('+n+')').join(' · ')
    : '—';

  // Latest signing
  const dated = rows.filter(r=>r.signed).sort((a,b)=>b.signed.localeCompare(a.signed));
  const latest = dated[0];
  const latestText = latest
    ? dmy(latest.signed)+' — '+(latest.org||'—')
    : '—';

  // Expiring in the next 6 months
  const expiring = rows.filter(r=>r.end && r.end>=TODAY && r.end<=SIX_MO)
                       .sort((a,b)=>a.end.localeCompare(b.end));
  const expText = expiring.length
    ? expiring.length+' — από '+dmy(expiring[0].end)+' ('+(expiring[0].org||'—')+')'
    : 'καμία';

  document.getElementById('p-name').textContent      = topName;
  document.getElementById('p-contracts').textContent = rows.length;
  document.getElementById('p-value').textContent     = money(totalVal);
  document.getElementById('p-clients').textContent   = clients;
  document.getElementById('p-avg').textContent       = money(avg);
  document.getElementById('p-topsvc').textContent    = topSvcText;
  document.getElementById('p-latest').textContent    = latestText;
  document.getElementById('p-expiring').textContent  = expText;
  profile.style.display='block';
}

function renderGrouped(rows){
  // Group rows by the chosen key, preserving current sort inside each group.
  const key = grpMode==='service' ? 'service' : 'org';
  const groups = {};
  rows.forEach(r=>{
    const k = r[key] || '(χωρίς τιμή)';
    (groups[k] = groups[k] || []).push(r);
  });
  // Sort groups by size, biggest first
  const ordered = Object.entries(groups).sort((a,b)=>b[1].length-a[1].length);
  return ordered.map(([g, gRows])=>{
    const gVal = gRows.reduce((s,r)=>s+(r.value||0),0);
    return '<tr class="group-head"><td colspan="7">'+g+
           ' <span class="g-count">'+gRows.length+' συμβάσεις · '+money(gVal)+'</span></td></tr>'+
           gRows.map(rowHTML).join('');
  }).join('');
}

function render(){
  current = filtered().slice();
  current.sort((a,b)=>{
    const x=a[sortKey]||'', y=b[sortKey]||'';
    if(sortKey==='value') return (x-y)*sortDir;
    return String(x).localeCompare(String(y),'el')*sortDir;
  });
  renderProfile(current);
  body.innerHTML = grpMode==='none'
    ? current.slice(0,2000).map(rowHTML).join('')
    : renderGrouped(current.slice(0,2000));
  const showing = qEl.value.trim().length > 0;
  empty.style.display = (!showing || current.length===0) ? 'block' : 'none';
  empty.textContent = !showing ? 'Γράψε όνομα αναδόχου παραπάνω.'
                       : (current.length===0 ? 'Κανένας ανάδοχος δεν ταιριάζει.' : '');
  document.getElementById('s-rows').textContent = current.length;
  document.getElementById('s-sum').textContent = money(current.reduce((s,r)=>s+(r.value||0),0));
  dl.disabled = current.length===0;
}
qEl.addEventListener('input', render);
document.querySelectorAll('[data-grp]').forEach(b=>b.addEventListener('click',()=>{
  grpMode = b.dataset.grp;
  document.querySelectorAll('[data-grp]').forEach(x=>x.setAttribute('aria-pressed', x===b));
  render();
}));
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k;
  if(sortKey===k) sortDir=-sortDir; else { sortKey=k; sortDir = (k==='value'||k==='signed'||k==='end') ? -1 : 1; }
  render();
}));

// CSV export — UTF-8 with BOM so Excel reads Greek correctly.
function csvField(v){
  const s = v==null ? '' : String(v);
  return /[",;\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
}
dl.addEventListener('click', ()=>{
  if(!current.length) return;
  const header = ['Ανάδοχος','Οργανισμός','Περιοχή','Υπηρεσία','Αξία (€)','Υπογραφή','Λήγει','ΑΔΑΜ','Σύμβαση'];
  const lines = [header.join(';')];
  current.forEach(r=>{
    lines.push([
      r.holder, r.org, r.region, r.service, r.value,
      dmy(r.signed), dmy(r.end), r.adam,
      r.adam ? 'https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+r.adam : ''
    ].map(csvField).join(';'));
  });
  const blob = new Blob(['\ufeff'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  const name = (qEl.value.trim() || 'contractors').replace(/[^\p{L}\p{N}._-]+/gu,'_').slice(0,60);
  a.href = URL.createObjectURL(blob);
  a.download = 'contractors_'+name+'.csv';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 2000);
});

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
