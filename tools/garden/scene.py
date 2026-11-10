"""Compose the garden (1280 x 800): sky, hills, ground, tufts, props and pets, drawn back-to-front by their feet (y)."""
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import draw  # noqa: E402
import props  # noqa: E402
from draw import INK, G, cr  # noqa: E402

W, H, HORIZON = 1280, 800, 330


def inner(svg_text):
    """Strip the outer <svg> so the drawing can be placed with a nested <svg x= y=>."""
    head, rest = svg_text.split(">", 1)
    vb = head.split('viewBox="')[1].split('"')[0]
    return vb, rest.rsplit("</svg>", 1)[0]


def place(svg_text, x, y, scale=1.0, flip=False, gid=None):
    vb, body = inner(svg_text)
    _, _, w, h = (float(v) for v in vb.split())
    t = f"translate({x:.1f} {y:.1f}) scale({-scale if flip else scale} {scale})"
    if flip:
        t = f"translate({x + w * scale:.1f} {y:.1f}) scale({-scale} {scale})"
    return f'<g id="{gid or "item"}" transform="{t}">{body}</g>', y + h * scale


PALETTE = {
    "day": dict(sky=("#BFE4FF", "#EAF7FF"), far="#C4E7AA", farL="#8CC273", near="#ADDA8E", nearL="#76B05C", ground=G["grass"], patch=G["grass2"]),
    "night": dict(sky=("#1D2B4F", "#3B4F7E"), far="#5E7F6A", farL="#3E5C4C", near="#557564", nearL="#38564A", ground="#4F7457", patch="#5A8263"),
    "night-rain": dict(sky=("#232E47", "#3F4C68"), far="#566F64", farL="#3A5148", near="#4F6A5D", nearL="#354C42", ground="#4A6B52", patch="#55785D"),
    "rain": dict(sky=("#9AACC0", "#D3DCE6"), far="#B4C9AE", farL="#8DA688", near="#A0BE97", nearL="#7C9B76", ground="#97C27D", patch="#A6CC8E"),
}


def mode_of(mode):
    return "night" if mode is True else "day" if mode in (False, None) else mode


def background(mode="day"):
    mode = mode_of(mode)
    P = PALETTE[mode]
    rnd = random.Random(5)
    a = draw.Art(3)
    sky_top, sky_low = P["sky"]
    defs = (f'<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{sky_top}"/>'
            f'<stop offset="1" stop-color="{sky_low}"/></linearGradient></defs>')
    sky = f'<rect width="{W}" height="{HORIZON + 20}" fill="url(#sky)"/>'
    far = [(-20, 300)] + [(x, 250 + 30 * ((i % 3) - 1) + rnd.uniform(-8, 8)) for i, x in enumerate(range(0, W + 120, 160))] + [(W + 40, 300), (W + 40, 380), (-20, 380)]
    near = [(-20, 330)] + [(x, 300 + 22 * ((i % 2) * 2 - 1) + rnd.uniform(-6, 6)) for i, x in enumerate(range(-40, W + 160, 210))] + [(W + 40, 330), (W + 40, 400), (-20, 400)]
    # far things get a softer, coloured pen line (air between us and them); the navy ink is for the foreground
    hills = (f'<path d="{cr(a.pen.jit(far, 1), True)}" fill="{P["far"]}"/>' + a.line_(far[1:-3], width=2.6, color=P["farL"]) +
             f'<path d="{cr(a.pen.jit(near, 1), True)}" fill="{P["near"]}"/>' + a.line_(near[1:-3], width=2.8, color=P["nearL"]))
    ground = f'<rect y="{HORIZON}" width="{W}" height="{H - HORIZON}" fill="{P["ground"]}"/>'
    patches = "".join(f'<path d="{cr(a.pen.jit(draw.ellipse(x, y, rx, ry, 12), 2), True)}" fill="{P["patch"]}" fill-opacity="0.8"/>'
                      for x, y, rx, ry in ((180, 430, 120, 26), (700, 560, 170, 30), (1050, 720, 150, 28), (360, 740, 110, 22), (980, 420, 90, 18)))
    extras = ""
    if mode == "night":
        extras += "".join(a.dot(rnd.uniform(0, W), rnd.uniform(8, 230), rnd.choice((1.4, 1.8, 2.4)), "#FFF6C8") for _ in range(46))
        moon = draw.Art(9)
        extras += moon.shape(draw.ellipse(1110, 90, 34, 34, 16), "#FFF2B3", jit=0.6)
        extras += f'<circle cx="1124" cy="80" r="30" fill="{sky_top}"/>'
    elif mode in ("rain", "night-rain"):
        # a heavy sky: a darker back layer of clouds, a lighter front layer, low and overlapping
        dark = mode == "night-rain"
        back = ("#36425C", "#212C45") if dark else ("#C6CFDB", "#7F91A8")
        front = ("#47546F", "#263250") if dark else ("#E2E7EE", "#8395AC")
        for i, (x, y, sc) in enumerate(((-60, 40, 1.6), (300, 20, 1.7), (660, 36, 1.6), (1000, 16, 1.7))):
            extras += place(draw.cloud(seed=141 + i, fill=back[0], ink=back[1]), x, y, scale=sc, gid="cloud")[0]
        for i, (x, y, sc) in enumerate(((100, 70, 1.4), (470, 84, 1.3), (820, 74, 1.45), (1130, 96, 1.2))):
            extras += place(draw.cloud(seed=151 + i, fill=front[0], ink=front[1]), x, y, scale=sc, gid="cloud")[0]
    else:
        for i, (x, y) in enumerate(((140, 70), (520, 40), (930, 90))):
            extras += place(draw.cloud(seed=121 + i), x, y, scale=0.9 + 0.1 * i, gid="cloud")[0]
    return defs + sky + extras + hills + ground + patches


