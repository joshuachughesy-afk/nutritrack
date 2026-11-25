"""Generate Sapling's app icons, splash screens and in-app logo from code (Pillow only).

    python tools/make_icons.py            # writes src/assets/icon*.png, splash*.png, favicon.png, logo.png

Design: a fresh two-leaf sprout rising in front of a warm morning sun, on a deep forest-green field, with a faint
ring around it (a nod to the calorie ring). Drawn at 4x and scaled down, so edges stay smooth at every size.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "src" / "assets"
SS = 4  # supersampling


def _hex(c: str, a: int = 255) -> tuple[int, int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), a


def _vgradient(w: int, h: int, top: str, bottom: str, mid: str | None = None) -> Image.Image:
    g = Image.new("RGBA", (1, h))
    t0, b0 = _hex(top), _hex(bottom)
    m0 = _hex(mid) if mid else None
    for y in range(h):
        t = y / (h - 1)
        if m0:
            a, b, u = (t0, m0, t * 2) if t < 0.5 else (m0, b0, (t - 0.5) * 2)
        else:
            a, b, u = t0, b0, t
        g.putpixel((0, y), tuple(int(a[i] * (1 - u) + b[i] * u) for i in range(4)))
    return g.resize((w, h))


def _radial(size: int, color: str, radius: float, cx: float, cy: float, strength: float = 1.0) -> Image.Image:
    """A soft glow: colour at the centre fading to transparent at `radius` (all in pixels)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r, g, b, _ = _hex(color)
    steps = 60
    for i in range(steps, 0, -1):
        rr = radius * i / steps
        a = int(255 * strength * (1 - i / steps) ** 1.6)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(r, g, b, a))
    return img.filter(ImageFilter.GaussianBlur(radius * 0.06))


def _leaf(size: int, base: tuple[float, float], angle: float, length: float, width: float, c1: str, c2: str,
          rib: str) -> Image.Image:
    """A leaf from `base`, pointing at `angle` (radians, 0 = right), filled with a gradient along its length."""
    pts = []
    n = 80
    ca, sa = math.cos(angle), math.sin(angle)
    for side in (1, -1):
        rng = range(n + 1) if side == 1 else range(n, -1, -1)
        for i in rng:
            t = i / n
            w = width * (math.sin(math.pi * t) ** 0.85) * (1 - 0.25 * t) * side
            x, y = t * length, w
            pts.append((base[0] + x * ca - y * sa, base[1] + x * sa + y * ca))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    # gradient along the leaf axis
    grad = Image.new("RGBA", (size, size))
    g1, g2 = _hex(c1), _hex(c2)
    gd = ImageDraw.Draw(grad)
    for k in range(64):
        t = k / 63
        col = tuple(int(g1[i] * (1 - t) + g2[i] * t) for i in range(4))
        x0 = base[0] + t * length * ca
        y0 = base[1] + t * length * sa
        r = length * 1.2 * (1 - t) + 4
        gd.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=col)
    leaf = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    leaf.paste(grad, (0, 0), mask)
    # midrib and a soft highlight along one edge
    rib_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(rib_layer).line([(base[0] + length * 0.08 * ca, base[1] + length * 0.08 * sa),
                                    (base[0] + length * 0.78 * ca, base[1] + length * 0.78 * sa)], fill=_hex(rib, 80),
                                   width=max(2, int(size * 0.004)))
    leaf = Image.alpha_composite(leaf, rib_layer)
    hl = Image.new("L", (size, size), 0)
    hp = [(base[0] + t * length * ca - (width * 0.55 * math.sin(math.pi * t)) * -sa,
           base[1] + t * length * sa - (width * 0.55 * math.sin(math.pi * t)) * ca) for t in [i / 40 for i in range(41)]]
    ImageDraw.Draw(hl).line(hp, fill=90, width=int(size * 0.012))
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(size * 0.006)), mask)
    leaf = Image.composite(Image.new("RGBA", (size, size), (255, 255, 255, 255)), leaf, hl) if False else \
        Image.alpha_composite(leaf, Image.merge("RGBA", (*[Image.new("L", (size, size), 255)] * 3, hl)))
    return leaf


