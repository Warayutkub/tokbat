// The garden's art: the catalogue (built-in manifest + installed packs, from Rust) and the hand-drawn SVGs
// (exported from Figma with the pencil brush expanded). Built-in drawings are files next to the page; pack drawings
// come through the API. Each is fetched once and cloned per use; group classes (leg-*, tail, eye-l …) let CSS move parts.
import { call } from "../api.js";

const BASE = "garden/base/";
const texts = new Map();
let manifestP = null;

export function manifest() {
  if (!manifestP) {
    manifestP = call("garden_catalog").then((m) => {
      m.byId = Object.fromEntries(m.items.map((i) => [i.id, i]));
      return m;
    });
  }
  return manifestP;
}
/** After a pack arrives: read the catalogue again next time. */
export function resetCatalog() { manifestP = null; }

function text(path) {
  if (!texts.has(path)) texts.set(path, fetch(BASE + path).then((r) => r.text()));
  return texts.get(path);
}
function packText(pack, file) {
  const key = `pack:${pack}/${file}`;
  if (!texts.has(key)) texts.set(key, call("pack_asset", pack, file));
  return texts.get(key);
}

async function fromText(src) {
  const t = document.createElement("template");
  t.innerHTML = (await src).trim();
  const el = t.content.firstElementChild;
  el.removeAttribute("width");
  el.removeAttribute("height");
  el.setAttribute("aria-hidden", "true");
  el.setAttribute("focusable", "false");
  return el;
}

export async function itemSvg(id) {
  const d = (await manifest()).byId[id];
  return fromText(d?.pack ? packText(d.pack, d.file) : text(`props/${id}.svg`));
}
export async function petSvg(species, color) {
  const p = (await manifest()).pets.find((x) => x.species === species && x.color === color);
  return fromText(p?.pack ? packText(p.pack, p.file) : text(`pets/${species}-${color}.svg`));
}

/** Warm the cache so the first paint of the garden doesn't pop in piece by piece. */
export function preload(m, ids = [], pets = []) {
  return Promise.all([...ids.map((i) => text(`props/${i}.svg`)), ...pets.map(([s, c]) => text(`pets/${s}-${c}.svg`)), text("bg/day.svg")]);
}

export const CATS = [
  ["trees", "ต้นไม้"], ["plants", "พุ่มไม้ & ดอกไม้"], ["homes", "บ้าน & ที่นอน"], ["farm", "ฟาร์ม"],
  ["toys", "ของเล่น & ชาม"], ["decor", "ตกแต่งสวน"], ["ground", "พื้น"],
];
export const RARITY = { common: "ธรรมดา", rare: "หายาก", special: "พิเศษ" };
/** Kinds of animal that have at least one colour to adopt (built-in and from packs), in catalogue order. */
export const kinds = (m) => (m.species || []).filter((k) => m.pets.some((p) => p.species === k.id));
export const speciesName = (m, id) => (m.species || []).find((k) => k.id === id)?.name || id;

export function coinSvg(size = 18) {
  return `<svg class="coin" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.6" fill="#FFD54A" stroke="#22304A" stroke-width="1.8"/><circle cx="12" cy="12" r="5.4" fill="none" stroke="#D9A21B" stroke-width="1.7"/></svg>`;
}
export function pawSvg(size = 20, punched = true) {
  const toes = [[-4.2, -2.2], [-1.5, -4.6], [1.5, -4.6], [4.2, -2.2]].map(([x, y]) => `<ellipse cx="${14 + x}" cy="${14 + y}" rx="1.9" ry="2.3" fill="#22304A"/>`).join("");
  return punched
    ? `<svg width="${size}" height="${size}" viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="10.5" fill="#FFE07A" stroke="#22304A" stroke-width="1.6"/>${toes}<ellipse cx="14" cy="15.8" rx="3.8" ry="3.2" fill="#22304A"/></svg>`
    : `<svg width="${size}" height="${size}" viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="10.5" fill="#F4F8FD" stroke="#9AA8BD" stroke-width="1.5" stroke-dasharray="3 2.4"/></svg>`;
}
