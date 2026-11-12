"""Tree drawings as SVG (stage 0–5, per species). Flet renders the bytes with ft.Image(src=...)."""
from __future__ import annotations

from .garden import SPECIES


def tree_svg(stage: int, species_key: str = "oak", muted: bool = False) -> bytes:
    sp = SPECIES.get(species_key, SPECIES["oak"])
    c1, c2 = sp.canopy
    ground = f'<ellipse cx="60" cy="108" rx="{16 + stage * 6}" ry="5" fill="#8a6a4a" opacity=".35"/>'
    if stage == 0:
        body = '<path d="M44 108 q16 -14 32 0z" fill="#9b7653"/><ellipse cx="60" cy="101" rx="5" ry="3.5" fill="#6b4a2e"/>'
    elif stage == 1:
        body = ('<path d="M60 108 V88" stroke="#4f8a3c" stroke-width="3" stroke-linecap="round"/>'
                '<path d="M60 92 q-12 -2 -14 -12 q11 0 14 12z" fill="#6fb34f"/>'
                '<path d="M60 89 q11 -3 14 -13 q-12 1 -14 13z" fill="#5aa040"/>')
    else:
        h = [0, 0, 34, 48, 60, 64][stage]   # trunk height
        r = [0, 0, 16, 24, 31, 34][stage]   # canopy radius
        top = 108 - h
        tw = max(3.0, stage * 1.6)
        trunk = (f'<path d="M{60 - tw} 108 L{60 - tw * 0.55} {top + r * 0.3} L{60 + tw * 0.55} {top + r * 0.3} '
                 f'L{60 + tw} 108z" fill="{sp.trunk}"/>')
        marks = ""
        if species_key == "birch":
            marks = "".join(f'<rect x="{60 - tw * 0.7}" y="{108 - h * f}" width="{tw * 0.9}" height="2" fill="#3a3a3a" '
                            f'opacity=".55"/>' for f in (0.3, 0.55, 0.8))
        if sp.shape == "cone":
            canopy = ""
            for i in range(3):
                w, y = r * (1.15 - i * 0.28), top - i * r * 0.55 + r * 0.6
                canopy += f'<path d="M{60 - w} {y} L60 {y - r * 1.1} L{60 + w} {y}z" fill="url(#g)"/>'
        else:
            ry = r * 1.2 if sp.shape == "oval" else r
            canopy = (f'<ellipse cx="60" cy="{top}" rx="{r}" ry="{ry}" fill="url(#g)"/>'
                      f'<ellipse cx="{60 - r * 0.55}" cy="{top + r * 0.35}" rx="{r * 0.55}" ry="{r * 0.5}" fill="{c2}"/>'
                      f'<ellipse cx="{60 + r * 0.6}" cy="{top + r * 0.3}" rx="{r * 0.5}" ry="{r * 0.45}" fill="{c2}"/>')
        deco = ""
        if stage == 5:  # blossoms, or red fruit on species without blossoms
            bloom = sp.bloom or "#e94b4b"
            spots = [(-0.5, -0.3), (0.35, -0.5), (0.1, 0.15), (-0.15, -0.65), (0.6, 0.1), (-0.6, 0.25), (0.3, 0.45)]
            deco = "".join(f'<circle cx="{60 + dx * r}" cy="{top + dy * r}" r="{2.6 if sp.bloom else 3}" fill="{bloom}"/>'
                           for dx, dy in spots)
        body = trunk + marks + canopy + deco
    style = ' opacity="0.4"' if muted else ""
    grad = (f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{"#bdbdbd" if muted else c1}"/>'
            f'<stop offset="1" stop-color="{"#9e9e9e" if muted else c2}"/></linearGradient></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 116"{style}>{grad}{ground}{body}</svg>').encode()
