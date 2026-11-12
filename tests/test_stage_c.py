import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from nutritrack.core import barcode, online
from nutritrack.core.nutrition import Profile
from nutritrack.core.trends import KCAL_PER_KG, adaptive_tdee, weight_trend
from nutritrack.service import Service, today_key
from nutritrack.store import Store

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


# ---------- Open Food Facts ----------
def test_off_units_are_converted_from_grams():
    f = online.parse_off_product({"code": "0038000016912", **load("off_product_special_k.json")["product"]})
    p = f.per100
    assert f.id == "off-0038000016912" and f.source == "OFF"
    assert p["kcal"] == pytest.approx(377)
    assert p["vitC"] == pytest.approx(68)          # 0.068 g -> 68 mg (label: 21 mg per 31 g)
    assert p["iron"] == pytest.approx(28)          # fortified: 0.028 g -> 28 mg
    assert p["sodium"] == pytest.approx(667)
    assert p["vitA"] == pytest.approx(500.1)       # 0.0005001 g -> 500 µg
    assert p["folate"] == pytest.approx(1290)
    assert f.servings[0].g == 31 and "31 g" in f.servings[0].label and f.servings[-1].g == 100


def test_off_serving_label_is_tidied():
    f = online.parse_off_product({"code": "3", "product_name": "Skyr", "serving_size": "150.0g", "serving_quantity": 150,
                                  "nutriments": {"energy-kcal_100g": 62}})
    assert f.servings[0].label == "150 g"


def test_off_brand_and_kj_fallback():
    f = online.parse_off_product({"code": "1", "product_name": "Bar", "brands": "Acme",
                                  "nutriments": {"energy_100g": 418.4, "salt_100g": 1.0}})
    assert f.name == "Bar (Acme)" and f.per100["kcal"] == pytest.approx(100) and f.per100["sodium"] == pytest.approx(400)
    assert online.parse_off_product({"code": "2", "product_name": "No data", "nutriments": {}}) is None


def test_off_search_and_barcode_with_fake_fetch():
    calls = []

    def fetch(url, headers):
        calls.append(url)
        return load("off_search_cereal.json") if "search" in url else {"status": 1, **load("off_product_special_k.json")}

    hits = online.search_off("special k", fetch=fetch)
    assert hits and all(h.source == "OFF" for h in hits) and "q=special+k" in calls[0]
    f = online.lookup_barcode(" 0038-0000-16912 ", fetch=fetch)
    assert f and f.id == "off-0038000016912" and "/product/0038000016912.json" in calls[1]
    assert online.lookup_barcode("12", fetch=fetch) is None
    assert online.lookup_barcode("0000000000000", fetch=lambda u, h: {"status": 0}) is None


# ---------- USDA ----------
def test_usda_parse_and_search():
    seen = {}

    def fetch(url, headers):
        seen.update(url=url, headers=headers)
        return load("usda_search_banana.json")

    foods = online.search_usda("banana", api_key="abc", fetch=fetch)
    assert seen["headers"]["X-Api-Key"] == "abc" and "Foundation%2CSR+Legacy" in seen["url"]
    raw, ripe = foods
    assert raw.id == "usda-173944" and raw.per100["kcal"] == 89 and raw.per100["potassium"] == 358
    assert raw.per100["folate"] == 20 and raw.servings[0].g == 118 and "medium" in raw.servings[0].label
    assert ripe.per100["kcal"] == pytest.approx(97.4)  # Atwater energy when 1008 is missing
    with pytest.raises(RuntimeError, match="rejected the API key"):
        online.search_usda("x", fetch=lambda u, h: {"error": {"code": "API_KEY_INVALID", "message": "bad key"}})
    with pytest.raises(RuntimeError, match="own free key"):
        online.search_usda("x", fetch=lambda u, h: {"error": {"code": "OVER_RATE_LIMIT"}})


def test_usda_detail_has_household_portions():
    f = online.parse_usda_detail(load("usda_food_173944.json"))  # real response
    assert f.id == "usda-173944" and f.per100["kcal"] == 89 and f.per100["potassium"] == 358
    labels = [s.label for s in f.servings]
    assert any("cup, sliced (150 g)" in l for l in labels) and labels[-1] == "100 g" and len(f.servings) <= 7
    seen = {}
    online.usda_food(173944, "k", fetch=lambda u, h: (seen.update(u=u, h=h), load("usda_food_173944.json"))[1])
    assert seen["u"].endswith("/fdc/v1/food/173944") and seen["h"]["X-Api-Key"] == "k"


