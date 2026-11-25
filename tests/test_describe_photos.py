"""Typed logging ("2 eggs and toast") and meal photos saved to log later."""
import io

import pytest

from nutritrack.core.describe import parse, split_items
from nutritrack.core.foods import FOODS


@pytest.mark.parametrize("text,name,grams", [
    ("2 eggs", "Egg, whole", 100),
    ("2 slices of toast", "Whole wheat bread", 64),
    ("a banana", "Banana", 118),
    ("150g chicken", "Chicken breast, cooked", 150),
    ("1 cup rice", "White rice, cooked", 158),
    ("1 tbsp peanut butter", "Peanut butter", 16),
    ("half an avocado", "Avocado", 68),
    ("an avocado", "Avocado", 136),
    ("1 1/2 cups milk", "Milk, 2%", 366),
    ("1½ cups greek yogurt", "Greek yogurt, plain nonfat", 367.5),
    ("3 oz salmon", "Salmon, Atlantic, cooked", 85.1),
    ("200ml oj", "Orange juice", 200),
    ("a couple of eggs", "Egg, whole", 100),
    ("2 scoops whey", "Whey protein powder (generic, check label)", 60),
])
def test_parse_amounts_and_foods(text, name, grams):
    [p] = parse(text, FOODS)
    assert p.food is not None and p.food.name == name and p.grams == pytest.approx(grams, abs=0.2)


def test_split_and_unknown_items():
    assert split_items("2 eggs, toast and a banana + coffee") == ["2 eggs", "toast", "a banana", "coffee"]
    items = parse("pizza and 2 eggs", FOODS)
    assert items[0].food is None and items[1].food.name == "Egg, whole"


def test_photo_queue_roundtrip(tmp_path):
    from PIL import Image

    from nutritrack.service import Service
    from nutritrack.store import Store
    svc = Service(Store(tmp_path / "p.db"))
    buf = io.BytesIO()
    Image.new("RGB", (1200, 900), "orange").save(buf, "JPEG")
    ph = svc.add_photo("2026-11-15", "lunch", buf.getvalue())
    assert svc.photos("2026-11-15", "lunch")[0]["id"] == ph["id"] and not svc.photos("2026-11-15", "dinner")
    assert len(ph["thumb"]) < 40_000  # a small thumbnail, not the full photo
    svc.remove_photo(ph["id"])
    assert svc.photos("2026-11-15") == []


def test_today_and_add_food_build_with_a_photo(tmp_path):
    from PIL import Image
    from test_ui_build import FakeApp

    from nutritrack.core.nutrition import Profile
    from nutritrack.service import today_key
    from nutritrack.store import Store
    from nutritrack.ui import add_food, today
    st = Store(tmp_path / "t.db")
    st.save_profile(Profile())
    app = FakeApp(st)
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "green").save(buf, "PNG")
    ph = app.svc.add_photo(today_key(), "dinner", buf.getvalue())
    assert today.build(app)
    add_food.open_sheet(app, "dinner", photo=ph)
    assert app.page.dialogs


def test_unreadable_photo_still_saves_a_reminder(tmp_path):
    from nutritrack.service import Service
    from nutritrack.store import Store
    svc = Service(Store(tmp_path / "h.db"))
    ph = svc.add_photo("2026-11-15", "lunch", b"\x00\x00\x00 ftypheic not really an image")
    assert ph["thumb"] == "" and svc.photos("2026-11-15", "lunch")


def test_tidy_label_for_older_saved_foods():
    from nutritrack.core.foods import tidy_label
    assert tidy_label("150.0g") == "150 g" and tidy_label("12.5 ml") == "12.5 ml"
    assert tidy_label("1 cup (148 g)") == "1 cup (148 g)"
