// Copied from web/js/garden/stage.js by tools/build_site.py — edit the app's file, then rerun.
// The garden scene: a 1280 x 800 world scaled to cover its box (anchored to the bottom, so the sky crops first).
// Things are layered by where their feet are; ground pieces (pond, path, mat…) always sit underneath.
// Pets are little actors: they walk, hop, fly or waddle (their species says which), hide from the rain or play in it,
// swim, perch, and go to bed at night.
import { itemSvg, petSvg } from "./art.js";

export const W = 1280, H = 800;
/** Zoom steps: the world is sized from the box height, so a wide window shows more garden instead of bigger things. */
export const ZOOMS = [0.62, 0.72, 0.82, 0.94];
const ZOOM_KEY = "tokbat.garden.zoom";
export const FEET_MIN = 430, FEET_MAX = 792;
/** The lawn runs half a scene past each side of the drawn scene (the background repeats there), so a wide window
 * or a zoomed-out view has room for things and pets all the way out. */
export const LAWN = { x0: -W / 2, x1: W + W / 2 };
const PET = { w: 180, h: 162 };
const DEFAULT_KIND = { gait: "walk", size: 1, speed: 50, rain: "shelter", water: "none" };
const rand = (a, b) => a + Math.random() * (b - a);
const div = (cls, style) => { const e = document.createElement("div"); e.className = cls; if (style) Object.assign(e.style, style); return e; };

// where a pet stands when it uses something (fractions of the item box, dy in px past its bottom)
const BED_SPOT = { "pet-bed": [0.5, 0.72, 0], "card-box": [0.5, 1, -6], teepee: [0.5, 1, 4], "dog-house": [0.5, 1, 8], "rabbit-hutch": [0.45, 1, 10], "cat-tower": [0.3, 1, -4] };
// trees and big leaves keep the rain off: where a pet stands under one, and the dry patch the rain skips
// (ellipse centre x/y and radii, as fractions of the drawing's box)
const TREE = { spot: [0.5, 1, 10], dry: [0.5, 0.78, 0.62, 0.5] };
const CANOPY = {
  "tree-round": TREE, "tree-pink": TREE, "tree-mango": TREE,
  pine: { spot: [0.5, 1, 10], dry: [0.5, 0.82, 0.72, 0.46] },
  coconut: { spot: [0.5, 1, 10], dry: [0.5, 0.8, 0.55, 0.42] },
  "taro-leaf": { spot: [0.56, 1, 32], dry: [0.55, 0.78, 0.7, 0.62] },
};

