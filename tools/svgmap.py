"""Shared SVG-to-polygon helpers for the continent map generators (polygon algebra via shapely)."""
import re

from shapely.geometry import Polygon
from shapely.ops import unary_union

NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?", re.I)


def parse_path(d):
    """SVG path data -> list of subpaths (lists of (x, y)); cubics sampled in 4 steps."""
    subs, cur = [], []
    x = y = sx = sy = 0.0
    last_ctrl = None
    for cmd, argstr in re.findall(r"([MmLlHhVvCcSsZz])([^MmLlHhVvCcSsZz]*)", d):
        a = [float(v) for v in NUM.findall(argstr)]
        rel = cmd.islower()
        kind = cmd.upper()
        if kind == "M":
            if cur:
                subs.append(cur)
            for i in range(0, len(a) - 1, 2):
                x = x + a[i] if rel else a[i]
                y = y + a[i + 1] if rel else a[i + 1]
                if i == 0:
                    cur, sx, sy = [(x, y)], x, y
                else:
                    cur.append((x, y))
            last_ctrl = None
        elif kind == "L":
            for i in range(0, len(a) - 1, 2):
                x = x + a[i] if rel else a[i]
                y = y + a[i + 1] if rel else a[i + 1]
                cur.append((x, y))
            last_ctrl = None
        elif kind in ("H", "V"):
            for v in a:
                if kind == "H":
                    x = x + v if rel else v
                else:
                    y = y + v if rel else v
                cur.append((x, y))
            last_ctrl = None
        elif kind in ("C", "S"):
            step = 6 if kind == "C" else 4
            for i in range(0, len(a) - step + 1, step):
                if kind == "C":
                    c1 = (x + a[i], y + a[i + 1]) if rel else (a[i], a[i + 1])
                    c2 = (x + a[i + 2], y + a[i + 3]) if rel else (a[i + 2], a[i + 3])
                    end = (x + a[i + 4], y + a[i + 5]) if rel else (a[i + 4], a[i + 5])
                else:
                    c1 = (2 * x - last_ctrl[0], 2 * y - last_ctrl[1]) if last_ctrl else (x, y)
                    c2 = (x + a[i], y + a[i + 1]) if rel else (a[i], a[i + 1])
                    end = (x + a[i + 2], y + a[i + 3]) if rel else (a[i + 2], a[i + 3])
                p0 = (x, y)
                for k in range(1, 5):
                    t = k / 4
                    m = 1 - t
                    cur.append(
                        (
                            m**3 * p0[0] + 3 * m * m * t * c1[0] + 3 * m * t * t * c2[0] + t**3 * end[0],
                            m**3 * p0[1] + 3 * m * m * t * c1[1] + 3 * m * t * t * c2[1] + t**3 * end[1],
                        )
                    )
                x, y = end
                last_ctrl = c2
        elif kind == "Z":
            x, y = sx, sy
            last_ctrl = None
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s) >= 6]


def read_fills(svg):
    """Every solid-filled <path> of the SVG text as fill color -> subpaths (artboard units)."""
    by_fill = {}
    for attrs in re.findall(r"<path([^>]*?)/?>", svg, re.S):
        fill = re.search(r'fill="(#[0-9A-Fa-f]{6})"', attrs)
        data = re.search(r'\sd="([^"]+)"', attrs)
        if fill and data:
            by_fill.setdefault(fill.group(1).upper(), []).extend(parse_path(data.group(1)))
    return by_fill


def solids_and_holes(by_fill):
    """Per fill: subpaths whose centroid lies inside a larger subpath of the same fill are holes."""
    solids, holes = {}, {}
    for fill, subs in by_fill.items():
        subs = sorted(subs, key=area, reverse=True)
        for i, sub in enumerate(subs):
            is_hole = any(inside(bigger, *centroid(sub)) for bigger in subs[:i])
            (holes if is_hole else solids).setdefault(fill, []).append(sub)
    return solids, holes


