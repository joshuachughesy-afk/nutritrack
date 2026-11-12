"""Today: calories, macros, meals and micronutrients for the selected day."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import MACROS, MICROS, fmt, micro_status
from ..service import pretty_date, shift
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
    controls.append(_summary(t, tot.total))
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
