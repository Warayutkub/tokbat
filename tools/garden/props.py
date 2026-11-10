"""Garden props collection, drawn the way the app mascot is drawn.

Rules (same as ชอล์ก and the pets): navy #22304A pen outline, 5 px on screen for big things (4 px for small ones),
flat fills, no shading beyond a couple of flat patches, few detail lines (3 px). Every prop is drawn at its real
on-screen size (scale 1 next to a pet in its 200 x 180 box), so it can be placed without rescaling the line.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from draw import Art, INK, blob, ellipse, rrect, svg  # noqa: E402

C = dict(
    leaf="#6DB34F", leaf2="#4F9238", leafL="#93CF67", pine="#3F8F5A", pine2="#2F7449", stem="#4F9238",
    trunk="#9A6A42", trunkL="#C69A6B", trunkD="#7A5232", pinkT="#FFB7CB", pinkT2="#F58FAE", mango="#FFC23D",
    wood="#E3B577", wood2="#C9955A", woodD="#A9733F", roof="#E46F5A", wall="#F6DEB0", door="#7A543A",
    red="#E8555C", redL="#F27C7C", cream="#FFF3DE", card="#DDAE72", card2="#C2924F", cardD="#9C6E3A",
    blue="#7DB9F0", blueL="#C4E2FB", water="#8FD0F2", waterL="#D3F0FD", carpet="#B9C6D8", carpet2="#9EADC3",
    yellow="#FFD54A", orange="#F08A3C", soil="#A0703F", soil2="#7E5530", stone="#C9CED6", stone2="#AEB5C0",
    hay="#F2CE6B", hay2="#D4A93E", twine="#A8743F", pot="#D9774E", potL="#E99470", rope="#EAD6AA", rope2="#C7AA74",
    post="#56647D", glass="#FFE69A", pink="#FF9DB5", pink2="#F27497", white="#FFFFFF", brown="#8A5A33",
    cactus="#5DAA6A", cabbage="#A9D86E", shirt="#6FA8DC", sack="#F3DFB8",
)


def A(seed, line=5.0):
    return Art(seed, line=line, k=1.0)


def leaf_pts(p0, p1, width, bend=0.0, n=8):
    """A pointed leaf along a gently bent line from p0 (base) to p1 (tip)."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    cx, cy = (x0 + x1) / 2 + nx * bend, (y0 + y1) / 2 + ny * bend
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
        tx = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx)
        ty = 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
        tl = math.hypot(tx, ty) or 1.0
        px, py = -ty / tl, tx / tl
        w = width / 2 * math.sin(math.pi * t) ** 0.7
        left.append((x + px * w, y + py * w))
        right.append((x - px * w, y - py * w))
    return left + right[::-1][1:-1]


def scallop(cx, cy, r_out, r_in, n, rot=0.0):
    """Flower / rosette outline: n round petals."""
    return [(cx + (r_out if i % 2 == 0 else r_in) * math.cos(rot + math.pi * i / n),
             cy + (r_out if i % 2 == 0 else r_in) * math.sin(rot + math.pi * i / n)) for i in range(2 * n)]


def edges(corners, k=4):
    """Polygon corners with extra points along each edge, so the smoothing keeps straight sides and crisp-ish corners."""
    out = []
    n = len(corners)
    for i in range(n):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % n]
        out += [(x0 + (x1 - x0) * t / k, y0 + (y1 - y0) * t / k) for t in range(k)]
    return out


def rect(x, y, w, h, r=4, k=3):
    return rrect(x, y, w, h, r, per_edge=k)


def face(a: Art, cx, cy, s=1.0):
    """The mascot's face (for the scarecrow): two white eyes, plain pupils, pink cheeks, a small smile."""
    out = []
    for gid, ex in (("eye-l", cx - 11 * s), ("eye-r", cx + 11 * s)):
        out.append(a.group(gid, a.shape(ellipse(ex, cy, 8.5 * s, 9 * s, 10), C["white"], jit=0.3, misreg=0, wide=3.2),
                           a.dot(ex + 1.5 * s, cy + 1 * s, 3.8 * s, INK)))
    out.append(a.shape(ellipse(cx - 20 * s, cy + 13 * s, 5 * s, 3.2 * s, 8), "#FFA8B8", jit=0.2, misreg=0, outline=False))
    out.append(a.shape(ellipse(cx + 20 * s, cy + 13 * s, 5 * s, 3.2 * s, 8), "#FFA8B8", jit=0.2, misreg=0, outline=False))
    out.append(a.line_([(cx - 6 * s, cy + 14 * s), (cx, cy + 18 * s), (cx + 6 * s, cy + 14 * s)], width=3, jit=0.2))
    return a.group("face", *out)


# ================================================================= trees
def tree_round(seed=41, leaf=C["leaf"], extra=None, name="Prop/tree-round"):
    a = A(seed)
    trunk = a.shape([(92, 246), (95, 200), (96, 160), (114, 160), (115, 200), (121, 246)], C["trunk"], jit=0.6, misreg=0)
    canopy = a.shape(blob(105, 100, 80, bumps=6, k=0.16, seed=seed), leaf, jit=1.0, misreg=0)
    patches = "" if extra else "".join(
        a.shape(ellipse(x, y, rx, ry, 9, rot=r), C["leaf2"], jit=0.5, misreg=0, outline=False, opacity=0.55)
        for x, y, rx, ry, r in ((136, 128, 17, 10, -0.3), (78, 138, 15, 9, 0.2), (152, 86, 12, 8, -0.5)))
    return svg(210, 250, a.group("trunk", trunk) + a.group("canopy", canopy, patches, (extra or (lambda _a: ""))(a)), name)


