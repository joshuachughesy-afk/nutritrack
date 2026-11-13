"""Trends: weight log + trend + adaptive TDEE, calories vs target, macro/water/supplement averages, micronutrient coverage."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import flet as ft
import flet_charts as fch

from ..core.nutrition import MICRO_BY_KEY, MICROS, fmt, kg_to_lb, lb_to_kg
from ..core.trends import weight_trend
from ..service import today_key
from . import components as cx
from . import theme as th

if TYPE_CHECKING:
    from .app import App

GRID = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)


def build(app: "App") -> list[ft.Control]:
    days = app.ui.trend_days

    def set_range(v):
        app.ui.trend_days = int(v)
        app.render()

    rng = cx.tabs([(str(n), f"{n} days") for n in (7, 30, 90)], str(days), set_range)
    summary = app.svc.period(days)
    return [rng, _adaptive_card(app), _weight_card(app, days), _calorie_card(app, summary), _averages_card(app, summary),
            _micro_card(summary)]


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
            field.error = "Check the number"
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
            min_x=max(0, x(shown[0][0]) - 1), max_x=days - 1, min_y=round(lo - pad, 1), max_y=round(hi + pad, 1), height=180, interactive=True,
            horizontal_grid_lines=fch.ChartGridLines(color=GRID, width=1),
            left_axis=fch.ChartAxis(label_size=40, show_min=False, show_max=False),
            bottom_axis=_date_axis(start, days),
        )
        delta = conv(shown[-1][2]) - conv(shown[0][2])
        items += [
            ft.Row([_legend(th.MACRO_COLORS["protein"], "Scale", dot=True), _legend(th.ACCENT, "Trend")], spacing=16),
            chart,
            th.muted(f"Trend {conv(shown[-1][2]):.1f} {unit}, {'up' if delta >= 0 else 'down'} {abs(delta):.1f} {unit} over this "
                     "period. Daily readings swing with water and food; the smooth trend line shows where you're really "
                     "heading.", th.T.CAPTION),
        ]
    else:
        items.append(th.muted("Log your weight a few mornings a week (after the bathroom, before eating) to see your trend.",
                              th.T.CAPTION))
    return th.card(*items)


def _adaptive_card(app: "App") -> ft.Control:
    """Your real daily burn, learned from what you log and how your weight moves."""
    p = app.store.profile()
    a = app.svc.adaptive()

    def use(on: bool):
        prof = app.store.profile()
        prof.use_adaptive = on
        app.store.save_profile(prof)
        app.render()
        app.toast("Your targets now follow your real burn" if on else "Back to the standard estimate")

    def how(_):
        cx.info_sheet(app.page, "How we learn your burn",
                      th.muted("We compare what you logged with how your weight trend moved. If you ate 2,800 a day and "
                               "held steady, you burn about 2,800. It needs most of your food logged and a few weigh-ins "
                               "a week, and it updates as you go.", th.T.LABEL),
                      th.muted(f"Standard estimate (Mifflin-St Jeor × activity): {fmt(a.formula)} kcal a day.", th.T.CAPTION))

    head = th.heading("Your real daily burn", ft.IconButton(ft.Icons.INFO_OUTLINE, icon_size=18, on_click=how,
                                                            tooltip="How this works"),
                      icon=ft.Icons.AUTO_GRAPH)
    if not a.ready:
        return th.card(head, th.muted(f"{a.reason} Until then your targets use the standard estimate "
                                      f"({fmt(a.formula)} kcal a day).", th.T.LABEL), spacing=8)
    diff = a.estimate - a.formula
    body = [head,
            ft.Row([th.display(f"~{fmt(a.estimate)}", 28), th.muted("kcal a day", th.T.LABEL)],
                   vertical_alignment=ft.CrossAxisAlignment.END, spacing=6),
            th.muted(f"Learned from {a.intake_days} logged days and {a.weigh_ins} weigh-ins. That's "
                     f"{fmt(abs(diff))} {'more' if diff >= 0 else 'less'} than the standard estimate.", th.T.CAPTION)]
    if p.use_adaptive:
        body += [cx.note(f"Your targets use {fmt(a.blended)} kcal a day as your burn.", "good"),
                 ft.TextButton("Use the standard estimate instead", on_click=lambda _: use(False))]
    else:
        body.append(ft.Row([ft.FilledButton("Use it for my targets", icon=ft.Icons.CHECK, on_click=lambda _: use(True))]))
    return th.card(*body, spacing=8)


# ---------- calories ----------
def _calorie_card(app: "App", s) -> ft.Control:
    n = len(s.days)
    start = date.fromisoformat(s.days[0].date).toordinal()
    width = max(3, min(18, 220 // n))
    top = max([r.kcal for r in s.days] + [r.target_kcal for r in s.days] + [1]) * 1.1
    groups = []
    for i, r in enumerate(s.days):
        groups.append(fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
            from_y=0, to_y=round(r.kcal), width=width,
            color=(ft.Colors.with_opacity(0.45, th.ACCENT) if r.date == today_key() else th.ACCENT) if r.logged
            else ft.Colors.TRANSPARENT,
            bg_to_y=round(r.target_kcal), bgcolor=ft.Colors.with_opacity(0.14, th.ACCENT), border_radius=4,
            tooltip=fch.BarChartRodTooltip(f"{date.fromisoformat(r.date).strftime('%a %d %b')}\n{fmt(r.kcal)} / {fmt(r.target_kcal)} kcal"),
        )]))
    chart = fch.BarChart(groups=groups, max_y=round(top), height=180, interactive=True,
                         horizontal_grid_lines=fch.ChartGridLines(color=GRID, width=1),
                         left_axis=fch.ChartAxis(label_size=44, show_max=False),
                         bottom_axis=_date_axis(start, n), group_alignment=ft.MainAxisAlignment.SPACE_AROUND)
    avg_diff = s.avg_kcal - s.avg_target_kcal
    if not s.logged_days:
        summary = "No days logged in this period yet."
    elif abs(avg_diff) <= s.avg_target_kcal * 0.05:
        summary = f"Averaging {fmt(s.avg_kcal)} kcal on {s.logged_days} logged days, right around your target."
    else:
        summary = (f"Averaging {fmt(s.avg_kcal)} kcal on {s.logged_days} logged days, about {fmt(abs(avg_diff))} "
                   f"{'above' if avg_diff > 0 else 'below'} your target of {fmt(s.avg_target_kcal)}.")
    return th.card(
        th.heading("Calories", icon=ft.Icons.LOCAL_FIRE_DEPARTMENT, icon_color=th.FIRE),
        ft.Row([_legend(th.ACCENT, "Eaten"), _legend(ft.Colors.with_opacity(0.3, th.ACCENT), "Target"),
                _legend(ft.Colors.with_opacity(0.45, th.ACCENT), "Today so far")], spacing=14, wrap=True),
        chart, th.muted(summary, th.T.CAPTION),
    )


# ---------- averages ----------
def _averages_card(app: "App", s) -> ft.Control:
    def row(label, value, target, unit, color):
        pct = value / target if target else 0
        return cx.metric_row(label, f"{fmt(value)} of {fmt(target)} {unit} · {round(pct * 100)}%", pct, color)

    rows = [row(k.title(), s.avg_macros[k], s.avg_macro_targets[k], "g", th.MACRO_COLORS[k]) for k in ("carbs", "protein", "fat")]
    rows.append(row("Water", s.avg_water / 1000, s.avg_water_target / 1000, "L", th.MACRO_COLORS["water"]))
    tiles = [cx.stat_tile("Full trees", f"{s.tree_days} of {len(s.days)}", "days", icon=ft.Icons.PARK)]
    if s.supplement_adherence is not None:
        tiles.append(cx.stat_tile("Supplements", f"{round(s.supplement_adherence * 100)}%", "of doses taken",
                                  icon=ft.Icons.MEDICATION))
    return th.card(th.heading("Daily averages", f"{s.logged_days} logged days", icon=ft.Icons.INSIGHTS),
                   *rows, ft.Row(tiles, spacing=8))


# ---------- micronutrients ----------
def _micro_card(s) -> ft.Control:
    if not s.logged_days:
        return th.card(th.heading("Vitamins & minerals", icon=ft.Icons.SPA_OUTLINED),
                       th.muted("Log a few days to see which nutrients you regularly miss.", th.T.LABEL))
    rows = []
    covered = 0
    for m in MICROS:
        if m.limit or m.key not in s.micro_avg:
            continue
        v = s.micro_avg[m.key]
        covered += v >= 1
        rows.append(ft.Container(cx.metric_row(m.label, f"{round(v * 100)}%", min(v, 1),
                                               th.ACCENT_SOFT if v >= 1 else th.MACRO_COLORS["protein"],
                                               icon=ft.Icons.CHECK_CIRCLE if v >= 1 else None, height=6),
                                 col={"xs": 12, "sm": 6}))
    low = [MICRO_BY_KEY[k].label for k in s.consistently_low]
    note = cx.note(f"Often low: {', '.join(low)}. Today's Vitamins & minerals card suggests foods that fill these.", "info") \
        if low else cx.note("Nothing is consistently low. Great variety.", "good")
    return th.card(th.heading("Vitamins & minerals", f"{covered} of {len(rows)} covered on average", icon=ft.Icons.SPA_OUTLINED),
                   note, ft.ResponsiveRow(rows, spacing=16, run_spacing=10))


# ---------- helpers ----------
def _legend(color, label: str, dot: bool = False) -> ft.Control:
    mark = ft.Container(width=10, height=10, bgcolor=color, border_radius=5) if dot else \
        ft.Container(width=16, height=3, bgcolor=color, border_radius=2)
    return ft.Row([mark, ft.Text(label, size=th.T.CAPTION)], spacing=6, tight=True)


def _date_axis(start_ordinal: int, n: int) -> fch.ChartAxis:
    step = 1 if n <= 7 else 7 if n <= 30 else 14
    labels = []
    for i in range(0, n, step):
        d = date.fromordinal(start_ordinal + i)
        labels.append(fch.ChartAxisLabel(value=i, label=ft.Text(d.strftime("%a") if n <= 7 else d.strftime("%d %b"), size=11)))
    return fch.ChartAxis(labels=labels, label_size=24, label_spacing=step)
