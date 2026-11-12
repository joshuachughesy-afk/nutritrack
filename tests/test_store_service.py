from datetime import date, datetime, timedelta

import pytest

from nutritrack.core.foods import FOODS
from nutritrack.core.nutrition import Profile, scale_nutrients
from nutritrack.core.reminders import stable_id
from nutritrack.core.supplements import SUPP_TEMPLATES
from nutritrack.service import Service, shift, today_key
from nutritrack.store import Store


@pytest.fixture
def svc(tmp_path):
    st = Store(tmp_path / "t.db")
    st.save_profile(Profile(sex="male", age=32, height_cm=180, weight_kg=84, activity="very", training_type="hybrid",
                            training_load="high"))
    return Service(st)


def food(fid):
    return next(f for f in FOODS if f.id == fid)


def log(svc, key, fid, grams, meal="lunch"):
    f = food(fid)
    svc.store.add_entry(key, meal, f.name, scale_nutrients(f.per100, grams), food_id=f.id, grams=grams)


def test_profile_roundtrip(svc):
    p = svc.store.profile()
    assert p.training_type == "hybrid" and p.training_days == (1, 2, 4, 5, 6)


def test_entries_totals_and_recents(svc):
    k = today_key()
    log(svc, k, "oats", 80, "breakfast"); log(svc, k, "chicken-breast", 172)
    tot = svc.totals(k)
    assert round(tot.food["kcal"]) == round(379 * 0.8 + 165 * 1.72)
    assert svc.store.recents()[:2] == ["chicken-breast", "oats"]
    svc.store.remove_entry(svc.store.entries(k)[0]["id"])
    assert len(svc.store.entries(k)) == 1


def test_water_and_undo(svc):
    k = today_key()
    svc.store.add_water(k, 500); svc.store.add_water(k, 250); svc.store.undo_water(k)
    assert svc.store.water_total(k) == 500


def test_supplements_count_and_creatine_raises_water(svc):
    k = today_key()
    base_water = svc.targets_for(k).water_ml
    cre = next(t for t in SUPP_TEMPLATES if t.tid == "creatine").make()
    d3 = next(t for t in SUPP_TEMPLATES if t.tid == "d3-2000").make()
    svc.store.save_supplement(cre); svc.store.save_supplement(d3)
    assert svc.targets_for(k).water_ml == base_water + 500
    assert svc.store.toggle_dose(k, d3, "08:00") is True
    assert svc.totals(k).supps["vitD"] == 50
    assert svc.dose_counts(k) == (2, 1)
    assert svc.store.toggle_dose(k, d3, "08:00") is False


def test_day_type_override_and_carb_cycling(svc):
    k = today_key()
    svc.store.set_day(k, day_type="training"); tr = svc.targets_for(k)
    svc.store.set_day(k, day_type="rest"); rs = svc.targets_for(k)
    assert tr.carbs > rs.carbs and tr.protein == rs.protein and tr.fat == rs.fat


def test_garden_finalize_freezes_past_days(svc):
    y = shift(today_key(), -1)
    log(svc, y, "chicken-breast", 300)
    svc.finalize_garden()
    frozen = svc.store.day(y)["garden"]
    assert frozen and frozen["species"] == "oak"
    # Later profile changes don't rewrite history
    p = svc.store.profile(); p.weight_kg = 60; svc.store.save_profile(p)
    svc.finalize_garden()
    assert svc.store.day(y)["garden"] == frozen
    days, h = svc.history()
    assert days[0] == (y, frozen["score"])


def test_due_events_fire_once(svc):
    svc.store.set("reminders", {**svc.store.reminders(), "enabled": True})
    d3 = next(t for t in SUPP_TEMPLATES if t.tid == "d3-1000").make(); d3.times = ["15:00"]
    svc.store.save_supplement(d3)
    now = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=15, minutes=5)
    first = svc.due_now(now)
    assert {e.kind for e in first} == {"supplement", "checkin"}
    assert svc.due_now(now) == []


def test_notification_plan(svc):
    svc.store.set("reminders", {**svc.store.reminders(), "enabled": True})
    d3 = next(t for t in SUPP_TEMPLATES if t.tid == "d3-1000").make(); d3.times = ["08:00", "20:00"]
    svc.store.save_supplement(d3)
    now = datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=12)
    plan = svc.notification_plan(now)
    supp = sorted((p for p in plan if p.kind == "supplement"), key=lambda p: p.when)
    # 08:00 already passed -> starts tomorrow; 20:00 still today; both repeat daily with a stable id
    assert [p.when.hour for p in supp] == [20, 8] and supp[1].when.date() == date.today() + timedelta(days=1)
    assert all(p.repeat_daily for p in supp) and supp[0].id == stable_id("supp", d3.id, "20:00")
    checkins = [p for p in plan if p.kind == "checkin"]
    assert len(checkins) == 2 + 3  # 15:00 + 19:30 today (11:00 passed) + 3 generic for tomorrow
    water = [p for p in plan if p.kind == "water"]
    assert water and all(p.when > now for p in water)  # nothing drunk yet -> nudges planned for later today
    # Disabled reminders -> nothing scheduled
    svc.store.set("reminders", {**svc.store.reminders(), "enabled": False})
    assert svc.notification_plan(now) == []


def test_export_import_roundtrip(svc, tmp_path):
    k = today_key(); log(svc, k, "banana", 118); svc.store.add_water(k, 300)
    blob = svc.store.export_json()
    other = Store(tmp_path / "o.db"); other.import_json(blob)
    assert other.entries(k)[0]["name"] == "Banana" and other.water_total(k) == 300 and other.profile().weight_kg == 84


# ---------- caching must never serve stale data ----------
def test_read_cache_invalidates_on_every_write(svc):
    k = today_key()
    assert svc.store.water_total(k) == 0
    svc.store.add_water(k, 500)
    assert svc.store.water_total(k) == 500            # same query, fresh after the write
    v = svc.store.version
    svc.store.entries(k); svc.store.entries(k)
    assert svc.store.version == v                      # reads don't bump the version
    svc.store.reset()
    assert svc.store.water_total(k) == 0 and svc.store.profile() is None


def test_memoised_targets_follow_profile_changes(svc):
    k = today_key()
    before = svc.targets_for(k).kcal
    p = svc.store.profile(); p.weight_kg = 100; svc.store.save_profile(p)
    assert svc.targets_for(k).kcal > before


def test_prefetched_period_matches_unprefetched(svc):
    t = date.today()
    for i in range(10):
        k = (t - timedelta(days=i)).isoformat()
        if i % 3:
            log(svc, k, "oats", 80 + i)
            svc.store.add_water(k, 300 * i)
    fresh = Service(Store(svc.store.path))             # separate store, no caches
    expected = [(r.date, r.kcal, r.water_ml, r.logged) for r in [
        type("R", (), {"date": d, "kcal": fresh.totals(d).total["kcal"], "water_ml": fresh.totals(d).water_ml,
                       "logged": fresh.has_log(d)})() for d in [(t - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]]]
    got = [(r.date, r.kcal, r.water_ml, r.logged) for r in svc.period(14).days]
    assert got == expected
    log(svc, t.isoformat(), "banana", 118)             # a write after prefetch must be visible
    assert svc.period(14).days[-1].kcal == pytest.approx(expected[-1][1] + 89 * 1.18)


def test_import_invalidates_cache(svc, tmp_path):
    k = today_key()
    blob = svc.store.export_json()
    svc.store.add_water(k, 999)
    assert svc.store.water_total(k) == 999
    svc.store.import_json(blob)
    assert svc.store.water_total(k) == 0
