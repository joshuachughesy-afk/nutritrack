import test from "node:test";
import assert from "node:assert/strict";
import worker, { route, allowed } from "./worker.js";

test("routes only the two USDA endpoints and drops unknown params", () => {
  assert.equal(route(new URL("https://r/fdc/v1/foods/search?query=banana&dataType=Foundation,SR%20Legacy&pageSize=20&api_key=x")),
    "/fdc/v1/foods/search?query=banana&dataType=Foundation%2CSR+Legacy&pageSize=20");
  assert.equal(route(new URL("https://r/fdc/v1/foods/search?query=a&pageSize=999")), "/fdc/v1/foods/search?query=a&pageSize=50");
  assert.equal(route(new URL("https://r/fdc/v1/food/173944")), "/fdc/v1/food/173944");
  assert.equal(route(new URL("https://r/fdc/v1/foods/search")), null);
  assert.equal(route(new URL("https://r/fdc/v1/food/../../etc")), null);
  assert.equal(route(new URL("https://r/v1/anything")), null);
});

test("rate limit resets each minute", () => {
  for (let i = 0; i < 60; i++) assert.ok(allowed("1.2.3.4", 0));
  assert.equal(allowed("1.2.3.4", 0), false);
  assert.ok(allowed("1.2.3.4", 60_000));
});

test("adds the key server-side and hides upstream errors", async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url, key: init.headers["X-Api-Key"] }; return new Response('{"foods":[]}', { status: 200 }); };
  const ok = await worker.fetch(new Request("https://r/fdc/v1/foods/search?query=oats"), { USDA_KEY: "secret" }, null);
  assert.equal(ok.status, 200);
  assert.equal(seen.key, "secret");
  assert.ok(seen.url.startsWith("https://api.nal.usda.gov/fdc/v1/foods/search?query=oats"));
  globalThis.fetch = async () => new Response('{"error":{"message":"key abc invalid"}}', { status: 403 });
  const bad = await worker.fetch(new Request("https://r/fdc/v1/food/1", { headers: { "cf-connecting-ip": "9.9.9.9" } }), { USDA_KEY: "secret" }, null);
  assert.equal(bad.status, 502);
  assert.ok(!(await bad.text()).includes("abc"));
  const nokey = await worker.fetch(new Request("https://r/fdc/v1/food/1"), {}, null);
  assert.equal(nokey.status, 503);
  const post = await worker.fetch(new Request("https://r/fdc/v1/food/1", { method: "POST" }), { USDA_KEY: "k" }, null);
  assert.equal(post.status, 405);
});
