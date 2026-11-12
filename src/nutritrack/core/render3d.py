"""A tiny low-poly 3D renderer for the garden trees (pure Python + Pillow, so it runs on desktop and phones).

Each tree is a real 3D mesh: jittered icosphere canopy clusters, tapered trunks, stacked cones for pines, blossoms or
fruit, all sitting on a floating grass island. Faces are flat-shaded (key light + sky fill) and painted back to front,
supersampled for smooth edges. Rotating the camera gives the turntable you can drag on the Today screen.
"""
from __future__ import annotations

import io
import math
import random
from functools import lru_cache

Vec = tuple[float, float, float]
Face = tuple[Vec, Vec, Vec, tuple[int, int, int]]


# ---------- vector helpers ----------
def _sub(a: Vec, b: Vec) -> Vec: return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a: Vec, b: Vec) -> Vec: return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a: Vec, k: float) -> Vec: return (a[0] * k, a[1] * k, a[2] * k)
def _dot(a: Vec, b: Vec) -> float: return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a: Vec, b: Vec) -> Vec: return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Vec) -> Vec:
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _vary(rgb: tuple[int, int, int], rnd: random.Random, amt: float = 0.08) -> tuple[int, int, int]:
    k = 1 + rnd.uniform(-amt, amt)
    return tuple(max(0, min(255, int(v * k))) for v in rgb)  # type: ignore[return-value]


def _outward(face: tuple[Vec, Vec, Vec], center: Vec) -> tuple[Vec, Vec, Vec]:
    a, b, c = face
    n = _cross(_sub(b, a), _sub(c, a))
    centroid = _mul(_add(_add(a, b), c), 1 / 3)
    return (a, c, b) if _dot(n, _sub(centroid, center)) < 0 else (a, b, c)


