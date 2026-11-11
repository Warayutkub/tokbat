// Landing: a live sample of the app's garden. It runs the app's own stage code and drawings (copied by
// tools/build_site.py), laid out like the approved Figma scene. A demo only: no coins, no shop, nothing saved.
const host = document.querySelector("[data-garden]");
const chips = [...document.querySelectorAll("[data-sky]")];
const SKIES = {
  day: { mode: "day", night: false, rain: false },
  night: { mode: "night", night: true, rain: false },
  rain: { mode: "rain", night: false, rain: true },
};
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
let stage = null;
let want = "day";

function pick(key) {
  want = key;
  chips.forEach((c) => c.setAttribute("aria-pressed", String(c.dataset.sky === key)));
  stage?.setSky(SKIES[key]);
}

async function boot() {
  const [{ Stage, W, H }, { manifest }] = await Promise.all([import("./garden/stage.js"), import("./garden/art.js")]);
  const [m, demo] = await Promise.all([manifest(), fetch("garden/demo.json").then((r) => r.json())]);

  // the box keeps the world's 16:10 shape, so the whole garden always fits (the app crops to its window instead).
  // Layout size, not the on-screen box: the section's entrance scales it for a moment.
  class DemoStage extends Stage {
    fit() {
      const w = this.host.clientWidth, h = this.host.clientHeight;
      if (!w || !h) return;
      this.s = Math.min(w / W, h / H);
      this.ox = (w - W * this.s) / 2;
      this.oy = h - H * this.s;
      this.world.style.transform = `translate(${this.ox}px, ${this.oy}px) scale(${this.s})`;
      if (this.items) this.updateDry();
    }
  }

  const s = new DemoStage(host, m);
  s.reduce = true; // hold still until everything is drawn
  await s.setItems(demo.items.map(([item, x, y], i) => ({ id: i + 1, item, x, y, flip: false })));
  await s.setPets(demo.pets.map(([species, color, name], i) => ({ id: i + 1, species, color, name })));
  s.pets.forEach((p, i) => {
    const [x, feet] = demo.pets[i][3];
    p.x = x;
    p.y = feet - 6;
    p.draw();
  });
  await s.setSky(SKIES[want]);
  stage = s;
  host.classList.add("is-live");
  watch();
}

// pets walk only while the garden is on screen (and never for people who asked for less motion)
function watch() {
  const set = (on) => {
    stage.reduce = still || !on;
    host.classList.toggle("is-paused", !on);
  };
  if (!("IntersectionObserver" in window)) return set(true);
  new IntersectionObserver(([e]) => set(e.isIntersecting), { threshold: 0.05 }).observe(host);
}

if (host) {
  // open on the viewer's own clock, as the app does (it never rains on its own here)
  const now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
  pick(mins >= 18 * 60 + 30 || mins < 6 * 60 ? "night" : "day");
  chips.forEach((c) => c.addEventListener("click", () => pick(c.dataset.sky)));
  const start = () => boot().catch((e) => console.warn("garden demo:", e)); // the drawn picture stays
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { io.disconnect(); start(); }
    }, { rootMargin: "400px 0px" });
    io.observe(host);
  } else {
    start();
  }
}
