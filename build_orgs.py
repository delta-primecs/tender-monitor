"""
ORGS — screener φορέων + φάκελος φορέα (Gödel-style "cover a new name in minutes").

Commands (in the command bar):
  ORGS [όρος]          screener: filter every φορέας by type, region, service status, value
  ORG  <φορέας>        DES  — the whole φορέας: call card, who signs, services has/lacks
  INC  <φορέας>        who holds each service (incumbents), since when, at what price
  NEXT <φορέας>        what they will tender next: expiries, expected window, estimated value
  ORG ωρωπου | εσωτερικος ελεγχος   → same, pre-filtered to one service

Reads data/contracts.jsonl only (no network) and writes docs/orgs.html.
Republications (superseded_by) are dropped; contracts whose title contradicts
the CPV (subject_check == "mismatch") are shown but NEVER counted as "has".

Run:  python build_orgs.py
"""

import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

STORE = "data/contracts.jsonl"
OUT = "docs/orgs.html"
SUBJ_MAX = 140

SERVICE_ORDER = [
    "Εσωτερικός έλεγχος", "Οικονομικός έλεγχος / Ορκωτοί", "DPO / Προστασία δεδομένων",
    "Διαχείριση κινδύνων", "Συμμόρφωση / Whistleblowing", "Χαρτογράφηση / Οργάνωση",
    "Κυβερνοασφάλεια", "Λογιστικές υπηρεσίες", "Φορολογικές υπηρεσίες", "Μισθοδοσία",
    "Επιχειρηματική / οικονομική συμβουλευτική",
]
SERVICE_ABBR = {
    "Εσωτερικός έλεγχος": "ΕΣΕ", "Οικονομικός έλεγχος / Ορκωτοί": "ΟΡΚ",
    "DPO / Προστασία δεδομένων": "DPO", "Διαχείριση κινδύνων": "ΚΙΝ",
    "Συμμόρφωση / Whistleblowing": "ΣΥΜ", "Χαρτογράφηση / Οργάνωση": "ΧΑΡ",
    "Κυβερνοασφάλεια": "CYB", "Λογιστικές υπηρεσίες": "ΛΟΓ",
    "Φορολογικές υπηρεσίες": "ΦΟΡ", "Μισθοδοσία": "ΜΙΣ",
    "Επιχειρηματική / οικονομική συμβουλευτική": "ΣΒΛ",
}

CHK = {"confirmed": 0, "unverified": 1, "mismatch": 2}


def org_type(name):
    n = (name or "").upper()
    if n.startswith("ΔΗΜΟΣ "):
        return "Δήμος"
    if "ΥΔΡΕΥΣΗΣ" in n or "Δ.Ε.Υ.Α" in n or n.startswith("ΔΕΥΑ"):
        return "ΔΕΥΑ"
    if n.startswith("ΠΕΡΙΦΕΡΕΙΑ") or "ΠΕΡΙΦΕΡΕΙΑΚ" in n:
        return "Περιφέρεια"
    if "ΔΗΜΟΤΙΚ" in n or "ΝΠΔΔ" in n or "Ν.Π.Δ.Δ" in n or "ΚΟΙΝΩΦΕΛ" in n:
        return "Νομικό πρόσωπο Δήμου"
    if "ΣΥΝΔΕΣΜΟΣ" in n or "ΦΟΡΕΑΣ ΔΙΑΧΕΙΡΙΣΗΣ" in n:
        return "Σύνδεσμος / ΦΟΔΣΑ"
    if "ΠΑΝΕΠΙΣΤΗΜ" in n or "ΠΟΛΥΤΕΧΝΕΙ" in n or "ΕΛΚΕ" in n or "ΕΙΔΙΚΟΣ ΛΟΓΑΡΙΑΣΜΟΣ" in n:
        return "Πανεπιστήμιο / ΕΛΚΕ"
    if "ΝΟΣΟΚΟΜΕΙ" in n or "ΥΓΕΙΟΝΟΜΙΚ" in n or "ΥΓΕΙΑΣ" in n:
        return "Υγεία"
    if n.startswith("ΥΠΟΥΡΓΕΙΟ") or "ΑΡΧΗ" in n:
        return "Υπουργείο / Αρχή"
    if " Α.Ε" in n or " ΑΕ" in n or "ΑΝΩΝΥΜ" in n:
        return "ΑΕ / Οργανισμός"
    return "Άλλο"


def main():
    if not os.path.exists(STORE):
        print(f"ERROR: {STORE} not found.")
        return

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
            if r.get("superseded_by"):
                continue  # republication — the newer record is kept
            if not r.get("orgkey") or not r.get("service"):
                continue
            rows.append(r)

    # dictionary-encode repeated strings to keep the page small
    svc_list = [s for s in SERVICE_ORDER if any(r["service"] == s for r in rows)]
    svc_list += sorted({r["service"] for r in rows} - set(svc_list))
    svc_idx = {s: i for i, s in enumerate(svc_list)}

    holders, holder_idx = [], {}
    signers, signer_idx = [], {}
    regions, region_idx = [], {}

    def enc(val, lst, idx):
        val = (val or "").strip()
        if val not in idx:
            idx[val] = len(lst)
            lst.append(val)
        return idx[val]

    org_names = defaultdict(Counter)
    org_regions = defaultdict(Counter)
    for r in rows:
        org_names[str(r["orgkey"])][r.get("org") or ""] += 1
        if r.get("region"):
            org_regions[str(r["orgkey"])][r["region"]] += 1

    org_keys = sorted(org_names)
    org_i = {k: i for i, k in enumerate(org_keys)}
    orgs = []
    for k in org_keys:
        name = org_names[k].most_common(1)[0][0]
        reg = org_regions[k].most_common(1)[0][0] if org_regions[k] else ""
        orgs.append({"k": k, "n": name, "t": org_type(name), "r": enc(reg, regions, region_idx)})

    contracts = []
    for r in rows:
        subj = (r.get("subject") or "").replace("\n", " ").strip()
        if len(subj) > SUBJ_MAX:
            subj = subj[:SUBJ_MAX - 1] + "…"
        contracts.append([
            org_i[str(r["orgkey"])],
            svc_idx[r["service"]],
            enc(r.get("holder"), holders, holder_idx),
            round(float(r.get("value") or 0), 2),
            r.get("signed") or "",
            r.get("end") or "",
            r.get("adam") or "",
            enc(r.get("signer"), signers, signer_idx),
            CHK.get(r.get("subject_check"), -1),
            1 if r.get("amendment") else 0,
            subj,
        ])

    data = {
        "svc": svc_list,
        "abbr": [SERVICE_ABBR.get(s, s[:3].upper()) for s in svc_list],
        "hold": holders, "sign": signers, "reg": regions,
        "orgs": orgs, "c": contracts,
    }
    stamp = datetime.now(ZoneInfo("Europe/Athens")).strftime("%d/%m/%Y %H:%M")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.replace("__DATA__", payload).replace("__STAMP__", stamp)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT}: {len(orgs)} φορείς, {len(contracts)} συμβάσεις, "
          f"{len(html) / 1e6:.1f} MB")