export class Stage {
  constructor(host, manifest) {
    this.m = manifest;
    this.kinds = Object.fromEntries((manifest.species || []).map((k) => [k.id, k]));
    this.perchTaken = new Map();
    this.host = host;
    this.el = div("g-stage");
    this.world = div("g-world", { width: `${W}px`, height: `${H}px` });
    this.bg = div("g-bg");
    this.layer = div("g-layer");
    this.fx = div("g-fx");
    this.night = div("g-night");
    this.rain = div("g-rain");
    this.rain.innerHTML = rainTiles();
    this.fireflies = div("g-flies");
    for (let i = 0; i < 28; i++) this.fireflies.append(div("g-fly", { left: `${rand(LAWN.x0 + 40, LAWN.x1 - 40)}px`, top: `${rand(400, 760)}px`, animationDelay: `-${rand(0, 6).toFixed(2)}s` }));
    this.fx.append(this.fireflies);
    this.world.append(this.bg, this.layer, this.fx);
    // tint and rain cover the whole box (also the sky above the world and the grass beside it)
    this.el.append(this.world, this.night, this.rain);
    const z = Number(localStorage.getItem(ZOOM_KEY));
    this.zoom = ZOOMS.includes(z) ? z : ZOOMS[1];
    host.append(this.el);
    this.items = new Map();
    this.pets = [];
    this.sky = { mode: null, night: false, rain: false };
    this.decor = false;
    this.ro = new ResizeObserver(() => this.fit());
    this.ro.observe(host);
    this.fit();
    this.last = performance.now();
    this.running = true;
    this.reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tick = (t) => {
      if (!this.running) return;
      const dt = Math.min(0.1, (t - this.last) / 1000);
      this.last = t;
      if (!document.hidden && !this.reduce) for (const p of this.pets) p.update(dt, this);
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  destroy() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.el.remove();
  }

  fit() {
    const r = this.host.getBoundingClientRect();
    if (!r.width || !r.height) return;
    // from the height only: wider windows get more grass on the sides (mirrored), taller ones more sky.
    // `inset` is room kept free at the bottom (the decorate tray), so nothing on the grass hides behind it.
    const h = Math.max(120, r.height - (this.inset || 0));
    this.s = Math.min(1.2, Math.max(0.45, (h / H) * this.zoom * 1.12));
    this.ox = (r.width - W * this.s) / 2;
    this.oy = h - H * this.s;
    this.world.style.transform = `translate(${this.ox}px, ${this.oy}px) scale(${this.s})`;
    if (this.items) this.updateDry();
  }

  /** Keep `px` free at the bottom of the box (0 = none); the garden slides up or back down. */
  setInset(px) {
    px = Math.max(0, Math.round(px));
    if (px === (this.inset || 0)) return;
    this.inset = px;
    this.world.classList.add("is-sliding");
    clearTimeout(this.slideT);
    this.slideT = setTimeout(() => this.world.classList.remove("is-sliding"), 400);
    this.fit();
    this.retarget();
  }

  /** Holes in the rain under every tree and big leaf, so a pet standing there is visibly out of the rain. */
  updateDry() {
    const zones = [];
    if (this.sky.rain && this.s) {
      for (const it of this.items.values()) {
        const c = CANOPY[it.def.id];
        if (!c) continue;
        const [fx, fy, rx, ry] = c.dry, d = it.def, r = it.row;
        const cx = this.ox + (r.x + (r.flip ? 1 - fx : fx) * d.w) * this.s;
        const cy = this.oy + (r.y + fy * d.h) * this.s;
        zones.push(`radial-gradient(${(rx * d.w * this.s).toFixed(1)}px ${(ry * d.h * this.s).toFixed(1)}px at ${cx.toFixed(1)}px ${cy.toFixed(1)}px, transparent 58%, #000 100%)`);
      }
    }
    const m = zones.length ? zones.join(", ") : "none";
    Object.assign(this.rain.style, { maskImage: m, webkitMaskImage: m, maskComposite: "intersect", webkitMaskComposite: "source-in", maskRepeat: "no-repeat", webkitMaskRepeat: "no-repeat" });
  }

  setZoom(z) {
    this.zoom = z;
    localStorage.setItem(ZOOM_KEY, String(z));
    this.fit();
    this.retarget();
  }

  toWorld(clientX, clientY) {
    const r = this.el.getBoundingClientRect();
    return { x: (clientX - r.left - this.ox) / this.s, y: (clientY - r.top - this.oy) / this.s };
  }

  /** Visible part of the world (for keeping things on screen). */
  view() {
    const r = this.host.getBoundingClientRect();
    return { x0: -this.ox / this.s, y0: -this.oy / this.s, x1: (r.width - this.ox) / this.s, y1: (r.height - this.oy) / this.s };
  }

  async setSky(sky) {
    this.el.classList.toggle("is-night", sky.night);
    this.el.classList.toggle("is-rain", sky.rain);
    const changed = sky.mode !== this.sky.mode;
    this.sky = sky;
    this.updateDry();
    if (!changed) return;
    // the drawn background, with mirrored copies either side so the hills run on without a seam
    const set = div("g-bg__set");
    for (const x of [-2, -1, 0, 1, 2]) {
      const img = document.createElement("img");
      img.src = `garden/base/bg/${sky.mode}.svg`;
      img.alt = "";
      img.draggable = false;
      img.className = "g-bg__img" + (x % 2 ? " is-mirror" : "");
      img.style.left = `${x * W - 1}px`;
      set.append(img);
    }
    await set.children[2].decode?.().catch(() => {});
    const old = [...this.bg.children];
    this.bg.append(set);
    if (old.length) {
      set.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 1200, easing: "ease-out" }).finished.then(() => old.forEach((o) => o.remove()));
    }
    this.retarget();
  }

  // ---------------------------------------------------------------- items
  def(id) { return this.m.byId[id]; }

  async addItem(row) {
    const d = this.def(row.item);
    if (!d || row.x === null || row.x === undefined) return null;
    const el = div("g-ent g-item" + (d.ground ? " is-ground" : ""));
    el.dataset.id = row.id;
    const flip = div("g-flip");
    flip.append(await itemSvg(d.id));
    el.append(flip);
    const it = { row: { ...row }, def: d, el };
    this.items.set(row.id, it);
    this.place(it);
    this.layer.append(el);
    if (d.light) {
      it.glow = div("g-glow");
      this.fx.append(it.glow);
      this.place(it);
    }
    if (d.id === "pond") {
      it.ripples = div("g-ripples");
      for (let i = 0; i < 4; i++) it.ripples.append(div("g-ripple", { left: `${rand(24, 70)}%`, top: `${rand(30, 70)}%`, animationDelay: `-${(i * 0.45).toFixed(2)}s` }));
      this.fx.append(it.ripples);
      this.place(it);
    }
    return it;
  }

  place(it) {
    const { row, def: d, el } = it;
    Object.assign(el.style, { left: `${row.x}px`, top: `${row.y}px`, width: `${d.w}px`, height: `${d.h}px`, zIndex: d.ground ? 1 : 10 + Math.round(row.y + d.h) });
    el.classList.toggle("is-flipped", !!row.flip);
    if (it.glow) {
      const lx = row.flip ? d.w - d.light[0] : d.light[0];
      Object.assign(it.glow.style, { left: `${row.x + lx}px`, top: `${row.y + d.light[1]}px` });
    }
    if (it.ripples) Object.assign(it.ripples.style, { left: `${row.x}px`, top: `${row.y}px`, width: `${d.w}px`, height: `${d.h}px` });
    if (CANOPY[d.id]) this.updateDry();
  }

  removeItem(id) {
    const it = this.items.get(id);
    if (!it) return;
    it.el.remove();
    it.glow?.remove();
    it.ripples?.remove();
    this.items.delete(id);
    if (CANOPY[it.def.id]) this.updateDry();
  }

  async setItems(rows) {
    for (const id of [...this.items.keys()]) this.removeItem(id);
    await Promise.all(rows.filter((r) => r.x !== null).map((r) => this.addItem(r)));
    this.updateDry();
    this.retarget();
  }

  /**
   * Spots pets use. home: a covered place they go inside (dog house, hutch, tent, a box for cats), for rain or night.
   * bed: an open bed to sleep on at night. shelter: under a tree or a big leaf when there's no home.
   */
  spots(kind, species) {
    const out = [];
    for (const it of this.items.values()) {
      const d = it.def, r = it.row;
      const mine = d.bed?.includes(species);
      if ((kind === "home" && mine && d.shelter) || (kind === "bed" && mine && !d.shelter)) {
        const [fx, fy, dy] = BED_SPOT[d.id] || [0.5, 1, 6];
        out.push({ x: r.x + (r.flip ? 1 - fx : fx) * d.w, y: Math.min(FEET_MAX, r.y + fy * d.h + dy), id: r.id });
      }
      if (kind === "shelter" && CANOPY[d.id]) {
        const [fx, fy, dy] = CANOPY[d.id].spot;
        out.push({ x: r.x + (r.flip ? 1 - fx : fx) * d.w + rand(-14, 14), y: Math.min(FEET_MAX, r.y + fy * d.h + dy), id: r.id });
      }
    }
    return out;
  }

  // ---------------------------------------------------------------- what animals use
  kind(id) { return { ...DEFAULT_KIND, id, ...this.kinds[id] }; }

  /** Where birds can stand: tree tops, fence rails, the lamp… (cover = under a canopy, dry in the rain). */
  perches() {
    const out = [];
    for (const it of this.items.values()) {
      const d = it.def, r = it.row;
      (d.perch || []).forEach(([fx, fy], i) => out.push({
        key: `${r.id}:${i}`, x: r.x + (r.flip ? 1 - fx : fx) * d.w, y: r.y + fy * d.h,
        z: 11 + Math.round(r.y + d.h), cover: fy > 0.3 && !!CANOPY[d.id],
      }));
    }
    return out;
  }

  /** Water areas (ponds) as world ellipses. */
  waters() {
    const out = [];
    for (const it of this.items.values()) {
      const w = it.def.water;
      if (!w) continue;
      const d = it.def, r = it.row;
      out.push({ cx: r.x + (r.flip ? 1 - w[0] : w[0]) * d.w, cy: r.y + w[1] * d.h, rx: w[2] * d.w, ry: w[3] * d.h });
    }
    return out;
  }

  inWater(x, y) { return this.waters().some((w) => ((x - w.cx) / w.rx) ** 2 + ((y - w.cy) / w.ry) ** 2 < 1); }

  /** A point at `k` times the water's radius (below 1 inside, above 1 round the edge), on the lawn. Outside the water
   * it keeps to the sides and the front: an animal standing behind a pond would look as if it sat on the water. */
  waterPoint(w, k) {
    const a = k > 1 ? rand(-0.15, 1.15) * Math.PI : Math.random() * Math.PI * 2;
    return { x: Math.max(LAWN.x0 + 60, Math.min(LAWN.x1 - 60, w.cx + Math.cos(a) * w.rx * k)), y: Math.max(FEET_MIN + 20, Math.min(FEET_MAX - 6, w.cy + Math.sin(a) * w.ry * k)) };
  }

  // ---------------------------------------------------------------- pets
  async setPets(rows) {
    this.perchTaken.clear();
    for (const p of this.pets) p.el.remove();
    this.pets = await Promise.all(rows.map(async (row, i) => {
      const p = new PetActor(this, row, await petSvg(row.species, row.color), i);
      this.layer.append(p.el);
      return p;
    }));
  }

  retarget() { for (const p of this.pets) p.timer = Math.min(p.timer, rand(0.2, 1.2)); }

  setDecor(on) {
    this.decor = on;
    this.el.classList.toggle("is-decor", on);
  }
}

