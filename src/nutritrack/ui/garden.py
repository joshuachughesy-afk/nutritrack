"""Placeholder until Stage B of the Python rebuild."""
from __future__ import annotations

import flet as ft

from . import theme as th


def build(app) -> list[ft.Control]:
    title = {"supps": "Supplements", "garden": "Your garden"}["garden"]
    return [ft.Text(title, size=22, weight=ft.FontWeight.W_700),
            th.card(th.muted("Being rebuilt in Python — coming in Stage B. The logic is already ported and tested.", 14))]
