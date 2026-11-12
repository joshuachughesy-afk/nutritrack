# 🌱 NutriTrack (Python)

A local-first calorie, macro and micronutrient tracker with water, supplements, smart reminders and a garden that
grows with your consistency, written entirely in **Python** with [Flet](https://flet.dev). One codebase runs as a
desktop app, a web app, and a native **Android / iOS** app.

Research behind the design: [`docs/research.md`](docs/research.md)

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install "flet[all]==1.1.2" flet-notifications==1.1.2 flet-charts==1.1.2 flet-camera==1.1.2 zxing-cpp pillow pytest python-barcode
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

## Design

* **3D low-poly trees.** `core/render3d.py` is a small renderer in pure Python with Pillow: real meshes (jittered
  icosphere canopies, tapered trunks, stacked cones for pines, blossoms and fruit) on a floating grass island,
  flat-shaded with a key light and sky fill, painted back to front and supersampled. Six species × six growth stages.
  Drag your tree sideways on Today or Garden to turn it on its turntable. Pre-rendered PNGs in `src/assets/trees/` are
  used if Pillow isn't available on a device.
* **Seasons.** Trees and islands follow the real season (Northern/Southern hemisphere, or "always summer" in Profile →
  Appearance): fresh greens, blossom and flowers in spring; orange/red/gold canopies, falling leaves and golden grass in
  autumn; bare branches, snow-covered islands and snow on evergreens in winter.
* **Your forest in 3D.** Progress → Garden shows every daily tree from the last 8 weeks on one landscape (a row per
  week). Drag to orbit, or tap **Fly around** for a full flight around it.
* **Motion.** Cards fade and rise in, staggered, when a screen opens. Progress bars, the gradient calorie ring and the
  water level animate from their previous value when you log something. When your tree reaches a new stage it pops,
  spins a full turn and throws confetti, with haptic feedback on phones.
* **Look.** Plus Jakarta Sans (SIL OFL), a leaf-green palette with a warm off-white light theme and a deep-forest dark
  theme (System / Light / Dark in Profile → Appearance), softly shadowed cards, a sky-gradient tree card and shimmer
  placeholders while online searches load.

## Editing what you logged

Tap any food on Today to change its amount, unit or meal (or delete it). The editor starts from what you logged, and
recognises clean serving multiples ("172 g" opens as "1 breast"). Quick adds open as an editable quick add.

## Online food data

* **Open Food Facts**: free, no key. Brand search and barcodes. Crowd-sourced, so check odd values against the label.
* **USDA FoodData Central**: lab-measured whole foods with full micronutrients. The shared `DEMO_KEY` is rate-limited,
  so get a free key at <https://api.data.gov/signup/> and paste it in **Profile → Food databases**.

Barcode photos are decoded on the device with `zxing-cpp`. If a phone build doesn't include it, the scanner falls back
to typing the barcode number.

## Tests

```bash
pytest -q
```

* `tests/test_parity.py`: about 950 cases checking that the Python port gives **identical** results to the original
  JavaScript app (targets for 2,016 profile/day/creatine combinations, scoring, pacing, streaks and supplement checks).
  The reference values come from `tests/js_reference.mjs`, run against `legacy-web/`.
* `tests/test_store_service.py`: database, carb cycling, creatine water, garden freezing, reminders and backups.
* `tests/test_stage_c.py`: Open Food Facts and USDA parsing (real and API-format fixtures), barcode decoding, weight
  trend, adaptive TDEE recovering a known burn rate even with ±1 kg water noise, and the service functions.
* `tests/test_ui_build.py`: every screen builds against a real database.

## Python rebuild stages

| Stage | Scope | Status |
|---|---|---|
| **A. Core + logging** | All nutrition science, training database, foods, supplements, pacing, garden scoring and reminder rules ported to tested Python; SQLite store; Today screen (date nav, training/rest toggle, calorie ring, carb-first macro bars, meals with copy-yesterday, micronutrients with the supplement share), Add-food sheet (search, recents, servings or grams, live preview, quick add), custom foods, Profile with onboarding, carb-cycling table and training recommendations | ✅ Done |
| **B. Water, supplements, pace, reminders, garden** | Water card (35 ml/kg + training + creatine, with breakdown); supplement checklist on Today with "due" flags; Supplements screen (stack, pause/edit/remove, timing tips, upper-limit and iron/calcium conflict checks, daily totals, 15 templates, editor with creatine field); pace check with "expected by now" markers and evening micronutrient gaps; **OS-scheduled notifications** through `flet-notifications` on Android/iOS/macOS/Windows (daily supplement reminders with a **Mark taken** action, live check-ins, water nudges; re-synced on every change), with an in-app reminder loop on web and Linux; reminder settings and test; tree card with growth tips and streak; Garden screen (level, stats, 8-week forest, seed picker, scoring rules); backup export and import | ✅ Done |
| **C. Extended data** | Online food search: **Open Food Facts** (branded foods, no key; picking a result fetches the full product) and **USDA FoodData Central** (lab-measured whole foods; add your free key in Profile → Food databases); online picks are saved for offline use and recents. **Barcode scanning**: camera capture or a photo decoded with zxing-cpp, or type the number. **Progress → Trends**: 7/30/90-day ranges, weight log with scale-vs-trend chart, calories-vs-target chart, macro/water/supplement averages, micronutrient coverage with consistently-low flags. **Adaptive TDEE**: intake minus the least-squares weight slope × 7,700 kcal/kg, blended with the formula by confidence and capped at ±25%; optional switch; profile weight follows your trend | ✅ Done |

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
  online.py                      Open Food Facts + USDA clients and parsers
  barcode.py                     Barcode decoding from photos (zxing-cpp)
  trends.py                      Weight trend, adaptive TDEE, period summaries
  render3d.py                    Low-poly 3D tree renderer (Pillow)
src/nutritrack/store.py          SQLite storage
src/nutritrack/service.py        App logic shared by the screens
src/nutritrack/ui/               Flet screens (today, add_food, foods, profile, supps, garden, trends)
  theme.py · motion.py           Design system; animation, haptics and confetti
  tree_view.py · forest_view.py  Interactive 3D tree and 3D forest
  notify.py                      Reminders
src/assets/                      Fonts (Plus Jakarta Sans) and pre-rendered trees
tests/                           pytest suite
legacy-web/                      Original HTML/JS app (reference)
```

*Not medical advice. Set targets with a clinician if you're pregnant, have a medical condition, or take medications.*
