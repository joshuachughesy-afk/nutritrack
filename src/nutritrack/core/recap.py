"""Weekly recap: "your week in the forest" — a short, shareable look back at the last full week (Monday–Sunday)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .garden import TREE_DAY, stage_for
from .nutrition import MICRO_BY_KEY, MICROS
from .trends import DayRow


@dataclass
class Recap:
    start: str                      # Monday (ISO date)
    end: str                        # Sunday
    days_logged: int
    full_trees: int
    trees: list[tuple[str, int | None]]  # (date, stage or None) for each of the 7 days
    avg_kcal_pct: float | None      # average calories as a share of target, logged days only
    avg_protein_pct: float | None
    avg_water_pct: float | None
    best_day: str | None            # date with the highest score
    best_score: int | None
    improved: tuple[str, float] | None  # (micro label, percentage-point gain vs the week before)
    headline: str = ""
    lines: list[str] = field(default_factory=list)


def last_full_week(today: date) -> tuple[date, date]:
    """Monday and Sunday of the most recent week that has ended (on a Sunday, that's the week ending today)."""
    end = today - timedelta(days=(today.weekday() + 1) % 7)  # most recent Sunday, or today if Sunday
    return end - timedelta(days=6), end


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_recap(week: list[DayRow], previous: list[DayRow]) -> Recap:
    logged = [r for r in week if r.logged]
    scored = [r for r in week if r.score is not None]
    best = max(scored, key=lambda r: r.score) if scored else None
    improved = None
    prev_logged = [r for r in previous if r.logged]
    if logged and prev_logged:
        gains = []
        for m in MICROS:
            if m.limit:
                continue
            now = _avg([min(r.micro_pct.get(m.key, 0), 1.5) for r in logged]) or 0
            before = _avg([min(r.micro_pct.get(m.key, 0), 1.5) for r in prev_logged]) or 0
            gains.append((now - before, m.key))
        gain, key = max(gains)
        if gain >= 0.1:
            improved = (MICRO_BY_KEY[key].label, gain * 100)
    rc = Recap(
        start=week[0].date, end=week[-1].date, days_logged=len(logged),
        full_trees=sum(1 for r in week if r.score is not None and r.score >= TREE_DAY),
        trees=[(r.date, stage_for(r.score) if r.score is not None else None) for r in week],
        avg_kcal_pct=_avg([r.kcal / r.target_kcal for r in logged if r.target_kcal]),
        avg_protein_pct=_avg([r.protein / r.target_protein for r in logged if r.target_protein]),
        avg_water_pct=_avg([r.water_ml / r.target_water for r in logged if r.target_water]),
        best_day=best.date if best else None, best_score=best.score if best else None, improved=improved,
    )
    rc.headline, rc.lines = _words(rc)
    return rc


def _words(rc: Recap) -> tuple[str, list[str]]:
    """Plain, encouraging sentences. Never scolding: a quiet week is just a quiet week."""
    if rc.days_logged == 0:
        return "A quiet week in the forest", ["No days logged. Your forest is still here whenever you're ready."]
    if rc.full_trees >= 6:
        head = f"{rc.full_trees} full trees. An outstanding week"
    elif rc.full_trees >= 3:
        head = f"{rc.full_trees} full trees this week"
    elif rc.full_trees:
        head = f"{rc.full_trees} full tree{'s' if rc.full_trees > 1 else ''} and {rc.days_logged} days logged"
    else:
        head = f"{rc.days_logged} day{'s' if rc.days_logged > 1 else ''} logged. A start"
    lines = []
    if rc.avg_protein_pct is not None:
        lines.append(f"Protein averaged {round(rc.avg_protein_pct * 100)}% of your target.")
    if rc.avg_kcal_pct is not None:
        diff = rc.avg_kcal_pct - 1
        lines.append("Calories landed right around your target." if abs(diff) <= 0.07 else
                     f"Calories averaged {round(rc.avg_kcal_pct * 100)}% of your target.")
    if rc.avg_water_pct is not None:
        lines.append(f"Water: {round(min(rc.avg_water_pct, 1.5) * 100)}% of your goal on average.")
    if rc.best_day:
        lines.append(f"Best day: {date.fromisoformat(rc.best_day).strftime('%A')} ({rc.best_score} points).")
    if rc.improved:
        lines.append(f"Most improved: {rc.improved[0]}, up {round(rc.improved[1])} points on the week before.")
    return head, lines


def share_png(rc: Recap, species_for, season_for, app_name: str = "Sapling", tagline: str = "") -> bytes:
    """A 1080×1350 image of the week to share: seven trees, the headline and the highlights. Needs Pillow."""
    import io
    from pathlib import Path

    from PIL import Image, ImageDraw, ImageFont

    from . import render3d

    W, H = 1080, 1350
    img = Image.new("RGB", (W, H))
    top, bottom = (215, 239, 255), (233, 247, 230)
    px = img.load()
    for y in range(H):  # sky-to-meadow gradient
        t = y / H
        col = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(W):
            px[x, y] = col
    d = ImageDraw.Draw(img)
    fonts = Path(__file__).resolve().parents[2] / "assets" / "fonts"

    def font(weight: str, size: int):
        try:
            return ImageFont.truetype(str(fonts / f"PlusJakartaSans-{weight}.ttf"), size)
        except OSError:
            return ImageFont.load_default()

    ink, soft, green = (22, 32, 26), (93, 107, 99), (31, 122, 77)
    d.text((80, 90), app_name.upper(), font=font("ExtraBold", 40), fill=green)
    d.text((80, 150), "My week in the forest", font=font("ExtraBold", 72), fill=ink)
    span = f"{date.fromisoformat(rc.start).strftime('%d %b')} – {date.fromisoformat(rc.end).strftime('%d %b %Y')}"
    d.text((80, 245), span, font=font("SemiBold", 36), fill=soft)
    # seven trees, one per day
    size, gap = 132, 9
    x0 = (W - (7 * size + 6 * gap)) // 2
    for i, (day, stage) in enumerate(rc.trees):
        x = x0 + i * (size + gap)
        if stage is not None:
            tree = Image.open(io.BytesIO(render3d.tree_png(species_for(day), stage, 30, size, season_for(day)))).convert("RGBA")
            img.paste(tree, (x, 330), tree)
        else:
            d.ellipse((x + size // 2 - 10, 330 + size - 40, x + size // 2 + 10, 330 + size - 20), fill=(205, 212, 200))
        letter = date.fromisoformat(day).strftime("%a")[0]
        tw = d.textlength(letter, font=font("SemiBold", 32))
        d.text((x + (size - tw) / 2, 330 + size + 10), letter, font=font("SemiBold", 32), fill=soft)

    def wrap(text: str, f, width: int) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if d.textlength(trial, font=f) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        return lines + ([cur] if cur else [])

    y = 560
    for line in wrap(rc.headline, font("ExtraBold", 58), W - 160):
        d.text((80, y), line, font=font("ExtraBold", 58), fill=ink)
        y += 72
    y += 20
    body = font("Regular", 38)
    for text in rc.lines:
        for i, line in enumerate(wrap(text, body, W - 200)):
            if i == 0:
                d.ellipse((84, y + 16, 100, y + 32), fill=green)
            d.text((120, y), line, font=body, fill=ink)
            y += 52
        y += 12
    if tagline:
        d.text((80, H - 110), tagline, font=font("SemiBold", 30), fill=soft)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