def tree_pink(seed=42):
    def flowers(a):
        pts = ((60, 70), (92, 46), (130, 58), (156, 96), (70, 120), (112, 100), (140, 140), (90, 150), (46, 104), (116, 46))
        return "".join(a.shape(scallop(x, y, 7, 4.5, 5, rot=i), C["white"] if i % 2 else C["pinkT2"], jit=0.2, misreg=0, outline=False)
                       for i, (x, y) in enumerate(pts))
    return tree_round(seed, C["pinkT"], flowers, "Prop/tree-pink")


def tree_mango(seed=43):
    def fruit(a):
        return "".join(a.shape(ellipse(x, y, 7.5, 10, 10, rot=0.35), C["mango"], jit=0.3, misreg=0, wide=3.2)
                       for x, y in ((66, 92), (104, 120), (146, 104), (88, 150), (128, 150), (118, 64)))
    return tree_round(seed, C["leaf"], fruit, "Prop/tree-mango")


def pine(seed=44):
    a = A(seed)
    trunk = a.shape(rect(74, 196, 22, 52, 4), C["trunk"], jit=0.5, misreg=0)
    tiers = []
    for top, bot, hw in ((96, 206, 74), (58, 160, 60), (16, 112, 44)):
        cx = 85
        pts = [(cx, top), (cx + hw * 0.5, (top + bot) / 2), (cx + hw, bot), (cx + hw * 0.5, bot + 8), (cx, bot + 2),
               (cx - hw * 0.5, bot + 8), (cx - hw, bot), (cx - hw * 0.5, (top + bot) / 2)]
        tiers.append(a.shape(pts, C["pine"], jit=0.7, misreg=0))
    return svg(170, 252, a.group("trunk", trunk) + a.group("tiers", *tiers), "Prop/pine")


def coconut(seed=45):
    a = A(seed)
    trunk = a.tube([(130, 276), (126, 230), (116, 180), (106, 136), (102, 108)], C["trunkL"], 20, tip=0.8)
    rings = "".join(a.line_([(x - 9, y + 2), (x + 9, y - 1)], width=3, color=C["trunk"], jit=0.3)
                    for x, y in ((127, 252), (122, 220), (115, 188), (109, 158), (105, 132)))
    back = [leaf_pts((102, 100), tip, 30, bend) for tip, bend in (((26, 70), 14), ((150, 34), -10), ((70, 26), 12))]
    front = [leaf_pts((102, 100), tip, 32, bend) for tip, bend in (((16, 128), -16), ((200, 84), -14), ((180, 140), 12), ((112, 22), 6))]
    nuts = "".join(a.shape(ellipse(x, y, 10, 10, 10), C["brown"], jit=0.3, misreg=0, wide=3.6) for x, y in ((90, 112), (106, 118), (118, 108)))
    return svg(220, 280, a.group("trunk", trunk, rings) + a.group("fronds-back", *[a.shape(p, C["leaf2"], jit=0.5, misreg=0) for p in back])
               + a.group("coconuts", nuts) + a.group("fronds", *[a.shape(p, C["leaf"], jit=0.5, misreg=0) for p in front]), "Prop/coconut")


def sapling(seed=46):
    a = A(seed, 4.5)
    mound = a.shape(ellipse(48, 100, 36, 10, 12), C["soil"], jit=0.5, misreg=0)
    stem = a.line_([(48, 98), (47, 74), (49, 54)], width=4.5, color=C["stem"])
    leaves = a.shape(leaf_pts((48, 60), (14, 44), 24, -6), C["leafL"], jit=0.4, misreg=0) + \
        a.shape(leaf_pts((48, 56), (84, 34), 26, 6), C["leafL"], jit=0.4, misreg=0)
    return svg(96, 114, a.group("sapling", stem, leaves, mound), "Prop/sapling")


# ================================================================= bushes & flowers
def bush(seed=51, berries=False):
    a = A(seed)
    body = a.shape(blob(70, 52, 46, bumps=5, k=0.22, seed=seed), C["leaf"], jit=0.9, misreg=0)
    extra = "".join(a.dot(x, y, 5, C["red"]) for x, y in ((46, 40), (76, 30), (96, 54), (58, 62), (84, 72))) if berries else \
        a.shape(ellipse(92, 66, 16, 8, 8, rot=-0.2), C["leaf2"], jit=0.4, misreg=0, outline=False, opacity=0.55)
    return svg(140, 98, a.group("bush", body, extra), "Prop/berry-bush" if berries else "Prop/bush")


def sunflower(seed=52):
    a = A(seed)
    stem = a.line_([(50, 196), (48, 140), (50, 84)], width=5, color=C["stem"])
    leaves = a.shape(leaf_pts((49, 152), (14, 128), 26, -8), C["leaf"], jit=0.4, misreg=0) + \
        a.shape(leaf_pts((50, 130), (86, 110), 26, 8), C["leaf"], jit=0.4, misreg=0)
    head = a.shape(scallop(50, 56, 42, 31, 12), C["yellow"], jit=0.5, misreg=0)
    center = a.shape(ellipse(50, 56, 18, 18, 12), C["brown"], jit=0.4, misreg=0, wide=4)
    seeds = "".join(a.dot(x, y, 2.2, "#6E4426") for x, y in ((44, 50), (54, 49), (48, 60), (57, 60), (41, 60)))
    return svg(100, 200, a.group("stem", stem, leaves) + a.group("flower", head, center, seeds), "Prop/sunflower")


