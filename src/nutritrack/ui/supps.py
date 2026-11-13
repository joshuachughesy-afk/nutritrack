"""Stack: your supplements, one-tap fixes for timing clashes, safety checks, daily totals, the add picker and editor."""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import MICROS, empty_nutrients, fmt
from ..core.pacing import from_min, to_min
from ..core.supplements import SUPP_TEMPLATES, Supplement, analyze_stack, creatine_per_dose, timing_advice
from ..store import new_id
from . import components as cx
from . import theme as th

if TYPE_CHECKING:
    from .app import App


def _has(s: Supplement, key: str, amount: float) -> bool:
    return (s.n.get(key) or 0) >= amount


def iron_clashes(supps: list[Supplement]) -> list[tuple[str, Supplement, list[Supplement]]]:
    """(time, iron supplement, supplements taken at the same time that block its absorption)."""
    by_time: dict[str, list[Supplement]] = {}
    for s in supps:
        if s.active:
            for t in s.times:
                by_time.setdefault(t, []).append(s)
    out = []
    for time, items in sorted(by_time.items()):
        iron = next((s for s in items if _has(s, "iron", 5)), None)
        blockers = [s for s in items if s is not iron and (_has(s, "calcium", 200) or _has(s, "zinc", 8))]
        if iron and blockers:
            out.append((time, iron, blockers))
    return out


