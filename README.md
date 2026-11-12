# 🌱 NutriTrack (Python)

A local-first calorie, macro and micronutrient tracker with water, supplements, smart reminders and a garden that
grows with your consistency, written entirely in **Python** with [Flet](https://flet.dev). One codebase runs as a
desktop app, a web app, and a native **Android / iOS** app.

Research behind the design: [`docs/research.md`](docs/research.md)

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "flet[all]==1.1.2" flet-notifications==1.1.2 flet-charts==1.1.2 pytest
flet run src/main.py          # desktop window
flet run --web src/main.py    # in your browser
```

## Put it on your phone

```bash
flet build apk     # Android (needs Flutter SDK + Android SDK; flet installs what it can)
flet build ipa     # iPhone (needs a Mac with Xcode)
```

During development you can also scan a QR code with the **Flet app** on your phone: run `flet run --android` or
`flet run --ios` and open the app on the same Wi-Fi network.

Your data lives in a SQLite file in the app's private storage (`~/.nutritrack/nutritrack.db` on desktop), which you
can analyse directly with pandas or any SQLite tool.

## Tests

```bash
pytest -q
```

* `tests/test_parity.py`: about 950 cases checking that the Python port gives **identical** results to the original
  JavaScript app (targets for 2,016 profile/day/creatine combinations, scoring, pacing, streaks and supplement checks).
  The reference values come from `tests/js_reference.mjs`, run against `legacy-web/`.
* `tests/test_store_service.py`: database, carb cycling, creatine water, garden freezing, reminders and backups.
* `tests/test_ui_build.py`: every screen builds against a real database.

## Python rebuild stages

| Stage | Scope | Status |
|---|---|---|
| **A. Core + logging** | All nutrition science, training database, foods, supplements, pacing, garden scoring and reminder rules ported to tested Python; SQLite store; Today screen (date nav, training/rest toggle, calorie ring, carb-first macro bars, meals with copy-yesterday, micronutrients with the supplement share), Add-food sheet (search, recents, servings or grams, live preview, quick add), custom foods, Profile with onboarding, carb-cycling table and training recommendations | ✅ Done |
| **B. Water, supplements, pace, reminders, garden** | Water card (35 ml/kg + training + creatine, with breakdown); supplement checklist on Today with "due" flags; Supplements screen (stack, pause/edit/remove, timing tips, upper-limit and iron/calcium conflict checks, daily totals, 15 templates, editor with creatine field); pace check with "expected by now" markers and evening micronutrient gaps; **OS-scheduled notifications** through `flet-notifications` on Android/iOS/macOS/Windows (daily supplement reminders with a **Mark taken** action, live check-ins, water nudges; re-synced on every change), with an in-app reminder loop on web and Linux; reminder settings and test; tree card with growth tips and streak; Garden screen (level, stats, 8-week forest, seed picker, scoring rules); backup export and import | ✅ Done |
| **C. Extended data** | Online food search (Open Food Facts / USDA), barcode scanning, weekly trends with `flet-charts`, weight log and adaptive TDEE | ⏳ Next |

The Python app now does everything the original HTML/JavaScript version did. That version is kept in
[`legacy-web/`](legacy-web/) only because the parity tests generate their reference values from it.

## Structure

```
src/main.py                      Entry point (flet run / flet build)
src/nutritrack/core/             Pure logic, no UI. Everything here is unit-tested
  nutrition.py                   Profile, BMR/TDEE, macro allocation, DRIs, carb cycling, hydration
  training.py                    Training-type macro database (g/kg ranges, tips, sources)
  foods.py                       Built-in reference foods (per 100 g, USDA)
  supplements.py                 Templates, timing advice, creatine, stack analysis
  pacing.py                      Time-of-day pace engine, micronutrient gap suggestions
  garden.py                      Day scoring, streaks/shields, levels, species
  trees.py                       Tree SVG drawings
  reminders.py                   Reminder rules + OS notification plan
src/nutritrack/store.py          SQLite storage
src/nutritrack/service.py        App logic shared by the screens
src/nutritrack/ui/               Flet screens (today, add_food, foods, profile, supps, garden) + notify.py (reminders)
tests/                           pytest suite
legacy-web/                      Original HTML/JS app (reference)
```

*Not medical advice. Set targets with a clinician if you're pregnant, have a medical condition, or take medications.*
