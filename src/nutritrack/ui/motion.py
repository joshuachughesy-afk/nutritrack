"""Motion: value tweens (bars, ring, water), staggered card entrances, haptics and celebrations.

Screens are rebuilt on every change, so animation works in two phases: controls are created at their *previous* value,
and once the frame is on screen `flush()` moves them to the new value, letting Flutter's implicit animations (and our
own short tweens for canvas shapes) do the rest.
"""
from __future__ import annotations

import asyncio
import math
import random
from typing import Awaitable, Callable

import flet as ft

from ..diagnostics import log

_prev: dict[str, float] = {}
_after: list[Callable[[], None]] = []
_tasks: list[Callable[[], Awaitable[None]]] = []
entering = False
_page: ft.Page | None = None
_haptics: ft.HapticFeedback | None = None


def bind(page: ft.Page) -> None:
    global _page, _haptics
    _page = page
    try:
        _haptics = ft.HapticFeedback()
    except Exception:
        _haptics = None


def start_value(key: str, value: float) -> float:
    """Where an animated value should start: its previous value (or 0 the first time, so things grow in)."""
    start = _prev.get(key, 0.0)
    _prev[key] = value
    return start


_widths: dict[str, tuple[float, float]] = {}  # bar key -> (track width px, fraction)


def start_width(key: str, value: float) -> float:
    """Pixel width a keyed bar should start at: its last drawn width (0 the first time, so it grows in)."""
    w, frac = _widths.get(key, (0.0, 0.0))
    return w * frac


def remember_width(key: str, width: float, value: float) -> None:
    _widths[key] = (width, value)


def after(fn: Callable[[], None]) -> None:
    _after.append(fn)


def task(fn: Callable[[], Awaitable[None]]) -> None:
    _tasks.append(fn)


def entrance(controls: list[ft.Control]) -> list[ft.Control]:
    """Fade + rise each card in, staggered, when a screen opens."""
    if not entering:
        return controls
    for i, c in enumerate(controls):
        dur = 280 + min(i, 8) * 70
        c.opacity = 0
        c.offset = ft.Offset(0, 0.06)
        c.animate_opacity = ft.Animation(dur, ft.AnimationCurve.EASE_OUT)
        c.animate_offset = ft.Animation(dur + 80, ft.AnimationCurve.EASE_OUT_CUBIC)

        def show(c=c):
            c.opacity = 1
            c.offset = ft.Offset(0, 0)
        after(show)
    return controls


async def flush() -> None:
    """Phase two: move everything to its final state."""
    if not (_after or _tasks) or _page is None:
        return
    await asyncio.sleep(0.05)
    fns, jobs = list(_after), list(_tasks)
    _after.clear(); _tasks.clear()
    for fn in fns:
        try:
            fn()
        except Exception:
            log.exception("animation step")
    try:
        _page.update()
    except Exception:  # the session closed mid-animation: nothing to animate
        return
    if jobs:
        for res in await asyncio.gather(*(j() for j in jobs), return_exceptions=True):
            if isinstance(res, Exception):
                log.error("animation task failed", exc_info=res)


async def tween(setter: Callable[[float], None], start: float, end: float, ms: int = 700, update=None) -> None:
    """Manual ease-out tween for things Flutter can't animate implicitly (canvas arcs, image frames)."""
    steps = max(6, ms // 33)
    for i in range(1, steps + 1):
        t = i / steps
        e = 1 - (1 - t) ** 3
        setter(start + (end - start) * e)
        try:
            (update or _page.update)()
        except Exception:
            return
        await asyncio.sleep(ms / 1000 / steps)


def haptic(kind: str = "light") -> None:
    if _haptics is None or _page is None or _page.web:
        return
    fn = {"light": _haptics.light_impact, "medium": _haptics.medium_impact, "heavy": _haptics.heavy_impact,
          "select": _haptics.selection_click}.get(kind)
    if fn:
        async def go():
            try:
                await fn()
            except Exception:
                pass
        _page.run_task(go)


CONFETTI = ["#1f7a4d", "#5fbf86", "#f2a93b", "#e0609a", "#4c7cf0", "#f2622e", "#ffd34d"]


def confetti(n: int = 36) -> None:
    """A short burst of confetti from the middle of the screen."""
    if _page is None:
        return
    w = float(getattr(_page, "width", None) or 400)
    h = float(getattr(_page, "height", None) or 800)
    cx, cy = w / 2, h * 0.32
    rnd = random.Random()
    pieces = []
    for _ in range(n):
        pieces.append(ft.Container(
            width=rnd.choice([6, 8, 10]), height=rnd.choice([8, 12, 14]), bgcolor=rnd.choice(CONFETTI), border_radius=2,
            left=cx, top=cy, rotate=ft.Rotate(rnd.uniform(0, math.pi)), opacity=1,
            animate_position=ft.Animation(rnd.randint(900, 1400), ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_opacity=ft.Animation(1300, ft.AnimationCurve.EASE_IN),
            animate_rotation=ft.Animation(1400, ft.AnimationCurve.EASE_OUT)))
    layer = ft.Stack(pieces, width=w, height=h)
    shield = ft.TransparentPointer(content=layer)
    _page.overlay.append(shield)
    _page.update()

    async def fly():
        await asyncio.sleep(0.03)
        for p in pieces:
            ang = rnd.uniform(-math.pi, 0) if rnd.random() < 0.8 else rnd.uniform(0, math.pi)
            dist = rnd.uniform(90, min(w, h) * 0.55)
            p.left = cx + math.cos(ang) * dist
            p.top = cy + math.sin(ang) * dist + rnd.uniform(60, 220)
            p.opacity = 0
            p.rotate = ft.Rotate(rnd.uniform(-6, 6))
        _page.update()
        await asyncio.sleep(1.5)
        if shield in _page.overlay:
            _page.overlay.remove(shield)
            _page.update()

    _page.run_task(fly)
