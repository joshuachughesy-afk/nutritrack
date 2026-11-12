# Calorie and Nutrition Tracker Research: Source Document

*Compiled 2026-11-12. This is the reference for the design decisions in NutriTrack.*

## 1. How calorie trackers work (the common model)

Almost every tracker uses the same core loop:

1. **Profile → targets.** You enter sex, age, height, weight, activity level and goal. The app estimates your
   Basal Metabolic Rate (usually the **Mifflin‑St Jeor** equation), multiplies it by an activity factor to get
   **TDEE** (Total Daily Energy Expenditure), then adds a deficit or surplus for your goal.
2. **Targets → macro split.** It turns the calorie target into protein, carb and fat grams, either as fixed
   percentages or with protein set per kg of body weight.
3. **Food database → logging.** You search a database (government data such as USDA FoodData Central, branded
   or barcode data, and user-submitted entries), pick a serving and log it to a meal.
4. **Totals vs targets.** The day's totals are compared with your targets, usually as rings or progress bars.
5. **Retention layer.** Streaks, reminders, weekly reports and sometimes adaptive targets that change as your
   weight trend comes in.

## 2. App-by-app breakdown

| App | Best known for | What it does well | Where it falls short |
|---|---|---|---|
| **MyFitnessPal** | Largest food database | Huge database including restaurants and barcodes; many integrations | Many inaccurate or duplicate user-submitted entries (one test reported about ±18% calorie error); free tier cut back in 2024; heavy ads; the 2026 redesign split opinion |
| **Cronometer** | Accuracy and micronutrients | Verified, lab-sourced data (USDA/NCCDB); tracks 80+ nutrients; strong supplement logging; lowest error in reported tests (about ±4%) | Denser, more clinical UI; slower to log; less social or motivating |
| **MacroFactor** | Adaptive targets | Recalculates TDEE from your weight trend; fast logging; no judgment about missed targets | No free tier; more app than casual users need; micronutrient view is secondary |
| **Lose It!** | Simplicity and price | Easiest to start; friendly UI; good streaks and badges | Less precise (reported error about 12–13%); tracks about 35 nutrients; best features behind a paywall |
| **AI or photo loggers** (Cal AI, PlateLens, Welling and others) | Speed | Logging from a photo or plain text removes the biggest friction point | Accuracy depends on portion estimates; hard to check or fix the numbers behind a guess |
| **Water apps** (WaterMinder and others) | Hydration | Simple tap-to-log; timed nudges | Separate app; no link to food or supplements |
| **Supplement or pill reminders** (Medisafe and others) | Adherence | Reliable scheduled reminders | Know nothing about the nutrients in what you take |
| **Forest** (focus app) | Value-based progression | Turns consistency into a growing forest you can see; losing a tree hurts | Not a nutrition app. **The progression model is the takeaway** |

## 3. Cross-cutting findings

**What users say breaks trackers:**
- **Logging friction is the main reason people quit.** Reviews and retention write-ups say that when a meal takes
  more than about 60 seconds to log, dropout rises sharply.
- **Database accuracy.** User-submitted entries have been reported to differ from USDA reference data by 15–30%
  per item. Crowd-sourced size doesn't help if the data is wrong.
- **Ads, upsells and billing surprises** come up often in 1-star reviews.
- **Cluttered UIs** with many entry points and repeated upsell prompts.
- **Fragmentation.** Food, water and supplements usually live in three separate apps, so no one view shows
  whether your *micronutrients* are covered.
