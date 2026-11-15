# Sapling USDA relay

A tiny Cloudflare Worker so people using Sapling get lab-verified USDA food data without their own API key.

* Forwards only `GET /fdc/v1/foods/search` (query, dataType, pageSize ≤ 50, pageNumber) and `GET /fdc/v1/food/{id}`.
* Adds the owner's key on the server (secret `USDA_KEY`); the app never sees it.
* Caches responses at the edge for 7 days and limits each visitor to 60 requests a minute.
* Doesn't pass USDA error bodies through, and stores nothing about who searched.

```bash
npx wrangler deploy
npx wrangler secret put USDA_KEY      # paste your api.data.gov key
node --test                           # unit tests
```

The app uses the relay when no personal key is set (Profile → Help & feedback → Advanced shows which is in use).