TEMPLATE = r"""<!doctype html>
<html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ORGS · DeltaPrime</title>
<link rel="stylesheet" href="godel.css">
<style>
  .wrap{max-width:none}
  /* ── screener filter panel (Gödel equity-screener look) ── */
  .fpanel{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:12px 16px}
  .fhead{display:flex;align-items:center;gap:12px;margin-bottom:10px}
  .flabel{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
  .fadd{min-width:220px}
  .frow{display:grid;grid-template-columns:210px 34px minmax(220px,1fr) 22px;gap:8px;
        align-items:center;margin:6px 0;max-width:900px}
  .frow.range{grid-template-columns:210px 34px minmax(100px,1fr) 14px minmax(100px,1fr) 22px}
  .frow .fn{color:var(--text);font-size:13px}
  .frow .op{display:flex;align-items:center;justify-content:center;height:32px;
        border:1px solid var(--hair2);background:var(--page);color:var(--muted);font-weight:700}
  .frow input,.frow select{height:32px;padding:0 10px;font-size:13px;width:100%;
        border:1px solid var(--hair2);outline:none;box-sizing:border-box}
  .frow input:focus,.frow select:focus{border-color:var(--accent)!important}
  .frow .dash{color:var(--muted);text-align:center}
  .frow .x{color:var(--muted);cursor:pointer;text-align:center;font-size:15px;
        background:none!important;border:0!important;padding:0}
  .frow .x:hover{color:var(--red)}
  .svcpair{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  .hint{color:var(--muted);font-size:11px;padding:8px 16px}
  /* ── results table ── */
  .res{background:var(--card);border:1px solid var(--hair);border-top:0}
  table.grid{width:100%;border-collapse:collapse;font-size:13px}
  table.grid th{text-align:left;padding:9px 12px;cursor:pointer;user-select:none;white-space:nowrap;
        position:sticky;top:0;z-index:1}
  table.grid th.num,table.grid td.num{text-align:right}
  table.grid td{padding:9px 12px;border-bottom:1px solid var(--hair);vertical-align:top}
  table.grid tr.sel td{background:var(--accent-dim)!important}
  table.grid tbody tr{cursor:pointer}
  .oname{color:var(--bright);font-weight:600}
  .otype{color:var(--muted);font-size:11px;margin-top:2px}
  .cov{display:flex;gap:3px;flex-wrap:nowrap}
  .dot{font-size:10px;font-weight:700;padding:2px 5px;border-radius:3px;border:1px solid var(--hair2);
       color:var(--muted);opacity:.45;letter-spacing:.02em}
  .dot.on{opacity:1;color:var(--green);background:var(--green-bg);border-color:transparent}
  .dot.soon{opacity:1;color:var(--amber);background:var(--amber-bg);border-color:transparent}
  .dot.old{opacity:.9;color:var(--text);background:var(--panel-2);border-color:transparent}
  .nx{white-space:nowrap}
  .nx .d{color:var(--bright)} .nx .s{color:var(--muted);font-size:11px}
  .nx.hot .d{color:var(--amber)}
  .more{display:block;width:100%;padding:11px;cursor:pointer;font-weight:700;letter-spacing:.05em}
  /* ── dossier ── */
  .dos-head{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:16px 18px}
  .back{color:var(--link);cursor:pointer;font-size:12px;text-decoration:none}
  .dos-title{font-size:22px;font-weight:700;color:var(--bright);margin:8px 0 4px;line-height:1.3}
  .dos-meta{color:var(--muted);font-size:12.5px;display:flex;gap:14px;flex-wrap:wrap}
  .dos-meta b{color:var(--text);font-weight:600}
  .callwho{margin-top:10px;font-size:13.5px;color:var(--text)}
  .callwho b{color:var(--bright)}
  .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  .acts a{font-size:11.5px;text-decoration:none;border:1px solid var(--hair2);padding:5px 10px;
       color:var(--link);background:var(--page)}
  .acts a:hover{border-color:var(--link)}
  .vtabs{display:flex;gap:0;border:1px solid var(--hair);border-top:0;background:var(--panel)}
  .vtabs button{border:0!important;border-right:1px solid var(--hair)!important;padding:9px 16px;
       cursor:pointer;font-size:12px;font-weight:700;letter-spacing:.05em;background:transparent!important}
  .vtabs button .k{display:inline-block;border:1px solid var(--hair2);font-size:10px;padding:0 4px;
       margin-right:7px;border-radius:3px;color:var(--muted)}
  .vtabs button.on{color:var(--accent)!important;background:var(--accent-dim)!important}
  .vtabs .svcsel{margin-left:auto;display:flex;align-items:center;gap:8px;padding:0 12px;font-size:11px;color:var(--muted)}
  .vtabs .svcsel select{height:28px;font-size:12px}
  .sec{background:var(--card);border:1px solid var(--hair);border-top:0}
  .sech{padding:10px 16px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
       color:var(--accent);font-weight:700;border-bottom:1px solid var(--hair);background:var(--panel)}
  .pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;white-space:nowrap}
  .p-on{color:var(--green)!important;background:var(--green-bg)!important}
  .p-soon{color:var(--amber)!important;background:var(--amber-bg)!important}
  .p-old{color:var(--text)!important;background:var(--panel-2)!important}
  .p-none{color:var(--red)!important;background:var(--red-bg)!important}
  .p-warn{color:var(--amber)!important;background:var(--amber-bg)!important}
  .opp{font-size:10px;font-weight:700;letter-spacing:.06em;color:var(--accent);border:1px solid var(--accent);
       padding:1px 6px;border-radius:3px;margin-left:6px;white-space:nowrap}
  .sub2{color:var(--muted);font-size:11.5px}
  .subject-line{color:var(--text);font-size:12px;margin-top:2px}
  .foot-note{color:var(--muted);font-size:11.5px;padding:10px 16px;border-top:1px solid var(--hair);line-height:1.6}
  .rel{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px}
  .rel a{font-size:12px;color:var(--link);text-decoration:none;border:1px solid var(--hair2);padding:4px 9px}
  .est{color:var(--muted);font-size:10.5px;margin-left:4px}
  .empty{color:var(--muted);text-align:center;padding:36px 16px;font-size:13px}
  a.ext{color:var(--link);text-decoration:none;white-space:nowrap}
  @media(max-width:860px){.frow,.frow.range{grid-template-columns:1fr;max-width:none}.frow .op,.frow .dash{display:none}}
</style></head><body>
<div id="nav"></div>
<div class="wrap">
  <div class="deskbar">
    <span class="db-title" id="dbt">ORGS</span>
    <span class="db-sub" id="dbs">SCREENER ΦΟΡΕΩΝ · ΚΗΜΔΗΣ</span>
    <div class="db-stats" id="stats"></div>
    <span class="db-stamp">__STAMP__</span>
  </div>

  <!-- ── SCREENER ── -->
  <div id="screener">
    <div class="fpanel">
      <div class="fhead">
        <span class="flabel">Φίλτρα:</span>
        <select class="fadd" id="fadd">
          <option value="">+ Add filter</option>
          <option value="name">Φορέας (όνομα)</option>
          <option value="type">Τύπος φορέα</option>
          <option value="region">Περιφέρεια</option>
          <option value="svc">Υπηρεσία (κατάσταση)</option>
          <option value="value">Συνολική αξία συμβάσεων (€)</option>
          <option value="count">Πλήθος συμβάσεων</option>
        </select>
        <span class="flabel" style="margin-left:auto">↑↓ επιλογή · Enter άνοιγμα</span>
      </div>
      <div id="frows"></div>
    </div>
    <div class="res">
      <table class="grid" id="tbl">
        <thead><tr>
          <th data-sort="name">Φορέας</th>
          <th data-sort="region">Περιφέρεια</th>
          <th data-sort="count" class="num">Συμβ.</th>
          <th data-sort="value" class="num">Αξία €</th>
          <th>Κάλυψη υπηρεσιών</th>
          <th data-sort="next">Επόμενη λήξη</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
      <div id="moreWrap"></div>
    </div>
    <div class="hint">Κάλυψη: <span class="dot on">ΧΧΧ</span> ενεργή ·
      <span class="dot soon">ΧΧΧ</span> λήγει ≤ 180 ημ. ·
      <span class="dot old">ΧΧΧ</span> είχε, έληξε · <span class="dot">ΧΧΧ</span> δεν βρέθηκε σύμβαση.
      Πηγή: ΚΗΜΔΗΣ (κυρίως από 2023). Τίτλοι που αντιφάσκουν με το CPV δεν μετράνε.</div>
  </div>

  <!-- ── DOSSIER (DES / INC / NEXT / HIST) ── -->
  <div id="dossier" style="display:none">
    <div class="dos-head" id="dhead"></div>
    <div class="vtabs" id="vtabs">
      <button data-v="des"><span class="k">D</span>DES · Φάκελος</button>
      <button data-v="inc"><span class="k">I</span>INC · Ποιος τον κρατά</button>
      <button data-v="next"><span class="k">N</span>NEXT · Τι έρχεται</button>
      <button data-v="hist"><span class="k">H</span>Ιστορικό</button>
      <span class="svcsel">Υπηρεσία
        <select id="svcsel"><option value="">— όλες —</option></select></span>
    </div>
    <div id="dbody"></div>
  </div>
</div>
<script src="nav.js"></script>
<script>
const D = __DATA__;
const TODAY = new Date(); TODAY.setHours(0,0,0,0);
const DAY = 86400000;
const KHMDHS = "https://cerpp.eprocurement.gov.gr/khmdhs-opendata/contract/attachment/";
const SOON = 180;           // "expiring soon" window for coverage dots
const NONCORE = ["Φορολογικές υπηρεσίες","Μισθοδοσία","Επιχειρηματική / οικονομική συμβουλευτική"];
const CORE = D.svc.map((s,i)=>i).filter(i=>!NONCORE.includes(D.svc[i]));

const esc = s => String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtEur = v => v ? Math.round(v).toLocaleString("el-GR") : "—";
const fmtD = s => s ? s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4) : "—";
const dnum = s => s ? new Date(s+"T00:00:00").getTime() : null;
const daysTo = s => s ? Math.round((dnum(s)-TODAY.getTime())/DAY) : null;
const norm = s => (s||"").toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g,"");
const median = a => { if(!a.length) return null; const b=[...a].sort((x,y)=>x-y); const m=b.length>>1; return b.length%2?b[m]:(b[m-1]+b[m])/2; };

// ── per-org model ──────────────────────────────────────────────────────────
const C = D.c.map(r=>({o:r[0],s:r[1],h:r[2],v:r[3],sg:r[4],e:r[5],a:r[6],si:r[7],chk:r[8],am:r[9],subj:r[10]}));
const ORGS = D.orgs.map((o,i)=>({i, k:o.k, name:o.n, type:o.t, region:D.reg[o.r]||"", n:norm(o.n), cs:[]}));
C.forEach(c=>ORGS[c.o].cs.push(c));

function svcStatus(cs){
  // cs = contracts of ONE service for ONE org. Mismatch-titled ones never count.
  const ok = cs.filter(c=>c.chk!==2);
  if(!ok.length) return cs.length ? {st:"warn"} : {st:"none"};
  const ends = ok.map(c=>c.e).filter(Boolean).sort();
  const maxEnd = ends.length ? ends[ends.length-1] : null;
  const latest = [...ok].sort((a,b)=>(b.e||b.sg).localeCompare(a.e||a.sg))[0];
  if(maxEnd && daysTo(maxEnd) >= 0){
    const d = daysTo(maxEnd);
    return {st: d<=SOON ? "soon":"on", end:maxEnd, days:d, cur:latest};
  }
  return {st:"old", end:maxEnd, days:maxEnd?daysTo(maxEnd):null, cur:latest};
}

ORGS.forEach(o=>{
  o.count = o.cs.length;
  o.value = o.cs.reduce((t,c)=>t+(c.v||0),0);
  o.bySvc = {};
  D.svc.forEach((s,si)=>{
    const cs = o.cs.filter(c=>c.s===si);
    o.bySvc[si] = svcStatus(cs);
  });
  // next upcoming expiry (future), any service
  let nx=null;
  o.cs.forEach(c=>{ if(c.chk!==2 && c.e && daysTo(c.e)>=0 && (!nx || c.e<nx.e)) nx=c; });
  o.next = nx;
  const last = [...o.cs].sort((a,b)=>b.sg.localeCompare(a.sg))[0];
  o.signer = last ? D.sign[last.si] : "";
  o.signerDate = last ? last.sg : "";
  o.first = o.cs.map(c=>c.sg).filter(Boolean).sort()[0]||"";
});

// related φορείς: a Δήμος ↔ its legal entities (name tokens of the Δήμος)
function dimosTokens(o){ return o.n.replace(/^ΔΗΜΟΣ\s+/,"").split(/\s+/).filter(t=>t.length>=3); }
const DIMOI = ORGS.filter(o=>o.type==="Δήμος").map(o=>({o, t:dimosTokens(o)})).filter(x=>x.t.length);
function related(o){
  if(o.type==="Δήμος"){
    const t = dimosTokens(o);
    return ORGS.filter(x=>x!==o && t.length && t.every(w=>x.n.includes(w))).slice(0,12);
  }
  return DIMOI.filter(d=>d.t.every(w=>o.n.includes(w))).map(d=>d.o).slice(0,4);
}

// ── SCREENER ───────────────────────────────────────────────────────────────
const SVC_STATES = [["has","Έχει ενεργή"],["lacks","Λείπει (καμία σύμβαση)"],["noactive","Χωρίς ενεργή (λείπει ή έληξε)"],
                    ["soon90","Λήγει ≤ 90 ημ."],["soon180","Λήγει ≤ 180 ημ."],["expired12","Έληξε τους τελευταίους 12 μήνες"]];
const TYPES = [...new Set(ORGS.map(o=>o.type))].sort();
const REGIONS = [...new Set(ORGS.map(o=>o.region).filter(Boolean))].sort();
let filters = [];        // {kind, ...}
let sortKey = "value", sortDir = -1, shown = 60, selRow = 0, curList = [];

function addFilter(kind, init){
  const f = Object.assign({kind, id:Math.random().toString(36).slice(2)}, init||{});
  if(kind==="svc" && f.svc==null){ f.svc = 0; f.state = f.state||"noactive"; }
  filters.push(f); renderFilters(); applyFilters();
}
function renderFilters(){
  const box = document.getElementById("frows");
  box.innerHTML = filters.map(f=>{
    const x = `<button class="x" data-x="${f.id}" title="Αφαίρεση">×</button>`;
    if(f.kind==="name") return `<div class="frow"><span class="fn">Φορέας</span><span class="op">~</span>
      <input data-f="${f.id}" data-k="q" value="${esc(f.q||"")}" placeholder="π.χ. ωρωπου, νάουσα, ΔΕΥΑ…">${x}</div>`;
    if(f.kind==="type") return `<div class="frow"><span class="fn">Τύπος φορέα</span><span class="op">=</span>
      <select data-f="${f.id}" data-k="v"><option value="">— όλοι —</option>${TYPES.map(t=>`<option ${f.v===t?"selected":""}>${esc(t)}</option>`).join("")}</select>${x}</div>`;
    if(f.kind==="region") return `<div class="frow"><span class="fn">Περιφέρεια</span><span class="op">=</span>
      <select data-f="${f.id}" data-k="v"><option value="">— όλες —</option>${REGIONS.map(t=>`<option ${f.v===t?"selected":""}>${esc(t)}</option>`).join("")}</select>${x}</div>`;
    if(f.kind==="svc") return `<div class="frow"><span class="fn">Υπηρεσία</span><span class="op">=</span>
      <div class="svcpair"><select data-f="${f.id}" data-k="svc">${D.svc.map((s,i)=>`<option value="${i}" ${+f.svc===i?"selected":""}>${esc(s)}</option>`).join("")}</select>
      <select data-f="${f.id}" data-k="state">${SVC_STATES.map(([k,l])=>`<option value="${k}" ${f.state===k?"selected":""}>${l}</option>`).join("")}</select></div>${x}</div>`;
    if(f.kind==="value"||f.kind==="count"){
      const lbl = f.kind==="value"?"Συνολική αξία (€)":"Πλήθος συμβάσεων";
      return `<div class="frow range"><span class="fn">${lbl}</span><span class="op">≶</span>
      <input data-f="${f.id}" data-k="min" value="${esc(f.min||"")}" placeholder="min" inputmode="numeric">
      <span class="dash">–</span>
      <input data-f="${f.id}" data-k="max" value="${esc(f.max||"")}" placeholder="max" inputmode="numeric">${x}</div>`;
    }
    return "";
  }).join("");
  box.querySelectorAll("[data-f]").forEach(el=>{
    const ev = el.tagName==="SELECT" ? "change" : "input";
    el.addEventListener(ev,()=>{ const f=filters.find(z=>z.id===el.dataset.f); f[el.dataset.k]=el.value; shown=60; applyFilters(); });
  });
  box.querySelectorAll("[data-x]").forEach(b=>b.addEventListener("click",()=>{
    filters = filters.filter(z=>z.id!==b.dataset.x); renderFilters(); applyFilters(); }));
}
const num = s => { const t=String(s||"").toUpperCase().replace(/\s/g,"").replace(/\./g,"").replace(",",".");
  if(!t) return null; const m=t.match(/^([\d.]+)([KΚMΜ]?)$/); if(!m) return null;
  return parseFloat(m[1])*(/[KΚ]/.test(m[2])?1e3:/[MΜ]/.test(m[2])?1e6:1); };

function passes(o){
  for(const f of filters){
    if(f.kind==="name" && f.q){ const ws=norm(f.q).split(/\s+/).filter(Boolean); if(!ws.every(w=>o.n.includes(w))) return false; }
    if(f.kind==="type" && f.v && o.type!==f.v) return false;
    if(f.kind==="region" && f.v && o.region!==f.v) return false;
    if(f.kind==="svc"){
      const s = o.bySvc[+f.svc];
      const st = f.state;
      if(st==="has" && !(s.st==="on"||s.st==="soon")) return false;
      if(st==="lacks" && !(s.st==="none"||s.st==="warn")) return false;
      if(st==="noactive" && (s.st==="on"||s.st==="soon")) return false;
      if(st==="soon90" && !(s.st==="soon" && s.days<=90)) return false;
      if(st==="soon180" && s.st!=="soon") return false;
      if(st==="expired12" && !(s.st==="old" && s.days!=null && s.days>=-365)) return false;
    }
    if(f.kind==="value"){ const a=num(f.min), b=num(f.max); if(a!=null&&o.value<a) return false; if(b!=null&&o.value>b) return false; }
    if(f.kind==="count"){ const a=num(f.min), b=num(f.max); if(a!=null&&o.count<a) return false; if(b!=null&&o.count>b) return false; }
  }
  return true;
}
function sortVal(o,k){
  if(k==="name") return o.name; if(k==="region") return o.region;
  if(k==="count") return o.count; if(k==="value") return o.value;
  if(k==="next") return o.next ? o.next.e : "9999";
  return 0;
}
function applyFilters(){
  curList = ORGS.filter(passes);
  curList.sort((a,b)=>{ const x=sortVal(a,sortKey), y=sortVal(b,sortKey);
    return (typeof x==="string" ? x.localeCompare(y,"el") : x-y) * sortDir; });
  selRow = 0; renderTable();
}
function covHtml(o){
  return CORE.map(si=>{ const s=o.bySvc[si]; const cls = s.st==="on"?"on":s.st==="soon"?"soon":s.st==="old"?"old":"";
    const tip = D.svc[si]+": "+({on:"ενεργή έως "+fmtD(s.end),soon:"λήγει σε "+s.days+" ημ.",old:"είχε — έληξε "+fmtD(s.end),none:"δεν βρέθηκε σύμβαση",warn:"μόνο με αντιφατικό τίτλο"}[s.st]);
    return `<span class="dot ${cls}" title="${esc(tip)}">${D.abbr[si]}</span>`; }).join("");
}
function renderTable(){
  const tb = document.getElementById("tbody");
  const rows = curList.slice(0, shown);
  tb.innerHTML = rows.map((o,i)=>{
    const nx = o.next ? `<div class="nx ${daysTo(o.next.e)<=90?"hot":""}"><span class="d">${fmtD(o.next.e)}</span>
      <div class="s">${esc(D.abbr[o.next.s])} · σε ${daysTo(o.next.e)} ημ.</div></div>` : `<span class="sub2">—</span>`;
    return `<tr data-i="${o.i}" class="${i===selRow?"sel":""}">
      <td><div class="oname">${esc(o.name)}</div><div class="otype">${esc(o.type)}</div></td>
      <td>${esc(o.region)}</td><td class="num">${o.count}</td><td class="num">${fmtEur(o.value)}</td>
      <td><div class="cov">${covHtml(o)}</div></td><td>${nx}</td></tr>`;
  }).join("") || `<tr><td colspan="6" class="empty">Κανένας φορέας με αυτά τα φίλτρα.</td></tr>`;
  tb.querySelectorAll("tr[data-i]").forEach(tr=>tr.addEventListener("click",()=>openOrg(+tr.dataset.i,"des")));
  const mw = document.getElementById("moreWrap");
  mw.innerHTML = curList.length>shown ? `<button class="more" id="moreBtn">Περισσότεροι (${curList.length-shown})</button>` : "";
  if(curList.length>shown) document.getElementById("moreBtn").onclick=()=>{ shown+=100; renderTable(); };
  document.getElementById("stats").innerHTML = `<span><b>${curList.length}</b> φορείς</span><span><b>${fmtEur(curList.reduce((t,o)=>t+o.value,0))}</b> €</span>`;
  document.querySelectorAll("#tbl th").forEach(th=>{ th.textContent = th.textContent.replace(/ [▲▼]$/,"");
    if(th.dataset.sort===sortKey) th.textContent += sortDir<0?" ▼":" ▲"; });
}
document.querySelectorAll("#tbl th[data-sort]").forEach(th=>th.addEventListener("click",()=>{
  const k=th.dataset.sort; if(sortKey===k) sortDir*=-1; else { sortKey=k; sortDir=(k==="name"||k==="region"||k==="next")?1:-1; }
  applyFilters(); }));
document.getElementById("fadd").addEventListener("change",e=>{ if(e.target.value) addFilter(e.target.value); e.target.value=""; });

// ── DOSSIER ────────────────────────────────────────────────────────────────
let cur = null, view = "des", svcFilter = "";
D.svc.forEach((s,i)=>{ const o=document.createElement("option"); o.value=i; o.textContent=s; document.getElementById("svcsel").appendChild(o); });
document.getElementById("svcsel").addEventListener("change",e=>{ svcFilter=e.target.value; renderView(); pushUrl(); });
document.querySelectorAll("#vtabs button").forEach(b=>b.addEventListener("click",()=>{ view=b.dataset.v; renderView(); pushUrl(); }));

function openOrg(i, v, svc){
  cur = ORGS[i]; view = v||"des"; svcFilter = (svc!=null && svc!=="") ? String(svc) : "";
  document.getElementById("screener").style.display="none";
  document.getElementById("dossier").style.display="";
  document.getElementById("svcsel").value = svcFilter;
  renderHead(); renderView(); pushUrl(); window.scrollTo(0,0);
}
function closeOrg(){
  cur=null; document.getElementById("dossier").style.display="none";
  document.getElementById("screener").style.display="";
  document.getElementById("dbt").textContent="ORGS"; document.getElementById("dbs").textContent="SCREENER ΦΟΡΕΩΝ · ΚΗΜΔΗΣ";
  renderTable(); pushUrl();
}
function pushUrl(){
  const p = new URLSearchParams();
  if(cur){ p.set("org",cur.k); if(view!=="des") p.set("view",view); if(svcFilter!=="") p.set("svc",svcFilter); }
  history.replaceState(null,"",location.pathname+(p.toString()?"?"+p:""));
}
function diavLink(uid){ return "https://diavgeia.gov.gr/search?query="+encodeURIComponent('organizationUid:"'+uid+'"')+"&sort=recent&page=0"; }
function finLink(uid){ const enc=s=>encodeURIComponent(s).replace(/%3A/g,":");
  return "https://diavgeia.gov.gr/search?query="+enc('decisionType:"ΙΣΟΛΟΓΙΣΜΟΣ – ΑΠΟΛΟΓΙΣΜΟΣ"')+"&page=0&fq="+enc('organizationUid:"'+uid+'"')+"&advanced&sort=recent"; }

function renderHead(){
  const o = cur;
  document.getElementById("dbt").textContent = view.toUpperCase()==="HIST" ? "HIST" : view.toUpperCase();
  document.getElementById("dbs").textContent = o.name;
  const has = CORE.filter(si=>["on","soon"].includes(o.bySvc[si].st)).length;
  document.getElementById("stats").innerHTML = `<span><b>${o.count}</b> συμβ.</span><span><b>${fmtEur(o.value)}</b> €</span><span><b>${has}/${CORE.length}</b> υπηρεσίες ενεργές</span>`;
  const rel = related(o);
  document.getElementById("dhead").innerHTML = `
    <a class="back" id="backBtn">← ORGS · όλοι οι φορείς</a>
    <div class="dos-title">${esc(o.name)}</div>
    <div class="dos-meta"><span>${esc(o.type)}</span><span>${esc(o.region)}</span>
      <span>Κωδ. φορέα <b>${esc(o.k)}</b></span><span>Συμβάσεις από <b>${fmtD(o.first)}</b></span></div>
    ${o.signer?`<div class="callwho">☎ Υπογράφει: <b>${esc(o.signer)}</b> <span class="sub2">(τελευταία υπογραφή ${fmtD(o.signerDate)})</span></div>`:""}
    <div class="acts">
      <a href="${diavLink(o.k)}" target="_blank" rel="noopener">Όλες οι αποφάσεις στη Διαύγεια ↗</a>
      <a href="${finLink(o.k)}" target="_blank" rel="noopener">Ισολογισμοί – Απολογισμοί ↗</a>
      <a href="diavgeia.html?q=${encodeURIComponent(o.name)}" target="_blank" rel="noopener">DIAV · θέμα + φορέας</a>
      <a href="accounts.html?q=${encodeURIComponent(o.name)}">Account Map</a>
    </div>
    ${rel.length?`<div class="dos-meta" style="margin-top:12px"><span>Σχετικοί φορείς:</span></div>
      <div class="rel" style="padding:6px 0 0">${rel.map(r=>`<a href="?org=${encodeURIComponent(r.k)}" data-rel="${r.i}">${esc(r.name)}</a>`).join("")}</div>`:""}`;
  document.getElementById("backBtn").onclick = closeOrg;
  document.querySelectorAll("[data-rel]").forEach(a=>a.addEventListener("click",e=>{ e.preventDefault(); openOrg(+a.dataset.rel, view, svcFilter); }));
}
function renderView(){
  document.querySelectorAll("#vtabs button").forEach(b=>b.classList.toggle("on", b.dataset.v===view));
  document.getElementById("dbt").textContent = view==="hist" ? "HIST" : view.toUpperCase();
  const fn = {des:viewDes, inc:viewInc, next:viewNext, hist:viewHist}[view] || viewDes;
  document.getElementById("dbody").innerHTML = fn(cur);
}
const svcList = () => svcFilter==="" ? D.svc.map((s,i)=>i) : [+svcFilter];

function statusPill(s){
  if(s.st==="on")   return `<span class="pill p-on">Ενεργή έως ${fmtD(s.end)}</span>`;
  if(s.st==="soon") return `<span class="pill p-soon">Λήγει σε ${s.days} ημ. (${fmtD(s.end)})</span>`;
  if(s.st==="old")  return s.end ? `<span class="pill p-old">Έληξε ${fmtD(s.end)}</span>`
                          : `<span class="pill p-old">Υπογράφηκε ${fmtD(s.cur&&s.cur.sg)} · χωρίς ημ. λήξης</span>`;
  if(s.st==="warn") return `<span class="pill p-warn" title="Υπάρχει σύμβαση με αυτό το CPV αλλά ο τίτλος της δείχνει άλλη υπηρεσία">⚠ Μόνο με αντιφατικό τίτλο</span>`;
  return `<span class="pill p-none">Δεν βρέθηκε σύμβαση</span>`;
}
function isOpp(s,si){ if(!CORE.includes(si)) return false;
  if(s.st==="old" && !s.end) return false;   // undated (e.g. one-off annual audit) — not a clear signal
  return s.st==="none"||s.st==="warn"||s.st==="old"||(s.st==="soon"&&s.days<=SOON); }

function viewDes(o){
  const rows = svcList().map(si=>{
    const s=o.bySvc[si], c=s.cur;
    return `<tr><td><b style="color:var(--bright)">${esc(D.svc[si])}</b>${isOpp(s,si)?'<span class="opp">ΕΥΚΑΙΡΙΑ</span>':""}</td>
      <td>${statusPill(s)}</td>
      <td>${c?`<a class="ext" href="contractors.html?q=${encodeURIComponent(D.hold[c.h])}">${esc(D.hold[c.h])}</a>${c.chk===1?' <span class="sub2" title="Ο τίτλος δεν επιβεβαιώνει ρητά την υπηρεσία">· προς επιβεβαίωση</span>':""}`:'<span class="sub2">—</span>'}</td>
      <td class="num">${c?fmtEur(c.v):"—"}</td>
      <td>${c&&c.a?`<a class="ext" target="_blank" rel="noopener" href="${KHMDHS+c.a}">σύμβαση ↗</a>`:""}</td></tr>`;
  }).join("");
  const nx = nextItems(o).filter(x=>x.kind!=="new").slice(0,3);
  return `<div class="sec"><div class="sech">Κάρτα κλήσης · τι έχει, τι του λείπει</div>
    <table class="grid"><thead><tr><th>Υπηρεσία</th><th>Κατάσταση</th><th>Τρέχων / τελευταίος ανάδοχος</th><th class="num">Αξία €</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table>
    <div class="foot-note">«Δεν βρέθηκε σύμβαση» = καμία σύμβαση στο ΚΗΜΔΗΣ για την υπηρεσία από το 2023 (ή καμία που ο τίτλος της να το επιβεβαιώνει).
      Δεν σημαίνει με βεβαιότητα ότι ο φορέας δεν έχει την υπηρεσία — επιβεβαίωσε πριν το πεις στο τηλέφωνο.</div></div>
    ${nx.length?`<div class="sec"><div class="sech">Επόμενες ευκαιρίες (NEXT)</div>${nextTable(nx)}</div>`:""}`;
}

function viewInc(o){
  const blocks = svcList().map(si=>{
    const cs = o.cs.filter(c=>c.s===si); if(!cs.length) return "";
    // ΚΗΜΔΗΣ spells the same firm differently ("ΑΝΑΒΑΘΜΙΣΗ", "…ΛΥΣΕΙΣ Α.Ε.") → group by a
    // normalized name, merging a name into a longer one that starts with it.
    const keyOf = h => norm(D.hold[h]).replace(/[«»"'.,()\-–_]/g," ")
      .replace(/\b(ΑΝΩΝΥΜΗ ΕΤΑΙΡΕΙΑ|ΜΟΝΟΠΡΟΣΩΠΗ|ΑΕ|ΙΚΕ|ΕΠΕ|ΟΕ|ΕΕ|Α Ε|Ι Κ Ε|Ε Π Ε|Ο Ε|Ε Ε)\b/g," ")
      .replace(/\s+/g," ").trim();
    const keys = [...new Set(cs.map(c=>keyOf(c.h)))].sort((a,b)=>b.length-a.length);
    const canon = {};
    keys.forEach(k=>{ canon[k] = keys.find(L=>L.length>k.length && (L+" ").startsWith(k+" ")) || k; });
    Object.keys(canon).forEach(k=>{ let c=canon[k]; while(canon[c]!==c) c=canon[c]; canon[k]=c; });
    const by = {}, label = {};
    cs.forEach(c=>{ const k=canon[keyOf(c.h)]; (by[k]=by[k]||[]).push(c);
      const nm=D.hold[c.h]; if(!label[k]||nm.length>label[k].length) label[k]=nm; });
    const rows = Object.entries(by).map(([k,arr])=>{
      const sg = arr.map(c=>c.sg).filter(Boolean).sort(), en = arr.map(c=>c.e).filter(Boolean).sort();
      const active = arr.some(c=>c.chk!==2 && c.e && daysTo(c.e)>=0);
      const warn = arr.every(c=>c.chk===2);
      return {h:label[k], n:arr.length, v:arr.reduce((t,c)=>t+c.v,0), from:sg[0], to:en[en.length-1]||sg[sg.length-1], active, warn,
              med:median(arr.map(c=>c.v).filter(Boolean))};
    }).sort((a,b)=>(b.active-a.active)||(b.to||"").localeCompare(a.to||""));
    return `<div class="sec"><div class="sech">${esc(D.svc[si])}</div><table class="grid">
      <thead><tr><th>Ανάδοχος</th><th class="num">Συμβ.</th><th class="num">Σύνολο €</th><th class="num">Τυπικό ποσό €</th><th>Περίοδος</th><th></th></tr></thead><tbody>
      ${rows.map(r=>`<tr><td><a class="ext" href="contractors.html?q=${encodeURIComponent(r.h)}">${esc(r.h)}</a>
        ${r.active?'<span class="pill p-on" style="margin-left:6px">ΕΝΕΡΓΟΣ</span>':""}${r.warn?'<span class="pill p-warn" style="margin-left:6px">⚠ τίτλος αντίθετος</span>':""}</td>
        <td class="num">${r.n}</td><td class="num">${fmtEur(r.v)}</td><td class="num">${fmtEur(r.med)}</td>
        <td>${fmtD(r.from)} → ${fmtD(r.to)}</td><td></td></tr>`).join("")}</tbody></table></div>`;
  }).join("");
  return blocks || `<div class="sec"><div class="empty">Καμία σύμβαση για ${svcFilter===""?"αυτόν τον φορέα":"αυτή την υπηρεσία"}.</div></div>`;
}

function nextItems(o){
  const out=[];
  svcList().forEach(si=>{
    const s=o.bySvc[si];
    const cs=o.cs.filter(c=>c.s===si && c.chk!==2);
    const vals=cs.map(c=>c.v).filter(Boolean);
    const durs=cs.filter(c=>c.sg&&c.e).map(c=>(dnum(c.e)-dnum(c.sg))/DAY/30.4).filter(m=>m>0&&m<120);
    const base={si, est:median(vals), dur:median(durs), cur:s.cur};
    if(s.st==="on"||s.st==="soon"){
      const from=new Date(dnum(s.end)-90*DAY), to=new Date(dnum(s.end)-30*DAY);
      const inWin = TODAY>=from && TODAY<=new Date(dnum(s.end));
      out.push({...base, kind:"renew", end:s.end, days:s.days, from, to, inWin});
    } else if(s.st==="old" && s.days!=null && s.days>=-365){
      out.push({...base, kind:"lapsed", end:s.end, days:s.days});
    } else if((s.st==="none"||s.st==="warn") && CORE.includes(si)){
      out.push({...base, kind:"new"});
    }
  });
  const rank={lapsed:0,renew:1,new:2};
  return out.sort((a,b)=> (rank[a.kind]-rank[b.kind]) || ((a.days??9e9)-(b.days??9e9)));
}
const dstr = d => d.toLocaleDateString("el-GR",{day:"2-digit",month:"2-digit",year:"numeric"});
function nextTable(items){
  return `<table class="grid"><thead><tr><th>Υπηρεσία</th><th>Τι αναμένεται</th><th>Τρέχων ανάδοχος</th>
    <th class="num">Εκτίμηση ποσού €</th><th class="num">Συνήθης διάρκεια</th></tr></thead><tbody>
    ${items.map(x=>{
      let what;
      if(x.kind==="renew") what = x.inWin
        ? `<span class="pill p-soon">ΤΩΡΑ · λήγει σε ${x.days} ημ.</span><div class="sub2" style="margin-top:4px">νέα διαδικασία αναμένεται ${dstr(x.from)} – ${dstr(x.to)}</div>`
        : `<span class="pill p-on">Λήγει ${fmtD(x.end)} (σε ${x.days} ημ.)</span><div class="sub2" style="margin-top:4px">παράθυρο διαδικασίας ~ ${dstr(x.from)} – ${dstr(x.to)}</div>`;
      else if(x.kind==="lapsed") what = `<span class="pill p-none">Έληξε πριν ${-x.days} ημ.</span><div class="sub2" style="margin-top:4px">πιθανή ανάθεση τώρα ή παράταση</div>`;
      else what = `<span class="pill p-old">Δεν έχει · νέα πώληση</span>`;
      return `<tr><td><b style="color:var(--bright)">${esc(D.svc[x.si])}</b></td><td>${what}</td>
        <td>${x.cur?esc(D.hold[x.cur.h]):'<span class="sub2">—</span>'}</td>
        <td class="num">${x.est?fmtEur(x.est)+'<span class="est">εκτ.</span>':"—"}</td>
        <td class="num">${x.dur?Math.round(x.dur)+" μήνες":"—"}</td></tr>`;
    }).join("")}</tbody></table>`;
}
function viewNext(o){
  const it = nextItems(o);
  return `<div class="sec"><div class="sech">NEXT · τι θα προκηρύξει μετά</div>
    ${it.length?nextTable(it):'<div class="empty">Τίποτα σε ορίζοντα για αυτή την επιλογή.</div>'}
    <div class="foot-note">Εκτίμηση ποσού = διάμεσος των προηγούμενων συμβάσεων του φορέα για την υπηρεσία.
      Παράθυρο διαδικασίας = 90 έως 30 ημέρες πριν τη λήξη. Είναι εκτιμήσεις από το ιστορικό, όχι ανακοινώσεις.</div></div>`;
}
function viewHist(o){
  const cs = o.cs.filter(c=>svcFilter===""||c.s===+svcFilter).sort((a,b)=>b.sg.localeCompare(a.sg));
  return `<div class="sec"><div class="sech">Ιστορικό συμβάσεων · ${cs.length}</div>
    <table class="grid"><thead><tr><th>Υπογραφή</th><th>Υπηρεσία</th><th>Ανάδοχος / τίτλος</th><th class="num">Αξία €</th><th>Λήξη</th><th></th></tr></thead><tbody>
    ${cs.map(c=>`<tr><td style="white-space:nowrap">${fmtD(c.sg)}</td><td>${esc(D.svc[c.s])}
        ${c.chk===2?'<div><span class="pill p-warn">⚠ τίτλος αντίθετος</span></div>':""}${c.am?'<div><span class="pill p-old">ΠΑΡΑΤΑΣΗ</span></div>':""}</td>
      <td><a class="ext" href="contractors.html?q=${encodeURIComponent(D.hold[c.h])}">${esc(D.hold[c.h])}</a>
        ${c.subj?`<div class="subject-line">${esc(c.subj)}</div>`:""}</td>
      <td class="num">${fmtEur(c.v)}</td><td style="white-space:nowrap">${fmtD(c.e)}</td>
      <td>${c.a?`<a class="ext" target="_blank" rel="noopener" href="${KHMDHS+c.a}">σύμβαση ↗</a>`:""}</td></tr>`).join("")
      || '<tr><td colspan="6" class="empty">Καμία σύμβαση.</td></tr>'}</tbody></table></div>`;
}

// ── resolve "ωρωπου | εσωτερικος ελεγχος" style queries ───────────────────
function findSvc(t){ const n=norm(t); if(!n) return "";
  let best=-1,bs=0; D.svc.forEach((s,i)=>{ const ns=norm(s); const ws=n.split(/\s+/).filter(w=>w.length>=3);
    const sc=ws.filter(w=>ns.includes(w.slice(0,Math.max(3,w.length-2)))).length; if(sc>bs){bs=sc;best=i;} });
  return best>=0?String(best):""; }
function resolveOrg(t){
  const ws=norm(t).split(/\s+/).filter(w=>w.length>=3); if(!ws.length) return {list:[]};
  const sc=ORGS.map(o=>({o,s:ws.filter(w=>o.n.includes(w)).length})).filter(x=>x.s>0)
    .sort((a,b)=>b.s-a.s || b.o.count-a.o.count || a.o.name.length-b.o.name.length);
  const full=sc.filter(x=>x.s===ws.length);
  if(full.length===1) return {one:full[0].o};
  // a Δήμος named exactly by the words wins over its sub-entities
  const dim=full.filter(x=>x.o.type==="Δήμος");
  if(dim.length===1) return {one:dim[0].o};
  return {list:(full.length?full:sc).map(x=>x.o)};
}

// ── keyboard (Gödel-style): ↑↓ Enter in screener; D I N H / Esc in dossier ─
document.addEventListener("keydown",e=>{
  const t=e.target; if(t&&(t.tagName==="INPUT"||t.tagName==="SELECT"||t.tagName==="TEXTAREA")) return;
  if(e.metaKey||e.ctrlKey||e.altKey) return;
  if(cur){
    const m={d:"des",i:"inc",n:"next",h:"hist"}[e.key.toLowerCase()];
    if(m){ view=m; renderView(); pushUrl(); e.preventDefault(); }
    else if(e.key==="Escape"||e.key==="Backspace"){ closeOrg(); e.preventDefault(); }
    return;
  }
  const n=Math.min(shown,curList.length);
  if(e.key==="ArrowDown"||e.key==="j"){ selRow=Math.min(n-1,selRow+1); renderTable(); e.preventDefault(); scrollSel(); }
  else if(e.key==="ArrowUp"||e.key==="k"){ selRow=Math.max(0,selRow-1); renderTable(); e.preventDefault(); scrollSel(); }
  else if(e.key==="Enter" && curList[selRow]){ openOrg(curList[selRow].i,"des"); }
});
function scrollSel(){ const r=document.querySelector("#tbody tr.sel"); if(r) r.scrollIntoView({block:"nearest"}); }

// ── boot from URL ──────────────────────────────────────────────────────────
(function(){
  const p=new URLSearchParams(location.search);
  const v=(p.get("view")||"des").toLowerCase();
  const svc=p.get("svc");
  if(p.get("org")){ const o=ORGS.find(x=>x.k===p.get("org")); if(o){ addFilter("name"); openOrg(o.i,v,svc); return; } }
  const q=(p.get("q")||"").trim();
  if(q){
    const [orgPart, svcPart] = q.split("|").map(s=>s.trim());
    const si = svcPart ? findSvc(svcPart) : (p.get("svc")||"");
    const r = resolveOrg(orgPart||"");
    if(p.get("view") && r.one){ addFilter("name",{q:orgPart}); openOrg(r.one.i,v,si); return; }
    addFilter("name",{q:orgPart});
    if(si!=="") addFilter("svc",{svc:+si,state:"noactive"});
    if(r.one && p.get("view")) openOrg(r.one.i,v,si);
    return;
  }
  addFilter("name"); addFilter("type");
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
