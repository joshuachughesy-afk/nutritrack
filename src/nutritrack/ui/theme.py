"""Design system: palette, typography, light/dark themes and the small building blocks every screen uses."""
from __future__ import annotations

import flet as ft

from . import motion

# ---------- palette ----------
ACCENT = "#1f7a4d"          # leaf green (brand)
ACCENT_SOFT = "#5fbf86"
MACRO_COLORS = {"protein": "#4c7cf0", "carbs": "#f2a93b", "fat": "#e0609a", "kcal": ACCENT, "water": "#2f9be0"}
STATUS_COLORS = {"low": "#e08a2b", "mid": "#d1b43a", "met": "#2f9a5a", "ok-limit": "#2f9a5a", "over": "#e0473f",
                 "none": "#8a948f", "behind": "#e08a2b", "on": "#2f9a5a", "ahead": "#d1b43a", "early": "#8a948f"}
EMPHASIS_COLORS = {"Carb": MACRO_COLORS["carbs"], "Protein": MACRO_COLORS["protein"], "Balanced": ACCENT}
FIRE = "#f2622e"
SHIELD = "#4c7cf0"
EARTH = "#8a6a4a"
MUTED = ft.Colors.ON_SURFACE_VARIANT

# Brand colours that change in dark mode. App.render() calls set_mode() before building a screen, so code that reads
# th.ACCENT at build time gets a green that stays readable on dark cards.
_LIGHT = {"ACCENT": "#1f7a4d", "ACCENT_SOFT": "#5fbf86"}
_DARK = {"ACCENT": "#6fd39a", "ACCENT_SOFT": "#3f9a68"}
DARK = False


def set_mode(dark: bool) -> None:
    global ACCENT, ACCENT_SOFT, DARK
    DARK = dark
    vals = _DARK if dark else _LIGHT
    ACCENT, ACCENT_SOFT = vals["ACCENT"], vals["ACCENT_SOFT"]
    MACRO_COLORS["kcal"] = ACCENT
    EMPHASIS_COLORS["Balanced"] = ACCENT
    for k in ("met", "ok-limit", "on"):
        STATUS_COLORS[k] = "#4cc27f" if dark else "#2f9a5a"


def ink(color: str) -> str:
    """A text-safe version of a brand/status colour: darker on light backgrounds, lighter on dark ones (WCAG AA)."""
    if not color.startswith("#") or len(color) != 7:
        return color
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    if DARK:
        r, g, b = (round(c + (255 - c) * 0.35) for c in (r, g, b))
    else:
        r, g, b = (round(c * 0.55) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------- tokens ----------
class T:
    """Type scale. Nothing smaller than CAPTION (12)."""
    DISPLAY, TITLE, HEADLINE, BODY, LABEL, CAPTION = 30, 24, 18, 15, 13, 12


class S:
    """Spacing scale."""
    XS, SM, MD, LG, XL = 4, 8, 12, 16, 24


class R:
    """Corner radii."""
    SM, MD, LG, PILL = 10, 14, 22, 999

FONT, FONT_SEMI, FONT_BOLD = "Jakarta", "JakartaSemi", "JakartaBold"
FONTS = {FONT: "fonts/PlusJakartaSans-Regular.ttf", FONT_SEMI: "fonts/PlusJakartaSans-SemiBold.ttf",
         FONT_BOLD: "fonts/PlusJakartaSans-ExtraBold.ttf"}

# Sky gradients behind the 3D tree (light / dark)
SKY = {False: ["#d7efff", "#e9f7e6"], True: ["#14324a", "#173a2a"]}


def emphasis_color(emphasis: str) -> str:
    return next((c for k, c in EMPHASIS_COLORS.items() if emphasis.startswith(k)), ACCENT)


def _scheme(dark: bool) -> ft.ColorScheme:
    if dark:
        return ft.ColorScheme(primary="#6fd39a", on_primary="#06210f", primary_container="#1d4a33",
                              on_primary_container="#c9f2d8", secondary="#9ab8ff", surface="#0f1612",
                              on_surface="#e6eee9", on_surface_variant="#9fb0a6", surface_container_lowest="#151e19",
                              surface_container_low="#18221c", surface_container="#1c2721",
                              surface_container_high="#223029", surface_container_highest="#2a3a31",
                              outline_variant="#2c3a33")
    return ft.ColorScheme(primary=ACCENT, on_primary="#ffffff", primary_container="#d2f1df",
                          on_primary_container="#0b3a22", secondary="#4c7cf0", surface="#f5f6f1",
                          on_surface="#16201a", on_surface_variant="#5d6b63", surface_container_lowest="#ffffff",
                          surface_container_low="#fbfcf9", surface_container="#f0f2ec", surface_container_high="#e9ece5",
                          surface_container_highest="#e3e7df", outline_variant="#dde3dc")


def theme(dark: bool = False) -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=ACCENT, color_scheme=_scheme(dark), font_family=FONT, use_material3=True,
        navigation_bar_theme=ft.NavigationBarTheme(indicator_color="#2a5a40" if dark else "#d2f1df", elevation=0,
                                                   bgcolor="#121a15" if dark else "#ffffff"),
    )


