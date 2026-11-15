# UI review and overhaul (v2.2)

Three reviewers looked at all 41 screens before this overhaul:

* a **senior engineer** (design system, interaction, accessibility, code structure),
* a **marketing graduate** (first impression, positioning, copy, retention, App Store readiness), and
* a **first-time user** from outside the field (a busy teacher who once tried MyFitnessPal).

Where all three agreed, it went to the top of the list.

## What they agreed on

| Finding | Engineer | Marketing | Outsider |
|---|:-:|:-:|:-:|
| Setup is one long technical form | ✓ | ✓ | ✓ |
| Jargon everywhere (BMR, TDEE, DRI, g/kg, UL) | ✓ | ✓ | ✓ |
| Today is about 7 screens long; Pace check reads "expected ~0" early in the day | ✓ | ✓ | ✓ |
| The quick-log button covers content | ✓ | ✓ | ✓ |
| Profile shows file paths, logs, README links and an API key field | ✓ | ✓ | ✓ |
| Tables and labels clip on a phone ("Femal e", "Prote", "Upper lim") | ✓ | ✓ | ✓ |
| Food search feels thin; online search is a separate manual step | ✓ | ✓ | ✓ |
| "Calorie target" shows different numbers on different screens | ✓ | ✓ | ✓ |
| "Meal plans" means a weekly plan to most people | | ✓ | ✓ |
| Nutrient colours judge you (orange, yellow, red) and 504% looks like a win | ✓ | ✓ | ✓ |
| The tree, forest, streaks, Copy yesterday and Grow-it tips are the best part | | ✓ | ✓ |

## What changed, section by section

**Foundation**
* **Tokens:** type, spacing and radius scales. Nothing is set below 12 px.
* **Shared components** (`ui/components.py`): stat tile, metric row, empty state, note, back header, tabs, toggle row, day chips, time picker field, info sheet and settings row.
* **Dark mode:** brand green switches to a light tint, so chips and icons stay readable. `th.ink()` makes any status colour text-safe (WCAG AA).
* **Typed UI state** (`ui/state.py`) replaces ad-hoc `App` attributes. Editors and settings pages have a back arrow (Esc or Alt+← on desktop). Switching tabs closes them, so you never come back to a half-finished form. Every new screen or sub-page opens at the top.
* **Screen builders have no side effects.** Growth celebrations and garden finalising run in `App.render()` before the screen is built.

**Onboarding:** a 7-step wizard with the navigation bar hidden.
1. Welcome, with the 3D tree and four value points.
2. What you train for (hybrid first).
3. Hours and training days (day chips) and carb cycling.
4. About you. The fields start empty, nothing is preselected and errors give the valid range.
5. Goal.
6. **Your fuel plan**, the reveal: training-day and rest-day calories, macros and water, with why.
7. Plant your first seed, with a "Keep me on pace" reminders opt-in.

**Today**
* **Order:** calories and macros come first. Each macro bar has an **"expected by now" pin**, and **one coaching line** replaces the five-row Pace card. Before breakfast it says when pacing starts.
* **Tree card:** smaller, with the score, a stage track, a streak pill and a shield pill. Tapping either pill explains it. It shows at most two Grow-it tips, and none on an empty day. In the morning it reads "Just waking up" instead of a failing score.
* **Meals:**
  * Empty meals collapse to one row with **+** and **Copy yesterday**. Copy now has Undo.
  * Entries show whole grams. Tap to edit, swipe to remove; the small ✕ is gone.
  * **Save meal** is a labelled button.
* **Water:** three equal buttons, and Undo moves into the confirmation. One line explains the target (base + training + creatine), with details behind ⓘ.
* **Supplements:**
  * The whole row is the tap target.
  * A tick replaces strikethrough.
  * Each dose shows a "Due" or "Taken" label.
  * An empty stack shows a friendly prompt.
* **Vitamins & minerals:**
  * The card summarises "9 of 13 covered".
  * It shows only what's above the safe maximum, then the three lowest, with foods to try.
  * "See all 14" opens the full list. Bars cap at 100%, with ✓ and ⚠ icons, so meaning isn't colour-only.
* **Morning weigh-in:** a card appears until you've logged today's weight.
* **Header:** tap the date to pick a day, use "Back to today", and the next-day arrow is disabled on today.
* **Quick-log button:** names the **next unlogged meal**, and the screen leaves room so it never covers the last card.

**Add food**
* The header shows the date when you're not logging to today.
* The search field says "Search foods and brands". It no longer shows "Search 45 foods".
* **Online search runs by itself** 0.6 s after you stop typing. Results have badges: **✓ Verified** (USDA) or **Brand label** (Open Food Facts). Lab-verified USDA results are one tap away.
* **Recent foods show your last amount and a ⊕ to re-log it in one tap.**
* **Every add confirms with Undo.**
* The amount screen has ½ / 1 / 1½ / 2 shortcuts and an error for 0.

