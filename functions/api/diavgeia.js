/**
 * Cloudflare PAGES FUNCTION — Διαύγεια φορέας resolver
 * ------------------------------------------------------------
 * File location in repo:  functions/api/diavgeia.js   →  /api/diavgeia
 *
 * Why this shape: Διαύγεια's free-text search is useless (it ORs words and
 * matches millions). What actually returns clean results — as the Διαύγεια UI
 * itself does — is filtering by ΦΟΡΕΑ (organizationUid). So this endpoint takes
 * the words the user typed, finds the matching organisation(s), and hands back
 * a ready Διαύγεια deep-link filtered to that φορέα (which DOES work:
 *   https://diavgeia.gov.gr/search?query=organizationUid:"55028"&sort=recent ).
 *
 *   GET /api/diavgeia?q=<όνομα φορέα>  → { matches:[{uid,label,score,url}], … }
 *
 * The full organisation list is fetched once from the Διαύγεια OpenData API
 * (the same endpoint resolve_orgs.py uses) and cached in the CHAT KV namespace
 * so later searches are instant. No new binding needed if CHAT is already bound;
 * without it, it just fetches each time.
 * ------------------------------------------------------------
 */

const ORGS_API = "https://diavgeia.gov.gr/luminapi/opendata/organizations";
const DECIS_WEB = "https://diavgeia.gov.gr/search";
const CACHE_KEY = "diavgeia:orgindex:v1";
const CACHE_TTL_MS = 7 * 24 * 3600 * 1000; // a week
const PAGE_SIZE = 500;
const MAX_PAGES = 12;                       // each page is ~5400 orgs; a few cover all

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  // ?debug=1 → show the RAW shape of the organizations endpoint so we can see
  // the real field names (page 0 only, nothing cached).
  if (url.searchParams.get("debug")) {
    try {
      const r = await fetch(ORGS_API + "?page=0&size=5", { headers: { "Accept": "application/json" } });
      const status = r.status;
      let d = null; try { d = await r.json(); } catch (e) {}
      const topKeys = d && typeof d === "object" && !Array.isArray(d) ? Object.keys(d) : [];
      const arr = Array.isArray(d) ? d : (d && (d.organizations || d.content || d.results)) || [];
      return json({
        debug: true, status, topKeys, isArray: Array.isArray(d),
        batchLen: arr.length,
        firstOrgKeys: arr[0] ? Object.keys(arr[0]) : [],
        sample: arr.slice(0, 3),
      });
    } catch (e) {
      return json({ debug: true, error: String(e) }, 502);
    }
  }

  const q = (url.searchParams.get("q") || "").trim();
  if (!q) return json({ matches: [], q: "" });

  let orgs;
  try {
    orgs = await loadOrgs(env);
  } catch (e) {
    return json({ error: "Αδυναμία φόρτωσης φορέων από τη Διαύγεια", matches: [] }, 502);
  }
  if (!orgs.length) {
    return json({ error: "Δεν φορτώθηκε η λίστα φορέων της Διαύγειας", matches: [] }, 502);
  }

  const tokens = tokenize(q);
  if (!tokens.length) return json({ q, matches: [], note: "πολύ γενικοί όροι" });

  const scored = [];
  for (const o of orgs) {
    let c = 0;
    for (const t of tokens) if (o.n.indexOf(t) !== -1) c++;
    if (c > 0) scored.push({ uid: o.u, label: o.l, score: c, len: o.l.length });
  }
  // most tokens matched first; shorter (more specific) label breaks ties
  scored.sort((a, b) => b.score - a.score || a.len - b.len);

  const matches = scored.slice(0, 8).map((m) => ({
    uid: m.uid,
    label: m.label,
    score: m.score,
    url: DECIS_WEB + "?query=" +
         encodeURIComponent('organizationUid:"' + m.uid + '"') +
         "&sort=recent&page=0",
  }));

  return json({ q, tokens, orgCount: orgs.length, matches });
}

// ── organisation index (cached) ─────────────────────────────────────────────
async function loadOrgs(env) {
  if (env && env.CHAT) {
    try {
      const raw = await env.CHAT.get(CACHE_KEY);
      if (raw) {
        const obj = JSON.parse(raw);
        if (obj && obj.t && Date.now() - obj.t < CACHE_TTL_MS && Array.isArray(obj.o))
          return obj.o;
      }
    } catch (e) { /* fall through to refetch */ }
  }
  const orgs = await fetchAllOrgs();
  if (env && env.CHAT && orgs.length) {
    try { await env.CHAT.put(CACHE_KEY, JSON.stringify({ t: Date.now(), o: orgs })); }
    catch (e) { /* cache is best-effort */ }
  }
  return orgs;
}

async function fetchAllOrgs() {
  const out = [];
  const seen = new Set();
  for (let page = 0; page < MAX_PAGES; page++) {
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
    // Stop at the last page, OR when the server ignores ?page= and just repeats
    // the same batch (no new orgs added) — the endpoint ignores ?size= too.
    if (added === 0) break;
  }
  return out;
}

function tokenize(s) {
  // unique, accent-stripped words of 3+ chars (so "ΤΑΜΕΙΟ", "ΣΚΑΛΑΣ" count,
  // but noise like "ΚΑΙ", "ΤΟΥ" is dropped)
  return Array.from(new Set(deAccent(s).split(/\s+/).filter((t) => t.length >= 3)));
}

function deAccent(s) {
  return (s || "").toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}