PROP_K = 1.0  # props (props.py) are drawn at real size with their final line weight, like the pets


def weigh(svg_text, k):
    """Multiply every stroke-width in a drawing by k."""
    return re.sub(r'stroke-width="([0-9.]+)"', lambda m: f'stroke-width="{float(m.group(1)) * k:.2f}"', svg_text)


TUFTS = [(70, 384), (380, 352), (640, 420), (930, 360), (1210, 440), (110, 650), (300, 690), (560, 640), (860, 760), (1080, 560),
         (1230, 600), (40, 760), (470, 770), (980, 470), (1180, 360), (760, 560)]
LAMP = (900, 270, 0.9)  # x, y, scale — the night overlay lights it


def elements(mode="day"):
    """Everything placed on the grass, as dicts (name, svg, x, y, scale, flip, feet), sorted back-to-front.

    Ground pieces (pond, path, mat, flower patches) always sit under everything; the rest is sorted by where its feet are.
    """
    rain = mode_of(mode) in ("rain", "night-rain")
    out = []

    def add(svg_text, x, y, scale=1.0, flip=False, name="item", ground=False):
        vb = svg_text.split('viewBox="')[1].split('"')[0]
        h = float(vb.split()[3])
        # one line weight for the whole scene, whatever the item's size (outlines end up 5 px, like the mascot)
        svg_text = weigh(svg_text, (PROP_K if name.startswith("Prop/") else 1.0) / scale)
        feet = y + h * scale
        out.append(dict(name=name, svg=svg_text, x=x, y=y, scale=scale, flip=flip, feet=feet - 10000 if ground else feet))

    # ground layer
    add(props.pond(111), 930, 606, 1.1, name="Prop/pond", ground=True)
    add(props.stepping_stones(112), 800, 486, 0.85, name="Prop/stepping-stones", ground=True)
    if rain:  # no picnic in the rain; puddles instead
        for i, (x, y, w) in enumerate(((170, 694, 150), (432, 652, 130), (590, 712, 160), (880, 748, 120))):
            add(props.puddle(131 + i, w), x, y, 1.0, name="Prop/puddle", ground=True)
    else:
        add(props.picnic_mat(113), 600, 676, 1.0, name="Prop/picnic-mat", ground=True)
    add(props.flower_patch(116), 476, 532, 1.0, name="Prop/flower-patch", ground=True)
    add(props.flower_patch(117), 1010, 500, 0.9, name="Prop/flower-patch", ground=True)
    for i, (x, y) in enumerate(TUFTS):
        add(props.grass_tuft(seed=120 + i), x, y, 0.9, name="Prop/grass-tuft")
    # back row, along the hills
    add(props.pine(44), 0, 176, 0.85, name="Prop/pine")
    add(props.tree_pink(42), 524, 168, 0.75, name="Prop/tree-pink")
    add(props.wood_fence(106), 506, 352, 0.9, name="Prop/wood-fence")
    add(props.rabbit_hutch(63), 318, 300, 0.85, name="Prop/rabbit-hutch")
    add(props.dog_house(61), 690, 292, 0.9, name="Prop/dog-house")
    add(props.lamp_post(102), *LAMP, name="Prop/lamp-post")
    add(props.mailbox(103), 1000, 334, 0.8, name="Prop/mailbox")
    add(props.coconut(45), 1070, 160, 0.95, name="Prop/coconut")
    add(props.tree_round(41), 96, 240, 1.0, name="Prop/tree-round")
    # middle
    add(props.scarecrow(86), 244, 432, 0.8, name="Prop/scarecrow")
    add(props.bench(101), 548, 478, 0.9, name="Prop/bench")
    add(props.sunflower(52), 1186, 420, 0.8, name="Prop/sunflower")
    add(props.carrot_plot(81), 30, 528, 1.0, name="Prop/carrot-plot")
    add(props.hay_bale(85), 400, 566, 0.9, name="Prop/hay-bale")
    add(props.tulips(53), 1100, 470, 0.8, name="Prop/tulips")
    # front
    add(props.food_bowl(91), 640, 690, 1.0, name="Prop/food-bowl")
    if not rain:
        add(props.ball(93), 726, 716, 1.0, name="Prop/ball")
    else:  # the cat shelters under a taro leaf
        add(props.taro_leaf(132), 806, 522, 1.1, name="Prop/taro-leaf")
    add(props.bush(51), -10, 690, 1.0, name="Prop/bush")
    add(props.bush(57, berries=True), 1146, 700, 1.0, name="Prop/berry-bush")
    # pets: rabbit by its hutch, dog by its house, cat on the picnic mat
    add(draw.rabbit(draw.RABBITS["ขาว"], seed=31), 372, 410, 0.85, name="Pet/rabbit · ขาว")
    add(draw.dog(draw.DOGS["ทอง"], seed=21), 712, 384, 0.95, flip=True, name="Pet/dog · ทอง")
    add(draw.cat(draw.CATS["ส้มลาย"], seed=11), 760, 584, 1.0, name="Pet/cat · ส้มลาย")
    return sorted(out, key=lambda e: e["feet"])


