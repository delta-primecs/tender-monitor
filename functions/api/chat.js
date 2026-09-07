/**
 * Cloudflare PAGES FUNCTION — Team Chat backend
 * ------------------------------------------------------------
 * File location in repo:  functions/api/chat.js
 * Cloudflare Pages automatically routes this to:  /api/chat
 *
 * Unlike a Worker, this does NOT serve the site — Pages already serves docs/.
 * This ONLY handles the chat API. Nothing else is touched. Zero risk to the tool.
 *
 *   GET  /api/chat            → returns last N messages
 *   POST /api/chat  {text}    → stores a message
 *
 * SETUP (one-time, in Pages project settings):
 *   - Create a KV namespace (e.g. "chat")
 *   - Bind it to the Pages project with variable name  CHAT
 * ------------------------------------------------------------
 */

const MAX_MESSAGES = 200;
const KV_KEY = "chat:messages";

// GET /api/chat  → list messages
export async function onRequestGet(context) {
  const { env } = context;
  if (!env.CHAT) return json({ ok: false, error: "KV not bound", messages: [] });
  const raw = await env.CHAT.get(KV_KEY);
  const messages = raw ? JSON.parse(raw) : [];
  return json({ ok: true, messages });
}

// POST /api/chat  → add a message
export async function onRequestPost(context) {
  const { request, env } = context;
  if (!env.CHAT) return json({ ok: false, error: "KV not bound" }, 500);

  let body;
  try { body = await request.json(); }
  catch { return json({ ok: false, error: "bad json" }, 400); }

  const text = (body.text || "").toString().trim().slice(0, 2000);
  if (!text) return json({ ok: false, error: "empty" }, 400);

  const email =
    request.headers.get("Cf-Access-Authenticated-User-Email") ||
    request.headers.get("cf-access-authenticated-user-email") ||
    "anon";
  const name = email === "anon" ? "anon" : email.split("@")[0];

  const msg = {
    id: Date.now() + "-" + Math.random().toString(36).slice(2, 7),
    name, email, text, ts: Date.now(),
  };

  const raw = await env.CHAT.get(KV_KEY);
  const messages = raw ? JSON.parse(raw) : [];
  messages.push(msg);
  await env.CHAT.put(KV_KEY, JSON.stringify(messages.slice(-MAX_MESSAGES)));

  return json({ ok: true, message: msg });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
