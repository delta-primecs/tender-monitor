"""
build_news.py — Τοπική Αυτοδιοίκηση news feed (Gödel terminal style).

Pulls RSS from Greek local-government news sites, merges + dedupes, sorts
newest first, renders docs/news.html. Optional in-page search filters live.

Defensive by design: if a feed is down or malformed, it's skipped — the page
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

# ── Sources ───────────────────────────────────────────────────────────────
# All WordPress-based local-gov news portals → standard /feed/ RSS.
# Add/remove freely; a dead feed is skipped, never breaks the build.
FEEDS = [
    ("Αυτοδιοίκηση",  "https://www.aftodioikisi.gr/feed/"),
    ("Airetos",       "https://airetos.gr/feed/"),
    ("Localit",       "https://localit.gr/feed/"),
    ("Epoli",         "https://epoli.gr/feed/"),
    ("Aftodioikisi·ΥΠΕΣ", "https://www.aftodioikisi.gr/tag/ypes/feed/"),
]

MAX_PER_FEED = 40      # cap per source so one prolific feed doesn't dominate
MAX_TOTAL    = 200     # overall cap on the page
TIMEOUT      = 20      # feedparser has no direct timeout; we guard via socket


def fetch_feed(name, url):
    """Return list of normalized items. Never raises."""
    items = []
    try:
        import socket
        socket.setdefaulttimeout(TIMEOUT)
        d = feedparser.parse(url)
        if getattr(d, "bozo", 0) and not d.entries:
            print(f"  {name}: no entries (bozo={d.bozo})")
            return []
        for e in d.entries[:MAX_PER_FEED]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link:
                continue
            # published time → epoch for sorting
            ts = 0
            for key in ("published_parsed", "updated_parsed"):
                if e.get(key):
                    try:
                        ts = int(time.mktime(e[key]))
                    except Exception:
                        ts = 0
                    break
            # short summary, stripped of HTML
            summary = e.get("summary", "") or ""
            summary = strip_html(summary)[:180]
            items.append({
                "source": name, "title": title, "link": link,
                "ts": ts, "summary": summary,
            })
        print(f"  {name}: {len(items)} items")
    except Exception as ex:
        print(f"  {name}: FAILED ({type(ex).__name__})")
    return items


def strip_html(s):
    import re
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return " ".join(s.split())


def main():
    print("Fetching news feeds …")
    all_items = []
    for name, url in FEEDS:
        all_items.extend(fetch_feed(name, url))

    # dedupe by link
    seen, deduped = set(), []
    for it in all_items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        deduped.append(it)

    # newest first
    deduped.sort(key=lambda x: x["ts"], reverse=True)
    deduped = deduped[:MAX_TOTAL]

    print(f"\nTotal after dedupe: {len(deduped)} items from "
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
  .item{padding:11px 16px;border-top:1px solid var(--hair);display:flex;gap:14px;align-items:baseline}
  .item:first-child{border-top:0}
  .item:nth-child(even){background:var(--panel-2)}
  .item:hover{background:#161d28}
  .src{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:.05em;
       white-space:nowrap;min-width:120px;font-weight:700}
  .body{flex:1;min-width:0}
  .ttl{font-size:14px;color:var(--bright);text-decoration:none;font-weight:500}
  .ttl:hover{color:var(--accent);text-decoration:underline}
  .sum{font-size:12px;color:var(--muted);margin-top:3px}
  .when{font-size:11px;color:var(--muted);white-space:nowrap;text-align:right;min-width:80px}
  .empty{padding:40px;text-align:center;color:var(--muted)}
  .foot{max-width:none;margin:12px auto 0;color:var(--muted);font-size:11px;line-height:1.6}
</style></head><body>
<div id="nav"></div>
<div class="wrap">
  <div class="desk">
    <span class="live-label">Live feed · ΤΟΠΙΚΗ ΑΥΤΟΔΙΟΙΚΗΣΗ</span>
    <h1>NEWS</h1>
    <div class="stamp"><div class="n">__STAMP__</div><div class="l">Updated</div></div>
  </div>
  <div class="controls">
    <input id="q" type="search" placeholder="Φίλτρο — λέξη-κλειδί, φορέας, πηγή… (προαιρετικό)">
  </div>
  <main class="list" id="list"></main>
  <div class="empty" id="empty" style="display:none"></div>
  <div class="foot">
    Πηγές τοπικής αυτοδιοίκησης · ανανέωση 2×/ημέρα · κάθε τίτλος ανοίγει στην πηγή.<br>
    Δεν φιλτράρεται αυτόματα — χρησιμοποίησε το πεδίο αναζήτησης για στόχευση.
  </div>
</div>
<script src="godel.css"></script>
<script src="nav.js"></script>
<script>
const ITEMS = __DATA__;
const listEl=document.getElementById('list'), emptyEl=document.getElementById('empty'), qEl=document.getElementById('q');
function ago(ts){
  if(!ts) return '';
  const d=Math.floor((Date.now()/1000 - ts)/86400);
  if(d<=0) return 'σήμερα'; if(d===1) return 'χθες'; return 'πριν '+d+' ημ.';
}
function render(){
  const q=(qEl.value||'').trim().toLowerCase();
  const rows = q ? ITEMS.filter(i=>((i.title||'')+' '+(i.summary||'')+' '+(i.source||'')).toLowerCase().includes(q)) : ITEMS;
  listEl.innerHTML='';
  rows.slice(0,300).forEach(i=>{
    const el=document.createElement('div'); el.className='item';
    el.innerHTML='<span class="src">'+(i.source||'')+'</span>'+
      '<div class="body"><a class="ttl" href="'+i.link+'" target="_blank" rel="noopener">'+i.title+'</a>'+
      (i.summary?'<div class="sum">'+i.summary+'</div>':'')+'</div>'+
      '<span class="when">'+ago(i.ts)+'</span>';
    listEl.appendChild(el);
  });
  emptyEl.style.display = rows.length? 'none':'block';
  emptyEl.textContent = rows.length? '' : 'Καμία είδηση δεν ταιριάζει.';
}
qEl.addEventListener('input', render);
render();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