// ------------------------------------------------------------------ pet actor
// How an animal moves comes from its species (manifest "species"): walk, hop (rabbit, frog), fly (bird) or
// waddle (duck, which also swims). Rain: "shelter" goes in or under cover, "play" stays out. Water: "near" likes the
// pond's edge, "swim" goes in. Feet are at (x, y); everything else hangs off that.
const HOP = { crouch: 0.12, air: 0.42, land: 0.12 };

class PetActor {
  constructor(stage, row, svg, i) {
    this.stage = stage;
    this.row = row;
    this.kind = stage.kind(row.species);
    this.gait = this.kind.gait;
    this.size = this.kind.size;
    this.speed = this.kind.speed;
    this.w = PET.w * this.size;
    this.h = PET.h * this.size;
    this.el = div("g-ent g-pet");
    this.el.dataset.species = row.species;
    this.el.dataset.gait = this.gait;
    this.el.style.width = `${this.w}px`;
    this.el.style.height = `${this.h}px`;
    this.flip = div("g-flip");
    this.bob = div("g-bob");
    this.bob.append(svg);
    this.flip.append(this.bob);
    this.wake = div("g-wake");
    this.tag = document.createElement("button");
    this.tag.type = "button";
    this.tag.className = "g-tag";
    this.tag.title = "ดูและเปลี่ยนชื่อ";
    this.tag.innerHTML = `<b></b><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 20C5 15 3 11.5 3 8.6 3 6 5 4 7.4 4c2 0 3.6 1.3 4.6 3 1-1.7 2.6-3 4.6-3C19 4 21 6 21 8.6c0 2.9-2 6.4-9 11.4z" fill="#FFA8B8" stroke="#22304A" stroke-width="1.6"/></svg><svg class="g-tag__edit" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 20l4-1 11-11-3-3L5 16z" fill="none" stroke="#66758F" stroke-width="2" stroke-linejoin="round"/></svg>`;
    this.tag.addEventListener("click", (e) => { e.stopPropagation(); stage.onPet?.(this); });
    this.tag.querySelector("b").textContent = row.name;
    this.zz = div("g-zz");
    this.zz.textContent = "z z";
    this.el.append(this.wake, this.flip, this.tag, this.zz);
    this.el.title = row.name;
    this.el.addEventListener("click", () => this.pet());
    this.x = rand(220, 1060);
    this.y = rand(560, 760);
    this.z = null;          // set while perched up high (birds) or flying, else from the feet
    this.lift = 0;          // height above the feet (hops, flight)
    this.perch = null;      // the perch a bird holds
    this.face = Math.random() < 0.5 ? 1 : -1;
    this.goal = null;
    this.move = null;       // the hop or flight in progress
    this.timer = rand(0.5, 2.5) + i * 0.4;
    this.mode = "idle";
    this.draw();
  }

