"""First run: a short, friendly setup instead of the full settings form.

Welcome → what you train for → your week → about you → your goal → your fuel plan (the reveal) → plant your first
seed and choose reminders. Answers live in app.ui.onboarding until the last step saves the profile.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ..core.nutrition import GOALS, Profile, day_targets, in_to_cm, lb_to_kg
from ..core.training import LOADS, TRAINING
from . import components as cx
from . import motion
from . import theme as th
from .tree_view import TreeView

if TYPE_CHECKING:
    from .app import App

STEPS = ["welcome", "training", "week", "you", "goal", "plan", "seed"]

TRAINING_ICONS = {"hybrid": ft.Icons.DIRECTIONS_RUN, "strength": ft.Icons.FITNESS_CENTER, "hypertrophy": ft.Icons.SPORTS_GYMNASTICS,
                  "hiit": ft.Icons.BOLT, "endurance": ft.Icons.DIRECTIONS_BIKE, "ultra": ft.Icons.TERRAIN,
                  "team": ft.Icons.SPORTS_SOCCER, "combat": ft.Icons.SPORTS_MMA, "general": ft.Icons.FAVORITE_BORDER,
                  "low": ft.Icons.SELF_IMPROVEMENT}
TRAINING_ORDER = ["hybrid", "strength", "endurance", "hiit", "hypertrophy", "team", "combat", "ultra", "general", "low"]
LOAD_TO_ACTIVITY = {"low": "light", "moderate": "moderate", "high": "very", "peak": "extra"}
GOAL_CARDS = [("lose", "Lose fat", "About 0.5 kg a week", ft.Icons.TRENDING_DOWN),
              ("lose_slow", "Lose slowly", "About 0.25 kg a week, easier on training", ft.Icons.SOUTH_EAST),
              ("maintain", "Maintain", "Fuel performance at your current weight", ft.Icons.TRENDING_FLAT),
              ("gain_slow", "Build", "Lean gain, about 0.25 kg a week", ft.Icons.TRENDING_UP)]


def _answers(app: "App") -> dict:
    a = app.ui.onboarding
    a.setdefault("step", 0)
    return a


def _go(app: "App", step: int) -> None:
    motion.haptic("select")
    _answers(app)["step"] = max(0, min(len(STEPS) - 1, step))
    app.render()


def _profile(a: dict) -> Profile:
    return Profile(sex=a.get("sex", "female"), age=a.get("age", 30), height_cm=a.get("height_cm", 170),
                   weight_kg=a.get("weight_kg", 70), activity=LOAD_TO_ACTIVITY.get(a.get("load", "moderate"), "moderate"),
                   goal=a.get("goal", "maintain"), training_type=a.get("training", "general"),
                   training_load=a.get("load", "moderate"), training_days=tuple(sorted(a.get("days", {1, 2, 4, 5, 6}))),
                   carb_cycling=a.get("cycling", True))


def build(app: "App") -> list[ft.Control]:
    a = _answers(app)
    step = STEPS[a["step"]]
    body = {"welcome": _welcome, "training": _training, "week": _week, "you": _you, "goal": _goal, "plan": _plan,
            "seed": _seed}[step](app, a)
    if step == "welcome":
        return body
    dots = ft.Row([ft.Container(width=22 if i == a["step"] else 8, height=8, border_radius=4,
                                bgcolor=th.ACCENT if i <= a["step"] else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                animate=ft.Animation(250, ft.AnimationCurve.EASE_OUT))
                   for i in range(1, len(STEPS))], spacing=6)
    top = ft.Row([ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, tooltip="Back", on_click=lambda _: _go(app, a["step"] - 1)),
                  ft.Container(dots, expand=True, alignment=ft.Alignment.CENTER), ft.Container(width=48)])
    return [top, *body]


def _next_button(text: str, on_click, enabled: bool = True) -> ft.Control:
    return ft.Container(ft.Row([ft.FilledButton(text, icon=ft.Icons.ARROW_FORWARD_ROUNDED, on_click=on_click,
                                                disabled=not enabled, expand=True,
                                                style=ft.ButtonStyle(padding=ft.Padding.symmetric(vertical=16),
                                                                     shape=ft.RoundedRectangleBorder(radius=16)))]),
                        padding=ft.Padding.only(top=8))


def _q(title: str, sub: str) -> ft.Control:
    return ft.Column([ft.Text(title, size=th.T.TITLE + 2, font_family=th.FONT_BOLD), th.muted(sub, th.T.BODY)], spacing=4)


def _option(icon, title: str, sub: str, selected: bool, on_click) -> ft.Control:
    return ft.Container(ft.Row([
        ft.Container(ft.Icon(icon, color=ft.Colors.ON_PRIMARY if selected else th.ACCENT, size=22), padding=10,
                     border_radius=th.R.MD, bgcolor=th.ACCENT if selected else ft.Colors.with_opacity(0.12, th.ACCENT)),
        ft.Column([ft.Text(title, size=th.T.BODY, font_family=th.FONT_SEMI),
                   th.muted(sub, th.T.CAPTION, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)], spacing=1, expand=True),
        ft.Icon(ft.Icons.CHECK_CIRCLE if selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=th.ACCENT if selected else ft.Colors.OUTLINE_VARIANT),
    ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=12, border_radius=th.R.LG - 4, ink=True, on_click=on_click,
        bgcolor=ft.Colors.with_opacity(0.08, th.ACCENT) if selected else ft.Colors.SURFACE_CONTAINER_LOWEST,
        border=ft.Border.all(2 if selected else 1, th.ACCENT if selected else ft.Colors.OUTLINE_VARIANT))


# ---------- steps ----------
def _welcome(app: "App", a: dict) -> list[ft.Control]:
    tree = TreeView("oak", 4, size=240, season=app.svc.season())
    sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])
    points = [(ft.Icons.BOLT, "Fuel tuned to how you train", "Carbs, protein and fat set for hybrid, strength or endurance."),
              (ft.Icons.SPA_OUTLINED, "Every vitamin and mineral", "Food and supplements together, so you see real gaps."),
              (ft.Icons.PARK_OUTLINED, "Grow a forest", "Every good day grows a tree. Keep your streak, watch the valley fill."),
              (ft.Icons.LOCK_OUTLINE, "Private by design", "No account, no ads. Your data stays on this device.")]
    return [
        ft.Row([ft.Container(tree.control, gradient=sky, alignment=ft.Alignment.CENTER, expand=True,
                             border_radius=th.R.LG, padding=ft.Padding.only(top=12, bottom=4))]),
        ft.Text("Grow a forest by fuelling well.", size=th.T.DISPLAY, font_family=th.FONT_BOLD),
        th.muted("Calories, macros and every nutrient, tuned to how you train. Takes about a minute to set up.", th.T.BODY),
        *[ft.Row([ft.Icon(ic, color=th.ACCENT, size=22),
                  ft.Column([ft.Text(t, size=th.T.BODY, font_family=th.FONT_SEMI), th.muted(s, th.T.LABEL)], spacing=0,
                            expand=True)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
          for ic, t, s in points],
        _next_button("Let's plant your first seed", lambda _: _go(app, 1)),
    ]


def _training(app: "App", a: dict) -> list[ft.Control]:
    def pick(key: str) -> None:
        a["training"] = key
        a.setdefault("cycling", TRAINING[key].carb_first)
        _go(app, 2)

    opts = [_option(TRAINING_ICONS.get(k, ft.Icons.FITNESS_CENTER), TRAINING[k].name, TRAINING[k].examples,
                    a.get("training") == k, lambda _, k=k: pick(k)) for k in TRAINING_ORDER if k in TRAINING]
    return [_q("What are you training for?", "This sets how your food is split between carbs, protein and fat."), *opts]


def _week(app: "App", a: dict) -> list[ft.Control]:
    tr = TRAINING[a.get("training", "general")]
    a.setdefault("load", "moderate")
    a.setdefault("days", {1, 2, 4, 5, 6})
    load_row = ft.Row(wrap=True, spacing=8, run_spacing=8)

    def set_load(k: str) -> None:
        a["load"] = k
        for c in load_row.controls:
            c.selected = c.data == k
        load_row.update()

    load_row.controls = [ft.Chip(label=ft.Text(v["detail"].replace("/week", " a week"), size=th.T.LABEL), data=k,
                                 selected=k == a["load"], show_checkmark=False, on_select=lambda _, k=k: set_load(k))
                         for k, v in LOADS.items()]
    days = cx.day_chips(a["days"], lambda s: a.__setitem__("days", s))
    cycling = cx.toggle_row("More carbs on training days", a.get("cycling", tr.carb_first),
                            lambda v: a.__setitem__("cycling", v),
                            sub="Fewer on rest days, same weekly total. Recommended for "
                                + ("your training." if tr.carb_first else "endurance and hybrid athletes."))
    return [_q("How much do you train?", "Roughly. You can change this any time."),
            th.card(th.label("Hours of training"), load_row,
                    th.label("Usual training days"), days,
                    th.muted("You can switch any day between training and rest on the Today screen.", th.T.CAPTION),
                    ft.Divider(height=4), cycling, spacing=12),
            _next_button("Next", lambda _: _go(app, 3))]


def _you(app: "App", a: dict) -> list[ft.Control]:
    imperial = a.get("units", app.store.units) == "imperial"

    def field(label, value, suffix, hint):
        return th.num_field(label, value, suffix=suffix, expand=True, hint_text=hint)

    w = a.get("weight_kg")
    h = a.get("height_cm")
    age = field("Age", a.get("age"), "years", "e.g. 30")
    weight = field("Weight", (round(w * 2.20462, 1) if imperial else round(w, 1)) if w else None, "lb" if imperial else "kg",
                   "e.g. 165" if imperial else "e.g. 75")
    height = field("Height", round(h) if h and not imperial else None, "cm", "e.g. 175")
    feet = field("Height", int(h / 2.54 // 12) if h and imperial else None, "ft", "5")
    inches = field("", round(h / 2.54 % 12) if h and imperial else None, "in", "9")
    sex_row = ft.Row(spacing=8)

    def set_sex(v: str) -> None:
        a["sex"] = v
        for c in sex_row.controls:
            c.selected = c.data == v
        sex_row.update()

    sex_row.controls = [ft.Chip(label=ft.Text(lbl, size=th.T.BODY - 1), data=v, selected=a.get("sex") == v, show_checkmark=False,
                                on_select=lambda _, v=v: set_sex(v)) for v, lbl in (("female", "Female"), ("male", "Male"))]
    err = ft.Text("", color=th.ink(th.STATUS_COLORS["over"]), size=th.T.LABEL, visible=False)

    def units(v: str) -> None:
        a["units"] = v
        app.render()

    def nxt(_):
        imp = a.get("units", app.store.units) == "imperial"
        ag = int(th.parse_num(age.value))
        wkg = lb_to_kg(th.parse_num(weight.value)) if imp else th.parse_num(weight.value)
        hcm = in_to_cm(th.parse_num(feet.value) * 12 + th.parse_num(inches.value)) if imp else th.parse_num(height.value)
        problems = []
        age.error = "18–100" if not 18 <= ag <= 100 else None
        weight.error = "Check weight" if not 30 <= wkg <= 300 else None
        (feet if imp else height).error = "Check height" if not 120 <= hcm <= 230 else None
        if "sex" not in a:
            problems.append("Choose female or male. It changes your burn rate and vitamin needs.")
        if age.error or weight.error or (feet if imp else height).error:
            problems.append("Ages 18–100, weight 30–300 kg, height 120–230 cm.")
        err.value, err.visible = " ".join(problems), bool(problems)
        if problems:
            app.page.update()
            return
        a.update(age=ag, weight_kg=wkg, height_cm=hcm)
        _go(app, 4)

    unit_tabs = cx.tabs([("metric", "Metric"), ("imperial", "Imperial")], "imperial" if imperial else "metric", units)
    return [_q("About you", "Used to estimate how much energy you burn and the vitamins you need."),
            th.card(unit_tabs, th.label("Sex"), sex_row, ft.Row([age]),
                    ft.Row([weight]), ft.Row([feet, inches] if imperial else [height], spacing=10), err, spacing=12),
            _next_button("Next", nxt)]


def _goal(app: "App", a: dict) -> list[ft.Control]:
    def pick(k: str) -> None:
        a["goal"] = k
        _go(app, 5)

    return [_q("What's your goal?", "You can change it later."),
            *[_option(ic, t, s, a.get("goal") == k, lambda _, k=k: pick(k)) for k, t, s, ic in GOAL_CARDS if k in GOALS]]


def _plan(app: "App", a: dict) -> list[ft.Control]:
    p = _profile(a)
    tt, rt = day_targets(p, True), day_targets(p, False)
    tr = tt.training
    imperial = a.get("units", app.store.units) == "imperial"

    def water(ml):
        return f"{ml / 29.5735:.0f} oz" if imperial else f"{ml / 1000:.1f} L"

    def day_col(label, icon, t):
        return ft.Container(ft.Column([
            th.icon_text(icon, label, th.ACCENT, bold=True),
            th.display(f"{t.kcal:,}", th.T.TITLE + 4), th.muted("kcal", th.T.CAPTION),
            *[ft.Row([th.dot(th.MACRO_COLORS[k]), ft.Text(f"{getattr(t, k)} g {k}", size=th.T.LABEL)], spacing=6)
              for k in (["carbs", "protein", "fat"] if tr.carb_first else ["protein", "carbs", "fat"])],
            ft.Row([ft.Icon(ft.Icons.WATER_DROP, size=14, color=th.MACRO_COLORS["water"]),
                    ft.Text(f"{water(t.water_ml)} water", size=th.T.LABEL)], spacing=6),
        ], spacing=4), expand=True, padding=14, border_radius=th.R.MD, bgcolor=ft.Colors.SURFACE_CONTAINER)

    cols = [day_col("Training day", ft.Icons.FITNESS_CENTER, tt)]
    if tt.cycling or tt.kcal != rt.kcal:
        cols.append(day_col("Rest day", ft.Icons.SELF_IMPROVEMENT, rt))
    why = (f"{tr.name}: carb-forward, to refill what your sessions burn." if tr.carb_first
           else f"{tr.name}: {tr.emphasis.lower()} split for your training.")
    notes = [cx.note(n, "warn") for n in tt.notes]
    return [_q("Your fuel plan", "Worked out from your answers. It adapts as you log and weigh in."),
            th.card(ft.Row(cols, spacing=10, vertical_alignment=ft.CrossAxisAlignment.START),
                    cx.note(why, "info", icon=ft.Icons.BOLT), *notes,
                    th.muted("Plus daily targets for 14 vitamins and minerals.", th.T.CAPTION), spacing=12),
            _next_button("Looks good", lambda _: _go(app, 6)),
            ft.Row([ft.TextButton("Change my answers", on_click=lambda _: _go(app, 1))], alignment=ft.MainAxisAlignment.CENTER)]


def _seed(app: "App", a: dict) -> list[ft.Control]:
    a.setdefault("reminders", True)
    tree = TreeView("oak", 1, size=200, season=app.svc.season())
    sky = ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER, colors=th.SKY[app.dark])

    async def finish(_):
        p = _profile(a)
        app.store.save_profile(p)
        app.store.set("units", a.get("units", app.store.units))
        if a.get("reminders"):
            rs = app.store.reminders()
            app.store.set("reminders", {**rs, "enabled": True})
            try:
                await app.notifier.request_permission()
            except Exception:
                from ..diagnostics import log
                log.exception("notification permission request failed")
        app.ui.onboarding = {}
        app.go("today")
        app.celebrate("🌱 Your first seed is planted. Log a meal to help it grow.")

    return [_q("Plant your first seed", "Each day you fuel well, your tree grows. Good days in a row build a streak."),
            ft.Row([ft.Container(tree.control, gradient=sky, alignment=ft.Alignment.CENTER, expand=True,
                                 border_radius=th.R.LG, padding=8)]),
            th.card(cx.toggle_row("Keep me on pace", a["reminders"], lambda v: a.__setitem__("reminders", v),
                                  sub="A nudge when you fall behind on food or water, and supplement reminders. "
                                      "Only when it helps."), spacing=8),
            _next_button("Plant it", finish)]