# ---------- Barcode decoding ----------
@pytest.mark.skipif(not barcode.available(), reason="zxing-cpp not installed")
def test_barcode_decodes_photo():
    import io

    bc = pytest.importorskip("barcode")
    from barcode.writer import ImageWriter
    buf = io.BytesIO()
    bc.get("ean13", "003800001691", writer=ImageWriter()).write(buf)
    assert barcode.decode(buf.getvalue()) == "0038000016912"


# ---------- Trends & adaptive TDEE ----------
def days_back(n, today="2026-11-12"):
    t = date.fromisoformat(today)
    return [(t - timedelta(days=i)).isoformat() for i in range(n, 0, -1)]


def test_weight_trend_smooths_noise():
    ws = [(d, 80 + (0.8 if i % 2 else -0.8)) for i, d in enumerate(days_back(20))]
    trend = [t for _, _, t in weight_trend(ws)]
    assert max(trend) - min(trend) < 1.0 < max(w for _, w in ws) - min(w for _, w in ws)


def test_adaptive_tdee_recovers_true_burn():
    # Eats 2,500/day while truly burning 3,000 -> loses 500*28/7700 ≈ 1.82 kg over 4 weeks.
    ds = days_back(28)
    true_tdee, intake = 3000, 2500
    weights = [(d, 85 - (true_tdee - intake) * i / KCAL_PER_KG) for i, d in enumerate(ds) if i % 2 == 0]
    res = adaptive_tdee({d: intake for d in ds}, weights, formula_tdee=2600, today="2026-11-12")
    assert res.ready and res.confidence == 1.0
    assert res.estimate == pytest.approx(true_tdee, abs=5) and res.blended == pytest.approx(res.estimate)


def test_adaptive_tdee_robust_to_water_noise():
    import random
    rnd = random.Random(7)
    ds = days_back(28)
    weights = [(d, 85 - 500 * i / KCAL_PER_KG + rnd.uniform(-1.0, 1.0)) for i, d in enumerate(ds) if i % 3 != 1]
    res = adaptive_tdee({d: 2500 for d in ds}, weights, 2600, "2026-11-12")
    assert res.ready and abs(res.estimate - 3000) < 300  # ±1 kg daily water noise still lands within ~10%


def test_adaptive_tdee_needs_enough_data_and_caps():
    ds = days_back(28)
    few = adaptive_tdee({d: 2500 for d in ds[-5:]}, [(ds[-3], 80), (ds[-1], 80)], 2600, "2026-11-12")
    assert not few.ready and "Still learning" in few.reason
    none = adaptive_tdee({}, [], 2600, "2026-11-12")
    assert not none.ready and "weigh" in none.reason.lower()
    # Implausible data (5 kg gain in 4 weeks on 1,500 kcal) is capped at +/-25% of the formula
    wild = adaptive_tdee({d: 1500 for d in ds}, [(d, 80 + i * 0.4) for i, d in enumerate(ds) if i % 2 == 0], 2600, "2026-11-12")
    assert wild.ready and wild.blended == pytest.approx(2600 * 0.75)


# ---------- Service ----------
@pytest.fixture
def svc(tmp_path):
    st = Store(tmp_path / "c.db")
    st.save_profile(Profile(sex="male", age=32, height_cm=180, weight_kg=84, activity="very", training_type="hybrid",
                            training_load="high"))
    return Service(st)


def test_log_weight_updates_profile_trend(svc):
    k = today_key()
    svc.log_weight(k, 82.0)
    assert svc.store.day(k)["weight_kg"] == 82.0 and svc.store.profile().weight_kg == 82.0


def test_adaptive_targets_switch_on(svc):
    t = date.fromisoformat(today_key())
    for i in range(28, 0, -1):
        k = (t - timedelta(days=i)).isoformat()
        svc.store.add_entry(k, "lunch", "Day", {"kcal": 2500, "protein": 150, "carbs": 300, "fat": 70}, amount_label="")
        if i % 2 == 0:
            svc.store.set_day(k, weight_kg=84 - (28 - i) * 500 / KCAL_PER_KG)
    formula = svc.targets_for(today_key()).tdee
    p = svc.store.profile(); p.use_adaptive = True; svc.store.save_profile(p)
    a = svc.adaptive()
    assert a.ready and svc.targets_for(today_key()).tdee == round(a.blended) != formula