# ---------- typography ----------
def display(text: str, size: int = 28, color=None, **kw) -> ft.Text:
    """Big numbers and screen titles."""
    return ft.Text(text, size=size, font_family=FONT_BOLD, color=color, **kw)


def title(text: str, size: int = T.TITLE) -> ft.Text:
    return ft.Text(text, size=size, font_family=FONT_BOLD)


def muted(text: str, size: float = T.LABEL, **kw) -> ft.Text:
    return ft.Text(text, size=max(T.CAPTION, size), color=MUTED, **kw)


def label(text: str, **kw) -> ft.Text:
    """In-card section label (level 2): 13 semibold, sentence case."""
    return ft.Text(text, size=T.LABEL, font_family=FONT_SEMI, **kw)


# ---------- surfaces ----------
SHADOW = [ft.BoxShadow(blur_radius=24, spread_radius=-6, color=ft.Colors.with_opacity(0.10, "#0b2e1c"), offset=ft.Offset(0, 8))]


def card(*controls: ft.Control, padding: int = 18, spacing: int = 10, bgcolor=None, gradient=None) -> ft.Container:
    return ft.Container(
        content=ft.Column(list(controls), spacing=spacing, tight=True),
        padding=padding, border_radius=22, gradient=gradient,
        bgcolor=None if gradient else (bgcolor or ft.Colors.SURFACE_CONTAINER_LOWEST),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.6, ft.Colors.OUTLINE_VARIANT)), shadow=SHADOW,
    )


