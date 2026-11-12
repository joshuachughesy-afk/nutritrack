"""My foods: create custom foods from a nutrition label (per serving) and manage them."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.foods import FOODS, Food, Serving
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from ..store import new_id
from . import theme as th

if TYPE_CHECKING:
    from .app import App


def build(app: "App") -> list[ft.Control]:
    name = ft.TextField(label="Name", hint_text="e.g. Mom's lasagna", dense=True, border_radius=10, max_length=80)
    serving_label = ft.TextField(label="Serving description", value="1 serving", dense=True, border_radius=10, expand=True)
    serving_g = th.num_field("Serving weight", 100, suffix="g", expand=True)
    macro_fields = {k: th.num_field(lbl, None if k == "kcal" else 0, expand=True) for k, lbl in
                    (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"),
                     ("fiber", "Fiber (g)"), ("sugar", "Sugar (g)"))}
    micro_fields = {m.key: th.num_field(f"{m.label} ({m.unit})", None, col={"xs": 6, "sm": 4})
                    for m in MICROS if m.key != "fiber"}

    def save(_):
        g = th.parse_num(serving_g.value)
        if not name.value.strip():
            name.error = "Required"; app.page.update(); return
        if g <= 0 or not macro_fields["kcal"].value:
            macro_fields["kcal"].error = "Required" if not macro_fields["kcal"].value else None
            serving_g.error = "Must be above 0" if g <= 0 else None
            app.page.update(); return
        per100 = empty_nutrients()
        for k, fld in {**macro_fields, **micro_fields}.items():
            per100[k] = th.parse_num(fld.value) * 100 / g
        app.store.save_custom_food(Food(new_id("c-"), name.value.strip(), "Custom",
                                        [Serving(serving_label.value.strip() or "1 serving", g)], per100, "custom"))
        app.render()
        app.toast("Food saved")

    form = th.card(
        th.heading("Create a custom food"),
        th.muted("Enter values from the nutrition label, per serving. Micronutrients are optional.", 12),
        name, ft.Row([serving_label, serving_g], spacing=10),
        ft.Row([macro_fields["kcal"], macro_fields["protein"]], spacing=10),
        ft.Row([macro_fields["carbs"], macro_fields["fat"]], spacing=10),
        ft.Row([macro_fields["fiber"], macro_fields["sugar"]], spacing=10),
        ft.ExpansionTile(title=ft.Text("Micronutrients (optional)", size=14),
                         controls=[ft.ResponsiveRow(list(micro_fields.values()), spacing=10, run_spacing=10)],
                         tile_padding=0, controls_padding=ft.Padding.only(bottom=8)),
        ft.FilledButton("Save food", icon=ft.Icons.SAVE, on_click=save),
    )

    custom = app.store.custom_foods()

    def delete(fid):
        app.confirm("Delete this food?", "Past log entries keep their values.",
                    lambda: (app.store.delete_custom_food(fid), app.render()))

    rows: list[ft.Control] = []
    for f in custom:
        sv = f.servings[0]
        n = scale_nutrients(f.per100, sv.g)
        rows.append(ft.ListTile(title=ft.Text(f.name), dense=True,
                                subtitle=th.muted(f"{sv.label} · {fmt(n['kcal'])} kcal · P {fmt(n['protein'])} · "
                                                  f"C {fmt(n['carbs'])} · F {fmt(n['fat'])}", 12),
                                trailing=ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip=f"Delete {f.name}",
                                                       on_click=lambda _, i=f.id: delete(i))))
    saved = th.card(th.heading(f"Saved ({len(custom)})"),
                    *(rows or [th.muted(f"No custom foods yet. The built-in list has {len(FOODS)} common foods with "
                                        "full micronutrient data.", 13)]))
    return [ft.Text("My foods", size=22, weight=ft.FontWeight.W_700), form, saved]
