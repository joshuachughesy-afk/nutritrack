"""Your whole garden as a 3D valley: the last 8 weeks of daily trees along a stream, oldest in the distance, today in
front. Drag sideways to orbit; the fly button plays a full orbit. Frames are rendered off the UI thread and cached."""
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
W, H = 640, 400
WEEKS = 8


def forest_trees(app: "App", weeks: int = WEEKS) -> tuple[tuple[int, str, int], ...]:
    """(slot, species, stage) for each logged day; slot 0 is the oldest day shown, the last slot is today."""
    days, _ = app.svc.history()
    scores = dict(days)
    today = date.fromisoformat(today_key())
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    trees = []
    for i in range(7 * weeks):
        d = start + timedelta(days=i)
        sc = scores.get(d.isoformat())
        if d <= today and sc is not None:
            trees.append((i, app.svc.species_for(d.isoformat()), stage_for(sc)))
    return tuple(trees)


class ForestView:
    def __init__(self, app: "App"):
        self.app = app
        self.trees = forest_trees(app)
        self.season = app.svc.season()
        self.angle = 0
        self.flying = False
        self.img = ft.Image(src=self._frame(self.angle), fit=ft.BoxFit.COVER, gapless_playback=True,
                            border_radius=18)
        gesture = ft.GestureDetector(content=self.img, on_horizontal_drag_update=self._drag,
                                     mouse_cursor=ft.MouseCursor.GRAB)
        self.fly_btn = ft.FilledTonalButton("Fly around", icon=ft.Icons.FLIGHT_TAKEOFF_ROUNDED, on_click=self._fly,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.with_opacity(0.88, ft.Colors.SURFACE),
                                                                 padding=ft.Padding.symmetric(horizontal=12)))
        count = len(self.trees)
        self.control = th.card(
            th.heading("Your forest", f"{count} tree{'s' if count != 1 else ''} planted · {self.season}",
                       icon=ft.Icons.FOREST),
            ft.Container(ft.Stack([gesture, ft.Container(self.fly_btn, right=8, top=8)]), aspect_ratio=W / H,
                         border_radius=18, clip_behavior=ft.ClipBehavior.HARD_EDGE),
            th.muted("Drag to look around. Today is closest; older days are further up the valley.", th.T.CAPTION),
            spacing=10,
        )

    def _frame(self, angle: int, small: bool = False) -> bytes:
        w, h = (480, 300) if small else (W, H)
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
