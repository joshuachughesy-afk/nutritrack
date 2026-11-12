"""Supplements: templates, timing guidance, creatine handling and stack analysis."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from .nutrition import MICROS, Nutrients, Targets, empty_nutrients, jround


@dataclass
class Supplement:
    id: str
    name: str
    dose_label: str
    times: list[str]                       # "HH:MM", one dose each
    n: Nutrients = field(default_factory=empty_nutrients)  # per dose
    with_food: bool = False
    active: bool = True
    creatine_g: float | None = None        # grams of creatine per dose (None = infer from name/label)
    tid: str | None = None                 # template it came from

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "Supplement":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True)
class SuppTemplate:
    tid: str
    name: str
    dose_label: str
    with_food: bool
    times: tuple[str, ...]
    n: dict
    creatine_g: float = 0.0

    def make(self) -> Supplement:
        n = empty_nutrients(); n.update(self.n)
        return Supplement(id="s-" + uuid.uuid4().hex[:10], name=self.name, dose_label=self.dose_label,
                          times=list(self.times), n=n, with_food=self.with_food,
                          creatine_g=self.creatine_g or None, tid=self.tid)


# Per-dose amounts at typical over-the-counter strengths; users edit them to match their label.
SUPP_TEMPLATES: list[SuppTemplate] = [
    SuppTemplate('multi', 'Multivitamin (generic)', '1 tablet', True, ('08:00',), {'calcium': 200, 'iron': 8, 'magnesium': 50, 'zinc': 11, 'vitA': 750, 'vitC': 90, 'vitD': 25, 'vitE': 15, 'vitK': 80, 'b12': 6, 'folate': 400}, creatine_g=0.0),
    SuppTemplate('d3-1000', 'Vitamin D3 1,000 IU', '1 softgel (25 µg)', True, ('08:00',), {'vitD': 25}, creatine_g=0.0),
    SuppTemplate('d3-2000', 'Vitamin D3 2,000 IU', '1 softgel (50 µg)', True, ('08:00',), {'vitD': 50}, creatine_g=0.0),
    SuppTemplate('k2', 'Vitamin K2 (MK-7)', '1 capsule (100 µg)', True, ('08:00',), {'vitK': 100}, creatine_g=0.0),
    SuppTemplate('mag', 'Magnesium glycinate', '200 mg elemental', False, ('21:00',), {'magnesium': 200}, creatine_g=0.0),
    SuppTemplate('zinc', 'Zinc', '15 mg', True, ('13:00',), {'zinc': 15}, creatine_g=0.0),
    SuppTemplate('iron', 'Iron (bisglycinate)', '18 mg', False, ('10:00',), {'iron': 18}, creatine_g=0.0),
    SuppTemplate('calcium', 'Calcium citrate', '500 mg', True, ('19:00',), {'calcium': 500}, creatine_g=0.0),
    SuppTemplate('vitc', 'Vitamin C', '500 mg', False, ('08:00',), {'vitC': 500}, creatine_g=0.0),
    SuppTemplate('b12', 'Vitamin B12', '1,000 µg', False, ('08:00',), {'b12': 1000}, creatine_g=0.0),
    SuppTemplate('folic', 'Folic acid', '400 µg', False, ('08:00',), {'folate': 400}, creatine_g=0.0),
    SuppTemplate('potassium', 'Potassium', '99 mg', True, ('13:00',), {'potassium': 99}, creatine_g=0.0),
    SuppTemplate('electrolytes', 'Electrolyte mix', '1 stick / scoop', False, ('16:00',), {'sodium': 500, 'potassium': 200, 'magnesium': 60}, creatine_g=0.0),
    SuppTemplate('fish-oil', 'Fish oil (omega-3)', '1 g (EPA+DHA ~600 mg)', True, ('19:00',), {'kcal': 9, 'fat': 1}, creatine_g=0.0),
    SuppTemplate('creatine', 'Creatine monohydrate', '5 g', False, ('08:00',), {}, creatine_g=5.0),
]


def _has(s: Supplement, key: str, minimum: float = 0.0001) -> bool:
    return (s.n.get(key) or 0) >= minimum


def creatine_per_dose(s: Supplement) -> float:
    """Grams of creatine per dose; falls back to parsing a "5 g" dose label for entries named creatine."""
    if s.creatine_g is not None:
        return float(s.creatine_g or 0)
    if "creatine" not in s.name.lower():
        return 0.0
    m = re.search(r"([\d.]+)\s*g\b", s.dose_label or "", re.I)
    return float(m.group(1)) if m else 5.0


def daily_creatine(supps: list[Supplement]) -> float:
    """Total daily creatine across the active stack (scheduled doses, taken or not)."""
    return sum(creatine_per_dose(s) * len(s.times) for s in supps if s.active)


def timing_advice(s: Supplement) -> list[str]:
    tips: list[str] = []
    name = s.name.lower()
    if any(_has(s, k) for k in ("vitA", "vitD", "vitE", "vitK")) or "fish oil" in name or "omega" in name:
        tips.append("Fat-soluble: take with a meal that contains fat for better absorption.")
    if _has(s, "iron", 5):
        tips.append("Iron: absorbs best on an empty stomach or with vitamin C. Keep it 2+ hours away from calcium, "
                    "zinc, coffee, tea and dairy.")
    if _has(s, "calcium", 250):
        tips.append("Calcium: the body absorbs about 500 mg at a time. Split larger doses and keep them away from iron.")
    if _has(s, "magnesium", 100):
        tips.append("Magnesium: the evening works well and may help sleep. Glycinate is gentle on the stomach.")
    if _has(s, "zinc", 8):
        tips.append("Zinc: take with food to avoid nausea and keep it about 2 hours apart from iron and calcium. "
                    "Long-term intake above 40 mg/day can deplete copper.")
    if creatine_per_dose(s):
        tips.append("Creatine: take it every day; consistency matters more than timing. It pulls water into muscle, "
                    "so your water goal goes up about 500 ml/day (about 1 L/day while loading with 20 g/day).")
    if "electrolyte" in name:
        tips.append("Electrolytes: best before or during long, hot or sweaty sessions.")
    if _has(s, "b12", 100):
        tips.append("B12: any time of day. Mornings are common because some people find it stimulating.")
    return tips


def analyze_stack(supps: list[Supplement], targets: Targets) -> tuple[Nutrients, list[str]]:
    """Daily totals if every dose is taken, upper-limit exposure, and same-time absorption conflicts."""
    active = [s for s in supps if s.active]
    totals = empty_nutrients()
    for s in active:
        for k in totals:
            totals[k] += (s.n.get(k) or 0) * len(s.times)

    warnings: list[str] = []
    for m in MICROS:
        t = targets.micros.get(m.key)
        amt = totals.get(m.key, 0)
        if not t or not t.ul or not amt:
            continue
        if amt > t.ul:
            scope = " for supplemental intake" if m.ul_scope == "supplement" else ""
            warnings.append(f"{m.label}: your supplements alone provide {jround(amt)} {m.unit}/day, above the "
                            f"{t.ul:g} {m.unit} upper limit{scope}.")
        elif m.ul_scope == "total" and amt > t.ul * 0.6:
            warnings.append(f"{m.label}: your supplements provide {jround(amt)} {m.unit}. Add food and you may get "
                            f"close to the {t.ul:g} {m.unit} upper limit.")
    if totals.get("vitA", 0) > 0:
        warnings.append("Vitamin A: the upper limit applies to preformed vitamin A (retinol). Beta-carotene doesn't "
                        "count, so check the label.")

    by_time: dict[str, list[Supplement]] = {}
    for s in active:
        for t in s.times:
            by_time.setdefault(t, []).append(s)
    for time, items in sorted(by_time.items()):
        iron = next((s for s in items if _has(s, "iron", 5)), None)
        blockers = [s for s in items if s is not iron and (_has(s, "calcium", 200) or _has(s, "zinc", 8))]
        if iron and blockers:
            warnings.append(f"{time}: {iron.name} is scheduled with {', '.join(b.name for b in blockers)}. Calcium "
                            "and zinc reduce iron absorption, so move one at least 2 hours apart.")
    return totals, warnings
