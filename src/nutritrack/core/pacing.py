"""Pacing engine: "am I on track for THIS time of day?", not just "how much is left?"."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .foods import Food
from .nutrition import MICROS, Micro, Nutrients, Targets, fmt

DEFAULT_SCHEDULE = {"wake": "07:00", "sleep": "23:00", "breakfast": "08:00", "lunch": "12:30", "dinner": "18:30"}

MEAL_LABELS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snacks": "Snacks"}
MEAL_ORDER = list(MEAL_LABELS)


def to_min(hhmm: str) -> int:
    h, _, m = str(hhmm).partition(":")
    return int(h) * 60 + int(m or 0)


def from_min(m: float) -> str:
    return f"{int(m // 60) % 24:02d}:{int(m % 60 + 0.5):02d}"


def _interpolate(points: list[tuple[float, float]], x: float) -> float:
    if x <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x <= x1:
            return y1 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]


def expected_food_share(sched: dict, now_min: float) -> float:
    """Share of the day's food you'd expect to have eaten by now. Each meal is "done" ~30–45 min after it starts."""
    pts = [
        (to_min(sched["wake"]), 0.0),
        (to_min(sched["breakfast"]) + 30, 0.25),
        (to_min(sched["lunch"]) + 30, 0.55),
        (to_min(sched["dinner"]) + 45, 0.9),
        (max(to_min(sched["dinner"]) + 46, to_min(sched["sleep"]) - 60), 1.0),
    ]
    return _interpolate(pts, now_min)


def expected_water_share(sched: dict, now_min: float) -> float:
    """Water spreads evenly from waking until an hour before bed."""
    return _interpolate([(to_min(sched["wake"]), 0.0), (to_min(sched["sleep"]) - 60, 1.0)], now_min)


@dataclass
class PaceRow:
    key: str
    label: str
    unit: str
    target: float
    actual: float
    share: float
    ahead_ok: bool
    expected: float
    status: str  # early | behind | on | ahead

    @property
    def gap(self) -> float:
        return self.expected - self.actual


def compute_pace(targets: Targets, totals: Nutrients, water_ml: float, sched: dict, now_min: float) -> list[PaceRow]:
    food = expected_food_share(sched, now_min)
    water = expected_water_share(sched, now_min)
    items = [
        ("kcal", "Calories", "kcal", targets.kcal, totals["kcal"], food, False),
        ("protein", "Protein", "g", targets.protein, totals["protein"], food, True),
        ("carbs", "Carbs", "g", targets.carbs, totals["carbs"], food, False),
        ("fat", "Fat", "g", targets.fat, totals["fat"], food, False),
        ("water", "Water", "ml", targets.water_ml, water_ml, water, True),
    ]
    rows = []
    for key, label, unit, target, actual, share, ahead_ok in items:
        expected = target * share
        if share < 0.12:
            status = "early"
        elif actual < expected * 0.8:
            status = "behind"
        elif actual > expected * 1.2 and actual > target * 0.3:
            status = "ahead"
        else:
            status = "on"
        rows.append(PaceRow(key, label, unit, target, actual, share, ahead_ok, expected, status))
    return rows


@dataclass
class MicroGap:
    micro: Micro
    pct: float
    foods: list[tuple[str, str, float]]  # (name, serving label, % of target per serving)


def micro_gaps(targets: Targets, totals: Nutrients, foods: list[Food], limit: int = 4) -> list[MicroGap]:
    """Micronutrients under half their target, with the foods that close the gap best per serving."""
    low = []
    for m in MICROS:
        if m.limit:
            continue
        pct = totals.get(m.key, 0) / targets.micros[m.key].target
        if pct < 0.5:
            low.append((pct, m))
    low.sort(key=lambda x: x[0])
    out = []
    for pct, m in low[:limit]:
        target = targets.micros[m.key].target
        ranked = sorted(((f, f.per100.get(m.key, 0) * f.servings[0].g / 100) for f in foods), key=lambda x: -x[1])
        best = [(f.name, f.servings[0].label, amt / target) for f, amt in ranked if amt > 0][:3]
        out.append(MicroGap(m, pct, best))
    return out


def pace_summary(rows: list[PaceRow], water_fmt: Callable[[float], str]) -> tuple[bool, str]:
    """One-line, non-judgmental summary: (on_track, text)."""
    relevant = [r for r in rows if r.status != "early"]
    if not relevant:
        return True, "Early in the day. Your targets are set."

    def amount(r: PaceRow) -> str:
        v = max(0.0, r.gap)
        return water_fmt(v) if r.unit == "ml" else f"{fmt(v)} {r.unit}"

    behind = [r for r in relevant if r.status == "behind"]
    ahead = [r for r in relevant if r.status == "ahead" and not r.ahead_ok]
    parts = []
    if behind:
        parts.append("Behind pace: " + ", ".join(f"{r.label.lower()} (~{amount(r)})" for r in behind))
    if ahead:
        parts.append("Ahead: " + ", ".join(r.label.lower() for r in ahead) + ". Go lighter later")
    if not parts:
        return True, "Everything is on pace. Nice work."
    return False, ". ".join(parts) + "."
