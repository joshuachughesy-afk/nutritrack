"""Profile: a short menu of settings pages. Each page saves on its own, so nothing is lost when another changes.

Pages: Body & goal · Training · Your targets · Reminders · Appearance · Backup & privacy · Help & feedback.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import (ACTIVITY, GOALS, Profile, cm_to_in, compute_targets, day_targets, in_to_cm, kg_to_lb,
                              lb_to_kg)
from ..core.supplements import daily_creatine
from ..core.training import LOADS, TRAINING
from . import components as cx
from . import theme as th

if TYPE_CHECKING:
    from .app import App

PAGES = {
    "body": ("Body & goal", ft.Icons.ACCESSIBILITY_NEW),
    "training": ("Training", ft.Icons.FITNESS_CENTER),
    "targets": ("Your targets", ft.Icons.TRACK_CHANGES),
    "reminders": ("Reminders", ft.Icons.NOTIFICATIONS_OUTLINED),
    "appearance": ("Appearance", ft.Icons.PALETTE_OUTLINED),
    "data": ("Backup & privacy", ft.Icons.LOCK_OUTLINE),
    "help": ("Help & feedback", ft.Icons.HELP_OUTLINE),
}


def build(app: "App") -> list[ft.Control]:
    p = app.store.profile() or Profile()
    page = app.ui.profile_page
    if page in PAGES:
        builder = {"body": _body, "training": _training, "targets": _targets, "reminders": _reminders,
                   "appearance": _appearance, "data": _data, "help": _help}[page]
        return [cx.back_header(PAGES[page][0], app.back)] + builder(app, p)
    return _menu(app, p)


def _open(app: "App", page: str) -> None:
    app.ui.profile_page = page
    app.render()


def _saved(app: "App", msg: str) -> None:
    app.ui.profile_page = None
    app.render()
    app.toast(msg)


# ---------- menu ----------
def _menu(app: "App", p: Profile) -> list[ft.Control]:
    creatine = daily_creatine(app.store.supplements())
    tt, rt = day_targets(p, True, creatine), day_targets(p, False, creatine)
    tr = TRAINING[p.training_type]
    w = f"{kg_to_lb(p.weight_kg):.0f} lb" if app.svc.imperial else f"{p.weight_kg:.1f} kg"
    rs = app.store.reminders()
    summary = th.card(
        ft.Row([ft.Container(ft.Icon(ft.Icons.PERSON, color=ft.Colors.WHITE, size=28), width=52, height=52, border_radius=26,
                             alignment=ft.Alignment.CENTER,
                             gradient=ft.RadialGradient(colors=["#6fcf8f", "#1f7a4d"], center=ft.Alignment(-0.4, -0.4))),
                ft.Column([ft.Text(tr.name, size=th.T.BODY + 1, font_family=th.FONT_BOLD, max_lines=1,
                                   overflow=ft.TextOverflow.ELLIPSIS),
                           th.muted(f"{w} · {GOALS[p.goal][0].split(' (')[0]} · {len(p.training_days)} training days a week",
                                    th.T.CAPTION)], spacing=0, expand=True)], spacing=12),
        ft.Row([cx.stat_tile("Training day", f"{tt.kcal:,}", "kcal", icon=ft.Icons.FITNESS_CENTER),
                cx.stat_tile("Rest day", f"{rt.kcal:,}", "kcal", icon=ft.Icons.SELF_IMPROVEMENT)], spacing=8),
        spacing=12)
    subs = {
        "body": f"{'Female' if p.sex == 'female' else 'Male'}, {p.age} · {w} · {GOALS[p.goal][0].split(' (')[0].lower()}",
        "training": f"{tr.name.split(' (')[0]} · {LOADS[p.training_load]['detail']}",
        "targets": "Calories, macros, water and how they're worked out",
        "reminders": "On" if rs["enabled"] else "Off: turn on pace nudges and supplement reminders",
        "appearance": {"system": "Match my phone", "light": "Light", "dark": "Dark"}[app.store.get("theme_mode", "system")]
                      + f" · seasons: {app.store.get('hemisphere', 'north').replace('off', 'always summer')}",
        "data": "Stored only on this device · export a backup",
        "help": "Report a problem, version and diagnostics",
    }
    groups = [["body", "training", "targets"], ["reminders", "appearance"], ["data", "help"]]
    out: list[ft.Control] = [cx.screen_title("Profile"), summary]
    for g in groups:
        out.append(th.card(*[cx.nav_tile(PAGES[k][1], PAGES[k][0], subs[k], lambda _, k=k: _open(app, k)) for k in g],
                           padding=6, spacing=0))
    out.append(th.muted("Not medical advice. If you're pregnant, have a medical condition or take medication, set targets "
                        "with a professional.", th.T.CAPTION, text_align=ft.TextAlign.CENTER))
    return out


# ---------- body & goal ----------
def _body(app: "App", p: Profile) -> list[ft.Control]:
    imperial = app.store.units == "imperial"
    unit_state = {"v": "imperial" if imperial else "metric"}
    sex = {"v": p.sex}
    sex_row = ft.Row(spacing=8)

    def set_sex(v):
        sex["v"] = v
        for c in sex_row.controls:
            c.selected = c.data == v
        sex_row.update()

    sex_row.controls = [ft.Chip(label=ft.Text(lbl), data=v, selected=p.sex == v, show_checkmark=False,
                                on_select=lambda _, v=v: set_sex(v)) for v, lbl in (("female", "Female"), ("male", "Male"))]
    age = th.num_field("Age", p.age, suffix="years", expand=True)
    weight_kg = th.num_field("Weight", f"{p.weight_kg:.1f}", suffix="kg", expand=True)
    weight_lb = th.num_field("Weight", f"{kg_to_lb(p.weight_kg):.1f}", suffix="lb", expand=True)
    height_cm = th.num_field("Height", round(p.height_cm), suffix="cm", expand=True)
    total_in = cm_to_in(p.height_cm)
    height_ft = th.num_field("Height", int(total_in // 12), suffix="ft", expand=True)
    height_in = th.num_field("", round(total_in % 12), suffix="in", expand=True)
    metric_box = ft.Column([ft.Row([weight_kg]), ft.Row([height_cm])], spacing=12, visible=not imperial)
    imperial_box = ft.Column([ft.Row([weight_lb]), ft.Row([height_ft, height_in], spacing=10)], spacing=12, visible=imperial)

    def set_units(v):
        unit_state["v"] = v
        metric_box.visible, imperial_box.visible = v == "metric", v == "imperial"
        app.page.update()

    activity = ft.Dropdown(label="Day-to-day activity, including workouts", value=p.activity, dense=True, border_radius=12,
                           expand=True, options=[ft.DropdownOption(key=k, text=v[0]) for k, v in ACTIVITY.items()])
    goal = ft.Dropdown(label="Goal", value=p.goal, dense=True, border_radius=12, expand=True,
                       options=[ft.DropdownOption(key=k, text=v[0]) for k, v in GOALS.items()])
    auto_weight = []

    def save(_):
        imp = unit_state["v"] == "imperial"
        w = lb_to_kg(th.parse_num(weight_lb.value)) if imp else th.parse_num(weight_kg.value)
        h = in_to_cm(th.parse_num(height_ft.value) * 12 + th.parse_num(height_in.value)) if imp else th.parse_num(height_cm.value)
        a = int(th.parse_num(age.value))
        age.error = "18–100" if not 18 <= a <= 100 else None
        (weight_lb if imp else weight_kg).error = "Check weight" if not 30 <= w <= 300 else None
        (height_ft if imp else height_cm).error = "Check height" if not 120 <= h <= 230 else None
        if age.error or (weight_lb if imp else weight_kg).error or (height_ft if imp else height_cm).error:
            app.page.update()
            return
        prof = app.store.profile() or Profile()
        prof.sex, prof.age, prof.weight_kg, prof.height_cm = sex["v"], a, w, h
        prof.activity, prof.goal, prof.auto_weight = activity.value, goal.value, bool(auto_weight[0].value)
        app.store.save_profile(prof)
        app.store.set("units", unit_state["v"])
        _saved(app, "Saved. Your targets are updated.")

    return [
        th.card(cx.tabs([("metric", "Metric"), ("imperial", "Imperial")], unit_state["v"], set_units),
                th.label("Sex"), th.muted("Changes your burn rate and vitamin needs.", th.T.CAPTION), sex_row,
                ft.Row([age]), metric_box, imperial_box,
                cx.toggle_row("Update weight from my weigh-ins", p.auto_weight, sub="Uses your smoothed trend, not a single "
                                                                                    "reading.", ref_out=auto_weight),
                spacing=12),
        th.card(ft.Row([goal]), ft.Row([activity]), spacing=12),
        ft.Row([ft.FilledButton("Save", icon=ft.Icons.CHECK, on_click=save, expand=True)]),
    ]


# ---------- training ----------
def _training(app: "App", p: Profile) -> list[ft.Control]:
    state = {"type": p.training_type, "load": p.training_load, "days": set(p.training_days)}
    desc = th.muted("", th.T.CAPTION)

    def describe():
        tr = TRAINING[state["type"]]
        desc.value = f"{tr.examples}. {tr.emphasis}."

    training = ft.Dropdown(label="What you train for", value=p.training_type, dense=True, border_radius=12, expand=True,
                           options=[ft.DropdownOption(key=k, text=v.name) for k, v in TRAINING.items()],
                           on_select=lambda e: (state.__setitem__("type", e.control.value), describe(), app.page.update()))
    describe()
    load_row = ft.Row(wrap=True, spacing=8, run_spacing=8)

    def set_load(k):
        state["load"] = k
        for c in load_row.controls:
            c.selected = c.data == k
        load_row.update()

    load_row.controls = [ft.Chip(label=ft.Text(f"{v['label']} · {v['detail'].replace('/week', ' a week')}",
                                               size=th.T.CAPTION), data=k, selected=k == p.training_load,
                                 show_checkmark=False, on_select=lambda _, k=k: set_load(k)) for k, v in LOADS.items()]
    cycling = []
    ov_fields = {k: th.num_field(lbl, (p.overrides or {}).get(k), expand=True, hint_text="auto") for k, lbl in
                 (("kcal", "Calories"), ("protein", "Protein (g)"), ("carbs", "Carbs (g)"), ("fat", "Fat (g)"))}

    def save(_):
        prof = app.store.profile() or Profile()
        prof.training_type, prof.training_load = state["type"], state["load"]
        prof.training_days = tuple(sorted(state["days"]))
        prof.carb_cycling = bool(cycling[0].value)
        prof.overrides = {k: th.parse_num(f.value) for k, f in ov_fields.items() if th.parse_num(f.value) > 0}
        app.store.save_profile(prof)
        _saved(app, "Saved. Your targets are updated.")

    t = day_targets(p, True)
    tr = t.training
    base = compute_targets(p)
    order = ["carbs", "protein", "fat"] if tr.carb_first else ["protein", "carbs", "fat"]
    recs: list[ft.Control] = []
    for key in order:
        g, gkg, (lo, hi) = getattr(base, key), base.gkg[key], getattr(tr, key)
        ok = lo - 0.05 <= gkg <= hi + 0.05
        recs.append(cx.metric_row(key.title(), f"{g} g · {gkg:.1f} g/kg (range {lo:g}–{hi:g})",
                                  (gkg - lo * 0.5) / (hi * 1.2 - lo * 0.5) if hi else 0, th.MACRO_COLORS[key],
                                  icon=ft.Icons.CHECK_CIRCLE if ok else ft.Icons.INFO_OUTLINE,
                                  icon_color=th.ink(th.STATUS_COLORS["met"] if ok else "#e08a2b"), height=6))
    return [
        th.card(ft.Row([training]), desc, th.label("Hours of training"), load_row,
                th.label("Usual training days"), cx.day_chips(state["days"], lambda s: state.__setitem__("days", s)),
                th.muted("Switch any single day between training and rest on Today.", th.T.CAPTION),
                cx.toggle_row("More carbs on training days", p.carb_cycling,
                              sub="Fewer on rest days, same weekly total.", ref_out=cycling), spacing=12),
        th.card(th.heading(f"Fuelling for {tr.name.split(' (')[0].lower()}", icon=ft.Icons.BOLT,
                           icon_color=th.emphasis_color(tr.emphasis)),
                *recs,
                *[ft.Row([ft.Text("•"), ft.Text(tip, size=th.T.LABEL, expand=True)],
                         vertical_alignment=ft.CrossAxisAlignment.START) for tip in tr.tips],
                ft.ExpansionTile(title=ft.Text("The science", size=th.T.LABEL + 1, font_family=th.FONT_SEMI), tile_padding=0,
                                 controls=[th.muted(
                                     "Ranges per kg of body weight follow the ACSM/AND/DC position on athletic nutrition "
                                     "(2016), ISSN position stands on protein (2017) and nutrient timing (2017), and Helms "
                                     "et al. (2014). Hybrid combines endurance carb guidance with strength-training "
                                     "protein. Burn uses Mifflin-St Jeor; vitamins and minerals use the NIH Dietary "
                                     "Reference Intakes.", th.T.CAPTION),
                                     *[ft.Row([ft.Text(x.name, size=th.T.CAPTION, expand=True),
                                               th.muted(f"C {x.carbs[0]:g}–{x.carbs[1]:g} · P {x.protein[0]:g}–{x.protein[1]:g}"
                                                        f" · F {x.fat[0]:g}–{x.fat[1]:g}", th.T.CAPTION)])
                                       for x in TRAINING.values()]],
                                 controls_padding=ft.Padding.only(bottom=8)), spacing=10),
        th.card(ft.ExpansionTile(title=ft.Text("Set my own numbers", size=th.T.BODY - 1, font_family=th.FONT_SEMI),
                                 subtitle=th.muted("Leave blank to use the automatic targets", th.T.CAPTION), tile_padding=0,
                                 controls=[ft.Row([ov_fields["kcal"], ov_fields["protein"]], spacing=10),
                                           ft.Row([ov_fields["carbs"], ov_fields["fat"]], spacing=10)],
                                 controls_padding=ft.Padding.only(bottom=8)), padding=ft.Padding.symmetric(horizontal=16, vertical=4)),
        ft.Row([ft.FilledButton("Save", icon=ft.Icons.CHECK, on_click=save, expand=True)]),
    ]


# ---------- targets ----------
def _targets(app: "App", p: Profile) -> list[ft.Control]:
    creatine = daily_creatine(app.store.supplements())
    tt, rt = day_targets(p, True, creatine), day_targets(p, False, creatine)
    n_train = len(p.training_days)
    weekly = round((tt.kcal * n_train + rt.kcal * (7 - n_train)) / 7) if tt.cycling else tt.kcal

    def day_card(label, icon, t):
        return th.card(th.heading(label, f"{t.kcal:,} kcal", icon=icon),
                       *[ft.Row([th.dot(th.MACRO_COLORS[k]), ft.Text(k.title(), size=th.T.LABEL, expand=True),
                                 ft.Text(f"{getattr(t, k)} g", size=th.T.LABEL, font_family=th.FONT_SEMI),
                                 th.muted(f"{t.gkg[k]:.1f} g/kg", th.T.CAPTION, width=72, text_align=ft.TextAlign.RIGHT)])
                         for k in ("carbs", "protein", "fat")],
                       ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=14, color=th.MACRO_COLORS["water"]),
                               ft.Text("Water", size=th.T.LABEL, expand=True),
                               ft.Text(app.svc.water_fmt(t.water_ml), size=th.T.LABEL, font_family=th.FONT_SEMI),
                               ft.Container(width=72)]), spacing=8)

    out: list[ft.Control] = [
        ft.Row([cx.stat_tile("Resting burn", f"{tt.bmr:,}", "kcal, at complete rest"),
                cx.stat_tile("Daily burn", f"{tt.tdee:,}", "kcal, with activity")], spacing=8),
        day_card("Training day", ft.Icons.FITNESS_CENTER, tt),
        day_card("Rest day", ft.Icons.SELF_IMPROVEMENT, rt),
        th.muted(f"Weekly average {weekly:,} kcal a day over {n_train} training and {7 - n_train} rest days."
                 + (" Your daily burn follows your weigh-ins (Progress → Trends)." if p.use_adaptive else ""), th.T.CAPTION),
    ]
    if tt.floor_applied:
        out.append(cx.note("Your target was raised to a safe minimum. Only go lower with professional guidance.", "warn"))
    out += [cx.note(n, "info") for n in tt.notes]
    out.append(ft.Row([ft.TextButton("Change training or goal", icon=ft.Icons.TUNE, on_click=lambda _: _open(app, "training"))]))
    return out


# ---------- reminders ----------
def _reminders(app: "App", p: Profile) -> list[ft.Control]:
    sched, rs = app.store.schedule(), app.store.reminders()
    notifier = app.notifier
    getp = lambda: app.page  # noqa: E731
    wake, sleep = cx.time_field(getp, sched["wake"], "Wake up", width=None), cx.time_field(getp, sched["sleep"], "Bedtime", width=None)
    wake.expand = sleep.expand = True
    meals = {k: cx.time_field(getp, sched[k], k.title(), width=None) for k in ("breakfast", "lunch", "dinner")}
    for f in meals.values():
        f.expand = True
    enabled_ref, supps_ref, water_ref = [], [], []
    every = ft.Dropdown(label="Check water every", value=str(rs["water_every_h"]).rstrip("0").rstrip("."), dense=True,
                        border_radius=12, width=170,
                        options=[ft.DropdownOption(key=k, text=f"{k} h") for k in ("1", "1.5", "2", "3")])
    checkins = list(rs["checkins"])
    check_row = ft.Row(wrap=True, spacing=8, run_spacing=8)

    def draw_checks():
        def setter(i, v):
            checkins[i] = v

        def remove(i):
            checkins.pop(i)
            draw_checks()
            check_row.update()

        def add(_):
            checkins.append("20:00" if not checkins else "12:00")
            draw_checks()
            check_row.update()

        check_row.controls = [ft.Row([cx.time_field(getp, v, f"Check-in {i + 1}", lambda nv, i=i: setter(i, nv), width=118),
                                      ft.IconButton(ft.Icons.CLOSE, icon_size=16, tooltip="Remove",
                                                    on_click=lambda _, i=i: remove(i))], spacing=0, tight=True)
                              for i, v in enumerate(checkins)]
        if len(checkins) < 3:
            check_row.controls.append(ft.TextButton("Add a check-in", icon=ft.Icons.ADD, on_click=add))

    draw_checks()
    how = ("Your phone delivers these even when NutriTrack is closed." if notifier.can_schedule
           else "On this device reminders appear while NutriTrack is open. On the phone app they arrive even when it's closed.")

    async def save(_):
        app.store.set("schedule", {"wake": wake.value, "sleep": sleep.value, **{k: f.value for k, f in meals.items()}})
        on = bool(enabled_ref[0].value)
        app.store.set("reminders", {"enabled": on, "supplements": bool(supps_ref[0].value), "water": bool(water_ref[0].value),
                                    "water_every_h": float(every.value or 2), "checkins": sorted(set(checkins))})
        if on and not await notifier.request_permission() and notifier.can_schedule:
            app.toast("Notifications are blocked. Allow them in your phone's settings.")
            return
        _saved(app, "Reminders on" if on else "Reminders saved")

    return [
        th.card(cx.toggle_row("Send me reminders", rs["enabled"], ref_out=enabled_ref,
                              sub="Never more than you ask for. " + how),
                ft.Divider(height=4),
                cx.toggle_row("Supplements", rs["supplements"], sub="At each dose's time, with a Mark taken button.",
                              ref_out=supps_ref),
                cx.toggle_row("Water", rs["water"], sub="Only when you're behind.", ref_out=water_ref), ft.Row([every]),
                th.label("Daily check-ins"),
                th.muted("How you're pacing on food and water. The evening one suggests foods for any gaps.", th.T.CAPTION),
                check_row, spacing=12),
        th.card(th.heading("Your day", icon=ft.Icons.SCHEDULE),
                th.muted("Meal times set your pace: half an hour after lunch you'd expect a bit over half the day's food.",
                         th.T.CAPTION),
                ft.Row([wake, sleep], spacing=10), ft.Row(list(meals.values()), spacing=8), spacing=12),
        ft.Row([ft.FilledButton("Save", icon=ft.Icons.CHECK, on_click=save, expand=True),
                ft.OutlinedButton("Send a test", on_click=lambda _: app.page.run_task(notifier.test))], spacing=8),
    ]


# ---------- appearance ----------
def _appearance(app: "App", p: Profile) -> list[ft.Control]:
    mode = app.store.get("theme_mode", "system")

    def hemi(v):
        app.store.set("hemisphere", v)
        app.render()

    return [
        th.card(th.label("Theme"),
                cx.tabs([("system", "Auto"), ("light", "Light"), ("dark", "Dark")], mode, app.set_theme_mode),
                th.muted("Auto follows your phone.", th.T.CAPTION), spacing=10),
        th.card(th.label("Seasons for your trees"),
                th.muted(f"Your forest follows the seasons: blossom in spring, gold in autumn, snow in winter. It's "
                         f"{app.svc.season()} now.", th.T.CAPTION),
                cx.tabs([("north", "North"), ("south", "South"), ("off", "Summer")], app.store.get("hemisphere", "north"), hemi),
                th.muted("North or South of the equator, or always summer.", th.T.CAPTION), spacing=10),
    ]


# ---------- backup & privacy ----------
def _data(app: "App", p: Profile) -> list[ft.Control]:
    def erase_dialog(_):
        confirm = ft.TextField(label="Type ERASE to confirm", dense=True, border_radius=12, autofocus=True)

        def go(_):
            if (confirm.value or "").strip().upper() != "ERASE":
                confirm.error = "Type ERASE"
                app.page.update()
                return
            app.page.pop_dialog()
            app.store.reset()
            app.ui.profile_page = None
            app.ui.onboarding = {}
            app.go("today")
            app.toast("All data erased")

        app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Erase everything?", font_family=th.FONT_BOLD),
            content=ft.Column([ft.Text("Your food log, weigh-ins, supplements, forest and settings will be deleted from "
                                       "this device. This can't be undone. Export a backup first if you might want it."),
                               confirm], tight=True, spacing=12),
            actions=[ft.TextButton("Cancel", on_click=lambda _: app.page.pop_dialog()),
                     ft.FilledButton("Erase", on_click=go, style=ft.ButtonStyle(bgcolor=th.STATUS_COLORS["over"],
                                                                                color=ft.Colors.WHITE))]))

    async def export(_):
        from datetime import date
        try:
            path = await ft.FilePicker().save_file(dialog_title="Save NutriTrack backup", file_name=f"nutritrack-{date.today()}.json",
                                                   allowed_extensions=["json"], src_bytes=app.store.export_json().encode())
            desktop = str(getattr(app.page.platform, "value", "")).lower() in ("windows", "macos", "linux")
            if path and desktop and not app.page.web:  # phones and web save src_bytes themselves
                from pathlib import Path
                Path(path).write_text(app.store.export_json())
            if path or app.page.web:
                app.toast("Backup saved")
        except Exception as ex:
            from ..diagnostics import log
            log.exception("export failed")
            app.toast(f"Export failed: {ex}")

    async def import_(_):
        try:
            files = await ft.FilePicker().pick_files(dialog_title="Choose a NutriTrack backup", allowed_extensions=["json"],
                                                     with_data=True)
            if not files:
                return
            f = files[0]
            data = (f.bytes if f.bytes else open(f.path, "rb").read()).decode()
        except Exception as ex:
            app.toast(f"Couldn't open that file: {ex}")
            return

        def restore():
            try:
                app.store.import_json(data)
            except Exception as ex:
                app.toast(f"That doesn't look like a NutriTrack backup ({ex})")
                return
            app.ui.profile_page = None
            app.go("today")
            app.toast("Backup restored")

        app.confirm("Replace everything with this backup?", f"Restoring “{f.name}” replaces all the data on this device. "
                    "Export a backup first if you want to keep what's here.", restore, "Replace")

    return [
        th.card(ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, color=th.ACCENT, size=28),
                        ft.Column([ft.Text("Private by design", size=th.T.BODY, font_family=th.FONT_SEMI),
                                   th.muted("Everything stays on this device. No account, no cloud, no ads. Online food "
                                            "searches send only what you type.", th.T.CAPTION)], spacing=2, expand=True)],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)),
        th.card(th.label("Backup"),
                th.muted("Save a copy of everything to a file, for a new phone or just in case.", th.T.CAPTION),
                ft.Row([ft.FilledTonalButton("Export backup", icon=ft.Icons.DOWNLOAD, on_click=export),
                        ft.OutlinedButton("Restore", icon=ft.Icons.UPLOAD, on_click=import_)], wrap=True), spacing=10),
        th.card(th.label("Danger zone"),
                ft.Row([ft.OutlinedButton("Erase all data", icon=ft.Icons.DELETE_FOREVER, on_click=erase_dialog,
                                          style=ft.ButtonStyle(color=th.ink(th.STATUS_COLORS["over"]),
                                                               side=ft.BorderSide(1, th.STATUS_COLORS["over"])))]),
                spacing=10),
    ]


# ---------- help & feedback ----------
def _help(app: "App", p: Profile) -> list[ft.Control]:
    import os

    from .. import __version__, diagnostics

    async def export_log(_):
        try:
            data = diagnostics.report(app.store, app.page, lines=400).encode()
            await ft.FilePicker().save_file(dialog_title="Save diagnostics", file_name="nutritrack-diagnostics.md", src_bytes=data)
        except Exception as ex:
            diagnostics.log.exception("export log failed")
            app.toast(f"Couldn't save: {ex}")

    def boom(_):  # developer check of the crash guard (NUTRITRACK_DEBUG=1)
        raise RuntimeError("Simulated error from the diagnostics card")

    key = ft.TextField(label="USDA FoodData Central key", value=app.store.get("usda_api_key") or "", password=True,
                       can_reveal_password=True, dense=True, border_radius=12, expand=True)

    def save_key(_):
        app.store.set("usda_api_key", (key.value or "").strip())
        app.toast("Key saved" if key.value else "Using the shared key")

    dev: list[ft.Control] = [
        th.label("Recent log"),
        ft.Container(ft.Text(diagnostics.tail(12), size=11, font_family="monospace", selectable=True), padding=10,
                     border_radius=th.R.MD, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST),
        th.muted(" · ".join(f"{k} {v}" for k, v in diagnostics.environment(app.page).items()), th.T.CAPTION),
        th.muted("Keyboard: Alt+← / Alt+→ change day · Alt+T today · Alt+N log food · Alt+1–5 tabs · Esc back", th.T.CAPTION),
        th.label("Food database key"),
        th.muted("Optional. Lab-verified search uses USDA's shared key, which can get busy. Your own free key from "
                 "api.data.gov makes it faster.", th.T.CAPTION),
        ft.Row([key, ft.TextButton("Save", on_click=save_key)]),
    ]
    if os.getenv("NUTRITRACK_DEBUG"):
        dev.append(ft.TextButton("Simulate an error", icon=ft.Icons.BUG_REPORT, on_click=boom))
    return [
        th.card(th.label("Something not working?"),
                th.muted("Copy the diagnostics and paste them into your bug report. They include app versions, record "
                         "counts and recent errors, never your food or body data.", th.T.CAPTION),
                ft.Row([ft.FilledTonalButton("Copy diagnostics", icon=ft.Icons.CONTENT_COPY,
                                             on_click=lambda _: app.copy(diagnostics.report(app.store, app.page))),
                        ft.OutlinedButton("Save to file", icon=ft.Icons.DOWNLOAD, on_click=export_log)], wrap=True),
                spacing=10),
        th.card(ft.ExpansionTile(title=ft.Text("Advanced", size=th.T.BODY - 1, font_family=th.FONT_SEMI), tile_padding=0,
                                 controls=dev, controls_padding=ft.Padding.only(bottom=8)),
                padding=ft.Padding.symmetric(horizontal=16, vertical=4)),
        th.muted(f"NutriTrack {__version__}", th.T.CAPTION, text_align=ft.TextAlign.CENTER),
    ]
