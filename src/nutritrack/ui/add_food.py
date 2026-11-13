"""Add-food bottom sheet: local + online search, barcode scanning, amount picker with live preview, and quick add."""
from __future__ import annotations

import asyncio
from datetime import date
from typing import TYPE_CHECKING

import flet as ft

from ..core import barcode as bc
from ..core import online
from ..core.foods import Food
from ..core.nutrition import MICROS, empty_nutrients, fmt, scale_nutrients
from ..core.pacing import MEAL_LABELS
from ..diagnostics import log
from ..service import today_key
from . import motion
from . import theme as th

if TYPE_CHECKING:
    from .app import App



def open_sheet(app: "App", meal: str, edit: dict | None = None, food: Food | None = None) -> None:
    """Add food to a meal, or (with `edit`) change a logged entry's amount, unit or meal."""
    content = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    height = min(680, max(480, int((getattr(app.page, "height", None) or 760) * 0.88)))
    sheet = ft.BottomSheet(
        content=ft.Container(content=content, padding=ft.Padding.only(left=16, right=16, top=8, bottom=24), height=height),
        show_drag_handle=True, scrollable=True, draggable=True)
    day_note = "" if app.date == today_key() else f" · {date.fromisoformat(app.date).strftime('%a %d %b')}"

    def close():
        app.page.pop_dialog()

    def header(title: str, back: bool = False) -> ft.Control:
        left = [ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: picker(), tooltip="Back to search")] if back else []
        return ft.Row(left + [ft.Text(title, size=th.T.HEADLINE, font_family=th.FONT_BOLD, expand=True, max_lines=2,
                                      overflow=ft.TextOverflow.ELLIPSIS),
                              ft.IconButton(ft.Icons.CLOSE, on_click=lambda _: close(), tooltip="Close")])

    def logged(name: str, entry_id: str, target_meal: str) -> None:
        """Every add confirms itself and can be undone."""
        motion.haptic("light")
        close()
        app.render()
        app.toast(f"Added {name} to {MEAL_LABELS[target_meal].lower()}",
                  undo=lambda: app.store.remove_entry(entry_id))

    # ---------- search ----------
    results = ft.Column(spacing=2)
    BADGES = {"OFF": ("Brand label", "#8a6a4a"), "recipe": ("Recipe", th.ACCENT), "custom": ("My food", th.SHIELD)}

    def badge(f: Food) -> ft.Control | None:
        if f.source == "USDA" and f.id.startswith("usda-"):
            return th.chip("✓ Verified", th.STATUS_COLORS["met"])
        if f.source in BADGES:
            return th.chip(*BADGES[f.source])
        return None

    def food_row(f: Food, fetch_full: bool = False, last: tuple[float, str] | None = None) -> ft.Control:
        sv = f.servings[0]
        grams, label = last if last else (sv.g, sv.label)
        kcal = fmt(f.per100["kcal"] * grams / 100)
        b = badge(f)

        def quick_log(_):
            eid = app.store.add_entry(app.date, meal, f.name, scale_nutrients(f.per100, grams), food_id=f.id, grams=grams,
                                      amount_label=label)
            logged(f.name, eid, meal)

        return ft.Container(ft.Row([
            ft.Column([ft.Text(f.name, size=th.T.BODY - 1, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                       ft.Row([th.muted(f"{label} · {kcal} kcal", th.T.CAPTION), *([b] if b else [])], spacing=6, wrap=True)],
                      spacing=2, expand=True),
            *([ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=th.ACCENT, tooltip=f"Log {label} now", on_click=quick_log)]
              if last else [ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=th.MUTED, size=18)]),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=4, vertical=8), border_radius=th.R.SM, ink=True,
            on_click=lambda _, food=f: (app.page.run_task(open_full, food) if fetch_full else detail(food)))

    async def open_full(f: Food) -> None:
        """Search hits carry fewer nutrients than the product page, so fetch the full product before showing it."""
        status.value = "Loading product…"
        app.page.update()
        try:
            full = await asyncio.to_thread(app.svc.full_food, f)
        except Exception:
            log.exception("loading full product failed")
            full = None
        detail(full or f)

    status = th.muted("", th.T.CAPTION)
    online_head = ft.Column(spacing=4)
    online_results = ft.Column(spacing=2)
    query = {"q": "", "token": 0, "done": set()}

    async def search_online(source: str = "off", auto: bool = False) -> None:
        q = query["q"].strip()
        if len(q) < 2 or (q, source) in query["done"]:
            return
        query["done"].add((q, source))
        status.value = "Searching " + ("lab-verified foods…" if source == "usda" else "brands…")
        if source == "off":
            online_results.controls = [_skeleton() for _ in range(3)]
        app.page.update()
        try:
            hits = await asyncio.to_thread(app.svc.search_online, q, source)
        except Exception as ex:
            log.exception("online search failed")
            status.value = f"Couldn't search online ({ex}). Check your connection."
            app.page.update()
            return
        if query["q"].strip() != q:  # the user kept typing
            return
        rows = [food_row(f, fetch_full=True) for f in hits]
        if source == "usda":  # add verified results after the brand ones
            online_results.controls = query.get("off_rows", []) + rows
            more.visible = False
        else:
            query["off_rows"] = rows
            online_results.controls = rows
            more.visible = (q, "usda") not in query["done"]
        status.value = "" if online_results.controls else f"Nothing online for “{q}”. Try fewer words, or create it under Foods."
        app.page.update()

    more = ft.TextButton("More results from USDA (lab-verified)", icon=ft.Icons.VERIFIED_OUTLINED, visible=False,
                         on_click=lambda _: app.page.run_task(search_online, "usda"))

    async def debounced(token: int) -> None:
        await asyncio.sleep(0.6)
        if token == query["token"]:
            await search_online("off", auto=True)

    def fill_results(q: str) -> None:
        tokens = [t for t in q.lower().split() if t]
        foods = app.svc.all_foods()
        items: list[ft.Control] = []
        if not tokens:
            online_head.controls, online_results.controls, status.value, more.visible = [], [], "", False
            meal_plans = [p for p in app.store.plans() if p.kind == "meal"]
            if meal_plans:
                items.append(th.label("Saved meals"))
                items.append(ft.Row([ft.Chip(label=ft.Text(f"{p.name} · {fmt(p.totals()['kcal'])} kcal", size=th.T.CAPTION),
                                             leading=ft.Icon(ft.Icons.BOOKMARK, size=16),
                                             on_click=lambda _, p=p: log_plan(p)) for p in meal_plans[:8]],
                                    wrap=True, spacing=6, run_spacing=6))
            recents = [f for f in (app.svc.find_food(i) for i in app.store.recents()) if f]
            if recents:
                last = app.store.last_amounts([f.id for f in recents])
                items.append(ft.Row([th.label("Recent"), th.muted("tap + to log the same amount again", th.T.CAPTION)],
                                    spacing=8, wrap=True))
                items += [food_row(f, last=last.get(f.id)) for f in recents]
            items.append(th.label("Common foods"))
            items += [food_row(f) for f in sorted(foods, key=lambda f: f.name)]
        else:
            hits = [f for f in foods if all(t in f.name.lower() or t in f.category.lower() for t in tokens)]
            items = [th.label("Your foods")] + [food_row(f) for f in hits] if hits else []
            online_head.controls = [th.label("Online")]
            query["token"] += 1
            if len(q.strip()) >= 2:
                app.page.run_task(debounced, query["token"])
        results.controls = items

    def log_plan(plan) -> None:
        n = app.svc.apply_plan(plan, app.date, meal)
        close()
        app.render()
        app.toast(f"Logged {n} item{'s' if n != 1 else ''} from “{plan.name}”")

    def picker() -> None:
        def on_change(e):
            query["q"] = e.control.value
            fill_results(e.control.value)
            app.page.update()

        search = ft.TextField(hint_text="Search foods and brands", prefix_icon=ft.Icons.SEARCH, expand=True,
                              autofocus=True, dense=True, border_radius=12, on_change=on_change,
                              on_submit=lambda _: app.page.run_task(search_online, "off"), value=query["q"])
        fill_results(query["q"])
        content.controls = [
            header(f"Add to {MEAL_LABELS[meal]}{day_note}"), ft.Row([search]),
            ft.Row([ft.FilledTonalButton("Scan barcode", icon=ft.Icons.QR_CODE_SCANNER, on_click=lambda _: scan()),
                    ft.TextButton("Quick add calories", icon=ft.Icons.BOLT, on_click=lambda _: quick())], wrap=True, spacing=4),
            results, online_head, status, online_results, more,
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
            boxes = [ft.Container(ft.Column([ft.Text(fmt(n[k]), size=18, font_family=th.FONT_BOLD), th.muted(lbl, th.T.CAPTION)],
                                            spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                  expand=True, padding=10, border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
                     for k, lbl in (("kcal", "kcal"), ("protein", "protein"), ("carbs", "carbs"), ("fat", "fat"))]
            good = sorted(((n[m.key] / t.micros[m.key].target, m) for m in MICROS if not m.limit), key=lambda x: -x[0])
            good = [(p, m) for p, m in good if p >= 0.1][:4]
            preview.controls = [ft.Row(boxes, spacing=8)]
            if good:
                preview.controls.append(ft.Row([th.muted("Good source of:", th.T.CAPTION)] +
                                                [th.chip(f"{m.label} {round(p * 100)}%", th.STATUS_COLORS["met"]) for p, m in good],
                                                wrap=True, spacing=6))
            app.page.update()

        def add(_):
            grams, label = amount()
            if grams <= 0:
                qty.error = "Enter an amount"
                app.page.update()
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
            eid = app.store.add_entry(app.date, meal, f.name, scale_nutrients(f.per100, grams), food_id=f.id, grams=grams,
                                      amount_label=label)
            logged(f.name, eid, meal)

        def set_qty(v: float) -> None:
            qty.value, qty.error = fmt(v), None
            update_preview()

        steps = ft.Row([ft.OutlinedButton(lbl, on_click=lambda _, v=v: set_qty(v),
                                          style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12)))
                        for lbl, v in (("½", 0.5), ("1", 1), ("1½", 1.5), ("2", 2))], spacing=6, wrap=True)
        qty.on_change = update_preview
        qty.on_submit = add
        unit.on_select = update_preview
        if entry:
            content.controls = [header(f.name), ft.Row([qty, unit], spacing=10), meal_dd, preview,
                                ft.Row([ft.FilledButton("Save changes", icon=ft.Icons.CHECK, on_click=add, expand=True),
                                        ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _: delete(entry))])]
        else:
            b = badge(f)
            content.controls = [header(f.name, back=True), *([ft.Row([b])] if b else []), ft.Row([qty, unit], spacing=10),
                                steps, preview,
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
                eid = app.store.add_entry(app.date, meal, name.value.strip() or "Quick add", n, amount_label="quick add")
                logged(name.value.strip() or "Quick add", eid, meal)
                return
            close()
            app.render()

        content.controls = [header("Edit quick add" if entry else "Quick add", back=not entry), name,
                            ft.Row([fields["kcal"], fields["protein"]], spacing=10),
                            ft.Row([fields["carbs"], fields["fat"]], spacing=10),
                            *([meal_dd] if entry else []),
                            th.muted("Good for eating out: a rough number beats no number. Quick adds don't count vitamins and minerals.",
                                     th.T.CAPTION)]
        if entry:
            content.controls.append(ft.Row([ft.FilledButton("Save changes", icon=ft.Icons.CHECK, on_click=add, expand=True),
                                            ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _: delete(entry))]))
        else:
            content.controls.append(ft.FilledButton("Add", icon=ft.Icons.CHECK, on_click=add, width=float("inf")))
        app.page.update()

    if edit:
        entry_food = app.svc.food_for_entry(edit)
        detail(entry_food, edit) if entry_food else quick(edit)
    elif food is not None:
        detail(food)
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
