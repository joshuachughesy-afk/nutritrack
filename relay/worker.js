// Sapling USDA relay: a Cloudflare Worker that forwards the two FoodData Central requests the app makes, adding the
// owner's API key on the server so people using the app never need their own. Responses are cached at the edge for a
// week (food data rarely changes) and each visitor is rate-limited, so one heavy user can't use up the key.
//
// Secret: USDA_KEY (set it with `wrangler secret put USDA_KEY` or in the Cloudflare dashboard).

const UPSTREAM = "https://api.nal.usda.gov";
const CACHE_SECONDS = 7 * 24 * 3600;
const LIMIT_PER_MINUTE = 60;
const SEARCH_PARAMS = new Set(["query", "dataType", "pageSize", "pageNumber"]);
const hits = new Map(); // ip -> [windowStart, count]; per isolate, best effort

export function route(url) {
  // Returns the upstream path+query to fetch, or null if the request isn't one we relay.
  if (url.pathname === "/fdc/v1/foods/search") {
    const q = new URLSearchParams();
    for (const [k, v] of url.searchParams) if (SEARCH_PARAMS.has(k)) q.set(k, v.slice(0, 120));
    if (!q.get("query")) return null;
    const size = Math.min(50, Math.max(1, parseInt(q.get("pageSize") || "20", 10) || 20));
    q.set("pageSize", String(size));
    return `/fdc/v1/foods/search?${q}`;
  }
  const m = url.pathname.match(/^\/fdc\/v1\/food\/(\d{1,10})$/);
  if (m) return `/fdc/v1/food/${m[1]}`;
  return null;
}

export function allowed(ip, now = Date.now()) {
  const minute = Math.floor(now / 60000);
  const [win, count] = hits.get(ip) || [minute, 0];
  const next = win === minute ? count + 1 : 1;
  hits.set(ip, [minute, next]);
  if (hits.size > 5000) hits.clear();
  return next <= LIMIT_PER_MINUTE;
}

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json", "access-control-allow-origin": "*", ...extra },
  });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "GET") return json(405, { error: { code: "METHOD", message: "GET only" } });
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health") return json(200, { ok: true, service: "sapling-usda-relay" });
    const path = route(url);
    if (!path) return json(404, { error: { code: "NOT_FOUND", message: "Unknown endpoint" } });
    if (!env.USDA_KEY) return json(503, { error: { code: "NO_KEY", message: "The relay has no USDA key yet" } });
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    if (!allowed(ip)) return json(429, { error: { code: "OVER_RATE_LIMIT", message: "Too many searches. Try again in a minute." } });

    const cache = typeof caches !== "undefined" ? caches.default : null;
    const cacheKey = new Request(`https://cache.sapling${path}`);
    if (cache) {
      const hit = await cache.match(cacheKey);
      if (hit) return hit;
    }
    const upstream = await fetch(UPSTREAM + path, { headers: { "X-Api-Key": env.USDA_KEY, Accept: "application/json" } });
    const body = await upstream.text();
    if (!upstream.ok) {
      // Never pass the upstream error through verbatim: it can echo request details.
      const code = upstream.status === 429 ? "OVER_RATE_LIMIT" : upstream.status === 404 ? "NOT_FOUND" : "UPSTREAM";
      return json(upstream.status === 404 ? 404 : 502, { error: { code, message: `USDA returned ${upstream.status}` } });
    }
    const res = new Response(body, {
      status: 200,
      headers: { "content-type": "application/json", "cache-control": `public, max-age=${CACHE_SECONDS}`,
                 "access-control-allow-origin": "*" },
    });
    if (cache && ctx) ctx.waitUntil(cache.put(cacheKey, res.clone()));
    return res;
  },
};
