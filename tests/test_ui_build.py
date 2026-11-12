"""Smoke test: every screen builds against a real database without touching a live Flet session."""
from datetime import date

import flet as ft
import pytest

from nutritrack.core.foods import FOODS
from nutritrack.core.nutrition import Profile, scale_nutrients
from nutritrack.core.supplements import SUPP_TEMPLATES
from nutritrack.service import Service, today_key
from nutritrack.store import Store
from nutritrack.ui import add_food, foods, garden, profile, supps, today


class FakePage:
    """Records what the UI asks the page to do."""
    def __init__(self):
        self.dialogs = []
    def update(self, *a): pass
    def show_dialog(self, d): self.dialogs.append(d)
    def pop_dialog(self): self.dialogs.pop() if self.dialogs else None


class FakeApp:
    def __init__(self, store):
        self.page, self.store, self.svc = FakePage(), store, Service(store)
        self.date, self.view, self.rendered = today_key(), "today", 0
    def render(self): self.rendered += 1
    def go(self, view, date=None): self.view = view
    def toast(self, msg): self.last_toast = msg
    def confirm(self, title, text, on_yes, yes_label="Delete"): on_yes()


@pytest.fixture
def app(tmp_path):
    st = Store(tmp_path / "ui.db")
    st.save_profile(Profile(training_type="hybrid", training_load="high"))
    f = FOODS[0]
    st.add_entry(today_key(), "lunch", f.name, scale_nutrients(f.per100, 100), food_id=f.id, grams=100, amount_label="100 g")
    st.save_supplement(SUPP_TEMPLATES[0].make())
    return FakeApp(st)


@pytest.mark.parametrize("module", [today, foods, profile, supps, garden])
def test_screen_builds(app, module):
    controls = module.build(app)
    assert controls and all(isinstance(c, ft.Control) for c in controls)


def test_onboarding_builds_without_profile(tmp_path):
    a = FakeApp(Store(tmp_path / "empty.db"))
    assert profile.build(a)


def test_add_food_sheet_opens_and_adds(app):
    add_food.open_sheet(app, "breakfast")
    sheet = app.page.dialogs[-1]
    assert isinstance(sheet, ft.BottomSheet)
