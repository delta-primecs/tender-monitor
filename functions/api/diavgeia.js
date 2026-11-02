/**
 * Cloudflare PAGES FUNCTION — Διαύγεια: φορέας + θέμα σε μία φράση
 * ------------------------------------------------------------
 * File location in repo:  functions/api/diavgeia.js   →  /api/diavgeia
 *
 * You type e.g.  "οικονομικες καταστασεις ωρωπου"  and get the decisions.
 * How it works (only proven mechanics — no free-text guessing):
 *   1. The words that match an organisation NAME  → resolve the ΦΟΡΕΑ (uid).
 *      (same organizations endpoint resolve_orgs.py uses)
 *   2. Fetch that φορέα's decisions:  q=organizationUid:"<uid>"  on the advanced
 *      endpoint (the exact filter the Διαύγεια site itself uses).
 *   3. The LEFTOVER words (the topic, e.g. "οικονομικες καταστασεις") filter the
 *      decisions by subject, client-side — so morphology & order don't matter.
 *
 * Routes:
 *   GET ?q=<φράση>            → resolve. Either {mode:"results",…} if one clear
 *                               φορέας, or {mode:"pick", matches, topic} to choose.
 *   GET ?uid=<uid>&topic=<..> → that φορέα's decisions, filtered by topic.
 *   GET ?debug=1              → raw shape of the organizations endpoint.
 *
 * Org list is cached in the CHAT KV namespace (already bound for chat).
 * ------------------------------------------------------------
 */

const ORGS_API = "https://diavgeia.gov.gr/luminapi/opendata/organizations";
const SEARCH_API = "https://diavgeia.gov.gr/luminapi/opendata/search/advanced";
const DECIS_WEB = "https://diavgeia.gov.gr/search";
const CACHE_KEY = "diavgeia:orgindex:v1";
const CACHE_TTL_MS = 7 * 24 * 3600 * 1000;
const PAGE_SIZE = 500;
const MAX_ORG_PAGES = 12;
const DECISION_PAGES = 3;   // up to 3×100 = 300 recent decisions per φορέας
const DECISION_SIZE = 100;

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  if (url.searchParams.get("debug")) return debugOrgs();

  // ── Step 2: a φορέας is chosen → fetch & topic-filter its decisions ──
  const uid = (url.searchParams.get("uid") || "").trim();
  if (uid) {
    const topic = (url.searchParams.get("topic") || "").trim();
    const label = (url.searchParams.get("label") || "").trim();
    const res = await orgDecisions(uid, topic);
    res.org = { uid, label };
    return json(res);
  }

  // ── Step 1: resolve the φορέας from the typed phrase ──
  const q = (url.searchParams.get("q") || "").trim();
  if (!q) return json({ mode: "empty" });

  let orgs;
  try { orgs = await loadOrgs(env); }
  catch (e) { return json({ mode: "error", error: "Αδυναμία φόρτωσης φορέων" }, 502); }
  if (!orgs.length) return json({ mode: "error", error: "Δεν φορτώθηκε η λίστα φορέων" }, 502);

  const tokens = tokenize(q);
  if (!tokens.length) return json({ mode: "none", q, orgCount: orgs.length });

  const scored = [];
  for (const o of orgs) {
    let c = 0;
    for (const t of tokens) if (o.n.indexOf(t) !== -1) c++;
    if (c > 0) scored.push({ uid: o.u, label: o.l, n: o.n, score: c, len: o.l.length });
  }
  scored.sort((a, b) => b.score - a.score || a.len - b.len);
  if (!scored.length) return json({ mode: "none", q, tokens, orgCount: orgs.length });

  const top = scored[0], second = scored[1];
  // topic = the words that are NOT part of the chosen φορέας's name
  const topic = tokens.filter((t) => top.n.indexOf(t) === -1).join(" ");
  const decisive = top.score >= 2 && (!second || top.score > second.score);

  if (decisive) {
    const res = await orgDecisions(top.uid, topic);
    res.org = { uid: top.uid, label: top.label };
    return json(res);
  }

  // ambiguous → let the user pick, carrying the topic along
  return json({
    mode: "pick", q, topic, orgCount: orgs.length,
    matches: scored.slice(0, 8).map((m) => ({ uid: m.uid, label: m.label, score: m.score })),
  });
}

