// The landing page's stand-in for the app's web/js/garden/art.js: the same drawings and the same two functions the
// stage needs, read from static files next to the page (no app, no packs). Written by hand; stage.js beside it is a copy.
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
  if (!texts.has(path)) texts.set(path, fetch(BASE + path).then((r) => (r.ok ? r.text() : Promise.reject(new Error(`${path}: ${r.status}`)))));
  return texts.get(path);
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

export const itemSvg = (id) => fromText(text(`props/${id}.svg`));
export const petSvg = (species, color) => fromText(text(`pets/${species}-${color}.svg`));
