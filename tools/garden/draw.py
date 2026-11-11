"""Hand-drawn (pencil-line) SVG generator for ตอกบัตร garden: pets (cat, dog, rabbit) and props.

Technique (same as the app's characters): jittered points, Catmull-Rom curves, outlines as open paths that
overlap their start a little (pen loop), fills as separate shapes slightly misregistered. Line colour #22304A.
Every part sits in its own <g id="..."> so it can be animated later (legs, tail, ears, eyes, pupils).
"""
from __future__ import annotations

import math
import random

INK = "#22304A"
LINE = 4.0          # outline weight, as heavy as the app mascot (3.75 on a 150 px character)
WIDE = 1.2          # explicit detail widths (eyes, whiskers, stripes) scale up with it
MAX_STROKE = 230    # longer pen strokes are split, so the stretch brush texture never gets smeared


class Pen:
    def __init__(self, seed: int):
        self.r = random.Random(seed)

    def jit(self, pts, amp=1.0):
        return [(x + self.r.uniform(-amp, amp), y + self.r.uniform(-amp, amp)) for x, y in pts]


def cr(pts, closed=False):
    """Catmull-Rom through pts → SVG cubic path data."""
    n = len(pts)
    if n < 2:
        return ""
    P = pts
    d = f"M{P[0][0]:.1f} {P[0][1]:.1f}"
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = P[(i - 1) % n] if (closed or i > 0) else P[i]
        p1 = P[i]
        p2 = P[(i + 1) % n]
        p3 = P[(i + 2) % n] if (closed or i + 2 < n) else P[(i + 1) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d + (" Z" if closed else "")


def cr_points(pts, steps=6, spacing=None):
    """Sample the same Catmull-Rom curve cr() draws (open): `steps` points per segment, or more so points sit ≤ spacing apart."""
    n = len(pts)
    out = []
    for i in range(n - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        n_k = steps if spacing is None else max(steps, math.ceil(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / spacing))
        for k in range(n_k):
            t = k / n_k
            u = 1 - t
            out.append((u ** 3 * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p2[0],
                        u ** 3 * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p2[1]))
    out.append(pts[-1])
    return out


def ellipse(cx, cy, rx, ry, n=14, rot=0.0, start=0.0):
    out = []
    for i in range(n):
        a = start + 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        c, s = math.cos(rot), math.sin(rot)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def rrect(x, y, w, h, r, per_edge=3):
    """Rounded rectangle as points, with extra points on straight edges so curves stay straight."""
    pts = []
    corners = [(x + w - r, y + r, -math.pi / 2), (x + w - r, y + h - r, 0), (x + r, y + h - r, math.pi / 2), (x + r, y + r, math.pi)]
    for (cx, cy, a0) in corners:
        for k in range(3):
            a = a0 + (math.pi / 2) * k / 2
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        # straight edge to next corner
        nxt = corners[(corners.index((cx, cy, a0)) + 1) % 4]
        ex, ey = cx + r * math.cos(a0 + math.pi / 2), cy + r * math.sin(a0 + math.pi / 2)
        nx, ny = nxt[0] + r * math.cos(nxt[2]), nxt[1] + r * math.sin(nxt[2])
        for k in range(1, per_edge):
            t = k / per_edge
            pts.append((ex + (nx - ex) * t, ey + (ny - ey) * t))
    return pts


class Art:
    """Collects layers for one drawing."""

    def __init__(self, seed=1, line=LINE, k=WIDE):
        self.pen = Pen(seed)
        self.parts: list[str] = []
        self.line = line
        self.k = k  # multiplier for explicit widths (1.0 = widths are already in final units)

    def shape(self, pts, fill, jit=0.9, misreg=1.0, outline=True, wide=None, opacity=None, ink=INK, inner=""):
        """Filled shape + its pen outline (open path overlapping its start). `inner` goes between the two (coat patches)."""
        p = self.pen.jit(pts, jit)
        out = []
        if fill:
            dx, dy = self.pen.r.uniform(-misreg, misreg), self.pen.r.uniform(-misreg, misreg)
            f = [(x + dx, y + dy) for x, y in p]
            op = f' fill-opacity="{opacity}"' if opacity is not None else ""
            out.append(f'<path id="fill" d="{cr(f, closed=True)}" fill="{fill}"{op}/>')
        out.append(inner)
        if outline:
            # like the mascot: start anywhere, go all the way round, then run on a little past the start
            k = self.pen.r.randrange(len(p))
            q = p[k:] + p[:k]
            a_, b_ = q[0], q[1]
            end = (a_[0] + (b_[0] - a_[0]) * 0.3 + self.pen.r.uniform(-1, 1), a_[1] + (b_[1] - a_[1]) * 0.3 + self.pen.r.uniform(-1, 1))
            out.append(self.stroke(q + [a_, end], wide * self.k if wide else self.line, ink))
        return "".join(out)

    def line_(self, pts, width=None, color=INK, jit=0.6):
        p = self.pen.jit(pts, jit)
        return self.stroke(p, width * self.k if width else self.line, color)

    def stroke(self, pts, width, color):
        """One pen stroke through pts; long ones become several overlapping strokes (like re-placing the pencil)."""
        kind = "ink" if color == INK else "line"
        attrs = f'stroke="{color}" stroke-width="{width:.2f}" stroke-linecap="round" stroke-linejoin="round" fill="none"'
        dense = cr_points(pts, 6, spacing=3.5)
        seg = [math.hypot(dense[i + 1][0] - dense[i][0], dense[i + 1][1] - dense[i][1]) for i in range(len(dense) - 1)]
        total = sum(seg)
        if total <= MAX_STROKE:
            return f'<path id="{kind}" d="{cr(pts)}" {attrs}/>'
        k = math.ceil(total / (MAX_STROKE * 0.85))
        piece = total / k
        out, start, acc, cut = [], 0, 0.0, piece
        for i, d in enumerate(seg):
            acc += d
            if acc >= cut or i == len(seg) - 1:
                end = i + 1
                # overlap a few px into the next piece, and start a hair off the line
                ext = min(len(dense) - 1, end + 2)
                chunk = dense[start:ext + 1]
                jx, jy = self.pen.r.uniform(-0.8, 0.8), self.pen.r.uniform(-0.8, 0.8)
                chunk = [(chunk[0][0] + jx, chunk[0][1] + jy)] + chunk[1:]
                d_ = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in chunk)
                out.append(f'<path id="{kind}" d="{d_}" {attrs}/>')
                start, cut = end, cut + piece
        return "".join(out)

    def tube(self, pts, fill, width, jit=0.6, tip=1.0):
        """A limb/tail as a CLOSED shape (fill + pen outline) around a centreline, round at both ends.

        Brushes only look right on outlines, so limbs are real shapes, not a fat stroke with a fill stroke on top.
        `tip` scales the radius at the far end (tails taper or swell a little)."""
        c = cr_points(self.pen.jit(pts, jit), 6)
        r0 = width / 2 + self.line / 2
        n = len(c)
        left, right = [], []
        for i, (x, y) in enumerate(c):
            ax, ay = c[max(i - 1, 0)]
            bx, by = c[min(i + 1, n - 1)]
            dx, dy = bx - ax, by - ay
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            r = r0 * (1 + (tip - 1) * i / (n - 1))
            left.append((x + nx * r, y + ny * r))
            right.append((x - nx * r, y - ny * r))
        def cap(cx, cy, r, ang):
            # sweep from one side, round the outer end, to the other side
            return [(cx + r * math.cos(ang - math.pi * k / 4), cy + r * math.sin(ang - math.pi * k / 4)) for k in (1, 2, 3)]
        ex, ey = c[-1]
        sx, sy = c[0]
        a_end = math.atan2(left[-1][1] - ey, left[-1][0] - ex)
        a_start = math.atan2(right[0][1] - sy, right[0][0] - sx)
        ring = left[::2] + [left[-1]] + cap(ex, ey, r0 * tip, a_end) + right[::-1][::2] + [right[0]] + cap(sx, sy, r0, a_start)
        # drop points that sit almost on top of each other (they make kinks in the curve)
        clean = [ring[0]]
        for p in ring[1:]:
            if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 2.0:
                clean.append(p)
        return self.shape(clean, fill, jit=0.35, misreg=0.6)

    def dot(self, cx, cy, r, fill):
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"/>'

    def group(self, gid, *items, transform=None):
        t = f' transform="{transform}"' if transform else ""
        return f'<g id="{gid}"{t}>' + "".join(items) + "</g>"


def svg(w, h, body, name):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" fill="none"><g id="{name}">{body}</g></svg>'


# ------------------------------------------------------------------ face helpers
def eyes(a: Art, lx, rx, y, rw=8.5, rh=10.0, look=(1.6, 0.8), pupil=5.2):
    """Far (left) eye first, then near (right) eye — pupils stay ≥2 px inside their own eye."""
    parts = []
    for gid, ex in (("eye-l", lx), ("eye-r", rx)):
        white = a.shape(ellipse(ex, y, rw, rh, 12), "#FFFFFF", jit=0.5, misreg=0.4, wide=2.6)
        px, py = ex + look[0], y + look[1]
        pup = a.dot(px, py, pupil, INK) + a.dot(px + 1.7, py - 2.0, 1.7, "#FFFFFF")
        parts.append(a.group(gid, white, a.group("pupil", pup)))
    return "".join(parts)


def cheeks(a: Art, pts, r=(5.5, 3.6)):
    return a.group("cheeks", *[f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{r[0]}" ry="{r[1]}" fill="#FFA8B8" fill-opacity="0.85"/>' for x, y in pts])


def shadow(cx, cy, rx, ry=5):
    return f'<ellipse id="shadow" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{INK}" fill-opacity="0.12"/>'


def darker(hex_, k=0.82):
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % (int(r * k), int(g * k), int(b * k))


# ------------------------------------------------------------------ pets — drawn exactly like the app mascot
# Same rules as ชอล์ก (wt/chars2.mjs): 200-unit box, body outline 5, stick legs 7 (navy, one stroke each),
# huge white eyes (outline 3.5) with plain navy pupils, solid pink cheeks, one-stroke mouth, dust dots at the feet,
# flat fills, no shading, no extra detail lines. Facing right; body side-on, face to the viewer.
PW, PH = 200, 180


def pet_art(seed):
    return Art(seed, line=5.0, k=1.0)


def sticks(a, lines, w=7.0):
    return "".join(a.group(gid, a.line_(pts, width=w, jit=0.5)) for gid, pts in lines)


def big_eyes(a, l, r, look=(2.5, 1.5), pupil=5.8):
    """l, r = (cx, cy, radius). Eyes never touch (gap between them), pupils stay inside."""
    out = []
    for gid, (cx, cy, rad) in (("eye-l", l), ("eye-r", r)):
        white = a.shape(ellipse(cx, cy, rad, rad * 1.06, 10), "#FFFFFF", jit=0.45, misreg=0, wide=3.5)
        pup = a.dot(cx + look[0], cy + look[1], pupil, INK)
        out.append(a.group(gid, white, a.group("pupil", pup)))
    return "".join(out)


def pink(a, pts, r=(6.5, 4.2)):
    return a.group("cheeks", *[a.shape(ellipse(x, y, r[0], r[1], 8), "#FFA8B8", jit=0.3, misreg=0, outline=False) for x, y in pts])


def dust(pts, op=0.55):
    return '<g id="dust">' + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{INK}" fill-opacity="{op}"/>' for x, y, r in pts) + "</g>"


def cr_loop(pts, steps=8):
    """Points along the closed Catmull-Rom curve cr(pts, closed=True) draws."""
    n, out = len(pts), []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        for k in range(steps):
            t = k / steps
            u = 1 - t
            out.append((u ** 3 * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p2[0],
                        u ** 3 * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p2[1]))
    return out


def clip_convex(subject, clip):
    """Sutherland–Hodgman: the part of polygon `subject` inside the convex polygon `clip`."""
    area = sum(clip[i][0] * clip[(i + 1) % len(clip)][1] - clip[(i + 1) % len(clip)][0] * clip[i][1] for i in range(len(clip)))
    sign = 1 if area > 0 else -1

    def inside(p, a, b):
        return sign * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) >= 0

    def cross(p, q, a, b):
        dx1, dy1, dx2, dy2 = q[0] - p[0], q[1] - p[1], b[0] - a[0], b[1] - a[1]
        den = dx1 * dy2 - dy1 * dx2 or 1e-9
        t = ((a[0] - p[0]) * dy2 - (a[1] - p[1]) * dx2) / den
        return (p[0] + t * dx1, p[1] + t * dy1)

    out = subject
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        src, out = out, []
        for j in range(len(src)):
            p, q = src[j], src[(j + 1) % len(src)]
            if inside(q, a, b):
                if not inside(p, a, b):
                    out.append(cross(p, q, a, b))
                out.append(q)
            elif inside(p, a, b):
                out.append(cross(p, q, a, b))
        if not out:
            break
    return out


def hull(pts):
    """Convex hull (monotone chain), counter-clockwise."""
    p = sorted(set((round(x, 2), round(y, 2)) for x, y in pts))
    if len(p) < 3:
        return p

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2 and (out[-1][0] - out[-2][0]) * (q[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (q[0] - out[-2][0]) <= 0:
                out.pop()
            out.append(q)
        return out

    lo, hi = half(p), half(p[::-1])
    return lo[:-1] + hi[:-1]


def coat(outline_pts, patches, grow=1.6):
    """Flat coat patches (calico, cow, tabby saddle) kept inside a body part: each patch is a rough blob, cut to
    the part's own curve pushed out a little so the pen outline drawn over it hides the cut edge."""
    loop = hull(cr_loop(outline_pts))  # the cut needs a convex outline; keep patches clear of any dents yourself
    cx = sum(x for x, _ in loop) / len(loop)
    cy = sum(y for _, y in loop) / len(loop)
    big = []
    for x, y in loop:
        d = math.hypot(x - cx, y - cy) or 1.0
        big.append((x + (x - cx) / d * grow, y + (y - cy) / d * grow))
    out = []
    for color, pts in patches:
        poly = clip_convex(cr_loop(pts, 6), big)
        if len(poly) > 2:
            out.append(f'<path id="coat" d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in poly) + f' Z" fill="{color}"/>')
    return "".join(out)


CAT_TORSO = [(60, 110), (80, 101), (108, 100), (132, 104), (146, 116), (145, 134), (128, 143), (98, 145), (68, 143), (54, 130)]
CAT_HEAD = [(102, 72), (112, 52), (138, 46), (164, 50), (176, 70), (174, 94), (160, 108), (138, 112), (114, 108), (101, 92)]
CAT_EAR_L, CAT_EAR_R = [(104, 66), (106, 30), (131, 52)], [(146, 50), (167, 28), (172, 66)]


def cat(colors, seed=11):
    """colors: body, stripe (or None), ear (inner); optional coat: torso / head patches [(colour, blob)],
    ear-l / ear-r (ear colour), stripes / head_stripes (positions, to override the default three)."""
    a = pet_art(seed)
    B, S = colors["body"], colors.get("stripe")
    legs = sticks(a, [("leg-back-far", [(70, 132), (68, 160)]), ("leg-back-near", [(86, 134), (88, 162)]),
                      ("leg-front-far", [(118, 134), (116, 161)]), ("leg-front-near", [(134, 132), (137, 160)])])
    tail = a.group("tail", a.line_([(58, 120), (42, 108), (36, 88), (42, 72), (53, 70)], width=6.5, jit=0.5))
    torso = [a.shape(CAT_TORSO, B, misreg=0, inner=coat(CAT_TORSO, colors.get("torso", [])))]
    if S:
        torso += [a.line_(pts, width=4, color=S, jit=0.4) for pts in colors.get("stripes", [[(x, 103), (x + 3, 116)] for x in (80, 94, 108)])]
    inner = colors.get("ear", "#FFA8B8")
    ears = [a.group("ear-l", a.shape(CAT_EAR_L, colors.get("ear-l", B), jit=0.6, misreg=0),
                    a.shape([(110, 58), (111, 41), (124, 53)], inner, jit=0.3, misreg=0, outline=False)),
            a.group("ear-r", a.shape(CAT_EAR_R, colors.get("ear-r", B), jit=0.6, misreg=0),
                    a.shape([(152, 50), (164, 38), (166, 58)], inner, jit=0.3, misreg=0, outline=False))]
    head = [a.shape(CAT_HEAD, B, misreg=0, inner=coat(CAT_HEAD, colors.get("head", [])))]
    if S:
        head += [a.line_(pts, width=3.6, color=S, jit=0.3)
                 for pts in colors.get("head_stripes", ([(129, 49), (131, 59)], [(140, 48), (140, 58)], [(151, 49), (149, 59)]))]
    face = [big_eyes(a, (124, 80, 11.8), (152, 78, 12.2), pupil=5.4), pink(a, [(110, 97), (166, 95)]),
            a.dot(139, 91, 2.6, INK),
            a.group("mouth", a.line_([(131, 96), (135, 100), (139, 96.5), (143, 100), (147, 96)], width=3.2, jit=0.25))]
    body = legs + tail + a.group("body", *torso) + a.group("head", *ears, *head, a.group("face", *face))
    return svg(PW, PH, body + dust([(60, 166, 2.4), (72, 170, 1.6), (128, 168, 2.2), (144, 164, 1.4), (150, 170, 1.8)]), "Pet/cat")


def dog(colors, seed=21):
    """colors: body, ear, spot (or None)."""
    a = pet_art(seed)
    B, S = colors["body"], colors.get("spot")
    E = colors.get("ear", darker(B, 0.8))
    legs = sticks(a, [("leg-back-far", [(70, 134), (67, 161)]), ("leg-back-near", [(86, 136), (88, 163)]),
                      ("leg-front-far", [(118, 136), (116, 162)]), ("leg-front-near", [(134, 134), (137, 161)])])
    tail = a.group("tail", a.line_([(58, 116), (46, 104), (40, 88), (42, 80)], width=6.5, jit=0.5))
    torso = [a.shape([(60, 112), (82, 102), (110, 101), (134, 106), (148, 118), (147, 136), (128, 146), (98, 148), (68, 146), (54, 132)], B, misreg=0)]
    if S:
        torso.append(a.shape(ellipse(86, 120, 15, 11, 9), S, jit=0.6, misreg=0, outline=False))
    ear_l = a.group("ear-l", a.shape(ellipse(104, 84, 12, 23, 10, rot=0.38), E, jit=0.5, misreg=0))
    ear_r = a.group("ear-r", a.shape(ellipse(172, 82, 12, 23, 10, rot=-0.38), E, jit=0.5, misreg=0))
    head = [a.shape([(104, 74), (114, 54), (138, 47), (162, 52), (174, 72), (172, 96), (158, 110), (138, 114), (116, 110), (103, 94)], B, misreg=0)]
    if S:
        head.append(a.shape(ellipse(154, 72, 15, 14, 9), S, jit=0.6, misreg=0, outline=False))
    face = [big_eyes(a, (125, 79, 11.4), (152, 77, 11.8), pupil=5.3), pink(a, [(112, 98), (165, 96)]),
            a.shape(ellipse(138.5, 93, 6, 4.4, 8), INK, jit=0.3, misreg=0, outline=False),
            a.group("mouth", a.shape([(131, 99), (146, 99), (144, 107), (138.5, 110.5), (133, 107)], INK, jit=0.3, misreg=0, outline=False),
                    a.group("tongue", a.shape(ellipse(138.5, 106.5, 4.2, 2.6, 8), "#FF8F9E", jit=0.2, misreg=0, outline=False)))]
    body = legs + tail + a.group("body", *torso) + a.group("head", ear_l, ear_r, *head, a.group("face", *face))
    return svg(PW, PH, body + dust([(60, 167, 2.4), (72, 171, 1.6), (128, 169, 2.2), (144, 165, 1.4), (150, 171, 1.8)]), "Pet/dog")


def rabbit(colors, seed=31):
    """colors: body, ear (inner), tail."""
    a = pet_art(seed)
    B = colors["body"]
    legs = sticks(a, [("leg-back-far", [(78, 140), (76, 158)]), ("leg-back-near", [(94, 143), (96, 161)]),
                      ("leg-front-far", [(118, 142), (116, 159)]), ("leg-front-near", [(132, 139), (134, 157)])])
    tail = a.group("tail", a.shape(ellipse(58, 124, 11, 10, 9), colors.get("tail", B), jit=0.6, misreg=0))
    torso = a.group("body", a.shape([(64, 116), (84, 104), (112, 104), (134, 114), (142, 130), (128, 146), (94, 149), (68, 145), (57, 131)], B, misreg=0))
    ears = []
    for gid, cx, cy, rot in (("ear-l", 124, 38, -0.16), ("ear-r", 152, 36, 0.2)):
        ears.append(a.group(gid, a.shape(ellipse(cx, cy, 10.5, 28, 12, rot=rot), B, jit=0.5, misreg=0),
                            a.shape(ellipse(cx + 0.5, cy + 4, 4.6, 19, 10, rot=rot), colors.get("ear", "#FFA8B8"), jit=0.3, misreg=0, outline=False)))
    head = a.shape([(106, 82), (114, 64), (138, 57), (160, 62), (171, 80), (169, 100), (156, 112), (138, 115), (118, 111), (106, 98)], B, misreg=0)
    face = [big_eyes(a, (126, 86, 10.8), (151, 84, 11.2), pupil=5.0), pink(a, [(114, 101), (163, 99)], r=(6, 3.8)),
            a.shape(ellipse(138.5, 97, 3.4, 2.6, 8), "#FF8F9E", jit=0.2, misreg=0, outline=False),
            a.group("mouth", a.line_([(132, 101), (135.5, 104.5), (138.5, 101.5), (141.5, 104.5), (145, 101)], width=3.0, jit=0.2))]
    body = legs + tail + torso + a.group("head", *ears, head, a.group("face", *face))
    return svg(PW, PH, body + dust([(68, 164, 2.4), (80, 168, 1.6), (124, 166, 2.2), (140, 162, 1.4), (146, 168, 1.8)]), "Pet/rabbit")


# ------------------------------------------------------------------ 0.4.0: animals that hop, fly, waddle and swim
# Same construction as the cat/dog/rabbit (200 x 180 box, feet near y 160, outline 5, ink stick legs 7, huge eyes,
# pink cheeks, one-stroke mouth, dust). Every moving part is its own group so the gait can move it.
def frog(colors, seed=41):
    """colors: body, belly, spot (or None). Sits wide and low; big eyes on bumps on top; a folded thigh, feet forward."""
    a = pet_art(seed)
    B = colors["body"]
    body_pts = [(50, 142), (54, 120), (70, 104), (98, 96), (128, 94), (152, 100), (168, 116), (168, 138), (152, 152), (112, 156), (72, 154)]
    patches = [(colors["belly"], [(96, 136), (156, 126), (172, 152), (96, 164)])]
    if colors.get("spot"):
        patches += [(colors["spot"], ellipse(x, y, rx, ry, 9)) for x, y, rx, ry in ((80, 116, 8, 6), (100, 108, 6, 5), (66, 130, 5, 4))]
    legs = [a.group("leg-back-far", a.line_([(56, 148), (58, 160), (74, 161)], width=7, jit=0.4)),
            a.group("leg-front-far", a.line_([(142, 148), (144, 161)], width=7, jit=0.4))]
    thigh = a.shape(ellipse(80, 140, 21, 13, 10, rot=-0.35), B, jit=0.4, misreg=0)
    legs_near = [a.group("leg-back-near", a.line_([(70, 150), (72, 161), (94, 161)], width=7, jit=0.4), thigh),
                 a.group("leg-front-near", a.line_([(158, 147), (162, 161)], width=7, jit=0.4))]
    bumps = [a.shape(ellipse(124, 88, 17, 16, 10), B, jit=0.4, misreg=0), a.shape(ellipse(152, 86, 18, 17, 10), B, jit=0.4, misreg=0)]
    face = [big_eyes(a, (124, 86, 11.2), (152, 84, 11.8), look=(2.2, 1.3), pupil=5.2), pink(a, [(132, 113), (167, 109)], r=(5.5, 3.6)),
            a.group("mouth", a.line_([(134, 121), (145, 127), (158, 126), (167, 118)], width=3.2, jit=0.25))]
    body = a.group("body", a.shape(body_pts, B, misreg=0, inner=coat(body_pts, patches)))
    head = a.group("head", *bumps, a.group("face", *face))
    out = "".join(legs) + body + head + "".join(legs_near)
    return svg(PW, PH, out + dust([(54, 167, 2.4), (66, 171, 1.6), (134, 168, 2.2), (150, 165, 1.4), (160, 170, 1.8)]), "Pet/frog")


def bird(colors, seed=51):
    """colors: body, wing, belly, beak. A small round bird: head on top-front, wings that can open, fan tail."""
    a = pet_art(seed)
    B, Wg = colors["body"], colors["wing"]
    legs = [a.group("leg-far", a.line_([(96, 138), (94, 160), (101, 160)], width=6, jit=0.4)),
            a.group("leg-near", a.line_([(110, 138), (112, 160), (120, 160)], width=6, jit=0.4))]
    tail = a.group("tail", a.shape([(66, 116), (40, 98), (44, 112), (38, 120), (64, 128)], Wg, jit=0.5, misreg=0))
    wing_far = a.group("wing-far", a.shape([(86, 98), (98, 86), (112, 92), (104, 104)], darker(Wg, 0.9), jit=0.4, misreg=0))
    body_pts = ellipse(98, 118, 38, 30, 12)
    body = a.group("body", a.shape(body_pts, B, misreg=0, inner=coat(body_pts, [(colors["belly"], [(96, 126), (128, 112), (142, 142), (98, 156)])])))
    wing_near = a.group("wing-near", a.shape([(76, 110), (100, 104), (116, 114), (102, 130), (80, 128)], Wg, jit=0.4, misreg=0))
    head_pts = ellipse(130, 84, 27, 26, 12)
    face = [big_eyes(a, (122, 82, 8.8), (142, 80, 9.2), look=(1.8, 1.0), pupil=4.4), pink(a, [(118, 96), (148, 94)], r=(4.6, 3.0)),
            a.group("beak", a.shape([(154, 84), (170, 89), (154, 95)], colors["beak"], jit=0.2, misreg=0, wide=3.2))]
    head = a.group("head", a.shape(head_pts, B, misreg=0), a.group("face", *face))
    return svg(PW, PH, "".join(legs) + tail + wing_far + body + wing_near + head + dust([(84, 166, 2.0), (94, 169, 1.4), (118, 167, 1.8), (128, 164, 1.2)]), "Pet/bird")


def duck(colors, seed=61):
    """colors: body, head, wing, bill, ring (or None). Boat-shaped body, tail tip up, a round head on a short neck, flat bill."""
    a = pet_art(seed)
    B, Hd = colors["body"], colors.get("head", colors["body"])
    legs = [a.group("leg-far", a.line_([(90, 144), (88, 160), (96, 161)], width=6.5, jit=0.4)),
            a.group("leg-near", a.line_([(106, 145), (108, 161), (117, 161)], width=6.5, jit=0.4))]
    tail = a.group("tail", a.shape([(56, 118), (40, 96), (66, 106)], B, jit=0.4, misreg=0))
    body = a.group("body", a.shape([(50, 120), (60, 106), (86, 102), (120, 104), (142, 112), (148, 128), (134, 144), (98, 150), (66, 146), (52, 134)], B, misreg=0))
    wing = a.group("wing-near", a.shape([(72, 114), (104, 110), (122, 120), (100, 134), (76, 130)], colors["wing"], jit=0.4, misreg=0))
    neck_pts = [(124, 116), (126, 92), (138, 84), (152, 92), (148, 116)]
    ring = colors.get("ring")
    neck = a.shape(neck_pts, Hd, jit=0.4, misreg=0, inner=coat(neck_pts, [(ring, [(118, 99), (160, 97), (160, 105), (118, 107)])]) if ring else "")
    head_pts = ellipse(146, 72, 27, 25, 12)
    face = [big_eyes(a, (138, 70, 9.6), (157, 69, 9.4), look=(1.8, 1.0), pupil=4.6), pink(a, [(132, 85), (162, 84)], r=(4.8, 3.2)),
            a.group("beak", a.shape([(164, 74), (186, 75), (190, 82), (184, 87), (164, 86)], colors["bill"], jit=0.25, misreg=0, wide=3.4))]
    head = a.group("head", neck, a.shape(head_pts, Hd, misreg=0), a.group("face", *face))
    return svg(PW, PH, "".join(legs) + tail + body + wing + head + dust([(76, 167, 2.2), (88, 170, 1.5), (118, 168, 2.0), (130, 165, 1.3)]), "Pet/duck")


FROGS = {
    "เขียว": {"body": "#8CCB5E", "belly": "#E3F4C6"},
    "เหลือง": {"body": "#F2D45C", "belly": "#FFF4C7", "spot": "#D8A93A"},
    "ฟ้า": {"body": "#7FC4E8", "belly": "#DDF1FB", "spot": "#4E95C2"},
    "น้ำตาล": {"body": "#B58A5A", "belly": "#F1DFC6", "spot": "#8A6440"},
}
BIRDS = {
    "ฟ้า": {"body": "#86C0F2", "wing": "#5E9FDB", "belly": "#E3F1FC", "beak": "#FFB347"},
    "เหลือง": {"body": "#FFD95C", "wing": "#F2B93A", "belly": "#FFF3C4", "beak": "#FF9A47"},
    "แดง": {"body": "#F08A72", "wing": "#D9654F", "belly": "#FFE1D6", "beak": "#FFC247"},
    "น้ำตาล": {"body": "#C29A72", "wing": "#99714C", "belly": "#F3E4D2", "beak": "#FFB347"},
}
DUCKS = {
    "ขาว": {"body": "#FFFFFF", "wing": "#EEF1F5", "bill": "#FFA94D"},
    "เหลือง": {"body": "#FFE07A", "wing": "#F5C94E", "bill": "#FF9F43"},
    "น้ำตาล": {"body": "#C29A72", "head": "#A97F57", "wing": "#8F6845", "bill": "#E3A13E"},
    "หัวเขียว": {"body": "#C9CED6", "head": "#4F9E6A", "wing": "#9AA3B0", "bill": "#F2C14E", "ring": "#FFFFFF"},
}


def pose(svg_text, moves=None, hide=(), extra=""):
    """A keyframe of a gait: `moves` maps a part id to an SVG transform, `hide` drops parts, `extra` is drawn on top."""
    for gid, t in (moves or {}).items():
        svg_text = svg_text.replace(f'<g id="{gid}">', f'<g id="{gid}" transform="{t}">', 1)
    for gid in hide:
        svg_text = svg_text.replace(f'<g id="{gid}">', f'<g id="{gid}" opacity="0">', 1)
    if extra:
        svg_text = svg_text.replace("</g></svg>", extra + "</g></svg>")
    return svg_text


def water_line(y=128, seed=71):
    """Pond water over the lower half of a swimming bird: a band with a pen line on top and two light ripples."""
    a = pet_art(seed)
    top = [(30 + i * 14, y + (3 if i % 2 else -2)) for i in range(11)]
    band = a.shape(top + [(176, y + 14), (156, y + 30), (100, y + 36), (44, y + 30), (24, y + 14)], "#8FD0F2", jit=0.4, misreg=0, outline=False)
    line = a.line_(top, width=4, jit=0.3)
    rip = a.line_([(52, y + 18), (68, y + 14), (84, y + 18)], width=3, color="#D3F0FD", jit=0.2) + \
        a.line_([(118, y + 22), (134, y + 18), (150, y + 22)], width=3, color="#D3F0FD", jit=0.2)
    return a.group("water", band, line, rip)


# colour sets (natural colours; the app UI palette does not apply inside the garden)
CATS = {
    "ส้มลาย": {"body": "#F4A75B", "stripe": "#D27A2E", "belly": "#FFF3E2"},
    "ขาว": {"body": "#FFFFFF", "belly": None, "ear": "#FFC2CE"},
    "ดำ": {"body": "#474D60", "ear": "#FF9DB0"},
    "เทา": {"body": "#B9C0CC", "stripe": "#8E97A6", "belly": "#F4F6F9"},
}
# cat coats for the first pack (2027): patches and saddles, cut to the head/body by coat()
DARK, ORANGE, TABBY, TABBY_LINE = "#474D60", "#F4A75B", "#A99B86", "#675D4F"
CATS_COATS = {
    "สามสี": {"id": "calico", "body": "#FFFFFF", "ear": "#FFC2CE", "ear-l": DARK, "ear-r": ORANGE,
              "torso": [(DARK, [(48, 94), (80, 92), (96, 104), (94, 120), (80, 128), (62, 126), (48, 120)]),
                        (ORANGE, [(92, 94), (122, 95), (130, 108), (118, 120), (100, 118), (90, 106)]),
                        (ORANGE, [(46, 128), (62, 124), (72, 136), (64, 150), (48, 150)])],
              "head": [(ORANGE, [(150, 38), (184, 42), (186, 80), (170, 80), (158, 66), (148, 56)]),
                       (DARK, [(96, 40), (126, 38), (134, 56), (124, 70), (108, 76), (94, 70)])]},
    "สลิดขาว": {"id": "tabby-white", "body": "#FFFFFF", "ear": "#FFC2CE", "stripe": TABBY_LINE, "ear-l": TABBY, "ear-r": TABBY,
                "torso": [(TABBY, [(46, 90), (150, 90), (152, 118), (132, 121), (114, 118), (96, 124), (76, 121), (58, 126), (46, 124)])],
                "stripes": [[(66, 104), (69, 117)], [(78, 102), (81, 116)], [(90, 102), (93, 116)], [(102, 102), (104, 114)]],
                # tabby round the eyes, white muzzle, a narrow white blaze up between the eyes (like the reference cat)
                "head": [(TABBY, [(94, 38), (186, 38), (186, 92), (166, 94), (152, 92), (143, 84), (141, 60), (137, 60), (134, 84),
                                  (124, 94), (110, 95), (94, 92)])],
                "head_stripes": [[(128, 48), (130, 57)], [(140, 47), (140, 54)], [(152, 48), (150, 57)]]},
    "สลิด": {"id": "tabby", "body": "#B4A58E", "ear": "#FFA8B8", "stripe": TABBY_LINE,
             "stripes": [[(64, 105), (67, 119)], [(76, 102), (79, 117)], [(88, 101), (91, 116)], [(100, 101), (102, 114)], [(58, 124), (64, 134)]],
             "head_stripes": [[(129, 49), (131, 59)], [(140, 48), (140, 58)], [(151, 49), (149, 59)], [(104, 86), (111, 88)], [(173, 84), (166, 86)]]},
    "วัว": {"id": "cow", "body": "#FFFFFF", "ear": "#FFC2CE", "ear-l": DARK,
            "torso": [(DARK, [(68, 94), (106, 94), (110, 112), (98, 124), (80, 122), (66, 110)]),
                      (DARK, [(44, 124), (60, 122), (68, 138), (58, 152), (44, 150)])],
            "head": [(DARK, [(94, 38), (130, 36), (136, 58), (128, 72), (110, 78), (94, 72)])]},
}
DOGS = {
    "ทอง": {"body": "#E9BC72", "ear": "#C98E45", "muzzle": "#FFF3DE"},
    "น้ำตาล": {"body": "#A8703F", "ear": "#7E4F28", "muzzle": "#F2D3AE"},
    "ขาวจุด": {"body": "#FFFFFF", "spot": "#B07A47", "ear": "#B07A47", "muzzle": "#FFFFFF"},
    "ดำ": {"body": "#474D60", "ear": "#6A7186"},
}
RABBITS = {
    "ขาว": {"body": "#FFFFFF", "belly": "#FFFFFF", "tail": "#FFFFFF"},
    "เทา": {"body": "#C3C8D1", "belly": "#F3F4F7"},
    "น้ำตาล": {"body": "#C69568", "belly": "#F6E6D2"},
    "ครีม": {"body": "#F6DFB8", "belly": "#FFF8EC"},
}


# ------------------------------------------------------------------ props (natural colours)
G = {"grass": "#A8DA84", "grass2": "#B9E296", "tuft": "#5E9E45", "leaf": "#6DB34F", "leaf2": "#4F9238",
     "trunk": "#9A6A42", "wood": "#E3B577", "wood2": "#C9955A", "roof": "#E46F5A", "wall": "#F6DEB0",
     "door": "#7A543A", "soil": "#A0703F", "soil2": "#7E5530", "stone": "#C9CED6", "sky": "#CDEBFF"}


def blob(cx, cy, r, bumps=7, k=0.18, seed=1):
    """A cloud/canopy outline: circle with soft bumps."""
    rnd = random.Random(seed)
    pts = []
    n = bumps * 4
    for i in range(n):
        a = 2 * math.pi * i / n
        bump = 1 + k * (0.5 + 0.5 * math.cos(a * bumps)) + rnd.uniform(-0.03, 0.03)
        pts.append((cx + r * bump * math.cos(a), cy + r * 0.86 * bump * math.sin(a)))
    return pts


def tree(seed=41, w=230):
    a = Art(seed)
    trunk = a.shape([(102, 250), (106, 200), (108, 150), (104, 128), (126, 128), (122, 150), (124, 200), (130, 250)], G["trunk"])
    roots = a.line_([(98, 251), (132, 251)], width=3.0)
    canopy = a.shape(blob(115, 95, 82, bumps=7, seed=seed), G["leaf"], jit=1.1)
    shade = "".join(f'<path d="{cr(a.pen.jit(ellipse(x, y, 16, 10, 8), 0.8), True)}" fill="{G["leaf2"]}" fill-opacity="0.7"/>' for x, y in ((85, 120), (140, 112), (112, 70), (70, 80), (156, 74)))
    return svg(w, 262, a.group("trunk", trunk, roots) + a.group("canopy", canopy, shade), "Prop/tree")


def bush(seed=51):
    a = Art(seed)
    body = a.shape(blob(60, 44, 40, bumps=5, k=0.22, seed=seed), G["leaf"], jit=1.0)
    berries = "".join(a.dot(x, y, 3.6, "#E8555C") for x, y in ((40, 36), (66, 28), (82, 48), (52, 54)))
    base = a.line_([(26, 74), (94, 74)], width=2.6, color=G["leaf2"])
    return svg(120, 82, a.group("bush", body, berries, base), "Prop/bush")


def pet_house(seed=61):
    a = Art(seed)
    walls = a.shape(rrect(22, 62, 136, 86, 6, per_edge=5), G["wall"])
    planks = "".join(a.line_([(26, y), (154, y)], width=2.0, color=G["wood2"]) for y in (84, 106, 128))
    door = a.shape([(68, 148), (68, 104), (74, 92), (90, 86), (106, 92), (112, 104), (112, 148)], G["door"])
    roof = a.shape([(8, 70), (90, 14), (172, 70), (164, 78), (90, 26), (16, 78)], G["roof"])
    plate = a.shape(rrect(70, 56, 40, 16, 5, per_edge=3), "#FFFFFF", jit=0.4, wide=2.4)
    return svg(180, 156, a.group("house", walls, planks, door, roof, plate), "Prop/pet-house")


def fence(seed=71, posts=4):
    a = Art(seed)
    span = 64
    rails = a.shape(rrect(8, 30, span * (posts - 1) + 22, 12, 5, per_edge=6), G["wood"], jit=0.7) + \
        a.shape(rrect(8, 56, span * (posts - 1) + 22, 12, 5, per_edge=6), G["wood"], jit=0.7)
    ps = "".join(a.shape([(10 + i * span, 82), (10 + i * span, 18), (19 + i * span, 8), (28 + i * span, 18), (28 + i * span, 82)], G["wood"], jit=0.6)
                 for i in range(posts))
    return svg(span * (posts - 1) + 40, 90, a.group("fence", rails, ps), "Prop/fence")


def farm_plot(seed=81, crop="carrot"):
    a = Art(seed)
    soil = a.shape(rrect(8, 30, 214, 78, 16, per_edge=7), G["soil"])
    rows = "".join(a.line_([(26, y), (204, y)], width=3.0, color=G["soil2"]) for y in (52, 76, 98))
    plants = []
    for row, y in enumerate((48, 72, 94)):
        for i in range(5):
            x = 40 + i * 37 + (row % 2) * 8
            if crop == "carrot":
                plants.append(a.shape([(x - 5, y + 2), (x + 5, y + 2), (x, y + 12)], "#F08A3C", jit=0.4, misreg=0.4, wide=2.2))
                plants.append(a.line_([(x, y), (x - 6, y - 12)], width=2.6, color=G["leaf2"]))
                plants.append(a.line_([(x, y), (x + 1, y - 14)], width=2.6, color=G["leaf2"]))
                plants.append(a.line_([(x, y), (x + 7, y - 11)], width=2.6, color=G["leaf2"]))
            else:
                plants.append(a.shape(ellipse(x, y - 2, 9, 7, 10), "#8FD16B", jit=0.6, wide=2.4))
    return svg(232, 116, a.group("farm-plot", soil, rows, *plants), "Prop/farm-plot")


def flower(color="#FFFFFF", seed=91):
    a = Art(seed, line=2.4)
    stem = a.line_([(16, 40), (16, 22)], width=2.6, color=G["leaf2"])
    leaf = a.shape(ellipse(22, 32, 6, 3, 8, rot=-0.5), G["leaf"], jit=0.3, wide=2.0)
    petals = "".join(a.shape(ellipse(16 + 6 * math.cos(t), 14 + 6 * math.sin(t), 5, 4.2, 8, rot=t), color, jit=0.3, misreg=0.3, wide=2.0)
                     for t in [i * 2 * math.pi / 5 for i in range(5)])
    center = a.dot(16, 14, 3.6, "#FFD54A")
    return svg(32, 44, a.group("flower", stem, leaf, petals, center), "Prop/flower")


def tuft(seed=101, w=38):
    a = Art(seed, line=2.6)
    blades = "".join(a.line_([(x, 20), (x + d, 4 + abs(d))], width=2.6, color=G["tuft"]) for x, d in ((8, -4), (14, -1), (19, 3), (25, 1), (30, 5)))
    return svg(w, 24, a.group("tuft", blades), "Prop/grass-tuft")


def stone(seed=111):
    a = Art(seed, line=2.6)
    return svg(40, 26, a.group("stone", a.shape(ellipse(20, 14, 16, 9, 10), G["stone"], jit=0.8)), "Prop/stone")


def cloud(seed=121, fill="#FFFFFF", ink="#8DB4DC"):
    """Puffy top (overlapping circles), gently flat bottom."""
    a = Art(seed, line=2.6)
    rnd = random.Random(seed)
    pts = [(18, 62), (12, 50), (22, 38)]
    for cx, cy, r in ((44, 34, 20), (78, 22, 26), (114, 28, 22), (144, 42, 16)):
        cx += rnd.uniform(-3, 3)
        pts += [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in (math.pi * 1.15, math.pi * 1.5, math.pi * 1.85)]
    pts += [(160, 56), (150, 66), (110, 68), (70, 69), (34, 67)]
    return svg(170, 80, a.group("cloud", a.shape(pts, fill, jit=0.8, ink=ink)), "Sky/cloud")
