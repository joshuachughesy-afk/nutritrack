"""Supplements: your stack, upper-limit and timing checks, daily totals, templates and the editor."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import MICROS, empty_nutrients, fmt
from ..core.supplements import (SUPP_TEMPLATES, Supplement, analyze_stack, creatine_per_dose, timing_advice)
from ..store import new_id
from . import theme as th

if TYPE_CHECKING:
    from .app import App


def build(app: "App") -> list[ft.Control]:
    editing = getattr(app, "supp_edit", None)
    if editing is not None:
        return _editor(app, editing)

    supps = app.store.supplements()
    t = app.svc.targets_for(app.date)
    totals, warnings = analyze_stack(supps, t)
    out: list[ft.Control] = [th.title("Supplements")]

    if warnings:
        out.append(th.card(th.heading("Check your stack", icon=ft.Icons.WARNING_AMBER_ROUNDED, icon_color=th.STATUS_COLORS["low"]),
                           *[ft.Container(ft.Text(w, size=13), padding=12, border_radius=14,
                                          bgcolor=ft.Colors.with_opacity(0.12, th.STATUS_COLORS["low"])) for w in warnings]))

    def edit(sid):
        app.supp_edit = sid
        app.render()

    def toggle_pause(s: Supplement):
        s.active = not s.active
        app.store.save_supplement(s)
        app.render()

    def delete(s: Supplement):
        app.confirm("Remove from your stack?", f"{s.name} will be removed. Doses already logged are kept.",
                    lambda: (app.store.delete_supplement(s.id), app.render()), "Remove")

    items: list[ft.Control] = []
    for s in supps:
        contents = " · ".join(f"{m.label} {fmt(s.n.get(m.key, 0))} {m.unit}" for m in MICROS if s.n.get(m.key, 0) > 0)
        cg = creatine_per_dose(s)
        if cg:
            contents = (contents + " · " if contents else "") + f"Creatine {fmt(cg)} g"
        tips = timing_advice(s)
        items.append(ft.Container(ft.Column([
            ft.Row([
                ft.Column([ft.Text(s.name, font_family=th.FONT_SEMI, size=15),
                           th.muted(f"{s.dose_label} · {', '.join(s.times)}{' · with food' if s.with_food else ''}", 12),
                           *([ft.Text(contents, size=12)] if contents else [])], spacing=2, expand=True),
                ft.IconButton(ft.Icons.EDIT_OUTLINED, tooltip="Edit", on_click=lambda _, i=s.id: edit(i)),
                ft.IconButton(ft.Icons.PLAY_ARROW if not s.active else ft.Icons.PAUSE, tooltip="Resume" if not s.active else "Pause",
                              on_click=lambda _, x=s: toggle_pause(x)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Remove", on_click=lambda _, x=s: delete(x)),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            *[ft.Row([ft.Text("•", size=12, color=th.MUTED), th.muted(tip, 12, expand=True)],
                     vertical_alignment=ft.CrossAxisAlignment.START) for tip in tips],
        ], spacing=4), opacity=1 if s.active else 0.5, padding=ft.Padding.symmetric(vertical=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))))
    out.append(th.card(
        th.heading("My stack", ft.FilledButton("Custom", icon=ft.Icons.ADD, on_click=lambda _: _new(app, None))),
        *(items or [th.muted("Nothing yet. Start from a common supplement below or add a custom one from your label.", 13)])))

    rows = []
    for m in MICROS:
        amt = totals.get(m.key, 0)
        if amt <= 0:
            continue
        tg = t.micros[m.key]
        rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(m.label)), ft.DataCell(ft.Text(f"{fmt(amt)} {m.unit}")),
                                      ft.DataCell(ft.Text(f"{round(amt / tg.target * 100)}%")),
                                      ft.DataCell(th.muted(f"{fmt(tg.ul)} {m.unit}" if tg.ul else "—"))]))
    if rows:
        out.append(th.card(th.heading("Daily stack totals"), th.muted("If every dose is taken, before food.", 12),
                           ft.Row([ft.DataTable(columns=[ft.DataColumn(ft.Text(h)) for h in ("", "Amount", "% of target", "Upper limit")],
                                                rows=rows, column_spacing=16, horizontal_margin=4)], scroll=ft.ScrollMode.AUTO)))

    owned = {s.tid for s in supps}
    tiles = []
    for tp in SUPP_TEMPLATES:
        added = tp.tid in owned
        tiles.append(ft.Container(
            ft.Column([ft.Text(tp.name, font_family=th.FONT_SEMI, size=13),
                       th.muted(tp.dose_label + (" · added" if added else ""), 11)], spacing=2),
            col={"xs": 6, "sm": 4}, padding=10, border_radius=10, opacity=0.5 if added else 1,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), bgcolor=ft.Colors.SURFACE,
            on_click=None if added else (lambda _, x=tp: _new(app, x)), ink=not added))
    out.append(th.card(th.heading("Common supplements"),
                       th.muted("Typical strengths. Tap one, then edit it to match your label.", 12),
                       ft.ResponsiveRow(tiles, spacing=8, run_spacing=8)))
    return out


def _new(app: "App", template) -> None:
    app.supp_draft = template.make() if template else Supplement(id=new_id("s-"), name="", dose_label="1 capsule",
                                                                  times=["08:00"])
    app.supp_edit = "new"
    app.render()


def _editor(app: "App", editing: str) -> list[ft.Control]:
    existing = next((s for s in app.store.supplements() if s.id == editing), None)
    s: Supplement = existing or app.supp_draft
    name = ft.TextField(label="Name", value=s.name, dense=True, border_radius=10, max_length=80)
    dose = ft.TextField(label="Dose", value=s.dose_label, dense=True, border_radius=10, max_length=60)
    times = [ft.TextField(label=f"Time {i + 1}", value=(s.times[i] if i < len(s.times) else ""), hint_text="HH:MM",
                          dense=True, border_radius=10, expand=True, keyboard_type=ft.KeyboardType.DATETIME) for i in range(3)]
    with_food = ft.Checkbox(label="Take with food", value=s.with_food)
    cg = creatine_per_dose(s)
    creatine = th.num_field("Creatine per dose", fmt(cg) if cg else None, suffix="g")
    micro = {m.key: th.num_field(f"{m.label} ({m.unit})", fmt(s.n.get(m.key)) if s.n.get(m.key) else None, col={"xs": 6, "sm": 4})
             for m in MICROS if m.key != "fiber"}

    def valid_time(v: str) -> bool:
        try:
            h, m = v.split(":")
            return 0 <= int(h) < 24 and 0 <= int(m) < 60 and len(m) == 2
        except ValueError:
            return False

    def save(_):
        ok = True
        if not name.value.strip():
            name.error = "Required"; ok = False
        ts = []
        for f in times:
            v = (f.value or "").strip()
            f.error = None
            if v:
                v = v if len(v) == 5 else v.zfill(5)
                if valid_time(v):
                    ts.append(v)
                else:
                    f.error = "Use HH:MM"; ok = False
        if not ts:
            times[0].error = "Add at least one time"; ok = False
        if not ok:
            app.page.update(); return
        n = empty_nutrients()
        n["kcal"], n["fat"] = s.n.get("kcal", 0), s.n.get("fat", 0)
        for k, f in micro.items():
            n[k] = th.parse_num(f.value)
        s.name, s.dose_label, s.times = name.value.strip(), dose.value.strip() or "1 dose", sorted(set(ts))
        s.with_food, s.n, s.creatine_g = bool(with_food.value), n, th.parse_num(creatine.value)
        app.store.save_supplement(s)
        app.supp_edit = None
        app.render()
        app.toast("Stack updated")

    def cancel(_):
        app.supp_edit = None
        app.render()

    return [
        ft.Text("Edit supplement" if existing else "Add supplement", size=22, font_family=th.FONT_BOLD),
        th.card(name, dose, th.muted("Times per day. Each time is one dose; leave extras blank.", 12), ft.Row(times, spacing=8),
                with_food, creatine,
                th.muted("If this contains creatine, your water goal goes up about 500 ml/day (about 1 L/day while loading at 15 g+/day).", 11),
                ft.Text("Nutrients per dose (from the label)", font_family=th.FONT_SEMI, size=14),
                ft.ResponsiveRow(list(micro.values()), spacing=10, run_spacing=10),
                th.muted("Vitamin D: 1,000 IU = 25 µg. Vitamin A: 1 µg RAE = 3.33 IU retinol.", 11),
                ft.Row([ft.FilledButton("Save" if existing else "Add to stack", icon=ft.Icons.CHECK, on_click=save),
                        ft.TextButton("Cancel", on_click=cancel)])),
    ]
