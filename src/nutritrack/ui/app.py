"""App shell: navigation, theme, shared state, re-rendering with motion, and feedback."""
from __future__ import annotations

import traceback
from datetime import datetime

import flet as ft

from .. import diagnostics
from ..core.pacing import to_min
from ..service import Service, shift, today_key
from ..store import Store
from . import motion
from . import theme as th

NAV = [
    ("today", "Today", ft.Icons.WB_SUNNY_OUTLINED, ft.Icons.WB_SUNNY),
    ("foods", "Foods", ft.Icons.RESTAURANT_OUTLINED, ft.Icons.RESTAURANT),
    ("supps", "Supps", ft.Icons.MEDICATION_OUTLINED, ft.Icons.MEDICATION),
    ("garden", "Progress", ft.Icons.PARK_OUTLINED, ft.Icons.PARK),
    ("profile", "Profile", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON),
]
THEME_MODES = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}


class App:
    def __init__(self, page: ft.Page, store: Store | None = None):
        diagnostics.setup_logging()
        diagnostics.log.info("start %s", diagnostics.environment(page))
        self.page = page
        self._install_crash_guard()
        self.store = store or Store()
        self.svc = Service(self.store)
        self.view = "today"
        self.date = today_key()
        self._last_screen: tuple[str, str] | None = None
        self.body = ft.Column(spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        page.title = "NutriTrack"
        page.fonts = th.FONTS
        page.theme = th.theme(dark=False)
        page.dark_theme = th.theme(dark=True)
        page.theme_mode = THEME_MODES.get(self.store.get("theme_mode", "system"), ft.ThemeMode.SYSTEM)
        page.bgcolor = ft.Colors.SURFACE
        page.padding = 0
        page.on_platform_brightness_change = lambda _: self.render()
        self.visible = True
        self.closed = False
        page.on_app_lifecycle_state_change = self._on_lifecycle
        page.on_disconnect = self._on_close
        page.on_close = self._on_close
        page.on_keyboard_event = self._on_key
        page.navigation_bar = ft.NavigationBar(
            destinations=[ft.NavigationBarDestination(icon=i, selected_icon=si, label=l) for _, l, i, si in NAV],
            on_change=self._on_nav, animation_duration=400,
        )
        page.add(ft.SafeArea(content=ft.Container(content=self.body, padding=ft.Padding.only(left=16, right=16, top=10),
                                                  expand=True), expand=True))
        motion.bind(page)
        from .notify import Notifier

        self.notifier = Notifier(self)
        self.svc.finalize_garden()
        self.render()
        page.run_task(self.notifier.loop)

    def _on_close(self, _=None) -> None:
        """The session ended (tab closed, app quit): stop background work so nothing keeps running for a dead client."""
        if not self.closed:
            diagnostics.log.info("session closed")
        self.closed = True

    def _on_lifecycle(self, e) -> None:
        """Pause background work when the app isn't on screen; refresh when it comes back."""
        state = getattr(e, "state", None)
        was = self.visible
        self.visible = state not in (ft.AppLifecycleState.HIDE, ft.AppLifecycleState.PAUSE,
                                     ft.AppLifecycleState.INACTIVE, ft.AppLifecycleState.DETACH)
        if self.visible and not was:
            if self.date < today_key() and self.view == "today":
                self.date = today_key()  # came back on a new day
            self.render()

    # ---------- theme ----------
    @property
    def dark(self) -> bool:
        mode = self.page.theme_mode
        if mode == ft.ThemeMode.DARK:
            return True
        if mode == ft.ThemeMode.LIGHT:
            return False
        return getattr(self.page, "platform_brightness", None) == ft.Brightness.DARK

    def set_theme_mode(self, mode: str) -> None:
        self.store.set("theme_mode", mode)
        self.page.theme_mode = THEME_MODES[mode]
        self.render()

    # ---------- navigation ----------
    def _on_nav(self, e: ft.Event) -> None:
        motion.haptic("select")
        self.go(NAV[e.control.selected_index][0])

    def go(self, view: str, date: str | None = None) -> None:
        changed = view != self.view or (date and date != self.date)
        self.view = view
        if date:
            self.date = date
        self.render()
        if changed:  # each screen opens at the top
            self.page.run_task(self.body.scroll_to, offset=0)

    def render(self) -> None:
        from . import foods, garden, profile, supps, today  # local import avoids import cycles

        if self.closed:
            return

        if not self.store.profile() and self.view != "profile":
            self.view = "profile"
        screen = (self.view, self.date, getattr(self, "progress_tab", ""), str(getattr(self, "supp_edit", "")))
        motion.entering = screen != self._last_screen
        self._last_screen = screen
        self.page.navigation_bar.selected_index = [n[0] for n in NAV].index(self.view)
        builder = {"today": today.build, "foods": foods.build, "supps": supps.build, "garden": garden.build,
                   "profile": profile.build}[self.view]
        try:
            controls = builder(self)
        except Exception:  # a bug in one screen shouldn't blank the app
            diagnostics.log.exception("failed to build %s", self.view)
            controls = [self._error_card(traceback.format_exc())]
        self.body.controls = motion.entrance(controls + [ft.Container(height=12)])
        self.page.floating_action_button = self._quick_log_button() if self.view == "today" else None
        self.page.update()
        self.page.run_task(motion.flush)
        if hasattr(self, "notifier"):
            self.notifier.request_sync()

    # ---------- errors ----------
    def _install_crash_guard(self) -> None:
        """Flet answers an exception in an event handler by crashing the whole session. Intercept that: log it, tell
        the user calmly, and keep the app running."""
        session = getattr(self.page, "session", None)
        if session is None:
            return

        def on_error(message: str) -> None:
            diagnostics.log.error("handler error: %s", message.splitlines()[0] if message else "?")
            try:
                self.page.show_dialog(ft.SnackBar(
                    content=ft.Text("Something went wrong. Your data is safe and the error was logged."),
                    action="Details", on_action=lambda _: self.show_error_details(message),
                    duration=8000, behavior=ft.SnackBarBehavior.FLOATING))
                self.page.update()
            except Exception:
                diagnostics.log.exception("could not show the error message")

        session.error = on_error

    def show_error_details(self, details: str) -> None:
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Error details", font_family=th.FONT_BOLD),
            content=ft.Container(ft.Column([ft.Text(details[-3000:], size=11, selectable=True, font_family="monospace")],
                                           scroll=ft.ScrollMode.AUTO), width=520, height=320),
            actions=[ft.TextButton("Copy", on_click=lambda _: self.copy(details)),
                     ft.FilledButton("Close", on_click=lambda _: self.page.pop_dialog())]))

    def _error_card(self, details: str) -> ft.Control:
        return th.card(
            th.heading("This screen hit a problem", icon=ft.Icons.ERROR_OUTLINE, icon_color=th.STATUS_COLORS["over"]),
            th.muted("Your data is safe. The error was saved to the log (Profile → About & diagnostics).", 13),
            ft.Row([ft.FilledButton("Try again", icon=ft.Icons.REFRESH, on_click=lambda _: self.render()),
                    ft.TextButton("Details", on_click=lambda _: self.show_error_details(details)),
                    ft.TextButton("Go to Today", on_click=lambda _: self.go("today", today_key()))], wrap=True))

    def copy(self, text: str) -> None:
        async def go():
            try:
                await ft.Clipboard().set(text)
                self.toast("Copied")
            except Exception:
                diagnostics.log.exception("clipboard failed")
                self.toast("Couldn't copy on this device")
        self.page.run_task(go)

    # ---------- quick actions ----------
    def current_meal(self) -> str:
        sched, now = self.store.schedule(), datetime.now()
        m = now.hour * 60 + now.minute
        if m < to_min(sched["lunch"]) - 45:
            return "breakfast"
        if m < to_min(sched["dinner"]) - 45:
            return "lunch"
        return "dinner" if m < to_min(sched["dinner"]) + 120 else "snacks"

    def quick_log(self) -> None:
        from . import add_food
        motion.haptic("light")
        add_food.open_sheet(self, self.current_meal())

    def _quick_log_button(self) -> ft.FloatingActionButton:
        return ft.FloatingActionButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED), ft.Text(f"Log {self.current_meal()}", font_family=th.FONT_SEMI)],
                           tight=True, spacing=6),
            tooltip="Log food (Alt+N)", on_click=lambda _: self.quick_log(),
            shape=ft.RoundedRectangleBorder(radius=18), width=60 + 9 * len(f"Log {self.current_meal()}"), height=52)

    def _on_key(self, e) -> None:
        """Desktop shortcuts. Alt-combos only, so typing in a text field never triggers them."""
        if not getattr(e, "alt", False):
            return
        key = (e.key or "").lower()
        if key in ("arrow left", "arrow right") and self.view == "today":
            self.date = shift(self.date, -1 if key == "arrow left" else 1)
            self.render()
        elif key == "t":
            self.go("today", today_key())
        elif key == "n":
            self.go("today")
            self.quick_log()
        elif key in "12345" and len(key) == 1:
            self.go(NAV[int(key) - 1][0])

    # ---------- feedback ----------
    def toast(self, msg: str, undo=None) -> None:
        """A short message; with `undo`, it offers an Undo action that calls it."""
        def do_undo(_):
            undo()
            self.render()
        self.page.show_dialog(ft.SnackBar(content=ft.Text(msg), duration=5000 if undo else 2500,
                                          action="Undo" if undo else None, on_action=do_undo if undo else None,
                                          behavior=ft.SnackBarBehavior.FLOATING))

    def celebrate(self, msg: str, big: bool = False) -> None:
        motion.haptic("heavy" if big else "medium")
        motion.confetti(48 if big else 30)
        self.toast(msg)

    def banner(self, title: str, body: str, payload: str = "") -> None:
        """An in-app reminder. Dose reminders get a one-tap "Mark taken"."""
        is_dose = payload.startswith("dose:")
        self.page.show_dialog(ft.SnackBar(
            content=ft.Column([ft.Text(title, font_family=th.FONT_BOLD), ft.Text(body)], spacing=2, tight=True),
            action="Mark taken" if is_dose else None,
            on_action=(lambda _: self.notifier.mark_from_payload(payload)) if is_dose else None,
            duration=12000, show_close_icon=True, behavior=ft.SnackBarBehavior.FLOATING))

    def confirm(self, title: str, text: str, on_yes, yes_label: str = "Delete") -> None:
        def yes(_):
            self.page.pop_dialog()
            on_yes()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text(title, font_family=th.FONT_BOLD), content=ft.Text(text),
            actions=[ft.TextButton("Cancel", on_click=lambda _: self.page.pop_dialog()),
                     ft.FilledButton(yes_label, on_click=yes)]))
