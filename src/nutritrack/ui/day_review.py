"""Look back on a single day (from the Garden calendar): its tree, score, nutrition, water, supplements and food log."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import flet as ft

from ..core.garden import TREE_DAY
from ..core.nutrition import MACROS, fmt
from ..core.pacing import MEAL_LABELS
from ..core.recipes import Plan
from ..service import today_key
from ..store import new_id
from . import motion
from . import theme as th
from .tree_view import tree_src

if TYPE_CHECKING:
    from .app import App

MEALS = list(MEAL_LABELS.items())


def ask_plan_name(app: "App", title: str, default: str, on_save) -> None:
    """Small dialog asking for a plan name, then calling on_save(name)."""
    name = ft.TextField(label="Name", value=default, autofocus=True, dense=True, border_radius=12, max_length=60)

    def save(_):
        if not (name.value or "").strip():
            name.error = "Give it a name"
            app.page.update()
            return
        app.page.pop_dialog()
        on_save(name.value.strip())

    name.on_submit = save
    app.page.show_dialog(ft.AlertDialog(title=ft.Text(title, font_family=th.FONT_BOLD), content=name,
                                        actions=[ft.TextButton("Cancel", on_click=lambda _: app.page.pop_dialog()),
                                                 ft.FilledButton("Save", on_click=save)]))


def save_entries_as_plan(app: "App", entries: list[dict], kind: str, default: str) -> None:
    def done(name: str) -> None:
        app.store.save_plan(Plan.from_entries(new_id("p-"), name, kind, entries))
        motion.haptic("light")
        app.toast(f"Saved “{name}”. Find it in Foods → Saved meals and in Add food.")
    ask_plan_name(app, "Save this meal" if kind == "meal" else "Save this day", default, done)


def open_review(app: "App", key: str) -> None:
    r = app.svc.day_review(key)
    t, tot = r["targets"], r["totals"]
    d = date.fromisoformat(key)
    score = r["score"]

    def stat(label: str, value: str, sub: str = "") -> ft.Control:
        return ft.Container(ft.Column([th.muted(label, 11, font_family=th.FONT_SEMI), th.display(value, 18),
                                       *([th.muted(sub, 11)] if sub else [])], spacing=0),
                            expand=True, padding=10, border_radius=14, bgcolor=ft.Colors.SURFACE_CONTAINER)

    header = ft.Row([
        ft.Image(src=tree_src(r["species"], r["stage"] or 0, 128, season=r["season"]), width=110, height=110),
        ft.Column([th.muted(d.strftime("%A").upper(), 11, font_family=th.FONT_SEMI),
                   th.display(d.strftime("%d %B %Y"), 20),
                   ft.Text(f"{r['stage_name']} · {score}/100" if score is not None else "Nothing logged", size=14,
                           font_family=th.FONT_SEMI),
                   *([th.chip("Tree day", th.ACCENT)] if score is not None and score >= TREE_DAY else [])],
                  spacing=2, expand=True),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    macro_rows = []
    for k, label, _ in MACROS:
        target = t.macro(k)
        macro_rows.append(ft.Column([
            ft.Row([th.dot(th.MACRO_COLORS[k]), ft.Text(label, size=12, font_family=th.FONT_SEMI, expand=True),
                    th.muted(f"{fmt(tot.total[k])} / {target} g", 11)]),
            th.bar(tot.total[k] / target if target else 0, th.MACRO_COLORS[k], height=7)], spacing=3))

    taken, scheduled = r["doses"]
    stats = ft.Row([
        stat("CALORIES", fmt(tot.total["kcal"]), f"of {t.kcal:,}"),
        stat("WATER", app.svc.water_fmt(tot.water_ml), f"of {app.svc.water_fmt(t.water_ml)}"),
        stat("SUPPS", f"{taken}/{scheduled}" if scheduled else "–", "doses taken"),
    ], spacing=8)

    meals: list[ft.Control] = []
    for m, label in MEALS:
        items = [e for e in r["entries"] if e["meal"] == m]
        if not items:
            continue
        meals.append(ft.Row([ft.Text(label, size=13, font_family=th.FONT_SEMI, expand=True),
                             th.muted(f"{fmt(sum(e['n']['kcal'] for e in items))} kcal", 12)]))
        meals += [ft.Row([ft.Text(e["name"], size=12.5, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                          th.muted(e["amount_label"] or "", 11), ft.Text(fmt(e["n"]["kcal"]), size=12.5)], spacing=8)
                  for e in items]
    if not meals:
        meals = [th.muted("No food was logged on this day.", 13)]
    if r["weight"]:
        w = r["weight"] * 2.20462 if app.svc.imperial else r["weight"]
        meals.append(th.muted(f"Weight logged: {w:.1f} {'lb' if app.svc.imperial else 'kg'}", 12))

    def open_day(_):
        app.page.pop_dialog()
        app.go("today", key)

    def copy_today(_):
        n = len(r["entries"])
        for e in r["entries"]:
            app.store.add_entry(today_key(), e["meal"], e["name"], e["n"], food_id=e.get("food_id"),
                                grams=e.get("grams") or 0, amount_label=e.get("amount_label") or "")
        app.page.pop_dialog()
        app.render()
        app.toast(f"Logged {n} item{'s' if n != 1 else ''} to today")

    actions: list[ft.Control] = [ft.FilledButton("Open this day", icon=ft.Icons.OPEN_IN_NEW, on_click=open_day)]
    if r["entries"]:
        actions += [ft.OutlinedButton("Save day", icon=ft.Icons.BOOKMARK_ADD_OUTLINED,
                                      on_click=lambda _: save_entries_as_plan(app, r["entries"], "day", d.strftime("%A %d %b"))),
                    ft.TextButton("Log again today", icon=ft.Icons.REPLAY, on_click=copy_today)]

    body = ft.Column([
        ft.Row([ft.Container(expand=True), ft.IconButton(ft.Icons.CLOSE, on_click=lambda _: app.page.pop_dialog())]),
        header, stats, *macro_rows, ft.Divider(height=10), *meals, ft.Row(actions, wrap=True, spacing=8),
    ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    app.page.show_dialog(ft.BottomSheet(
        content=ft.Container(body, padding=ft.Padding.only(left=18, right=18, bottom=24), height=640),
        show_drag_handle=True, scrollable=True, draggable=True))