  pet() {
    this.el.classList.remove("is-happy");
    void this.el.offsetWidth;
    this.el.classList.add("is-happy", "show-tag");
    clearTimeout(this.tagT);
    this.tagT = setTimeout(() => this.el.classList.remove("show-tag", "is-happy"), 2600);
    if (this.mode === "sleep") { this.set("idle"); this.timer = 3; }
  }

  set(mode) {
    if (mode === this.mode) return;
    this.mode = mode;
    const c = this.el.classList;
    c.toggle("is-walking", mode === "walk");
    c.toggle("is-sleeping", mode === "sleep");
    c.toggle("is-hiding", mode === "home");
    c.toggle("is-wet", mode === "wet");
    c.toggle("is-flying", mode === "fly");
    c.toggle("is-pecking", mode === "peck");
  }

  setPhase(p) {
    if (p === this.phase) return;
    this.phase = p;
    for (const k of ["crouch", "air", "land"]) this.el.classList.toggle(`is-${k}`, p === k);
  }

  draw() {
    const s = this.el.style;
    s.left = `${this.x - this.w / 2}px`;
    s.top = `${this.y - this.h + 6 * this.size}px`;
    s.zIndex = this.z ?? 10 + Math.round(this.y);
    this.bob.style.translate = this.lift ? `0 ${(-this.lift).toFixed(1)}px` : "";
    this.el.classList.toggle("is-left", this.face < 0);
    this.el.classList.toggle("is-perched", !!this.perch);
    const swim = this.kind.water === "swim" && !this.move && this.stage.inWater(this.x, this.y);
    this.el.classList.toggle("is-swimming", swim);
  }