// ── fetch a φορέας's decisions, filter by topic words ───────────────────────
async function orgDecisions(uid, topic) {
  const stems = tokenize(topic).map(stem);
  const items = [];
  let apiErr = null, tried = "";
  for (let page = 0; page < DECISION_PAGES; page++) {
    tried = SEARCH_API + "?q=" + encodeURIComponent('organizationUid:"' + uid + '"') +
            "&size=" + DECISION_SIZE + "&page=" + page + "&sort=recent";
    let r;
    try { r = await fetch(tried, { headers: { "Accept": "application/json" } }); }
    catch (e) { apiErr = "σφάλμα δικτύου"; break; }
    if (!r.ok) { if (page === 0) apiErr = "Διαύγεια HTTP " + r.status; break; }
    const d = await r.json();
    const decisions = d.decisions || d.results || [];
    if (!decisions.length) break;
    for (const dec of decisions) items.push(mapDecision(dec));
    if (decisions.length < DECISION_SIZE) break;
  }
  if (apiErr && !items.length) return { mode: "results", items: [], error: apiErr, tried };

  let shown = items, topicApplied = false;
  if (stems.length) {
    const f = items.filter((it) => {
      const s = deAccent(it.subject);
      return stems.every((st) => s.indexOf(st) !== -1);
    });
    if (f.length) { shown = f; topicApplied = true; }
  }
  return {
    mode: "results",
    topic, topicApplied,
    total: items.length, shown: shown.length,
    items: shown,
    webUrl: DECIS_WEB + "?query=" + encodeURIComponent('organizationUid:"' + uid + '"') +
            "&sort=recent&page=0",
  };
}

function mapDecision(d) {
  const ada = (d.ada || d.ADA || "").toString();
  const enc = ada ? encodeURIComponent(ada) : "";
  return {
    ada,
    subject: (d.subject || d.subjectText || "(χωρίς θέμα)").toString().replace(/\s+/g, " ").trim(),
    type: (d.documentTypeLabel || (d.documentType && d.documentType.label) || "").toString(),
    date: toDate(d.publishTimestamp || d.issueDate || d.submissionTimestamp),
    view: enc ? "https://diavgeia.gov.gr/decision/view/" + enc : null,
    doc: enc ? "https://diavgeia.gov.gr/doc/" + enc : null,
  };
}

// ── organisation index (cached) ─────────────────────────────────────────────
async function loadOrgs(env) {
  if (env && env.CHAT) {
    try {
      const raw = await env.CHAT.get(CACHE_KEY);
      if (raw) {
        const obj = JSON.parse(raw);
        if (obj && obj.t && Date.now() - obj.t < CACHE_TTL_MS && Array.isArray(obj.o)) return obj.o;
      }
    } catch (e) {}
  }
  const orgs = await fetchAllOrgs();
  if (env && env.CHAT && orgs.length) {
    try { await env.CHAT.put(CACHE_KEY, JSON.stringify({ t: Date.now(), o: orgs })); } catch (e) {}
  }
  return orgs;
}

async function fetchAllOrgs() {
  const out = [];
  const seen = new Set();
  for (let page = 0; page < MAX_ORG_PAGES; page++) {
    let r;
    try { r = await fetch(ORGS_API + "?page=" + page + "&size=" + PAGE_SIZE,
                          { headers: { "Accept": "application/json" } }); }
    catch (e) { break; }
    if (!r.ok) break;
    const d = await r.json();
    const batch = Array.isArray(d) ? d : (d.organizations || d.content || d.results || []);
    if (!batch.length) break;
    let added = 0;
    for (const o of batch) {
      const uid = (o.uid || o.id || o.organizationId || "").toString();
      const label = (o.label || o.name || "").toString();
      if (uid && label && !seen.has(uid)) {
        seen.add(uid);
        out.push({ u: uid, l: label, n: deAccent(label) });
        added++;
      }
    }
    if (added === 0) break; // last page, or server ignores ?page= (repeats batch)
  }
  return out;
}

async function debugOrgs() {
  try {
    const r = await fetch(ORGS_API + "?page=0&size=5", { headers: { "Accept": "application/json" } });
    let d = null; try { d = await r.json(); } catch (e) {}
    const arr = Array.isArray(d) ? d : (d && (d.organizations || d.content || d.results)) || [];
    return json({
      debug: true, status: r.status,
      topKeys: d && !Array.isArray(d) ? Object.keys(d) : [],
      batchLen: arr.length,
      firstOrgKeys: arr[0] ? Object.keys(arr[0]) : [],
      sample: arr.slice(0, 3),
    });
  } catch (e) {
    return json({ debug: true, error: String(e) }, 502);
  }
}

// stems: trim Greek inflection so topic words match any case ending
function stem(t) {
  if (t.length >= 6) return t.slice(0, t.length - 2);
  if (t.length >= 4) return t.slice(0, t.length - 1);
  return t;
}
function tokenize(s) {
  return Array.from(new Set(deAccent(s).split(/\s+/).filter((t) => t.length >= 3)));
}
function deAccent(s) {
  return (s || "").toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
function toDate(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") { try { return new Date(v).toISOString().slice(0, 10); } catch (e) { return null; } }
  const s = v.toString();
  return s.length >= 10 ? s.slice(0, 10) : s;
}
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}
