// Router + shared context. Views live in js/views/*.js and export render(root, params, ctx).
import { call } from "./api.js";
import { toast, hydrateMascots } from "./ui.js";
import * as log from "./views/log.js";
import * as history from "./views/history.js";
import * as report from "./views/report.js";
import * as settings from "./views/settings.js";
import * as welcome from "./views/welcome.js";
import * as garden from "./views/garden.js";
import * as shop from "./views/shop.js";
import * as adopt from "./views/adopt.js";
import { checkPacks } from "./garden/packs.js";

const VIEWS = { log, history, report, settings, welcome, garden, shop, adopt };
const TAB_OF = { shop: "garden", adopt: "garden" };
const ctx = { settings: {}, today: null };
let cleanup = null;
let seq = 0;

function route() {
  const [path, qs] = location.hash.replace(/^#\/?/, "").split("?");
  const home = ctx.settings.game_enabled !== false && ctx.settings.start_page === "garden" ? "garden" : "log";
  return { name: VIEWS[path] ? path : home, params: Object.fromEntries(new URLSearchParams(qs || "")) };
}

async function show() {
  const { name, params } = route();
  const my = ++seq;
  const tab = TAB_OF[name] || name;
  document.querySelectorAll(".tab").forEach((t) => (t.dataset.tab === tab ? t.setAttribute("aria-current", "page") : t.removeAttribute("aria-current")));
  // every visit renders into its own box, so a slow, older visit can never paint over a newer one
  const root = document.createElement("div");
  root.className = "view";
  const dlg = document.getElementById("dialog");
  if (dlg.open) dlg.close();
  cleanup?.();
  cleanup = null;
  document.getElementById("view").replaceChildren(root);
  try {
    const c = await VIEWS[name].render(root, params, ctx);
    if (my === seq && typeof c === "function") cleanup = c;
  } catch (err) {
    console.error(err);
    toast(`มีบางอย่างผิดพลาด: ${err.message || err}`, { error: true, action: "ลองอีกครั้ง", onAction: show });
  }
}

async function boot() {
  const b = await call("bootstrap");
  ctx.settings = b.settings;
  ctx.today = b.today;
  document.body.classList.toggle("no-chars", !b.settings.show_characters);
  document.body.classList.toggle("no-game", b.settings.game_enabled === false);
  window.addEventListener("garden:coins", (e) => {
    const pill = document.querySelector(".coins");
    document.getElementById("coins").textContent = e.detail.n;
    pill.classList.toggle("is-negative", e.detail.n < 0);
    if (e.detail.bump) { pill.classList.remove("is-bump"); void pill.offsetWidth; pill.classList.add("is-bump"); }
  });
  if (b.settings.game_enabled !== false) call("garden_state").then((g) => garden.setCoins(g.balance)).catch(() => {});
  window.addEventListener("garden:packs", (e) => {
    const n = e.detail.reduce((a, p) => a + p.items + p.pets, 0);
    toast(`ของใหม่มาแล้ว ${n} อย่าง · ${e.detail.map((p) => p.title).join(", ")}`, { action: "ไปร้านค้า", onAction: () => { location.hash = "#/shop"; } });
  });
  if (b.settings.game_enabled !== false && b.settings.auto_packs !== false) setTimeout(() => checkPacks().catch(() => {}), 4000);
  hydrateMascots();
  if (!location.hash && b.count === 0 && !b.settings.first_run_done) location.hash = "#/welcome";
  window.addEventListener("hashchange", show);
  await show();
}

boot();
