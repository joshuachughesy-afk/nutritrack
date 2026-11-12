"""Nutrition science: targets, DRIs, carb periodization, hydration and nutrient math.

Micronutrient values are NIH ODS / IOM Dietary Reference Intakes for adults.
All quantities are stored in metric (kg, cm, ml, g/mg/µg).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Iterable

from .training import LOADS, TRAINING, TrainingType


def jround(x: float) -> int:
    """Round half up, like JavaScript's Math.round (Python's jround() uses banker's rounding)."""
    return math.floor(x + 0.5)


# ---------- Nutrient definitions ----------
@dataclass(frozen=True)
class Micro:
    key: str
    label: str
    unit: str
    limit: bool = False          # sodium: a ceiling, not a goal
    ul_scope: str | None = None  # "total" = UL on food + supplements; "supplement" = UL on supplemental forms only


MACROS = (("protein", "Protein", 4), ("carbs", "Carbs", 4), ("fat", "Fat", 9))

MICROS: tuple[Micro, ...] = (
    Micro("fiber", "Fiber", "g"),
    Micro("sodium", "Sodium", "mg", limit=True),
    Micro("potassium", "Potassium", "mg"),
    Micro("calcium", "Calcium", "mg", ul_scope="total"),
    Micro("iron", "Iron", "mg", ul_scope="total"),
    Micro("magnesium", "Magnesium", "mg", ul_scope="supplement"),
    Micro("zinc", "Zinc", "mg", ul_scope="total"),
    Micro("vitA", "Vitamin A", "µg", ul_scope="supplement"),
    Micro("vitC", "Vitamin C", "mg", ul_scope="total"),
    Micro("vitD", "Vitamin D", "µg", ul_scope="total"),
    Micro("vitE", "Vitamin E", "mg", ul_scope="supplement"),
    Micro("vitK", "Vitamin K", "µg"),
    Micro("b12", "Vitamin B12", "µg"),
    Micro("folate", "Folate", "µg", ul_scope="supplement"),
)
MICRO_BY_KEY = {m.key: m for m in MICROS}

NUTRIENT_KEYS: tuple[str, ...] = ("kcal", "protein", "carbs", "fat", "sugar") + tuple(m.key for m in MICROS)

ACTIVITY = {
    "sedentary": ("Sedentary (desk job, little exercise)", 1.2),
    "light": ("Lightly active (1–3 workouts/wk)", 1.375),
    "moderate": ("Moderately active (3–5 workouts/wk)", 1.55),
    "very": ("Very active (6–7 workouts/wk)", 1.725),
    "extra": ("Extremely active (physical job + training)", 1.9),
}

GOALS = {
    "lose": ("Lose ~0.5 kg per week", -500),
    "lose_slow": ("Lose slowly (~0.25 kg per week)", -250),
    "maintain": ("Maintain weight", 0),
    "gain_slow": ("Lean gain (~0.25 kg per week)", 250),
}

DEFAULT_TRAINING_DAYS = (1, 2, 4, 5, 6)  # 0=Sun … 6=Sat → Mon, Tue, Thu, Fri, Sat


def weekday_sun0(d) -> int:
    """Day of week with Sunday = 0 (matches the stored training_days)."""
    return (d.weekday() + 1) % 7


ML_PER_OZ = 29.5735


# ---------- Profile ----------
@dataclass
class Profile:
    sex: str = "male"
    age: int = 30
    height_cm: float = 178
    weight_kg: float = 80
    activity: str = "moderate"
    goal: str = "maintain"
    training_type: str = "general"
    training_load: str = "moderate"
    training_days: tuple[int, ...] = DEFAULT_TRAINING_DAYS
    carb_cycling: bool = True
    overrides: dict = field(default_factory=dict)  # kcal / protein / carbs / fat
    adaptive_tdee: float | None = None             # set by the adaptive-TDEE engine when enabled

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["training_days"] = list(self.training_days)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        if "training_days" in known:
            known["training_days"] = tuple(known["training_days"])
        return cls(**known)


# ---------- DRIs ----------
@dataclass
class MicroTarget:
    target: float
    ul: float | None = None
    limit: bool = False


def dri_table(sex: str, age: int) -> dict[str, MicroTarget]:
    m = sex == "male"
    older, oldest = age >= 51, age >= 71
    return {
        "sodium": MicroTarget(2300, limit=True),
        "potassium": MicroTarget(3400 if m else 2600),
        "calcium": MicroTarget(1200 if (oldest if m else older) else 1000, ul=2000 if older else 2500),
        "iron": MicroTarget(8 if (m or older) else 18, ul=45),
        "magnesium": MicroTarget((420 if age >= 31 else 400) if m else (320 if age >= 31 else 310), ul=350),
        "zinc": MicroTarget(11 if m else 8, ul=40),
        "vitA": MicroTarget(900 if m else 700, ul=3000),
        "vitC": MicroTarget(90 if m else 75, ul=2000),
        "vitD": MicroTarget(20 if oldest else 15, ul=100),
        "vitE": MicroTarget(15, ul=1000),
        "vitK": MicroTarget(120 if m else 90),
        "b12": MicroTarget(2.4),
        "folate": MicroTarget(400, ul=1000),
    }