def build(app: "App") -> list[ft.Control]:
    if app.ui.supp_edit is not None:
        return _editor(app, app.ui.supp_edit)
    if app.ui.supp_picker:
        return _picker(app)

    supps = app.store.supplements()
    t = app.svc.targets_for(app.date)
    totals, warnings = analyze_stack(supps, t)
    active = [s for s in supps if s.active]
    doses = sum(len(s.times) for s in active)
    add_btn = ft.FilledButton("Add", icon=ft.Icons.ADD, on_click=lambda _: _open_picker(app))
    out: list[ft.Control] = [cx.screen_title("Your stack", trailing=add_btn)]
    if not supps:
        out.append(th.card(cx.empty_state(
            ft.Icons.MEDICATION_OUTLINED, "Add what you take. It counts toward your vitamins and minerals, gets checked "
            "against safe maximums, and you get a reminder at the right time.",
            ft.FilledButton("Add a supplement", icon=ft.Icons.ADD, on_click=lambda _: _open_picker(app)),
            title="Supplements, sorted")))
        return out
    out.append(th.muted(f"{len(active)} active · {doses} dose{'s' if doses != 1 else ''} a day. Tick them off on Today.",
                        th.T.LABEL))

    # 1. Things to fix, each with a one-tap fix.
    fixes: list[ft.Control] = []
    for time, iron, blockers in iron_clashes(supps):
        for b in blockers:
            new_time = from_min(min(to_min(time) + 180, 21 * 60))

            def move(_, b=b, old=time, new=new_time):
                b.times = sorted({new if x == old else x for x in b.times})
                app.store.save_supplement(b)
                app.render()
                app.toast(f"Moved {b.name} to {new}")

            mineral = "Calcium" if _has(b, "calcium", 200) else "Zinc"
            fixes.append(cx.note(f"{iron.name} and {b.name} are both at {time}. {mineral} blocks iron absorption.", "warn",
                                 action=ft.TextButton(f"Move to {new_time}", on_click=move)))
    safety = [w for w in warnings if w[:2].isdigit() is False and not w.startswith("Vitamin A: the upper limit applies")]
    fixes += [cx.note(w, "warn") for w in safety]
    if fixes:
        out.append(th.card(th.heading("Worth a look", icon=ft.Icons.TIPS_AND_UPDATES_OUTLINED, icon_color="#e08a2b"),
                           *fixes, spacing=10))

    # 2. The stack, one compact row each.
    def edit(sid):
        app.ui.supp_edit = sid
        app.render()

    def toggle_pause(s: Supplement):
        s.active = not s.active
        app.store.save_supplement(s)
        app.render()
        app.toast(f"{s.name} {'resumed' if s.active else 'paused. Resume it any time'}")

    def delete(s: Supplement):
        app.confirm("Remove from your stack?", f"{s.name} will be removed. Doses already logged are kept.",
                    lambda: (app.store.delete_supplement(s.id), app.render()), "Remove")

    rows: list[ft.Control] = []
    for s in supps:
        contents = ", ".join(f"{m.label} {fmt(s.n.get(m.key, 0))} {m.unit}" for m in MICROS if s.n.get(m.key, 0) > 0)
        cg = creatine_per_dose(s)
        if cg:
            contents = (contents + ", " if contents else "") + f"creatine {fmt(cg)} g"
        rows.append(ft.Container(ft.Row([
            ft.Column([
                ft.Row([ft.Text(s.name, font_family=th.FONT_SEMI, size=th.T.BODY, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        *([th.chip("Paused", "#8a948f")] if not s.active else [])], spacing=6),
                th.muted(f"{s.dose_label} · {', '.join(s.times)}{' · with food' if s.with_food else ''}", th.T.CAPTION),
                *([th.muted(contents, th.T.CAPTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)] if contents else []),
            ], spacing=1, expand=True),
            ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, tooltip="More", items=[
                ft.PopupMenuItem(content=ft.Text("Edit"), icon=ft.Icons.EDIT_OUTLINED, on_click=lambda _, i=s.id: edit(i)),
                ft.PopupMenuItem(content=ft.Text("Resume" if not s.active else "Pause"),
                                 icon=ft.Icons.PLAY_ARROW if not s.active else ft.Icons.PAUSE_CIRCLE_OUTLINE,
                                 on_click=lambda _, x=s: toggle_pause(x)),
                ft.PopupMenuItem(content=ft.Text("Remove"), icon=ft.Icons.DELETE_OUTLINE, on_click=lambda _, x=s: delete(x)),
            ]),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER), opacity=1 if s.active else 0.6, ink=True,
            on_click=lambda _, i=s.id: edit(i), border_radius=th.R.MD,
            padding=ft.Padding.only(left=10, top=8, bottom=8)))
    out.append(th.card(*rows, spacing=2, padding=8))

    # 3. What the stack adds up to, against your needs and the safe maximum.
    total_rows: list[ft.Control] = []
    for m in MICROS:
        amt = totals.get(m.key, 0)
        if amt <= 0:
            continue
        tg = t.micros[m.key]
        pct = amt / tg.target if tg.target else 0
        over = bool(tg.ul) and amt > tg.ul
        value = f"{fmt(amt)} {m.unit} · {round(pct * 100)}%"
        near = bool(tg.ul) and amt > tg.ul * 0.6
        note = (f"{'Above' if over else 'Close to'} the {fmt(tg.ul)} {m.unit} safe max"
                + (" from supplements" if m.ul_scope == "supplement" else "")) if near else None
        total_rows.append(cx.metric_row(m.label, value, min(pct, 1), "#e08a2b" if over else th.ACCENT_SOFT, note=note,
                                        note_color="#e08a2b" if over else None,
                                        icon=ft.Icons.WARNING_AMBER_ROUNDED if over else ft.Icons.CHECK_CIRCLE if pct >= 1 else None,
                                        icon_color=th.ink("#e08a2b" if over else th.ACCENT_SOFT), height=7))
    if total_rows:
        out.append(th.card(th.heading("What your stack adds up to", icon=ft.Icons.SPA_OUTLINED),
                           th.muted("% of your daily need on a day with every dose taken, before food.", th.T.CAPTION), *total_rows, spacing=10))

    # 4. Timing tips, once each.
    tips: list[str] = []
    for s in active:
        for tip in timing_advice(s):
            if tip not in tips:
                tips.append(tip)
    if "Vitamin A" in " ".join(warnings):
        tips.append("Vitamin A: the safe maximum is for retinol. Beta-carotene doesn't count, so check your label.")
    if tips:
        out.append(th.card(ft.ExpansionTile(
            title=ft.Text("Timing tips", size=th.T.BODY, font_family=th.FONT_SEMI), tile_padding=0,
            leading=ft.Icon(ft.Icons.SCHEDULE, color=th.ACCENT),
            controls=[ft.Row([ft.Text("•"), ft.Text(tip, size=th.T.LABEL, expand=True)],
                             vertical_alignment=ft.CrossAxisAlignment.START) for tip in tips],
            controls_padding=ft.Padding.only(bottom=8)), padding=ft.Padding.symmetric(horizontal=16, vertical=4)))
    return out


def _open_picker(app: "App") -> None:
    app.ui.supp_picker = True
    app.render()


def _picker(app: "App") -> list[ft.Control]:
    """Add a supplement: common ones at typical strengths, or a custom one from the label."""
    owned = {s.tid for s in app.store.supplements()}

    def back():
        app.ui.supp_picker = False
        app.render()

    tiles = []
    for tp in SUPP_TEMPLATES:
        added = tp.tid in owned
        tiles.append(ft.Container(ft.Row([
            ft.Column([ft.Text(tp.name, font_family=th.FONT_SEMI, size=th.T.LABEL, max_lines=2),
                       th.muted(tp.dose_label, th.T.CAPTION, max_lines=1)], spacing=2, expand=True),
            ft.Icon(ft.Icons.CHECK_CIRCLE if added else ft.Icons.ADD_CIRCLE_OUTLINE, size=20,
                    color=th.ACCENT if added else th.MUTED),
        ], spacing=6), col={"xs": 6, "sm": 4}, padding=12, border_radius=th.R.MD,
            border=ft.Border.all(1, th.ACCENT if added else ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.with_opacity(0.08, th.ACCENT) if added else ft.Colors.SURFACE_CONTAINER_LOWEST,
            tooltip="Already in your stack" if added else f"Add {tp.name}",
            on_click=None if added else (lambda _, x=tp: _new(app, x)), ink=not added))
    return [cx.back_header("Add a supplement", back, subtitle="Typical strengths. Adjust to match your label."),
            ft.ResponsiveRow(tiles, spacing=8, run_spacing=8),
            th.card(ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, color=th.ACCENT),
                            ft.Column([ft.Text("Something else?", font_family=th.FONT_SEMI, size=th.T.BODY),
                                       th.muted("Enter it from the label.", th.T.CAPTION)], spacing=0, expand=True),
                            ft.FilledTonalButton("Custom", icon=ft.Icons.ADD, on_click=lambda _: _new(app, None))]),
                    padding=14)]


