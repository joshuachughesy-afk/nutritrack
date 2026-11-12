"""App shell: navigation, theme, shared state, re-rendering with motion, and feedback."""
from __future__ import annotations

import flet as ft

from ..service import Service, today_key
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
        self.page = page
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
        page.on_app_lifecycle_state_change = self._on_lifecycle
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

        if not self.store.profile() and self.view != "profile":
            self.view = "profile"
        screen = (self.view, self.date, getattr(self, "progress_tab", ""), str(getattr(self, "supp_edit", "")))
        motion.entering = screen != self._last_screen
        self._last_screen = screen
        self.page.navigation_bar.selected_index = [n[0] for n in NAV].index(self.view)
        builder = {"today": today.build, "foods": foods.build, "supps": supps.build, "garden": garden.build,
                   "profile": profile.build}[self.view]
        self.body.controls = motion.entrance(builder(self) + [ft.Container(height=12)])
        self.page.update()
        self.page.run_task(motion.flush)
        if hasattr(self, "notifier"):
            self.notifier.request_sync()

    # ---------- feedback ----------
    def toast(self, msg: str) -> None:
        self.page.show_dialog(ft.SnackBar(content=ft.Text(msg), duration=2500, behavior=ft.SnackBarBehavior.FLOATING))

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