def tulips(seed=53):
    a = A(seed, 4.5)
    out = []
    for x, y, col, top in ((34, 58, C["red"], 30), (66, 44, C["pink"], 18), (98, 60, C["yellow"], 32)):
        out.append(a.line_([(x, 124), (x + 1, 90), (x, y + 12)], width=4.5, color=C["stem"]))
    out.append(a.shape(leaf_pts((40, 124), (10, 76), 22, -6), C["leaf"], jit=0.4, misreg=0))
    out.append(a.shape(leaf_pts((88, 124), (122, 82), 22, 6), C["leaf"], jit=0.4, misreg=0))
    for x, y, col, top in ((34, 58, C["red"], 30), (66, 44, C["pink"], 18), (98, 60, C["yellow"], 32)):
        cup = [(x - 14, y - 12), (x - 6, y - 3), (x, y - 15), (x + 6, y - 3), (x + 14, y - 12), (x + 13, y + 6), (x, y + 15), (x - 13, y + 6)]
        out.append(a.shape(cup, col, jit=0.4, misreg=0))
    return svg(132, 130, a.group("tulips", *out), "Prop/tulips")


def pot(a: Art, x, top, w, h):
    rim = a.shape(rect(x - 4, top, w + 8, 16, 4), C["potL"], jit=0.4, misreg=0)
    body = a.shape([(x, top + 14), (x + w, top + 14), (x + w - 7, top + h), (x + 7, top + h)], C["pot"], jit=0.4, misreg=0)
    return a.group("pot", body, rim)


def cactus(seed=54):
    a = A(seed)
    arms = a.tube([(40, 82), (22, 78), (20, 56)], C["cactus"], 13) + a.tube([(62, 66), (80, 62), (82, 44)], C["cactus"], 13)
    body = a.shape(rect(36, 24, 30, 92, 15, 4), C["cactus"], jit=0.5, misreg=0)
    lines = a.line_([(51, 34), (51, 104)], width=2.6, color="#3F8A4E", jit=0.3)
    flower = a.shape(scallop(51, 22, 9, 5.5, 5), C["pink"], jit=0.2, misreg=0, wide=3)
    return svg(104, 156, a.group("cactus", arms, body, lines, flower) + pot(a, 22, 104, 58, 48), "Prop/cactus")


def potted_plant(seed=55):
    a = A(seed)
    leaves = [a.shape(leaf_pts((60, 104), tip, 36, b), col, jit=0.5, misreg=0)
              for tip, b, col in (((18, 50), -10, C["leaf2"]), ((104, 54), 10, C["leaf2"]), ((40, 20), -8, C["leaf"]),
                                  ((86, 22), 8, C["leaf"]), ((60, 14), 0, C["leafL"]))]
    return svg(122, 158, a.group("leaves", *leaves) + pot(a, 32, 100, 56, 52), "Prop/potted-plant")


def mushrooms(seed=56):
    a = A(seed, 4.5)
    out = []
    for cx, base, cap_w, cap_h, stem_w, stem_h in ((40, 92, 34, 26, 16, 30), (84, 92, 24, 18, 12, 22)):
        out.append(a.shape(rect(cx - stem_w / 2, base - stem_h, stem_w, stem_h, 5), C["cream"], jit=0.4, misreg=0))
        cap = [(cx - cap_w, base - stem_h + 4), (cx - cap_w * 0.8, base - stem_h - cap_h * 0.7), (cx, base - stem_h - cap_h),
               (cx + cap_w * 0.8, base - stem_h - cap_h * 0.7), (cx + cap_w, base - stem_h + 4), (cx, base - stem_h + 2)]
        out.append(a.shape(cap, C["red"], jit=0.4, misreg=0))
        for dx, dy, r in ((-0.45, -0.5, 4.5), (0.15, -0.75, 3.5), (0.5, -0.3, 3)):
            out.append(a.dot(cx + dx * cap_w, base - stem_h + dy * cap_h, r * cap_w / 34 * 1.3, C["white"]))
    return svg(112, 98, a.group("mushrooms", *out), "Prop/mushrooms")


# ================================================================= pet homes & beds
def dog_house(seed=61):
    a = A(seed)
    walls = a.shape(rect(28, 70, 134, 94, 6, 5), C["wall"], jit=0.6, misreg=0)
    planks = "".join(a.line_([(34, y), (156, y)], width=3, color=C["wood2"], jit=0.4) for y in (94, 118, 142))
    door = a.shape([(70, 164), (70, 116), (78, 102), (95, 96), (112, 102), (120, 116), (120, 164)], C["door"], jit=0.5, misreg=0)
    roof = a.shape([(10, 80), (95, 14), (180, 80), (170, 92), (95, 32), (20, 92)], C["roof"], jit=0.5, misreg=0)
    plate = a.shape(rect(74, 50, 42, 18, 6), C["white"], jit=0.3, misreg=0, wide=3.5)
    return svg(190, 172, a.group("dog-house", walls, planks, door, roof, plate), "Prop/dog-house")


def cat_tower(seed=62):
    a = A(seed)
    base = a.shape(rect(14, 214, 132, 22, 8, 5), C["carpet"], jit=0.5, misreg=0)
    posts = []
    for x, y, h in ((42, 118, 98), (102, 64, 152)):
        posts.append(a.shape(rect(x, y, 18, h, 3), C["rope"], jit=0.4, misreg=0))
        posts += [a.line_([(x + 2, yy), (x + 16, yy - 6)], width=2.6, color=C["rope2"], jit=0.2) for yy in range(int(y) + 14, int(y + h) - 4, 12)]
    shelf = a.shape(rect(16, 106, 76, 18, 8, 4), C["carpet"], jit=0.5, misreg=0)
    bed = a.shape([(64, 40), (156, 40), (150, 64), (136, 74), (84, 74), (70, 64)], C["carpet"], jit=0.5, misreg=0)
    cushion = a.shape(ellipse(110, 42, 40, 7, 10), C["carpet2"], jit=0.3, misreg=0, wide=3.5)
    toy = a.line_([(28, 124), (27, 156)], width=2.6, jit=0.3) + a.shape(scallop(27, 162, 8, 6, 6), C["pink"], jit=0.2, misreg=0, wide=3)
    return svg(172, 240, a.group("cat-tower", base, *posts, shelf, toy, bed, cushion), "Prop/cat-tower")


