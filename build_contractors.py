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
                    "amendment": bool(r.get("amendment")),
                    "subject": r.get("subject") or "",
                    "subject_check": r.get("subject_check") or "unverified",
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
  
  
  .desk{background:var(--panel);color:var(--text);border:1px solid var(--hair);padding:22px 24px 20px}
  .live-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#9fd0ca;font-weight:600}
  h1{font-family:var(--mono);font-weight:700;font-size:27px;margin:8px 0 2px;letter-spacing:-.01em}
  .sub{color:#a7c3bd;font-size:12.5px}
  .readout{display:flex;gap:22px;margin-top:16px;flex-wrap:wrap}
  .stat .n{font-family:var(--mono);font-size:22px;font-weight:700;line-height:1}
  .stat .l{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8fae9f;margin-top:4px}
  .controls{background:var(--card);border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .search{flex:1;min-width:220px}
  .search input{width:100%;padding:11px 12px;border:1px solid var(--hair);border-radius:9px;font:inherit;font-size:14.5px;background:var(--page)}
  .search input:focus{outline:2px solid var(--link);outline-offset:1px}
  .btn{font:inherit;font-size:13px;font-weight:600;color:#fff;background:var(--link);border:0;padding:10px 14px;border-radius:9px;cursor:pointer}
  .btn:hover{background:var(--link-ink)}
  .btn[disabled]{background:#b5c2c0;cursor:default}
  .profile{background:#f6f9f8;border-left:1px solid var(--hair);border-right:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:14px 18px}
  .profile-head{display:flex;align-items:baseline;gap:20px;flex-wrap:wrap;padding-bottom:10px;border-bottom:1px solid var(--hair)}
  .profile-name{font-family:var(--mono);font-weight:700;font-size:18px;color:var(--ink);letter-spacing:-.005em}
  .profile-stats{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin-left:auto}
  .profile-stats b{color:var(--link-ink);font-family:var(--mono);font-weight:700;font-size:13px}
  .profile-lines{padding:10px 0 4px;display:flex;flex-direction:column;gap:5px}
  .profile-line{font-size:13px;color:var(--muted)}
  .profile-line .p-label{color:var(--muted);font-weight:600;letter-spacing:.02em}
  .profile-line .p-value{color:var(--text)}
  .profile-line.hot .p-value{color:var(--gold);font-weight:700}
  .profile-tools{display:flex;align-items:center;gap:10px;margin-top:8px;padding-top:10px;border-top:1px solid var(--hair)}
  .p-label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700}
  .seg{display:inline-flex;border:1px solid var(--hair);border-radius:7px;overflow:hidden;background:var(--card)}
  .seg button{font:inherit;font-size:12px;font-weight:500;color:var(--muted);background:var(--card);border:0;padding:5px 10px;cursor:pointer;border-left:1px solid var(--hair)}
  .seg button:first-child{border-left:0}
  .seg button[aria-pressed="true"]{background:var(--ink);color:#fff}
  tr.group-head td{background:#f0f4f2;font-family:var(--mono);font-weight:700;color:var(--ink);font-size:13px;padding-top:14px;padding-bottom:8px;letter-spacing:.005em}
  tr.group-head td .g-count{color:var(--muted);font-weight:500;font-size:12px;font-family:var(--mono);margin-left:8px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0;;overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:10px 12px;text-align:left;border-top:1px solid var(--hair);vertical-align:top}
  th{background:#f5f7f6;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700;cursor:pointer;user-select:none;position:sticky;top:0}
  th:hover{color:var(--text)}
  th .arr{display:inline-block;width:10px;color:var(--muted)}
  tr:hover td{background:#faf9f5}
  .holder{font-weight:600;color:var(--link-ink)}
  .org{color:var(--text)}
  .service{font-size:11.5px;font-weight:600;color:var(--tag);background:var(--tag-bg);border-radius:5px;padding:2px 8px;white-space:nowrap}
  .tag-amend{display:inline-block;margin-left:6px;font-size:10.5px;font-weight:700;letter-spacing:.04em;color:#8a5a11;background:#f6ecd2;border-radius:5px;padding:2px 8px;white-space:nowrap;cursor:help}
  .tag-chk{display:inline-block;margin-left:6px;font-size:10.5px;font-weight:700;border-radius:5px;padding:2px 8px;white-space:nowrap;cursor:help}
  .tag-bad{color:#8a1a10;background:#f4d0cb}
  .tag-warn{color:#8a5a11;background:#f6ecd2}
  tr.is-amend td{background:#fdfbf3}
  .value{font-family:var(--mono);font-weight:700;color:var(--gold);white-space:nowrap}
  .date{color:var(--muted);white-space:nowrap}
  .adam{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;color:var(--muted)}
  .doc{color:var(--link-ink);text-decoration:none;font-weight:600}
  .doc:hover{text-decoration:underline}
  .empty{padding:34px;text-align:center;color:var(--muted)}
  .foot{max-width:none;margin:16px auto 0;color:var(--muted);font-size:12.5px;line-height:1.55}
  .split{display:flex;gap:2px;align-items:flex-start}
  .left{flex:1 1 55%;min-width:0;overflow-x:auto}
  .right{flex:1 1 45%;position:sticky;top:12px;height:calc(100vh - 24px);
         background:var(--panel);border:1px solid var(--hair);border-top:0;
         display:flex;flex-direction:column;overflow:hidden}
  tbody tr[data-adam]{cursor:pointer}
  tbody tr.sel{background:var(--accent-dim)!important;box-shadow:inset 3px 0 0 var(--accent)}
  .opencue{color:var(--link);font-size:10.5px;margin-left:6px;opacity:0;white-space:nowrap}
  tbody tr:hover .opencue{opacity:1}
  .detail-empty{margin:auto;text-align:center;color:var(--muted);font-size:13px;padding:40px}
  .de-icon{font-size:40px;color:var(--hair2);margin-bottom:14px}
  .detail-head{display:flex;align-items:center;gap:12px;padding:10px 14px;
       border-bottom:1px solid var(--hair);background:#0c1219}
  .dh-adam{color:var(--accent);font-weight:700;font-size:12px;letter-spacing:.04em}
  .dh-close{margin-left:auto;color:var(--muted);cursor:pointer;text-decoration:none;font-size:14px}
  .dh-close:hover{color:var(--hot,#ff5d52)}
  #detail-frame{flex:1;width:100%;border:0;background:var(--page)}
  .detail-missing{margin:auto;text-align:center;padding:40px 30px;max-width:420px}
  .dm-title{color:var(--signal,#e8a13a);font-size:14px;font-weight:700;margin-bottom:10px}
  .dm-sub{color:var(--muted);font-size:12px;line-height:1.6;margin-bottom:20px}
  .dm-btn{display:inline-block;background:var(--accent-dim);color:var(--accent);
       border:1px solid var(--accent);padding:10px 18px;text-decoration:none;
       font-weight:700;font-size:12px;letter-spacing:.04em;text-transform:uppercase}
  .dm-btn:hover{background:var(--accent);color:var(--page)}
  .dm-alt{display:block;margin-top:16px;color:var(--link);font-size:11px;text-decoration:none}
  .hint-cmd{font-size:11px;color:var(--muted)}
  .hint-cmd b{color:var(--accent)}
  @media(max-width:900px){
    .split{flex-direction:column}
    .right{position:static;width:100%;height:70vh;border-top:1px solid var(--hair)}
  }
  .foot b{color:var(--text)}
</style>
</head>
<body>
<link rel="stylesheet" href="godel.css">
<div id="nav"></div>
<script src="nav.js"></script>
<div class="wrap">
  <div class="deskbar">
    <span class="db-title">CONTRACTORS</span>
    <span class="db-sub">ΚΗΜΔΗΣ</span>
    <div class="db-filters">
      <button id="dl" class="btn" disabled>Download CSV</button>
      <button id="dl90" class="btn" title="Συμβάσεις που λήγουν στις επόμενες 90 ημέρες — hit list">⬇ Λήξεις 90ημ</button>
      <span class="hint-cmd">αναζήτηση: <b>CON &lt;όνομα&gt;</b></span>
    </div>
    <div class="db-stats">
      <span><b id="s-rows">0</b> συμβ.</span>
      <span><b id="s-sum">0 €</b></span>
      <span class="db-stamp">__STAMP__</span>
    </div>
    <input id="q" type="search" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none" tabindex="-1" aria-hidden="true">
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
  <div class="split">
    <div class="left">
      <main class="list">
        <table id="tbl">
          <thead><tr>
            <th data-k="holder">Ανάδοχος <span class="arr"></span></th>
            <th data-k="org">Οργανισμός <span class="arr"></span></th>
            <th data-k="service">Υπηρεσία <span class="arr"></span></th>
            <th data-k="value">Αξία <span class="arr"></span></th>
            <th data-k="signed">Υπογραφή <span class="arr"></span></th>
            <th data-k="end">Λήγει <span class="arr"></span></th>
          </tr></thead>
          <tbody id="body"></tbody>
        </table>
        <div class="empty" id="empty" style="display:none">Χρησιμοποίησε το command bar: <b>CON &lt;όνομα&gt;</b></div>
      </main>
    </div>
    <div class="right" id="detail">
      <div class="detail-empty" id="detail-empty">
        <div class="de-icon">◧</div>
        <div>Κλικ σε σύμβαση αριστερά<br>για το πλήρες κείμενο εδώ.</div>
      </div>
      <div class="detail-head" id="detail-head" style="display:none">
        <span class="dh-adam" id="dh-adam"></span>
        <a class="dh-close" id="dh-close" title="Κλείσιμο">✕</a>
      </div>
      <iframe id="detail-frame" style="display:none"></iframe>
      <div class="detail-missing" id="detail-missing" style="display:none">
        <div class="dm-title">Το κείμενο δεν έχει δημιουργηθεί ακόμα</div>
        <div class="dm-sub">Τρέξε το Contract Reader για αυτό το ΑΔΑΜ (μία φορά), και μετά ανοίγει εδώ αμέσως.</div>
        <a class="dm-btn" id="dm-btn" target="_blank" rel="noopener">▶ Δημιουργία κειμένου</a>
        <a class="dm-alt" id="dm-alt" target="_blank" rel="noopener">ή άνοιξε το πρωτότυπο PDF ↗</a>
      </div>
    </div>
  </div>
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
  const amend = r.amendment
    ? '<span class="tag-amend" title="'+(r.subject||'').replace(/"/g,'&quot;')+'">ΠΑΡΑΤΑΣΗ / ΤΡΟΠΟΠΟΙΗΣΗ</span>'
    : '';
  const sc = r.subject_check || 'unverified';
  const chk = sc==='mismatch'
    ? '<span class="tag-chk tag-bad" title="'+(r.subject||'').replace(/"/g,'&quot;')+'">⚠ τίτλος αντίθετος</span>'
    : (sc==='unverified'
        ? '<span class="tag-chk tag-warn" title="Ο τίτλος δεν επιβεβαιώνει την υπηρεσία — έλεγξε τη σύμβαση">⚠ προς επιβεβαίωση</span>'
        : '');
  return '<tr'+(r.amendment?' class="is-amend"':'')+' data-adam="'+(r.adam||'')+'">'+
    '<td class="holder">'+(r.holder||'')+'</td>'+
    '<td class="org">'+(r.org||'')+(r.region?' <span class="date">· '+r.region+'</span>':'')+'</td>'+
    '<td>'+(r.service?'<span class="service">'+r.service+'</span>':'')+amend+chk+'</td>'+
    '<td class="value">'+money(r.value)+'</td>'+
    '<td class="date">'+dmy(r.signed)+'</td>'+
    '<td class="date">'+dmy(r.end)+(r.adam?' <span class="opencue">κείμενο →</span>':'')+'</td>'+
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

// ── Split-view: click a row → open its contract text on the right ─────────
const REPO_ACTIONS="https://github.com/delta-primecs/tender-monitor/actions/workflows/contract_reader.yml";
const KHMDHS_PDF="https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/";
let selRow=null;
body.addEventListener('click', (e)=>{
  const tr=e.target.closest('tr[data-adam]');
  if(!tr) return;
  const adam=tr.getAttribute('data-adam');
  if(!adam) return;
  if(selRow) selRow.classList.remove('sel');
  tr.classList.add('sel'); selRow=tr;
  const deEmpty=document.getElementById('detail-empty'),
        deHead=document.getElementById('detail-head'),
        deFrame=document.getElementById('detail-frame'),
        deMiss=document.getElementById('detail-missing');
  deEmpty.style.display='none';
  const url='contracts/'+adam+'.html';
  fetch(url,{method:'HEAD'}).then(r=>{
    deHead.style.display='flex';
    document.getElementById('dh-adam').textContent=adam;
    if(r.ok){
      deFrame.style.display='block'; deMiss.style.display='none'; deFrame.src=url;
    } else { showMiss(); }
  }).catch(showMiss);
  function showMiss(){
    deHead.style.display='flex';
    document.getElementById('dh-adam').textContent=adam;
    deFrame.style.display='none';
    deMiss.style.display='flex'; deMiss.style.flexDirection='column';
    document.getElementById('dm-btn').href=REPO_ACTIONS;
    document.getElementById('dm-alt').href=KHMDHS_PDF+adam;
  }
});
document.getElementById('dh-close').addEventListener('click', ()=>{
  document.getElementById('detail-head').style.display='none';
  document.getElementById('detail-frame').style.display='none';
  document.getElementById('detail-missing').style.display='none';
  document.getElementById('detail-empty').style.display='flex';
  if(selRow){selRow.classList.remove('sel');selRow=null;}
});
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

// Hit-list export: ALL contracts across ALL contractors expiring in the next
// 90 days, regardless of what's in the search box. This is the "who's ripe
// to displace" list — one row per contract, sorted by soonest end date.
document.getElementById('dl90').addEventListener('click', ()=>{
  // Compute +90 day window (today inclusive → today+90 inclusive)
  const today = TODAY;
  const in90 = (()=>{ const d=new Date(); d.setDate(d.getDate()+90); return d.toISOString().slice(0,10); })();
  // Filter: end date exists, is today or later, and within window.
  // Apply the same dedup pass we use elsewhere so republications don't inflate.
  const all = dedupRepublications(ROWS.filter(r =>
    r.end && r.end >= today && r.end <= in90
  ));
  if(!all.length){
    alert('Καμία σύμβαση δεν λήγει στις επόμενες 90 ημέρες.');
    return;
  }
  // Soonest expiring at the top — that's the call order
  all.sort((a,b)=>(a.end||'').localeCompare(b.end||''));
  // Compute days-until-end for the sales team's convenience
  const daysUntil = (endStr)=>{
    const [y,m,d]=endStr.split('-').map(Number);
    const end=new Date(Date.UTC(y,m-1,d));
    const now=new Date(TODAY);
    return Math.round((end - now)/86400000);
  };
  const header = ['Λήγει σε (ημ.)','Λήγει','Ανάδοχος','Οργανισμός','Περιοχή','Υπηρεσία','Αξία (€)','Υπογραφή','ΑΔΑΜ','Σύμβαση'];
  const lines = [header.join(';')];
  all.forEach(r=>{
    lines.push([
      daysUntil(r.end),
      dmy(r.end),
      r.holder, r.org, r.region, r.service, r.value,
      dmy(r.signed), r.adam,
      r.adam ? 'https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/'+r.adam : ''
    ].map(csvField).join(';'));
  });
  const blob = new Blob(['\ufeff'+lines.join('\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  // filename includes today's date for versioning
  a.href = URL.createObjectURL(blob);
  a.download = 'hitlist_lixeis_90d_'+today+'.csv';
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