def bmr(p: Profile) -> float:
    """Mifflin-St Jeor."""
    return 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age + (5 if p.sex == "male" else -161)


def _lerp(r: tuple[float, float], t: float) -> float:
    return r[0] + (r[1] - r[0]) * t


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)


# ---------- Targets ----------
@dataclass
class Water:
    base: int
    training: int
    creatine: int
    creatine_g: float

    @property
    def total(self) -> int:
        return self.base + self.training + self.creatine


@dataclass
class Targets:
    bmr: int
    tdee: int
    kcal: int
    protein: int
    carbs: int
    fat: int
    micros: dict[str, MicroTarget]
    floor_applied: bool
    training_id: str
    training: TrainingType
    gkg: dict[str, float]
    notes: list[str]
    tdee_source: str = "formula"
    # Day-specific (set by day_targets)
    day_type: str = "training"
    cycling: bool = False
    water: Water | None = None

    @property
    def water_ml(self) -> int:
        return self.water.total if self.water else 0

    def macro(self, key: str) -> float:
        return getattr(self, key)


def compute_targets(p: Profile) -> Targets:
    """
    Macro allocation, in priority order:
      1. Protein from the training type's g/kg range (top of range in a deficit, to protect muscle).
      2. Carbs get first claim on remaining calories, up to the type's g/kg target for your load.
      3. Fat takes the rest: never below a health floor (max of 0.6 g/kg, 20% kcal), never above 35% kcal.
         Surplus calories go to fat up to the top of its range, then back to carbs.
    """
    o = p.overrides or {}
    w = p.weight_kg
    base = bmr(p)
    formula_tdee = base * ACTIVITY.get(p.activity, ACTIVITY["sedentary"])[1]
    tdee, source = (p.adaptive_tdee, "adaptive") if p.adaptive_tdee else (formula_tdee, "formula")
    floor = 1500 if p.sex == "male" else 1200
    kcal = max(floor, jround((tdee + GOALS.get(p.goal, GOALS["maintain"])[1]) / 10) * 10)
    if o.get("kcal"):
        kcal = int(o["kcal"])

    training_id = p.training_type if p.training_type in TRAINING else "general"
    tr = TRAINING[training_id]
    t = LOADS.get(p.training_load, LOADS["moderate"])["t"]
    cutting = str(p.goal).startswith("lose")

    protein = int(o.get("protein") or jround(_lerp(tr.protein, 1 if cutting else t) * w))
    carb_goal = _lerp(tr.carbs, t) * w
    fat_floor = max(0.6 * w, 0.2 * kcal / 9)
    fat_cap = 0.35 * kcal / 9
    rest = kcal - protein * 4

    if o.get("carbs") and o.get("fat"):
        carbs, fat = float(o["carbs"]), float(o["fat"])
    elif o.get("carbs"):
        carbs = float(o["carbs"]); fat = max(0.0, (rest - carbs * 4) / 9)
    elif o.get("fat"):
        fat = float(o["fat"]); carbs = max(0.0, (rest - fat * 9) / 4)
    else:
        carbs = max(0.0, min(carb_goal, (rest - fat_floor * 9) / 4))
        fat = (rest - carbs * 4) / 9
        fat_max = _clamp(tr.fat[1] * w, fat_floor, fat_cap)
        if fat > fat_max:
            carbs += (fat - fat_max) * 9 / 4
            fat = fat_max
    carbs, fat = jround(carbs), jround(max(0.0, fat))

    gkg = {"protein": protein / w, "carbs": carbs / w, "fat": fat / w}
    notes: list[str] = []
    if gkg["carbs"] < tr.carbs[0] - 0.05:
        notes.append(f"Carbs ({gkg['carbs']:.1f} g/kg) are below the {tr.carbs[0]:g}–{tr.carbs[1]:g} g/kg recommended for "
                     f"{tr.name.lower()}. Your calorie target leaves too little room. A smaller deficit, or more carbs "
                     "on training days, will help performance.")
    if gkg["carbs"] > tr.carbs[1] + 0.05 and not o.get("carbs"):
        notes.append(f"Your calorie target is above what {tr.name.lower()} needs at this load, so the extra goes to carbs "
                     f"({gkg['carbs']:.1f} g/kg). If this feels like a lot, re-check your activity level.")
    if (t >= 0.7 and p.activity in ("sedentary", "light")) or (t == 0 and p.activity in ("very", "extra")):
        notes.append("Your activity level and training load don't match. Activity sets total calories; "
                     "training load sets the macro split.")
    if protein * 4 + carbs * 4 + fat * 9 > kcal + 50:
        notes.append("Your manual overrides add up to more calories than your daily target.")

    micros = dri_table(p.sex, p.age)
    micros["fiber"] = MicroTarget(jround(kcal / 1000 * 14))
    return Targets(jround(base), jround(tdee), kcal, protein, carbs, fat, micros,
                   floor_applied=not o.get("kcal") and kcal == floor, training_id=training_id, training=tr,
                   gkg=gkg, notes=notes, tdee_source=source)


