"""Typed logging: turn "2 eggs, 2 slices of toast and a banana" into foods and amounts.

Runs entirely on the device against your own foods and the built-in list. Every line comes back with what it matched
and how sure it is, so the screen can show a preview you confirm (and fix) before anything is logged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .foods import Food

NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "half": 0.5, "a half": 0.5, "couple": 2, "a couple of": 2,
                "a few": 3, "few": 3, "dozen": 12}
FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
# unit word -> (grams per unit, or None to use a matching serving)
UNITS = {"g": 1, "gram": 1, "grams": 1, "gr": 1, "kg": 1000, "ml": 1, "l": 1000, "litre": 1000, "liter": 1000,
         "oz": 28.35, "ounce": 28.35, "ounces": 28.35, "lb": 453.6,
         "cup": None, "cups": None, "tbsp": None, "tablespoon": None, "tablespoons": None, "tsp": None, "teaspoon": None,
         "teaspoons": None, "slice": None, "slices": None, "scoop": None, "scoops": None, "handful": None,
         "handfuls": None, "can": None, "cans": None, "fillet": None, "fillets": None, "breast": None, "breasts": None,
         "portion": None, "portions": None, "piece": None, "pieces": None, "serving": None, "servings": None,
         "container": None, "patty": None, "patties": None, "square": None, "squares": None, "bowl": None, "bowls": None}
UNIT_ALIASES = {"tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tsp": "tsp", "teaspoon": "tsp",
                "teaspoons": "tsp", "bowl": "cup", "bowls": "cup"}
SYNONYMS = {"toast": "whole wheat bread", "bread": "whole wheat bread", "yoghurt": "yogurt", "pb": "peanut butter",
            "oj": "orange juice", "spud": "potato", "beans": "black beans", "porridge": "oats", "oatmeal": "oats",
            "protein shake": "whey protein", "shake": "whey protein", "whey": "whey protein", "chicken": "chicken breast",
            "mince": "ground beef", "steak": "ground beef", "prawns": "shrimp", "prawn": "shrimp", "rice": "white rice",
            "egg whites": "egg white", "chocolate": "dark chocolate", "nuts": "almonds", "cheese": "cheddar"}
FILLER = {"of", "some", "with", "the", "my", "fresh", "cooked", "large", "small", "medium", "big"}


@dataclass
class Parsed:
    text: str                 # the phrase as typed
    food: Food | None
    grams: float
    label: str                # amount as shown and logged, e.g. "2 × 1 large egg"
    confident: bool


def split_items(text: str) -> list[str]:
    parts = re.split(r",|\n|;|\+|\band\b|\bwith\b|&", text.lower())
    return [p.strip(" .") for p in parts if p.strip(" .")]


def _quantity(words: list[str]) -> tuple[float | None, list[str]]:
    if not words:
        return None, words
    w = words[0]
    for sym, v in FRACTIONS.items():  # "1½", "½"
        if w.endswith(sym):
            head = w[: -len(sym)]
            return (float(head) if head.replace(".", "").isdigit() else 0) + v, words[1:]
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(?:/(\d+))?([a-z]*)", w)
    if m:
        q = float(m.group(1).replace(",", "."))
        if m.group(2):
            q = q / float(m.group(2))
        rest = words[1:]
        if m.group(3):  # "150g"
            rest = [m.group(3)] + rest
        if len(rest) >= 1 and re.fullmatch(r"\d+/\d+", rest[0] or ""):  # "1 1/2"
            a, b = rest[0].split("/")
            q += float(a) / float(b)
            rest = rest[1:]
        return q, rest
    for phrase in sorted(NUMBER_WORDS, key=len, reverse=True):
        n = phrase.split()
        if words[: len(n)] == n:
            rest = words[len(n):]
            if rest and rest[0] == "of":
                rest = rest[1:]
            return NUMBER_WORDS[phrase], rest
    return None, words


def _singular(w: str) -> str:
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text: str) -> set[str]:
    return {_singular(t) for t in re.findall(r"[a-z]+", text.lower()) if t not in FILLER}


def match_food(name: str, foods: list[Food]) -> tuple[Food | None, float]:
    """Best food for a phrase and a 0–1 score (share of the phrase's words found in the food's name)."""
    phrase = name.strip()
    for k in sorted(SYNONYMS, key=len, reverse=True):
        if re.fullmatch(rf"{k}s?", phrase) or phrase == k:
            phrase = SYNONYMS[k]
            break
    want = _tokens(phrase)
    if not want:
        return None, 0.0
    best, best_score = None, 0.0
    for f in foods:
        have = _tokens(f.name)
        hit = len(want & have)
        if not hit:
            continue
        score = hit / len(want) - 0.02 * len(have - want)   # prefer the closer, shorter name
        if f.source == "custom":
            score += 0.05                                   # your own foods win ties
        if score > best_score:
            best, best_score = f, score
    return best, max(0.0, min(1.0, best_score))


def _serving_for(food: Food, unit: str | None):
    if unit is None:
        return food.servings[0]
    u = UNIT_ALIASES.get(unit, _singular(unit))
    for sv in food.servings:
        if re.search(rf"\b{re.escape(u)}s?\b", sv.label.lower()):
            return sv
    return food.servings[0]


def parse(text: str, foods: list[Food]) -> list[Parsed]:
    out: list[Parsed] = []
    for item in split_items(text):
        words = [w for w in item.split() if w not in ("big", "small", "large", "medium", "some")]
        qty, rest = _quantity(words)
        while rest and rest[0] in ("a", "an", "of"):  # "half an avocado", "a couple of eggs"
            rest = rest[1:]
        unit = None
        if rest and rest[0] in UNITS:
            unit, rest = rest[0], rest[1:]
            if rest and rest[0] == "of":
                rest = rest[1:]
        name = " ".join(rest)
        food, score = match_food(name, foods)
        if food is None:
            out.append(Parsed(item, None, 0, "", False))
            continue
        q = qty if qty is not None else 1
        per_unit = UNITS.get(unit) if unit else None
        if per_unit:  # a weight or volume
            grams = q * per_unit
            label = f"{q:g} {unit}"
        else:
            sv = _serving_for(food, unit)
            if sv.label.startswith("½") and unit is None:  # "an avocado" is two "½ avocado" servings
                grams = q * 2 * sv.g
                label = sv.label if q == 0.5 else f"{q:g} whole ({round(grams)} g)"
            else:
                grams = q * sv.g
                label = sv.label if q == 1 else f"{q:g} × {sv.label}"
        out.append(Parsed(item, food, round(grams, 1), label, score >= 0.6))
    return out
