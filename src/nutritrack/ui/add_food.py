"""Add-food bottom sheet: search, recents, amount picker with live preview, and quick add."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.foods import Food
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from . import theme as th

if TYPE_CHECKING:
    from .app import App

MEAL_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snacks": "Snacks"}


def open_sheet(app: "App", meal: str) -> None:
    content = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    sheet = ft.BottomSheet(
        content=ft.Container(content=content, padding=ft.Padding.only(left=16, right=16, top=8, bottom=24), height=620),
        show_drag_handle=True, scrollable=True, draggable=True)

    def close():
        app.page.pop_dialog()

    def header(title: str, back: bool = False) -> ft.Control:
        left = [ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: picker(), tooltip="Back to search")] if back else []
        return ft.Row(left + [ft.Text(title, size=18, weight=ft.FontWeight.W_700, expand=True),
                              ft.IconButton(ft.Icons.CLOSE, on_click=lambda _: close(), tooltip="Close")])

    # ---------- search ----------
    results = ft.Column(spacing=0)

    def result_tile(f: Food) -> ft.Control:
        sv = f.servings[0]
        tag = "  · custom" if f.source == "custom" else ""
        return ft.ListTile(title=ft.Text(f.name + tag, size=14),
                           subtitle=th.muted(f"{sv.label} · {fmt(f.per100['kcal'] * sv.g / 100)} kcal", 12),
                           dense=True, on_click=lambda _, food=f: detail(food))

    def fill_results(q: str) -> None:
        tokens = [t for t in q.lower().split() if t]
        foods = app.svc.all_foods()
        items: list[ft.Control] = []
        if not tokens:
            recents = [f for f in (app.svc.find_food(i) for i in app.store.recents()) if f]
            if recents:
                items.append(th.muted("RECENT", 11, weight=ft.FontWeight.W_600))
                items += [result_tile(f) for f in recents]
            items.append(th.muted("ALL FOODS", 11, weight=ft.FontWeight.W_600))
            items += [result_tile(f) for f in sorted(foods, key=lambda f: f.name)]
        else:
            hits = [f for f in foods if all(t in f.name.lower() or t in f.category.lower() for t in tokens)]
            items = [result_tile(f) for f in hits] or [th.muted(f"No match for “{q}”. Create it under Foods.", 13)]
        results.controls = items

    def picker() -> None:
        search = ft.TextField(hint_text=f"Search {len(app.svc.all_foods())} foods…", prefix_icon=ft.Icons.SEARCH,
                              autofocus=True, dense=True, border_radius=12,
                              on_change=lambda e: (fill_results(e.control.value), app.page.update()))
        fill_results("")
        content.controls = [header(f"Add to {MEAL_LABELS[meal]}"), search,
                            ft.Row([ft.TextButton("Quick add calories", icon=ft.Icons.BOLT, on_click=lambda _: quick())],
                                   alignment=ft.MainAxisAlignment.END),
                            results]
        app.page.update()

    # ---------- amount + preview ----------
    def detail(f: Food) -> None:
        qty = th.num_field("Amount", 1, expand=1, autofocus=True)
        unit = ft.Dropdown(label="Unit", value="0", dense=True, expand=2, border_radius=10,
                           options=[ft.DropdownOption(key=str(i), text=s.label) for i, s in enumerate(f.servings)]
                                   + [ft.DropdownOption(key="g", text="grams")])
        preview = ft.Column(spacing=8)
        t = app.svc.targets_for(app.date)

        def amount() -> tuple[float, str]:
            q = th.parse_num(qty.value)
            if unit.value == "g":
                return q, f"{fmt(q)} g"
            sv = f.servings[int(unit.value or 0)]
            return q * sv.g, ("" if q == 1 else f"{fmt(q)} × ") + sv.label

        def update_preview(*_):
            grams, _ = amount()
            n = scale_nutrients(f.per100, grams)
            boxes = [ft.Container(ft.Column([ft.Text(fmt(n[k]), size=18, weight=ft.FontWeight.W_700), th.muted(lbl, 11)],
                                            spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                  expand=True, padding=10, border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
                     for k, lbl in (("kcal", "kcal"), ("protein", "protein"), ("carbs", "carbs"), ("fat", "fat"))]
            good = sorted(((n[m.key] / t.micros[m.key].target, m) for m in MICROS if not m.limit), key=lambda x: -x[0])
            good = [(p, m) for p, m in good if p >= 0.1][:4]
            preview.controls = [ft.Row(boxes, spacing=8)]
            if good:
                preview.controls.append(ft.Row([th.muted("Good source of:", 12)] +
                                                [th.chip(f"{m.label} {round(p * 100)}%", th.STATUS_COLORS["met"]) for p, m in good],
                                                wrap=True, spacing=6))
            app.page.update()

        def add(_):
            grams, label = amount()
            if grams <= 0:
                return
            app.store.add_entry(app.date, meal, f.name, scale_nutrients(f.per100, grams), food_id=f.id, grams=grams,
                                amount_label=label)
            close()
            app.render()

        qty.on_change = update_preview
        qty.on_submit = add
        unit.on_select = update_preview
        content.controls = [header(f.name, back=True), ft.Row([qty, unit], spacing=10), preview,
                            ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add, width=float("inf"))]
        update_preview()

    # ---------- quick add ----------
    def quick() -> None:
        name = ft.TextField(label="Description", value="Quick add", dense=True, border_radius=10)
        fields = {k: th.num_field(lbl, 0 if k != "kcal" else None, expand=True)
                  for k, lbl in (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"))}

        def add(_):
            n = empty_nutrients()
            for k, fld in fields.items():
                n[k] = th.parse_num(fld.value)
            if n["kcal"] <= 0:
                fields["kcal"].error = "Required"
                app.page.update()
                return
            app.store.add_entry(app.date, meal, name.value.strip() or "Quick add", n, amount_label="quick add")
            close()
            app.render()

        content.controls = [header("Quick add", back=True), name,
                            ft.Row([fields["kcal"], fields["protein"]], spacing=10),
                            ft.Row([fields["carbs"], fields["fat"]], spacing=10),
                            th.muted("Good for restaurant meals. Quick adds don't include micronutrients.", 12),
                            ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add, width=float("inf"))]
        app.page.update()

    picker()
    app.page.show_dialog(sheet)
