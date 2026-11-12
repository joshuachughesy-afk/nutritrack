"""Local-first SQLite storage. Everything stays on the device (no account, no server).

Tables are plain and analysis-friendly, e.g. `pandas.read_sql("select * from entries", conn)`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .core.foods import Food
from .core.nutrition import Profile
from .core.pacing import DEFAULT_SCHEDULE
from .core.reminders import DEFAULT_REMINDERS
from .core.supplements import Supplement

SCHEMA = """
create table if not exists settings (key text primary key, value text not null);
create table if not exists custom_foods (id text primary key, data text not null, created real not null);
create table if not exists entries (
  id text primary key, date text not null, meal text not null, food_id text, name text not null,
  grams real not null default 0, amount_label text not null default '', n text not null, created real not null);
create index if not exists entries_date on entries(date);
create table if not exists water (id text primary key, date text not null, ml real not null, at real not null);
create index if not exists water_date on water(date);
create table if not exists supplements (id text primary key, data text not null, position integer not null default 0);
create table if not exists doses (
  id text primary key, date text not null, supp_id text not null, time text not null, name text not null,
  n text not null, at real not null, unique(date, supp_id, time));
create table if not exists days (
  date text primary key, day_type text, species text, peak_stage integer default 0,
  garden text, notified text, weight_kg real);
