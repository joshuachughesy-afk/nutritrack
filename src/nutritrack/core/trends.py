"""Trends: smoothed weight trend, adaptive TDEE estimate, and period summaries for charts.

Adaptive TDEE (the MacroFactor-style idea from docs/research.md): what you ate minus the energy stored or released,
as shown by your weight trend, is what you actually burned.
    TDEE ≈ average logged intake − (trend weight change kg × 7,700 kcal/kg) ÷ days
Daily scale weight swings 1–2 kg with water and food. For display we show an exponentially smoothed trend (α = 0.1 per
weigh-in, as in Walker's "Hacker's Diet"). For the estimate we use a least-squares slope through the weigh-ins: it
averages out the same noise but, unlike the smoothed trend, doesn't lag behind real change (a lagging trend would
under-read weight change and bias TDEE toward intake). The estimate is blended with the Mifflin-St Jeor formula in
proportion to how much data there is, and capped at ±25% of the formula so one bad week can't swing your targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

KCAL_PER_KG = 7700
ALPHA = 0.1
MIN_DAY_KCAL = 1000      # days logged below this are treated as incomplete logging, not real intake
WINDOW_DAYS = 28
MIN_SPAN_DAYS = 14
MIN_INTAKE_DAYS = 10
MIN_WEIGH_INS = 6


def weight_trend(weights: list[tuple[str, float]]) -> list[tuple[str, float, float]]:
    """[(date, scale_kg)] sorted by date -> [(date, scale_kg, trend_kg)] for each weigh-in."""
    out, trend = [], None
    for d, w in sorted(weights):
        trend = w if trend is None else trend + ALPHA * (w - trend)
        out.append((d, w, trend))
    return out


def slope_kg_per_day(weights: list[tuple[str, float]]) -> float:
    """Least-squares slope of scale weight against time."""
    xs = [date.fromisoformat(d).toordinal() for d, _ in weights]
    ys = [w for _, w in weights]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0


def trend_on(series: list[tuple[str, float, float]], day: str) -> float | None:
    """Trend value as of `day` (carried forward from the last weigh-in on or before it)."""
    val = None
    for d, _, t in series:
        if d <= day:
            val = t
        else:
            break
    return val


@dataclass
class AdaptiveTDEE:
    ready: bool
    formula: float
    estimate: float | None = None      # raw data-driven estimate
    blended: float | None = None       # what targets use
    confidence: float = 0.0
    avg_intake: float | None = None
    trend_change_kg: float | None = None
    span_days: int = 0
    intake_days: int = 0
    weigh_ins: int = 0
    reason: str = ""


def adaptive_tdee(intake: dict[str, float], weights: list[tuple[str, float]], formula_tdee: float, today: str) -> AdaptiveTDEE:
    """`intake` maps date -> logged kcal. Uses the last 28 complete days (today is excluded: it isn't over)."""
    end = date.fromisoformat(today) - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    in_window = [(d, w) for d, w in weights if start.isoformat() <= d <= end.isoformat()]
    days = [(start + timedelta(days=i)).isoformat() for i in range(WINDOW_DAYS)]
    logged = [intake[d] for d in days if intake.get(d, 0) >= MIN_DAY_KCAL]
    res = AdaptiveTDEE(ready=False, formula=formula_tdee, intake_days=len(logged), weigh_ins=len(in_window))
    if len(in_window) < 2:
        res.reason = f"Log your weight a few times a week ({MIN_WEIGH_INS}+ weigh-ins over 2 weeks)."
        return res
    first, last = in_window[0][0], in_window[-1][0]
    span = (date.fromisoformat(last) - date.fromisoformat(first)).days
    res.span_days = span
    if span < MIN_SPAN_DAYS or len(in_window) < MIN_WEIGH_INS or len(logged) < MIN_INTAKE_DAYS:
        need = []
        if span < MIN_SPAN_DAYS:
            need.append(f"{MIN_SPAN_DAYS - span} more days of weigh-ins")
        if len(in_window) < MIN_WEIGH_INS:
            need.append(f"{MIN_WEIGH_INS - len(in_window)} more weigh-ins")
        if len(logged) < MIN_INTAKE_DAYS:
            need.append(f"{MIN_INTAKE_DAYS - len(logged)} more fully logged days")
        res.reason = "Still learning: needs " + ", ".join(need) + "."
        return res
    slope = slope_kg_per_day(in_window)
    avg = sum(logged) / len(logged)
    est = avg - slope * KCAL_PER_KG
    conf = min(1.0, len(logged) / 21, len(in_window) / 10, span / 21)
    blended = formula_tdee * (1 - conf) + est * conf
    blended = max(formula_tdee * 0.75, min(formula_tdee * 1.25, blended))
    return AdaptiveTDEE(True, formula_tdee, est, blended, conf, avg, slope * span, span, len(logged), len(in_window))


@dataclass
class DayRow:
    date: str
    kcal: float
    target_kcal: float
    protein: float
    carbs: float
    fat: float
    target_protein: float
    target_carbs: float
    target_fat: float
    water_ml: float
    target_water: float
    doses_taken: int
    doses_scheduled: int
    score: int | None
    micro_pct: dict[str, float] = field(default_factory=dict)  # micro key -> fraction of target
    logged: bool = False


@dataclass
class PeriodSummary:
    days: list[DayRow]
    logged_days: int
    avg_kcal: float
    avg_target_kcal: float
    avg_macros: dict[str, float]
    avg_macro_targets: dict[str, float]
    avg_water: float
    avg_water_target: float
    supplement_adherence: float | None
    tree_days: int
    micro_avg: dict[str, float]          # average fraction of target over logged days
    consistently_low: list[str]          # micros averaging < 70%


def summarize(rows: list[DayRow]) -> PeriodSummary:
    logged = [r for r in rows if r.logged]
    n = len(logged) or 1

    def avg(attr):
        return sum(getattr(r, attr) for r in logged) / n if logged else 0.0

    sched = sum(r.doses_scheduled for r in rows)
    micro_keys = list(logged[0].micro_pct) if logged else []
    micro_avg = {k: sum(r.micro_pct.get(k, 0) for r in logged) / n for k in micro_keys}
    return PeriodSummary(
        days=rows, logged_days=len(logged),
        avg_kcal=avg("kcal"), avg_target_kcal=avg("target_kcal"),
        avg_macros={k: avg(k) for k in ("protein", "carbs", "fat")},
        avg_macro_targets={k: avg(f"target_{k}") for k in ("protein", "carbs", "fat")},
        avg_water=avg("water_ml"), avg_water_target=avg("target_water"),
        supplement_adherence=(sum(r.doses_taken for r in rows) / sched) if sched else None,
        tree_days=sum(1 for r in rows if r.score is not None and r.score >= 65),
        micro_avg=micro_avg,
        consistently_low=[k for k, v in sorted(micro_avg.items(), key=lambda x: x[1]) if v < 0.7],
    )