**Foods**
* **My foods is a searchable list first.** "New food" opens a sub-page editor that can also edit and delete. It warns when the calories don't match the macros.
* **Recipes:** an empty state with a clear call to action, whole-number per-serving tiles, and an overflow menu. The editor is a sub-page with a back arrow.
* **Meal plans → Saved meals**, everywhere. They log to the day you're viewing, not always today.

**Stack** (the "Supps" tab, renamed)
* "Worth a look" turns iron/calcium/zinc timing clashes into **one-tap fixes** ("Move to 13:00").
* Supplements are compact rows with a ⋮ menu (Edit, Pause, Remove). Timing tips appear once, in a collapsible card.
* Daily totals are bars with "% of need". The safe maximum is mentioned only when you're close to it or above it.
* **Add** opens a picker of common supplements (added ones get a ✓) or a custom one. The editor uses **time pickers** and lets you add or remove dose times.

**Progress**
* Garden and Trends share the same header: the title, then the tabs.
* **Garden:**
  * The forest valley comes first (the Today tree isn't repeated).
  * Then the level hero and three stat tiles. Streak and Shields explain themselves when tapped.
  * The calendar:
    * numbers every day and names the months
    * starts at your first logged week
    * has a legend
    * opens the look-back for any past day
  * "How your tree grows" is a friendly checklist in a sheet.
  * The fly button is labelled "Fly around".
* **Trends:**
  * 30 days by default.
  * **"Your real daily burn"** (adaptive TDEE) leads the tab, with a **Use it for my targets** button and a plain explanation.
  * The weight chart fits its data, and the x-axis labels now show.
  * Today's calorie bar is marked "so far".
  * The summary is neutral ("right around your target").
  * Averages use metric rows, and vitamin coverage caps at 100% with ✓.

**Profile**
* Profile is now a menu: a summary card (training-day and rest-day calories) and seven pages.
* The pages are Body & goal, Training, Your targets, Reminders, Appearance, Backup & privacy, and Help & feedback. Each saves on its own, so changing the theme no longer discards an unsaved form.
* **Targets** explain the calorie numbers: resting burn, daily burn, training-day and rest-day targets, and the weekly average. The screens no longer show different calorie numbers without saying why.
* **Reminders** use time pickers and switches.
* **Backup & privacy:**
  * The page leads with "Private by design".
  * **Restoring a backup asks first.**
  * **Erase** is a separate red action that needs you to type ERASE.
* File paths, logs, versions, keyboard shortcuts and the USDA key live under **Help & feedback → Advanced**.

## Follow-up (v2.3): the "left for later" list, done

* **Renamed to Sapling**, with the tagline "Fuel your training. Cover every nutrient. Grow a forest." The Python
  package is still `nutritrack`, so existing data folders and imports keep working.
* **USDA relay** (`relay/`): a Cloudflare Worker that adds the key on the server, caches for a week and rate-limits
  each visitor. The app uses it when there's no personal key. To finish it, deploy it from the Cloudflare dashboard
  (see `relay/README.md`) and set `DEFAULT_RELAY` in `core/online.py` to its address.
* **Native back gesture:** sub-pages are pushed as a second view, so Android back and iOS swipe-back close them.
* **Per-card updates:** water and supplement taps rebuild only the affected Today cards, so the scroll position is kept.
* **Distinct growth stages, a 12-step rewards ladder** drawn into the valley, and two new species.
* **Weekly recap:** shown Sunday evening and Monday, opened by a Sunday 18:00 notification, with a shareable image.
* **Describe it** (typed logging, parsed on the device) and **Photo for later**.

## Bug hunt (v2.3)

An automated crawler pressed every button and changed every input on every screen, sub-page and sheet. A fuzz run
simulated two months of random use, then built every screen for every day. A browser pass watched the console.
Fixed:

* **Bedtime after midnight:** pacing broke (the water curve ran backwards) and pacing switched off after midnight.
* **Left open past midnight:** Today stayed on yesterday.
* **Water Undo** applied to whichever day was on screen, not the day the water was added.
* **Adding a third check-in** silently vanished as a duplicate time.
* **Removing a dose time or check-in twice quickly** crashed.
* **Trends averages and supplement adherence** counted today's unfinished day.
* **Night-time wording** said "Good evening" and "Just waking up" at 2 am.
* **The weigh-in card** couldn't be skipped.
* **Today in the calendar** wasn't highlighted before you'd logged anything.
* **"Try: salmon, salmon"** appeared in the nutrient suggestions.
* **The adaptive-burn message** didn't say it only counts the last 4 weeks.

Known and left alone: in the web preview, `datetime.now()` is the server's clock, not the viewer's. The phone app
runs locally, so it isn't affected.