def rabbit_hutch(seed=63):
    a = A(seed)
    legs = "".join(a.shape(rect(x, 140, 12, 30, 3), C["woodD"], jit=0.3, misreg=0) for x in (30, 156))
    box = a.shape(rect(20, 70, 156, 80, 6, 5), C["wood"], jit=0.5, misreg=0)
    mesh = a.shape(rect(34, 86, 78, 50, 4, 4), C["cream"], jit=0.4, misreg=0, wide=4)
    grid = "".join(a.line_([(x, 89), (x, 133)], width=2.2, color=C["stone2"], jit=0.2) for x in (50, 66, 82, 98)) + \
        "".join(a.line_([(37, y), (109, y)], width=2.2, color=C["stone2"], jit=0.2) for y in (102, 119))
    door = a.shape(rect(124, 86, 40, 50, 4), C["wood2"], jit=0.4, misreg=0, wide=4)
    knob = a.dot(156, 112, 3.4, INK)
    roof = a.shape([(8, 78), (21, 56), (34, 34), (99, 34), (164, 34), (177, 56), (190, 78), (99, 78)], C["roof"], jit=0.5, misreg=0)
    return svg(198, 174, a.group("rabbit-hutch", legs, box, mesh, grid, door, knob, roof), "Prop/rabbit-hutch")


def card_box(seed=64):
    a = A(seed)
    # open box seen from the front: back flap standing up, dark inside, two flaps folded out, front face
    flap_back = a.shape([(34, 42), (38, 26), (40, 12), (76, 12), (112, 12), (114, 26), (118, 42)], C["card2"], jit=0.4, misreg=0)
    inside = a.shape([(26, 48), (34, 38), (76, 38), (118, 38), (126, 48)], C["cardD"], jit=0.3, misreg=0, outline=False)
    flap_l = a.shape([(26, 48), (16, 38), (6, 26), (22, 22), (38, 20), (40, 34)], C["card"], jit=0.3, misreg=0)
    flap_r = a.shape([(126, 48), (136, 38), (146, 26), (130, 22), (114, 20), (112, 34)], C["card"], jit=0.3, misreg=0)
    front = a.shape(rect(24, 46, 104, 68, 3, 4), C["card"], jit=0.5, misreg=0)
    tape = a.shape(rect(66, 48, 20, 64, 1, 3), "#EBD3A2", jit=0.3, misreg=0, outline=False)
    paw = a.shape(ellipse(104, 94, 7, 6, 8), C["cardD"], jit=0.2, misreg=0, outline=False) + \
        "".join(a.dot(104 + dx, 84 + dy, 2.6, C["cardD"]) for dx, dy in ((-7, 2), (-2.5, -2), (2.5, -2), (7, 2)))
    return svg(152, 120, a.group("box", flap_back, inside, flap_l, flap_r, front, tape, paw), "Prop/card-box")


def pet_bed(seed=65):
    a = A(seed)
    outer = a.shape(ellipse(86, 54, 78, 30, 16), C["blue"], jit=0.6, misreg=0)
    inner = a.shape(ellipse(86, 50, 56, 17, 14), C["blueL"], jit=0.4, misreg=0, wide=4)
    bone = a.shape(bone_pts(70, 40, 0.5), C["white"], jit=0.2, misreg=0, wide=3)
    return svg(172, 90, a.group("pet-bed", outer, inner, bone), "Prop/pet-bed")


def teepee(seed=66):
    a = A(seed)
    poles = a.line_([(60, 6), (82, 40)], width=5, color=C["woodD"]) + a.line_([(92, 4), (72, 40)], width=5, color=C["woodD"])

    def lx(y):
        return 76 - (y - 26) * (68 / 134)

    def rx(y):
        return 76 + (y - 26) * (68 / 134)
    cloth = a.shape([(76, 26), (144, 160), (8, 160)], C["cream"], jit=0.5, misreg=0)
    bands = "".join(a.shape([(lx(y1) + 7, y1), (rx(y1) - 7, y1), (rx(y2) - 7, y2), (lx(y2) + 7, y2)], col, jit=0.3, misreg=0, outline=False)
                    for y1, y2, col in ((84, 98, C["pink"]), (114, 126, C["blue"])))
    door = a.shape([(76, 92), (104, 160), (48, 160)], "#5A4636", jit=0.4, misreg=0, wide=4)
    return svg(152, 166, a.group("teepee", poles, cloth, bands, door), "Prop/teepee")


# ================================================================= farm
def plot(a: Art, w, h):
    soil = a.shape(rect(8, 30, w - 16, h - 38, 16, 7), C["soil"], jit=0.6, misreg=0)
    rows = "".join(a.line_([(26, y), (w - 26, y)], width=3, color=C["soil2"], jit=0.4) for y in (60, 92))
    return soil, rows


def carrot_plot(seed=81):
    a = A(seed)
    soil, rows = plot(a, 232, 124)
    plants = []
    for row, y in enumerate((56, 88)):
        for i in range(4):
            x = 48 + i * 46 + (row % 2) * 14
            plants.append(a.line_([(x, y), (x - 7, y - 16)], width=3.6, color=C["leaf2"], jit=0.2))
            plants.append(a.line_([(x, y), (x + 1, y - 19)], width=3.6, color=C["leaf2"], jit=0.2))
            plants.append(a.line_([(x, y), (x + 8, y - 15)], width=3.6, color=C["leaf2"], jit=0.2))
            plants.append(a.shape([(x - 8, y), (x + 8, y), (x + 3, y + 9), (x, y + 13), (x - 3, y + 9)], C["orange"], jit=0.3, misreg=0, wide=3.4))
    return svg(232, 124, a.group("plot", soil, rows, *plants), "Prop/carrot-plot")


