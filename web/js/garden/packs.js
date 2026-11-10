// New garden items arrive as content packs from the app's GitHub Pages site. At most once a day, while online
// and only if the setting is on, the page reads the pack list, downloads what's new and hands it to Rust, which
// checks the signature, every file's hash and every drawing before keeping anything. Nothing about the user is sent.
import { call } from "../api.js";
import { resetCatalog } from "./art.js";

export const PACK_INDEX = "https://warayutkub.github.io/tokbat/packs/index.json";
const CHECKED = "tokbat.packs.checked";
const EVERY = 20 * 3600 * 1000;

const get = async (url, as = "text") => {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r[as]();
};

/** {got: [...installed], failed: [...], offline?, skipped?} */
export async function checkPacks({ force = false } = {}) {
  if (!force && Date.now() - Number(localStorage.getItem(CHECKED) || 0) < EVERY) return { skipped: true, got: [], failed: [] };
  if (!navigator.onLine) return { offline: true, got: [], failed: [] };
  // a local list for development: localStorage "tokbat.packs.index" = "/packs-test/index.json"
  const url = new URL(localStorage.getItem("tokbat.packs.index") || PACK_INDEX, location.href);
  let index;
  try { index = await get(url, "json"); } catch { return { offline: true, got: [], failed: [] }; }
  localStorage.setItem(CHECKED, String(Date.now()));
  const have = Object.fromEntries((await call("pack_list")).map((p) => [p.id, p.version]));
  const got = [], failed = [];
  for (const p of index.packs || []) {
    if ((have[p.id] || 0) >= p.version) continue;
    try {
      const packUrl = new URL(p.url, url);
      const [pack, sig] = await Promise.all([get(packUrl), get(new URL("pack.sig", packUrl))]);
      const files = {};
      await Promise.all(Object.keys(JSON.parse(pack).files || {}).map(async (f) => { files[f] = await get(new URL(f, packUrl)); }));
      const r = await call("pack_install", { pack, sig, files });
      if (r.ok) got.push(r); else failed.push({ id: p.id, error: r.error?.message });
    } catch (e) {
      failed.push({ id: p.id, error: String(e.message || e) });
    }
  }
  if (got.length) {
    resetCatalog();
    window.dispatchEvent(new CustomEvent("garden:packs", { detail: got }));
  }
  if (failed.length) console.warn("garden packs not installed", failed);
  return { got, failed };
}

/** "2026-11-10 21:05:00" in local time, the same shape Rust stores. */
export function stamp(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
