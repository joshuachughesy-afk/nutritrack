"""Foods tab: my foods (from a label), recipes (built from ingredients) and saved meals (meals or whole days)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.foods import Food, Serving
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from ..core.recipes import Ingredient, Recipe
from ..service import pretty_date, today_key
from ..store import new_id
from ..core.pacing import MEAL_LABELS
from . import components as cx
from . import motion
from . import theme as th

if TYPE_CHECKING:
    from .app import App


TABS = [("foods", "My foods"), ("recipes", "Recipes"), ("plans", "Saved meals")]


def build(app: "App") -> list[ft.Control]:
    tab = app.ui.foods_tab
    if tab == "recipes" and app.ui.recipe_edit:
        return _recipe_editor(app)
    if tab == "foods" and app.ui.food_edit:
        return _food_editor(app)

    def switch(v):
        app.ui.foods_tab = v
        app.ui.close_sub("foods")
        app.render()

    body = _recipes(app) if tab == "recipes" else _plans(app) if tab == "plans" else _my_foods(app)
    return [cx.screen_title("Foods"), cx.tabs(TABS, tab, switch)] + body


def _food_editor(app: "App") -> list[ft.Control]:
    """Create or edit a food from its nutrition label (values per serving)."""
    fid = app.ui.food_edit
    f0 = next((f for f in app.store.custom_foods() if f.id == fid), None) if fid != "new" else None
    sv0 = f0.servings[0] if f0 else Serving("1 serving", 100)

    def per_serving(k):
        if not f0:
            return None
        v = f0.per100.get(k, 0) * sv0.g / 100
        return fmt(v) if v else None

    name = ft.TextField(label="Name", hint_text="e.g. Mum's lasagna", dense=True, border_radius=12,
                        value=f0.name if f0 else "")
    serving_label = ft.TextField(label="Serving", value=sv0.label, dense=True, border_radius=12, expand=True)
    serving_g = th.num_field("Weight", fmt(sv0.g), suffix="g", expand=True)
    macro_fields = {k: th.num_field(lbl, per_serving(k), expand=True, hint_text="0") for k, lbl in
                    (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"),
                     ("fiber", "Fiber (g)"), ("sugar", "Sugar (g)"))}
    micro_fields = {m.key: th.num_field(f"{m.label} ({m.unit})", per_serving(m.key), col={"xs": 6, "sm": 4})
                    for m in MICROS if m.key != "fiber"}
    check = ft.Container()

    def close():
        app.ui.food_edit = None
        app.render()

    def save(_):
        g = th.parse_num(serving_g.value)
        name.error = "Give it a name" if not (name.value or "").strip() else None
        macro_fields["kcal"].error = "Required" if th.parse_num(macro_fields["kcal"].value) <= 0 else None
        serving_g.error = "Above 0" if g <= 0 else None
        if name.error or macro_fields["kcal"].error or serving_g.error:
            app.page.update()
            return
        per100 = empty_nutrients()
        for k, fld in {**macro_fields, **micro_fields}.items():
            per100[k] = th.parse_num(fld.value) * 100 / g
        food = Food(f0.id if f0 else new_id("c-"), name.value.strip(), "Custom",
                    [Serving(serving_label.value.strip() or "1 serving", g)], per100, "custom")
        app.store.save_custom_food(food)
        app.ui.food_edit = None
        app.render()
        app.toast(f"Saved {food.name}. It's in Add food now.")

    def sanity(*_):
        """Labels are often mistyped: warn when calories don't match the macros."""
        kcal = th.parse_num(macro_fields["kcal"].value)
        est = 4 * th.parse_num(macro_fields["protein"].value) + 4 * th.parse_num(macro_fields["carbs"].value) \
            + 9 * th.parse_num(macro_fields["fat"].value)
        check.content = cx.note(f"The macros add up to about {fmt(est)} kcal, not {fmt(kcal)}. Worth a second look at the "
                                "label.", "warn") if kcal and est and abs(est - kcal) / kcal > 0.2 else None
        app.page.update()

    for k in ("kcal", "protein", "carbs", "fat"):
        macro_fields[k].on_blur = sanity

    def delete(_):
        app.confirm(f"Delete {f0.name}?", "Things you've already logged keep their values.",
                    lambda: (app.store.delete_custom_food(f0.id), close()))

    actions: list[ft.Control] = [ft.FilledButton("Save food", icon=ft.Icons.CHECK, on_click=save)]
    if f0:
        actions.append(ft.TextButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=delete,
                                     style=ft.ButtonStyle(color=th.ink(th.STATUS_COLORS["over"]))))
    return [cx.back_header("New food" if not f0 else "Edit food", close, subtitle="Copy the values from the label, per serving"),
            th.card(name, ft.Row([serving_label, serving_g], spacing=10),
                    ft.Row([macro_fields["kcal"], macro_fields["protein"]], spacing=10),
                    ft.Row([macro_fields["carbs"], macro_fields["fat"]], spacing=10),
                    ft.Row([macro_fields["fiber"], macro_fields["sugar"]], spacing=10), check,
                    ft.ExpansionTile(title=ft.Text("Vitamins & minerals (optional)", size=th.T.BODY - 1),
                                     controls=[ft.ResponsiveRow(list(micro_fields.values()), spacing=10, run_spacing=10)],
                                     tile_padding=0, controls_padding=ft.Padding.only(bottom=8)),
                    ft.Row(actions, wrap=True), spacing=12)]