def cabbage_plot(seed=82):
    a = A(seed)
    soil, rows = plot(a, 232, 124)
    heads = []
    for row, y in enumerate((52, 84)):
        for i in range(4):
            x = 46 + i * 46 + (row % 2) * 14
            heads.append(a.shape(scallop(x, y, 17, 14, 7, rot=i), C["cabbage"], jit=0.4, misreg=0, wide=3.8))
            heads.append(a.shape(ellipse(x, y + 1, 8, 7, 9), C["leafL"], jit=0.3, misreg=0, wide=3))
    return svg(232, 124, a.group("plot", soil, rows, *heads), "Prop/cabbage-plot")


def tomato(seed=83):
    a = A(seed)
    mound = a.shape(ellipse(56, 150, 44, 10, 12), C["soil"], jit=0.5, misreg=0)
    stakes = a.line_([(30, 148), (32, 20)], width=5, color=C["woodD"]) + a.line_([(82, 148), (80, 24)], width=5, color=C["woodD"])
    leaves = [a.shape(leaf_pts(b, t, 30, bd), C["leaf"], jit=0.4, misreg=0)
              for b, t, bd in (((56, 140), (18, 96), -6), ((56, 140), (96, 92), 6), ((56, 104), (24, 56), -6), ((56, 100), (92, 52), 6), ((56, 80), (56, 24), 0))]
    fruit = []
    for x, y in ((38, 90), (74, 78), (54, 120), (80, 118), (44, 52)):
        fruit.append(a.shape(ellipse(x, y, 10, 9.5, 10), C["red"], jit=0.3, misreg=0, wide=3.6))
        fruit.append(a.shape(scallop(x, y - 8, 5, 2.5, 5), C["leaf2"], jit=0.1, misreg=0, outline=False))
    return svg(112, 162, a.group("tomato", stakes, *leaves, *fruit, mound), "Prop/tomato")


def watering_can(seed=84):
    a = A(seed, 4.5)
    spout = a.tube([(86, 66), (104, 50), (120, 32)], C["blue"], 9)
    rose = a.shape(ellipse(122, 30, 7, 10, 10, rot=0.7), C["blue"], jit=0.3, misreg=0, wide=4)
    handle = a.line_([(36, 34), (44, 12), (72, 10), (84, 32)], width=6.5)
    body = a.shape(rect(26, 30, 64, 54, 12, 4), C["blue"], jit=0.5, misreg=0)
    band = a.line_([(30, 46), (86, 46)], width=3, color=C["blueL"], jit=0.3)
    return svg(136, 92, a.group("watering-can", handle, spout, rose, body, band), "Prop/watering-can")


def hay_bale(seed=85):
    a = A(seed)
    bale = a.shape(rect(10, 16, 124, 62, 16, 5), C["hay"], jit=0.6, misreg=0)
    straw = "".join(a.line_([(x, y), (x + 8, y - 3)], width=2.6, color=C["hay2"], jit=0.3)
                    for x, y in ((24, 34), (58, 28), (100, 36), (32, 62), (70, 56), (110, 64), (82, 40)))
    bands = a.line_([(46, 18), (43, 47), (46, 76)], width=4, color=C["twine"]) + a.line_([(98, 18), (101, 47), (98, 76)], width=4, color=C["twine"])
    return svg(144, 84, a.group("hay", bale, straw, bands), "Prop/hay-bale")


def scarecrow(seed=86):
    a = A(seed)
    post = a.shape(rect(75, 80, 12, 140, 3), C["woodD"], jit=0.3, misreg=0)
    bar = a.shape(rect(18, 100, 126, 11, 3, 5), C["woodD"], jit=0.3, misreg=0)
    straw = "".join(a.line_(p, width=3.4, color=C["hay2"], jit=0.2) for p in (
        [(30, 112), (24, 126)], [(36, 112), (34, 128)], [(126, 112), (128, 128)], [(132, 112), (140, 126)], [(72, 176), (68, 190)], [(90, 176), (94, 190)]))
    shirt = a.shape([(44, 96), (118, 96), (112, 116), (104, 118), (106, 178), (56, 178), (58, 118), (50, 116)], C["shirt"], jit=0.5, misreg=0)
    patch = a.shape(rect(64, 140, 16, 14, 2), C["yellow"], jit=0.3, misreg=0, wide=3)
    head = a.shape(ellipse(81, 64, 30, 28, 14), C["sack"], jit=0.5, misreg=0)
    brim = a.shape(ellipse(81, 40, 42, 8, 14), C["hay"], jit=0.4, misreg=0)
    crown = a.shape([(62, 40), (66, 18), (81, 12), (96, 18), (100, 40)], C["hay"], jit=0.4, misreg=0)
    band = a.line_([(65, 33), (97, 33)], width=4, color=C["red"], jit=0.2)
    return svg(162, 222, a.group("scarecrow", post, straw, bar, shirt, patch, head, face(a, 81, 66, 0.95), brim, crown, band), "Prop/scarecrow")


# ================================================================= toys & bowls (small: 4 px outline)
def bowl(seed, fill, top_fill, name, extra=None):
    a = A(seed, 4)
    body = a.shape([(8, 22), (74, 22), (66, 46), (16, 46)], fill, jit=0.4, misreg=0)
    rim = a.shape(ellipse(41, 22, 34, 8, 14), top_fill, jit=0.3, misreg=0)
    return svg(82, 52, a.group("bowl", body, rim, (extra or (lambda _a: ""))(a)), name)


