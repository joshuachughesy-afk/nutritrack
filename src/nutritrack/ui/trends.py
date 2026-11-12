"""Trends: weight log + trend + adaptive TDEE, calories vs target, macro/water/supplement averages, micronutrient coverage."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import flet as ft
import flet_charts as fch

from ..core.nutrition import MICRO_BY_KEY, MICROS, fmt, kg_to_lb, lb_to_kg
from ..core.trends import weight_trend
from ..service import today_key
from . import theme as th

if TYPE_CHECKING:
    from .app import App

GRID = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)


def build(app: "App") -> list[ft.Control]:
    days = getattr(app, "trend_days", 7)

    def set_range(e):
        app.trend_days = int(list(e.control.selected)[0])
        app.render()

    rng = ft.SegmentedButton(segments=[ft.Segment(value=str(n), label=ft.Text(f"{n} days")) for n in (7, 30, 90)],
                             selected=[str(days)], on_change=set_range, show_selected_icon=False)
    summary = app.svc.period(days)
    return [rng, _weight_card(app, days), _calorie_card(app, summary), _averages_card(app, summary), _micro_card(summary)]


# ---------- weight ----------
def _weight_card(app: "App", days: int) -> ft.Control:
    imperial = app.svc.imperial
    unit = "lb" if imperial else "kg"
    conv = kg_to_lb if imperial else (lambda x: x)
    today = today_key()
    current = app.store.day(today)["weight_kg"]
    field = th.num_field("Today's weight", f"{conv(current):.1f}" if current else None, suffix=unit, expand=True)

    def save(_):
        v = th.parse_num(field.value)
        kg = lb_to_kg(v) if imperial else v
        if not 25 <= kg <= 400:
            field.error = "Check this value"
            app.page.update(); return
        app.svc.log_weight(today, round(kg, 2))
        app.render()
        app.toast("Weight logged")

    series = weight_trend(app.store.weights())
    start = date.fromisoformat(today).toordinal() - days + 1
    shown = [(d, w, t) for d, w, t in series if date.fromisoformat(d).toordinal() >= start]
    items: list[ft.Control] = [th.heading("Weight", icon=ft.Icons.MONITOR_WEIGHT),
                               ft.Row([field, ft.FilledButton("Log", icon=ft.Icons.CHECK, on_click=save)],
                                      vertical_alignment=ft.CrossAxisAlignment.CENTER)]
    if shown:
        x = lambda d: date.fromisoformat(d).toordinal() - start  # noqa: E731
        ys = [conv(v) for _, w, t in shown for v in (w, t)]
        lo, hi = min(ys), max(ys)
        pad = max(0.5, (hi - lo) * 0.15)
        scale_pts = [fch.LineChartDataPoint(x(d), round(conv(w), 2), tooltip=f"{d[5:]}: {conv(w):.1f} {unit}") for d, w, _ in shown]
        trend_pts = [fch.LineChartDataPoint(x(d), round(conv(t), 2), tooltip=f"trend {conv(t):.1f} {unit}") for d, _, t in shown]
        chart = fch.LineChart(
            data_series=[
                fch.LineChartData(points=scale_pts, stroke_width=0, color=ft.Colors.with_opacity(0.55, th.MACRO_COLORS["protein"]),
                                  point=fch.ChartCirclePoint(radius=4, color=th.MACRO_COLORS["protein"], stroke_width=0)),
                fch.LineChartData(points=trend_pts, stroke_width=2, color=th.ACCENT, curved=True, point=False),
            ],
            min_x=0, max_x=days - 1, min_y=round(lo - pad, 1), max_y=round(hi + pad, 1), height=180, interactive=True,
            horizontal_grid_lines=fch.ChartGridLines(color=GRID, width=1),
            left_axis=fch.ChartAxis(label_size=40, show_min=False, show_max=False),
            bottom_axis=_date_axis(start, days),
        )
        delta = conv(shown[-1][2]) - conv(shown[0][2])
        items += [
            ft.Row([_legend(th.MACRO_COLORS["protein"], "Scale", dot=True), _legend(th.ACCENT, "Trend")], spacing=16),
            chart,
            th.muted(f"Trend {conv(shown[-1][2]):.1f} {unit} · {'+' if delta >= 0 else '−'}{abs(delta):.1f} {unit} over this "
                     "period. Daily readings swing with water and food; the trend shows the real direction.", 12),
        ]
    else:
        items.append(th.muted("Log your weight a few mornings a week (after the bathroom, before eating) to see your trend.", 12))
    items.append(_adaptive_block(app))
    return th.card(*items)


def _adaptive_block(app: "App") -> ft.Control:
    p = app.store.profile()
    a = app.svc.adaptive()

    def toggle(e):
        prof = app.store.profile()
        prof.use_adaptive = bool(e.control.value)
        app.store.save_profile(prof)
        app.render()
        app.toast("Targets now adapt to your data" if prof.use_adaptive else "Back to the formula estimate")

    if a.ready:
        diff = a.estimate - a.formula
        text = (f"Your data suggests you burn about {fmt(a.estimate)} kcal/day ({'+' if diff >= 0 else '−'}{fmt(abs(diff))} vs the "
                f"formula's {fmt(a.formula)}). Based on {a.intake_days} logged days and {a.weigh_ins} weigh-ins; "
                f"confidence {round(a.confidence * 100)}%." + (f" Targets use {fmt(a.blended)}." if p.use_adaptive else ""))
    else:
        text = f"Adaptive TDEE: {a.reason} Until then targets use the formula ({fmt(a.formula)} kcal/day)."
    return ft.Container(ft.Column([
        ft.Row([ft.Icon(ft.Icons.AUTO_GRAPH, color=th.ACCENT, size=20),
                ft.Text("Adaptive calorie target", font_family=th.FONT_SEMI, size=14, expand=True),
                ft.Switch(value=p.use_adaptive, on_change=toggle)]),
        ft.Text(text, size=12),
        th.muted("It compares what you logged with how your weight trend moved, which works out what you actually burn. "
                 "It only works if you log most of what you eat.", 11),
    ], spacing=4), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=12, padding=12)


# ---------- calories ----------
def _calorie_card(app: "App", s) -> ft.Control:
    n = len(s.days)
    start = date.fromisoformat(s.days[0].date).toordinal()
    width = max(3, min(18, 220 // n))
    top = max([r.kcal for r in s.days] + [r.target_kcal for r in s.days] + [1]) * 1.1
    groups = []
    for i, r in enumerate(s.days):
        groups.append(fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
            from_y=0, to_y=round(r.kcal), width=width, color=th.ACCENT if r.logged else ft.Colors.TRANSPARENT,
            bg_to_y=round(r.target_kcal), bgcolor=ft.Colors.with_opacity(0.14, th.ACCENT), border_radius=4,
            tooltip=fch.BarChartRodTooltip(f"{date.fromisoformat(r.date).strftime('%a %d %b')}\n{fmt(r.kcal)} / {fmt(r.target_kcal)} kcal"),
        )]))
    chart = fch.BarChart(groups=groups, max_y=round(top), height=180, interactive=True,
                         horizontal_grid_lines=fch.ChartGridLines(color=GRID, width=1),
                         left_axis=fch.ChartAxis(label_size=44, show_max=False),
                         bottom_axis=_date_axis(start, n), group_alignment=ft.MainAxisAlignment.SPACE_AROUND)
    avg_diff = s.avg_kcal - s.avg_target_kcal
    return th.card(
        th.heading("Calories", icon=ft.Icons.LOCAL_FIRE_DEPARTMENT, icon_color="#e8590c"),
        ft.Row([_legend(th.ACCENT, "Eaten"), _legend(ft.Colors.with_opacity(0.3, th.ACCENT), "Target")], spacing=16),
        chart,
        th.muted(f"Average {fmt(s.avg_kcal)} kcal on {s.logged_days} logged days, "
                 f"{fmt(abs(avg_diff))} {'over' if avg_diff > 0 else 'under'} your average target of {fmt(s.avg_target_kcal)}."
                 if s.logged_days else "No days logged in this period yet.", 12),
    )


# ---------- averages ----------
def _averages_card(app: "App", s) -> ft.Control:
    def row(label, value, target, unit, color):
        pct = value / target if target else 0
        return ft.Column([
            ft.Row([th.dot(color), ft.Text(label, size=13, font_family=th.FONT_SEMI, expand=True),
                    th.muted(f"{fmt(value)} / {fmt(target)} {unit}", 12),
                    ft.Text(f"{round(pct * 100)}%", size=12, font_family=th.FONT_BOLD, width=44, text_align=ft.TextAlign.RIGHT)]),
            th.bar(pct, color),
        ], spacing=4)

    rows = [row(k.title(), s.avg_macros[k], s.avg_macro_targets[k], "g", th.MACRO_COLORS[k]) for k in ("carbs", "protein", "fat")]
    rows.append(row("Water", s.avg_water / 1000, s.avg_water_target / 1000, "L", th.MACRO_COLORS["water"]))
    stats = [ft.Text(f"Tree days: {s.tree_days} of {len(s.days)}", size=13)]
    if s.supplement_adherence is not None:
        stats.append(ft.Text(f"Supplements taken: {round(s.supplement_adherence * 100)}% of scheduled doses", size=13))
    return th.card(th.heading("Daily averages", th.muted(f"{s.logged_days} logged days", 12), icon=ft.Icons.INSIGHTS),
                   *rows, ft.Divider(height=8), *stats)


# ---------- micronutrients ----------
def _micro_card(s) -> ft.Control:
    if not s.logged_days:
        return th.card(th.heading("Micronutrient coverage"), th.muted("Log some days to see which nutrients you regularly miss.", 12))
    rows = []
    for m in MICROS:
        if m.limit or m.key not in s.micro_avg:
            continue
        v = s.micro_avg[m.key]
        status = "met" if v >= 1 else "mid" if v >= 0.7 else "low"
        rows.append(ft.Container(ft.Column([
            ft.Row([ft.Text(m.label, size=13, expand=True),
                    ft.Text(f"{round(v * 100)}%", size=12, font_family=th.FONT_BOLD, color=th.STATUS_COLORS[status])]),
            th.bar(v, th.STATUS_COLORS[status], height=6)], spacing=3), col={"xs": 12, "sm": 6}))
    low = [MICRO_BY_KEY[k].label for k in s.consistently_low]
    note = (f"Consistently low: {', '.join(low)}. Check the evening pace check for foods that fill these, or ask a "
            "professional whether a supplement makes sense." if low else "No nutrient is consistently low. Great variety.")
    return th.card(th.heading("Micronutrient coverage", th.muted("average % of target", 12), icon=ft.Icons.SPA),
                   ft.ResponsiveRow(rows, spacing=16, run_spacing=10), ft.Text(note, size=12))


# ---------- helpers ----------
def _legend(color, label: str, dot: bool = False) -> ft.Control:
    mark = ft.Container(width=10, height=10, bgcolor=color, border_radius=5) if dot else \
        ft.Container(width=16, height=3, bgcolor=color, border_radius=2)
    return ft.Row([mark, ft.Text(label, size=12)], spacing=6, tight=True)


def _date_axis(start_ordinal: int, n: int) -> fch.ChartAxis:
    step = 1 if n <= 7 else 7 if n <= 30 else 14
    labels = []
    for i in range(0, n, step):
        d = date.fromordinal(start_ordinal + i)
        labels.append(fch.ChartAxisLabel(value=i, label=ft.Text(d.strftime("%a") if n <= 7 else d.strftime("%d %b"), size=10)))
    return fch.ChartAxis(labels=labels, label_size=24)