def night_overlay(fireflies=True):
    rnd = random.Random(8)
    over = f'<rect width="{W}" height="{H}" fill="#14204A" fill-opacity="0.28"/>'
    lx, ly, ls = LAMP  # warm light around the lamp glass
    gx, gy = lx + 36 * ls, ly + 39 * ls
    over += (f'<circle cx="{gx:.0f}" cy="{gy:.0f}" r="78" fill="#FFE69A" fill-opacity="0.16"/>'
             f'<circle cx="{gx:.0f}" cy="{gy:.0f}" r="40" fill="#FFE69A" fill-opacity="0.28"/>')
    if not fireflies:  # no fireflies out in the rain
        return over
    over += "".join(f'<circle cx="{rnd.uniform(40, W - 40):.0f}" cy="{rnd.uniform(380, 760):.0f}" r="3.2" fill="#FFF07A"/>' for _ in range(16))
    over += "".join(f'<circle cx="{rnd.uniform(40, W - 40):.0f}" cy="{rnd.uniform(380, 760):.0f}" r="9" fill="#FFF07A" fill-opacity="0.18"/>' for _ in range(10))
    return over


def rain_overlay(night=False):
    """Rain streaks (pen strokes, so they get the brush too), splashes on the grass, rings on the pond, a cool tint."""
    rnd = random.Random(21)
    a = draw.Art(23, k=1.0)
    out = "" if night else f'<rect width="{W}" height="{H}" fill="#4E6683" fill-opacity="0.12"/>'
    drop = "#AFC4DE" if night else "#EEF5FC"
    for _ in range(170):
        x, y, ln = rnd.uniform(-40, W + 30), rnd.uniform(-20, H - 24), rnd.uniform(18, 28)
        out += a.line_([(x, y), (x - 0.28 * ln, y + ln)], width=2.4, color=drop, jit=0)
    for _ in range(26):
        x, y = rnd.uniform(20, W - 20), rnd.uniform(380, 790)
        out += "".join(a.line_(p, width=2, color=drop, jit=0) for p in ([(x - 6, y - 4), (x - 2, y)], [(x, y - 7), (x, y - 1)], [(x + 6, y - 4), (x + 2, y)]))
    for cx, cy, rx in ((1010, 650, 14), (1066, 676, 10), (1100, 648, 12), (1036, 690, 8)):  # the pond
        out += a.shape(draw.ellipse(cx, cy, rx, rx * 0.32, 12), None, jit=0.2, misreg=0, wide=2.2, ink=drop)
    return out


def rain_streaks(night=False):
    """Only the falling rain and a few splashes on the grass (the app moves this layer; nothing tied to where props stand)."""
    rnd = random.Random(31)
    a = draw.Art(33, k=1.0)
    drop = "#AFC4DE" if night else "#EEF5FC"
    out = ""
    for _ in range(170):
        x, y, ln = rnd.uniform(-40, W + 30), rnd.uniform(-20, H - 24), rnd.uniform(18, 28)
        out += a.line_([(x, y), (x - 0.28 * ln, y + ln)], width=2.4, color=drop, jit=0)
    for _ in range(26):
        x, y = rnd.uniform(20, W - 20), rnd.uniform(380, 790)
        out += "".join(a.line_(p, width=2, color=drop, jit=0) for p in ([(x - 6, y - 4), (x - 2, y)], [(x, y - 7), (x, y - 1)], [(x + 6, y - 4), (x + 2, y)]))
    return out


def scene(mode="day"):
    mode = mode_of(mode)
    body = "".join(place(e["svg"], e["x"], e["y"], e["scale"], e["flip"], e["name"])[0] for e in elements(mode))
    over = {"night": lambda: night_overlay(), "rain": lambda: rain_overlay(),
            "night-rain": lambda: night_overlay(fireflies=False) + rain_overlay(night=True)}.get(mode, lambda: "")()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f'{background(mode)}{body}{over}</svg>')


if __name__ == "__main__":
    import preview
    for night in (False, True):
        name = "scene-night" if night else "scene-day"
        html = f"<html><body style='margin:0'>{scene(night)}</body></html>"
        print(preview.shoot(html, name, W, H, scale=1))