def creatine_water_ml(creatine_g: float) -> int:
    """
    Creatine draws water into muscle cells (~1–2 kg intracellular water when saturated). The ISSN creatine position
    stand (Kreider et al., 2017) finds no evidence it causes dehydration or cramping, but the water it holds still has
    to come from somewhere: ~+500 ml/day on a maintenance dose (3–5 g), ~+1 L/day while loading (~20 g/day).
    """
    if not creatine_g:
        return 0
    return 1000 if creatine_g >= 15 else 500


LOAD_WATER_ML = {"low": 350, "moderate": 500, "high": 650, "peak": 800}


def day_targets(p: Profile, is_training: bool, creatine_g: float = 0) -> Targets:
    """
    Day-specific targets with carb periodization ("fuel for the work required"): rest days drop carbs toward the low
    end and the saved carbs move to training days, so the weekly average still matches your calorie target.
    """
    base = compute_targets(p)
    w = p.weight_kg
    n_t = len(p.training_days)
    n_r = 7 - n_t
    tr = base.training
    carb_forward = not tr.emphasis.startswith(("Balanced", "Protein"))
    rest_gkg = max(3.0, tr.carbs[0] - 1) if carb_forward else tr.carbs[0]
    rest_carbs = min(base.carbs, jround(rest_gkg * w))
    delta = base.carbs - rest_carbs
    o = p.overrides or {}
    cycling = p.carb_cycling and n_t > 0 and n_r > 0 and delta > 0 and not o.get("carbs") and not o.get("kcal")

    carbs, kcal = base.carbs, base.kcal
    if cycling:
        if is_training:
            add = jround(delta * n_r / n_t)
            carbs += add; kcal += add * 4
        else:
            carbs = rest_carbs; kcal -= delta * 4

    water = Water(
        base=jround(35 * w / 50) * 50,
        training=LOAD_WATER_ML.get(p.training_load, 500) if is_training else 0,
        creatine=creatine_water_ml(creatine_g),
        creatine_g=creatine_g or 0,
    )
    micros = dict(base.micros)
    micros["fiber"] = MicroTarget(jround(base.kcal / 1000 * 14))
    return replace(base, carbs=carbs, kcal=kcal, cycling=cycling, day_type="training" if is_training else "rest",
                   water=water, gkg={**base.gkg, "carbs": carbs / w}, micros=micros)


# ---------- Nutrient math ----------
Nutrients = dict[str, float]


def empty_nutrients() -> Nutrients:
    return {k: 0.0 for k in NUTRIENT_KEYS}


def scale_nutrients(per100: Nutrients, grams: float) -> Nutrients:
    f = grams / 100
    return {k: (per100.get(k) or 0) * f for k in NUTRIENT_KEYS}


def sum_nutrients(items: Iterable[Nutrients | None]) -> Nutrients:
    out = empty_nutrients()
    for n in items:
        if not n:
            continue
        for k in NUTRIENT_KEYS:
            out[k] += n.get(k) or 0
    return out


def micro_status(m: Micro, target: MicroTarget | None, total: float, supplement_amount: float = 0) -> tuple[float, str]:
    """Return (fraction of target, status) where status is low | mid | met | over | ok-limit | none."""
    if not target or not target.target:
        return 0.0, "none"
    pct = total / target.target
    if target.limit:
        return pct, "over" if pct > 1 else "ok-limit"
    ul_base = supplement_amount if m.ul_scope == "supplement" else total
    if target.ul and m.ul_scope and ul_base > target.ul:
        return pct, "over"
    return pct, "met" if pct >= 1 else "mid" if pct >= 0.5 else "low"


# ---------- Units & formatting ----------
def kg_to_lb(kg: float) -> float: return kg * 2.20462
def lb_to_kg(lb: float) -> float: return lb / 2.20462
def cm_to_in(cm: float) -> float: return cm / 2.54
def in_to_cm(i: float) -> float: return i * 2.54


def fmt(v: float | None, unit: str = "") -> str:
    if v is None:
        v = 0
    a = abs(v)
    if a < 0.005:
        s = "0"
    elif a >= 100:
        s = f"{jround(v):,}"
    elif a >= 10:
        s = f"{v:.0f}"
    elif a >= 1:
        s = f"{v:.1f}".rstrip("0").rstrip(".")
    else:
        s = f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{s} {unit}" if unit else s


def fmt_water(ml: float, imperial: bool = False) -> str:
    if imperial:
        return f"{jround(ml / ML_PER_OZ)} oz"
    if ml >= 1000:
        return f"{float(f'{ml / 1000:.2f}'):g} L"
    return f"{jround(ml)} ml"
