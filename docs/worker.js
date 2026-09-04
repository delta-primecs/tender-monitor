/**
 * Cloudflare Worker — Tender Radar + Team Chat
 * ------------------------------------------------------------
 * This Worker does TWO jobs:
 *   1. Serves your static tool (the docs/ folder) — as it already does.
 *   2. Adds a tiny chat API backed by Cloudflare KV.
 *
 * Chat endpoints:
 *   POST /api/chat/send      body: {text: "..."}   → stores a message
 *   GET  /api/chat/messages                        → returns last N messages
 *
 * Identity: Cloudflare Access puts the logged-in user's email in a request
 * header, so messages are auto-attributed — no login logic needed here.
 *
 * SETUP (one-time, in Cloudflare dashboard — see the guide):
 *   - Create a KV namespace (e.g. "CHAT")
 *   - Bind it to this Worker with the variable name  CHAT
 * ------------------------------------------------------------
 */

const MAX_MESSAGES = 200;          // rolling history kept in KV
const KV_KEY = "chat:messages";    // single key holding the JSON array

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // ---- Chat API ----
    if (url.pathname === "/api/chat/messages" && request.method === "GET") {
      return json(await getMessages(env));
    }
    if (url.pathname === "/api/chat/send" && request.method === "POST") {
      return await sendMessage(request, env);
    }

    // ---- Everything else: serve the static site ----
    // If your Worker uses the built-in static assets binding (env.ASSETS),
    // this line serves docs/. If your setup differs, keep whatever you had
    // here before for serving the site.
    if (env.ASSETS) {
      return env.ASSETS.fetch(request);
    }
    return new Response("Not found", { status: 404 });
  },
};

// ---------- helpers ----------
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

// Who is the caller? Cloudflare Access sets these headers after login.
function callerEmail(request) {
  return (
    request.headers.get("Cf-Access-Authenticated-User-Email") ||
    request.headers.get("cf-access-authenticated-user-email") ||
    "anon"
  );
}

// Short display name from an email (before the @)
function nameFromEmail(email) {
  if (!email || email === "anon") return "anon";
  return email.split("@")[0];
}

async function getMessages(env) {
  if (!env.CHAT) return { ok: false, error: "KV not bound", messages: [] };
  const raw = await env.CHAT.get(KV_KEY);
  const messages = raw ? JSON.parse(raw) : [];
  return { ok: true, messages };
}

async function sendMessage(request, env) {
  if (!env.CHAT) return json({ ok: false, error: "KV not bound" }, 500);

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "bad json" }, 400);
  }

  const text = (body.text || "").toString().trim().slice(0, 2000);
  if (!text) return json({ ok: false, error: "empty" }, 400);

  const email = callerEmail(request);
  const msg = {
    id: Date.now() + "-" + Math.random().toString(36).slice(2, 7),
    name: nameFromEmail(email),
    email,
    text,
    ts: Date.now(),
  };

  // read-modify-write the rolling list
  const raw = await env.CHAT.get(KV_KEY);
  const messages = raw ? JSON.parse(raw) : [];
  messages.push(msg);
  // keep only the last MAX_MESSAGES
  const trimmed = messages.slice(-MAX_MESSAGES);
  await env.CHAT.put(KV_KEY, JSON.stringify(trimmed));

  return json({ ok: true, message: msg });
}