def test_period_summary(svc):
    t = today_key()
    svc.store.add_entry(t, "lunch", "x", {"kcal": 1000, "protein": 50, "vitC": 90}, amount_label="")
    s = svc.period(7)
    assert len(s.days) == 7 and s.logged_days == 1 and s.avg_kcal == 1000
    assert s.micro_avg["vitC"] == pytest.approx(1.0) and "fiber" in s.consistently_low


def test_remember_online_food(svc):
    f = online.parse_off_product({"code": "0038000016912", **load("off_product_special_k.json")["product"]})
    svc.remember_food(f)
    assert svc.find_food("off-0038000016912").source == "OFF"


# ---------- 3D trees ----------
def test_render3d_all_species_and_turntable():
    from nutritrack.core import render3d
    from nutritrack.core.garden import SPECIES
    if not render3d.available():
        pytest.skip("Pillow not installed")
    assert set(SPECIES) == set(render3d.SPECIES_COLORS)
    sizes = set()
    for sp in SPECIES:
        for stage in range(6):
            png = render3d.tree_png(sp, stage, 30, 96)
            assert png[:8] == b"\x89PNG\r\n\x1a\n"
            sizes.add(len(render3d.tree_mesh(sp, stage)))
    assert len(sizes) > 6  # stages and species really differ
    # The turntable shows genuinely different views
    assert render3d.tree_png("cherry", 5, 0, 96) != render3d.tree_png("cherry", 5, 90, 96)
    # Bigger stages have more geometry than seeds
    assert len(render3d.tree_mesh("oak", 5)) > len(render3d.tree_mesh("oak", 0))


def test_bundled_tree_assets_exist():
    from nutritrack.core.garden import SPECIES
    from nutritrack.core.render3d import SEASONS
    root = Path(__file__).parent.parent / "src" / "assets" / "trees"
    for season in SEASONS:
        for sp in SPECIES:
            for stage in range(6):
                assert (root / season / f"{sp}_{stage}.png").stat().st_size > 500


# ---------- seasons, forest, editing ----------
def test_season_mapping_and_hemispheres():
    from nutritrack.core.render3d import season_for
    assert [season_for(m) for m in (1, 4, 7, 10)] == ["winter", "spring", "summer", "autumn"]
    assert [season_for(m, "south") for m in (1, 4, 7, 10)] == ["summer", "autumn", "winter", "spring"]
    assert season_for(1, "off") == "summer"


def test_seasonal_trees_differ_and_winter_is_bare():
    from nutritrack.core import render3d
    if not render3d.available():
        pytest.skip("Pillow not installed")
    oak = {s: render3d.tree_mesh("oak", 4, s) for s in render3d.SEASONS}
    assert len(oak["winter"]) < len(oak["summer"])            # no canopy in winter
    assert len(render3d.tree_mesh("pine", 4, "winter")) > 100  # evergreens keep their needles
    assert render3d.tree_png("oak", 4, 30, 64, "autumn") != render3d.tree_png("oak", 4, 30, 64, "summer")
    forest = render3d.forest_png(((0, 0, "oak", 4), (3, 2, "pine", 5)), 35, 160, 105, "winter", 8)
    assert forest[:8] == b"\x89PNG\r\n\x1a\n"


def test_update_entry_and_food_for_entry(svc):
    from nutritrack.core.foods import FOODS
    from nutritrack.core.nutrition import scale_nutrients
    k = today_key()
    oats = next(f for f in FOODS if f.id == "oats")
    eid = svc.store.add_entry(k, "breakfast", oats.name, scale_nutrients(oats.per100, 40), food_id="oats", grams=40,
                              amount_label="½ cup dry (40 g)")
    svc.store.update_entry(eid, meal="snacks", grams=80, amount_label="2 × ½ cup dry (40 g)", n=scale_nutrients(oats.per100, 80))
    e = svc.store.entry(eid)
    assert e["meal"] == "snacks" and e["grams"] == 80 and e["n"]["kcal"] == pytest.approx(379 * 0.8)
    assert svc.food_for_entry(e).id == "oats"
    # A custom food that was later deleted is rebuilt from the entry itself
    gone = {**e, "food_id": "c-deleted", "name": "Lasagna", "grams": 250, "amount_label": "1 slice", "n": {"kcal": 500, "protein": 25}}
    f = svc.food_for_entry(gone)
    assert f.per100["kcal"] == 200 and f.servings[0].g == 250
    assert svc.food_for_entry({**e, "food_id": None, "grams": 0}) is None  # quick adds edit as quick adds
