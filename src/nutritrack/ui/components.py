"""Shared UI components built on the design tokens in theme.py.

Screens compose these instead of hand-building the same stat tile, metric row or empty state in several places, so a
visual change happens once and every screen stays consistent.
"""
from __future__ import annotations

from datetime import time as dtime
from typing import Callable

import flet as ft

from . import theme as th

DAY_LETTERS = ["S", "M", "T", "W", "T", "F", "S"]  # Sunday first (matches Profile.training_days)
DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def stat_tile(label: str, value: str, sub: str = "", icon=None, color: str | None = None, expand: bool | int = True,
              on_click=None, tooltip: str | None = None) -> ft.Container:
    """A small labelled number: 'Calories 2,140 of 3,330'."""
    top: list[ft.Control] = []
    if icon is not None:
        top.append(ft.Icon(icon, size=18, color=color or th.ACCENT))
    top.append(th.muted(label, th.T.CAPTION, font_family=th.FONT_SEMI, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
    return ft.Container(
        ft.Column([ft.Row(top, spacing=6, tight=True), th.display(value, th.T.HEADLINE, max_lines=1),
                   *([th.muted(sub, th.T.CAPTION, max_lines=2)] if sub else [])], spacing=2, tight=True),
        expand=expand, padding=th.S.MD, border_radius=th.R.MD, bgcolor=ft.Colors.SURFACE_CONTAINER,
        on_click=on_click, ink=on_click is not None, tooltip=tooltip)


def metric_row(label: str, value: str, fraction: float, color: str, *, extra: float = 0, extra_color: str | None = None,
               note: str | None = None, note_color: str | None = None, key: str | None = None, icon=None,
               icon_color: str | None = None, height: int = 8) -> ft.Control:
    """Label · value on one line, a progress bar below, and an optional note. Text is always readable: colour only
    goes on the bar and the status icon."""
    head: list[ft.Control] = [ft.Text(label, size=th.T.LABEL, font_family=th.FONT_SEMI, expand=True, max_lines=1,
                                      overflow=ft.TextOverflow.ELLIPSIS),
                              th.muted(value, th.T.CAPTION, max_lines=1)]
    if icon is not None:
        head.append(ft.Icon(icon, size=16, color=icon_color or color))
    items: list[ft.Control] = [ft.Row(head, spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                               th.bar(fraction, color, height=height, extra=extra, extra_color=extra_color, key=key)]
    if note:
        items.append(ft.Text(note, size=th.T.CAPTION, color=th.ink(note_color) if note_color else th.MUTED))
    return ft.Column(items, spacing=5)


def empty_state(icon, text: str, action: ft.Control | None = None, title: str | None = None) -> ft.Control:
    return ft.Container(ft.Column([
        ft.Container(ft.Icon(icon, size=30, color=th.ACCENT), padding=14, border_radius=th.R.PILL,
                     bgcolor=ft.Colors.with_opacity(0.12, th.ACCENT)),
        *([ft.Text(title, size=th.T.BODY, font_family=th.FONT_SEMI, text_align=ft.TextAlign.CENTER)] if title else []),
        th.muted(text, th.T.LABEL, text_align=ft.TextAlign.CENTER),
        *([action] if action else []),
    ], spacing=th.S.SM, horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        padding=ft.Padding.symmetric(vertical=th.S.LG, horizontal=th.S.SM), alignment=ft.Alignment.CENTER)


def note(text: str, kind: str = "info", action: ft.Control | None = None, icon=None) -> ft.Container:
    """A tinted inline message. kind: info | warn | good."""
    color = {"info": th.ACCENT, "warn": "#e08a2b", "good": th.STATUS_COLORS["met"], "blue": th.SHIELD}[kind]
    ic = icon or {"info": ft.Icons.INFO_OUTLINE, "warn": ft.Icons.WARNING_AMBER_ROUNDED,
                  "good": ft.Icons.CHECK_CIRCLE_OUTLINE, "blue": ft.Icons.INFO_OUTLINE}[kind]
    body: ft.Control = ft.Text(text, size=th.T.LABEL)
    if action is not None:  # the action goes under the text so the message never gets squeezed
        body = ft.Column([body, action], spacing=2, tight=True)
    return ft.Container(ft.Row([ft.Icon(ic, size=18, color=th.ink(color)), ft.Container(body, expand=True)], spacing=10,
                               vertical_alignment=ft.CrossAxisAlignment.START),
                        bgcolor=ft.Colors.with_opacity(0.10, color), border_radius=th.R.MD,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10))


def back_header(title: str, on_back: Callable, trailing: ft.Control | None = None, subtitle: str | None = None) -> ft.Control:
    """Header for a sub-page (editor, settings page): a back arrow, the title and an optional action."""
    col: list[ft.Control] = [ft.Text(title, size=th.T.HEADLINE + 2, font_family=th.FONT_BOLD, max_lines=1,
                                     overflow=ft.TextOverflow.ELLIPSIS)]
    if subtitle:
        col.append(th.muted(subtitle, th.T.CAPTION))
    return ft.Row([ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, tooltip="Back", on_click=lambda _: on_back()),
                   ft.Column(col, spacing=0, expand=True), *([trailing] if trailing else [])],
                  spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def screen_title(text: str, subtitle: str | None = None, trailing: ft.Control | None = None) -> ft.Control:
    col: list[ft.Control] = [th.title(text)]
    if subtitle:
        col.insert(0, th.muted(subtitle.upper(), th.T.CAPTION, font_family=th.FONT_SEMI))
    return ft.Row([ft.Column(col, spacing=0, expand=True), *([trailing] if trailing else [])],
                  vertical_alignment=ft.CrossAxisAlignment.END)


def tabs(options: list[tuple[str, str]], selected: str, on_change: Callable[[str], None]) -> ft.Control:
    """Full-width segmented tabs without icons (icons made the labels clip on phones)."""
    return ft.Row([ft.SegmentedButton(
        segments=[ft.Segment(value=v, label=ft.Text(lbl, max_lines=1)) for v, lbl in options],
        selected=[selected], show_selected_icon=False, expand=True,
        on_change=lambda e: on_change(list(e.control.selected)[0]))])


def toggle_row(label: str, value: bool, on_change: Callable[[bool], None] | None = None, sub: str | None = None,
               ref_out: list | None = None) -> ft.Control:
    """A switch with a label that wraps instead of running off the card."""
    sw = ft.Switch(value=value, on_change=(lambda e: on_change(bool(e.control.value))) if on_change else None)
    if ref_out is not None:
        ref_out.append(sw)
    text: list[ft.Control] = [ft.Text(label, size=th.T.BODY - 1, font_family=th.FONT_SEMI)]
    if sub:
        text.append(th.muted(sub, th.T.CAPTION))
    return ft.Row([ft.Column(text, spacing=1, expand=True), sw], vertical_alignment=ft.CrossAxisAlignment.CENTER)


def day_chips(selected: set[int], on_change: Callable[[set[int]], None] | None = None) -> ft.Control:
    """Seven round day toggles in one row (S M T W T F S), Sunday = 0."""
    state = set(selected)
    chips: list[ft.Container] = []

    def paint(i: int) -> None:
        on = i in state
        c = chips[i]
        c.bgcolor = th.ACCENT if on else ft.Colors.SURFACE_CONTAINER_HIGH
        c.content.color = ft.Colors.ON_PRIMARY if on else ft.Colors.ON_SURFACE

    def flip(i: int) -> None:
        state.symmetric_difference_update({i})
        paint(i)
        chips[i].update()
        if on_change:
            on_change(set(state))

    for i, letter in enumerate(DAY_LETTERS):
        chips.append(ft.Container(ft.Text(letter, size=th.T.LABEL + 1, font_family=th.FONT_BOLD), width=42, height=42,
                                  border_radius=21, alignment=ft.Alignment.CENTER, ink=True, tooltip=DAY_NAMES[i],
                                  animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                                  on_click=lambda _, i=i: flip(i)))
        paint(i)
    row = ft.Row(chips, spacing=4, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    row.data = state  # the live selection, for forms that read it on save
    return row


def time_field(page_getter: Callable[[], ft.Page], value: str, label: str = "Time", on_change: Callable[[str], None] | None = None,
               width: int | None = 120) -> ft.TextField:
    """A read-only field that opens the system time picker. `.value` stays "HH:MM"."""
    field = ft.TextField(label=label, value=value, read_only=True, dense=True, border_radius=12, width=width,
                         suffix_icon=ft.Icons.SCHEDULE)

    def picked(e) -> None:
        t = e.control.value
        if t is None:
            return
        field.value = f"{t.hour:02d}:{t.minute:02d}"
        field.update()
        if on_change:
            on_change(field.value)

    def open_picker(_) -> None:
        try:
            h, m = (int(x) for x in (field.value or "08:00").split(":"))
        except ValueError:
            h, m = 8, 0
        page_getter().show_dialog(ft.TimePicker(value=dtime(h, m), on_change=picked, help_text=label,
                                                hour_format=ft.TimePickerHourFormat.H24))

    field.on_click = open_picker
    field.on_focus = open_picker
    return field


def info_sheet(page: ft.Page, title: str, *controls: ft.Control) -> None:
    """Open a bottom sheet with an explanation: where the science and fine print live."""
    page.show_dialog(ft.BottomSheet(
        content=ft.Container(ft.Column([ft.Text(title, size=th.T.HEADLINE, font_family=th.FONT_BOLD), *controls],
                                       spacing=th.S.MD, tight=True, scroll=ft.ScrollMode.AUTO),
                             padding=ft.Padding.only(left=20, right=20, bottom=28, top=4)),
        show_drag_handle=True, scrollable=True))


def info_button(page_getter: Callable[[], ft.Page], title: str, *controls: ft.Control, tooltip: str = "How this works") -> ft.IconButton:
    return ft.IconButton(ft.Icons.INFO_OUTLINE_ROUNDED, icon_size=20, tooltip=tooltip,
                         on_click=lambda _: info_sheet(page_getter(), title, *controls))


def nav_tile(icon, title: str, sub: str, on_click, color: str | None = None) -> ft.Control:
    """A settings row: icon tile, title, one-line summary, chevron."""
    col = color or th.ACCENT
    return ft.Container(ft.Row([
        ft.Container(ft.Icon(icon, size=20, color=col), padding=8, border_radius=th.R.SM,
                     bgcolor=ft.Colors.with_opacity(0.14, col)),
        ft.Column([ft.Text(title, size=th.T.BODY, font_family=th.FONT_SEMI),
                   th.muted(sub, th.T.CAPTION, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=0, expand=True),
        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=th.MUTED),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10), border_radius=th.R.MD, ink=True, on_click=on_click)
