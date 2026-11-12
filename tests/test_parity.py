"""Golden tests: the Python app must keep producing the values captured from the original JavaScript app."""
import json
from pathlib import Path

import pytest

from nutritrack.core.garden import score_day, summarize_history
from nutritrack.core.nutrition import MICROS, Profile, day_targets, empty_nutrients
from nutritrack.core.pacing import compute_pace
from nutritrack.core.supplements import SUPP_TEMPLATES, analyze_stack

REF = json.loads((Path(__file__).parent / "golden.json").read_text())
SCHED = {"wake": "07:00", "sleep": "23:00", "breakfast": "08:00", "lunch": "12:30", "dinner": "18:30"}


def to_profile(p: dict) -> Profile:
    return Profile(sex=p["sex"], age=p["age"], height_cm=p["heightCm"], weight_kg=p["weightKg"], activity=p["activity"],
                   goal=p["goal"], training_type=p["trainingType"], training_load=p["trainingLoad"],
                   overrides=p.get("overrides", {}))


@pytest.mark.parametrize("case", REF["targets"], ids=lambda c: f"{c['p']['sex']}-{c['p']['age']}-{c['p']['trainingType']}-{c['p']['goal']}-{c['training']}-{c['creatineG']}")
def test_targets_match_js(case):
    t = day_targets(to_profile(case["p"]), case["training"], case["creatineG"])
    o = case["out"]
    assert (t.kcal, t.protein, t.carbs, t.fat, t.water_ml, t.bmr, t.tdee, t.cycling, len(t.notes)) == \
           (o["kcal"], o["protein"], o["carbs"], o["fat"], o["water"], o["bmr"], o["tdee"], o["cycling"], o["notes"])
    assert t.micros["fiber"].target == o["fiber"]


@pytest.mark.parametrize("case", REF["micros"], ids=lambda c: f"{c['sex']}-{c['age']}")
def test_micronutrient_targets_match_js(case):
    t = day_targets(Profile(sex=case["sex"], age=case["age"]), True)
    for k, (target, ul) in case["micros"].items():
        if k == "fiber":  # scales with calories, checked per profile in test_targets_match_js
            continue
        assert t.micros[k].target == target and t.micros[k].ul == ul, k


BASE = day_targets(to_profile(REF["base"]["profile"]), True, 5)


def test_base_matches():
    b = REF["base"]
    assert (BASE.kcal, BASE.protein, BASE.carbs, BASE.fat, BASE.water_ml) == (b["kcal"], b["protein"], b["carbs"], b["fat"], b["water"])


@pytest.mark.parametrize("case", REF["scores"], ids=lambda c: f"f{c['f']}-w{c['w']}-s{c['sch']}{c['tk']}")
def test_score_and_pace_match_js(case):
    f, w = case["f"], case["w"]
    n = empty_nutrients()
    for k in ("kcal", "protein", "carbs", "fat"):
        n[k] = getattr(BASE, k) * f
    for m in MICROS:
        n[m.key] = BASE.micros[m.key].target * f * (0.7 if m.limit else 1)
    supp = empty_nutrients(); supp["vitD"] = 120 if f > 1.2 else 10
    n["vitD"] += supp["vitD"]
    r = score_day(BASE, n, supp, BASE.water_ml * w, case["sch"], case["tk"])
    assert r.score == case["score"]
    pace = compute_pace(BASE, n, BASE.water_ml * w, SCHED, 900)
    assert [[p.key, p.status, int(p.expected + 0.5)] for p in pace] == case["pace"]


def test_history_matches_js():
    scores = [80, 80, 80, 80, 80, 80, 80, None, 90, 90, 90, 30, None, 70, 75]
    h = summarize_history([(f"2026-10-{i + 1:02d}", s) for i, s in enumerate(scores)], "2026-10-15")
    ref = REF["history"]
    assert (h.streak, h.best, h.shields, h.points, h.tree_days, h.marks) == \
           (ref["streak"], ref["best"], ref["shields"], ref["points"], ref["treeDays"], ref["marks"])


def test_stack_analysis_matches_js():
    times = {"calcium": ["10:00"], "iron": ["10:00"], "d3-2000": ["08:00", "20:00"]}
    stack = []
    for i, t in enumerate(x for x in SUPP_TEMPLATES if x.tid in ("multi", "iron", "calcium", "d3-2000")):
        s = t.make(); s.id = f"s{i}"; s.times = times.get(t.tid, list(t.times)); stack.append(s)
    totals, warnings = analyze_stack(stack, BASE)
    assert (len(warnings), totals["vitD"], totals["calcium"]) == (REF["stack"]["warnings"], REF["stack"]["vitD"], REF["stack"]["calcium"])
