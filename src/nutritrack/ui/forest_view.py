"""Your whole garden as one 3D landscape: a plot per day for the last 8 weeks (rows = weeks, columns = Mon..Sun).

Drag sideways to orbit; "Fly around" plays a full orbit. Frames are rendered off the UI thread and cached.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import TYPE_CHECKING

import flet as ft

from ..core import render3d
from ..core.garden import stage_for
from ..service import today_key
from . import motion
from . import theme as th

from ..diagnostics import log

if TYPE_CHECKING:
    from .app import App

STEP = 15
W, H = 640, 420


def forest_trees(app: "App", weeks: int = 8) -> tuple[tuple[int, int, str, int], ...]:
    days, _ = app.svc.history()
    scores = dict(days)
    today = date.fromisoformat(today_key())
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    trees = []
    for i in range(7 * weeks):
        d = start + timedelta(days=i)
        sc = scores.get(d.isoformat())
        if d <= today and sc is not None:
            trees.append((i % 7, i // 7, app.svc.species_for(d.isoformat()), stage_for(sc)))
    return tuple(trees)


class ForestView:
    def __init__(self, app: "App"):
        self.app = app
        self.trees = forest_trees(app)
        self.season = app.svc.season()
        self.angle = 35
        self.flying = False
        self.img = ft.Image(src=self._frame(self.angle), fit=ft.BoxFit.CONTAIN, gapless_playback=True)
        gesture = ft.GestureDetector(content=self.img, on_horizontal_drag_update=self._drag,
                                     mouse_cursor=ft.MouseCursor.GRAB)
        self.fly_btn = ft.FilledTonalButton("Fly around", icon=ft.Icons.FLIGHT_TAKEOFF_ROUNDED, on_click=self._fly)
        count = len(self.trees)
        sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])
        self.control = th.card(
            th.heading("Your forest", th.muted(f"{count} tree{'s' if count != 1 else ''} · {self.season}", 12),
                       icon=ft.Icons.FOREST),
            ft.Container(gesture, gradient=sky, border_radius=18, padding=4, alignment=ft.Alignment.CENTER,
                         aspect_ratio=W / H),
            ft.Row([th.muted("Drag to look around. Each row is a week, oldest at the back.", 12, expand=True), self.fly_btn],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _frame(self, angle: int, small: bool = False) -> bytes:
        w, h = (480, 315) if small else (W, H)
        return render3d.forest_png(self.trees, angle % 360, w, h, self.season)

    def _drag(self, e) -> None:
        if self.flying:
            return
        q = int(round((self.angle - (e.primary_delta or 0) * 0.6) / STEP) * STEP) % 360
        if q != self.angle:
            self.angle = q
            self.img.src = self._frame(q)
            self.img.update()

    async def _fly(self, _=None) -> None:
        if self.flying:
            return
        self.flying = True
        motion.haptic("light")
        self.fly_btn.disabled = True
        self.fly_btn.update()
        try:
            start = self.angle
            for i in range(1, 360 // STEP + 1):
                a = (start + i * STEP) % 360
                frame = await asyncio.to_thread(self._frame, a, True)
                self.img.src = frame
                self.img.update()
                await asyncio.sleep(0.02)
            self.angle = start
            self.img.src = await asyncio.to_thread(self._frame, start)
            self.img.update()
        except Exception:
            log.exception("forest fly-around")
        finally:
            self.flying = False
            self.fly_btn.disabled = False
            try:
                self.fly_btn.update()
            except Exception:
                pass
