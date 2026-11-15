"""Weekly recap: which week, the words, the share image, the Sunday notification and when the Today card shows."""
from datetime import date, datetime

from nutritrack.core.recap import build_recap, last_full_week, share_png
from nutritrack.core.trends import DayRow


def row(d, logged=True, score=70, kcal=2000, protein=150, water=3000, iron=0.5):
    return DayRow(date=d, kcal=kcal if logged else 0, target_kcal=2000, protein=protein if logged else 0, carbs=0, fat=0,
                  target_protein=150, target_carbs=1, target_fat=1, water_ml=water if logged else 0, target_water=3000,
                  doses_taken=0, doses_scheduled=0, score=score if logged else None, logged=logged,
                  micro_pct={"iron": iron if logged else 0})


def week(start_day=9, **kw):
    return [row(f"2026-11-{start_day + i:02d}", **kw) for i in range(7)]


def test_last_full_week():
    assert last_full_week(date(2026, 11, 15)) == (date(2026, 11, 9), date(2026, 11, 15))   # Sunday: this week
    assert last_full_week(date(2026, 11, 16)) == (date(2026, 11, 9), date(2026, 11, 15))   # Monday: last week
    assert last_full_week(date(2026, 11, 18)) == (date(2026, 11, 9), date(2026, 11, 15))


def test_recap_words_are_kind_and_specific():
    rc = build_recap(week(), week(2, iron=0.2))
    assert rc.full_trees == 7 and rc.days_logged == 7 and "outstanding" in rc.headline
    assert any("Calories landed right around" in line for line in rc.lines)
    assert any(line.startswith("Most improved: Iron") for line in rc.lines)
    quiet = build_recap(week(logged=False), week(2, logged=False))
    assert quiet.headline == "A quiet week in the forest" and quiet.trees[0][1] is None


def test_share_image_is_a_portrait_png():
    import io

    from PIL import Image
    rc = build_recap(week(), week(2))
    data = share_png(rc, lambda d: "oak", lambda d: "summer", "Sapling", "tagline")
    im = Image.open(io.BytesIO(data))
    assert im.size == (1080, 1350) and data[:8] == b"\x89PNG\r\n\x1a\n"


def test_sunday_recap_notification_is_planned():
    from nutritrack.core.nutrition import Profile, day_targets, empty_nutrients
    from nutritrack.core.pacing import DEFAULT_SCHEDULE
    from nutritrack.core.reminders import plan_notifications
    t = day_targets(Profile(), True)
    plan = plan_notifications(datetime(2026, 11, 12, 9, 0), {"enabled": True}, DEFAULT_SCHEDULE, [], set(), t,
                              empty_nutrients(), 0, [], str)
    recap = [p for p in plan if p.kind == "recap"]
    assert len(recap) == 1 and recap[0].when == datetime(2026, 11, 15, 18, 0)
    late = plan_notifications(datetime(2026, 11, 15, 19, 0), {"enabled": True}, DEFAULT_SCHEDULE, [], set(), t,
                              empty_nutrients(), 0, [], str)
    assert [p.when for p in late if p.kind == "recap"] == [datetime(2026, 11, 22, 18, 0)]


def test_today_card_shows_sunday_evening_until_seen(tmp_path, monkeypatch):
    from test_ui_build import FakeApp

    from nutritrack.core.foods import FOODS
    from nutritrack.core.nutrition import Profile, scale_nutrients
    from nutritrack.store import Store
    from nutritrack.ui import recap
    st = Store(tmp_path / "w.db")
    st.save_profile(Profile())
    st.add_entry("2026-11-10", "lunch", "x", scale_nutrients(FOODS[0].per100, 100), grams=100)
    app = FakeApp(st)
    app.date = "2026-11-15"
    monkeypatch.setattr(recap, "today_key", lambda: "2026-11-15")
    assert recap.due(app, datetime(2026, 11, 15, 18, 0))
    assert not recap.due(app, datetime(2026, 11, 15, 12, 0))     # Sunday morning: the week isn't over
    st.set("recap_seen", "2026-11-09")
    assert not recap.due(app, datetime(2026, 11, 16, 9, 0))
