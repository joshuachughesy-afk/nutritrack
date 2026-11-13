"""Progress → Garden: your forest valley, level, streaks, calendar look-back, today's seed and how scoring works."""
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import flet as ft

from ..core.garden import SPECIES, STAGES, TREE_DAY, level_info, stage_for
from ..service import pretty_date, today_key
from . import components as cx
from . import theme as th
from .day_review import open_review
from .tree_view import tree_src

if TYPE_CHECKING:
    from .app import App


def build(app: "App") -> list[ft.Control]:
    """The Progress tab: Garden (motivation) and Trends (analysis), with the same header on both."""
    tab = app.ui.progress_tab

    def switch(v):
        app.ui.progress_tab = v
        app.render()

    head = [cx.screen_title("Progress"), cx.tabs([("garden", "Garden"), ("trends", "Trends")], tab, switch)]
    if tab == "trends":
        from . import trends
        return head + trends.build(app)
    return head + _garden(app)


def _garden(app: "App") -> list[ft.Control]:
    svc = app.svc
    t0 = date.fromisoformat(today_key())
    app.store.prefetch((t0 - timedelta(days=t0.weekday() + 7 * 7)).isoformat(), t0.isoformat())  # read-ahead only
    days, h = svc.history()
    lv = level_info(h.points)
    scores = dict(days)
    today = date.fromisoformat(today_key())
    next_species = min((s for s in SPECIES.values() if s.level > lv.level), key=lambda s: s.level, default=None)

    hero = th.card(ft.Row([
        ft.Container(ft.Column([ft.Text("Level", size=th.T.CAPTION, color=ft.Colors.WHITE),
                                ft.Text(str(lv.level), size=28, font_family=th.FONT_BOLD, color=ft.Colors.WHITE)],
                               spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
                     width=72, height=72, border_radius=36, alignment=ft.Alignment.CENTER,
                     gradient=ft.RadialGradient(colors=["#6fcf8f", "#1f7a4d"], center=ft.Alignment(-0.4, -0.4))),
        ft.Column([
            ft.Text(f"{round(lv.next - h.points):,} points to level {lv.level + 1}" if lv.next else "Top level reached",
                    font_family=th.FONT_BOLD, size=th.T.BODY),
            th.bar(lv.progress, th.ACCENT, height=10),
            th.muted(f"Unlocks the {next_species.name.lower()} at level {next_species.level}" if next_species
                     else "Every tree species unlocked", th.T.CAPTION),
        ], spacing=6, expand=True),
    ], spacing=16))

    def explain(title, text):
        return lambda _: cx.info_sheet(app.page, title, th.muted(text, th.T.LABEL))

    stats = ft.Row([
        cx.stat_tile("Streak", f"{h.streak}", "days in a row", icon=ft.Icons.LOCAL_FIRE_DEPARTMENT, color=th.FIRE,
                     on_click=explain("Streak", f"Days in a row with a full tree ({TREE_DAY}+ points). Your best is {h.best}.")),
        cx.stat_tile("Full trees", f"{h.tree_days}", f"best streak {h.best}", icon=ft.Icons.PARK, color=th.ACCENT),
        cx.stat_tile("Shields", f"{h.shields}", "of 2", icon=ft.Icons.SHIELD, color=th.SHIELD,
                     on_click=explain("Shields", "Every 7 days in a row earns a shield (you can hold 2). A shield covers "
                                                 "one missed day, so a busy day doesn't wipe out your streak.")),
    ], spacing=8)

    # Calendar: Monday-first weeks from your first logged week (at most 8), each day numbered.
    logged = sorted(k for k in scores)
    first = date.fromisoformat(logged[0]) if logged else today
    weeks = max(2, min(8, (today - (first - timedelta(days=first.weekday()))).days // 7 + 1))
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    cells: list[ft.Control] = [ft.Container(th.muted(d, th.T.CAPTION), alignment=ft.Alignment.CENTER, col=1)
                               for d in ("M", "T", "W", "T", "F", "S", "S")]
    for i in range(7 * weeks):
        d = start + timedelta(days=i)
        k = d.isoformat()
        sc = scores.get(k)
        mark = h.marks.get(k)
        num = ft.Text(str(d.day), size=10, color=th.MUTED, font_family=th.FONT_SEMI)
        if d > today:
            content, bg, border = num, None, None
        elif sc is not None:
            content = ft.Stack([ft.Image(src=tree_src(svc.species_for(k), stage_for(sc), 96, season=svc.season(k)),
                                         fit=ft.BoxFit.CONTAIN, left=0, right=0, top=0, bottom=0),
                                ft.Container(num, left=3, top=1)])
            bg = ft.Colors.with_opacity(0.10, th.EARTH)
            border = ft.Border.all(2, th.ACCENT) if d == today else None
        else:
            content = ft.Stack([ft.Container(num, left=3, top=1),
                                *([ft.Container(ft.Icon(ft.Icons.SHIELD, size=14, color=th.SHIELD), alignment=ft.Alignment.CENTER,
                                                left=0, right=0, top=0, bottom=0)] if mark == "shielded" else [])])
            bg, border = None, ft.Border.all(1, ft.Colors.OUTLINE_VARIANT)
        tip = (f"{pretty_date(k)}: {sc} points" if sc is not None else
               f"{pretty_date(k)}: covered by a shield" if mark == "shielded" else f"{pretty_date(k)}: nothing logged")
        cells.append(ft.Container(content, col=1, aspect_ratio=1, border_radius=8, bgcolor=bg, border=border, padding=1,
                                  tooltip=tip, on_click=(lambda _, key=k: open_review(app, key)) if d <= today else None,
                                  ink=d <= today))
    months = sorted({(start + timedelta(days=i)).strftime("%B") for i in range(0, 7 * weeks, 7)},
                    key=lambda m: [(start + timedelta(days=i)).strftime("%B") for i in range(0, 7 * weeks, 7)].index(m))
    legend = ft.Row([th.icon_text(ft.Icons.PARK, "logged", th.ACCENT, size=th.T.CAPTION),
                     th.icon_text(ft.Icons.CHECK_BOX_OUTLINE_BLANK, "missed", th.MUTED, size=th.T.CAPTION),
                     th.icon_text(ft.Icons.SHIELD, "shield", th.SHIELD, size=th.T.CAPTION)], spacing=14, wrap=True)
    calendar = th.card(th.heading("Calendar", " – ".join(months), icon=ft.Icons.CALENDAR_MONTH),
                       ft.ResponsiveRow(cells, columns=7, spacing=4, run_spacing=4), legend,
                       th.muted("Tap a day to look back at what you ate.", th.T.CAPTION))

    seed = svc.seed()

    def pick(key):
        app.store.set("garden", {**app.store.garden_settings(), "seed": key})
        app.store.set_day(today_key(), species=key)
        app.render()
        app.toast(f"🌱 Today's tree is now a {SPECIES[key].name.lower()}")

    seeds = []
    for k, sp in SPECIES.items():
        locked = sp.level > lv.level
        seeds.append(ft.Container(ft.Column([
            ft.Image(src=tree_src(k, 4, 112, season=svc.season()), width=72, height=72, opacity=0.3 if locked else 1),
            ft.Text(sp.name, size=th.T.CAPTION, font_family=th.FONT_SEMI, text_align=ft.TextAlign.CENTER, max_lines=2),
            *([th.icon_text(ft.Icons.LOCK, f"Level {sp.level}", th.MUTED, size=th.T.CAPTION)] if locked else []),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), col={"xs": 4, "sm": 2}, padding=8,
            border_radius=th.R.MD,
            border=ft.Border.all(2 if k == seed else 1, th.ACCENT if k == seed else ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.with_opacity(0.10, th.ACCENT) if k == seed else ft.Colors.SURFACE_CONTAINER_LOWEST,
            on_click=None if locked else (lambda _, key=k: pick(key)), ink=not locked,
            tooltip=f"Reach level {sp.level} to unlock" if locked else f"Plant a {sp.name.lower()}"))
    seed_card = th.card(th.heading("Today's seed", icon=ft.Icons.SPA_OUTLINED),
                        th.muted("Pick the tree you're growing today. Levels unlock new species.", th.T.CAPTION),
                        ft.ResponsiveRow(seeds, spacing=8, run_spacing=8))

    def how(_):
        cx.info_sheet(app.page, "How your tree grows",
                      th.muted("Each day earns up to 100 points:", th.T.LABEL),
                      *[ft.Row([ft.Icon(ic, size=18, color=th.ACCENT), ft.Text(t, size=th.T.LABEL, expand=True),
                                ft.Text(pts, size=th.T.LABEL, font_family=th.FONT_BOLD)])
                        for ic, t, pts in RULES],
                      th.muted(f"{TREE_DAY} points grows a full tree and keeps your streak alive. Eating more than 25% over "
                               "your calories caps the day at a sapling. Every 7 days in a row earns a shield (hold up to 2) "
                               "that covers one missed day.", th.T.CAPTION),
                      ft.Row([th.chip(f"{name} {lo}+", th.ACCENT) for lo, name, _ in STAGES], wrap=True, spacing=6))

    from .forest_view import ForestView
    return [ForestView(app).control, hero, stats, calendar, seed_card,
            ft.Row([ft.TextButton("How your tree grows", icon=ft.Icons.HELP_OUTLINE, on_click=how)],
                   alignment=ft.MainAxisAlignment.CENTER)]


RULES = [(ft.Icons.LOCAL_FIRE_DEPARTMENT, "Calories close to target (within 10%)", "20"),
         (ft.Icons.FITNESS_CENTER, "Protein 90% or more", "15"),
         (ft.Icons.RICE_BOWL, "Carbs and fat near target", "15"),
         (ft.Icons.SPA_OUTLINED, "Vitamins and minerals covered", "20"),
         (ft.Icons.WATER_DROP, "Water goal", "15"),
         (ft.Icons.MEDICATION, "Supplements taken", "10")]
