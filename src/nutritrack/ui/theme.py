"""Shared colors and small building blocks for every screen."""
from __future__ import annotations

import flet as ft

ACCENT = "#2f7d4f"
MACRO_COLORS = {"protein": "#3d7be0", "carbs": "#e0a33d", "fat": "#c95a8a", "kcal": ACCENT, "water": "#3a97d6"}
STATUS_COLORS = {"low": "#d98a2b", "mid": "#c9b13a", "met": "#2f9a5a", "ok-limit": "#2f9a5a", "over": "#d0473f",
                 "none": "#8a948f", "behind": "#d98a2b", "on": "#2f9a5a", "ahead": "#c9b13a", "early": "#8a948f"}
EMPHASIS_COLORS = {"Carb": MACRO_COLORS["carbs"], "Protein": MACRO_COLORS["protein"], "Balanced": ACCENT}

MUTED = ft.Colors.ON_SURFACE_VARIANT


def emphasis_color(emphasis: str) -> str:
    return next((c for k, c in EMPHASIS_COLORS.items() if emphasis.startswith(k)), ACCENT)


def theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=ACCENT, use_material3=True)


def card(*controls: ft.Control, padding: int = 16, spacing: int = 10, bgcolor=None) -> ft.Container:
    return ft.Container(
        content=ft.Column(list(controls), spacing=spacing, tight=True),
        padding=padding,
        border_radius=16,
        bgcolor=bgcolor or ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
    )


def heading(text: str, trailing: ft.Control | None = None, size: int = 17) -> ft.Control:
    title = ft.Text(text, size=size, weight=ft.FontWeight.W_600)
    if trailing is None:
        return title
    return ft.Row([title, trailing], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                  vertical_alignment=ft.CrossAxisAlignment.CENTER)


def muted(text: str, size: int = 13, **kw) -> ft.Text:
    return ft.Text(text, size=size, color=MUTED, **kw)


def bar(fraction: float, color: str, height: int = 8, extra: float = 0, extra_color: str | None = None) -> ft.Control:
    """Rounded progress bar. `extra` draws a lighter second segment (e.g. the supplement share)."""
    f = max(0.0, min(1.0, fraction))
    e = max(0.0, min(1.0 - f, extra))
    segs: list[ft.Control] = []
    if f > 0:
        segs.append(ft.Container(bgcolor=color, expand=int(f * 1000), border_radius=999))
    if e > 0.001:
        segs.append(ft.Container(bgcolor=ft.Colors.with_opacity(0.45, extra_color or color), expand=int(e * 1000),
                                 border_radius=999))
    rest = 1 - f - e
    if rest > 0.001:
        segs.append(ft.Container(expand=int(rest * 1000)))
    return ft.Container(content=ft.Row(segs, spacing=0), height=height, border_radius=999,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, clip_behavior=ft.ClipBehavior.HARD_EDGE)


def chip(text: str, color: str, size: int = 11) -> ft.Container:
    return ft.Container(content=ft.Text(text, size=size, weight=ft.FontWeight.W_600, color=color),
                        bgcolor=ft.Colors.with_opacity(0.14, color), border_radius=999,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2))


def dot(color: str, size: int = 9) -> ft.Container:
    return ft.Container(width=size, height=size, bgcolor=color, border_radius=size)


def num_field(label: str, value=None, width: int | None = None, suffix: str | None = None, **kw) -> ft.TextField:
    return ft.TextField(label=label, value="" if value in (None, "") else str(value), keyboard_type=ft.KeyboardType.NUMBER,
                        width=width, dense=True, suffix=suffix, border_radius=10, **kw)


def parse_num(v: str | None, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default