"""


def default_db_path() -> Path:
    # Flet sets FLET_APP_STORAGE_DATA to the app's private data folder on phones and desktop builds.
    base = os.getenv("FLET_APP_STORAGE_DATA") or os.path.join(Path.home(), ".nutritrack")
    Path(base).mkdir(parents=True, exist_ok=True)
    return Path(base) / "nutritrack.db"


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:12]


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = str(path or default_db_path())
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---------- helpers ----------
    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def _x(self, sql: str, args: tuple = ()) -> None:
        with self.lock:
            self.conn.execute(sql, args)
            self.conn.commit()

    # ---------- settings ----------
    def get(self, key: str, default=None):
        rows = self._q("select value from settings where key=?", (key,))
        return json.loads(rows[0]["value"]) if rows else default

    def set(self, key: str, value) -> None:
        self._x("insert into settings(key, value) values(?, ?) on conflict(key) do update set value=excluded.value",
                (key, json.dumps(value)))

    def profile(self) -> Profile | None:
        d = self.get("profile")
        return Profile.from_dict(d) if d else None

    def save_profile(self, p: Profile) -> None:
        self.set("profile", p.to_dict())

    @property
    def units(self) -> str:
        return self.get("units", "metric")

    def schedule(self) -> dict:
        return {**DEFAULT_SCHEDULE, **(self.get("schedule") or {})}

    def reminders(self) -> dict:
        return {**DEFAULT_REMINDERS, **(self.get("reminders") or {})}

    def garden_settings(self) -> dict:
        return {"seed": "oak", "last_level": 1, **(self.get("garden") or {})}

    def recents(self) -> list[str]:
        return self.get("recents", [])

    # ---------- foods ----------
    def custom_foods(self) -> list[Food]:
        return [Food.from_dict(json.loads(r["data"])) for r in self._q("select data from custom_foods order by created desc")]

    def save_custom_food(self, f: Food) -> None:
        self._x("insert or replace into custom_foods(id, data, created) values(?, ?, ?)",
                (f.id, json.dumps(f.to_dict()), time.time()))

    def delete_custom_food(self, food_id: str) -> None:
        self._x("delete from custom_foods where id=?", (food_id,))

    # ---------- food log ----------
    def entries(self, date: str) -> list[dict]:
        rows = self._q("select * from entries where date=? order by created", (date,))
        return [{**dict(r), "n": json.loads(r["n"])} for r in rows]

    def add_entry(self, date: str, meal: str, name: str, n: dict, food_id: str | None = None, grams: float = 0,
                  amount_label: str = "") -> str:
        eid = new_id("e-")
        self._x("insert into entries(id, date, meal, food_id, name, grams, amount_label, n, created) values(?,?,?,?,?,?,?,?,?)",
                (eid, date, meal, food_id, name, grams, amount_label, json.dumps(n), time.time()))
        if food_id:
            self.set("recents", ([food_id] + [r for r in self.recents() if r != food_id])[:12])
        return eid

    def remove_entry(self, entry_id: str) -> None:
        self._x("delete from entries where id=?", (entry_id,))

    def logged_dates(self) -> list[str]:
        return [r["date"] for r in self._q("select distinct date from entries order by date")]

    # ---------- water ----------
    def water_total(self, date: str) -> float:
        return float(self._q("select coalesce(sum(ml), 0) s from water where date=?", (date,))[0]["s"])

    def water_count(self, date: str) -> int:
        return int(self._q("select count(*) c from water where date=?", (date,))[0]["c"])

    def add_water(self, date: str, ml: float) -> None:
        self._x("insert into water(id, date, ml, at) values(?,?,?,?)", (new_id("w-"), date, ml, time.time()))

    def undo_water(self, date: str) -> None:
        self._x("delete from water where id = (select id from water where date=? order by at desc limit 1)", (date,))

    # ---------- supplements ----------
    def supplements(self) -> list[Supplement]:
        return [Supplement.from_dict(json.loads(r["data"])) for r in self._q("select data from supplements order by position, rowid")]

    def save_supplement(self, s: Supplement) -> None:
        exists = self._q("select position from supplements where id=?", (s.id,))
        pos = exists[0]["position"] if exists else len(self._q("select id from supplements"))
        self._x("insert or replace into supplements(id, data, position) values(?,?,?)", (s.id, json.dumps(s.to_dict()), pos))

    def delete_supplement(self, supp_id: str) -> None:
        self._x("delete from supplements where id=?", (supp_id,))

    def doses(self, date: str) -> list[dict]:
        return [{**dict(r), "n": json.loads(r["n"])} for r in self._q("select * from doses where date=? order by time", (date,))]

    def toggle_dose(self, date: str, s: Supplement, time_str: str) -> bool:
        """Toggle a scheduled dose; nutrients are snapshotted so editing the supplement later doesn't rewrite history.
        Returns True if the dose is now marked taken."""
        if self._q("select id from doses where date=? and supp_id=? and time=?", (date, s.id, time_str)):
            self._x("delete from doses where date=? and supp_id=? and time=?", (date, s.id, time_str))
            return False
        self.mark_dose(date, s, time_str)
        return True

    def mark_dose(self, date: str, s: Supplement, time_str: str) -> None:
        self._x("insert or ignore into doses(id, date, supp_id, time, name, n, at) values(?,?,?,?,?,?,?)",
                (new_id("d-"), date, s.id, time_str, s.name, json.dumps(s.n), time.time()))

    # ---------- per-day metadata ----------
    def day(self, date: str) -> dict:
        rows = self._q("select * from days where date=?", (date,))
        if not rows:
            return {"date": date, "day_type": None, "species": None, "peak_stage": 0, "garden": None, "notified": [],
                    "weight_kg": None}
        d = dict(rows[0])
        d["garden"] = json.loads(d["garden"]) if d["garden"] else None
        d["notified"] = json.loads(d["notified"]) if d["notified"] else []
        return d

    def set_day(self, date: str, **fields) -> None:
        cur = self.day(date)
        cur.update(fields)
        self._x("insert or replace into days(date, day_type, species, peak_stage, garden, notified, weight_kg) "
                "values(?,?,?,?,?,?,?)",
                (date, cur["day_type"], cur["species"], cur["peak_stage"] or 0,
                 json.dumps(cur["garden"]) if cur["garden"] else None, json.dumps(cur["notified"] or []), cur["weight_kg"]))

    def frozen_days(self) -> dict[str, dict]:
        return {r["date"]: json.loads(r["garden"]) for r in self._q("select date, garden from days where garden is not null")}

    # ---------- backup ----------
    def export_json(self) -> str:
        out = {"version": 2, "settings": {r["key"]: json.loads(r["value"]) for r in self._q("select * from settings")}}
        for table in ("custom_foods", "entries", "water", "supplements", "doses", "days"):
            out[table] = [dict(r) for r in self._q(f"select * from {table}")]
        return json.dumps(out, indent=1)

    def import_json(self, text: str) -> None:
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("version") != 2:
            raise ValueError("Not a NutriTrack (Python) backup")
        with self.lock:
            for table in ("settings", "custom_foods", "entries", "water", "supplements", "doses", "days"):
                self.conn.execute(f"delete from {table}")
            for k, v in data["settings"].items():
                self.conn.execute("insert into settings(key, value) values(?, ?)", (k, json.dumps(v)))
            for table in ("custom_foods", "entries", "water", "supplements", "doses", "days"):
                for row in data.get(table, []):
                    cols = ", ".join(row)
                    self.conn.execute(f"insert into {table}({cols}) values({', '.join('?' * len(row))})", tuple(row.values()))
            self.conn.commit()

    def reset(self) -> None:
        with self.lock:
            for table in ("settings", "custom_foods", "entries", "water", "supplements", "doses", "days"):
                self.conn.execute(f"delete from {table}")
            self.conn.commit()
