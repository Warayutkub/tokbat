// The garden's art pack: manifest + hand-drawn SVG files (exported from Figma with the pencil brush expanded).
// Every drawing is fetched once and cloned for each use; group classes (leg-*, tail, eye-l …) let CSS move the parts.
const BASE = "garden/base/";
const texts = new Map();
let manifestP = null;

export function manifest() {
  if (!manifestP) {
    manifestP = fetch(BASE + "manifest.json").then((r) => r.json()).then((m) => {
      m.byId = Object.fromEntries(m.items.map((i) => [i.id, i]));
      return m;
    });
  }
  return manifestP;
}

function text(path) {
  if (!texts.has(path)) texts.set(path, fetch(BASE + path).then((r) => r.text()));
  return texts.get(path);
}

async function svg(path) {
  const t = document.createElement("template");
  t.innerHTML = (await text(path)).trim();
  const el = t.content.firstElementChild;
  el.removeAttribute("width");
  el.removeAttribute("height");
  el.setAttribute("aria-hidden", "true");
  el.setAttribute("focusable", "false");
  return el;
}

export const itemSvg = (id) => svg(`props/${id}.svg`);
export const petSvg = (species, color) => svg(`pets/${species}-${color}.svg`);
export const bgSvg = (mode) => svg(`bg/${mode}.svg`);

/** Warm the cache so the first paint of the garden doesn't pop in piece by piece. */
export function preload(m, ids = [], pets = []) {
  return Promise.all([...ids.map((i) => text(`props/${i}.svg`)), ...pets.map(([s, c]) => text(`pets/${s}-${c}.svg`)), text("bg/day.svg")]);
}

export const CATS = [
  ["trees", "ต้นไม้"], ["plants", "พุ่มไม้ & ดอกไม้"], ["homes", "บ้าน & ที่นอน"], ["farm", "ฟาร์ม"],
  ["toys", "ของเล่น & ชาม"], ["decor", "ตกแต่งสวน"], ["ground", "พื้น"],
];
export const RARITY = { common: "ธรรมดา", rare: "หายาก", special: "พิเศษ" };
export const SPECIES = { cat: "แมว", dog: "หมา", rabbit: "กระต่าย" };

export function coinSvg(size = 18) {
  return `<svg class="coin" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.6" fill="#FFD54A" stroke="#22304A" stroke-width="1.8"/><circle cx="12" cy="12" r="5.4" fill="none" stroke="#D9A21B" stroke-width="1.7"/></svg>`;
}
export function pawSvg(size = 20, punched = true) {
  const toes = [[-4.2, -2.2], [-1.5, -4.6], [1.5, -4.6], [4.2, -2.2]].map(([x, y]) => `<ellipse cx="${14 + x}" cy="${14 + y}" rx="1.9" ry="2.3" fill="#22304A"/>`).join("");
  return punched
    ? `<svg width="${size}" height="${size}" viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="10.5" fill="#FFE07A" stroke="#22304A" stroke-width="1.6"/>${toes}<ellipse cx="14" cy="15.8" rx="3.8" ry="3.2" fill="#22304A"/></svg>`
    : `<svg width="${size}" height="${size}" viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="10.5" fill="#F4F8FD" stroke="#9AA8BD" stroke-width="1.5" stroke-dasharray="3 2.4"/></svg>`;
}
