"""The interactive 3D tree: drag sideways to turn it, it spins and pops when it grows.

Frames come from core.render3d (pure Python + Pillow). If Pillow isn't available on a device, the pre-rendered PNGs in
assets/trees/ are used instead (no rotation).
"""
from __future__ import annotations

import asyncio

import flet as ft

from ..core import render3d
from . import motion

STEP = 15  # degrees between turntable frames


def tree_src(species: str, stage: int, size: int = 160, angle: int = 30, season: str = "summer"):
    """Image source for a tree: rendered bytes when possible, else the bundled (summer) asset."""
    if render3d.available():
        return render3d.tree_png(species, stage, angle % 360, size, season)
    return f"trees/{species}_{stage}.png"


class TreeView:
    """Builds the tree control; `.control` is what goes on screen."""

    def __init__(self, species: str, stage: int, size: int = 220, grew: bool = False, on_tap=None, season: str = "summer"):
        self.species, self.stage, self.size_px, self.season = species, stage, size, season
        self.angle = 30
        self.can_spin = render3d.available()
        self.img = ft.Image(src=tree_src(species, stage, size, self.angle, season), width=size, height=size, gapless_playback=True)
        gesture = ft.GestureDetector(content=self.img, on_horizontal_drag_update=self._drag, on_tap=on_tap,
                                     mouse_cursor=ft.MouseCursor.GRAB if self.can_spin else None)
        self.control = ft.Container(content=gesture, width=size, height=size, scale=ft.Scale(0.6 if grew else 1),
                                    animate_scale=ft.Animation(900, ft.AnimationCurve.ELASTIC_OUT),
                                    tooltip="Drag to turn your tree" if self.can_spin else None)
        if grew:  # pop in and do a full turn
            motion.after(lambda: setattr(self.control, "scale", ft.Scale(1)))
            motion.task(self.spin)

    def _set_angle(self, angle: float) -> bool:
        q = int(round(angle / STEP) * STEP) % 360
        if q == self.angle:
            return False
        self.angle = q
        self.img.src = tree_src(self.species, self.stage, self.size_px, q, self.season)
        return True

    def _drag(self, e) -> None:
        if self.can_spin and self._set_angle(self.angle - (e.primary_delta or 0) * 0.9):
            self.img.update()

    async def spin(self) -> None:
        if not self.can_spin:
            return
        start = self.angle
        for i in range(1, 360 // STEP + 1):
            self._set_angle(start + i * STEP)
            try:
                self.img.update()
            except Exception:
                return
            await asyncio.sleep(0.045)
