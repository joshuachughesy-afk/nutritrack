"""Add-food bottom sheet: local + online search, barcode scanning, amount picker with live preview, and quick add."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import flet as ft

from ..core import barcode as bc
from ..core import online
from ..core.foods import Food
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from . import theme as th

if TYPE_CHECKING:
    from .app import App

MEAL_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snacks": "Snacks"}


def open_sheet(app: "App", meal: str, edit: dict | None = None) -> None:
    """Add food to a meal, or (with `edit`) change a logged entry's amount, unit or meal."""
    content = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    sheet = ft.BottomSheet(
        content=ft.Container(content=content, padding=ft.Padding.only(left=16, right=16, top=8, bottom=24), height=620),
        show_drag_handle=True, scrollable=True, draggable=True)

    def close():
        app.page.pop_dialog()

    def header(title: str, back: bool = False) -> ft.Control:
        left = [ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: picker(), tooltip="Back to search")] if back else []
        return ft.Row(left + [ft.Text(title, size=18, font_family=th.FONT_BOLD, expand=True),
                              ft.IconButton(ft.Icons.CLOSE, on_click=lambda _: close(), tooltip="Close")])

    # ---------- search ----------
    results = ft.Column(spacing=0)

    SOURCE_TAGS = {"custom": "custom", "OFF": "Open Food Facts", "USDA": "USDA"}

    def result_tile(f: Food, fetch_full: bool = False) -> ft.Control:
        sv = f.servings[0]
        tag = f"  · {SOURCE_TAGS[f.source]}" if f.source in SOURCE_TAGS else ""
        return ft.ListTile(title=ft.Text(f.name, size=14),
                           subtitle=th.muted(f"{sv.label} · {fmt(f.per100['kcal'] * sv.g / 100)} kcal{tag}", 12),
                           dense=True, on_click=lambda _, food=f: (app.page.run_task(open_full, food) if fetch_full
                                                                   else detail(food)))

    async def open_full(f: Food) -> None:
        """Search hits carry fewer nutrients than the product page, so fetch the full product before showing it."""
        status.value = "Loading product…"
        app.page.update()
        try:
            full = await asyncio.to_thread(app.svc.full_food, f)
        except Exception:
            full = None
        detail(full or f)

    status = th.muted("", 12)
    online_results = ft.Column(spacing=0)
    query = {"q": "", "source": "off"}

    async def search_online(_=None) -> None:
        q = query["q"].strip()
        if len(q) < 2:
            status.value = "Type at least 2 letters, then search online."
            app.page.update(); return
        status.value = f"Searching {'USDA' if query['source'] == 'usda' else 'Open Food Facts'}…"
        online_results.controls = [_skeleton() for _ in range(4)]
        app.page.update()
        try:
            hits = await asyncio.to_thread(app.svc.search_online, q, query["source"])
            status.value = (f"{len(hits)} results. Values are from "
                            + ("USDA FoodData Central (lab-measured)." if query["source"] == "usda"
                               else "Open Food Facts (crowd-sourced, so check against the label)."))
            online_results.controls = [result_tile(f, fetch_full=True) for f in hits] or \
                [th.muted("No results online either. Create it under Foods.", 13)]
        except Exception as ex:
            status.value = f"Couldn't search online: {ex}"
            online_results.controls = []
        app.page.update()

    def fill_results(q: str) -> None:
        tokens = [t for t in q.lower().split() if t]
        foods = app.svc.all_foods()
        items: list[ft.Control] = []
        if not tokens:
            recents = [f for f in (app.svc.find_food(i) for i in app.store.recents()) if f]
            if recents:
                items.append(th.muted("RECENT", 11, font_family=th.FONT_SEMI))
                items += [result_tile(f) for f in recents]
            items.append(th.muted("ALL FOODS", 11, font_family=th.FONT_SEMI))
            items += [result_tile(f) for f in sorted(foods, key=lambda f: f.name)]
        else:
            hits = [f for f in foods if all(t in f.name.lower() or t in f.category.lower() for t in tokens)]
            items = [result_tile(f) for f in hits] or [th.muted(f"Nothing saved matches “{q}”. Search online below, or create it under Foods.", 13)]
        results.controls = items

    def picker() -> None:
        def on_change(e):
            query["q"] = e.control.value
            fill_results(e.control.value)
            app.page.update()

        search = ft.TextField(hint_text=f"Search {len(app.svc.all_foods())} foods…", prefix_icon=ft.Icons.SEARCH,
                              autofocus=True, dense=True, border_radius=12, on_change=on_change,
                              on_submit=lambda _: app.page.run_task(search_online), value=query["q"])

        def set_source(e):
            query["source"] = list(e.control.selected)[0]

        source = ft.SegmentedButton(segments=[ft.Segment(value="off", label=ft.Text("Brands")),
                                              ft.Segment(value="usda", label=ft.Text("USDA"))],
                                    selected=[query["source"]], on_change=set_source, show_selected_icon=False)
        fill_results(query["q"])
        content.controls = [
            header(f"Add to {MEAL_LABELS[meal]}"), search,
            ft.Row([ft.FilledTonalButton("Scan barcode", icon=ft.Icons.QR_CODE_SCANNER, on_click=lambda _: scan()),
                    ft.TextButton("Quick add", icon=ft.Icons.BOLT, on_click=lambda _: quick())], wrap=True),
            results,
            ft.Divider(),
            ft.Row([ft.Text("Search online", font_family=th.FONT_SEMI, size=14, expand=True), source]),
            ft.FilledButton("Search online", icon=ft.Icons.TRAVEL_EXPLORE, on_click=lambda _: app.page.run_task(search_online)),
            status, online_results,
        ]
        app.page.update()

    # ---------- barcode ----------
    def scan() -> None:
        code = ft.TextField(label="Barcode number", hint_text="e.g. 0038000016912", keyboard_type=ft.KeyboardType.NUMBER,
                            dense=True, border_radius=10, expand=True, autofocus=app.page.web or not bc.available())
        scan_status = th.muted("Point the camera at the barcode, or type the number printed under it.", 12)
        camera_box = ft.Column(spacing=8)

        async def look_up(_=None) -> None:
            digits = online.normalize_barcode(code.value or "")
            if not digits:
                code.error = "Enter 8–14 digits"
                app.page.update(); return
            code.error = None
            scan_status.value = "Looking it up on Open Food Facts…"
            app.page.update()
            try:
                f = await asyncio.to_thread(app.svc.lookup_barcode, digits)
            except Exception as ex:
                scan_status.value = f"Couldn't reach Open Food Facts: {ex}"
                app.page.update(); return
            if f:
                detail(f)
            else:
                scan_status.value = (f"Product {digits} isn't in Open Food Facts yet. Create it under Foods "
                                     "(and consider adding it at openfoodfacts.org).")
                app.page.update()

        async def decoded(image: bytes) -> None:
            text = await asyncio.to_thread(bc.decode, image)
            if text:
                code.value = text
                await look_up()
            else:
                scan_status.value = "No barcode found in that photo. Fill the frame with the barcode and try again."
                app.page.update()

        async def from_photo(_) -> None:
            files = await ft.FilePicker().pick_files(file_type=ft.FilePickerFileType.IMAGE, with_data=True)
            if files:
                data = files[0].bytes or open(files[0].path, "rb").read()
                await decoded(data)

        async def start_camera() -> None:
            try:
                import flet_camera as fcam
                cam = fcam.Camera(height=240, expand=True)
                camera_box.controls = [ft.Container(cam, height=240, border_radius=12, clip_behavior=ft.ClipBehavior.HARD_EDGE)]
                app.page.update()
                cams = await cam.get_available_cameras()
                back = next((c for c in cams if "back" in str(c.lens_direction).lower()), cams[0] if cams else None)
                if back is None:
                    raise RuntimeError("no camera")
                await cam.initialize(back, fcam.ResolutionPreset.HIGH, enable_audio=False)

                async def capture(_):
                    scan_status.value = "Reading barcode…"
                    app.page.update()
                    await decoded(await cam.take_picture())

                camera_box.controls.append(ft.FilledButton("Capture", icon=ft.Icons.CAMERA_ALT, on_click=capture))
            except Exception:
                camera_box.controls = []
            app.page.update()

        buttons = [ft.FilledButton("Look up", icon=ft.Icons.SEARCH, on_click=look_up)]
        if bc.available():
            buttons.append(ft.OutlinedButton("Use a photo", icon=ft.Icons.IMAGE, on_click=from_photo))
        code.on_submit = look_up
        content.controls = [header("Scan barcode", back=True), camera_box, ft.Row([code]), ft.Row(buttons, wrap=True),
                            scan_status]
        app.page.update()
        if bc.available() and not app.page.web:
            app.page.run_task(start_camera)

    # ---------- amount + preview ----------
    def detail(f: Food, entry: dict | None = None) -> None:
        q0, u0 = 1.0, "0"
        if entry:  # start from what was logged
            grams0 = float(entry["grams"] or 0)
            match = next((i for i, sv in enumerate(f.servings) if sv.label and sv.label in (entry["amount_label"] or "")), None)
            if match is None:  # e.g. logged as "172 g" when 172 g is exactly one breast
                match = next((i for i, sv in enumerate(f.servings)
                              if sv.g and 0.25 <= grams0 / sv.g <= 20 and abs(grams0 / sv.g * 4 - round(grams0 / sv.g * 4)) < 0.02), None)
            q0, u0 = (grams0 / f.servings[match].g, str(match)) if match is not None else (grams0, "g")
        qty = th.num_field("Amount", fmt(q0), expand=1, autofocus=True)
        unit = ft.Dropdown(label="Unit", value=u0, dense=True, expand=2, border_radius=10,
                           options=[ft.DropdownOption(key=str(i), text=s.label) for i, s in enumerate(f.servings)]
                                   + [ft.DropdownOption(key="g", text="grams")])
        meal_dd = ft.Dropdown(label="Meal", value=entry["meal"] if entry else meal, dense=True, border_radius=10,
                              options=[ft.DropdownOption(key=k, text=v) for k, v in MEAL_LABELS.items()])
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
            boxes = [ft.Container(ft.Column([ft.Text(fmt(n[k]), size=18, font_family=th.FONT_BOLD), th.muted(lbl, 11)],
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
            if entry:
                app.store.update_entry(entry["id"], meal=meal_dd.value, grams=grams, amount_label=label,
                                       n=scale_nutrients(f.per100, grams))
                close()
                app.render()
                app.toast(f"Updated {f.name}")
                return
            if f.source in ("OFF", "USDA"):
                app.svc.remember_food(f)  # keep a copy so it works offline and shows in recents
            app.store.add_entry(app.date, meal, f.name, scale_nutrients(f.per100, grams), food_id=f.id, grams=grams,
                                amount_label=label)
            close()
            app.render()

        qty.on_change = update_preview
        qty.on_submit = add
        unit.on_select = update_preview
        if entry:
            content.controls = [header(f.name), ft.Row([qty, unit], spacing=10), meal_dd, preview,
                                ft.Row([ft.FilledButton("Save changes", icon=ft.Icons.CHECK, on_click=add, expand=True),
                                        ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _: delete(entry))])]
        else:
            content.controls = [header(f.name, back=True), ft.Row([qty, unit], spacing=10), preview,
                                ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add, width=float("inf"))]
        update_preview()

    def delete(entry: dict) -> None:
        app.store.remove_entry(entry["id"])
        close()
        app.render()
        app.toast(f"Removed {entry['name']}", undo=lambda: app.store.restore_entry(entry))

    # ---------- quick add ----------
    def quick(entry: dict | None = None) -> None:
        name = ft.TextField(label="Description", value=entry["name"] if entry else "Quick add", dense=True, border_radius=10)
        fields = {k: th.num_field(lbl, fmt(entry["n"].get(k, 0)) if entry else (0 if k != "kcal" else None), expand=True)
                  for k, lbl in (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"))}
        meal_dd = ft.Dropdown(label="Meal", value=entry["meal"] if entry else meal, dense=True, border_radius=10,
                              options=[ft.DropdownOption(key=k, text=v) for k, v in MEAL_LABELS.items()])

        def add(_):
            n = empty_nutrients()
            for k, fld in fields.items():
                n[k] = th.parse_num(fld.value)
            if n["kcal"] <= 0:
                fields["kcal"].error = "Required"
                app.page.update()
                return
            if entry:
                app.store.update_entry(entry["id"], meal=meal_dd.value, name=name.value.strip() or "Quick add", n=n)
            else:
                app.store.add_entry(app.date, meal, name.value.strip() or "Quick add", n, amount_label="quick add")
            close()
            app.render()

        content.controls = [header("Edit quick add" if entry else "Quick add", back=not entry), name,
                            ft.Row([fields["kcal"], fields["protein"]], spacing=10),
                            ft.Row([fields["carbs"], fields["fat"]], spacing=10),
                            *([meal_dd] if entry else []),
                            th.muted("Good for restaurant meals. Quick adds don't include micronutrients.", 12)]
        if entry:
            content.controls.append(ft.Row([ft.FilledButton("Save changes", icon=ft.Icons.CHECK, on_click=add, expand=True),
                                            ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _: delete(entry))]))
        else:
            content.controls.append(ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add, width=float("inf")))
        app.page.update()

    if edit:
        food = app.svc.food_for_entry(edit)
        detail(food, edit) if food else quick(edit)
    else:
        picker()
    app.page.show_dialog(sheet)


def _skeleton() -> ft.Control:
    """Shimmering placeholder row while online results load."""
    def block(w, h):
        return ft.Container(width=w, height=h, border_radius=6, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
    row = ft.Container(ft.Column([block(220, 14), block(140, 10)], spacing=6), padding=ft.Padding.symmetric(vertical=10, horizontal=16))
    try:
        return ft.Shimmer(content=row, base_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                          highlight_color=ft.Colors.SURFACE_CONTAINER_LOW)
    except Exception:
        return row
