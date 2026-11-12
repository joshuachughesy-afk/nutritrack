"""App-level logic shared by every screen: day targets, totals, scoring, garden history, reminders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .core.foods import FOODS, Food
from .core.garden import (STAGES, SPECIES, DayScore, History, level_info, score_day, stage_for, summarize_history)
from .core.nutrition import (DEFAULT_TRAINING_DAYS, Nutrients, Targets, day_targets, fmt_water, sum_nutrients,
                             weekday_sun0)
from .core.pacing import micro_gaps
from .core.reminders import Event, Planned, due_events, plan_notifications
from .core.supplements import daily_creatine
from .store import Store


def date_key(d: date) -> str:
    return d.isoformat()


def today_key() -> str:
    return date.today().isoformat()


def shift(key: str, days: int) -> str:
    return (date.fromisoformat(key) + timedelta(days=days)).isoformat()


def pretty_date(key: str) -> str:
    t = today_key()
    if key == t:
        return "Today"
    if key == shift(t, -1):
        return "Yesterday"
    if key == shift(t, 1):
        return "Tomorrow"
    return date.fromisoformat(key).strftime("%a %d %b")


@dataclass
class DayTotals:
    food: Nutrients
    supps: Nutrients
    total: Nutrients
    water_ml: float


class Service:
    def __init__(self, store: Store):
        self.store = store

    # ---------- units ----------
    @property
    def imperial(self) -> bool:
        return self.store.units == "imperial"

    def water_fmt(self, ml: float) -> str:
        return fmt_water(ml, self.imperial)

    # ---------- foods ----------
    def all_foods(self) -> list[Food]:
        return self.store.custom_foods() + FOODS

    def find_food(self, food_id: str) -> Food | None:
        return next((f for f in self.all_foods() if f.id == food_id), None)

    # ---------- targets ----------
    def is_training_day(self, key: str) -> bool:
        dt = self.store.day(key)["day_type"]
        if dt:
            return dt == "training"
        p = self.store.profile()
        days = p.training_days if p else DEFAULT_TRAINING_DAYS
        return weekday_sun0(date.fromisoformat(key)) in days

    def targets_for(self, key: str) -> Targets:
        p = self.store.profile()
        return day_targets(p, self.is_training_day(key), daily_creatine(self.store.supplements()))

    def totals(self, key: str) -> DayTotals:
        food = sum_nutrients(e["n"] for e in self.store.entries(key))
        supps = sum_nutrients(d["n"] for d in self.store.doses(key))
        return DayTotals(food, supps, sum_nutrients([food, supps]), self.store.water_total(key))

    def dose_counts(self, key: str) -> tuple[int, int]:
        active = [s for s in self.store.supplements() if s.active]
        ids = {s.id for s in active}
        scheduled = sum(len(s.times) for s in active)
        taken = sum(1 for d in self.store.doses(key) if d["supp_id"] in ids)
        return scheduled, min(taken, scheduled)

    # ---------- garden ----------
    def seed(self) -> str:
        return self.store.garden_settings()["seed"]

    def species_for(self, key: str) -> str:
        d = self.store.day(key)
        return d["species"] or (d["garden"] or {}).get("species") or self.seed()

    def has_log(self, key: str) -> bool:
        return bool(self.store.entries(key))

    def live_score(self, key: str) -> tuple[DayScore, Targets, DayTotals]:
        t = self.targets_for(key)
        tot = self.totals(key)
        scheduled, taken = self.dose_counts(key)
        return score_day(t, tot.total, tot.supps, tot.water_ml, scheduled, taken), t, tot

    def day_score(self, key: str) -> int | None:
        frozen = self.store.day(key)["garden"]
        if frozen:
            return frozen["score"]
        return self.live_score(key)[0].score if self.has_log(key) else None

    def finalize_garden(self) -> None:
        """Freeze finished days so later profile changes don't rewrite your garden."""
        if not self.store.profile():
            return
        today = today_key()
        frozen = self.store.frozen_days()
        for key in self.store.logged_dates():
            if key < today and key not in frozen:
                self.store.set_day(key, garden={"score": self.live_score(key)[0].score, "species": self.species_for(key)})

    def history(self) -> tuple[list[tuple[str, int | None]], History]:
        today = today_key()
        logged = self.store.logged_dates()
        start = logged[0] if logged and logged[0] < today else today
        frozen = self.store.frozen_days()
        days: list[tuple[str, int | None]] = []
        k = start
        while k <= today:
            if k in frozen:
                days.append((k, frozen[k]["score"]))
            elif k == today and self.has_log(k):
                days.append((k, self.live_score(k)[0].score))
            else:
                days.append((k, None))
            k = shift(k, 1)
        return days, summarize_history(days, today)

    def check_growth(self, key: str, stage: int) -> list[str]:
        """Messages to celebrate a stage-up today or a new garden level."""
        msgs = []
        if key == today_key() and stage > (self.store.day(key)["peak_stage"] or 0):
            self.store.set_day(key, peak_stage=stage)
            if stage >= 1:
                msgs.append(f"🌱 Your tree grew into a {STAGES[stage][1].lower()}!")
        lvl = level_info(self.history()[1].points).level
        g = self.store.garden_settings()
        if lvl > g["last_level"]:
            self.store.set("garden", {**g, "last_level": lvl})
            unlocked = [s.name for s in SPECIES.values() if s.level == lvl]
            msgs.append(f"🎉 Garden level {lvl}!" + (f" Unlocked: {', '.join(unlocked)}" if unlocked else ""))
        return msgs

    # ---------- reminders ----------
    def _now_min(self, now: datetime) -> int:
        return now.hour * 60 + now.minute

    def due_now(self, now: datetime | None = None) -> list[Event]:
        """In-app reminders due now that haven't been shown yet (marks them as sent)."""
        now = now or datetime.now()
        settings = self.store.reminders()
        if not settings["enabled"] or not self.store.profile():
            return []
        key = date_key(now.date())
        t = self.targets_for(key)
        tot = self.totals(key)
        taken = {(d["supp_id"], d["time"]) for d in self.store.doses(key)}
        events = due_events(settings, self.store.schedule(), self._now_min(now), self.store.supplements(), taken, t,
                            tot.total, tot.water_ml, self.all_foods(), self.water_fmt)
        sent = set(self.store.day(key)["notified"])
        fresh = [e for e in events if e.key not in sent]
        if fresh:
            self.store.set_day(key, notified=sorted(sent | {e.key for e in fresh}))
        return fresh

    def notification_plan(self, now: datetime | None = None) -> list[Planned]:
        now = now or datetime.now()
        if not self.store.profile():
            return []
        key = date_key(now.date())
        t = self.targets_for(key)
        tot = self.totals(key)
        taken = {(d["supp_id"], d["time"]) for d in self.store.doses(key)}
        return plan_notifications(now, self.store.reminders(), self.store.schedule(), self.store.supplements(), taken, t,
                                  tot.total, tot.water_ml, self.all_foods(), self.water_fmt)

    def gaps(self, key: str, limit: int = 3):
        return micro_gaps(self.targets_for(key), self.totals(key).total, self.all_foods(), limit)
