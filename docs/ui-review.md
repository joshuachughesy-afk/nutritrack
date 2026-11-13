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

## Left for later, with reasons

* **Rename the app** (suggested: Grove, Canopy). This is the owner's call, and it needs a trademark and App Store check.
* **Ship a USDA key or a small relay** before any public release. A consumer shouldn't have to get an API key. The field stays under Advanced for now.
* **OS back gesture** (Android back, iOS swipe-back). This needs a `page.views` router. The in-app back arrow, Esc and Alt+← work today.
* **Per-card updates instead of full re-renders.** This is a performance refactor and has no visible change. The current renders are cached and cheap (see the README).
* **Weekly recap and share card, a longer unlock ladder** (decorations, wildlife, seasonal seeds), **more distinct growth stages, and typed or photo logging.** These are new features rather than UI fixes.