def food_bowl(seed=91):
    def kibble(a):
        return "".join(a.shape(ellipse(x, y, 4.2, 3.4, 7, rot=x), C["brown"], jit=0.2, misreg=0, outline=False)
                       for x, y in ((28, 20), (36, 17), (44, 20), (52, 17), (33, 23), (48, 23), (58, 21), (24, 22)))
    return bowl(seed, C["red"], C["redL"], "Prop/food-bowl", kibble)


def water_bowl(seed=92):
    def shine(a):
        return a.line_([(26, 21), (36, 19)], width=2.8, color=C["white"], jit=0.1)
    return bowl(seed, C["blue"], C["waterL"], "Prop/water-bowl", shine)


def ball(seed=93):
    a = A(seed, 4)
    b = a.shape(ellipse(24, 24, 19, 19, 12), C["red"], jit=0.4, misreg=0)
    stripe = a.line_([(10, 16), (22, 22), (38, 18)], width=4, color=C["white"], jit=0.2)
    return svg(48, 48, a.group("ball", b, stripe), "Prop/ball")


def bone_pts(x, y, s=1.0):
    pts = [(16, 12), (54, 12), (55, 5), (64, 4), (68, 10), (64, 16), (68, 22), (64, 28), (55, 27), (54, 20), (16, 20), (15, 27),
           (6, 28), (2, 22), (6, 16), (2, 10), (6, 4), (15, 5)]
    return [(x + px * s, y + py * s) for px, py in pts]


def bone(seed=94):
    a = A(seed, 4)
    return svg(76, 38, a.group("bone", a.shape(bone_pts(4, 3), C["cream"], jit=0.3, misreg=0)), "Prop/bone")


def yarn(seed=95):
    a = A(seed, 4)
    tail = a.line_([(40, 42), (50, 50), (46, 58), (58, 60)], width=3, color=C["pink2"], jit=0.2)
    b = a.shape(ellipse(28, 30, 21, 21, 12), C["pink"], jit=0.4, misreg=0)
    wraps = "".join(a.line_(p, width=3, color=C["pink2"], jit=0.2) for p in (
        [(14, 20), (26, 26), (36, 44)], [(12, 34), (28, 36), (42, 26)], [(22, 12), (30, 22), (44, 32)]))
    return svg(64, 64, a.group("yarn", tail, b, wraps), "Prop/yarn")


def frisbee(seed=96):
    a = A(seed, 4)
    disc = a.shape(ellipse(34, 18, 29, 11, 14), C["yellow"], jit=0.4, misreg=0)
    ring = a.shape(ellipse(34, 16, 16, 5, 12), C["mango"], jit=0.2, misreg=0, wide=2.8)
    return svg(68, 34, a.group("frisbee", disc, ring), "Prop/frisbee")


def scratch_post(seed=97):
    a = A(seed, 4.5)
    base = a.shape(rect(8, 120, 76, 18, 6, 4), C["carpet"], jit=0.4, misreg=0)
    pole = a.shape(rect(35, 32, 22, 92, 3), C["rope"], jit=0.3, misreg=0)
    turns = "".join(a.line_([(37, y), (55, y - 6)], width=2.4, color=C["rope2"], jit=0.2) for y in range(46, 122, 11))
    cap = a.shape(rect(26, 20, 40, 14, 5), C["carpet"], jit=0.3, misreg=0)
    toy = a.line_([(62, 30), (72, 46), (70, 62)], width=2.4, jit=0.2) + a.shape(ellipse(70, 68, 7, 7, 9), C["yellow"], jit=0.2, misreg=0, wide=3)
    return svg(92, 142, a.group("scratch-post", base, pole, turns, cap, toy), "Prop/scratch-post")


# ================================================================= garden decor
def bench(seed=101):
    a = A(seed)
    legs = "".join(a.shape(rect(x, 14, 11, 92, 3), C["woodD"], jit=0.3, misreg=0) for x in (32, 140))
    slats = a.shape(rect(20, 20, 144, 14, 5, 6), C["wood"], jit=0.4, misreg=0) + a.shape(rect(20, 40, 144, 14, 5, 6), C["wood"], jit=0.4, misreg=0)
    seat = a.shape(rect(10, 62, 164, 16, 6, 6), C["wood"], jit=0.4, misreg=0)
    return svg(184, 110, a.group("bench", legs, slats, seat), "Prop/bench")


def lamp_post(seed=102):
    a = A(seed, 4.5)
    base = a.shape(rect(20, 186, 32, 12, 4), C["post"], jit=0.3, misreg=0)
    pole = a.shape(rect(31, 56, 10, 134, 3), C["post"], jit=0.3, misreg=0)
    glass = a.shape(rect(20, 24, 32, 30, 5), C["glass"], jit=0.3, misreg=0)
    cap = a.shape([(14, 26), (36, 8), (58, 26)], C["post"], jit=0.3, misreg=0)
    foot = a.shape(rect(16, 52, 40, 8, 3), C["post"], jit=0.3, misreg=0)
    return svg(72, 202, a.group("lamp", base, pole, glass, cap, foot), "Prop/lamp-post")


def mailbox(seed=103):
    a = A(seed, 4.5)
    post = a.shape(rect(36, 62, 12, 78, 3), C["woodD"], jit=0.3, misreg=0)
    box = a.shape([(10, 66), (10, 38), (16, 24), (42, 18), (68, 24), (74, 38), (74, 66)], C["red"], jit=0.4, misreg=0)
    slot = a.line_([(26, 44), (58, 44)], width=3, jit=0.2)
    flag = a.line_([(80, 62), (80, 26)], width=4) + a.shape([(80, 26), (96, 30), (80, 38)], C["yellow"], jit=0.2, misreg=0, wide=3.5)
    return svg(110, 142, a.group("mailbox", post, box, slot, flag), "Prop/mailbox")