def area(poly):
    return abs(sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1] for i in range(len(poly)))) / 2


def centroid(poly):
    a = cx = cy = 0.0
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i - 1], poly[i]
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    a *= 0.5
    return (cx / (6 * a), cy / (6 * a))


def inside(poly, x, y):
    res, j = False, len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            res = not res
        j = i
    return res


def edge_distance(poly, x, y):
    best = float("inf")
    for k in range(len(poly)):
        (ax, ay), (bx, by) = poly[k - 1], poly[k]
        dx, dy = bx - ax, by - ay
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, ((x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2) ** 0.5)
    return best


def clearance(poly, lakes, x, y):
    """Distance from (x, y) to the nearest zone border or lake shore; -1 outside or in a lake."""
    if not inside(poly, x, y) or any(inside(lake, x, y) for lake in lakes):
        return -1.0
    return min([edge_distance(poly, x, y)] + [edge_distance(lake, x, y) for lake in lakes])


def pole(poly, lakes):
    """Pole of inaccessibility of the zone minus its lakes (grid search, refined twice)."""
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    best, best_d = None, -1.0
    for _ in range(3):
        for i in range(41):
            for j in range(41):
                x, y = x0 + (x1 - x0) * i / 40, y0 + (y1 - y0) * j / 40
                d = clearance(poly, lakes, x, y)
                if d > best_d:
                    best, best_d = (x, y), d
        w, h = (x1 - x0) / 6, (y1 - y0) / 6
        x0, x1, y0, y1 = best[0] - w, best[0] + w, best[1] - h, best[1] + h
    return best


def label_anchor(poly, lakes):
    """The area centroid when it sits well clear of borders and lakes, else the pole."""
    c = centroid(poly)
    p = pole(poly, lakes)
    if clearance(poly, lakes, *c) >= 0.5 * clearance(poly, lakes, *p):
        return c
    return p


def simplify(poly, eps):
    def dp(pts):
        if len(pts) < 3:
            return pts
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        best, idx = 0.0, 0
        for i in range(1, len(pts) - 1):
            x0, y0 = pts[i]
            d = abs(dy * (x0 - x1) - dx * (y0 - y1)) / length if length else ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
            if d > best:
                best, idx = d, i
        if best > eps:
            return dp(pts[: idx + 1])[:-1] + dp(pts[idx:])
        return [pts[0], pts[-1]]

    half = len(poly) // 2
    return dp(poly[: half + 1])[:-1] + dp(poly[half:] + [poly[0]])[:-1]


def normalized(poly, frame, offset_x):
    """Artboard points -> the square 0..1 frame (artboard centered horizontally, y southward)."""
    pts = [{"x": round((x + offset_x) / frame, 4), "y": round(y / frame, 4)} for x, y in poly]
    return pts + [pts[0]]


def joined(shapes, seam):
    """Union of adjoining shapely parts; growing and shrinking by `seam` closes the hairline gaps
    between them without moving the outer outline."""
    return unary_union([s.buffer(seam) for s in shapes]).buffer(-seam)


def shape(ring):
    """A source ring as a valid shapely polygon (self-touching SVG rings are repaired)."""
    return Polygon(ring).buffer(0)


def outline(geom, name, sliver=12.0):
    """The exterior ring of a zone that must be one piece; slivers up to `sliver` units² that a
    hand-placed cut leaves behind are dropped, anything larger is an error."""
    parts = sorted(getattr(geom, "geoms", [geom]), key=lambda g: g.area, reverse=True)
    if not parts or parts[0].is_empty:
        raise SystemExit(f"{name}: empty outline")
    lost = [round(p.area, 1) for p in parts[1:] if p.area > sliver]
    if lost:
        raise SystemExit(f"{name}: falls apart into extra pieces {lost}")
    return list(parts[0].exterior.coords)[:-1]
