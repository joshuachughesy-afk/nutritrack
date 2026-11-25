"""Weekly recap: a card on Today (Sunday evening and Monday) and a sheet with the week's trees and a Share button."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import TYPE_CHECKING

import flet as ft

from .. import APP_NAME, TAGLINE
from ..core.recap import last_full_week, share_png
from ..diagnostics import log
from ..service import today_key
from . import components as cx
from . import motion
from . import theme as th
from .tree_view import tree_src

if TYPE_CHECKING:
    from .app import App


def due(app: "App", now: datetime | None = None) -> bool:
    """Show the Today card from Sunday 17:00 through Monday, until it's opened or dismissed."""
    now = now or datetime.now()
    if app.date != today_key():
        return False
    wd = now.weekday()
    if not ((wd == 6 and now.hour >= 17) or wd == 0):
        return False
    mon, _ = last_full_week(now.date())
    if app.store.get("recap_seen") == mon.isoformat():
        return False
    return app.store.logged_dates() != []


def card(app: "App") -> ft.Control:
    rc = app.svc.week_recap()

    def dismiss(_):
        app.store.set("recap_seen", rc.start)
        app.render()

    trees = ft.Row([ft.Image(src=tree_src(app.svc.species_for(d), st, 96, season=app.svc.season(d)), width=40, height=40)
                    if st is not None else ft.Container(width=40, height=40) for d, st in rc.trees],
                   spacing=2, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    return th.card(
        th.heading("Your week in the forest", ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, tooltip="Dismiss",
                                                           on_click=dismiss), icon=ft.Icons.AUTO_STORIES_ROUNDED),
        trees, ft.Text(rc.headline, size=th.T.BODY, font_family=th.FONT_SEMI),
        ft.Row([ft.FilledTonalButton("See your week", icon=ft.Icons.ARROW_FORWARD_ROUNDED, on_click=lambda _: open_sheet(app))]),
        spacing=10)


def open_sheet(app: "App") -> None:
    rc = app.svc.week_recap()
    app.store.set("recap_seen", rc.start)
    motion.haptic("light")

    async def make_png() -> bytes:
        return await asyncio.to_thread(share_png, rc, app.svc.species_for, app.svc.season, APP_NAME, TAGLINE)

    async def share(_):
        try:
            data = await make_png()
            await ft.Share().share_files([ft.ShareFile.from_bytes(data, mime_type="image/png", name="my-week.png")],
                                         text=f"My week in the forest: {rc.headline}")
        except Exception:
            log.exception("share failed; offering a download instead")
            await save(None)

    async def save(_):
        try:
            data = await make_png()
            await ft.FilePicker().save_file(dialog_title="Save your week", file_name=f"sapling-week-{rc.start}.png",
                                            src_bytes=data)
        except Exception as ex:
            log.exception("saving the recap image failed")
            app.toast(f"Couldn't save the image: {ex}")

    days = ft.Row([ft.Column([ft.Image(src=tree_src(app.svc.species_for(d), st, 96, season=app.svc.season(d)), width=44,
                                       height=44) if st is not None else
                              ft.Container(ft.Container(width=8, height=8, border_radius=4,
                                                        bgcolor=ft.Colors.OUTLINE_VARIANT),
                                           width=44, height=44, alignment=ft.Alignment.CENTER),
                              th.muted(date.fromisoformat(d).strftime("%a")[0], th.T.CAPTION)],
                             spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                   for d, st in rc.trees], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    span = f"{date.fromisoformat(rc.start).strftime('%d %b')} – {date.fromisoformat(rc.end).strftime('%d %b')}"
    tiles = ft.Row([cx.stat_tile("Full trees", f"{rc.full_trees}", "of 7 days", icon=ft.Icons.PARK_ROUNDED),
                    cx.stat_tile("Logged", f"{rc.days_logged}", "days", icon=ft.Icons.EDIT_NOTE_ROUNDED)], spacing=8)
    body = ft.Column([
        th.muted(span.upper(), th.T.CAPTION, font_family=th.FONT_SEMI),
        ft.Text(rc.headline, size=th.T.TITLE, font_family=th.FONT_BOLD),
        days, tiles,
        *[ft.Row([ft.Icon(ft.Icons.CIRCLE_ROUNDED, size=8, color=th.ACCENT), ft.Text(line, size=th.T.BODY - 1, expand=True)],
                 vertical_alignment=ft.CrossAxisAlignment.START) for line in rc.lines],
        ft.Row([ft.FilledButton("Share", icon=ft.Icons.IOS_SHARE_ROUNDED, on_click=share),
                ft.OutlinedButton("Save image", icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=save)], spacing=8),
    ], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO)
    app.page.show_dialog(ft.BottomSheet(content=ft.Container(body, padding=ft.Padding.only(left=20, right=20, bottom=28)),
                                        show_drag_handle=True, scrollable=True))
    app.render()