def signpost(seed=104):
    a = A(seed)
    post = a.shape(rect(52, 40, 13, 98, 3), C["woodD"], jit=0.3, misreg=0)
    board = a.shape([(10, 20), (51, 20), (92, 20), (103, 29), (114, 39), (103, 48), (92, 58), (51, 58), (10, 58), (9, 39)], C["wood"], jit=0.4, misreg=0)
    paw = a.shape(ellipse(52, 44, 8, 6.5, 9), C["woodD"], jit=0.2, misreg=0, outline=False) + \
        "".join(a.dot(52 + dx, 33 + dy, 3, C["woodD"]) for dx, dy in ((-8, 3), (-3, -1.5), (3, -1.5), (8, 3)))
    return svg(120, 140, a.group("signpost", post, board, paw), "Prop/signpost")


def picket_fence(seed=105):
    a = A(seed, 4.5)
    rails = a.shape(rect(6, 34, 178, 11, 4, 6), C["white"], jit=0.4, misreg=0) + a.shape(rect(6, 60, 178, 11, 4, 6), C["white"], jit=0.4, misreg=0)
    pickets = "".join(a.shape([(x, 88), (x, 22), (x + 9, 8), (x + 18, 22), (x + 18, 88)], C["white"], jit=0.4, misreg=0) for x in (12, 48, 84, 120, 156))
    return svg(190, 92, a.group("picket-fence", rails, pickets), "Prop/picket-fence")


def wood_fence(seed=106):
    a = A(seed)
    rails = a.shape(rect(8, 30, 170, 13, 5, 6), C["wood"], jit=0.5, misreg=0) + a.shape(rect(8, 58, 170, 13, 5, 6), C["wood"], jit=0.5, misreg=0)
    posts = "".join(a.shape([(x, 88), (x, 18), (x + 10, 8), (x + 20, 18), (x + 20, 88)], C["wood"], jit=0.5, misreg=0) for x in (10, 82, 156))
    return svg(186, 92, a.group("wood-fence", rails, posts), "Prop/wood-fence")


# ================================================================= ground (always under everything; pets walk over it)
def pond(seed=111):
    a = A(seed)
    water = a.shape(ellipse(112, 54, 100, 40, 18), C["water"], jit=1.2, misreg=0)
    ripples = a.line_([(52, 40), (70, 34), (88, 38)], width=3, color=C["waterL"], jit=0.2) + \
        a.line_([(128, 70), (148, 64), (166, 68)], width=3, color=C["waterL"], jit=0.2)
    pad = a.shape([(150, 38), (138, 30), (142, 18), (158, 14), (172, 22), (172, 34), (160, 40), (156, 30)], C["leaf"], jit=0.3, misreg=0, wide=3.6)
    lotus = a.shape(scallop(164, 26, 7, 4, 5), C["pink"], jit=0.2, misreg=0, wide=3)
    stones = "".join(a.shape(ellipse(x, y, rx, ry, 9), C["stone"], jit=0.3, misreg=0, wide=4)
                     for x, y, rx, ry in ((22, 70, 14, 8), (200, 44, 12, 7), (60, 92, 12, 6)))
    return svg(224, 104, a.group("pond", water, ripples, pad, lotus, stones), "Prop/pond")


def stepping_stones(seed=112):
    a = A(seed, 4.5)
    st = "".join(a.shape(ellipse(x, y, rx, ry, 11, rot=r), C["stone"], jit=0.5, misreg=0) for x, y, rx, ry, r in (
        (26, 50, 20, 11, 0.1), (74, 30, 18, 10, -0.1), (122, 48, 21, 11, 0.05), (170, 28, 18, 10, -0.15)))
    return svg(196, 66, a.group("stepping-stones", st), "Prop/stepping-stones")


def picnic_mat(seed=113):
    a = A(seed)
    sl = 26 / 74

    def L(y):
        return 30 - (y - 10) * sl

    def R(y):
        return 176 - (y - 10) * sl
    base = a.shape(edges([(30, 10), (176, 10), (150, 84), (4, 84)]), C["red"], jit=0.4, misreg=0, outline=False)
    bands = "".join(a.shape(edges([(L(y1) + 4, y1), (R(y1) - 4, y1), (R(y2) - 4, y2), (L(y2) + 4, y2)], 6), C["white"], jit=0.1, misreg=0, outline=False, opacity=0.5)
                    for y1, y2 in ((20, 30), (42, 52), (64, 74)))
    cols = "".join(a.shape(edges([(t - 1, 13), (t + 11, 13), (t + 12 - 26, 81), (t - 26, 81)], 6), C["white"], jit=0.1, misreg=0, outline=False, opacity=0.5)
                   for t in (46, 76, 106, 136))
    edge = a.shape(edges([(32, 11), (174, 11), (149, 83), (6, 83)]), None, jit=0.4, misreg=0)
    return svg(184, 94, a.group("picnic-mat", base, bands, cols, edge), "Prop/picnic-mat")


def grass_tuft(seed=114):
    a = A(seed, 4)
    blades = "".join(a.line_([(x, 30), (x + d, 6 + abs(d))], width=4, color=C["leaf2"], jit=0.3) for x, d in ((10, -6), (18, -2), (25, 3), (32, 1), (40, 7)))
    return svg(52, 34, a.group("tuft", blades), "Prop/grass-tuft")


def stones(seed=115):
    a = A(seed, 4)
    st = "".join(a.shape(ellipse(x, y, rx, ry, 10), c, jit=0.4, misreg=0) for x, y, rx, ry, c in (
        (24, 28, 18, 11, C["stone"]), (52, 32, 12, 8, C["stone2"]), (44, 18, 9, 6, C["stone"])))
    return svg(72, 44, a.group("stones", st), "Prop/stones")


