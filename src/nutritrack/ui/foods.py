"""Foods tab: my foods (from a label), recipes (built from ingredients) and meal plans (saved meals or days)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.foods import FOODS, Food, Serving
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from ..core.recipes import Ingredient, Recipe
from ..service import today_key
from ..store import new_id
from . import motion
from . import theme as th

if TYPE_CHECKING:
    from .app import App


TABS = [("foods", "My foods", ft.Icons.RESTAURANT), ("recipes", "Recipes", ft.Icons.MENU_BOOK),
        ("plans", "Meal plans", ft.Icons.BOOKMARKS)]
MEAL_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snacks": "Snacks"}


def build(app: "App") -> list[ft.Control]:
    tab = getattr(app, "foods_tab", "foods")

    def switch(e):
        app.foods_tab = list(e.control.selected)[0]
        app.recipe_edit = None
        app.render()

    tabs = ft.SegmentedButton(segments=[ft.Segment(value=k, label=ft.Text(lbl)) for k, lbl, _ in TABS],
                              selected=[tab], on_change=switch, show_selected_icon=False, expand=True)
    if tab == "recipes":
        body = _recipe_editor(app) if getattr(app, "recipe_edit", None) else _recipes(app)
    elif tab == "plans":
        body = _plans(app)
    else:
        body = _my_foods(app)
    return [th.title("Foods"), ft.Row([tabs])] + body


def _my_foods(app: "App") -> list[ft.Control]:
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

    custom = [f for f in app.store.custom_foods() if f.source == "custom"]

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
    return [form, saved]


# ---------- recipes ----------
def _per_serving_row(n: dict) -> ft.Control:
    def box(k, lbl):
        return ft.Container(ft.Column([th.display(fmt(n[k]), 17), th.muted(lbl, 11)], spacing=0,
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            expand=True, padding=8, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER)
    return ft.Row([box("kcal", "kcal"), box("protein", "protein"), box("carbs", "carbs"), box("fat", "fat")], spacing=6)


def _recipes(app: "App") -> list[ft.Control]:
    recipes = app.store.recipes()

    def new(_):
        app.recipe_edit, app.recipe_draft = "new", Recipe(new_id("r-"), "", 2, [])
        app.render()

    def edit(r: Recipe):
        app.recipe_edit, app.recipe_draft = r.id, Recipe.from_dict(r.to_dict())
        app.render()

    def log(r: Recipe):
        from . import add_food
        add_food.open_sheet(app, app.current_meal(), food=r.to_food())

    def delete(r: Recipe):
        app.confirm(f"Delete {r.name}?", "Past log entries keep their values.",
                    lambda: (app.store.delete_recipe(r.id), app.render()))

    cards: list[ft.Control] = []
    for r in recipes:
        n = r.per_serving()
        cards.append(th.card(
            ft.Row([ft.Column([ft.Text(r.name, size=16, font_family=th.FONT_BOLD),
                               th.muted(f"{fmt(r.servings)} servings · {len(r.ingredients)} ingredients · "
                                        f"{fmt(r.total_grams / max(r.servings, 0.01))} g per serving", 12)],
                              spacing=2, expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit", on_click=lambda _, r=r: edit(r)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete", on_click=lambda _, r=r: delete(r))]),
            th.muted("PER SERVING", 11, font_family=th.FONT_SEMI), _per_serving_row(n),
            ft.FilledTonalButton("Log a serving", icon=ft.Icons.ADD, on_click=lambda _, r=r: log(r)), spacing=8))
    intro = th.card(
        th.heading("Recipes", ft.FilledButton("New recipe", icon=ft.Icons.ADD, on_click=new), icon=ft.Icons.MENU_BOOK),
        th.muted("Build a dish from its ingredients and say how many servings it makes. NutriTrack works out the "
                 "nutrition per serving, and the recipe appears in Add food like any other food.", 12))
    if not recipes:
        cards = [th.card(th.muted("No recipes yet. Try your go-to breakfast or a batch-cooked dinner.", 13))]
    return [intro, *cards]


def _recipe_editor(app: "App") -> list[ft.Control]:
    r: Recipe = app.recipe_draft
    foods = [f for f in app.svc.all_foods() if f.source != "recipe"]
    name = ft.TextField(label="Recipe name", value=r.name, dense=True, border_radius=12, max_length=80,
                        hint_text="e.g. Chicken burrito bowl")
    servings = th.num_field("Servings it makes", fmt(r.servings), expand=True)
    preview = ft.Column(spacing=6)
    ingredients = ft.Column(spacing=6)
    results = ft.Column(spacing=0)

    def refresh_preview():
        r.servings = max(th.parse_num(servings.value, r.servings), 0.25)
        preview.controls = [th.muted(f"PER SERVING ({fmt(r.total_grams / r.servings)} g)", 11, font_family=th.FONT_SEMI),
                            _per_serving_row(r.per_serving()),
                            th.muted(f"Whole recipe: {fmt(r.totals()['kcal'])} kcal · {fmt(r.total_grams)} g", 11)]

    def set_grams(ing: Ingredient, value: str):
        g = th.parse_num(value)
        if g <= 0:
            return
        f = app.svc.find_food(ing.food_id) if ing.food_id else None
        ing.n = scale_nutrients(f.per100, g) if f else {k: v * g / ing.grams for k, v in ing.n.items()}
        ing.grams = g
        refresh_preview()
        app.page.update()

    def remove(ing: Ingredient):
        r.ingredients.remove(ing)
        draw_ingredients(); refresh_preview(); app.page.update()

    def draw_ingredients():
        rows = []
        for ing in r.ingredients:
            rows.append(ft.Container(ft.Row([
                ft.Text(ing.name, size=13.5, expand=True, max_lines=2),
                th.num_field("g", fmt(ing.grams), width=90, on_change=lambda e, ing=ing: set_grams(ing, e.control.value)),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip="Remove", on_click=lambda _, ing=ing: remove(ing)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.only(left=12), border_radius=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER))
        ingredients.controls = rows or [th.muted("No ingredients yet. Search below to add some.", 12)]

    def add(f):
        g = f.servings[0].g
        r.ingredients.append(Ingredient(f.id, f.name, g, scale_nutrients(f.per100, g)))
        search.value, results.controls = "", []
        motion.haptic("light")
        draw_ingredients(); refresh_preview(); app.page.update()

    def find(e):
        q = [t for t in (e.control.value or "").lower().split() if t]
        hits = [f for f in foods if q and all(t in f.name.lower() for t in q)][:8]
        results.controls = [ft.ListTile(title=ft.Text(f.name, size=13.5), dense=True,
                                        subtitle=th.muted(f"adds {f.servings[0].label}", 11), on_click=lambda _, f=f: add(f))
                            for f in hits]
        app.page.update()

    search = ft.TextField(hint_text="Add an ingredient…", prefix_icon=ft.Icons.SEARCH, dense=True, border_radius=12,
                          on_change=find)
    servings.on_change = lambda _: (refresh_preview(), app.page.update())

    def save(_):
        if not (name.value or "").strip():
            name.error = "Give your recipe a name"; app.page.update(); return
        if not r.ingredients:
            search.error = "Add at least one ingredient"; app.page.update(); return
        r.name = name.value.strip()
        refresh_preview()
        app.store.save_recipe(r)
        app.recipe_edit = None
        app.render()
        app.toast(f"Saved {r.name}. Find it in Add food.")

    def cancel(_):
        app.recipe_edit = None
        app.render()

    draw_ingredients(); refresh_preview()
    return [th.card(
        th.heading("New recipe" if app.recipe_edit == "new" else "Edit recipe", icon=ft.Icons.MENU_BOOK),
        name, ft.Row([servings]), ft.Text("Ingredients", size=14, font_family=th.FONT_SEMI), ingredients, search, results,
        ft.Divider(height=8), preview,
        ft.Row([ft.FilledButton("Save recipe", icon=ft.Icons.CHECK, on_click=save), ft.TextButton("Cancel", on_click=cancel)]),
        spacing=10)]


# ---------- meal plans ----------
def _plans(app: "App") -> list[ft.Control]:
    plans = app.store.plans()

    def log(plan, meal=None):
        n = app.svc.apply_plan(plan, today_key(), meal)
        motion.haptic("medium")
        app.toast(f"Logged {n} item{'s' if n != 1 else ''} from “{plan.name}” to today")

    def delete(plan):
        app.confirm(f"Delete “{plan.name}”?", "This only removes the plan, not anything you've logged.",
                    lambda: (app.store.delete_plan(plan.id), app.render()))

    cards: list[ft.Control] = []
    for plan in plans:
        tot = plan.totals()
        names = ", ".join(i.name.split(",")[0] for i in plan.items[:4]) + ("…" if len(plan.items) > 4 else "")
        if plan.kind == "meal":
            log_btn = ft.PopupMenuButton(
                content=ft.Container(ft.Row([ft.Icon(ft.Icons.ADD, size=18), ft.Text("Log to today", size=14)], tight=True,
                                            spacing=6), padding=ft.Padding.symmetric(horizontal=14, vertical=9),
                                     border_radius=20, bgcolor=ft.Colors.SECONDARY_CONTAINER),
                items=[ft.PopupMenuItem(content=ft.Text(f"As {lbl.lower()}"), on_click=lambda _, m=m, p=plan: log(p, m))
                       for m, lbl in MEAL_LABELS.items()])
        else:
            log_btn = ft.FilledTonalButton("Log whole day to today", icon=ft.Icons.ADD, on_click=lambda _, p=plan: log(p))
        cards.append(th.card(
            ft.Row([ft.Column([ft.Text(plan.name, size=16, font_family=th.FONT_BOLD),
                               th.muted(names, 12, max_lines=2)], spacing=2, expand=True),
                    th.chip("Meal" if plan.kind == "meal" else "Whole day", th.ACCENT if plan.kind == "meal" else "#4c7cf0"),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete plan", on_click=lambda _, p=plan: delete(p))],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            th.muted(f"{len(plan.items)} items · {fmt(tot['kcal'])} kcal · P {fmt(tot['protein'])} · C {fmt(tot['carbs'])} · "
                     f"F {fmt(tot['fat'])} g", 12),
            ft.Row([log_btn]), spacing=8))
    intro = th.card(
        th.heading("Meal plans", icon=ft.Icons.BOOKMARKS),
        th.muted("Save meals you eat often and log them in one tap. To save one, tap the bookmark on a meal on Today, "
                 "or open a day from the Garden calendar and choose Save as plan. Saved meals also appear in Add food.", 12))
    if not plans:
        cards = [th.card(th.muted("No meal plans yet.", 13))]
    return [intro, *cards]
