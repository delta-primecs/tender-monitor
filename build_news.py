"""
build_news.py - Τοπική Αυτοδιοίκηση news feed (Godel terminal style).

Pulls RSS from Greek local-government news sites, merges + dedupes, sorts
newest first, renders docs/news.html. Optional in-page search filters live.

Defensive by design: if a feed is down or malformed, it's skipped - the page
still builds from whatever feeds responded. No keyword filtering (user reads
with the eye); a search box is provided for optional narrowing.

Run:  python build_news.py
Needs: feedparser  (pip install feedparser)
"""

import html
import time
import json
from datetime import datetime, timezone

import feedparser

# -- Sources ---------------------------------------------------------------
# All WordPress-based local-gov news portals -> standard /feed/ RSS.
# Add/remove freely; a dead feed is skipped, never breaks the build.
FEEDS = [
    # (name, url, category)  — category ΠΡΟΘΕΣΜΙΕΣ = deadline calendar (sorted soonest-first)
    ("Αυτοδιοίκηση", "https://www.aftodioikisi.gr/feed/",                         "ΑΥΤΟΔΙΟΙΚΗΣΗ"),
    ("Airetos",      "https://www.airetos.gr/feed/",                             "ΑΥΤΟΔΙΟΙΚΗΣΗ"),

    ("Taxheaven · Νέα",       "https://www.taxheaven.gr/bibliothiki/soft/xml/soft_new.xml", "ΦΟΡΟΛΟΓΙΚΑ"),
    ("Taxheaven · Προθεσμίες","https://www.taxheaven.gr/bibliothiki/soft/xml/soft_dat.xml", "ΠΡΟΘΕΣΜΙΕΣ"),

    ("ΟΤ · Οικονομία", "https://www.ot.gr/category/oikonomia/feed/", "ΟΙΚΟΝΟΜΙΑ"),
    ("ΟΤ · Φορολογία", "https://www.ot.gr/category/forologia/feed/", "ΦΟΡΟΛΟΓΙΚΑ"),
    ("ΟΤ · Αγορές",    "https://www.ot.gr/category/agores/feed/",    "ΟΙΚΟΝΟΜΙΑ"),

    ("Καθημερινή · Οικ.", "https://feeds.feedburner.com/kathimerini_economy", "ΟΙΚΟΝΟΜΙΑ"),
    ("Capital.gr",   "https://www.capital.gr/rss",           "ΟΙΚΟΝΟΜΙΑ"),
    ("Ναυτεμπορική", "https://www.naftemporiki.gr/feed/",    "ΟΙΚΟΝΟΜΙΑ"),
]

MAX_PER_FEED = 40      # cap per source so one prolific feed doesn't dominate
MAX_TOTAL    = 200     # overall cap on the page
TIMEOUT      = 20      # feedparser has no direct timeout; we guard via socket


def fetch_feed(name, url, category):
    """Return list of normalized items. Never raises. Tolerant of non-standard
    XML (e.g. Taxheaven custom feeds) - needs only a title to keep an item."""
    items = []
    is_deadline = (category == "ΠΡΟΘΕΣΜΙΕΣ")
    try:
        import socket
        socket.setdefaulttimeout(TIMEOUT)
        d = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0 (tender-monitor)"})
        if getattr(d, "bozo", 0) and not d.entries:
            print(f"  {name}: no entries (bozo={getattr(d,'bozo','?')})")
            return []
        for e in d.entries[:MAX_PER_FEED]:
            title = (e.get("title") or "").strip()
            if not title:
                continue
            link = (e.get("link") or e.get("id") or e.get("guid") or url).strip()
            ts = 0
            for key in ("published_parsed", "updated_parsed", "created_parsed", "date_parsed"):
                if e.get(key):
                    try:
                        ts = int(time.mktime(e[key]))
                    except Exception:
                        ts = 0
                    break
            summary = strip_html(e.get("summary", "") or e.get("description", "") or "")[:180]
            items.append({
                "source": name, "title": title, "link": link,
                "ts": ts, "summary": summary,
                "cat": category, "deadline": is_deadline,
            })
        print(f"  {name}: {len(items)} items [{category}]")
    except Exception as ex:
        print(f"  {name}: FAILED ({type(ex).__name__})")
    return items


def strip_html(s):
    import re
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return " ".join(s.split())


