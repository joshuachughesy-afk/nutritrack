# 🌱 NutriTrack

A local-first calorie, macro and micronutrient tracker with water, supplements, smart reminders and a
growth-based progression system. No account, no ads, and your data stays on your device.

Research behind the design: [`docs/research.md`](docs/research.md)

## Run it

```bash
cd nutritrack && python3 -m http.server 8765
```

Then open http://localhost:8765. To use it on your phone, host the folder on any static host (for example GitHub Pages) and choose "Add to Home Screen". ES modules need http://; double-clicking `index.html` won't work.

## Build stages

| Stage | Scope | Status |
|---|---|---|
| **1. Foundation** | Profile → BMR/TDEE/macro targets (Mifflin-St Jeor), age- and sex-specific DRI micronutrient targets, 42-food USDA reference list, meal logging with servings or grams, quick add, recents, copy yesterday's meal, custom foods, calorie ring, macro and micronutrient bars, export/import | ✅ Done |
| **1b. Training types** | Database of 10 training types with g/kg macro ranges (ACSM/ISSN); carb-first allocation for hybrid and endurance; load-based placement within ranges; warnings, fueling tips and a comparison table | ✅ Done |
| **2. Water + supplements** | Water tracking (35 ml/kg, more on training days scaled by load); 15 supplement templates plus custom ones from your label; up to 3 dose times each; daily checklist with "due" flags; taken doses count toward micronutrients (striped bar segment); upper-limit checks with supplement-only limits applied correctly; iron + calcium/zinc timing conflicts; timing tips for each supplement; training and rest days with carb cycling that keeps the weekly calorie average unchanged | ✅ Done |
| **3. Notifications + pacing** | Pace engine built on your meal times (expected share of the day's food and water by now); Pace check card with bars and an "expected by now" marker; evening micronutrient gaps with foods that fill them; reminders for supplement doses, water when behind pace, and up to 3 daily check-ins (each sent once, never repeated); system notifications through a service worker, with stacked in-app banners as fallback; installable PWA (manifest, icons, offline app shell) | ✅ Done |
| **4. Progression** | Seeds → sprouts → trees that grow from daily goals met (macros, micros, water, supplements); a garden/forest view; streaks with forgiveness | ⏳ Next |
| **5. Extended data** | Open Food Facts / USDA search, barcode scanning, weekly trends, adaptive TDEE from weight trend | Planned |

## Structure

```
index.html         App shell
css/styles.css     Styles (light/dark, mobile-first)
js/app.js          Views, modal, events
js/nutrition.js    Targets, DRIs, nutrient math
js/training.js     Training-type macro database (g/kg ranges, tips)
js/supplements.js  Supplement templates, timing advice, stack analysis
js/pacing.js       Time-of-day pace engine, micronutrient gap suggestions
js/reminders.js    Reminder rules (pure) + notification delivery
sw.js              Service worker (offline shell, notification clicks)
js/foods.js        Built-in reference foods (per 100 g)
js/store.js        localStorage persistence
docs/research.md   Competitive research and pros/cons
```

*Not medical advice. Set targets with a clinician if you're pregnant, have a medical condition, or take medications.*
