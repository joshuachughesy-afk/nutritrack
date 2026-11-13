"""Profile & targets: onboarding form, computed targets, carb cycling and training recommendations."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import (ACTIVITY, GOALS, Profile, cm_to_in, compute_targets, day_targets, in_to_cm, kg_to_lb,
                              lb_to_kg)
from ..core.supplements import daily_creatine
from ..core.training import LOADS, TRAINING
from . import theme as th

if TYPE_CHECKING:
    from .app import App

WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def build(app: "App") -> list[ft.Control]:
    existing = app.store.profile()
    p = existing or Profile()
    imperial = app.store.units == "imperial"
    o = p.overrides or {}

    units = ft.SegmentedButton(segments=[ft.Segment(value="metric", label=ft.Text("Metric · kg, cm, ml")),
                                         ft.Segment(value="imperial", label=ft.Text("Imperial · lb, ft, oz"))],
                               selected=["imperial" if imperial else "metric"], show_selected_icon=False)
    sex = ft.SegmentedButton(segments=[ft.Segment(value="male", label=ft.Text("Male")),
                                       ft.Segment(value="female", label=ft.Text("Female"))],
                             selected=[p.sex], show_selected_icon=False)
    age = th.num_field("Age", p.age, expand=True)
    weight_kg = th.num_field("Weight", f"{p.weight_kg:.1f}", suffix="kg", expand=True)
    weight_lb = th.num_field("Weight", f"{kg_to_lb(p.weight_kg):.1f}", suffix="lb", expand=True)
    height_cm = th.num_field("Height", round(p.height_cm), suffix="cm", expand=True)
    total_in = cm_to_in(p.height_cm)
    height_ft = th.num_field("Height", int(total_in // 12), suffix="ft", expand=True)
    height_in = th.num_field("", round(total_in % 12), suffix="in", expand=True)

    def dd(label, options: dict, value):
        return ft.Dropdown(label=label, value=value, dense=True, border_radius=10, expand=True,
                           options=[ft.DropdownOption(key=k, text=v) for k, v in options.items()])

    activity = dd("Activity", {k: v[0] for k, v in ACTIVITY.items()}, p.activity)
    goal = dd("Goal", {k: v[0] for k, v in GOALS.items()}, p.goal)
    training = dd("Training type", {k: v.name for k, v in TRAINING.items()}, p.training_type)
    training_desc = th.muted("", 12)
    load_value = {"v": p.training_load}
    load_chips: list[ft.Chip] = []

    def pick_load(key: str) -> None:
        load_value["v"] = key
        for c in load_chips:
            c.selected = c.data == key
        app.page.update()

    for k, v in LOADS.items():
        load_chips.append(ft.Chip(label=ft.Text(f"{v['label']} · {v['detail']}", size=12), data=k,
                                  selected=k == p.training_load, show_checkmark=False,
                                  on_select=lambda _, key=k: pick_load(key)))
    load = ft.Row(load_chips, wrap=True, spacing=6, run_spacing=6)
    load_hint = th.muted("Hours of training per week. Sets where you sit within each macro range.", 11)
    days = [ft.Checkbox(label=d, value=i in p.training_days) for i, d in enumerate(WEEKDAYS)]
    cycling = ft.Switch(label="Carb cycling: more carbs on training days, fewer on rest days (same weekly total)",
                        value=p.carb_cycling)
    ov = {k: th.num_field(lbl, o.get(k), expand=True) for k, lbl in
          (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"))}

    metric_box = ft.Row([weight_kg, height_cm], spacing=10)
    imperial_box = ft.Row([weight_lb, height_ft, height_in], spacing=10)

    def sync(*_):
        imp = list(units.selected)[0] == "imperial"
        metric_box.visible, imperial_box.visible = not imp, imp
        tr = TRAINING[training.value]
        training_desc.value = (f"{tr.examples}. {tr.emphasis}: carbs {tr.carbs[0]:g}–{tr.carbs[1]:g} · "
                               f"protein {tr.protein[0]:g}–{tr.protein[1]:g} · fat {tr.fat[0]:g}–{tr.fat[1]:g} g/kg")
        app.page.update()

    units.on_change = sync
    training.on_select = sync
    metric_box.visible, imperial_box.visible = not imperial, imperial
    tr0 = TRAINING[training.value]
    training_desc.value = (f"{tr0.examples}. {tr0.emphasis}: carbs {tr0.carbs[0]:g}–{tr0.carbs[1]:g} · "
                           f"protein {tr0.protein[0]:g}–{tr0.protein[1]:g} · fat {tr0.fat[0]:g}–{tr0.fat[1]:g} g/kg")

    def save(_):
        imp = list(units.selected)[0] == "imperial"
        w = lb_to_kg(th.parse_num(weight_lb.value)) if imp else th.parse_num(weight_kg.value)
        h = in_to_cm(th.parse_num(height_ft.value) * 12 + th.parse_num(height_in.value)) if imp else th.parse_num(height_cm.value)
        a = int(th.parse_num(age.value))
        errors = {age: a < 18 or a > 100, (weight_lb if imp else weight_kg): w < 30, (height_ft if imp else height_cm): h < 120}
        for fld, bad in errors.items():
            fld.error = "Check this value" if bad else None
        if any(errors.values()):
            app.page.update()
            return
        new = Profile(sex=list(sex.selected)[0], age=a, height_cm=h, weight_kg=w, activity=activity.value, goal=goal.value,
                      training_type=training.value, training_load=load_value["v"],
                      training_days=tuple(i for i, c in enumerate(days) if c.value), carb_cycling=bool(cycling.value),
                      overrides={k: th.parse_num(f.value) for k, f in ov.items() if th.parse_num(f.value) > 0})
        first = existing is None
        app.store.save_profile(new)
        app.store.set("units", "imperial" if imp else "metric")
        if first:
            app.go("today")
        else:
            app.render()
            app.toast("Targets updated")

    form = th.card(
        th.heading("Units"), units,
        th.heading("About you"), th.muted("Sex is used for BMR and nutrient targets.", 12), sex,
        ft.Row([age], spacing=10), metric_box, imperial_box,
        ft.Row([activity], spacing=10), ft.Row([goal], spacing=10),
        th.heading("Training"), ft.Row([training]), training_desc,
        th.muted("Training load", 13, font_family=th.FONT_SEMI), load, load_hint,
        th.muted("Usual training days (you can switch any day on the Today screen)", 13, font_family=th.FONT_SEMI),
        ft.Row(days, wrap=True, spacing=0), cycling,
        ft.ExpansionTile(title=ft.Text("Manual overrides (leave blank for automatic)", size=14), tile_padding=0,
                         controls=[ft.Row([ov["kcal"], ov["protein"]], spacing=10), ft.Row([ov["carbs"], ov["fat"]], spacing=10)],
                         controls_padding=ft.Padding.only(bottom=8)),
        ft.FilledButton("Save changes" if existing else "Calculate my targets", icon=ft.Icons.CHECK, on_click=save),
        spacing=12,
    )

    out: list[ft.Control] = [ft.Text("Profile & targets" if existing else "Welcome to NutriTrack", size=22,
                                     font_family=th.FONT_BOLD)]
    if not existing:
        out.append(th.muted("Tell us about yourself to calculate calorie, macro and micronutrient targets. "
                            "Everything is stored only on this device.", 14))
    out.append(form)
    if existing:
        out += _targets(app, p) + [_reminders_card(app), _training_card(app, p), _appearance_card(app),
                                   _databases_card(app), _data_card(app), _about_card(app)]
    return out


def _targets(app: "App", p: Profile) -> list[ft.Control]:
    creatine = daily_creatine(app.store.supplements())
    tt, rt = day_targets(p, True, creatine), day_targets(p, False, creatine)

    def stat(label, value):
        return ft.Container(ft.Column([th.muted(label, 12), ft.Text(value, size=18, font_family=th.FONT_BOLD)], spacing=0),
                            padding=10, border_radius=10, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, expand=True)

    items: list[ft.Control] = [
        th.heading("Your targets"),
        ft.Row([stat("BMR", f"{tt.bmr:,}"), stat("TDEE", f"{tt.tdee:,}"), stat("Daily target", f"{tt.kcal if not tt.cycling else round((tt.kcal * len(p.training_days) + rt.kcal * (7 - len(p.training_days))) / 7):,} kcal")], spacing=8),
    ]
    if tt.floor_applied:
        items.append(_note("Your target was raised to the minimum safe floor. Use a manual override only with professional guidance."))
    items += [_note(n) for n in tt.notes]
    if tt.cycling:
        def row(label, t):
            return ft.DataRow(cells=[ft.DataCell(ft.Text(label)), ft.DataCell(ft.Text(f"{t.kcal:,}")),
                                     ft.DataCell(ft.Text(f"{t.carbs} g ({t.gkg['carbs']:.1f}/kg)")),
                                     ft.DataCell(ft.Text(f"{t.protein} g")), ft.DataCell(ft.Text(f"{t.fat} g")),
                                     ft.DataCell(ft.Text(app.svc.water_fmt(t.water_ml)))])
        items.append(ft.Row([ft.DataTable(
            columns=[ft.DataColumn(ft.Text(h)) for h in ("Carb cycling", "Calories", "Carbs", "Protein", "Fat", "Water")],
            rows=[row("🏋️ Training", tt), row("🛌 Rest", rt)], column_spacing=16, horizontal_margin=4)],
            scroll=ft.ScrollMode.AUTO))
    return [th.card(*items)]


def _note(text: str) -> ft.Control:
    return ft.Container(ft.Text(text, size=13), padding=10, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.14, th.STATUS_COLORS["low"]))


def _training_card(app: "App", p: Profile) -> ft.Control:
    t = day_targets(p, True)
    tr = t.training
    order = [("carbs", "Carbs"), ("protein", "Protein"), ("fat", "Fat")] if tr.carb_first else \
            [("protein", "Protein"), ("carbs", "Carbs"), ("fat", "Fat")]
    base = compute_targets(p)
    rows = []
    for key, label in order:
        g, gkg, (lo, hi) = getattr(base, key), base.gkg[key], getattr(tr, key)
        pct = round(g * (9 if key == "fat" else 4) / base.kcal * 100)
        ok = lo - 0.05 <= gkg <= hi + 0.05
        rows.append(ft.DataRow(cells=[
            ft.DataCell(ft.Row([th.dot(th.MACRO_COLORS[key]), ft.Text(label, font_family=th.FONT_SEMI)], spacing=6)),
            ft.DataCell(ft.Text(f"{g} g", font_family=th.FONT_BOLD)), ft.DataCell(ft.Text(f"{gkg:.1f}")),
            ft.DataCell(th.muted(f"{lo:g}–{hi:g}")), ft.DataCell(th.muted(f"{pct}%")),
            ft.DataCell(th.chip("in range" if ok else ("below" if gkg < lo else "above"),
                                th.STATUS_COLORS["met" if ok else "low"]))]))
    compare = [ft.DataRow(selected=k == t.training_id, cells=[
        ft.DataCell(ft.Text(x.name, size=13)), ft.DataCell(ft.Text(f"{x.carbs[0]:g}–{x.carbs[1]:g}")),
        ft.DataCell(ft.Text(f"{x.protein[0]:g}–{x.protein[1]:g}")), ft.DataCell(ft.Text(f"{x.fat[0]:g}–{x.fat[1]:g}")),
        ft.DataCell(th.chip(x.emphasis, th.emphasis_color(x.emphasis)))]) for k, x in TRAINING.items()]
    return th.card(
        th.heading("Macro recommendations"),
        ft.Row([th.chip(f"{tr.name} · {tr.emphasis}", th.emphasis_color(tr.emphasis))], wrap=True),
        ft.Row([ft.DataTable(columns=[ft.DataColumn(ft.Text(h)) for h in ("", "Target", "g/kg", "Recommended", "% kcal", "")],
                             rows=rows, column_spacing=14, horizontal_margin=4)], scroll=ft.ScrollMode.AUTO),
        ft.Text(f"Fueling tips for {tr.name.lower()}", font_family=th.FONT_SEMI, size=14),
        *[ft.Row([ft.Text("•"), ft.Text(tip, size=13, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START)
          for tip in tr.tips],
        ft.ExpansionTile(title=ft.Text("Compare all training types (g/kg/day)", size=14), tile_padding=0, controls=[
            ft.Row([ft.DataTable(columns=[ft.DataColumn(ft.Text(h)) for h in ("Training type", "Carbs", "Protein", "Fat", "Emphasis")],
                                 rows=compare, column_spacing=14, horizontal_margin=4)], scroll=ft.ScrollMode.AUTO)]),
        th.muted("Ranges are based on the ACSM/AND/DC joint position on athletic nutrition (2016), ISSN position stands "
                 "on protein (2017) and nutrient timing (2017), and Helms et al. (2014). Hybrid ranges combine endurance "
                 "carb guidance with resistance-training protein guidance. BMR uses Mifflin-St Jeor; micronutrient "
                 "targets are the NIH Dietary Reference Intakes. This is not medical advice.", 11),
    )


def _hhmm(v: str) -> str | None:
    v = (v or "").strip()
    try:
        h, m = v.split(":")
        if 0 <= int(h) < 24 and 0 <= int(m) < 60 and len(m) == 2:
            return f"{int(h):02d}:{m}"
    except ValueError:
        pass
    return None


def _reminders_card(app: "App") -> ft.Control:
    sched, rs = app.store.schedule(), app.store.reminders()
    notifier = app.notifier

    def tf(label, value):
        return ft.TextField(label=label, value=value or "", hint_text="HH:MM", dense=True, border_radius=10, expand=True,
                            keyboard_type=ft.KeyboardType.DATETIME)

    wake, sleep = tf("Wake up", sched["wake"]), tf("Bedtime", sched["sleep"])
    meals = {k: tf(k.title(), sched[k]) for k in ("breakfast", "lunch", "dinner")}
    enabled = ft.Switch(label="Send me reminders", value=rs["enabled"])
    supps = ft.Checkbox(label="Supplement doses at their scheduled times", value=rs["supplements"])
    water = ft.Checkbox(label="Water nudges when I'm behind", value=rs["water"])
    every = ft.Dropdown(label="Check water every", value=str(rs["water_every_h"]).rstrip("0").rstrip("."), dense=True, width=170,
                        border_radius=10, options=[ft.DropdownOption(key=k, text=f"{k} h") for k in ("1", "1.5", "2", "3")])
    checks = [tf(f"Check-in {i + 1}", rs["checkins"][i] if i < len(rs["checkins"]) else "") for i in range(3)]
    if notifier.can_schedule:
        how = "Reminders are scheduled with your phone's system, so they arrive even when NutriTrack is closed."
    else:
        how = ("Here, reminders appear while NutriTrack is open. Install the app on your phone (see README) so the "
               "system can deliver them even when it's closed.")

    async def save(_):
        fields = [wake, sleep, *meals.values()]
        bad = False
        for f in fields:
            f.error = None if _hhmm(f.value) else "Use HH:MM"
            bad |= f.error is not None
        cis = []
        for f in checks:
            f.error = None
            if (f.value or "").strip():
                v = _hhmm(f.value)
                if v:
                    cis.append(v)
                else:
                    f.error, bad = "Use HH:MM", True
        if bad:
            app.page.update(); return
        app.store.set("schedule", {"wake": _hhmm(wake.value), "sleep": _hhmm(sleep.value),
                                   **{k: _hhmm(f.value) for k, f in meals.items()}})
        app.store.set("reminders", {"enabled": bool(enabled.value), "supplements": bool(supps.value), "water": bool(water.value),
                                    "water_every_h": float(every.value or 2), "checkins": sorted(cis)})
        if enabled.value and not await notifier.request_permission() and notifier.can_schedule:
            app.toast("Notifications are blocked. Allow them in your phone's settings.")
        app.render()
        app.toast("Reminders on" if enabled.value else "Reminders saved")

    return th.card(
        th.heading("Schedule & reminders"),
        th.muted("Your meal times set the pace: about 30 minutes after lunch you'd expect about 55% of the day's food. Water "
                 "spreads evenly until an hour before bed.", 12),
        ft.Row([wake, sleep], spacing=10), ft.Row(list(meals.values()), spacing=10),
        enabled, supps, ft.Row([water, every], wrap=True),
        th.muted("Daily check-ins: macro and water pace. The evening one also lists micronutrient gaps.", 12),
        ft.Row(checks, spacing=8),
        th.muted(how, 12),
        ft.Row([ft.FilledButton("Save reminders", icon=ft.Icons.NOTIFICATIONS_ACTIVE, on_click=save),
                ft.TextButton("Send a test", on_click=lambda _: app.page.run_task(notifier.test))], wrap=True),
    )


def _appearance_card(app: "App") -> ft.Control:
    mode = app.store.get("theme_mode", "system")
    seg = ft.SegmentedButton(
        segments=[ft.Segment(value="system", label=ft.Text("System"), icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO)),
                  ft.Segment(value="light", label=ft.Text("Light"), icon=ft.Icon(ft.Icons.LIGHT_MODE)),
                  ft.Segment(value="dark", label=ft.Text("Dark"), icon=ft.Icon(ft.Icons.DARK_MODE))],
        selected=[mode], show_selected_icon=False, on_change=lambda e: app.set_theme_mode(list(e.control.selected)[0]))
    hemi = ft.SegmentedButton(
        segments=[ft.Segment(value="north", label=ft.Text("Northern")), ft.Segment(value="south", label=ft.Text("Southern")),
                  ft.Segment(value="off", label=ft.Text("Always summer"))],
        selected=[app.store.get("hemisphere", "north")], show_selected_icon=False,
        on_change=lambda e: (app.store.set("hemisphere", list(e.control.selected)[0]), app.render()))
    return th.card(th.heading("Appearance", icon=ft.Icons.PALETTE_OUTLINED), ft.Row([seg], wrap=True),
                   ft.Text("Seasons for your trees", size=14, font_family=th.FONT_SEMI),
                   th.muted(f"Your garden follows the seasons: blossom in spring, gold in autumn, snow in winter. "
                            f"It's {app.svc.season()} now.", 12),
                   ft.Row([hemi], wrap=True))


def _about_card(app: "App") -> ft.Control:
    """Version, environment, recent log and a copyable report for bug reports."""
    import os

    from .. import diagnostics

    env = diagnostics.environment(app.page)
    log_tail = diagnostics.tail(12)

    async def export_log(_):
        try:
            data = diagnostics.report(app.store, app.page, lines=400).encode()
            await ft.FilePicker().save_file(dialog_title="Save diagnostics", file_name="nutritrack-diagnostics.md", src_bytes=data)
        except Exception as ex:
            diagnostics.log.exception("export log failed")
            app.toast(f"Couldn't save: {ex}")

    def boom(_):  # developer check of the crash guard (NUTRITRACK_DEBUG=1)
        raise RuntimeError("Simulated error from the diagnostics card")

    actions: list[ft.Control] = [
        ft.FilledTonalButton("Copy diagnostics", icon=ft.Icons.CONTENT_COPY,
                             on_click=lambda _: app.copy(diagnostics.report(app.store, app.page))),
        ft.OutlinedButton("Save diagnostics", icon=ft.Icons.DOWNLOAD, on_click=export_log),
    ]
    if os.getenv("NUTRITRACK_DEBUG"):
        actions.append(ft.TextButton("Simulate an error", icon=ft.Icons.BUG_REPORT, on_click=boom))
    return th.card(
        th.heading("About & diagnostics", icon=ft.Icons.INFO_OUTLINE),
        th.muted(" · ".join(f"{k} {v}" for k, v in env.items()), 12),
        th.muted("Desktop shortcuts: Alt+← / Alt+→ change day · Alt+T today · Alt+N log food · Alt+1–5 switch tabs", 12),
        ft.Text("Recent log", size=14, font_family=th.FONT_SEMI),
        ft.Container(ft.Text(log_tail, size=10.5, font_family="monospace", selectable=True), padding=10, border_radius=12,
                     bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
        th.muted(f"Log file: {diagnostics.log_file()}. Found a bug? Copy the diagnostics into a GitHub issue. They include "
                 "versions, record counts and the log, never your food or body data.", 11),
        ft.Row(actions, wrap=True),
    )


def _databases_card(app: "App") -> ft.Control:
    key = ft.TextField(label="USDA FoodData Central API key (optional)", value=app.store.get("usda_api_key") or "",
                       password=True, can_reveal_password=True, dense=True, border_radius=10)

    def save(_):
        app.store.set("usda_api_key", (key.value or "").strip())
        app.toast("USDA key saved" if key.value else "Using USDA's shared demo key")

    return th.card(
        th.heading("Food databases", icon=ft.Icons.TRAVEL_EXPLORE),
        th.muted("Brand search and barcodes use Open Food Facts (free, no key, crowd-sourced). Whole foods use USDA FoodData "
                 "Central (lab-measured, full micronutrients). USDA's shared demo key is often busy, so get your own free key "
                 "at api.data.gov/signup and paste it here. It's stored only on this device.", 12),
        key, ft.FilledButton("Save key", icon=ft.Icons.KEY, on_click=save),
    )


def _data_card(app: "App") -> ft.Control:
    def erase():
        app.store.reset()
        app.go("profile")
        app.toast("All data erased")

    async def export(_):
        from datetime import date
        picker = ft.FilePicker()
        try:
            path = await picker.save_file(dialog_title="Save NutriTrack backup", file_name=f"nutritrack-{date.today()}.json",
                                          allowed_extensions=["json"], src_bytes=app.store.export_json().encode())
            desktop = str(getattr(app.page.platform, "value", "")).lower() in ("windows", "macos", "linux")
            if path and desktop and not app.page.web:  # phones and web save src_bytes themselves
                from pathlib import Path
                Path(path).write_text(app.store.export_json())
            if path or app.page.web:
                app.toast("Backup saved")
        except Exception as ex:
            app.toast(f"Export failed: {ex}")

    async def import_(_):
        picker = ft.FilePicker()
        try:
            files = await picker.pick_files(dialog_title="Choose a NutriTrack backup", allowed_extensions=["json"], with_data=True)
            if not files:
                return
            f = files[0]
            data = f.bytes if f.bytes else open(f.path, "rb").read()
            app.store.import_json(data.decode())
            app.go("today")
            app.toast("Backup restored")
        except Exception as ex:
            app.toast(f"Import failed: {ex}")

    return th.card(
        th.heading("Your data"),
        th.muted(f"Stored on this device in {app.store.path}", 12),
        ft.Row([ft.OutlinedButton("Export backup", icon=ft.Icons.DOWNLOAD, on_click=export),
                ft.OutlinedButton("Import backup", icon=ft.Icons.UPLOAD, on_click=import_),
                ft.OutlinedButton("Erase all data", icon=ft.Icons.DELETE_FOREVER,
                                  on_click=lambda _: app.confirm("Erase all data?", "This cannot be undone.", erase,
                                                                 "Erase"))], wrap=True),
    )
