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

        class _N:
            can_schedule = False
            async def request_permission(self): return False
            async def test(self): pass
            def mark_from_payload(self, p): pass
        self.notifier = _N()
    def render(self): self.rendered += 1
    def go(self, view, date=None): self.view = view
    dark = False
    visible = True
    def toast(self, msg): self.last_toast = msg
    def celebrate(self, msg, big=False): self.last_toast = msg
    def set_theme_mode(self, mode): self.theme_mode = mode
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


def test_supplement_editor_builds(app):
    supps._new(app, supps.SUPP_TEMPLATES[2])
    assert app.supp_edit == "new" and supps.build(app)
    app.supp_edit = app.store.supplements()[0].id
    assert supps.build(app)


def test_today_with_history_and_past_day(app):
    from nutritrack.service import shift
    app.store.add_water(app.date, 500)
    app.date = shift(app.date, -1)
    assert today.build(app)


def test_onboarding_builds_without_profile(tmp_path):
    a = FakeApp(Store(tmp_path / "empty.db"))
    assert profile.build(a)


def test_progress_trends_tab_builds(app):
    from datetime import timedelta
    t = date.today()
    for i in range(20):
        app.svc.log_weight((t - timedelta(days=i)).isoformat(), 84 - i * 0.05)
    for n in (7, 30, 90):
        app.progress_tab, app.trend_days = "trends", n
        assert garden.build(app)


def test_edit_sheet_and_forest(app):
    e = app.store.entries(app.date)[0]
    add_food.open_sheet(app, e["meal"], edit=e)
    assert isinstance(app.page.dialogs[-1], ft.BottomSheet)
    qid = app.store.add_entry(app.date, "dinner", "Restaurant", {"kcal": 700}, amount_label="quick add")
    add_food.open_sheet(app, "dinner", edit=app.store.entry(qid))
    from nutritrack.ui.forest_view import ForestView
    assert ForestView(app).control


def test_add_food_sheet_opens_and_adds(app):
    add_food.open_sheet(app, "breakfast")
    sheet = app.page.dialogs[-1]
    assert isinstance(sheet, ft.BottomSheet)


def test_no_expanded_children_in_wrapping_rows():
    """Flutter can't expand a child inside a wrapping Row (it renders an error box), so catch it statically."""
    import ast
    from pathlib import Path
    bad = []
    for p in (Path(__file__).parent.parent / "src" / "nutritrack" / "ui").glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "Row":
                wrap = any(k.arg == "wrap" and getattr(k.value, "value", None) is True for k in node.keywords)
                if wrap and node.args and isinstance(node.args[0], ast.List):
                    bad += [f"{p.name}:{node.lineno}" for el in node.args[0].elts
                            if isinstance(el, ast.Call) and any(k.arg == "expand" for k in el.keywords)]
    assert not bad, bad