  // ---------------------------------------------------------------- deciding where to go
  choose(st) {
    if (this.gait === "fly") return this.chooseFlight(st);
    const sp = this.row.species, { night, rain } = st.sky, k = this.kind;
    const near = (list) => list.sort((a, c) => Math.hypot(a.x - this.x, a.y - this.y) - Math.hypot(c.x - this.x, c.y - this.y))[0];
    const here = { x: this.x, y: this.y };
    const water = st.waters();
    if (rain && k.rain !== "play") {
      // inside if it can, under a tree or leaf if not, otherwise it sits there shivering
      const home = near(st.spots("home", sp)), tree = near(st.spots("shelter", sp));
      this.goal = home ? { ...home, then: "home" } : tree ? { ...tree, then: night ? "sleep" : "idle" } : { ...here, then: night ? "sleep" : "wet" };
    } else if (night) {
      const home = near(st.spots("home", sp)), bed = near(st.spots("bed", sp));
      const edge = k.water !== "none" && water.length ? st.waterPoint(water[0], 1.35) : null;
      this.goal = home ? { ...home, then: "home" } : bed ? { ...bed, then: "sleep" } : edge ? { ...edge, then: "sleep" } : { ...here, then: "sleep" };
    } else if (k.water === "swim" && water.length && Math.random() < (rain ? 0.8 : 0.5)) {
      this.goal = { ...st.waterPoint(water[Math.floor(Math.random() * water.length)], rand(0.1, 0.75)), then: "idle" };
    } else if (k.water === "near" && water.length && Math.random() < 0.6) {
      this.goal = { ...st.waterPoint(water[Math.floor(Math.random() * water.length)], rand(1.3, 1.7)), then: "idle" };
    } else if (Math.random() < (rain ? 0.85 : 0.7)) {
      const v = st.view();
      for (let i = 0; i < 6; i++) { // somewhere on the grass, not in the pond (only swimmers stop in water)
        this.goal = { x: rand(Math.max(LAWN.x0 + 90, v.x0 + 90), Math.min(LAWN.x1 - 90, v.x1 - 90)), y: rand(Math.max(FEET_MIN + 40, v.y0 + 200), Math.min(FEET_MAX - 6, v.y1 - 8)), then: "idle" };
        if (!st.inWater(this.goal.x, this.goal.y)) break;
      }
    } else {
      this.goal = null;
    }
  }

