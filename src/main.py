"""NutriTrack entry point.

Run:   flet run src/main.py            (desktop window)
       flet run --web src/main.py      (browser)
Build: flet build apk | ipa | macos | windows | linux
"""
import os

import flet as ft

from nutritrack.ui.app import App


def main(page: ft.Page) -> None:
    App(page)


if __name__ == "__main__":
    if os.getenv("NUTRITRACK_WEB"):  # headless/dev: serve in a browser on a fixed port
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=int(os.getenv("PORT", "8551")), no_cdn=True, assets_dir="assets")
    else:
        ft.run(main, assets_dir="assets")