- **Shame-based feedback.** Red numbers and "you failed" messages push people away. Neutral, coaching-style
  feedback works better (MacroFactor's stated philosophy).

**What works:**
- Recents, favorites and "copy yesterday's meal", because most people eat the same 20–30 foods.
- Verified nutrient data with full micronutrient coverage (Cronometer).
- Showing *pace*, not just totals: are you on track **for this time of day**?
- Meaningful visual progression (Forest's tree, Apple's rings) and streaks with some forgiveness.

## 4. Pros and cons summary

### Pros to adopt
- ✅ Mifflin‑St Jeor plus activity factor for initial targets (an industry standard backed by evidence)
- ✅ Protein set per kg of body weight (1.6–2.2 g/kg for active people), fat as % of calories, carbs fill the rest
- ✅ Verified reference data (USDA-derived values) over crowd-sourced data
- ✅ Wide micronutrient coverage, compared with official **DRIs** (Dietary Reference Intakes) that adjust for age and sex
- ✅ Supplements count toward micronutrient totals (Cronometer)
- ✅ Recents and copy-meal for fast logging; quick-add for restaurant meals
- ✅ Progress rings and bars you can read at a glance
- ✅ Water tracking and supplement reminders **in the same app**
- ✅ Forest-style growth mechanic: consistency becomes something you can see and lose

### Cons to avoid
- ❌ Ads, paywalls and dark-pattern upsells (NutriTrack is local, free, no account)
- ❌ Crowd-sourced data with no checking
- ❌ Shame-based red or green judgment. Use "below / on pace / above" language instead
- ❌ Burying micronutrients behind a paywall or an extra screen
- ❌ Ignoring upper limits. Supplements can push iron, zinc, vitamin A, vitamin D and others past safe Upper Intake Levels (ULs)
- ❌ Reminders that fire whether or not they're useful. Nudges should depend on your pace

## 5. Expert considerations built into NutriTrack

- **Upper Intake Levels (UL):** some ULs apply only to *supplemental or synthetic* forms (magnesium, folic acid,
  vitamin E, preformed vitamin A). The app applies them to supplement intake, not food, so spinach never
  triggers a false warning.
- **Fiber target:** 14 g per 1,000 kcal (the basis of the IOM AI), so it scales with your calorie target.
- **Sodium** is a *ceiling* (2,300 mg CDRR), not a goal. It's shown as a limit.
- **Calorie floor:** targets never drop below 1,200 kcal (female) or 1,500 kcal (male) without a manual override.
- **Absorption timing for supplements** (Stage 2): iron away from calcium; fat-soluble vitamins (A, D, E, K)
  with a meal; magnesium in the evening.
- **Hydration:** baseline of about 35 ml per kg of body weight, adjustable.
- **Creatine and hydration:** creatine pulls water into muscle cells (about 1–2 kg of extra intracellular water once
  saturated). The ISSN creatine position stand (Kreider et al., 2017) found no evidence that it causes dehydration or
  cramping, but the extra water has to come from somewhere. NutriTrack adds about **+500 ml/day** on a maintenance dose
  (3–5 g) and about **+1 L/day** during a loading phase (15 g/day or more), whenever creatine is in your active stack.
- This app is not medical advice. Anyone with a medical condition, pregnancy or medications should set targets
  with a clinician.

## 6. Macro recommendations by training type

Different training places different demands on fuel. NutriTrack stores these ranges in `js/training.js` (g per kg of
body weight per day) and places you within each range based on your weekly training load.

| Training type | Carbs | Protein | Fat | Emphasis |
|---|---|---|---|---|
| General fitness | 3–5 | 1.2–1.6 | 0.8–1.2 | Balanced |
| Strength / powerlifting | 3–5 | 1.6–2.2 | 0.8–1.2 | Protein-forward |
| Bodybuilding / hypertrophy | 4–6 | 1.8–2.4 | 0.7–1.0 | Protein-forward |
| CrossFit / HIIT / functional | 4–7 | 1.6–2.0 | 0.8–1.0 | Carb-leaning |
| **Hybrid (strength + endurance)** | **5–8** | 1.6–2.0 | 0.8–1.0 | **Carb-forward** |
| Team / field sports | 5–7 | 1.4–1.8 | 0.8–1.0 | Carb-forward |
| Combat sports | 4–6 | 1.6–2.2 | 0.8–1.0 | Balanced |
| Endurance (1–3 h/day) | 6–10 | 1.4–1.8 | 0.8–1.0 | Carb-forward |
| Ultra-endurance (4 h+/day) | 8–12 | 1.6–2.0 | 1.0–1.5 | Carb-forward |
| Low intensity / mobility | 3–5 | 1.2–1.6 | 0.8–1.2 | Balanced |

**How targets are allocated:**
1. Protein comes from the type's range, and moves to the top of it when you are in a deficit.
2. Carbs get first claim on the remaining calories, up to the type's target for your load.
3. Fat takes the rest. It never drops below a health floor (the higher of 0.6 g/kg or 20% of calories) and never
   goes above 35% of calories.
4. If your calorie target can't fit the recommended carbs (common in a deficit), the app tells you rather than
   quietly cutting performance fuel.

**Why hybrid athletes need carbs first:** endurance volume drains muscle glycogen and lifting depends on it being
refilled. Protein above about 2.0 g/kg adds no measurable benefit and takes calories away from carbs.

**Sources:** Thomas, Erdman & Burke, *ACSM/AND/DC Joint Position: Nutrition and Athletic Performance* (2016);
Jäger et al., *ISSN Position Stand: Protein and Exercise* (2017); Kerksick et al., *ISSN Position Stand: Nutrient
Timing* (2017); Helms et al., *Evidence-based recommendations for natural bodybuilding contest preparation* (2014).
Concurrent or hybrid training has no dedicated position stand, so its ranges combine the endurance carb bands with
resistance-training protein guidance.

## 7. Adaptive TDEE (how NutriTrack learns your real burn rate)

Formula estimates such as Mifflin-St Jeor are typically within about ±10% for most people, but can be off by several
hundred kcal for an individual. Once you've logged at least 10 full days and 6 weigh-ins over 2+ weeks, NutriTrack
estimates your real expenditure:

    TDEE ≈ average logged intake − (weight slope kg/day × 7,700 kcal/kg)

* **Least-squares slope, not a smoothed trend.** Smoothing (as in the Hacker's Diet) is great for display but lags real
  change. In testing, a lagging trend under-read a 1.7 kg loss as 0.8 kg and under-estimated TDEE by about 260 kcal. A
  regression line averages out the same ±1–2 kg water noise with no lag.
* **Blended by confidence** (logged days, weigh-ins, span) with the formula, and **capped at ±25%** of it.
* **Only as good as your logging:** days under 1,000 kcal logged are treated as incomplete and ignored.

## Sources

- [Fitia: Best food tracking app (US 2026 comparison)](https://fitia.app/en/learn/article/best-food-tracking-app-us-2026-comparison/)
- [Fitia: Best macro tracker apps 2026](https://fitia.app/learn/article/best-macro-tracker-apps-2026/)
- [Fitia: Best MyFitnessPal alternatives 2026](https://fitia.app/learn/article/best-myfitnesspal-alternatives-2026/)
- [Programming Insider: 10 best macro tracking apps 2026](https://programminginsider.com/10-best-macro-tracking-apps-2026/)
- [SetForSet: MyFitnessPal alternatives](https://www.setforset.com/blogs/news/myfitnesspal-alternatives-8-calorie-trackers-worth-switching-to)
- [Welling: Best calorie tracker apps, reviews and rankings](https://www.welling.ai/articles/best-calorie-tracker-apps-expert-reviews-rankings)
- [Sarasota Magazine: 12 best free calorie tracker apps 2026](https://www.sarasotamagazine.com/advantagepoint/2026/06/12-best-free-daily-calorie-tracker-apps-in-2026-top-picks-for-smarter-nutrition)
- [Nutrola: Calorie tracker retention rates](https://nutrola.app/en/blog/calorie-tracker-retention-rates-how-long-users-stick-with-each-app)
- [Nutrola: I keep quitting calorie tracking](https://nutrola.app/en/blog/i-keep-quitting-calorie-tracking-how-to-stick-with-it)
- [Kimola: Calorie tracking apps through customer feedback analysis](https://kimola.com/blog/understanding-calorie-tracking-and-nutrition-apps-through-customer-feedback-analysis)
- [Unstar: Calorie tracking apps ranked by 1-star reviews 2026](https://unstar.app/fr/blog/calorie-tracking-apps-ranked-1-star-reviews-2026)
- NIH Office of Dietary Supplements, DRI tables (RDA/AI/UL values used in `js/nutrition.js`)
- USDA FoodData Central (reference values for the built-in food list)

> **Caveat:** many 2026 comparison articles are published by competing app makers (Fitia, Welling, Nutrola), and
> the accuracy percentages conflict between sources. Treat the numbers as directional only.
