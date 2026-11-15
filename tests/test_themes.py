"""Seasons and holidays: dates, combined themes, the 3D decorations and the animated effects."""
from datetime import date

import pytest

from nutritrack.core.themes import HOLIDAYS, LUNAR_NEW_YEAR, SEASON_AMBIENT, easter, holiday_for, theme_for


def test_easter_dates():
    assert easter(2024) == date(2024, 3, 31)
    assert easter(2025) == date(2025, 4, 20)
    assert easter(2026) == date(2026, 4, 5)
    assert easter(2027) == date(2027, 3, 28)


@pytest.mark.parametrize("d,key", [
    (date(2026, 12, 25), "christmas"), (date(2026, 12, 18), "christmas"), (date(2026, 12, 31), "new_year"),
    (date(2027, 1, 1), "new_year"), (date(2026, 2, 14), "valentines"), (date(2026, 3, 17), "st_patricks"),
    (date(2026, 4, 3), "easter"), (date(2026, 4, 6), "easter"), (date(2026, 10, 31), "halloween"),
    (date(2026, 2, 17), "lunar_new_year"), (date(2026, 7, 14), None), (date(2026, 12, 27), None),
])
def test_holiday_windows(d, key):
    h = holiday_for(d)
    assert (h.key if h else None) == key


def test_theme_combines_season_and_holiday():
    xmas = theme_for(date(2026, 12, 25), "winter")
    assert xmas.holiday.key == "christmas" and "lights" in xmas.decor and xmas.ambient == "twinkle"
    off = theme_for(date(2026, 12, 25), "winter", holidays=False)
    assert off.holiday is None and off.ambient == "snow"
    south = theme_for(date(2026, 12, 25), "summer")  # Christmas in the southern hemisphere: lights, no snow
    assert "sun" in south.decor and "lights" in south.decor
    assert theme_for(date(2026, 7, 1), "summer", preview="halloween").holiday.key == "halloween"
    assert theme_for(date(2026, 7, 1), "summer", preview="winter").ambient == "snow"
    assert set(LUNAR_NEW_YEAR) >= set(range(2025, 2036))


@pytest.mark.parametrize("key", [*SEASON_AMBIENT, *HOLIDAYS])
def test_every_theme_renders(key):
    from nutritrack.core import render3d
    season = key if key in SEASON_AMBIENT else "winter"
    th = theme_for(date(2026, 6, 1), season, preview=key)
    trees = ((0, "oak", 3), (10, "pine", 5))
    assert render3d.forest_png(trees, 0, 96, 60, th.season, th.decor)[:4] == b"\x89PNG"
    assert render3d.tree_png("pine", 4, 30, 64, th.season, th.decor)[:4] == b"\x89PNG"


def test_ambient_particles_for_every_effect(tmp_path):
    from test_ui_build import FakeApp

    from nutritrack.store import Store
    from nutritrack.ui.ambient import CYCLE, Ambient
    app = FakeApp(Store(tmp_path / "a.db"))
    for kind in CYCLE:
        a = Ambient(app, kind, 6)
        assert a.control.ignore_interactions  # never blocks taps or drags on the card below
        for p in a.parts:
            a._reset(p)
            a._go(p, 1.0)
            assert p.alignment is not None
    app.store.set("effects", False)
    tasks_before = len(getattr(app.page, "tasks", []))
    Ambient(app, "snow")
    assert len(getattr(app.page, "tasks", [])) == tasks_before  # effects off: no animation loop