# ---------- primitives ----------
def _icosphere(center: Vec, radius: Vec, color, rnd: random.Random, subdiv: int = 1, jitter: float = 0.12) -> list[Face]:
    t = (1 + math.sqrt(5)) / 2
    verts = [_norm(v) for v in [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t),
                                (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
             (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
             (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache: dict[tuple[int, int], int] = {}

        def mid(i: int, j: int) -> int:
            key = (min(i, j), max(i, j))
            if key not in cache:
                verts.append(_norm(_mul(_add(verts[i], verts[j]), 0.5)))
                cache[key] = len(verts) - 1
            return cache[key]

        faces = [f for a, b, c in faces for f in ((a, mid(a, b), mid(a, c)), (b, mid(b, c), mid(a, b)),
                                                    (c, mid(a, c), mid(b, c)), (mid(a, b), mid(b, c), mid(a, c)))]
    pts = []
    for v in verts:
        k = 1 + rnd.uniform(-jitter, jitter)
        pts.append((center[0] + v[0] * radius[0] * k, center[1] + v[1] * radius[1] * k, center[2] + v[2] * radius[2] * k))
    return [(*_outward((pts[a], pts[b], pts[c]), center), _vary(color, rnd)) for a, b, c in faces]


def _frustum(y0: float, y1: float, r0: float, r1: float, color, rnd, sides: int = 7, x: float = 0, z: float = 0,
             bands: list[tuple[float, float]] | None = None, band_color=None) -> list[Face]:
    out: list[Face] = []
    for i in range(sides):
        a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
        p = lambda r, a, y: (x + r * math.cos(a), y, z + r * math.sin(a))  # noqa: E731
        q = [p(r0, a0, y0), p(r0, a1, y0), p(r1, a1, y1), p(r1, a0, y1)]
        center = (x, (y0 + y1) / 2, z)
        col = _vary(color, rnd, 0.05)
        out += [(*_outward((q[0], q[1], q[2]), center), col), (*_outward((q[0], q[2], q[3]), center), col)]
        if bands:  # dark birch marks: small quads just outside the bark
            for by, bh in bands:
                yb0, yb1 = y0 + (y1 - y0) * by, y0 + (y1 - y0) * (by + bh)
                rb0 = r0 + (r1 - r0) * by + 0.004
                rb1 = r0 + (r1 - r0) * (by + bh) + 0.004
                if rnd.random() < 0.6:
                    b = [p(rb0, a0, yb0), p(rb0, a1, yb0), p(rb1, a1, yb1), p(rb1, a0, yb1)]
                    out += [(*_outward((b[0], b[1], b[2]), center), band_color),
                            (*_outward((b[0], b[2], b[3]), center), band_color)]
    return out


def _cone(y0: float, height: float, radius: float, color, rnd, sides: int = 8) -> list[Face]:
    apex = (0.0, y0 + height, 0.0)
    center = (0.0, y0 + height * 0.3, 0.0)
    out: list[Face] = []
    for i in range(sides):
        a0, a1 = 2 * math.pi * i / sides, 2 * math.pi * (i + 1) / sides
        r0, r1 = radius * (1 + rnd.uniform(-0.06, 0.06)), radius * (1 + rnd.uniform(-0.06, 0.06))
        p0, p1 = (r0 * math.cos(a0), y0, r0 * math.sin(a0)), (r1 * math.cos(a1), y0, r1 * math.sin(a1))
        out.append((*_outward((p0, p1, apex), center), _vary(color, rnd, 0.07)))
        out.append((*_outward((p0, p1, (0.0, y0 - height * 0.08, 0.0)), center), _vary(color, rnd, 0.1)))
    return out


def _island(rnd: random.Random, radius: float = 0.78) -> list[Face]:
    """A floating hexagonal grass island with a rocky underside."""
    sides, out = 9, []
    rim = []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        r = radius * (1 + rnd.uniform(-0.05, 0.05))
        rim.append((r * math.cos(a), rnd.uniform(-0.015, 0.015), r * math.sin(a)))
    top_c = (0.0, 0.02, 0.0)
    grass, dirt, rock = _hex("#6dbb5a"), _hex("#8a6142"), _hex("#6e5a4b")
    for i in range(sides):
        a, b = rim[i], rim[(i + 1) % sides]
        out.append((*_outward((top_c, a, b), (0, -1, 0)), _vary(grass, rnd, 0.06)))
        lip_a, lip_b = (a[0] * 0.98, a[1] - 0.12, a[2] * 0.98), (b[0] * 0.98, b[1] - 0.12, b[2] * 0.98)
        out += [(*_outward((a, b, lip_b), (0, 0, 0)), _vary(dirt, rnd)), (*_outward((a, lip_b, lip_a), (0, 0, 0)), _vary(dirt, rnd))]
        tip = (rnd.uniform(-0.06, 0.06), -0.5, rnd.uniform(-0.06, 0.06))
        out.append((*_outward((lip_a, lip_b, tip), (0, -0.2, 0)), _vary(rock, rnd, 0.12)))
    for _ in range(5):  # little pebbles and tufts
        ang, d = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.45, 0.8) * radius
        out += _icosphere((d * math.cos(ang), 0.03, d * math.sin(ang)), (0.06, 0.035, 0.06), _hex("#9aa59a"), rnd, 0, 0.2)
    return out


# ---------- tree models ----------
SPECIES_COLORS = {
    "oak": ("#3f9a52", "#7a5232", None),
    "pine": ("#2f7a52", "#6b4a2e", None),
    "cherry": ("#f4a6c6", "#6e4434", "#ffffff"),
    "maple": ("#e8823a", "#6b4430", None),
    "birch": ("#a3cf5c", "#ece7da", None),
    "golden": ("#f2c94c", "#7a5a2a", "#fff3b0"),
}
FRUIT = "#e5484d"


def tree_mesh(species: str, stage: int) -> list[Face]:
    rnd = random.Random(f"{species}-{stage}")
    leaf_hex, trunk_hex, bloom_hex = SPECIES_COLORS.get(species, SPECIES_COLORS["oak"])
    leaf, trunk = _hex(leaf_hex), _hex(trunk_hex)
    faces = _island(rnd)
    if stage == 0:  # a mound with a seed
        faces += _icosphere((0, 0.02, 0), (0.22, 0.1, 0.22), _hex("#8a6142"), rnd, 1, 0.1)
        faces += _icosphere((0.02, 0.12, 0.0), (0.06, 0.045, 0.05), _hex("#5c3b22"), rnd, 0, 0.05)
        return faces
    if stage == 1:  # sprout
        faces += _icosphere((0, 0.0, 0), (0.16, 0.06, 0.16), _hex("#8a6142"), rnd, 1, 0.1)
        faces += _frustum(0.0, 0.42, 0.03, 0.02, _hex("#4f8a3c"), rnd, 6)
        faces += _icosphere((-0.11, 0.42, 0.0), (0.13, 0.035, 0.07), _hex("#78c257"), rnd, 1, 0.05)
        faces += _icosphere((0.11, 0.47, 0.01), (0.13, 0.035, 0.07), _hex("#62ad46"), rnd, 1, 0.05)
        return faces
    h = {2: 0.5, 3: 0.72, 4: 0.86, 5: 0.9}[stage]
    r = {2: 0.34, 3: 0.48, 4: 0.6, 5: 0.63}[stage]
    tw = {2: 0.065, 3: 0.095, 4: 0.12, 5: 0.125}[stage]
    if species == "pine":
        faces += _frustum(0.0, h * 0.5, tw, tw * 0.7, trunk, rnd, 6)
        tiers = 3 if stage < 4 else 4
        tier_h, step = r * 1.0, r * 0.5
        cones = []
        for i in range(tiers):
            y = h * 0.3 + i * step
            rad = r * (1.05 - i * 0.2)
            faces += _cone(y, tier_h, rad, leaf, rnd, 9)
            cones.append((y, tier_h, rad))
        top = None
    else:
        bands = [(0.12, 0.05), (0.3, 0.04), (0.5, 0.05), (0.7, 0.04)] if species == "birch" else None
        faces += _frustum(0.0, h, tw, tw * 0.55, trunk, rnd, 7, bands=bands, band_color=_hex("#2f2f2f"))
        # two little branches
        for side in (-1, 1):
            if stage >= 3:
                bx = side * r * 0.35
                faces += _frustum(h * 0.55, h * 0.85, tw * 0.4, tw * 0.25, trunk, rnd, 5, x=bx * 0.5)
        stretch = 1.35 if species == "birch" else 1.0
        clusters = [(0, h + r * 0.55, 0, 1.0)] + [
            (math.cos(a) * r * 0.62, h + r * 0.25 + rnd.uniform(-0.05, 0.08), math.sin(a) * r * 0.62, 0.72)
            for a in [rnd.uniform(0, 2 * math.pi) + k * 2 * math.pi / (3 if stage < 4 else 4) for k in range(3 if stage < 4 else 4)]]
        for cx, cy, cz, k in clusters:
            rr = r * k
            faces += _icosphere((cx, cy, cz), (rr * 0.78, rr * 0.7 * stretch, rr * 0.78), leaf, rnd, 1, 0.14)
        top = h + r * 1.3
    if stage == 5 and species == "pine":  # pinecones / berries sitting on the cone surfaces
        for _ in range(10):
            y0, th, rad = cones[rnd.randrange(len(cones))]
            f = rnd.uniform(0.05, 0.5)
            ang = rnd.uniform(0, 2 * math.pi)
            rr = rad * (1 - f) * 0.92
            faces += _icosphere((math.cos(ang) * rr, y0 + th * f, math.sin(ang) * rr), (0.05, 0.05, 0.05), _hex(FRUIT), rnd, 0, 0.05)
    elif stage == 5:  # blossoms or fruit
        deco = _hex(bloom_hex or FRUIT)
        for _ in range(14 if bloom_hex else 9):
            ang, el = rnd.uniform(0, 2 * math.pi), rnd.uniform(-0.2, 1.0)
            d = r * 0.82
            p = (math.cos(ang) * d * math.cos(el * 0.8), (top - r * 0.7) + math.sin(el) * r * 0.55, math.sin(ang) * d * math.cos(el * 0.8))
            s = 0.045 if bloom_hex else 0.055
            faces += _icosphere(p, (s, s, s), deco, rnd, 0, 0.05)
    return faces


# ---------- rendering ----------
LIGHT = _norm((-0.55, 0.8, 0.45))  # key light: upper left, toward the viewer
SKY = (0.9, 0.95, 1.05)


def render(faces: list[Face], angle_deg: float = 30.0, size: int = 256, elevation_deg: float = 22.0,
           supersample: int = 3, shadow: bool = True) -> bytes:
    from PIL import Image, ImageDraw, ImageFilter

    ss = size * supersample
    ay, ax = math.radians(angle_deg), math.radians(elevation_deg)
    cy_, sy_, cx_, sx_ = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)

    def xf(v: Vec) -> Vec:
        x, y, z = v
        x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_          # turntable (around Y)
        y, z = y * cx_ - z * sx_, y * sx_ + z * cx_          # look down a little (around X)
        return x, y, z

    scale = ss * 0.385
    ox, oy = ss / 2, ss * 0.72
    tris = []
    for a, b, c, col in faces:
        ta, tb, tc = xf(a), xf(b), xf(c)
        n = _norm(_cross(_sub(tb, ta), _sub(tc, ta)))
        if n[2] <= 0:   # facing away from the camera
            continue
        diff = max(0.0, _dot(n, LIGHT))
        sky = 0.5 + 0.5 * n[1]
        k = 0.42 + 0.62 * diff
        rgb = tuple(max(0, min(255, int(col[i] * k * (0.92 + 0.08 * sky * SKY[i])))) for i in range(3))
        depth = (ta[2] + tb[2] + tc[2]) / 3
        pts = [(ox + p[0] * scale, oy - p[1] * scale) for p in (ta, tb, tc)]
        tris.append((depth, pts, rgb))
    tris.sort(key=lambda t: t[0])

    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    if shadow:  # soft contact shadow beneath the floating island
        sh = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse([ox - scale * 0.8, oy + scale * 0.62, ox + scale * 0.8, oy + scale * 0.8], fill=(0, 0, 0, 70))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(ss * 0.02)))
    draw = ImageDraw.Draw(img)
    for _, pts, rgb in tris:
        draw.polygon(pts, fill=(*rgb, 255), outline=(*rgb, 255))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


@lru_cache(maxsize=512)
def tree_png(species: str, stage: int, angle: int = 30, size: int = 256) -> bytes:
    return render(tree_mesh(species, stage), angle_deg=angle, size=size)


def available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False
