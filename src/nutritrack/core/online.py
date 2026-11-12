"""Online food data: Open Food Facts (branded foods and barcodes, no key) and USDA FoodData Central (whole foods).

Parsers are pure functions over the APIs' JSON so they can be tested offline; the client functions take an optional
`fetch` callable so tests (and the UI) can swap the network layer.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Callable

from .foods import Food, Serving
from .nutrition import NUTRIENT_KEYS

USER_AGENT = "NutriTrack/2.0 (open-source nutrition tracker)"  # Open Food Facts asks apps to identify themselves
OFF_FIELDS = "code,product_name,brands,serving_size,serving_quantity,nutriments"
TIMEOUT = 12

Fetch = Callable[[str, dict], dict]


def http_json(url: str, headers: dict | None = None) -> dict:
    """GET JSON. API errors that come back as JSON (e.g. USDA's {"error": {...}}) are returned, not raised."""
    import urllib.error

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            if isinstance(body, dict):
                return body if "error" in body else {"error": {"code": str(e.code), "message": str(body)[:200]}}
        except Exception:
            pass
        return {"error": {"code": str(e.code), "message": f"HTTP {e.code} {e.reason}"}}


def friendly_error(err: dict) -> str:
    code = (err.get("code") or "").upper()
    if code == "API_KEY_INVALID":
        return "USDA rejected the API key. Check the key under Profile → Food databases."
    if code == "OVER_RATE_LIMIT":
        return "USDA's shared demo key is busy. Add your own free key under Profile → Food databases."
    return err.get("message") or code or "Request failed"


# ---------- Open Food Facts ----------
# OFF stores `<nutrient>_100g` normalised to grams; multiply into the app's units.
OFF_MAP: dict[str, tuple[str, float]] = {
    "protein": ("proteins_100g", 1), "carbs": ("carbohydrates_100g", 1), "fat": ("fat_100g", 1),
    "fiber": ("fiber_100g", 1), "sugar": ("sugars_100g", 1),
    "sodium": ("sodium_100g", 1000), "potassium": ("potassium_100g", 1000), "calcium": ("calcium_100g", 1000),
    "iron": ("iron_100g", 1000), "magnesium": ("magnesium_100g", 1000), "zinc": ("zinc_100g", 1000),
    "vitA": ("vitamin-a_100g", 1e6), "vitC": ("vitamin-c_100g", 1000), "vitD": ("vitamin-d_100g", 1e6),
    "vitE": ("vitamin-e_100g", 1000), "vitK": ("vitamin-k_100g", 1e6), "b12": ("vitamin-b12_100g", 1e6),
    "folate": ("folates_100g", 1e6),
}


def _num(v) -> float | None:
    try:
        f = float(v)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def parse_off_product(p: dict) -> Food | None:
    """One OFF product -> Food (per 100 g). Returns None when there's no usable energy value."""
    n = p.get("nutriments") or {}
    kcal = _num(n.get("energy-kcal_100g"))
    if kcal is None and _num(n.get("energy_100g")) is not None:  # kJ only
        kcal = _num(n.get("energy_100g")) / 4.184
    if kcal is None:
        return None
    per100 = {k: 0.0 for k in NUTRIENT_KEYS}
    per100["kcal"] = kcal
    for key, (field, factor) in OFF_MAP.items():
        v = _num(n.get(field))
        if v is None and key == "folate":
            v = _num(n.get("vitamin-b9_100g"))
        if v is None and key == "sodium" and _num(n.get("salt_100g")) is not None:
            v = _num(n.get("salt_100g")) / 2.5
        per100[key] = max(0.0, (v or 0) * factor)

    name = (p.get("product_name") or "").strip() or "Unnamed product"
    brands = p.get("brands")
    brand = (brands[0] if isinstance(brands, list) and brands else str(brands or "").split(",")[0]).strip()
    if brand and brand.lower() not in name.lower():
        name = f"{name} ({brand})"
    servings: list[Serving] = []
    sq = _num(p.get("serving_quantity"))
    if sq and sq > 0:
        label = (p.get("serving_size") or "").strip() or f"1 serving ({sq:g} g)"
        if not re.search(r"\d+(\.\d+)?\s*(g|ml)\b", label, re.I):
            label = f"{label} ({sq:g} g)"
        servings.append(Serving(label, sq))
    servings.append(Serving("100 g", 100))
    return Food(id=f"off-{p.get('code', '')}", name=name, category="Open Food Facts", servings=servings,
                per100=per100, source="OFF")


def search_off(query: str, fetch: Fetch | None = None, page_size: int = 20) -> list[Food]:
    url = "https://search.openfoodfacts.org/search?" + urllib.parse.urlencode(
        {"q": query, "page_size": page_size, "fields": OFF_FIELDS})
    data = (fetch or (lambda u, h: http_json(u, h)))(url, {})
    return [f for f in (parse_off_product(h) for h in data.get("hits", [])) if f]


def normalize_barcode(code: str) -> str | None:
    digits = re.sub(r"\D", "", code or "")
    return digits if 8 <= len(digits) <= 14 else None


def lookup_barcode(code: str, fetch: Fetch | None = None) -> Food | None:
    digits = normalize_barcode(code)
    if not digits:
        return None
    url = f"https://world.openfoodfacts.org/api/v2/product/{digits}.json?fields={OFF_FIELDS}"
    data = (fetch or (lambda u, h: http_json(u, h)))(url, {})
    if data.get("status") != 1 or not data.get("product"):
        return None
    product = {"code": digits, **data["product"]}
    return parse_off_product(product)


# ---------- USDA FoodData Central ----------
USDA_IDS: dict[int, tuple[str, float]] = {
    1003: ("protein", 1), 1004: ("fat", 1), 1005: ("carbs", 1), 1079: ("fiber", 1), 2000: ("sugar", 1),
    1087: ("calcium", 1), 1089: ("iron", 1), 1090: ("magnesium", 1), 1092: ("potassium", 1), 1093: ("sodium", 1),
    1095: ("zinc", 1), 1106: ("vitA", 1), 1162: ("vitC", 1), 1114: ("vitD", 1), 1109: ("vitE", 1), 1185: ("vitK", 1),
    1178: ("b12", 1), 1190: ("folate", 1),
}
ENERGY_IDS = (1008, 2047, 2048)  # kcal; Foundation foods often only carry the Atwater variants


def parse_usda_food(f: dict) -> Food | None:
    values = {fn.get("nutrientId"): _num(fn.get("value")) for fn in f.get("foodNutrients", [])}
    kcal = next((values[i] for i in ENERGY_IDS if values.get(i) is not None), None)
    if kcal is None:
        return None
    per100 = {k: 0.0 for k in NUTRIENT_KEYS}
    per100["kcal"] = kcal
    for nid, (key, factor) in USDA_IDS.items():
        if values.get(nid) is not None:
            per100[key] = max(0.0, values[nid] * factor)
    if not per100["folate"] and values.get(1177):  # total folate when DFE isn't reported
        per100["folate"] = values[1177]
    measures = sorted((m for m in f.get("foodMeasures") or [] if _num(m.get("gramWeight"))),
                      key=lambda m: m.get("rank", 99))
    servings = [Serving(f"{m.get('disseminationText', 'serving').strip()} ({_num(m['gramWeight']):g} g)", _num(m["gramWeight"]))
                for m in measures[:3]]
    servings.append(Serving("100 g", 100))
    name = f.get("description", "USDA food").strip()
    name = name[0].upper() + name[1:] if name else "USDA food"
    return Food(id=f"usda-{f.get('fdcId')}", name=name, category=f.get("foodCategory") or "USDA", servings=servings,
                per100=per100, source="USDA")


def search_usda(query: str, api_key: str | None = None, fetch: Fetch | None = None, page_size: int = 20) -> list[Food]:
    """Whole foods from the Foundation and SR Legacy datasets (lab-measured, full micronutrients)."""
    url = "https://api.nal.usda.gov/fdc/v1/foods/search?" + urllib.parse.urlencode(
        {"query": query, "dataType": "Foundation,SR Legacy", "pageSize": page_size})
    data = (fetch or (lambda u, h: http_json(u, h)))(url, {"X-Api-Key": api_key or "DEMO_KEY"})
    if "error" in data:
        raise RuntimeError(friendly_error(data["error"]))
    return [x for x in (parse_usda_food(f) for f in data.get("foods", [])) if x]


def parse_usda_detail(d: dict) -> Food | None:
    """A full FoodData Central food (/fdc/v1/food/{id}): nested nutrients plus household portions."""
    flat = {"fdcId": d.get("fdcId"), "description": d.get("description"),
            "foodCategory": (d.get("foodCategory") or {}).get("description") if isinstance(d.get("foodCategory"), dict)
            else d.get("foodCategory"),
            "foodNutrients": [{"nutrientId": (fn.get("nutrient") or {}).get("id"), "value": fn.get("amount")}
                              for fn in d.get("foodNutrients", []) if fn.get("amount") is not None]}
    food = parse_usda_food(flat)
    if food is None:
        return None
    portions = []
    for p in sorted(d.get("foodPortions") or [], key=lambda p: p.get("sequenceNumber") or 99):
        g = _num(p.get("gramWeight"))
        if not g:
            continue
        unit = ((p.get("measureUnit") or {}).get("name") or "").strip()
        unit = "" if unit.lower() in ("undetermined", "") else unit + " "
        desc = (p.get("portionDescription") or p.get("modifier") or "").strip()
        amount = _num(p.get("amount")) or 1
        label = desc if desc and desc[0].isdigit() else f"{amount:g} {unit}{desc}".strip()
        portions.append(Serving(f"{label} ({g:g} g)", g))
    # Put typical single-item portions first; drop near-duplicates by label.
    seen, servings = set(), []
    for sv in portions:
        if sv.label not in seen:
            seen.add(sv.label); servings.append(sv)
    food.servings = servings[:6] + [Serving("100 g", 100)]
    return food


def usda_food(fdc_id: int | str, api_key: str | None = None, fetch: Fetch | None = None) -> Food | None:
    url = f"https://api.nal.usda.gov/fdc/v1/food/{int(fdc_id)}"
    data = (fetch or (lambda u, h: http_json(u, h)))(url, {"X-Api-Key": api_key or "DEMO_KEY"})
    if "error" in data:
        raise RuntimeError(friendly_error(data["error"]))
    return parse_usda_detail(data)