  /** Birds: from perch to perch, down to the grass to peck, into a tree when it rains, asleep on a perch at night. */
  chooseFlight(st) {
    const { night, rain } = st.sky;
    const free = st.perches().filter((p) => !st.perchTaken.has(p.key) || st.perchTaken.get(p.key) === this);
    const pick = (list) => list[Math.floor(Math.random() * list.length)];
    const near = (list) => list.sort((a, c) => Math.hypot(a.x - this.x, a.y - this.y) - Math.hypot(c.x - this.x, c.y - this.y))[0];
    let to = null, then = "idle";
    if (rain) {
      to = near(free.filter((p) => p.cover)) || null;
      then = night ? "sleep" : "idle";
      if (!to) { this.goal = { x: this.x, y: this.y, perch: this.perch, then: night ? "sleep" : "wet" }; return; }
    } else if (night) {
      to = this.perch || near(free) || null;
      then = "sleep";
      if (!to) { this.goal = { x: this.x, y: this.y, then: "sleep" }; return; }
    } else {
      const r = Math.random();
      if (r < 0.5 && free.length) to = pick(free);
      else if (r < 0.85) {
        const v = st.view();
        to = { x: rand(Math.max(LAWN.x0 + 90, v.x0 + 90), Math.min(LAWN.x1 - 90, v.x1 - 90)), y: rand(FEET_MIN + 60, FEET_MAX - 10) };
        if (st.inWater(to.x, to.y)) to.y = Math.min(FEET_MAX - 10, to.y + 90);
        then = "peck";
      } else { this.goal = null; return; }
    }
    this.goal = { x: to.x, y: to.y, perch: to.key ? to : null, then };
  }