def main():
    print("Fetching news feeds ...")
    all_items = []
    for name, url, category in FEEDS:
        all_items.extend(fetch_feed(name, url, category))

    # dedupe by link
    seen, deduped = set(), []
    for it in all_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        deduped.append(it)

    # Sort here as a sensible default; the page re-sorts per active filter.
    # News: newest first (ts desc). Deadlines get their own sort in JS.
    deduped.sort(key=lambda x: x["ts"], reverse=True)
    deduped = deduped[:MAX_TOTAL]

    n_dead = sum(1 for i in deduped if i.get("deadline"))
    print(f"\nTotal after dedupe: {len(deduped)} items "
          f"({n_dead} deadlines) from "
          f"{len(set(i['source'] for i in deduped))} live sources")

    stamp = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    write_page(deduped, stamp)


def write_page(items, stamp):
    payload = json.dumps(items, ensure_ascii=False)
    htmlout = TEMPLATE.replace("__DATA__", payload).replace("__STAMP__", stamp)
    with open("docs/news.html", "w", encoding="utf-8") as f:
        f.write(htmlout)
    print("Written: docs/news.html")


TEMPLATE = r"""<!doctype html>
<html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEWS · Αυτοδιοίκηση</title>
<link rel="stylesheet" href="godel.css">
<style>
  .wrap{max-width:none;margin:0 auto}
  .desk{background:var(--panel);border:1px solid var(--hair);padding:12px 16px;
        display:flex;align-items:center;gap:16px;flex-wrap:wrap}
  .live-label{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);
        font-weight:700;display:flex;align-items:center;gap:6px;padding-right:16px;
        border-right:1px solid var(--hair2)}
  .live-label::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--accent);
        box-shadow:0 0 6px var(--accent);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
  h1{font-family:var(--mono);font-weight:700;font-size:18px;margin:0;color:var(--bright);
     text-transform:uppercase;letter-spacing:.02em}
  .stamp{margin-left:auto;text-align:right}
  .stamp .n{font-size:13px;font-weight:700;color:var(--bright)}
  .stamp .l{font-size:9px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-top:3px}
  .controls{background:var(--panel);border:1px solid var(--hair);border-top:0;padding:10px 16px}
  .controls input{width:100%;padding:8px 10px;border:1px solid var(--hair2);background:var(--page);
        color:var(--text);font-family:var(--mono);font-size:13px}
  .list{background:var(--card);border:1px solid var(--hair);border-top:0}
  .newshead{display:flex;gap:16px;align-items:center;padding:7px 16px;
    background:#0c1219;border-bottom:1px solid var(--hair2);
    font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:700}
  .newsrow{display:flex;gap:16px;align-items:center;padding:8px 16px;
    border-top:1px solid var(--hair);text-decoration:none;color:inherit}
  .newsrow:first-of-type{border-top:0}
  .newsrow:nth-child(even){background:var(--panel-2)}
  .newsrow:hover{background:#161d28}
  /* Column widths: headline flexes, the rest fixed */
  .nh-ttl,.nr-ttl{flex:1;min-width:0}
  .nh-date,.nr-date{width:78px;flex:none;text-align:right}
  .nh-time,.nr-time{width:52px;flex:none;text-align:right}
  .nh-src,.nr-src{width:150px;flex:none}
  .nr-ttl{font-size:13.5px;color:var(--bright);white-space:nowrap;
    overflow:hidden;text-overflow:ellipsis}
  .newsrow:hover .nr-ttl{color:var(--accent)}
  .nr-date,.nr-time{font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums}
  .nr-src{font-size:10px;color:var(--accent);text-transform:uppercase;
    letter-spacing:.05em;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .newsrow.hot{background:var(--amber-bg,#2a2010)!important}
  .newsrow.hot .nr-time{color:var(--amber,#e8a13a);font-weight:700}
  .newsrow.past{opacity:.45}
  .newsrow.past .nr-time{color:var(--muted)}
  .dl-tag{font-size:11px}
  .empty{padding:40px;text-align:center;color:var(--muted)}
  .foot{max-width:none;margin:12px auto 0;color:var(--muted);font-size:11px;line-height:1.6}
</style></head><body>
<div id="nav"></div>
<div class="wrap">
  <div class="deskbar">
    <span class="db-title">NEWS</span>
    <span class="db-sub">ΤΟΠΙΚΗ ΑΥΤΟΔΙΟΙΚΗΣΗ · RSS</span>
    <div class="db-filters">
      <div class="seg" id="seg-cat">
        <button data-cat="all" aria-pressed="true">Όλα</button>
        <button data-cat="ΑΥΤΟΔΙΟΙΚΗΣΗ" aria-pressed="false">Αυτοδιοίκηση</button>
        <button data-cat="ΦΟΡΟΛΟΓΙΚΑ" aria-pressed="false">Φορολογικά</button>
        <button data-cat="ΟΙΚΟΝΟΜΙΑ" aria-pressed="false">Οικονομία</button>
        <button data-cat="ΠΡΟΘΕΣΜΙΕΣ" aria-pressed="false">⏰ Προθεσμίες</button>
      </div>
    </div>
    <div class="db-stats">
      <span class="db-stamp">__STAMP__</span>
    </div>
    <input id="q" type="search" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none" tabindex="-1" aria-hidden="true">
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty" style="display:none"></div>
  <div class="foot">
    Πηγές τοπικής αυτοδιοίκησης · ανανέωση 2×/ημέρα · κάθε τίτλος ανοίγει στην πηγή.<br>
    Δεν φιλτράρεται αυτόματα - χρησιμοποίησε το πεδίο αναζήτησης για στόχευση.
  </div>
</div>
<script src="godel.css"></script>
<script src="nav.js"></script>
<script>
const ITEMS = __DATA__;
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
let catFilter='all';
function pad(n){return String(n).padStart(2,'0');}
function fmtDate(ts){ if(!ts) return '—'; const d=new Date(ts*1000);
  return pad(d.getDate())+'/'+pad(d.getMonth()+1)+'/'+String(d.getFullYear()).slice(2); }
function fmtTime(ts){ if(!ts) return '—'; const d=new Date(ts*1000);
  return pad(d.getHours())+':'+pad(d.getMinutes()); }
function daysLeft(ts){ if(!ts) return null; return Math.ceil((ts*1000 - Date.now())/86400000); }
function render(){
  const q=(qEl.value||'').trim().toLowerCase();
  let rows = ITEMS.filter(i=>{
    if(catFilter!=='all' && i.cat!==catFilter) return false;
    if(q && !((i.title||'')+' '+(i.summary||'')+' '+(i.source||'')).toLowerCase().includes(q)) return false;
    return true;
  });
  const deadlineView = (catFilter==='ΠΡΟΘΕΣΜΙΕΣ');
  if(deadlineView){
    // soonest deadline first; past ones sink
    rows = rows.slice().sort((a,b)=>(a.ts||9e12)-(b.ts||9e12));
  }
  const dateHdr = deadlineView ? 'Λήγει' : 'Ημ/νία';
  let html='<div class="newshead"><span class="nh-ttl">Τίτλος</span>'+
           '<span class="nh-date">'+dateHdr+'</span>'+
           (deadlineView?'<span class="nh-time">Απομ.</span>':'<span class="nh-time">Ώρα</span>')+
           '<span class="nh-src">Πηγή</span></div>';
  rows.slice(0,400).forEach(i=>{
    const safe=(i.title||'').replace(/"/g,'&quot;');
    let col3, rowcls='';
    if(i.deadline){
      const dl=daysLeft(i.ts);
      if(dl===null) col3='—';
      else if(dl<0){ col3='έληξε'; rowcls=' past'; }
      else if(dl===0){ col3='σήμερα'; rowcls=' hot'; }
      else { col3=dl+'ημ'; if(dl<=7) rowcls=' hot'; }
    } else {
      col3=fmtTime(i.ts);
    }
    html+='<a class="newsrow'+rowcls+'" href="'+i.link+'" target="_blank" rel="noopener">'+
      '<span class="nr-ttl" title="'+safe+'">'+(i.deadline?'<span class="dl-tag">⏰</span> ':'')+(i.title||'')+'</span>'+
      '<span class="nr-date">'+fmtDate(i.ts)+'</span>'+
      '<span class="nr-time">'+col3+'</span>'+
      '<span class="nr-src">'+(i.source||'')+'</span>'+
      '</a>';
  });
  listEl.innerHTML=html;
  emptyEl.style.display = rows.length? 'none':'block';
  emptyEl.textContent = rows.length? '' : 'Καμία εγγραφή δεν ταιριάζει.';
}
qEl.addEventListener('input', render);
document.querySelectorAll('#seg-cat button').forEach(b=>b.addEventListener('click',()=>{
  catFilter=b.dataset.cat;
  document.querySelectorAll('#seg-cat button').forEach(x=>x.setAttribute('aria-pressed', x===b));
  render();
}));
render();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
