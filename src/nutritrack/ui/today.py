"""Today: how am I doing and what do I eat next?

Order: header → calories & macros (with an "expected by now" pin and one coaching line) → your tree → meals →
water and supplements → a short nutrient summary (full list on demand) → morning weigh-in.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import TYPE_CHECKING

import flet as ft
import flet.canvas as cv

from ..core.garden import STAGES, TREE_DAY, growth_tips, stage_for
from ..core.nutrition import MACROS, MICROS, fmt, micro_status
from ..core.pacing import compute_pace, pace_summary, to_min
from ..service import pretty_date, shift, today_key
from . import add_food, motion
from . import components as cx
from . import theme as th
from .day_review import save_entries_as_plan
from .tree_view import TreeView

if TYPE_CHECKING:
    from .app import App

MEALS = [("breakfast", "Breakfast", ft.Icons.EGG_ALT_OUTLINED), ("lunch", "Lunch", ft.Icons.LUNCH_DINING_OUTLINED),
         ("dinner", "Dinner", ft.Icons.DINNER_DINING_OUTLINED), ("snacks", "Snacks", ft.Icons.COOKIE_OUTLINED)]


def build(app: "App") -> list[ft.Control]:
    svc, key = app.svc, app.date
    t = svc.targets_for(key)
    tot = svc.totals(key)
    controls: list[ft.Control] = [_header(app), _day_type(app, t), _summary(app, t, tot)]
    tree = _tree_card(app)
    if tree:
        controls.append(tree)
    controls += [_meal(app, m, label, icon) for m, label, icon in MEALS]
    controls.append(ft.ResponsiveRow([ft.Container(_water(app, t, tot), col={"xs": 12, "md": 6}),
                                      ft.Container(_supp_checklist(app), col={"xs": 12, "md": 6})], spacing=16, run_spacing=16))
    controls.append(_micros(app, t, tot))
    if key == today_key() and app.store.day(key).get("weight_kg") is None:
        controls.append(_weigh_in(app))
    return controls


# ---------- header ----------
def _greeting(hour: int | None = None) -> str:
    h = datetime.now().hour if hour is None else hour
    if 4 <= h < 12:
        return "Good morning"
    return "Good afternoon" if 12 <= h < 17 else "Good evening"  # 17:00 until 03:59


def _header(app: "App") -> ft.Control:
    def move(d):
        motion.haptic("select")
        app.date = shift(app.date, d)
        app.render()

    def picked(e):
        v = e.control.value
        if v:
            app.go("today", v.date().isoformat() if hasattr(v, "date") else v.isoformat())

    def pick_date(_):
        app.page.show_dialog(ft.DatePicker(value=date.fromisoformat(app.date), first_date=date(2020, 1, 1),
                                           last_date=date.fromisoformat(today_key()), on_change=picked))

    is_today = app.date == today_key()
    sub = date.fromisoformat(app.date).strftime("%A, %d %B")
    title = _greeting() if is_today else pretty_date(app.date)
    nav = ft.Row([
        ft.IconButton(ft.Icons.CHEVRON_LEFT_ROUNDED, on_click=lambda _: move(-1), tooltip="Previous day",
                      style=ft.ButtonStyle(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)),
        ft.IconButton(ft.Icons.CHEVRON_RIGHT_ROUNDED, on_click=lambda _: move(1), tooltip="Next day", disabled=is_today,
                      style=ft.ButtonStyle(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)),
    ], spacing=6)
    date_line = ft.Container(ft.Row([th.muted(sub.upper() if is_today else sub, th.T.CAPTION, font_family=th.FONT_SEMI),
                                     ft.Icon(ft.Icons.EXPAND_MORE, size=16, color=th.MUTED)], spacing=2, tight=True),
                             on_click=pick_date, tooltip="Pick a date")
    left: list[ft.Control] = [date_line, th.title(title, 26)]
    if not is_today:
        left.append(ft.Container(th.chip("Back to today", th.ACCENT), on_click=lambda _: app.go("today", today_key()),
                                 padding=ft.Padding.only(top=4)))
    return ft.Row([ft.Column(left, spacing=0, expand=True), nav], vertical_alignment=ft.CrossAxisAlignment.START)


def _day_type(app: "App", t) -> ft.Control:
    def change(v):
        motion.haptic("select")
        app.store.set_day(app.date, day_type=v)
        app.render()

    return cx.tabs([("training", "Training day"), ("rest", "Rest day")], t.day_type, change)


# ---------- calories, macros and pace ----------
def _ring(app: "App", eaten: float, target: float, size: int = 148) -> ft.Control:
    frac = min(eaten / target, 1.0) if target else 0.0
    over = eaten > target * 1.05
    stroke = 14
    start = motion.start_value(f"ring:{app.date}", frac)
    colors = ["#e0473f", "#f2622e"] if over else [th.ACCENT_SOFT, th.ACCENT, th.ACCENT_SOFT]
    paint = ft.Paint(stroke_width=stroke, style=ft.PaintingStyle.STROKE, stroke_cap=ft.StrokeCap.ROUND,
                     gradient=ft.SweepGradient(colors=colors, center=ft.Alignment.CENTER, start_angle=0,
                                               end_angle=2 * math.pi, rotation=-math.pi / 2))
    box = (stroke / 2, stroke / 2, size - stroke, size - stroke)
    value = cv.Arc(*box, start_angle=-math.pi / 2, sweep_angle=max(0.001, start * 2 * math.pi), paint=paint)
    canvas = cv.Canvas(shapes=[
        cv.Arc(*box, start_angle=0, sweep_angle=2 * math.pi,
               paint=ft.Paint(stroke_width=stroke, style=ft.PaintingStyle.STROKE,
                              color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))),
        value], width=size, height=size)
    if abs(start - frac) > 0.001:
        def setter(v):
            value.sweep_angle = max(0.001, v * 2 * math.pi)
        motion.task(lambda: motion.tween(setter, start, frac, 750, canvas.update))
    remaining = target - eaten
    center = ft.Column([th.display(fmt(abs(remaining)), 30),
                        th.muted("kcal left" if remaining >= 0 else "kcal over", th.T.CAPTION)],
                       spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
    return ft.Stack([canvas, ft.Container(center, width=size, height=size, alignment=ft.Alignment.CENTER)],
                    width=size, height=size)


def _pace_rows(app: "App", t, tot):
    """Pace rows when they mean something (today, after the first meal), else None."""
    if app.date != today_key():
        return None, ""
    now = datetime.now()
    sched = app.store.schedule()
    m = now.hour * 60 + now.minute
    if m < to_min(sched["breakfast"]) + 30 or m > to_min(sched["sleep"]):
        return None, f"Pace check starts after breakfast ({sched['breakfast']})." if m < to_min(sched["breakfast"]) + 30 else ""
    rows = compute_pace(t, tot.total, tot.water_ml, sched, m)
    if all(r.status == "early" for r in rows):
        return None, f"Pace check starts after breakfast ({sched['breakfast']})."
    return {r.key: r for r in rows}, ""


def _summary(app: "App", t, tot) -> ft.Control:
    total = tot.total
    pace, early_msg = _pace_rows(app, t, tot)
    order = [MACROS[1], MACROS[0], MACROS[2]] if t.training.carb_first else list(MACROS)
    macros = []
    for key, label, _ in order:
        target = t.macro(key)
        pct = total[key] / target if target else 0
        left = target - total[key]
        r = pace.get(key) if pace else None
        macros.append(ft.Column([
            ft.Row([th.dot(th.MACRO_COLORS[key]), ft.Text(label, size=th.T.LABEL, font_family=th.FONT_SEMI)], spacing=6),
            ft.Text(spans=[ft.TextSpan(fmt(total[key]), ft.TextStyle(size=16, font_family=th.FONT_BOLD)),
                           ft.TextSpan(f" / {target} g", ft.TextStyle(size=th.T.CAPTION, color=th.MUTED))]),
            th.bar(pct, th.MACRO_COLORS[key], height=9, key=f"macro:{app.date}:{key}",
                   marker=r.share if r and r.status != "early" else None),
            th.muted(f"{fmt(-left)} g over" if pct > 1.1 else f"{fmt(max(0, left))} g left", th.T.CAPTION),
        ], spacing=5, expand=True))

    tr = t.training
    day = "Training day" if t.day_type == "training" else "Rest day"
    side = ft.Column([
        ft.Column([th.muted("Eaten", th.T.CAPTION, font_family=th.FONT_SEMI), th.display(fmt(total["kcal"]), 22)], spacing=0),
        ft.Column([th.muted("Target", th.T.CAPTION, font_family=th.FONT_SEMI), th.display(f"{t.kcal:,}", 22)], spacing=0),
        th.muted(day + (" · more carbs" if t.cycling and t.day_type == "training" else
                        " · lighter carbs" if t.cycling else ""), th.T.CAPTION),
    ], spacing=8)

    # One coaching line instead of a second table of bars.
    if pace:
        on, text = pace_summary(list(pace.values()), app.svc.water_fmt)
        coach = cx.note(text, "good" if on else "info", icon=ft.Icons.CHECK_CIRCLE_OUTLINE if on else ft.Icons.TIMER_OUTLINED)
    elif early_msg:
        coach = cx.note(early_msg, "info", icon=ft.Icons.WB_TWILIGHT)
    else:
        coach = None

    def explain(_):
        cx.info_sheet(
            app.page, f"{tr.name} · {tr.emphasis.lower()}",
            th.muted(f"Your daily burn is about {t.tdee:,} kcal. Your target is {t.kcal:,} kcal today"
                     + (" (training days get more carbs; rest days fewer, with the same weekly total)." if t.cycling else "."),
                     th.T.LABEL),
            ft.Text(f"Per kg of body weight: carbs {t.gkg['carbs']:.1f} g · protein {t.gkg['protein']:.1f} g · "
                    f"fat {t.gkg['fat']:.1f} g", size=th.T.LABEL),
            *[ft.Row([ft.Text("•"), ft.Text(tip, size=th.T.LABEL, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START)
              for tip in tr.tips],
            th.muted("The black pin on each bar shows where you'd expect to be by now, based on your meal times.", th.T.CAPTION))

    plan = ft.Container(ft.Row([ft.Icon(ft.Icons.BOLT, size=16, color=th.ink(th.emphasis_color(tr.emphasis))),
                                ft.Text(f"{tr.name.split(' (')[0]} · {tr.emphasis.lower()}", size=th.T.CAPTION,
                                        font_family=th.FONT_SEMI, color=th.ink(th.emphasis_color(tr.emphasis))),
                                ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=th.MUTED)], spacing=4, tight=True),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5), border_radius=th.R.PILL,
                        bgcolor=ft.Colors.with_opacity(0.14, th.emphasis_color(tr.emphasis)), on_click=explain,
                        tooltip="Why these targets?")
    return th.card(ft.Row([_ring(app, total["kcal"], t.kcal), side], spacing=22, alignment=ft.MainAxisAlignment.CENTER),
                   ft.Row(macros, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
                   *([coach] if coach else []), ft.Row([plan]), spacing=16)


# ---------- the tree ----------
def _tree_card(app: "App") -> ft.Control | None:
    svc, key = app.svc, app.date
    is_today = key == today_key()
    frozen = app.store.day(key)["garden"]
    if not is_today and not frozen and not svc.has_log(key):
        return None
    ds, t, tot = svc.live_score(key)
    score = frozen["score"] if frozen else ds.score
    stage = stage_for(score)
    nxt = STAGES[stage + 1] if stage + 1 < len(STAGES) else None
    grew = bool(getattr(app, "grew", False)) and is_today

    tree = TreeView(svc.species_for(key), stage, size=150, grew=grew, on_tap=lambda _: app.go("garden"),
                    season=svc.season(key))
    track = ft.Row([ft.Container(height=6, expand=True, border_radius=99,
                                 bgcolor=th.ACCENT_SOFT if score >= lo else ft.Colors.with_opacity(0.22, ft.Colors.ON_SURFACE),
                                 animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT))
                    for lo, _, _ in STAGES[1:]], spacing=4)
    now_h = datetime.now().hour
    if is_today and score < 40 and now_h < 11:
        status = "Just waking up. Breakfast gets it growing."
    elif is_today:
        status = f"{nxt[0] - score} points to a {nxt[1].lower()}" if nxt else STAGES[stage][2]
    else:
        status = "Final tree for this day" + (" · a full tree day" if score >= TREE_DAY else "")
    info: list[ft.Control] = [
        ft.Row([ft.Column([th.muted("Today's tree" if is_today else "This day's tree", th.T.CAPTION, font_family=th.FONT_SEMI),
                           ft.Text(STAGES[stage][1], size=th.T.HEADLINE + 2, font_family=th.FONT_BOLD)], spacing=0, expand=True),
                ft.Text(spans=[ft.TextSpan(str(score), ft.TextStyle(size=28, font_family=th.FONT_BOLD)),
                               ft.TextSpan("/100", ft.TextStyle(size=th.T.CAPTION, color=th.MUTED))])],
               vertical_alignment=ft.CrossAxisAlignment.END),
        track, th.muted(status, th.T.CAPTION),
    ]
    if is_today:
        _, h = svc.history()

        def shield_info(_):
            cx.info_sheet(app.page, "Streaks and shields",
                          th.muted(f"A day of {TREE_DAY}+ points grows a full tree and keeps your streak going. Every 7 days "
                                   "in a row earns a shield (you can hold 2). A shield covers one missed day, so a busy "
                                   "day doesn't wipe out your streak.", th.T.LABEL))
        pills = [ft.Container(th.pill(ft.Icons.LOCAL_FIRE_DEPARTMENT, f"{h.streak} days", th.FIRE), on_click=shield_info,
                              tooltip=f"{h.streak}-day streak")]
        if h.shields:
            pills.append(ft.Container(th.pill(ft.Icons.SHIELD, str(h.shields), th.SHIELD),
                                      on_click=shield_info, tooltip=f"{h.shields} shield{'s' if h.shields > 1 else ''}: "
                                                                    "each covers one missed day"))
        info.append(ft.Row(pills, spacing=6, wrap=True, run_spacing=6))
    sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])
    items: list[ft.Control] = [ft.Row([ft.Container(tree.control, width=140), ft.Column(info, spacing=8, expand=True)],
                                      spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
    if is_today:
        scheduled, taken = svc.dose_counts(key)
        tips = growth_tips(ds, t, tot.total, tot.water_ml, scheduled, taken, svc.gaps(key, 2), svc.water_fmt)
        # Calories and water already have their own cards, so lead with the tip they don't show.
        tips = sorted(tips, key=lambda tp: (("kcal" in tp.text or "water" in tp.text.lower()), -tp.gain))[:2]
        for tip in tips:
            items.append(ft.Row([th.chip(f"+{round(tip.gain)}", th.ACCENT), ft.Text(tip.text, size=th.T.LABEL, expand=True)],
                                spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
    return th.card(*items, gradient=sky, padding=14, spacing=8)


# ---------- meals ----------
def _meal(app: "App", meal: str, label: str, icon) -> ft.Control:
    entries = [e for e in app.store.entries(app.date) if e["meal"] == meal]
    kcal = sum(e["n"]["kcal"] for e in entries)

    def remove(entry):
        motion.haptic("light")
        app.store.remove_entry(entry["id"])
        app.render()
        app.toast(f"Removed {entry['name']}", undo=lambda: app.store.restore_entry(entry))

    def open_add(_):
        motion.haptic("light")
        add_food.open_sheet(app, meal)

    yesterday = [e for e in app.store.entries(shift(app.date, -1)) if e["meal"] == meal]

    def copy(_):
        motion.haptic("medium")
        ids = [app.store.add_entry(app.date, meal, e["name"], e["n"], food_id=e["food_id"], grams=e["grams"],
                                   amount_label=e["amount_label"]) for e in yesterday]
        app.render()
        app.toast(f"Copied {len(ids)} item{'s' if len(ids) != 1 else ''} from yesterday",
                  undo=lambda: [app.store.remove_entry(i) for i in ids if i])

    if not entries:  # an empty meal is one compact row, not a whole card
        actions: list[ft.Control] = []
        if yesterday:
            actions.append(ft.TextButton("Copy yesterday", icon=ft.Icons.REPLAY_ROUNDED, on_click=copy))
        actions.append(ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip=f"Add to {label.lower()}", on_click=open_add,
                                     style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.14, th.ACCENT)),
                                     icon_color=th.ACCENT))
        return ft.Container(ft.Row([
            ft.Container(ft.Icon(icon, size=18, color=th.MUTED), padding=6),
            ft.Column([ft.Text(label, size=th.T.BODY, font_family=th.FONT_SEMI),
                       th.muted("Nothing yet", th.T.CAPTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=0, expand=True),
            *actions], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.only(left=10, right=6, top=6, bottom=6), border_radius=th.R.LG,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), on_click=open_add, ink=True)

    rows: list[ft.Control] = []
    for e in entries:
        n = e["n"]
        row = ft.Container(ft.Row([
            ft.Column([ft.Text(e["name"], size=th.T.BODY - 1, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                               font_family=th.FONT_SEMI),
                       th.muted(f"{e['amount_label']} · P {round(n['protein'])} · C {round(n['carbs'])} · F {round(n['fat'])}",
                                th.T.CAPTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=1, expand=True),
            ft.Text(fmt(n["kcal"]), size=th.T.BODY, font_family=th.FONT_BOLD),
            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=18, color=th.MUTED),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            padding=ft.Padding.only(left=12, right=6, top=8, bottom=8), border_radius=th.R.MD,
            bgcolor=ft.Colors.SURFACE_CONTAINER, ink=True,
            on_click=lambda _, e=e: (motion.haptic("select"), add_food.open_sheet(app, meal, edit=e)))
        swipe_bg = ft.Container(ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE, color=ft.Colors.WHITE), ft.Text("Remove", color=ft.Colors.WHITE)],
                                       alignment=ft.MainAxisAlignment.END), bgcolor=th.STATUS_COLORS["over"], border_radius=th.R.MD,
                                padding=ft.Padding.only(right=16))
        rows.append(ft.Dismissible(content=row, key=e["id"], dismiss_direction=ft.DismissDirection.END_TO_START,
                                   background=swipe_bg, secondary_background=swipe_bg,
                                   on_dismiss=lambda _, e=e: remove(e)))

    actions = [ft.FilledTonalButton("Add food", icon=ft.Icons.ADD_ROUNDED, on_click=open_add),
               ft.TextButton("Save meal", icon=ft.Icons.BOOKMARK_ADD_OUTLINED,
                             on_click=lambda _: save_entries_as_plan(app, entries, "meal", f"My {label.lower()}"))]
    return th.card(th.heading(label, f"{fmt(kcal)} kcal", icon=icon), *rows, ft.Row(actions, wrap=True, spacing=4), spacing=8)


# ---------- micronutrients ----------
def _micro_rows(t, tot) -> list[tuple]:
    out = []
    for m in MICROS:
        target = t.micros[m.key]
        pct, status = micro_status(m, target, tot.total[m.key], tot.supps[m.key])
        out.append((m, target, pct, status))
    return out


def micro_row(m, target, pct, status, tot) -> ft.Control:
    """One nutrient: bar capped at 100% (food solid, supplements lighter), a check when covered, a warning above the
    safe maximum. The percentage text is never colour-only."""
    color = {"met": th.ACCENT_SOFT, "ok-limit": th.ACCENT_SOFT, "over": "#e08a2b"}.get(status, th.MACRO_COLORS["protein"])
    food_pct = min(tot.food[m.key] / target.target, 1) if target.target else 0
    supp_pct = max(0.0, min(pct, 1) - food_pct)
    icon = {"met": ft.Icons.CHECK_CIRCLE, "ok-limit": ft.Icons.CHECK_CIRCLE, "over": ft.Icons.WARNING_AMBER_ROUNDED}.get(status)
    value = f"{fmt(tot.total[m.key])} of {fmt(target.target)} {m.unit}{' max' if m.limit else ''}"
    if not m.limit:
        value += f" · {round(pct * 100)}%"
    note = None
    if status == "over" and not m.limit:
        note = f"Above the {fmt(target.ul)} {m.unit} safe max{' from supplements' if m.ul_scope == 'supplement' else ''}"
    return cx.metric_row(m.label, value, food_pct, color, extra=supp_pct, note=note, note_color="#e08a2b",
                         key=f"micro:{m.key}", icon=icon, icon_color=th.ink(color) if icon else None, height=7)


def _micros(app: "App", t, tot) -> ft.Control:
    rows = _micro_rows(t, tot)
    scored = [r for r in rows if not r[0].limit]
    covered = sum(1 for _, _, pct, _ in scored if pct >= 1)
    over = [r for r in rows if r[3] == "over"]
    low = sorted([r for r in scored if r[2] < 1], key=lambda r: r[2])[:3]
    gaps = {g.micro.key: g for g in app.svc.gaps(app.date, 3)}

    items: list[ft.Control] = []
    for m, target, pct, status in over + low:
        items.append(micro_row(m, target, pct, status, tot))
        g = gaps.get(m.key)
        if g and g.foods:
            items.append(th.muted("Try: " + ", ".join(n.split(",")[0].lower() for n, _, _ in g.foods), th.T.CAPTION))
    if not items:
        items.append(cx.note("Every vitamin and mineral is covered today.", "good"))

    def see_all(_):
        cx.info_sheet(app.page, "Vitamins & minerals",
                      th.muted("Solid bar = from food, lighter = from supplements. ✓ means covered; ⚠ means above the "
                               "safe maximum.", th.T.CAPTION),
                      *[micro_row(m, target, pct, status, tot) for m, target, pct, status in rows])

    return th.card(th.heading("Vitamins & minerals", f"{covered} of {len(scored)} covered", icon=ft.Icons.SPA_OUTLINED),
                   *items, ft.TextButton(f"See all {len(rows)}", icon=ft.Icons.LIST_ROUNDED, on_click=see_all), spacing=10)


# ---------- water ----------
def _water(app: "App", t, tot) -> ft.Control:
    total, target = tot.water_ml, t.water_ml
    pct = total / target if target else 0
    imperial = app.svc.imperial
    amounts = [(8, 237), (16, 473), (24, 710)] if imperial else [(250, 250), (500, 500), (750, 750)]
    glass_h = 100

    def add(ml, lbl):
        motion.haptic("light")
        app.store.add_water(app.date, ml)
        app.render()
        app.toast(f"Added {lbl} of water", undo=lambda: app.store.undo_water(app.date))

    level_start = motion.start_value(f"water:{app.date}", min(pct, 1))
    level = ft.Container(gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                                    colors=["#7cc8f2", "#2f8fd6"]),
                         border_radius=16, left=0, right=0, bottom=0, height=glass_h * level_start,
                         animate=ft.Animation(800, ft.AnimationCurve.EASE_OUT_CUBIC))
    if abs(level_start - min(pct, 1)) > 0.001:
        motion.after(lambda: setattr(level, "height", glass_h * min(pct, 1)))
    glass = ft.Stack([
        ft.Container(bgcolor=ft.Colors.with_opacity(0.10, th.MACRO_COLORS["water"]), border_radius=16,
                     left=0, right=0, top=0, bottom=0),
        level,
        ft.Container(ft.Column([th.display(app.svc.water_fmt(total), 24),
                                th.muted(f"of {app.svc.water_fmt(target)} · {round(pct * 100)}%", th.T.CAPTION)],
                               spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                     alignment=ft.Alignment.TOP_CENTER, padding=ft.Padding.only(top=12), left=0, right=0, top=0, bottom=0),
    ], height=glass_h)
    unit = "oz" if imperial else "ml"
    buttons = [ft.FilledTonalButton(f"+{lbl}", on_click=lambda _, m=ml, lb=f"{lbl} {unit}": add(m, lb), expand=True,
                                    tooltip=f"Add {lbl} {unit}")
               for lbl, ml in amounts]
    w = t.water
    parts = [("Base for your body weight", w.base)]
    if w.training:
        parts.append(("Training day", w.training))
    if w.creatine:
        parts.append((f"Creatine ({fmt(w.creatine_g)} g a day{', loading' if w.creatine_g >= 15 else ''})", w.creatine))
    reason = " + ".join([app.svc.water_fmt(w.base)] + [f"{app.svc.water_fmt(v)} {lbl.split(' (')[0].lower()}"
                                                      for lbl, v in parts[1:]])

    def why(_):
        cx.info_sheet(app.page, "Your water target",
                      *[ft.Row([ft.Text(lbl, size=th.T.LABEL, expand=True), ft.Text(app.svc.water_fmt(v), size=th.T.LABEL)])
                        for lbl, v in parts],
                      th.muted("The base is 35 ml per kg of body weight. Training adds more by how hard you train, and "
                               "creatine pulls water into muscle, so it adds some too.", th.T.CAPTION),
                      *([th.muted(f"During exercise, drink about {'14–27 oz' if imperial else '400–800 ml'} an hour, "
                                  "more in the heat.", th.T.CAPTION)] if t.day_type == "training" else []))

    return th.card(th.heading("Water", ft.IconButton(ft.Icons.INFO_OUTLINE, icon_size=18, tooltip="Why this much?",
                                                     on_click=why),
                              icon=ft.Icons.WATER_DROP, icon_color=th.MACRO_COLORS["water"]),
                   glass, ft.Row(buttons, spacing=6), th.muted(reason if len(parts) > 1 else "", th.T.CAPTION)
                   if len(parts) > 1 else ft.Container(), spacing=10)


# ---------- supplements ----------
def _supp_checklist(app: "App") -> ft.Control:
    supps = [s for s in app.store.supplements() if s.active]
    taken = {(d["supp_id"], d["time"]) for d in app.store.doses(app.date)}
    doses = sorted(((s, t) for s in supps for t in s.times), key=lambda x: x[1])
    now = datetime.now().strftime("%H:%M")
    is_today = app.date == today_key()

    def toggle(s, time):
        motion.haptic("light")
        app.store.toggle_dose(app.date, s, time)
        app.render()

    rows: list[ft.Control] = []
    for s, time in doses:
        done = (s.id, time) in taken
        due = is_today and not done and time <= now
        rows.append(ft.Container(ft.Row([
            ft.Icon(ft.Icons.CHECK_CIRCLE if done else ft.Icons.RADIO_BUTTON_UNCHECKED, size=24,
                    color=th.ACCENT if done else ft.Colors.OUTLINE),
            ft.Column([ft.Text(s.name, size=th.T.BODY - 1, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                               font_family=th.FONT_SEMI, color=th.MUTED if done else None),
                       th.muted(f"{time} · {s.dose_label}{' · with food' if s.with_food else ''}", th.T.CAPTION,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=0, expand=True),
            *([th.chip("Due", "#e08a2b")] if due else [th.muted("Taken", th.T.CAPTION)] if done else []),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=6, vertical=8), border_radius=th.R.MD, ink=True,
            on_click=lambda _, s=s, t=time: toggle(s, t), tooltip="Mark taken" if not done else "Mark not taken"))
    done_count = sum(1 for s, t in doses if (s.id, t) in taken)
    if not doses:
        return th.card(th.heading("Supplements", icon=ft.Icons.MEDICATION),
                       cx.empty_state(ft.Icons.MEDICATION_OUTLINED, "Add what you take and it counts toward your "
                                      "vitamins and minerals, with reminders at the right time.",
                                      ft.FilledTonalButton("Add your stack", icon=ft.Icons.ADD, on_click=lambda _: app.go("supps"))))
    return th.card(
        th.heading("Supplements", f"{done_count} of {len(doses)} taken", icon=ft.Icons.MEDICATION),
        th.bar(done_count / len(doses), th.ACCENT, height=6, key=f"supps:{app.date}"),
        ft.Column(rows, spacing=0), spacing=6)


# ---------- weight ----------
def _weigh_in(app: "App") -> ft.Control:
    imperial = app.svc.imperial
    field = th.num_field("Weight", None, suffix="lb" if imperial else "kg", expand=True,
                         hint_text="Morning, before eating")

    def save(_):
        v = th.parse_num(field.value)
        kg = v / 2.20462 if imperial else v
        if not 30 <= kg <= 300:
            field.error = "Check the number"
            app.page.update()
            return
        app.svc.log_weight(app.date, round(kg, 2))
        motion.haptic("light")
        app.render()
        app.toast("Weight logged. Your trend is in Progress → Trends.")

    field.on_submit = save
    return th.card(th.heading("Morning weigh-in", "optional", icon=ft.Icons.MONITOR_WEIGHT_OUTLINED),
                   th.muted("A few weigh-ins a week let NutriTrack learn your real daily burn.", th.T.CAPTION),
                   ft.Row([field, ft.FilledTonalButton("Log", on_click=save)], spacing=8), spacing=10)
