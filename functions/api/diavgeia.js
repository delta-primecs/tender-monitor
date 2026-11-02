/**
 * Cloudflare PAGES FUNCTION — Διαύγεια full-text search proxy
 * ------------------------------------------------------------
 * File location in repo:  functions/api/diavgeia.js
 * Cloudflare Pages routes this to:  /api/diavgeia
 *
 * Why a proxy: the Διαύγεια website (the Angular SPA) does NOT run a free-text
 * search from a URL you deep-link to, and its OpenData API cannot be called
 * straight from the browser (CORS). So we call the SAME OpenData endpoint the
 * ingester already uses, but SERVER-SIDE here on the edge, and hand the page
 * back clean JSON. No KV, no secrets, nothing else touched.
 *
 *   GET /api/diavgeia?q=<ελεύθερο κείμενο>&page=0  → { total, page, q, items:[…] }
 * ------------------------------------------------------------
 */

// Classic OpenData full-text endpoint — this one DOES accept plain free-text
// `q`. (The newer luminapi .../search/advanced wants structured field queries
// like cpv:"…" and returns HTTP 400 for bare words.)
const API = "https://diavgeia.gov.gr/opendata/search";
const SIZE = 30;

export async function onRequestGet(context) {
  const url = new URL(context.request.url);
  const q = (url.searchParams.get("q") || "").trim();
  const page = Math.max(0, parseInt(url.searchParams.get("page") || "0", 10) || 0);

  if (!q) return json({ total: 0, page: 0, q: "", items: [] });

  // Only the params the classic endpoint is known to accept for free text.
  const api = API + "?q=" + encodeURIComponent(q) +
              "&size=" + SIZE + "&page=" + page;

  let data;
  try {
    const r = await fetch(api, {
      headers: { "Accept": "application/json" },
      cf: { cacheTtl: 0 },
    });
    if (!r.ok) {
      let detail = "";
      try { detail = (await r.text()).slice(0, 300); } catch (e) {}
      return json({ error: "Διαύγεια HTTP " + r.status, detail, tried: api, items: [] }, 502);
    }
    data = await r.json();
  } catch (e) {
    return json({ error: "Αδυναμία σύνδεσης με τη Διαύγεια", items: [] }, 502);
  }

  const decisions = data.decisions || data.results || [];
  const items = decisions.map((d) => {
    const ada = (d.ada || d.ADA || d.adam || "").toString();
    const enc = ada ? encodeURIComponent(ada) : "";
    return {
      ada,
      subject: (d.subject || d.subjectText || "(χωρίς θέμα)").toString().replace(/\s+/g, " ").trim(),
      org: orgName(d),
      type: (d.documentTypeLabel || (d.documentType && d.documentType.label) || "").toString(),
      date: toDate(d.publishTimestamp || d.issueDate || d.submissionTimestamp || d.publicationDate),
      // Per Διαύγεια: the ΑΔΑ is Greek text and /doc/ needs it percent-encoded,
      // otherwise it serves a broken redirect.
      view: enc ? "https://diavgeia.gov.gr/decision/view/" + enc : null,
      doc: enc ? "https://diavgeia.gov.gr/doc/" + enc : null,
    };
  });

  const total =
    (data.info && (data.info.total ?? data.info.actualSize)) ??
    data.total ?? data.numFound ?? items.length;

  return json({ total, page, q, size: SIZE, items });
}

function orgName(d) {
  // The API sometimes gives a name, sometimes only an id — show whatever we have.
  if (d.organization && typeof d.organization === "object")
    return (d.organization.label || d.organization.value || d.organization.name || "").toString();
  return (d.organizationLabel || d.organizationName || d.organization || d.organizationId || "").toString();
}

function toDate(v) {
  if (v === null || v === undefined || v === "") return null;
  if (typeof v === "number") {
    try { return new Date(v).toISOString().slice(0, 10); } catch (e) { return null; }
  }
  const s = v.toString();
  return s.length >= 10 ? s.slice(0, 10) : s;
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
