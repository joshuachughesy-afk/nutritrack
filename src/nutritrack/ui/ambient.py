"""Animated seasonal and holiday effects over the tree and forest cards.

A handful of light particles (snow, leaves, sprouting flowers, a turning sun, fireworks, hearts…) move with Flutter's
implicit animations: each cycle sets a start position without animation, then an end position with it, so the device
does the in-between frames and the server only sends two small updates per cycle. The loop stops by itself when the
card leaves the screen, the app goes to the background, or the session ends, and it never takes taps or drags.
"""
from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import flet as ft

from ..diagnostics import log

if TYPE_CHECKING:
    from .app import App

PALETTES = {
    "leaves": ["#d9822b", "#c0392b", "#e8b43a", "#a0522d"],
    "petals": ["#ff9ec7", "#9ad0ff", "#ffe066", "#b6f09c", "#c9a7ff"],
    "hearts": ["#ff4d6d", "#ff8fa3", "#c9184a"],
    "fireworks": ["#ffd84d", "#ff4d6d", "#4dd2ff", "#7dff7a", "#ff8de0"],
    "twinkle": ["#ffd84d", "#ffffff", "#ff8de0", "#4dd2ff"],
    "lanterns": ["#e63946", "#ff7b54"],
    "clover": ["#2e9e4f", "#55c271"],
    "sprouts": ["#ffd84d", "#ff8de0", "#ffffff", "#b48ef0", "#ff9f5a"],
}
CYCLE = {"snow": 7.0, "leaves": 6.0, "petals": 7.0, "hearts": 6.5, "lanterns": 9.0, "clover": 6.5, "sprouts": 4.0,
         "sun": 8.0, "twinkle": 2.2, "fireworks": 1.8, "bats": 7.0}