def _food_row(app: "App", f: Food, on_click) -> ft.Control:
    sv = f.servings[0]
    n = scale_nutrients(f.per100, sv.g)
    tag = {"custom": ("My food", th.SHIELD), "OFF": ("Brand label", th.EARTH)}.get(f.source)
    if f.source == "USDA" and f.id.startswith("usda-"):
        tag = ("✓ Verified", th.STATUS_COLORS["met"])
    return ft.Container(ft.Row([
        ft.Column([ft.Text(f.name, size=th.T.BODY - 1, font_family=th.FONT_SEMI, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                   ft.Row([th.muted(f"{sv.label} · {fmt(n['kcal'])} kcal · P {round(n['protein'])} · C {round(n['carbs'])} · "
                                    f"F {round(n['fat'])}", th.T.CAPTION), *([th.chip(*tag)] if tag else [])],
                          spacing=6, wrap=True)], spacing=2, expand=True),
        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=th.MUTED),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.symmetric(horizontal=8, vertical=10),
        border_radius=th.R.MD, ink=True, on_click=on_click)


def _my_foods(app: "App") -> list[ft.Control]:
    mine = [f for f in app.store.custom_foods() if f.source != "recipe"]
    lst = ft.Column(spacing=2)

    def new(_):
        app.ui.food_edit = "new"
        app.render()

    def open_food(f: Food):
        if f.source == "custom":
            app.ui.food_edit = f.id
            app.render()
        else:  # foods saved from online search: log them
            from . import add_food
            add_food.open_sheet(app, app.current_meal(), food=f)

    def fill(q: str = ""):
        tokens = [t for t in q.lower().split() if t]
        hits = [f for f in mine if all(t in f.name.lower() for t in tokens)]
        lst.controls = [_food_row(app, f, lambda _, f=f: open_food(f)) for f in hits] or \
            [th.muted(f"Nothing matches “{q}”.", th.T.LABEL)]

    new_btn = ft.FilledButton("New food", icon=ft.Icons.ADD, on_click=new)
    if not mine:
        return [th.card(cx.empty_state(ft.Icons.RESTAURANT_MENU, "Foods you create show up here and in Add food. Foods you "
                                       "pick from online search are saved here too, so they work offline.",
                                       new_btn, title="Your own foods"))]
    search = ft.TextField(hint_text="Search", prefix_icon=ft.Icons.SEARCH, dense=True,
                          border_radius=12, on_change=lambda e: (fill(e.control.value), app.page.update()), expand=True)
    fill()
    return [ft.Row([search, new_btn], spacing=8), th.card(lst, padding=8, spacing=0)]


# ---------- recipes ----------
def _per_serving_row(n: dict) -> ft.Control:
    def box(k, lbl):
        return ft.Container(ft.Column([th.display(str(round(n[k])), 17), th.muted(lbl, th.T.CAPTION)], spacing=0,
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            expand=True, padding=8, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER)
    return ft.Row([box("kcal", "kcal"), box("protein", "g protein"), box("carbs", "g carbs"), box("fat", "g fat")], spacing=6)


def _recipes(app: "App") -> list[ft.Control]:
    recipes = app.store.recipes()

    def new(_):
        app.ui.recipe_edit, app.ui.recipe_draft = "new", Recipe(new_id("r-"), "", 2, [])
        app.render()

    def edit(r: Recipe):
        app.ui.recipe_edit, app.ui.recipe_draft = r.id, Recipe.from_dict(r.to_dict())
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
            ft.Row([ft.Column([ft.Text(r.name, size=th.T.BODY + 1, font_family=th.FONT_BOLD),
                               th.muted(f"Makes {fmt(r.servings)} · {len(r.ingredients)} ingredients · "
                                        f"{round(r.total_grams / max(r.servings, 0.01))} g a serving", th.T.CAPTION)],
                              spacing=2, expand=True),
                    ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, tooltip="More", items=[
                        ft.PopupMenuItem(content=ft.Text("Edit"), icon=ft.Icons.EDIT_OUTLINED, on_click=lambda _, r=r: edit(r)),
                        ft.PopupMenuItem(content=ft.Text("Delete"), icon=ft.Icons.DELETE_OUTLINE,
                                         on_click=lambda _, r=r: delete(r))])],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            th.label("Per serving"), _per_serving_row(n),
            ft.FilledTonalButton("Log a serving", icon=ft.Icons.ADD, on_click=lambda _, r=r: log(r)), spacing=8))
    if not recipes:
        return [th.card(cx.empty_state(ft.Icons.MENU_BOOK, "Add ingredients and how many servings it makes. We'll do the "
                                       "maths, and the recipe shows up in Add food.",
                                       ft.FilledButton("New recipe", icon=ft.Icons.ADD, on_click=new),
                                       title="Batch-cook once, log in one tap"))]
    return [ft.Row([th.muted(f"{len(recipes)} recipe{'s' if len(recipes) != 1 else ''}", th.T.LABEL, expand=True),
                    ft.FilledButton("New recipe", icon=ft.Icons.ADD, on_click=new)]), *cards]


def _recipe_editor(app: "App") -> list[ft.Control]:
    r: Recipe = app.ui.recipe_draft
    foods = [f for f in app.svc.all_foods() if f.source != "recipe"]
    name = ft.TextField(label="Recipe name", value=r.name, dense=True, border_radius=12, max_length=80,
                        hint_text="e.g. Chicken burrito bowl")
    servings = th.num_field("Servings it makes", fmt(r.servings), expand=True)
    preview = ft.Column(spacing=6)
    ingredients = ft.Column(spacing=6)
    results = ft.Column(spacing=0)

    def refresh_preview():
        r.servings = max(th.parse_num(servings.value, r.servings), 0.25)
        preview.controls = [th.label(f"Per serving ({round(r.total_grams / r.servings)} g)"),
                            _per_serving_row(r.per_serving()),
                            th.muted(f"Whole recipe: {fmt(r.totals()['kcal'])} kcal · {fmt(r.total_grams)} g", th.T.CAPTION)]

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
                ft.Text(ing.name, size=th.T.LABEL + 1, expand=True, max_lines=2),
                th.num_field("g", fmt(ing.grams), width=90, on_change=lambda e, ing=ing: set_grams(ing, e.control.value)),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip="Remove", on_click=lambda _, ing=ing: remove(ing)),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER), padding=ft.Padding.only(left=12), border_radius=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER))
        ingredients.controls = rows or [th.muted("No ingredients yet. Search below to add some.", th.T.CAPTION)]

    def add(f):
        g = f.servings[0].g
        r.ingredients.append(Ingredient(f.id, f.name, g, scale_nutrients(f.per100, g)))
        search.value, results.controls = "", []
        motion.haptic("light")
        draw_ingredients(); refresh_preview(); app.page.update()

    def find(e):
        q = [t for t in (e.control.value or "").lower().split() if t]
        hits = [f for f in foods if q and all(t in f.name.lower() for t in q)][:8]
        results.controls = [ft.ListTile(title=ft.Text(f.name, size=th.T.LABEL + 1), dense=True,
                                        subtitle=th.muted(f"adds {f.servings[0].label}", th.T.CAPTION),
                                        on_click=lambda _, f=f: add(f), content_padding=ft.Padding.symmetric(horizontal=4))
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
        app.ui.recipe_edit = None
        app.render()
        app.toast(f"Saved {r.name}. Find it in Add food.")

    def cancel(_):
        app.ui.recipe_edit = None
        app.render()

    draw_ingredients(); refresh_preview()
    return [cx.back_header("New recipe" if app.ui.recipe_edit == "new" else "Edit recipe", lambda: cancel(None),
                           trailing=ft.FilledButton("Save", on_click=save)),
            th.card(name, ft.Row([servings]), th.label("Ingredients"), ingredients, search, results, spacing=10),
            th.card(preview, spacing=8),
            ft.Row([ft.FilledButton("Save recipe", icon=ft.Icons.CHECK, on_click=save, expand=True)])]


# ---------- saved meals ----------
def _plans(app: "App") -> list[ft.Control]:
    plans = app.store.plans()
    key = app.date
    when = "today" if key == today_key() else pretty_date(key)

    def log(plan, meal=None):
        n = app.svc.apply_plan(plan, key, meal)
        motion.haptic("medium")
        app.toast(f"Logged {n} item{'s' if n != 1 else ''} from “{plan.name}” to {when}")

    def delete(plan):
        app.confirm(f"Delete “{plan.name}”?", "This only removes the saved meal, not anything you've logged.",
                    lambda: (app.store.delete_plan(plan.id), app.render()))

    cards: list[ft.Control] = []
    for plan in plans:
        tot = plan.totals()
        names = ", ".join(i.name.split(",")[0] for i in plan.items[:4]) + ("…" if len(plan.items) > 4 else "")
        if plan.kind == "meal":
            log_btn = ft.PopupMenuButton(
                content=ft.FilledTonalButton(f"Log to {when}", icon=ft.Icons.ADD, on_click=None),
                tooltip="Choose a meal",
                items=[ft.PopupMenuItem(content=ft.Text(f"As {lbl.lower()}"), on_click=lambda _, m=m, p=plan: log(p, m))
                       for m, lbl in MEAL_LABELS.items()])
        else:
            log_btn = ft.FilledTonalButton(f"Log the whole day to {when}", icon=ft.Icons.ADD, on_click=lambda _, p=plan: log(p))
        cards.append(th.card(
            ft.Row([ft.Column([ft.Text(plan.name, size=th.T.BODY + 1, font_family=th.FONT_BOLD),
                               th.muted(names, th.T.CAPTION, max_lines=2)], spacing=2, expand=True),
                    th.chip("Meal" if plan.kind == "meal" else "Whole day", th.ACCENT if plan.kind == "meal" else th.SHIELD),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete", on_click=lambda _, p=plan: delete(p))],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            th.muted(f"{len(plan.items)} items · {fmt(tot['kcal'])} kcal · P {round(tot['protein'])} · "
                     f"C {round(tot['carbs'])} · F {round(tot['fat'])} g", th.T.CAPTION),
            ft.Row([log_btn]), spacing=8))
    if not plans:
        return [th.card(cx.empty_state(ft.Icons.BOOKMARKS_OUTLINED, "Tap Save meal under any meal on Today, or save a "
                                       "whole day from the Progress calendar. Then log it again in one tap.",
                                       title="Eat the same breakfast most days?"))]
    return cards