def heading(text: str, trailing: ft.Control | str | None = None, size: int = 17, icon=None, icon_color=None) -> ft.Control:
    """Card title (level 1): icon tile + title, optional trailing control or muted text that ellipsises, never clips."""
    t: ft.Control = ft.Text(text, size=size, font_family=FONT_SEMI, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    if icon is not None:
        col = icon_color or ACCENT
        t = ft.Row([ft.Container(ft.Icon(icon, size=size + 1, color=col), padding=6, border_radius=R.SM,
                                 bgcolor=ft.Colors.with_opacity(0.14, col)), t], spacing=10, tight=True)
    if trailing is None:
        return t
    if isinstance(trailing, str):
        trailing = muted(trailing, T.CAPTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.RIGHT)
        return ft.Row([t, ft.Container(trailing, expand=True, alignment=ft.Alignment.CENTER_RIGHT)], spacing=8,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)
    return ft.Row([t, trailing], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)


# ---------- data marks ----------
def bar(fraction: float, color: str, height: int = 8, extra: float = 0, extra_color: str | None = None,
        key: str | None = None, marker: float | None = None) -> ft.Control:
    """Rounded progress bar. With a `key` it animates from its previous value; `extra` adds a lighter second segment.

    The bar measures its own width (on_size_change) and animates the fill's pixel width. Flet's implicit scale
    animation ignores scale_x, so width is the reliable way to get a smooth fill.
    """
    f = max(0.0, min(1.0, fraction))
    total = max(0.0, min(1.0, f + max(0.0, extra)))
    anim = ft.Animation(700, ft.AnimationCurve.EASE_OUT_CUBIC) if key else None
    fills: list[tuple[ft.Container, float, str | None]] = []

    def fill(value: float, col, k: str | None) -> ft.Container:
        start_w = motion.start_width(k, value) if k else None
        c = ft.Container(bgcolor=col, border_radius=999, height=height, width=start_w or 0, animate=anim)
        fills.append((c, value, k))
        return c

    layers: list[ft.Control] = []
    if total - f > 0.001:
        layers.append(fill(total, ft.Colors.with_opacity(0.4, extra_color or color), f"{key}:x" if key else None))
    layers.append(fill(f, color, key))
    pin = None
    if marker is not None:  # "where you'd expect to be by now"
        m = max(0.0, min(1.0, marker))
        pin = ft.Container(width=3, height=height + 6, bgcolor=ft.Colors.ON_SURFACE, border_radius=2, left=0, top=0,
                           tooltip="Expected by now", data=m)
        layers.append(pin)

    def sized(e) -> None:
        width = getattr(e, "width", None) or 0
        if not width:
            return
        for c, value, k in fills:
            c.width = width * value
            if k:
                motion.remember_width(k, width, value)
        if pin is not None:
            pin.left = max(0.0, min(width - 3, width * pin.data - 1.5))
        try:
            track.update()
        except Exception:  # the bar left the page before its size arrived
            motion.log.debug("bar update skipped", exc_info=True)

    track = ft.Container(ft.Stack(layers, alignment=ft.Alignment.CENTER_LEFT), height=height, border_radius=999,
                         bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                         on_size_change=sized, expand=True)
    if pin is not None:  # the pin sticks out a little above and below the bar
        pin.top = 0
        pin.height = height
        track.clip_behavior = ft.ClipBehavior.NONE
        track.border_radius = 999
    return ft.Row([track], spacing=0)


def chip(text: str, color: str, size: int = T.CAPTION) -> ft.Container:
    return ft.Container(content=ft.Text(text, size=max(T.CAPTION, size), font_family=FONT_SEMI, color=ink(color)),
                        bgcolor=ft.Colors.with_opacity(0.16, color), border_radius=999,
                        padding=ft.Padding.symmetric(horizontal=9, vertical=3))


def dot(color: str, size: int = 9) -> ft.Container:
    return ft.Container(width=size, height=size, bgcolor=color, border_radius=size)


def icon_text(icon, text: str, color=None, size: int = 13, bold: bool = False) -> ft.Control:
    return ft.Row([ft.Icon(icon, size=size + 3, color=color),
                   ft.Text(text, size=size, font_family=FONT_SEMI if bold else None)], spacing=4, tight=True)


def pill(icon, text: str, color: str) -> ft.Container:
    return ft.Container(ft.Row([ft.Icon(icon, size=16, color=color), ft.Text(text, size=13, font_family=FONT_SEMI)],
                               spacing=5, tight=True),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5), border_radius=999,
                        bgcolor=ft.Colors.with_opacity(0.13, color))


# ---------- inputs ----------
def num_field(label: str, value=None, width: int | None = None, suffix: str | None = None, **kw) -> ft.TextField:
    return ft.TextField(label=label, value="" if value in (None, "") else str(value), keyboard_type=ft.KeyboardType.NUMBER,
                        width=width, dense=True, suffix=suffix, border_radius=12, **kw)


def parse_num(v: str | None, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return default
