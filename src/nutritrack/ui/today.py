"""Today: calories, macros, meals and micronutrients for the selected day."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from datetime import datetime

from ..core.garden import STAGES, TREE_DAY, growth_tips, stage_for
from ..core.nutrition import MACROS, MICROS, fmt, micro_status
from ..core.pacing import compute_pace
from ..core.trees import tree_svg
from ..service import pretty_date, shift, today_key
from . import add_food
from . import theme as th

if TYPE_CHECKING:
    from .app import App

MEALS = [("breakfast", "Breakfast"), ("lunch", "Lunch"), ("dinner", "Dinner"), ("snacks", "Snacks")]


def build(app: "App") -> list[ft.Control]:
    svc, key = app.svc, app.date
    t = svc.targets_for(key)
    tot = svc.totals(key)
    controls: list[ft.Control] = [_date_nav(app), _day_type(app, t)]
    if t.cycling:
        controls.append(th.muted(("Training day: extra carbs to fuel the session." if t.day_type == "training"
                                  else "Rest day: carbs drop toward maintenance needs.")
                                 + " Your weekly average still matches your target.", size=12,
                                 text_align=ft.TextAlign.CENTER))
    tree = _tree_card(app)
    if tree:
        controls.append(tree)
    controls.append(_summary(t, tot.total))
    if key == today_key():
        controls.append(_pace(app, t, tot))
    controls += [ft.ResponsiveRow([ft.Container(_water(app, t, tot), col={"xs": 12, "md": 6}),
                                   ft.Container(_supp_checklist(app), col={"xs": 12, "md": 6})], spacing=14, run_spacing=14)]
    controls += [_meal(app, m, label) for m, label in MEALS]
    controls.append(_micros(t, tot))
    return controls


def _date_nav(app: "App") -> ft.Control:
    def move(d):
        app.date = shift(app.date, d)
        app.render()

    return ft.Row([
        ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda _: move(-1), tooltip="Previous day"),
        ft.Text(pretty_date(app.date), size=20, weight=ft.FontWeight.W_700),
        ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda _: move(1), tooltip="Next day"),
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)


def _day_type(app: "App", t) -> ft.Control:
    def change(e):
        app.store.set_day(app.date, day_type=list(e.control.selected)[0])
        app.render()

    return ft.SegmentedButton(
        segments=[ft.Segment(value="training", label=ft.Text("Training day"), icon=ft.Icon(ft.Icons.FITNESS_CENTER)),
                  ft.Segment(value="rest", label=ft.Text("Rest day"), icon=ft.Icon(ft.Icons.HOTEL))],
        selected=[t.day_type], on_change=change, show_selected_icon=False)


def _summary(t, tot) -> ft.Control:
    remaining = t.kcal - tot["kcal"]
    over = tot["kcal"] > t.kcal * 1.05
    ring = ft.Stack([
        ft.ProgressRing(value=min(tot["kcal"] / t.kcal, 1) if t.kcal else 0, stroke_width=11, width=132, height=132,
                        color=th.STATUS_COLORS["over"] if over else th.ACCENT, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        stroke_cap=ft.StrokeCap.ROUND),
        ft.Container(content=ft.Column([
            ft.Text(fmt(abs(remaining)), size=26, weight=ft.FontWeight.W_700),
            th.muted("kcal left" if remaining >= 0 else "kcal over", size=12),
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
            width=132, height=132, alignment=ft.Alignment.CENTER),
    ], width=132, height=132)
    stats = ft.Column([
        ft.Column([th.muted("Eaten", 12), ft.Text(fmt(tot["kcal"]), size=19, weight=ft.FontWeight.W_700)], spacing=0),
        ft.Column([th.muted("Target", 12), ft.Text(fmt(t.kcal), size=19, weight=ft.FontWeight.W_700)], spacing=0),
    ], spacing=8)

    order = [MACROS[1], MACROS[0], MACROS[2]] if t.training.carb_first else list(MACROS)
    macros = []
    for key, label, _ in order:
        target = t.macro(key)
        pct = tot[key] / target if target else 0
        left = target - tot[key]
        macros.append(ft.Column([
            ft.Row([th.dot(th.MACRO_COLORS[key]), ft.Text(label, weight=ft.FontWeight.W_600, size=14)], spacing=6),
            th.muted(f"{fmt(tot[key])} / {target} g", 12),
            th.bar(pct, th.MACRO_COLORS[key]),
            th.muted(f"{fmt(-left)} g over" if pct > 1.1 else f"{fmt(max(0, left))} g left", 11),
        ], spacing=4, expand=True))
    tr = t.training
    badge = ft.Row([th.chip(f"{tr.name} · {tr.emphasis}", th.emphasis_color(tr.emphasis)),
                    th.muted(f"C {t.gkg['carbs']:.1f} · P {t.gkg['protein']:.1f} · F {t.gkg['fat']:.1f} g/kg", 12)],
                   wrap=True, spacing=8)
    return th.card(ft.Row([ring, stats], spacing=22, alignment=ft.MainAxisAlignment.CENTER),
                   ft.Row(macros, spacing=12, vertical_alignment=ft.CrossAxisAlignment.START), badge, spacing=14)


def _meal(app: "App", meal: str, label: str) -> ft.Control:
    entries = [e for e in app.store.entries(app.date) if e["meal"] == meal]
    kcal = sum(e["n"]["kcal"] for e in entries)

    def remove(eid):
        app.store.remove_entry(eid)
        app.render()

    rows: list[ft.Control] = []
    for e in entries:
        n = e["n"]
        rows.append(ft.Row([
            ft.Column([ft.Text(e["name"], size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                       th.muted(f"{e['amount_label']} · P {fmt(n['protein'])} · C {fmt(n['carbs'])} · F {fmt(n['fat'])}", 12)],
                      spacing=1, expand=True),
            ft.Text(fmt(n["kcal"]), size=14),
            ft.IconButton(ft.Icons.CLOSE, icon_size=18, tooltip=f"Remove {e['name']}", on_click=lambda _, i=e["id"]: remove(i)),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

    actions: list[ft.Control] = [ft.FilledTonalButton("Add food", icon=ft.Icons.ADD,
                                                      on_click=lambda _: add_food.open_sheet(app, meal))]
    yesterday = [e for e in app.store.entries(shift(app.date, -1)) if e["meal"] == meal]
    if not entries and yesterday:
        def copy(_):
            for e in yesterday:
                app.store.add_entry(app.date, meal, e["name"], e["n"], food_id=e["food_id"], grams=e["grams"],
                                    amount_label=e["amount_label"])
            app.render()
        actions.append(ft.TextButton("Copy yesterday", icon=ft.Icons.REPLAY, on_click=copy))

    return th.card(th.heading(label, th.muted(f"{fmt(kcal)} kcal", 13)), *rows, ft.Row(actions, wrap=True), spacing=6)


def _micros(t, tot) -> ft.Control:
    rows = []
    for m in MICROS:
        target = t.micros[m.key]
        pct, status = micro_status(m, target, tot.total[m.key], tot.supps[m.key])
        color = th.STATUS_COLORS[status]
        food_pct = min(tot.food[m.key] / target.target, 1) if target.target else 0
        supp_pct = max(0.0, min(pct, 1) - food_pct)
        items: list[ft.Control] = [
            ft.Row([ft.Text(m.label, size=13, weight=ft.FontWeight.W_600, expand=True),
                    th.muted(f"{fmt(tot.total[m.key])} / {fmt(target.target)} {m.unit}{' limit' if m.limit else ''}", 12),
                    ft.Text(f"{round(pct * 100)}%", size=12, weight=ft.FontWeight.W_700, color=color, width=44,
                            text_align=ft.TextAlign.RIGHT)], spacing=6),
            th.bar(food_pct, color, extra=supp_pct),
        ]
        if status == "over" and not m.limit:
            scope = " from supplements" if m.ul_scope == "supplement" else ""
            items.append(ft.Text(f"Above the {fmt(target.ul)} {m.unit} upper limit{scope}", size=11, color=color))
        rows.append(ft.Container(ft.Column(items, spacing=4), col={"xs": 12, "sm": 6}))
    legend = ft.Row([th.chip("under 50%", th.STATUS_COLORS["low"]), th.chip("50–99%", th.STATUS_COLORS["mid"]),
                     th.chip("met", th.STATUS_COLORS["met"]), th.chip("above limit", th.STATUS_COLORS["over"]),
                     th.chip("lighter = from supplements", th.STATUS_COLORS["none"])], wrap=True, spacing=6)
    return th.card(th.heading("Micronutrients", th.muted("vs. your DRI targets", 12)),
                   ft.ResponsiveRow(rows, spacing=18, run_spacing=12), legend, spacing=12)


# ---------- Stage B cards ----------
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
    info: list[ft.Control] = [
        ft.Row([ft.Text(STAGES[stage][1], size=18, weight=ft.FontWeight.W_700, expand=True),
                ft.Text(spans=[ft.TextSpan(str(score), ft.TextStyle(size=24, weight=ft.FontWeight.W_700)),
                               ft.TextSpan("/100", ft.TextStyle(size=13, color=th.MUTED))])]),
        ft.Row([ft.Container(height=6, expand=True, border_radius=99,
                             bgcolor=th.STATUS_COLORS["met"] if score >= lo else ft.Colors.SURFACE_CONTAINER_HIGHEST)
                for lo, _, _ in STAGES[1:]], spacing=4),
    ]
    if is_today:
        info.append(th.muted(f"{nxt[0] - score} more points to grow into a {nxt[1].lower()}." if nxt else STAGES[stage][2], 12))
        _, h = svc.history()
        streak = [th.icon_text(ft.Icons.LOCAL_FIRE_DEPARTMENT, f"{h.streak}-day streak", "#e8590c", bold=True)]
        if h.shields:
            streak.append(ft.Container(th.icon_text(ft.Icons.SHIELD, str(h.shields), "#3d7be0"),
                                       tooltip="Each shield covers one missed day"))
        info.append(ft.Row(streak, spacing=14))
        scheduled, taken = svc.dose_counts(key)
        tips = growth_tips(ds, t, tot.total, tot.water_ml, scheduled, taken, svc.gaps(key, 2), svc.water_fmt)
        for tip in tips:
            info.append(ft.Row([th.chip(f"+{round(tip.gain)}", th.STATUS_COLORS["met"]), ft.Text(tip.text, size=12, expand=True)],
                               spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
        for msg in svc.check_growth(key, stage):
            app.toast(msg)
    else:
        info.append(th.muted("Final tree for this day." + (" Counted as a tree day." if score >= TREE_DAY else ""), 12))
    img = ft.Container(ft.Image(src=tree_svg(stage, svc.species_for(key)), width=120, height=116),
                       on_click=lambda _: app.go("garden"), tooltip="Open your garden")
    return th.card(ft.ResponsiveRow([ft.Container(img, col={"xs": 12, "sm": 4}, alignment=ft.Alignment.CENTER),
                                     ft.Container(ft.Column(info, spacing=6), col={"xs": 12, "sm": 8})],
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER))


def _pace(app: "App", t, tot) -> ft.Control:
    now = datetime.now()
    sched = app.store.schedule()
    rows = compute_pace(t, tot.total, tot.water_ml, sched, now.hour * 60 + now.minute)
    label = {"early": "early", "behind": "behind pace", "on": "on pace", "ahead": "ahead"}
    items: list[ft.Control] = [th.heading("Pace check", th.muted(f"expected by {now.strftime('%H:%M')}", 12), icon=ft.Icons.TIMER_OUTLINED)]
    for r in rows:
        status = "ahead" if r.status == "ahead" and not r.ahead_ok else ("on" if r.status == "ahead" else r.status)
        show = (lambda v: app.svc.water_fmt(v)) if r.unit == "ml" else (lambda v, u=r.unit: f"{fmt(v)}{'' if u == 'kcal' else ' g'}")
        marker_left = max(0.0, min(1.0, r.share))
        items.append(ft.Column([
            ft.Row([ft.Text(r.label, size=13, weight=ft.FontWeight.W_600, width=70),
                    th.muted(f"{show(r.actual)} · expected ~{show(r.expected)}", 12, expand=True),
                    th.chip(label[r.status], th.STATUS_COLORS[status])]),
            ft.Stack([
                ft.Container(th.bar(r.actual / r.target if r.target else 0, th.MACRO_COLORS[r.key]), top=4, left=0, right=0),
                ft.Row([ft.Container(expand=max(1, int(marker_left * 1000))),
                        ft.Container(width=3, height=16, bgcolor=ft.Colors.ON_SURFACE, border_radius=2),
                        ft.Container(expand=max(1, int((1 - marker_left) * 1000)))], spacing=0),
            ], height=16),
        ], spacing=4))
    if key_gaps := (app.svc.gaps(app.date, 3) if now.hour * 60 + now.minute >= _to_min(sched["dinner"]) - 60 else []):
        items.append(ft.Text("Close today's gaps", size=13, weight=ft.FontWeight.W_600))
        for g in key_gaps:
            foods = " · ".join(f"{n} ({sv}, +{round(p * 100)}%)" for n, sv, p in g.foods)
            items.append(ft.Text(spans=[ft.TextSpan(f"{g.micro.label} {round(g.pct * 100)}%: ", ft.TextStyle(weight=ft.FontWeight.W_600)),
                                        ft.TextSpan(foods)], size=12))
    if not app.store.reminders()["enabled"]:
        items.append(ft.Container(ft.Row([ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, size=18), ft.Text("Get check-ins, water nudges and supplement reminders.", size=12, expand=True),
                                          ft.TextButton("Turn on", on_click=lambda _: app.go("profile"))]),
                                  bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=ft.Padding.only(left=10)))
    return th.card(*items)


def _to_min(hhmm: str) -> int:
    h, _, m = hhmm.partition(":")
    return int(h) * 60 + int(m or 0)


def _water(app: "App", t, tot) -> ft.Control:
    total, target = tot.water_ml, t.water_ml
    pct = total / target if target else 0
    imperial = app.svc.imperial
    amounts = [(8, 237), (16, 473), (24, 710)] if imperial else [(250, 250), (500, 500), (750, 750)]

    def add(ml):
        app.store.add_water(app.date, ml)
        app.render()

    def undo(_):
        app.store.undo_water(app.date)
        app.render()

    glass = ft.Stack([
        ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=12, left=0, right=0, top=0, bottom=0),
        ft.Container(gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                                colors=["#5fb3e8", "#2f86c8"]),
                     border_radius=12, left=0, right=0, bottom=0, height=84 * min(pct, 1)),
        ft.Container(ft.Text(f"{round(pct * 100)}%", size=22, weight=ft.FontWeight.W_700), alignment=ft.Alignment.CENTER,
                     left=0, right=0, top=0, bottom=0),
    ], height=84)
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
    return th.card(th.heading("Water", icon=ft.Icons.WATER_DROP, icon_color=th.MACRO_COLORS["water"], trailing=th.muted(f"{app.svc.water_fmt(total)} / {app.svc.water_fmt(target)}", 12)),
                   glass, ft.Row(buttons, wrap=True, spacing=6), *breakdown, *extra, spacing=8)


def _supp_checklist(app: "App") -> ft.Control:
    supps = [s for s in app.store.supplements() if s.active]
    taken = {(d["supp_id"], d["time"]) for d in app.store.doses(app.date)}
    doses = sorted(((s, t) for s in supps for t in s.times), key=lambda x: x[1])
    now = datetime.now().strftime("%H:%M")
    is_today = app.date == today_key()

    def toggle(s, time):
        app.store.toggle_dose(app.date, s, time)
        app.render()

    rows: list[ft.Control] = []
    for s, time in doses:
        done = (s.id, time) in taken
        due = is_today and not done and time <= now
        rows.append(ft.Row([
            ft.Checkbox(value=done, on_change=lambda _, s=s, t=time: toggle(s, t)),
            ft.Column([ft.Text(s.name, size=14, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                               style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if done else None,
                               color=th.MUTED if done else None),
                       th.muted(f"{time} · {s.dose_label}{' · with food' if s.with_food else ''}", 11)], spacing=0, expand=True),
            *([th.chip("due", th.STATUS_COLORS["low"])] if due else []),
        ], spacing=4))
    done_count = sum(1 for s, t in doses if (s.id, t) in taken)
    return th.card(
        th.heading("Supplements", icon=ft.Icons.MEDICATION, trailing=th.muted(f"{done_count} / {len(doses)} taken", 12)),
        *(rows or [th.muted("No supplements yet. Add your stack and they'll count toward your micronutrients.", 12)]),
        ft.FilledTonalButton("Manage stack" if doses else "Add supplements", icon=ft.Icons.MEDICATION,
                             on_click=lambda _: app.go("supps")), spacing=4)