def _new(app: "App", template) -> None:
    app.ui.supp_draft = template.make() if template else Supplement(id=new_id("s-"), name="", dose_label="1 capsule",
                                                                  times=["08:00"])
    app.ui.supp_edit = "new"
    app.ui.supp_picker = False
    app.render()


def _editor(app: "App", editing: str) -> list[ft.Control]:
    existing = next((s for s in app.store.supplements() if s.id == editing), None)
    s: Supplement = existing or app.ui.supp_draft
    name = ft.TextField(label="Name", value=s.name, dense=True, border_radius=12)
    dose = ft.TextField(label="Dose", value=s.dose_label, dense=True, border_radius=12, hint_text="e.g. 2 capsules")
    times_state = list(s.times) or ["08:00"]
    times_row = ft.Row(wrap=True, spacing=8, run_spacing=8)
    with_food = cx.toggle_row("Take with food", s.with_food, sub="Fat-soluble vitamins, fish oil and multis absorb better "
                                                                 "with a meal.", ref_out=(food_ref := []))
    cg = creatine_per_dose(s)
    creatine = th.num_field("Creatine per dose", fmt(cg) if cg else None, suffix="g", expand=True)
    micro = {m.key: th.num_field(f"{m.label} ({m.unit})", fmt(s.n.get(m.key)) if s.n.get(m.key) else None, col={"xs": 6, "sm": 4})
             for m in MICROS if m.key != "fiber"}

    def draw_times():
        def set_time(i, v):
            times_state[i] = v

        def remove(i):
            times_state.pop(i)
            draw_times()
            times_row.update()

        times_row.controls = [ft.Row([cx.time_field(lambda: app.page, tv, f"Dose {i + 1}", lambda v, i=i: set_time(i, v),
                                                    width=118),
                                      *([ft.IconButton(ft.Icons.CLOSE, icon_size=16, tooltip="Remove this time",
                                                       on_click=lambda _, i=i: remove(i))] if len(times_state) > 1 else [])],
                                     spacing=0, tight=True)
                              for i, tv in enumerate(times_state)]
        if len(times_state) < 4:
            times_row.controls.append(ft.TextButton("Add a time", icon=ft.Icons.ADD, on_click=add_time))

    def add_time(_):
        last = to_min(times_state[-1]) if times_state else 8 * 60
        times_state.append(from_min(min(last + 4 * 60, 22 * 60)))
        draw_times()
        times_row.update()

    draw_times()

    def back():
        app.ui.supp_edit = None
        app.render()

    def save(_):
        if not (name.value or "").strip():
            name.error = "Give it a name"
            app.page.update()
            return
        n = empty_nutrients()
        n["kcal"], n["fat"] = s.n.get("kcal", 0), s.n.get("fat", 0)
        for k, f in micro.items():
            n[k] = th.parse_num(f.value)
        s.name, s.dose_label, s.times = name.value.strip(), (dose.value or "").strip() or "1 dose", sorted(set(times_state))
        s.with_food, s.n, s.creatine_g = bool(food_ref[0].value), n, th.parse_num(creatine.value)
        app.store.save_supplement(s)
        app.ui.supp_edit = None
        app.render()
        app.toast(f"{'Saved' if existing else 'Added'} {s.name}")

    tips = timing_advice(s)
    return [
        cx.back_header("Edit supplement" if existing else "Add supplement", back,
                       trailing=ft.FilledButton("Save", on_click=save)),
        th.card(name, dose, th.label("When you take it"), times_row,
                th.muted("Each time is one dose and gets its own reminder.", th.T.CAPTION), with_food, spacing=12),
        th.card(ft.Row([creatine]),
                th.muted("Creatine raises your water goal: about +500 ml a day, or +1 L while loading (15 g+ a day).",
                         th.T.CAPTION),
                ft.ExpansionTile(title=ft.Text("Vitamins & minerals per dose", size=th.T.BODY - 1, font_family=th.FONT_SEMI),
                                 subtitle=th.muted("From the label", th.T.CAPTION), tile_padding=0,
                                 expanded=not existing and not s.tid,
                                 controls=[ft.ResponsiveRow(list(micro.values()), spacing=10, run_spacing=10),
                                           th.muted("Vitamin D: 1,000 IU = 25 µg. Vitamin A: 1 µg RAE = 3.33 IU retinol.",
                                                    th.T.CAPTION)],
                                 controls_padding=ft.Padding.only(bottom=8)), spacing=10),
        *([th.card(th.label("Tips"), *[ft.Row([ft.Text("•"), ft.Text(tip, size=th.T.LABEL, expand=True)],
                                               vertical_alignment=ft.CrossAxisAlignment.START) for tip in tips])]
          if tips else []),
        ft.Row([ft.FilledButton("Save" if existing else "Add to stack", icon=ft.Icons.CHECK, on_click=save, expand=True)]),
    ]