def sprout(size: int, with_ground: bool = True) -> Image.Image:
    """The sprout alone on a transparent background (used by the icon, the splash and the in-app logo)."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stem_base = (s * 0.5, s * 0.80)
    stem_top = (s * 0.5, s * 0.47)
    # gently curved stem
    pts = [(stem_base[0] + math.sin(t * math.pi) * s * 0.018, stem_base[1] + (stem_top[1] - stem_base[1]) * t)
           for t in [i / 40 for i in range(41)]]
    d.line(pts, fill=_hex("#f4f1de"), width=int(s * 0.042), joint="curve")
    d.ellipse([stem_top[0] - s * 0.021, stem_top[1] - s * 0.021, stem_top[0] + s * 0.021, stem_top[1] + s * 0.021],
              fill=_hex("#f4f1de"))
    left = _leaf(s, (s * 0.49, s * 0.50), math.radians(200), s * 0.29, s * 0.105, "#8fe388", "#3db36b", "#1f7a4d")
    right = _leaf(s, (s * 0.51, s * 0.46), math.radians(-28), s * 0.34, s * 0.12, "#a8f08f", "#2fa864", "#1f7a4d")
    img = Image.alpha_composite(img, left)
    img = Image.alpha_composite(img, right)
    if with_ground:
        shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse([s * 0.30, s * 0.775, s * 0.70, s * 0.86], fill=_hex("#0b3d26", 150))
        img = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s * 0.01)), img)
        d = ImageDraw.Draw(img)
        d.chord([s * 0.33, s * 0.77, s * 0.67, s * 0.90], 180, 360, fill=_hex("#7a5232"))
        d.chord([s * 0.36, s * 0.775, s * 0.64, s * 0.86], 180, 360, fill=_hex("#946640"))
    return img


def icon(size: int = 1024, padding: float = 0.0) -> Image.Image:
    """Full-bleed square icon (iOS and stores mask the corners themselves; no transparency)."""
    s = size * SS
    bg = _vgradient(s, s, "#2e9e66", "#0b3d26", "#17663f")
    bg = Image.alpha_composite(bg, _radial(s, "#fff3c4", s * 0.36, s * 0.5, s * 0.52, 0.55))   # morning sun glow
    d = ImageDraw.Draw(bg)
    r = s * 0.17
    d.ellipse([s * 0.5 - r, s * 0.52 - r, s * 0.5 + r, s * 0.52 + r], fill=_hex("#ffe29a"))       # the sun
    ring = s * 0.385  # a progress ring, like the calorie ring: bright for three quarters, faint for the rest
    box = [s * 0.5 - ring, s * 0.52 - ring, s * 0.5 + ring, s * 0.52 + ring]
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))  # draw translucent strokes on a layer, then blend
    ld = ImageDraw.Draw(layer)
    ld.arc(box, 175, 270, fill=_hex("#c9f2d8", 55), width=int(s * 0.02))
    ld.arc(box, -90, 175, fill=_hex("#d9f7e4", 235), width=int(s * 0.02))
    bg = Image.alpha_composite(bg, layer)
    sp = sprout(int(s * (1 - padding)))
    off = int((s - sp.width) / 2)
    bg.alpha_composite(sp, (off, off + int(s * 0.01)))
    return bg.resize((size, size), Image.LANCZOS).convert("RGB")


def adaptive_foreground(size: int = 1024) -> Image.Image:
    """Android adaptive icon foreground: the sprout and sun inside the 66% safe zone, on transparency."""
    s = size * SS
    fg = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    fg = Image.alpha_composite(fg, _radial(s, "#ffd166", s * 0.28, s * 0.5, s * 0.52, 0.9))
    d = ImageDraw.Draw(fg)
    r = s * 0.115
    d.ellipse([s * 0.5 - r, s * 0.52 - r, s * 0.5 + r, s * 0.52 + r], fill=_hex("#ffe29a"))
    sp = sprout(int(s * 0.66))
    fg.alpha_composite(sp, (int(s * 0.17), int(s * 0.18)))
    return fg.resize((size, size), Image.LANCZOS)


def splash(size: int = 1024, dark: bool = False) -> Image.Image:
    """Centered sprout for the launch screen (transparent; the platform paints the background colour)."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img = Image.alpha_composite(img, _radial(s, "#ffd166", s * 0.3, s * 0.5, s * 0.5, 0.55 if dark else 0.7))
    sp = sprout(int(s * 0.62))
    img.alpha_composite(sp, (int(s * 0.19), int(s * 0.17)))
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon(1024).save(OUT / "icon.png", optimize=True)
    icon(1024).save(OUT / "icon_ios.png", optimize=True)
    adaptive_foreground(1024).save(OUT / "icon_android.png", optimize=True)
    icon(192).save(OUT / "favicon.png", optimize=True)
    splash(1024).save(OUT / "splash.png", optimize=True)
    splash(1024, dark=True).save(OUT / "splash_dark.png", optimize=True)
    logo = sprout(512 * SS, with_ground=False).resize((256, 256), Image.LANCZOS)
    logo.save(OUT / "logo.png", optimize=True)
    print("wrote icons to", OUT)


if __name__ == "__main__":
    main()
