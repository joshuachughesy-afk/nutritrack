"""Reminder rules (pure, testable).

Two delivery paths:
  * plan_notifications(): what to hand the phone's OS scheduler. These fire even when the app is closed.
    Supplement doses repeat daily. Check-ins and water nudges are one-shot for the rest of today, with live
    pace numbers, plus generic check-ins for tomorrow; the plan is rebuilt whenever you log something.
  * due_events(): what is due right now while the app is open (in-app banners, and the fallback on
    platforms that can't schedule ahead).
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from .foods import Food
from .nutrition import Nutrients, Targets
from .pacing import compute_pace, from_min, micro_gaps, pace_summary, to_min
from .supplements import Supplement

DEFAULT_REMINDERS = {
    "enabled": False,        # user opted in
    "supplements": True,     # remind at each scheduled dose
    "water": True,           # nudge at intervals, only when behind pace
    "water_every_h": 2.0,
    "checkins": ["11:00", "15:00", "19:30"],
}

WINDOW_DOSE = 20      # minutes after a dose time we'll still remind in-app
WINDOW_CHECKIN = 30


@dataclass
class Event:
    key: str
    kind: str   # supplement | water | checkin
    title: str
    body: str
    payload: str = ""


@dataclass
class Planned:
    id: int
    when: datetime
    title: str
    body: str
    payload: str
    repeat_daily: bool = False
    kind: str = ""


def _water_slots(sched: dict, every_h: float) -> list[int]:
    step = max(30, int(every_h * 60))
    first, last = to_min(sched["wake"]) + 120, to_min(sched["sleep"]) - 60
    return list(range(first, last + 1, step))


def due_events(settings: dict, sched: dict, now_min: int, supps: list[Supplement], taken: set[tuple[str, str]],
               targets: Targets, totals: Nutrients, water_ml: float, foods: list[Food],
               water_fmt: Callable[[float], str]) -> list[Event]:
    """Which reminders are due right now? Each has a stable key; callers record sent keys so nothing repeats."""
    events: list[Event] = []

    def within(t: int, win: int) -> bool:
        return t <= now_min < t + win

    if settings.get("supplements"):
        for s in supps:
            if not s.active:
                continue
            for time in s.times:
                if (s.id, time) not in taken and within(to_min(time), WINDOW_DOSE):
                    events.append(Event(f"supp:{s.id}:{time}", "supplement", f"💊 Time for {s.name}",
                                        f"{s.dose_label}{' · take with food' if s.with_food else ''}.",
                                        payload=f"dose:{s.id}:{time}"))

    pace = compute_pace(targets, totals, water_ml, sched, now_min)
    if settings.get("water"):
        w = next(r for r in pace if r.key == "water")
        for t in _water_slots(sched, settings.get("water_every_h", 2)):
            if within(t, WINDOW_CHECKIN) and w.status == "behind":
                events.append(Event(f"water:{from_min(t)}", "water", "💧 Hydration check",
                                    f"{water_fmt(water_ml)} of {water_fmt(targets.water_ml)} so far, about "
                                    f"{water_fmt(max(0, w.gap))} behind pace. A glass now gets you back on track."))

    for time in settings.get("checkins") or []:
        if not time or not within(to_min(time), WINDOW_CHECKIN):
            continue
        events.append(_checkin_event(time, pace, targets, totals, foods, sched, water_fmt))

    # A check-in already reports water pace, so skip a separate water nudge in the same window.
    if any(e.kind == "checkin" for e in events):
        events = [e for e in events if e.kind != "water"]
    return events


def _checkin_event(time: str, pace, targets: Targets, totals: Nutrients, foods: list[Food], sched: dict,
                   water_fmt: Callable[[float], str]) -> Event:
    on_track, text = pace_summary(pace, water_fmt)
    if to_min(time) >= to_min(sched["dinner"]) - 60:
        gaps = micro_gaps(targets, totals, foods, limit=2)
        if gaps:
            text += " Low today: " + ", ".join(
                f"{g.micro.label} (try {g.foods[0][0].lower() if g.foods else 'a varied meal'})" for g in gaps) + "."
    return Event(f"check:{time}", "checkin", "✅ On track" if on_track else "📊 Check-in", text, payload="today")


def stable_id(*parts: str) -> int:
    """Deterministic positive 31-bit id so rescheduling replaces the same OS notification."""
    return zlib.crc32(":".join(parts).encode()) & 0x7FFFFFFF


def plan_notifications(now: datetime, settings: dict, sched: dict, supps: list[Supplement],
                       taken_today: set[tuple[str, str]], targets: Targets, totals: Nutrients, water_ml: float,
                       foods: list[Food], water_fmt: Callable[[float], str]) -> list[Planned]:
    """Everything the OS should deliver from now on (rebuilt on every change)."""
    if not settings.get("enabled"):
        return []
    plan: list[Planned] = []
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    now_min = now.hour * 60 + now.minute

    def at(day: datetime, hhmm: str) -> datetime:
        return day + timedelta(minutes=to_min(hhmm))

    # Supplements: daily repeating at each dose time. If today's dose is already taken (or past), start tomorrow.
    if settings.get("supplements"):
        for s in supps:
            if not s.active:
                continue
            for time in s.times:
                first = today if to_min(time) > now_min and (s.id, time) not in taken_today else today + timedelta(days=1)
                plan.append(Planned(stable_id("supp", s.id, time), at(first, time), f"💊 Time for {s.name}",
                                    f"{s.dose_label}{' · take with food' if s.with_food else ''}.",
                                    payload=f"dose:{s.id}:{time}", repeat_daily=True, kind="supplement"))

    # Check-ins: today's remaining ones carry a projection ("if nothing changes"); tomorrow's are generic.
    for i, time in enumerate(settings.get("checkins") or []):
        t = to_min(time)
        if t > now_min:
            pace = compute_pace(targets, totals, water_ml, sched, t)
            ev = _checkin_event(time, pace, targets, totals, foods, sched, water_fmt)
            plan.append(Planned(stable_id("check", "today", str(i)), at(today, time), ev.title, ev.body,
                                payload="today", kind="checkin"))
        plan.append(Planned(stable_id("check", "tomorrow", str(i)), at(today + timedelta(days=1), time),
                            "📊 Check-in", "Open NutriTrack to see if you're on pace for today.", payload="today",
                            kind="checkin"))

    # Water: only slots today where, if you drink nothing more, you'd be behind pace.
    if settings.get("water"):
        checkin_mins = {to_min(c) for c in settings.get("checkins") or [] if c}
        for t in _water_slots(sched, settings.get("water_every_h", 2)):
            if t <= now_min or any(abs(t - c) < WINDOW_CHECKIN for c in checkin_mins):
                continue
            w = next(r for r in compute_pace(targets, totals, water_ml, sched, t) if r.key == "water")
            if w.status == "behind":
                plan.append(Planned(stable_id("water", from_min(t)), at(today, from_min(t)), "💧 Hydration check",
                                    f"You're at {water_fmt(water_ml)} of {water_fmt(targets.water_ml)}. By now you'd "
                                    f"want about {water_fmt(w.expected)}, so have a glass.", payload="today", kind="water"))
    return plan
