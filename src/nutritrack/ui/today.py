"""Today: greeting, your 3D tree, calories & macros, pace, water, supplements, meals and micronutrients."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import TYPE_CHECKING

import flet as ft
import flet.canvas as cv

from ..core.garden import STAGES, TREE_DAY, growth_tips, stage_for
from ..core.nutrition import MACROS, MICROS, fmt, micro_status
from ..core.pacing import compute_pace
from ..service import pretty_date, shift, today_key
from . import add_food, motion
from . import theme as th
from .tree_view import TreeView

if TYPE_CHECKING:
    from .app import App

MEALS = [("breakfast", "Breakfast", ft.Icons.EGG_ALT_OUTLINED), ("lunch", "Lunch", ft.Icons.LUNCH_DINING_OUTLINED),
         ("dinner", "Dinner", ft.Icons.DINNER_DINING_OUTLINED), ("snacks", "Snacks", ft.Icons.COOKIE_OUTLINED)]


def build(app: "App") -> list[ft.Control]:
    svc, key = app.svc, app.date
    t = svc.targets_for(key)
    tot = svc.totals(key)
    controls: list[ft.Control] = [_header(app), _day_type(app, t)]
    tree = _tree_card(app)
    if tree:
        controls.append(tree)
    controls.append(_summary(app, t, tot.total))
    if key == today_key():
        controls.append(_pace(app, t, tot))
    controls.append(ft.ResponsiveRow([ft.Container(_water(app, t, tot), col={"xs": 12, "md": 6}),
                                      ft.Container(_supp_checklist(app), col={"xs": 12, "md": 6})], spacing=16, run_spacing=16))
    controls += [_meal(app, m, label, icon) for m, label, icon in MEALS]
    controls.append(_micros(t, tot))
    return controls


# ---------- header ----------
def _greeting() -> str:
    h = datetime.now().hour
    return "Good morning" if 4 <= h < 12 else "Good afternoon" if h < 17 else "Good evening"


def _header(app: "App") -> ft.Control:
    def move(d):
        motion.haptic("select")
        app.date = shift(app.date, d)
        app.render()

    is_today = app.date == today_key()
    sub = date.fromisoformat(app.date).strftime("%A, %d %B")
    title = _greeting() if is_today else pretty_date(app.date)
    nav = ft.Row([
        ft.IconButton(ft.Icons.CHEVRON_LEFT_ROUNDED, on_click=lambda _: move(-1), tooltip="Previous day",
                      style=ft.ButtonStyle(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)),
        ft.IconButton(ft.Icons.CHEVRON_RIGHT_ROUNDED, on_click=lambda _: move(1), tooltip="Next day",
                      style=ft.ButtonStyle(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)),
    ], spacing=6)
    left = [th.muted(sub.upper() if is_today else sub, 12, font_family=th.FONT_SEMI), th.title(title, 26)]
    if not is_today:
        left.append(ft.TextButton("Back to today", icon=ft.Icons.TODAY, on_click=lambda _: app.go("today", today_key()),
                                  style=ft.ButtonStyle(padding=0)))
    return ft.Row([ft.Column(left, spacing=0, expand=True), nav], vertical_alignment=ft.CrossAxisAlignment.START)


def _day_type(app: "App", t) -> ft.Control:
    def change(e):
        motion.haptic("select")
        app.store.set_day(app.date, day_type=list(e.control.selected)[0])
        app.render()

    seg = ft.SegmentedButton(
        segments=[ft.Segment(value="training", label=ft.Text("Training day"), icon=ft.Icon(ft.Icons.FITNESS_CENTER)),
                  ft.Segment(value="rest", label=ft.Text("Rest day"), icon=ft.Icon(ft.Icons.SELF_IMPROVEMENT))],
        selected=[t.day_type], on_change=change, show_selected_icon=False, expand=True)
    items: list[ft.Control] = [ft.Row([seg])]
    if t.cycling:
        items.append(th.muted(("Extra carbs today to fuel your session." if t.day_type == "training"
                               else "Lighter carbs today. Your weekly average still matches your target."), 12,
                              text_align=ft.TextAlign.CENTER))
    return ft.Column(items, spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER)


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

    grew = False
    if is_today:
        for msg in svc.check_growth(key, stage):
            grew = True
            app.celebrate(msg, big="level" in msg.lower())

    tree = TreeView(svc.species_for(key), stage, size=210, grew=grew, on_tap=lambda _: app.go("garden"),
                    season=svc.season(key))
    track = ft.Row([ft.Container(height=7, expand=True, border_radius=99,
                                 bgcolor=th.ACCENT_SOFT if score >= lo else ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE),
                                 animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT))
                    for lo, _, _ in STAGES[1:]], spacing=5)
    info: list[ft.Control] = [
        ft.Row([ft.Column([th.muted("TODAY'S TREE" if is_today else "THIS DAY'S TREE", 11, font_family=th.FONT_SEMI),
                           ft.Text(STAGES[stage][1], size=20, font_family=th.FONT_BOLD)], spacing=0, expand=True),
                ft.Text(spans=[ft.TextSpan(str(score), ft.TextStyle(size=34, font_family=th.FONT_BOLD)),
                               ft.TextSpan(" /100", ft.TextStyle(size=13, color=th.MUTED))])],
               vertical_alignment=ft.CrossAxisAlignment.END),
        track,
    ]
    if is_today:
        info.append(th.muted(f"{nxt[0] - score} more points to grow into a {nxt[1].lower()}." if nxt else STAGES[stage][2], 12))
        _, h = svc.history()
        pills = [th.pill(ft.Icons.LOCAL_FIRE_DEPARTMENT, f"{h.streak}-day streak", th.FIRE)]
        if h.shields:
            pills.append(ft.Container(th.pill(ft.Icons.SHIELD, f"{h.shields} shield{'s' if h.shields > 1 else ''}", "#4c7cf0"),
                                      tooltip="Each shield covers one missed day"))
        info.append(ft.Row(pills, spacing=8, wrap=True))
        scheduled, taken = svc.dose_counts(key)
        tips = growth_tips(ds, t, tot.total, tot.water_ml, scheduled, taken, svc.gaps(key, 2), svc.water_fmt)
        if tips:
            info.append(th.muted("GROW IT", 11, font_family=th.FONT_SEMI))
        for tip in tips:
            info.append(ft.Row([th.chip(f"+{round(tip.gain)}", th.ACCENT), ft.Text(tip.text, size=12.5, expand=True)],
                               spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
    else:
        info.append(th.muted("Final tree for this day." + (" Counted as a tree day." if score >= TREE_DAY else ""), 12))

    sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])
    return th.card(ft.ResponsiveRow([
        ft.Container(tree.control, col={"xs": 12, "sm": 5}, alignment=ft.Alignment.CENTER),
        ft.Container(ft.Column(info, spacing=8), col={"xs": 12, "sm": 7}),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER), gradient=sky, padding=16)


# ---------- calories & macros ----------
def _ring(app: "App", eaten: float, target: float, size: int = 150) -> ft.Control:
    frac = min(eaten / target, 1.0) if target else 0.0
    over = eaten > target * 1.05
    stroke = 14
    start = motion.start_value(f"ring:{app.date}", frac)
    colors = ["#e0473f", "#f2622e"] if over else ["#5fbf86", th.ACCENT, "#5fbf86"]
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
                        th.muted("kcal left" if remaining >= 0 else "kcal over", 12)],
                       spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
    return ft.Stack([canvas, ft.Container(center, width=size, height=size, alignment=ft.Alignment.CENTER)],
                    width=size, height=size)


def _summary(app: "App", t, tot) -> ft.Control:
    stats = ft.Column([
        ft.Column([th.muted("EATEN", 11, font_family=th.FONT_SEMI), th.display(fmt(tot["kcal"]), 22)], spacing=0),
        ft.Column([th.muted("TARGET", 11, font_family=th.FONT_SEMI), th.display(fmt(t.kcal), 22)], spacing=0),
        ft.Column([th.muted("BURN (TDEE)", 11, font_family=th.FONT_SEMI), ft.Text(f"{t.tdee:,}", size=15)], spacing=0),
    ], spacing=8)
    order = [MACROS[1], MACROS[0], MACROS[2]] if t.training.carb_first else list(MACROS)
    macros = []
    for key, label, _ in order:
        target = t.macro(key)
        pct = tot[key] / target if target else 0
        left = target - tot[key]
        macros.append(ft.Column([
            ft.Row([th.dot(th.MACRO_COLORS[key]), ft.Text(label, size=14, font_family=th.FONT_SEMI)], spacing=6),
            ft.Text(spans=[ft.TextSpan(fmt(tot[key]), ft.TextStyle(size=16, font_family=th.FONT_BOLD)),
                           ft.TextSpan(f" / {target} g", ft.TextStyle(size=12, color=th.MUTED))]),
            th.bar(pct, th.MACRO_COLORS[key], height=9, key=f"macro:{app.date}:{key}"),
            th.muted(f"{fmt(-left)} g over" if pct > 1.1 else f"{fmt(max(0, left))} g left", 11),
        ], spacing=5, expand=True))
    tr = t.training
    badge = ft.Row([th.chip(f"{tr.name} · {tr.emphasis}", th.emphasis_color(tr.emphasis)),
                    th.muted(f"C {t.gkg['carbs']:.1f} · P {t.gkg['protein']:.1f} · F {t.gkg['fat']:.1f} g/kg", 12)],
                   wrap=True, spacing=8)
    return th.card(ft.Row([_ring(app, tot["kcal"], t.kcal), stats], spacing=26, alignment=ft.MainAxisAlignment.CENTER),
                   ft.Row(macros, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START), badge, spacing=18)


# ---------- meals ----------
def _meal(app: "App", meal: str, label: str, icon) -> ft.Control:
    entries = [e for e in app.store.entries(app.date) if e["meal"] == meal]
    kcal = sum(e["n"]["kcal"] for e in entries)

    def remove(eid):
        motion.haptic("light")
        app.store.remove_entry(eid)
        app.render()

    rows: list[ft.Control] = []
    for e in entries:
        n = e["n"]
        rows.append(ft.Container(ft.Row([
            ft.Column([ft.Text(e["name"], size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, font_family=th.FONT_SEMI),
                       th.muted(f"{e['amount_label']} · P {fmt(n['protein'])} · C {fmt(n['carbs'])} · F {fmt(n['fat'])}", 12)],
                      spacing=1, expand=True),
            ft.Text(fmt(n["kcal"]), size=15, font_family=th.FONT_BOLD),
            ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip=f"Remove {e['name']}", on_click=lambda _, i=e["id"]: remove(i)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.only(left=12, top=6, bottom=6),
            border_radius=14, bgcolor=ft.Colors.SURFACE_CONTAINER, ink=True, tooltip="Tap to edit",
            on_click=lambda _, e=e: (motion.haptic("select"), add_food.open_sheet(app, meal, edit=e))))

    actions: list[ft.Control] = [ft.FilledTonalButton("Add food", icon=ft.Icons.ADD_ROUNDED,
                                                      on_click=lambda _: (motion.haptic("light"), add_food.open_sheet(app, meal)))]
    yesterday = [e for e in app.store.entries(shift(app.date, -1)) if e["meal"] == meal]
    if not entries and yesterday:
        def copy(_):
            motion.haptic("medium")
            for e in yesterday:
                app.store.add_entry(app.date, meal, e["name"], e["n"], food_id=e["food_id"], grams=e["grams"],
                                    amount_label=e["amount_label"])
            app.render()
        actions.append(ft.TextButton("Copy yesterday", icon=ft.Icons.REPLAY_ROUNDED, on_click=copy))

    return th.card(th.heading(label, th.display(f"{fmt(kcal)} kcal", 14, color=th.MUTED), icon=icon),
                   *rows, ft.Row(actions, wrap=True), spacing=8)


# ---------- micronutrients ----------
def _micros(t, tot) -> ft.Control:
    rows = []
    for m in MICROS:
        target = t.micros[m.key]
        pct, status = micro_status(m, target, tot.total[m.key], tot.supps[m.key])
        color = th.STATUS_COLORS[status]
        food_pct = min(tot.food[m.key] / target.target, 1) if target.target else 0
        supp_pct = max(0.0, min(pct, 1) - food_pct)
        items: list[ft.Control] = [
            ft.Row([ft.Text(m.label, size=13, font_family=th.FONT_SEMI, expand=True),
                    th.muted(f"{fmt(tot.total[m.key])} / {fmt(target.target)} {m.unit}{' limit' if m.limit else ''}", 12),
                    ft.Text(f"{round(pct * 100)}%", size=12, font_family=th.FONT_BOLD, color=color, width=44,
                            text_align=ft.TextAlign.RIGHT)], spacing=6),
            th.bar(food_pct, color, extra=supp_pct, key=f"micro:{m.key}"),
        ]
        if status == "over" and not m.limit:
            scope = " from supplements" if m.ul_scope == "supplement" else ""
            items.append(ft.Text(f"Above the {fmt(target.ul)} {m.unit} upper limit{scope}", size=11, color=color))
        rows.append(ft.Container(ft.Column(items, spacing=5), col={"xs": 12, "sm": 6}))
    legend = ft.Row([th.chip("under 50%", th.STATUS_COLORS["low"]), th.chip("50–99%", th.STATUS_COLORS["mid"]),
                     th.chip("met", th.STATUS_COLORS["met"]), th.chip("above limit", th.STATUS_COLORS["over"]),
                     th.chip("lighter = from supplements", th.STATUS_COLORS["none"])], wrap=True, spacing=6)
    return th.card(th.heading("Micronutrients", th.muted("vs. your DRI targets", 12), icon=ft.Icons.SPA_OUTLINED),
                   ft.ResponsiveRow(rows, spacing=18, run_spacing=14), legend, spacing=14)


# ---------- pace ----------
def _pace(app: "App", t, tot) -> ft.Control:
    now = datetime.now()
    sched = app.store.schedule()
    rows = compute_pace(t, tot.total, tot.water_ml, sched, now.hour * 60 + now.minute)
    label = {"early": "early", "behind": "behind pace", "on": "on pace", "ahead": "ahead"}
    items: list[ft.Control] = [th.heading("Pace check", th.muted(f"expected by {now.strftime('%H:%M')}", 12),
                                          icon=ft.Icons.TIMER_OUTLINED)]
    for r in rows:
        status = "ahead" if r.status == "ahead" and not r.ahead_ok else ("on" if r.status == "ahead" else r.status)
        show = (lambda v: app.svc.water_fmt(v)) if r.unit == "ml" else (lambda v, u=r.unit: f"{fmt(v)}{'' if u == 'kcal' else ' g'}")
        marker_left = max(0.0, min(1.0, r.share))
        items.append(ft.Column([
            ft.Row([ft.Text(r.label, size=13, font_family=th.FONT_SEMI, width=72),
                    th.muted(f"{show(r.actual)} · expected ~{show(r.expected)}", 12, expand=True),
                    th.chip(label[r.status], th.STATUS_COLORS[status])]),
            ft.Stack([
                ft.Container(th.bar(r.actual / r.target if r.target else 0, th.MACRO_COLORS[r.key], key=f"pace:{r.key}"),
                             top=4, left=0, right=0),
                ft.Row([ft.Container(expand=max(1, int(marker_left * 1000))),
                        ft.Container(width=3, height=16, bgcolor=ft.Colors.ON_SURFACE, border_radius=2),
                        ft.Container(expand=max(1, int((1 - marker_left) * 1000)))], spacing=0),
            ], height=16),
        ], spacing=4))
    if key_gaps := (app.svc.gaps(app.date, 3) if now.hour * 60 + now.minute >= _to_min(sched["dinner"]) - 60 else []):
        items.append(ft.Text("Close today's gaps", size=13, font_family=th.FONT_SEMI))
        for g in key_gaps:
            foods = " · ".join(f"{n} ({sv}, +{round(p * 100)}%)" for n, sv, p in g.foods)
            items.append(ft.Text(spans=[ft.TextSpan(f"{g.micro.label} {round(g.pct * 100)}%: ", ft.TextStyle(font_family=th.FONT_SEMI)),
                                        ft.TextSpan(foods)], size=12))
    if not app.store.reminders()["enabled"]:
        items.append(ft.Container(ft.Row([ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED, size=18, color=th.ACCENT),
                                          ft.Text("Get check-ins, water nudges and supplement reminders.", size=12, expand=True),
                                          ft.TextButton("Turn on", on_click=lambda _: app.go("profile"))]),
                                  bgcolor=ft.Colors.with_opacity(0.08, th.ACCENT), border_radius=14,
                                  padding=ft.Padding.only(left=12)))
    return th.card(*items)


def _to_min(hhmm: str) -> int:
    h, _, m = hhmm.partition(":")
    return int(h) * 60 + int(m or 0)


# ---------- water ----------
def _water(app: "App", t, tot) -> ft.Control:
    total, target = tot.water_ml, t.water_ml
    pct = total / target if target else 0
    imperial = app.svc.imperial
    amounts = [(8, 237), (16, 473), (24, 710)] if imperial else [(250, 250), (500, 500), (750, 750)]
    glass_h = 96

    def add(ml):
        motion.haptic("light")
        app.store.add_water(app.date, ml)
        app.render()

    def undo(_):
        app.store.undo_water(app.date)
        app.render()

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
        ft.Container(ft.Column([th.display(f"{round(pct * 100)}%", 26),
                                th.muted(f"{app.svc.water_fmt(total)} of {app.svc.water_fmt(target)}", 11)],
                               spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                     alignment=ft.Alignment.CENTER, left=0, right=0, top=0, bottom=0),
    ], height=glass_h)
    buttons: list[ft.Control] = [ft.FilledTonalButton(f"+{lbl} {'oz' if imperial else 'ml'}", on_click=lambda _, m=ml: add(m))
                                 for lbl, ml in amounts]
    if app.store.water_count(app.date):
        buttons.append(ft.TextButton("Undo", on_click=undo))
    w = t.water
    parts = [("Baseline (35 ml/kg)", w.base, "")]
    if w.training:
        parts.append(("Training day", w.training, "+"))
    if w.creatine:
        parts.append((f"Creatine ({fmt(w.creatine_g)} g/day{', loading' if w.creatine_g >= 15 else ''})", w.creatine, "+"))
    breakdown = [ft.Row([th.muted(lbl, 12, expand=True), ft.Text(f"{sign}{app.svc.water_fmt(v)}", size=12)]) for lbl, v, sign in parts]
    extra = [th.muted(f"During exercise, drink about {'14–27 oz' if imperial else '400–800 ml'} per hour, more in heat.", 11)] \
        if t.day_type == "training" else []
    return th.card(th.heading("Water", icon=ft.Icons.WATER_DROP, icon_color=th.MACRO_COLORS["water"]),
                   glass, ft.Row(buttons, wrap=True, spacing=6), *breakdown, *extra, spacing=10)


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
            ft.Checkbox(value=done, on_change=lambda _, s=s, t=time: toggle(s, t), shape=ft.CircleBorder()),
            ft.Column([ft.Text(s.name, size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, font_family=th.FONT_SEMI,
                               style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if done else None,
                               color=th.MUTED if done else None),
                       th.muted(f"{time} · {s.dose_label}{' · with food' if s.with_food else ''}", 11)], spacing=0, expand=True),
            *([th.chip("due", th.STATUS_COLORS["low"])] if due else []),
        ], spacing=4), opacity=0.7 if done else 1, animate_opacity=300))
    done_count = sum(1 for s, t in doses if (s.id, t) in taken)
    progress = th.bar(done_count / len(doses), th.ACCENT, height=6, key=f"supps:{app.date}") if doses else ft.Container()
    return th.card(
        th.heading("Supplements", icon=ft.Icons.MEDICATION, trailing=th.muted(f"{done_count} / {len(doses)} taken", 12)),
        progress,
        *(rows or [th.muted("No supplements yet. Add your stack and they'll count toward your micronutrients.", 12)]),
        ft.FilledTonalButton("Manage stack" if doses else "Add supplements", icon=ft.Icons.MEDICATION,
                             on_click=lambda _: app.go("supps")), spacing=6)
