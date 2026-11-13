"""Garden: level, streaks, an 8-week forest of daily trees, seed picker and how scoring works."""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import flet as ft

from ..core.garden import SPECIES, STAGES, TREE_DAY, level_info, stage_for
from ..service import pretty_date, today_key
from . import theme as th
from .day_review import open_review
from .tree_view import TreeView, tree_src

if TYPE_CHECKING:
    from .app import App


def build(app: "App") -> list[ft.Control]:
    """The Progress tab: Garden (motivation) and Trends (analysis)."""
    tab = getattr(app, "progress_tab", "garden")

    def switch(e):
        app.progress_tab = list(e.control.selected)[0]
        app.render()

    toggle = ft.SegmentedButton(segments=[ft.Segment(value="garden", label=ft.Text("Garden"), icon=ft.Icon(ft.Icons.PARK)),
                                          ft.Segment(value="trends", label=ft.Text("Trends"), icon=ft.Icon(ft.Icons.SHOW_CHART))],
                                selected=[tab], on_change=switch, show_selected_icon=False)
    if tab == "trends":
        from . import trends
        return [th.title("Progress"), toggle] + trends.build(app)
    return [toggle] + _garden(app)


def _garden(app: "App") -> list[ft.Control]:
    svc = app.svc
    t0 = date.fromisoformat(today_key())
    app.store.prefetch((t0 - timedelta(days=t0.weekday() + 7 * 7)).isoformat(), t0.isoformat())  # calendar + forest
    svc.finalize_garden()
    days, h = svc.history()
    lv = level_info(h.points)
    scores = dict(days)
    today = date.fromisoformat(today_key())
    next_species = min((s for s in SPECIES.values() if s.level > lv.level), key=lambda s: s.level, default=None)

    today_score = scores.get(today.isoformat())
    showcase = TreeView(svc.seed(), stage_for(today_score) if today_score is not None else 4, size=200,
                        on_tap=lambda _: app.go("today", today_key()), season=svc.season())
    sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])
    stage_card = th.card(ft.Column([
        ft.Container(showcase.control, alignment=ft.Alignment.CENTER),
        th.muted("Drag to turn · tap to open today", 11, text_align=ft.TextAlign.CENTER),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2), gradient=sky, padding=10)
    hero = th.card(ft.Row([
        ft.Container(ft.Column([ft.Text("Level", size=11, color=ft.Colors.WHITE),
                                ft.Text(str(lv.level), size=28, font_family=th.FONT_BOLD, color=ft.Colors.WHITE)],
                               spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                     width=72, height=72, border_radius=36, alignment=ft.Alignment.CENTER,
                     gradient=ft.RadialGradient(colors=["#6fcf8f", th.ACCENT], center=ft.Alignment(-0.4, -0.4))),
        ft.Column([
            ft.Row([ft.Text(f"{round(h.points):,} growth points", font_family=th.FONT_BOLD, expand=True),
                    th.muted(f"{round(lv.next - h.points):,} to level {lv.level + 1}" if lv.next else "Max level", 12)]),
            th.bar(lv.progress, th.ACCENT, height=10),
            th.muted(f"Next unlock: {next_species.name} at level {next_species.level}" if next_species
                     else "Every species unlocked", 12),
        ], spacing=6, expand=True),
    ], spacing=16))

    def stat(icon, value, label):
        ic, col = icon
        return ft.Container(th.card(ft.Column([ft.Icon(ic, size=22, color=col), ft.Text(str(value), size=22, font_family=th.FONT_BOLD),
                                               th.muted(label, 12)], spacing=2,
                                              horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=10),
                            col={"xs": 6, "sm": 3})

    stats = ft.ResponsiveRow([stat((ft.Icons.LOCAL_FIRE_DEPARTMENT, "#e8590c"), h.streak, "day streak"),
                              stat((ft.Icons.EMOJI_EVENTS, "#e0a33d"), h.best, "best streak"),
                              stat((ft.Icons.PARK, th.ACCENT), h.tree_days, "tree days"),
                              stat((ft.Icons.SHIELD, "#3d7be0"), h.shields, "shields")], spacing=10, run_spacing=10)

    # Forest: 8 weeks, Monday-first rows, ending with the current week.
    start = today - timedelta(days=today.weekday() + 7 * 7)
    cells: list[ft.Control] = [ft.Container(th.muted(d, 11), alignment=ft.Alignment.CENTER, col=1)
                               for d in ("M", "T", "W", "T", "F", "S", "S")]
    for i in range(7 * 8):
        d = start + timedelta(days=i)
        k = d.isoformat()
        sc = scores.get(k)
        mark = h.marks.get(k)
        tip = f"{pretty_date(k)}: {sc} points" if sc is not None else f"{pretty_date(k)}: no log"
        if d > today:
            content, bg, border = None, None, ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
        elif sc is not None:
            content = ft.Image(src=tree_src(svc.species_for(k), stage_for(sc), 96, season=svc.season(k)), fit=ft.BoxFit.CONTAIN)
            bg, border = ft.Colors.with_opacity(0.10, "#8a6a4a"), ft.Border.all(2, th.ACCENT) if d == today else None
        else:
            content = ft.Icon(ft.Icons.SHIELD, size=14, color="#3d7be0") if mark == "shielded" else None
            bg, border = ft.Colors.with_opacity(0.10, "#8a6a4a"), None
        cells.append(ft.Container(content, col=1, aspect_ratio=1, border_radius=8, bgcolor=bg, border=border, padding=2,
                                  alignment=ft.Alignment.CENTER, tooltip=tip,
                                  on_click=(lambda _, key=k: open_review(app, key)) if sc is not None else None))
    forest = th.card(th.heading("Calendar", th.muted("tap a tree to look back", 12), icon=ft.Icons.CALENDAR_MONTH),
                     ft.ResponsiveRow(cells, columns=7, spacing=4, run_spacing=4))

    seed = svc.seed()

    def pick(key):
        app.store.set("garden", {**app.store.garden_settings(), "seed": key})
        app.store.set_day(today_key(), species=key)
        app.render()
        app.toast(f"🌱 Planting {SPECIES[key].name.lower()} today")

    seeds = []
    for k, sp in SPECIES.items():
        locked = sp.level > lv.level
        seeds.append(ft.Container(ft.Column([
            ft.Image(src=tree_src(k, 4, 112, season=svc.season()), width=80, height=80, opacity=0.3 if locked else 1),
            ft.Text(sp.name, size=12, font_family=th.FONT_SEMI, text_align=ft.TextAlign.CENTER),
            *([th.icon_text(ft.Icons.LOCK, f"Level {sp.level}", th.MUTED, size=11)] if locked else []),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), col={"xs": 4, "sm": 2}, padding=8, border_radius=12,
            border=ft.Border.all(2 if k == seed else 1, th.ACCENT if k == seed else ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.with_opacity(0.10, th.ACCENT) if k == seed else ft.Colors.SURFACE,
            on_click=None if locked else (lambda _, key=k: pick(key)), ink=not locked))
    seed_card = th.card(th.heading("Choose today's seed"),
                        th.muted("Today's tree grows as this species. Higher garden levels unlock more.", 12),
                        ft.ResponsiveRow(seeds, spacing=8, run_spacing=8))

    rules = [("Calories", "20", "full within ±10% of target; more than 25% over caps the day at a sapling"),
             ("Protein", "15", "full at 90%+ of target"), ("Carbs / Fat", "10 / 5", "full within ±15% / ±20%"),
             ("Micronutrients", "20", "average coverage; −2 for each upper limit exceeded"),
             ("Water", "15", "share of today's water goal"),
             ("Supplements", "10", "doses taken (with no stack, the rest scales up to 100)")]
    how = th.card(
        th.heading("How your tree grows"),
        *[ft.Row([ft.Text(a, font_family=th.FONT_SEMI, size=13, width=110), ft.Text(b, size=13, width=50),
                  th.muted(c, 12, expand=True)], vertical_alignment=ft.CrossAxisAlignment.START) for a, b, c in rules],
        ft.Row([th.chip(f"{name} {lo}+", th.ACCENT) for lo, name, _ in STAGES], wrap=True, spacing=6),
        th.muted(f"A day of {TREE_DAY}+ points is a tree day and extends your streak. Every 7-day streak earns a shield "
                 "(hold up to 2) that covers one missed day, so a busy day doesn't wipe out your progress.", 12),
    )
    from .forest_view import ForestView
    return [th.title("Your garden"), stage_card, hero, stats, ForestView(app).control, forest, seed_card, how]