  // ---------------------------------------------------------------- moving
  update(dt, st) {
    if (st.decor) { if (this.mode === "walk" || this.mode === "fly") this.set("idle"); return; }
    if (this.move) return this.step(dt, st);
    this.timer -= dt;
    if (!this.goal && this.timer <= 0) {
      this.choose(st);
      const g = this.goal;
      if (["home", "sleep", "wet"].includes(this.mode) && g?.then === this.mode && Math.hypot(g.x - this.x, g.y - this.y) < 8) { this.goal = null; this.timer = 20; return; }
      if (!g) { this.timer = rand(2, 5); return; }
    }
    if (!this.goal) return;
    const dx = this.goal.x - this.x, dy = this.goal.y - this.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 3) return this.arrive(st);
    if (Math.abs(dx) > 2) this.face = dx < 0 ? -1 : 1;
    if (this.gait === "fly") return this.takeOff(st, dist);
    if (this.gait === "hop") {
      this.set("hop");
      const len = Math.min(dist, this.speed * 0.9 * (st.sky.rain && this.kind.rain !== "play" ? 1.4 : 1));
      this.move = { kind: "hop", t: 0, fx: this.x, fy: this.y, tx: this.x + (dx / dist) * len, ty: this.y + (dy / dist) * len, rest: rand(0.15, 0.5) };
      return this.step(0, st);
    }
    // walk and waddle
    this.set("walk");
    const step = Math.min(dist, this.speed * (st.sky.rain && this.kind.rain !== "play" ? 1.7 : 1) * dt);
    this.x += (dx / dist) * step;
    this.y += (dy / dist) * step;
    this.draw();
  }

  takeOff(st, dist) {
    if (this.perch) st.perchTaken.delete(this.perch.key);
    this.perch = null;
    const to = this.goal.perch;
    if (to) st.perchTaken.set(to.key, this);
    this.move = { kind: "fly", t: 0, fx: this.x, fy: this.y, tx: this.goal.x, ty: this.goal.y, dur: dist / this.speed + 0.5, arc: Math.min(110, Math.max(36, dist * 0.25)) };
    this.set("fly");
    this.z = 2000;
  }

  /** One frame of a hop or a flight. */
  step(dt, st) {
    const m = this.move;
    m.t += dt;
    if (m.kind === "fly") {
      const u = Math.min(1, m.t / m.dur);
      const e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      this.x = m.fx + (m.tx - m.fx) * e;
      this.y = m.fy + (m.ty - m.fy) * e;
      this.lift = Math.sin(Math.PI * u) * m.arc;
      if (u >= 1) { this.move = null; this.lift = 0; return this.arrive(st); }
      return this.draw();
    }
    // hop: crouch → air (an arc) → land → rest
    const t = m.t, { crouch, air, land } = HOP;
    if (t < crouch) this.setPhase("crouch");
    else if (t < crouch + air) {
      this.setPhase("air");
      const u = (t - crouch) / air;
      this.x = m.fx + (m.tx - m.fx) * u;
      this.y = m.fy + (m.ty - m.fy) * u;
      this.lift = Math.sin(Math.PI * u) * 30 * this.size;
    } else if (t < crouch + air + land) {
      this.setPhase("land");
      this.x = m.tx; this.y = m.ty; this.lift = 0;
    } else {
      this.setPhase(null);
      if (t >= crouch + air + land + m.rest) this.move = null;
    }
    this.draw();
  }

  arrive(st) {
    const g = this.goal;
    this.x = g.x; this.y = g.y;
    if (g.perch) { this.perch = g.perch; this.z = g.perch.z; }
    else if (this.gait === "fly") this.z = null;
    this.set(g.then);
    this.goal = null;
    this.timer = this.mode === "idle" ? rand(2.5, 7) : this.mode === "peck" ? rand(1.5, 3) : 20;
    if (this.mode === "peck") setTimeout(() => { if (this.mode === "peck") this.set("idle"); }, 1400);
    this.draw();
  }
}

function rainTiles() {
  let lines = "";
  for (let i = 0; i < 150; i++) {
    const x = Math.random() * (W + 120) - 40, y = Math.random() * H, l = 18 + Math.random() * 12;
    lines += `<path d="M${x.toFixed(1)} ${y.toFixed(1)}l${(-0.28 * l).toFixed(1)} ${l.toFixed(1)}"/>`;
  }
  const tile = (x, y) => `<svg class="g-rain__tile" style="left:${x}px;top:${y}px" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><g stroke-width="2.4" stroke-linecap="round">${lines}</g></svg>`;
  return `<div class="g-rain__fall">${[0, W].flatMap((x) => [tile(x, -H), tile(x, 0), tile(x, H)]).join("")}</div>`;
}
