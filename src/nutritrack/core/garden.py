"""Progression: each day plants a seed; how well you hit your goals decides how big that day's tree grows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .nutrition import MICROS, Nutrients, Targets, fmt, jround, micro_status
from .pacing import MicroGap

TREE_DAY = 65  # score that counts as a "tree day" for streaks

STAGES = [
    (0, "Seed", "Freshly planted. Log something to get it going."),
    (15, "Sprout", "Breaking ground."),
    (40, "Sapling", "Taking root."),
    (65, "Young tree", "A solid day. This counts toward your streak."),
    (85, "Mighty tree", "Excellent. Nearly every goal hit."),
    (95, "Flourishing tree", "A perfect day. It's blossoming."),
]


def stage_for(score: float) -> int:
    return max(i for i, (lo, _, _) in enumerate(STAGES) if score >= lo)


LEVELS = [0, 300, 800, 1500, 2500, 4000, 6000, 8500, 11500, 15000]


@dataclass(frozen=True)
class Species:
    name: str
    level: int
    canopy: tuple[str, str]
    trunk: str
    shape: str  # round | cone | oval
    bloom: str | None = None


SPECIES: dict[str, Species] = {
    "oak": Species("Oak", 1, ("#3f8f4f", "#2f7a40"), "#7a5232", "round"),
    "pine": Species("Pine", 2, ("#2f6f4a", "#245c3c"), "#6b4a2e", "cone"),
    "cherry": Species("Cherry blossom", 3, ("#f2a7c3", "#e687ab"), "#6e4434", "round", "#ffffff"),
    "maple": Species("Autumn maple", 4, ("#e0823a", "#c9612a"), "#6b4430", "round"),
    "birch": Species("Birch", 5, ("#9cc95a", "#7fb143"), "#e9e4d8", "oval"),
    "golden": Species("Golden tree", 7, ("#f2c94c", "#e0a92e"), "#7a5a2a", "round", "#fff6c9"),
    "jacaranda": Species("Jacaranda", 8, ("#9b7fe0", "#7f63c9"), "#5e4636", "round", "#e3d6ff"),
    "ginkgo": Species("Ginkgo", 10, ("#e8d35a", "#cdb73c"), "#6e5a3a", "oval"),
}


# ---------- rewards: things that appear in your forest valley as you keep going ----------
@dataclass(frozen=True)
class Reward:
    key: str
    name: str
    blurb: str
    kind: str        # tree_days | best_streak | level
    need: int
    icon: str        # Material icon name, for the UI


REWARDS: list[Reward] = [
    Reward("flowers", "Wildflowers", "Meadow flowers along the stream", "tree_days", 3, "LOCAL_FLORIST"),
    Reward("stones", "Stepping stones", "A way across the stream", "tree_days", 7, "WAVES"),
    Reward("birds", "Songbirds", "Birds circling over the valley", "best_streak", 7, "FLUTTER_DASH"),
    Reward("bench", "Bench", "A place to sit by the water", "level", 3, "CHAIR"),
    Reward("deer", "Deer", "A deer grazing near your trees", "best_streak", 14, "PETS"),
    Reward("bridge", "Footbridge", "A wooden bridge over the stream", "tree_days", 21, "ROUTE"),
    Reward("lanterns", "Lanterns", "Lanterns along the path", "level", 5, "LIGHT"),
    Reward("fox", "Fox", "A fox curled up on the bank", "best_streak", 30, "PETS"),
    Reward("cabin", "Cabin", "A cabin at the edge of the forest", "level", 6, "CABIN"),
    Reward("orchard", "Orchard", "Fruit trees on the far slope", "tree_days", 60, "PARK"),
    Reward("windmill", "Windmill", "A windmill on the hill", "level", 9, "WIND_POWER"),
    Reward("aurora", "Northern lights", "Ribbons of light over the mountains", "best_streak", 100, "AUTO_AWESOME"),
]


def reward_progress(r: Reward, h: "History", level: int) -> int:
    return {"tree_days": h.tree_days, "best_streak": h.best, "level": level}[r.kind]


def rewards_status(h: "History", level: int) -> list[tuple[Reward, bool, int]]:
    """Every reward with (unlocked?, how far there is still to go)."""
    out = []
    for r in REWARDS:
        have = reward_progress(r, h, level)
        out.append((r, have >= r.need, max(0, r.need - have)))
    return out


def unlocked_rewards(h: "History", level: int) -> tuple[str, ...]:
    return tuple(r.key for r, ok, _ in rewards_status(h, level) if ok)


def next_reward(h: "History", level: int) -> tuple[Reward, str] | None:
    """The closest locked reward and what it takes, in plain words."""
    locked = [(left, r) for r, ok, left in rewards_status(h, level) if not ok]
    if not locked:
        return None
    left, r = min(locked, key=lambda x: (x[0] / max(1, x[1].need), x[1].need))
    return r, needs_text(r, left)


def needs_text(r: Reward, left: int) -> str:
    return {"tree_days": f"{left} more full tree{'s' if left != 1 else ''}",
            "best_streak": f"a {r.need}-day streak ({left} more day{'s' if left != 1 else ''})",
            "level": f"level {r.need}"}[r.kind]


@dataclass
class LevelInfo:
    level: int
    points: float
    cur: int
    next: int | None
    progress: float


def level_info(points: float) -> LevelInfo:
    level = max(i + 1 for i, lv in enumerate(LEVELS) if points >= lv)
    cur = LEVELS[level - 1]
    nxt = LEVELS[level] if level < len(LEVELS) else None
    return LevelInfo(level, points, cur, nxt, (points - cur) / (nxt - cur) if nxt else 1.0)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _band(actual: float, target: float, full: float, zero: float) -> float:
    dev = abs(actual / target - 1) if target else 1
    return _clamp01(1 - (dev - full) / (zero - full))


@dataclass
class ScorePart:
    key: str
    label: str
    max: float
    pts: float


@dataclass
class DayScore:
    score: int
    parts: list[ScorePart]
    capped: bool = False


def score_day(targets: Targets, totals: Nutrients, supp_totals: Nutrients, water_ml: float,
              doses_scheduled: int, doses_taken: int) -> DayScore:
    """
    Score a day out of 100:
      calories 20 (full within ±10%, none beyond ±30%) · protein 15 (full at ≥90%, none <50%)
      carbs 10 (±15% / ±40%) · fat 5 (±20% / ±50%) · micronutrients 20 (average coverage, −2 per limit exceeded)
      water 15 · supplements 10 (with none scheduled, the rest scales up to 100)
    More than 25% over the calorie target caps the day at 60 (a sapling), so it can't count as a tree day.
    """
    parts = [
        ScorePart("kcal", "Calories", 20, 20 * _band(totals["kcal"], targets.kcal, 0.10, 0.30)),
        ScorePart("protein", "Protein", 15, 15 * _clamp01((totals["protein"] / targets.protein - 0.5) / 0.4)),
        ScorePart("carbs", "Carbs", 10, 10 * _band(totals["carbs"], targets.carbs, 0.15, 0.40)),
        ScorePart("fat", "Fat", 5, 5 * _band(totals["fat"], targets.fat, 0.20, 0.50)),
    ]
    goals = [m for m in MICROS if not m.limit]
    coverage = sum(min(totals.get(m.key, 0) / targets.micros[m.key].target, 1) for m in goals) / len(goals)
    over = sum(1 for m in MICROS
               if micro_status(m, targets.micros[m.key], totals.get(m.key, 0), supp_totals.get(m.key, 0))[1] == "over")
    parts.append(ScorePart("micros", "Micronutrients", 20, max(0.0, 20 * coverage - 2 * over)))
    parts.append(ScorePart("water", "Water", 15, 15 * _clamp01(water_ml / targets.water_ml if targets.water_ml else 0)))
    if doses_scheduled > 0:
        parts.append(ScorePart("supps", "Supplements", 10, 10 * min(doses_taken, doses_scheduled) / doses_scheduled))

    total_max = sum(p.max for p in parts)
    scale = 100 / total_max
    raw = sum(p.pts for p in parts)
    for p in parts:
        p.pts *= scale; p.max *= scale
    score = jround(raw * scale)
    capped = totals["kcal"] > targets.kcal * 1.25 and score > TREE_DAY - 5
    if capped:
        score = TREE_DAY - 5
    return DayScore(score, parts, capped)


@dataclass
class Tip:
    gain: float
    text: str


def growth_tips(ds: DayScore, targets: Targets, totals: Nutrients, water_ml: float, doses_scheduled: int,
                doses_taken: int, gaps: list[MicroGap], water_fmt: Callable[[float], str]) -> list[Tip]:
    """Concrete next actions, ordered by how many points they'd add."""
    parts = {p.key: p for p in ds.parts}
    tips: list[Tip] = []

    def add(key: str, text: str) -> None:
        p = parts.get(key)
        if p and p.max - p.pts >= 1:
            tips.append(Tip(p.max - p.pts, text))

    kcal_gap = targets.kcal - totals["kcal"]
    add("kcal", f"Eat about {fmt(kcal_gap)} kcal more" if kcal_gap > 0
        else f"You're {fmt(-kcal_gap)} kcal over, so keep the rest of today light")
    if totals["protein"] < targets.protein * 0.9:
        add("protein", f"Add {fmt(targets.protein * 0.9 - totals['protein'])} g protein (Greek yogurt, chicken, tofu, whey)")
    carb_gap = targets.carbs - totals["carbs"]
    add("carbs", f"Add {fmt(carb_gap)} g carbs (oats, rice, fruit, potatoes)" if carb_gap > 0
        else f"Carbs are {fmt(-carb_gap)} g over target")
    fat_gap = targets.fat - totals["fat"]
    add("fat", f"Add {fmt(fat_gap)} g fat (nuts, olive oil, avocado)" if fat_gap > 0 else f"Fat is {fmt(-fat_gap)} g over target")
    if water_ml < targets.water_ml:
        add("water", f"Drink {water_fmt(targets.water_ml - water_ml)} more water")
    if doses_scheduled > doses_taken:
        left = doses_scheduled - doses_taken
        add("supps", f"Take your {left} remaining supplement dose{'s' if left > 1 else ''}")
    if gaps:
        add("micros", "Boost " + " and ".join(f"{g.micro.label} ({g.foods[0][0].lower() if g.foods else 'varied foods'})"
                                              for g in gaps[:2]))
    return sorted(tips, key=lambda t: -t.gain)[:3]


@dataclass
class History:
    streak: int = 0
    best: int = 0
    shields: int = 0
    points: float = 0
    tree_days: int = 0
    marks: dict[str, str] = field(default_factory=dict)  # date -> tree | shielded | missed | today


def summarize_history(days: list[tuple[str, int | None]], today: str) -> History:
    """
    Walk the history day by day (ascending, up to and including today). A tree day (≥65) extends the streak;
    every 7 in a row earns a shield (max 2). A missed day uses a shield if you have one; otherwise the streak
    resets. Today never breaks a streak because it isn't over yet.
    """
    h = History()
    for date, score in days:
        if score is not None:
            h.points += score
        if score is not None and score >= TREE_DAY:
            h.streak += 1; h.tree_days += 1
            if h.streak % 7 == 0:
                h.shields = min(2, h.shields + 1)
            h.marks[date] = "tree"
        elif date == today:
            h.marks[date] = "today"
        elif h.shields > 0 and h.streak > 0:
            h.shields -= 1; h.marks[date] = "shielded"
        else:
            h.streak = 0; h.marks[date] = "missed"
        h.best = max(h.best, h.streak)
    return h
