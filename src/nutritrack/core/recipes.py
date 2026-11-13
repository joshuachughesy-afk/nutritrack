"""Recipes (a dish built from ingredients, split into servings) and meal plans (saved meals or whole days to re-log)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .foods import Food, Serving
from .nutrition import Nutrients, empty_nutrients, sum_nutrients


@dataclass
class Ingredient:
    food_id: str | None
    name: str
    grams: float
    n: Nutrients  # nutrients for this amount


@dataclass
class Recipe:
    id: str
    name: str
    servings: float = 1
    ingredients: list[Ingredient] = field(default_factory=list)

    @property
    def total_grams(self) -> float:
        return sum(i.grams for i in self.ingredients)

    def totals(self) -> Nutrients:
        return sum_nutrients(i.n for i in self.ingredients)

    def per_serving(self) -> Nutrients:
        s = max(self.servings, 0.01)
        return {k: v / s for k, v in self.totals().items()}

    def to_food(self) -> Food:
        """The recipe as a loggable food: per-100 g values and a '1 serving' unit."""
        g = self.total_grams or 1.0
        per100 = {k: v * 100 / g for k, v in self.totals().items()}
        serving_g = g / max(self.servings, 0.01)
        servings = [Serving(f"1 serving ({serving_g:.0f} g)", serving_g)]
        if self.servings > 1:
            servings.append(Serving(f"Whole recipe ({g:.0f} g)", g))
        return Food(self.id, self.name, "Recipe", servings, per100, source="recipe")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Recipe":
        return cls(d["id"], d["name"], float(d.get("servings", 1)), [Ingredient(**i) for i in d.get("ingredients", [])])


@dataclass
class PlanItem:
    meal: str
    name: str
    food_id: str | None
    grams: float
    amount_label: str
    n: Nutrients


@dataclass
class Plan:
    id: str
    name: str
    kind: str  # "meal" or "day"
    items: list[PlanItem] = field(default_factory=list)

    def totals(self) -> Nutrients:
        return sum_nutrients(i.n for i in self.items) if self.items else empty_nutrients()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(d["id"], d["name"], d.get("kind", "meal"), [PlanItem(**i) for i in d.get("items", [])])

    @classmethod
    def from_entries(cls, plan_id: str, name: str, kind: str, entries: list[dict]) -> "Plan":
        return cls(plan_id, name, kind, [PlanItem(e["meal"], e["name"], e.get("food_id"), float(e.get("grams") or 0),
                                                  e.get("amount_label") or "", dict(e["n"])) for e in entries])
