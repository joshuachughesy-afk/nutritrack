"""App shell: navigation, shared state, re-rendering and toasts."""
from __future__ import annotations

import flet as ft

from ..service import Service, today_key
from ..store import Store
from . import theme as th

NAV = [
    ("today", "Today", ft.Icons.TODAY_OUTLINED, ft.Icons.TODAY),
    ("foods", "Foods", ft.Icons.RESTAURANT_OUTLINED, ft.Icons.RESTAURANT),
    ("supps", "Supps", ft.Icons.MEDICATION_OUTLINED, ft.Icons.MEDICATION),
    ("garden", "Garden", ft.Icons.PARK_OUTLINED, ft.Icons.PARK),
    ("profile", "Profile", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON),
]


class App:
    def __init__(self, page: ft.Page, store: Store | None = None):
        self.page = page
        self.store = store or Store()
        self.svc = Service(self.store)
        self.view = "today"
        self.date = today_key()
        self.body = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)

        page.title = "NutriTrack"
        page.theme = th.theme()
        page.dark_theme = th.theme()
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.padding = 0
        page.navigation_bar = ft.NavigationBar(
            destinations=[ft.NavigationBarDestination(icon=i, selected_icon=si, label=l) for _, l, i, si in NAV],
            on_change=self._on_nav,
        )
        page.add(ft.SafeArea(content=ft.Container(content=self.body, padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                                                  expand=True), expand=True))
        self.svc.finalize_garden()
        self.render()

    # ---------- navigation ----------
    def _on_nav(self, e: ft.Event) -> None:
        self.go(NAV[e.control.selected_index][0])

    def go(self, view: str, date: str | None = None) -> None:
        self.view = view
        if date:
            self.date = date
        self.render()

    def render(self) -> None:
        from . import foods, garden, profile, supps, today  # local import avoids import cycles

        if not self.store.profile() and self.view != "profile":
            self.view = "profile"
        self.page.navigation_bar.selected_index = [n[0] for n in NAV].index(self.view)
        builder = {"today": today.build, "foods": foods.build, "supps": supps.build, "garden": garden.build,
                   "profile": profile.build}[self.view]
        self.body.controls = builder(self)
        self.page.update()

    # ---------- feedback ----------
    def toast(self, msg: str) -> None:
        self.page.show_dialog(ft.SnackBar(content=ft.Text(msg), duration=2500, behavior=ft.SnackBarBehavior.FLOATING))

    def confirm(self, title: str, text: str, on_yes, yes_label: str = "Delete") -> None:
        def yes(_):
            self.page.pop_dialog()
            on_yes()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text(title), content=ft.Text(text),
            actions=[ft.TextButton("Cancel", on_click=lambda _: self.page.pop_dialog()),
                     ft.FilledButton(yes_label, on_click=yes)]))
