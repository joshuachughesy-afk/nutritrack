"""Seasons and holidays: what the forest looks like today.

A theme is the season (from the date and your hemisphere) plus, on special days, a holiday. Each one names
* `ambient`: the animated particles over the tree and forest cards (snow, leaves, sprouts, sun, fireworks…), and
* `decor`: what gets built into the 3D scenes (Christmas lights, Easter eggs, pumpkins, spring flowers…).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Holiday:
    key: str
    name: str
    greeting: str
    accent: str          # a colour for the banner
    icon: str            # Material icon name
    ambient: str         # particle style for the overlay
    decor: tuple[str, ...] = ()


HOLIDAYS = {
    "christmas": Holiday("christmas", "Christmas", "Merry Christmas! Your forest is dressed for the holidays.", "#c0392b",
                         "PARK", "twinkle", ("lights", "star", "presents")),
    "new_year": Holiday("new_year", "New Year", "Happy New Year! Here's to a forest full of good days.", "#7b61ff",
                        "CELEBRATION", "fireworks", ("lanterns_gold",)),
    "valentines": Holiday("valentines", "Valentine's Day", "Happy Valentine's Day. Look after yourself too.", "#e0609a",
                          "FAVORITE", "hearts", ("hearts",)),
    "lunar_new_year": Holiday("lunar_new_year", "Lunar New Year", "Happy Lunar New Year! Wishing you a year of growth.",
                              "#d62828", "LIGHT", "lanterns", ("red_lanterns",)),
    "st_patricks": Holiday("st_patricks", "St Patrick's Day", "Happy St Patrick's Day! Luck favours a well-fed forest.",
                           "#2e9e4f", "SPA", "clover", ("clover",)),
    "easter": Holiday("easter", "Easter", "Happy Easter! See if you can spot the eggs in the valley.", "#b48ef0",
                      "EGG", "petals", ("eggs", "bunny")),
    "halloween": Holiday("halloween", "Halloween", "Happy Halloween! Something's glowing in the valley tonight.", "#e8590c",
                         "NIGHTLIGHT", "bats", ("pumpkins", "moon")),
}

# Lunar New Year falls on a different date each year (first new moon of the lunisolar year).
LUNAR_NEW_YEAR = {2025: (1, 29), 2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3), 2031: (1, 23),
                  2032: (2, 11), 2033: (1, 31), 2034: (2, 19), 2035: (2, 8)}

SEASON_AMBIENT = {"spring": "sprouts", "summer": "sun", "autumn": "leaves", "winter": "snow"}
SEASON_DECOR = {"spring": ("blooms", "butterflies", "rabbits"), "summer": ("sun",), "autumn": ("leaf_litter",),
                "winter": ()}


def easter(year: int) -> date:
    """Western Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holiday_for(d: date) -> Holiday | None:
    """The holiday for a date, if any. Each runs over a few days so it isn't missed."""
    md = (d.month, d.day)
    if (12, 18) <= md <= (12, 26):
        return HOLIDAYS["christmas"]
    if md >= (12, 30) or md <= (1, 2):
        return HOLIDAYS["new_year"]
    if (2, 13) <= md <= (2, 14):
        return HOLIDAYS["valentines"]
    if md == (3, 17):
        return HOLIDAYS["st_patricks"]
    if (10, 27) <= md <= (10, 31):
        return HOLIDAYS["halloween"]
    e = easter(d.year)
    if e - timedelta(days=2) <= d <= e + timedelta(days=1):
        return HOLIDAYS["easter"]
    lny = LUNAR_NEW_YEAR.get(d.year)
    if lny and abs((d - date(d.year, *lny)).days) <= 2:
        return HOLIDAYS["lunar_new_year"]
    return None


@dataclass(frozen=True)
class Theme:
    season: str
    holiday: Holiday | None
    ambient: str                 # particle style
    decor: tuple[str, ...]       # 3D additions


def theme_for(d: date, season: str, holidays: bool = True, preview: str | None = None) -> Theme:
    """Combine the season with a holiday. `preview` (or env SAPLING_THEME) forces a season or holiday, for testing."""
    preview = preview or os.getenv("SAPLING_THEME") or None
    hol = holiday_for(d) if holidays else None
    if preview in HOLIDAYS:
        hol = HOLIDAYS[preview]
    elif preview in SEASON_AMBIENT:
        season, hol = preview, None
    decor = SEASON_DECOR.get(season, ())
    if hol:
        decor = tuple(x for x in decor if x != "sun" or hol.key not in ("halloween",)) + hol.decor
    return Theme(season, hol, hol.ambient if hol else SEASON_AMBIENT.get(season, "sun"), decor)