class Ambient:
    """`.control` is a transparent layer to put on top of a card's content in a Stack (left/top/right/bottom = 0)."""

    def __init__(self, app: "App", kind: str, count: int = 9, seed: int = 0):
        self.app, self.kind = app, kind
        self.rnd = random.Random(seed)
        self.parts: list[ft.Container] = []
        self.rot = 0.0
        for i in range(count if kind != "sun" else 1):
            self.parts.append(self._particle(i))
        self.control = ft.Container(ft.Stack(self.parts, expand=True), left=0, right=0, top=0, bottom=0,
                                    ignore_interactions=True, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        if app.store.get("effects", True) and not getattr(app, "reduce_motion", False):
            app.page.run_task(self._loop)

    # ---------- particles ----------
    def _icon(self, color: str) -> ft.Control:
        k = self.kind
        size = self.rnd.uniform(10, 16)
        if k == "snow":
            d = self.rnd.uniform(5, 9)  # white flakes with a soft blue edge, so they show against a pale sky
            return ft.Container(width=d, height=d, border_radius=d, bgcolor="#ffffff",
                                border=ft.Border.all(1, ft.Colors.with_opacity(0.55, "#8fb3d9")),
                                shadow=[ft.BoxShadow(blur_radius=4, color=ft.Colors.with_opacity(0.5, "#6c8fb3"))])
        if k == "petals":
            return ft.Container(width=7, height=10, border_radius=5, bgcolor=color)
        icon = {"leaves": ft.Icons.ECO, "hearts": ft.Icons.FAVORITE, "fireworks": ft.Icons.AUTO_AWESOME,
                "twinkle": ft.Icons.AUTO_AWESOME, "lanterns": ft.Icons.LIGHT, "clover": ft.Icons.SPA,
                "sprouts": ft.Icons.LOCAL_FLORIST, "bats": ft.Icons.FLUTTER_DASH, "sun": ft.Icons.WB_SUNNY}[k]
        if k == "sun":  # a warm glow behind a bright sun
            return ft.Container(ft.Icon(ft.Icons.WB_SUNNY, size=38, color="#ffb300"), width=58, height=58,
                                border_radius=29, alignment=ft.Alignment.CENTER,
                                gradient=ft.RadialGradient(colors=[ft.Colors.with_opacity(0.55, "#fff3b0"),
                                                                   ft.Colors.with_opacity(0.0, "#fff3b0")]))
        elif k == "fireworks":
            size = self.rnd.uniform(22, 34)
        return ft.Icon(icon, size=size, color=color)

    def _particle(self, i: int) -> ft.Container:
        color = self.rnd.choice(PALETTES.get(self.kind, ["#ffffff"]))
        if self.kind == "bats":
            color = "#2b2340"
        if self.kind == "sun":
            color = "#ffb703"
        # The outer container fills the card and moves via alignment; only the inner one spins, around its own centre.
        inner = ft.Container(self._icon(color), rotate=0, scale=1, animate_rotation=ft.Animation(1),
                             animate_scale=ft.Animation(1))
        c = ft.Container(inner, left=0, right=0, top=0, bottom=0, opacity=1)
        c.data = {"x": self.rnd.uniform(-0.95, 0.95), "delay": i / 9}
        self._reset(c)
        return c

    def _reset(self, c: ft.Container) -> None:
        """Start position (no animation)."""
        k, x = self.kind, c.data["x"]
        # Keep an animation attached but make it instant: removing it (None) swaps the widget for a non-animated one,
        # and the next move would then jump to the end instead of animating.
        snap = ft.Animation(1)
        c.animate = c.animate_opacity = c.content.animate_rotation = c.content.animate_scale = snap
        if k in ("snow", "leaves", "petals", "clover"):
            c.alignment, c.opacity = ft.Alignment(x, -1.15), 1
            c.content.rotate = 0
        elif k in ("hearts", "lanterns"):
            c.alignment, c.opacity = ft.Alignment(x, 1.15), 0.95
        elif k == "sprouts":
            c.alignment, c.content.scale, c.opacity = ft.Alignment(x, 0.96), 0.01, 1
        elif k == "bats":
            c.alignment = ft.Alignment(-1.2, self.rnd.uniform(-0.8, -0.2))
        elif k == "sun":
            c.alignment, c.content.rotate, c.opacity = ft.Alignment(-0.9, -0.85), self.rot, 0.95
        else:  # twinkle / fireworks
            c.alignment = ft.Alignment(self.rnd.uniform(-0.9, 0.9), self.rnd.uniform(-0.9, 0.2 if k == "twinkle" else -0.2))
            # fireworks start as a bright spark and burst outward as they fade; stars twinkle in from nothing
            c.content.scale, c.opacity = 0.2, (1.0 if k == "fireworks" else 0.0)

    def _go(self, c: ft.Container, dur: float) -> None:
        """End position (animated)."""
        k, x, ms = self.kind, c.data["x"], int(dur * 1000)
        anim = ft.Animation(ms, ft.AnimationCurve.LINEAR if k in ("snow", "petals") else ft.AnimationCurve.EASE_IN_OUT)
        c.animate, c.animate_opacity = anim, anim
        c.content.animate_rotation = c.content.animate_scale = anim
        if k in ("snow", "leaves", "petals", "clover"):
            drift = self.rnd.uniform(-0.35, 0.35)
            c.alignment = ft.Alignment(max(-1, min(1, x + drift)), 1.15)
            c.content.rotate = self.rnd.uniform(-3, 3) if k != "snow" else 0
            c.opacity = 0.0  # fade as it falls, so nothing piles up along the bottom edge
            c.animate_opacity = ft.Animation(ms, ft.AnimationCurve.EASE_IN_EXPO)
        elif k in ("hearts", "lanterns"):
            c.alignment, c.opacity = ft.Alignment(x + self.rnd.uniform(-0.2, 0.2), -1.15), 0.2
        elif k == "sprouts":
            c.content.scale = self.rnd.uniform(0.8, 1.2)
        elif k == "bats":
            c.alignment = ft.Alignment(1.2, self.rnd.uniform(-0.9, -0.3))
        elif k == "sun":
            self.rot += 0.6
            c.content.rotate, c.opacity = self.rot, 1.0 if c.opacity < 1 else 0.85
        else:
            c.content.scale, c.opacity = (1.5 if k == "fireworks" else 1.0), (0.0 if k == "fireworks" else 0.95)

    # ---------- the loop ----------
    def _alive(self) -> bool:
        try:
            _ = self.control.page  # raises once the card has left the page
        except Exception:
            return False
        return not self.app.closed

    async def _loop(self) -> None:
        dur = CYCLE.get(self.kind, 6.0)
        await asyncio.sleep(0.4)
        try:
            for cycle in range(400):  # bounded: ~45 minutes of snow at most per screen visit
                if not self._alive():
                    return
                if not self.app.visible:
                    await asyncio.sleep(2)
                    continue
                group = [p for i, p in enumerate(self.parts) if (i + cycle) % 2 == 0] if len(self.parts) > 3 else self.parts
                for p in group:
                    if self.kind != "sprouts" or cycle % 3 == 0:
                        self._reset(p)
                        p.data["x"] = self.rnd.uniform(-0.95, 0.95) if self.kind != "sun" else 0
                self.control.update()
                await asyncio.sleep(0.05)
                for p in group:
                    self._go(p, dur * self.rnd.uniform(0.85, 1.15))
                self.control.update()
                await asyncio.sleep(dur / 2 if len(self.parts) > 3 else dur)
        except Exception:
            if self._alive():
                log.exception("ambient effect stopped")


def layer(app: "App", kind: str, count: int = 9, seed: int = 0) -> ft.Control:
    if kind == "snow":
        count = int(count * 1.6)  # snow reads best as many small flakes
    return Ambient(app, kind, count, seed).control
