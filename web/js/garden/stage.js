// The garden scene: a 1280 x 800 world scaled to cover its box (anchored to the bottom, so the sky crops first).
// Things are layered by where their feet are; ground pieces (pond, path, mat…) always sit underneath.
// Pets are little actors: they wander, hide from the rain under trees and leaves, and go to bed at night.
import { itemSvg, petSvg } from "./art.js";

export const W = 1280, H = 800;
/** Zoom steps: the world is sized from the box height, so a wide window shows more garden instead of bigger things. */
export const ZOOMS = [0.62, 0.72, 0.82, 0.94];
const ZOOM_KEY = "tokbat.garden.zoom";
export const FEET_MIN = 430, FEET_MAX = 792;
const PET = { w: 180, h: 162 };
const SPEED = { cat: 46, dog: 58, rabbit: 64 };
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
    for (let i = 0; i < 14; i++) this.fireflies.append(div("g-fly", { left: `${rand(40, W - 40)}px`, top: `${rand(400, 760)}px`, animationDelay: `-${rand(0, 6).toFixed(2)}s` }));
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
    // from the height only: wider windows get more grass on the sides (mirrored), taller ones more sky
    this.s = Math.min(1.2, Math.max(0.45, (r.height / H) * this.zoom * 1.12));
    this.ox = (r.width - W * this.s) / 2;
    this.oy = r.height - H * this.s;
    this.world.style.transform = `translate(${this.ox}px, ${this.oy}px) scale(${this.s})`;
    if (this.items) this.updateDry();
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

  // ---------------------------------------------------------------- pets
  async setPets(rows) {
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
class PetActor {
  constructor(stage, row, svg, i) {
    this.stage = stage;
    this.row = row;
    this.speed = SPEED[row.species] || 50;
    this.el = div("g-ent g-pet");
    this.el.dataset.species = row.species;
    this.el.style.width = `${PET.w}px`;
    this.el.style.height = `${PET.h}px`;
    this.flip = div("g-flip");
    const bob = div("g-bob");
    bob.append(svg);
    this.flip.append(bob);
    this.tag = document.createElement("button");
    this.tag.type = "button";
    this.tag.className = "g-tag";
    this.tag.title = "ดูและเปลี่ยนชื่อ";
    this.tag.innerHTML = `<b></b><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 20C5 15 3 11.5 3 8.6 3 6 5 4 7.4 4c2 0 3.6 1.3 4.6 3 1-1.7 2.6-3 4.6-3C19 4 21 6 21 8.6c0 2.9-2 6.4-9 11.4z" fill="#FFA8B8" stroke="#22304A" stroke-width="1.6"/></svg><svg class="g-tag__edit" viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M4 20l4-1 11-11-3-3L5 16z" fill="none" stroke="#66758F" stroke-width="2" stroke-linejoin="round"/></svg>`;
    this.tag.addEventListener("click", (e) => { e.stopPropagation(); stage.onPet?.(this); });
    this.tag.querySelector("b").textContent = row.name;
    this.zz = div("g-zz");
    this.zz.textContent = "z z";
    this.el.append(this.flip, this.tag, this.zz);
    this.el.title = row.name;
    this.el.addEventListener("click", () => this.pet());
    this.x = rand(220, 1060);
    this.y = rand(560, 760);
    this.face = Math.random() < 0.5 ? 1 : -1;
    this.target = null;
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
    this.el.classList.toggle("is-walking", mode === "walk");
    this.el.classList.toggle("is-sleeping", mode === "sleep");
    this.el.classList.toggle("is-hiding", mode === "home");
    this.el.classList.toggle("is-wet", mode === "wet");
  }

  draw() {
    const s = this.el.style;
    s.left = `${this.x - PET.w / 2}px`;
    s.top = `${this.y - PET.h + 6}px`;
    s.zIndex = 10 + Math.round(this.y);
    this.el.classList.toggle("is-left", this.face < 0);
  }

  choose(st) {
    const sp = this.row.species, { night, rain } = st.sky;
    const near = (list) => list.sort((a, c) => Math.hypot(a.x - this.x, a.y - this.y) - Math.hypot(c.x - this.x, c.y - this.y))[0];
    const here = { x: this.x, y: this.y };
    if (rain) {
      // inside if it can, under a tree or leaf if not, otherwise it sits there shivering
      const home = near(st.spots("home", sp)), tree = near(st.spots("shelter", sp));
      this.goal = home ? { ...home, then: "home" } : tree ? { ...tree, then: night ? "sleep" : "idle" } : { ...here, then: night ? "sleep" : "wet" };
    } else if (night) {
      const home = near(st.spots("home", sp)), bed = near(st.spots("bed", sp));
      this.goal = home ? { ...home, then: "home" } : bed ? { ...bed, then: "sleep" } : { ...here, then: "sleep" };
    } else if (Math.random() < 0.7) {
      const v = st.view();
      this.goal = { x: rand(Math.max(90, v.x0 + 90), Math.min(W - 90, v.x1 - 90)), y: rand(Math.max(FEET_MIN + 40, v.y0 + 200), Math.min(FEET_MAX - 6, v.y1 - 8)), then: "idle" };
    } else {
      this.goal = null;
    }
  }

  update(dt, st) {
    if (st.decor) { if (this.mode === "walk") this.set("idle"); return; }
    this.timer -= dt;
    if (!this.goal && this.timer <= 0) {
      this.choose(st);
      if (["home", "sleep", "wet"].includes(this.mode) && this.goal?.then === this.mode && Math.hypot(this.goal.x - this.x, this.goal.y - this.y) < 8) { this.goal = null; this.timer = 20; return; }
      if (!this.goal) { this.timer = rand(2, 5); return; }
    }
    if (!this.goal) return;
    const dx = this.goal.x - this.x, dy = this.goal.y - this.y;
    const dist = Math.hypot(dx, dy);
    if (dist < 3) {
      this.set(this.goal.then);
      this.goal = null;
      this.timer = this.mode === "idle" ? rand(2.5, 7) : 20;
      this.draw();
      return;
    }
    this.set("walk");
    const step = Math.min(dist, this.speed * (st.sky.rain ? 1.7 : 1) * dt);
    this.x += (dx / dist) * step;
    this.y += (dy / dist) * step;
    if (Math.abs(dx) > 2) this.face = dx < 0 ? -1 : 1;
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