def flower_patch(seed=116):
    a = A(seed, 3.6)
    out = []
    for x, y, col in ((18, 34, C["white"]), (40, 24, C["pink"]), (62, 36, C["yellow"]), (84, 26, C["white"]), (100, 38, C["pink"])):
        out.append(a.line_([(x, y + 6), (x, y + 16)], width=3.4, color=C["stem"], jit=0.1))
        out.append(a.shape(scallop(x, y, 8, 5, 5, rot=x), col, jit=0.2, misreg=0, wide=3))
        out.append(a.dot(x, y, 2.6, C["mango"]))
    return svg(118, 56, a.group("flower-patch", *out), "Prop/flower-patch")


# ================================================================= rain only
def puddle(seed=131, w=150):
    """Rain puddle (ground): soft blue, its own blue line instead of navy, with two ripple rings."""
    a = A(seed, 3.6)
    k = w / 150
    water = a.shape(ellipse(75 * k, 26, 68 * k, 17, 16), "#B9DDF2", jit=0.8, misreg=0, ink="#6E9CC2")
    rings = a.shape(ellipse(56 * k, 24, 15, 4.5, 12), None, jit=0.2, misreg=0, wide=2.4, ink=C["white"]) + \
        a.shape(ellipse(98 * k, 30, 9, 3, 10), None, jit=0.2, misreg=0, wide=2.2, ink=C["white"])
    return svg(w, 50, a.group("puddle", water, rings), "Prop/puddle")


def taro_leaf(seed=132):
    """ใบบอน: a big leaf on a bent stem — a pet can sit under it out of the rain."""
    a = A(seed)
    stem = a.line_([(52, 196), (60, 150), (78, 100), (96, 64)], width=6, color=C["stem"])
    leaf = a.shape([(8, 80), (26, 48), (66, 26), (110, 20), (150, 30), (174, 56), (178, 86), (152, 72), (122, 66), (96, 74), (70, 64), (38, 70)],
                   C["leaf"], jit=0.8, misreg=0)
    veins = "".join(a.line_(p, width=3, color=C["leaf2"], jit=0.3) for p in (
        [(96, 70), (64, 44), (34, 56)], [(96, 70), (100, 32)], [(96, 70), (132, 42), (160, 56)]))
    return svg(184, 200, a.group("stem", stem) + a.group("leaf", leaf, veins), "Prop/taro-leaf")


CATALOG = [
    ("ต้นไม้", None, [("ต้นไม้พุ่มกลม", tree_round), ("ต้นสน", pine), ("ต้นมะพร้าว", coconut), ("ชมพูพันธุ์ทิพย์", tree_pink),
                      ("ต้นมะม่วง", tree_mango), ("ต้นกล้า", sapling)]),
    ("พุ่มไม้ & ดอกไม้", None, [("พุ่มไม้", bush), ("พุ่มเบอร์รี่", lambda: bush(57, berries=True)), ("ทานตะวัน", sunflower), ("ทิวลิป", tulips),
                               ("กระบองเพชร", cactus), ("ไม้กระถาง", potted_plant), ("ใบบอน", taro_leaf), ("เห็ด", mushrooms)]),
    ("บ้าน & ที่นอนสัตว์", None, [("บ้านหมา", dog_house), ("คอนโดแมว", cat_tower), ("บ้านกระต่าย", rabbit_hutch), ("กล่องกระดาษ", card_box),
                                 ("เบาะนอน", pet_bed), ("เต็นท์", teepee)]),
    ("ฟาร์ม", None, [("แปลงแครอท", carrot_plot), ("แปลงกะหล่ำ", cabbage_plot), ("ต้นมะเขือเทศ", tomato), ("บัวรดน้ำ", watering_can),
                    ("ฟางก้อน", hay_bale), ("หุ่นไล่กา", scarecrow)]),
    ("ของเล่น & ชาม", None, [("ชามอาหาร", food_bowl), ("ชามน้ำ", water_bowl), ("ลูกบอล", ball), ("กระดูก", bone), ("ไหมพรม", yarn),
                            ("จานร่อน", frisbee), ("ที่ลับเล็บ", scratch_post)]),
    ("ตกแต่งสวน", None, [("ม้านั่ง", bench), ("เสาไฟ", lamp_post), ("ตู้จดหมาย", mailbox), ("ป้ายไม้", signpost), ("รั้วขาว", picket_fence),
                        ("รั้วไม้", wood_fence)]),
    ("พื้น", "วางใต้ทุกอย่าง สัตว์เดินทับได้", [("บ่อน้ำ", pond), ("ทางเดินหิน", stepping_stones), ("ผ้าปิกนิก", picnic_mat), ("หย่อมหญ้า", grass_tuft),
                                                ("ก้อนหิน", stones), ("ดอกไม้เล็ก", flower_patch)]),
]


def sheet_html():
    rows = []
    for title, note, items in CATALOG:
        cells = "".join(f'<div class="c"><div class="art">{fn()}</div><p>{name}</p></div>' for name, fn in items)
        n = f' <small>· {note}</small>' if note else ""
        rows.append(f'<h2>{title}{n}</h2><div class="row">{cells}</div>')
    return ("<html><head><meta charset='utf-8'><style>body{margin:20px;background:#F3F8EC;font:600 14px 'Leelawadee UI';color:#22304A}"
            ".row{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap}.c{background:#E2F1D3;border-radius:14px;padding:12px 14px 8px;"
            "display:flex;flex-direction:column;align-items:center;justify-content:flex-end;min-width:100px}.c p{margin:6px 0 0}"
            "h2{margin:18px 0 8px;font-size:18px}small{font-weight:500;opacity:.7}</style></head><body>" + "".join(rows) + "</body></html>")


if __name__ == "__main__":
    import preview
    print(preview.shoot(sheet_html(), "props", 1500, 2150, scale=1))
