// Router + shared context. Views live in js/views/*.js and export render(root, params, ctx).
import { call } from "./api.js";
import { toast, hydrateMascots } from "./ui.js";
import * as log from "./views/log.js";
import * as history from "./views/history.js";
import * as report from "./views/report.js";
import * as settings from "./views/settings.js";
import * as welcome from "./views/welcome.js";

const VIEWS = { log, history, report, settings, welcome };
const ctx = { settings: {}, today: null };
let cleanup = null;
let seq = 0;

function route() {
  const [path, qs] = location.hash.replace(/^#\/?/, "").split("?");
  return { name: VIEWS[path] ? path : "log", params: Object.fromEntries(new URLSearchParams(qs || "")) };
}

async function show() {
  const { name, params } = route();
  const my = ++seq;
  document.querySelectorAll(".tab").forEach((t) => (t.dataset.tab === name ? t.setAttribute("aria-current", "page") : t.removeAttribute("aria-current")));
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
  hydrateMascots();
  if (!location.hash && b.count === 0 && !b.settings.first_run_done) location.hash = "#/welcome";
  window.addEventListener("hashchange", show);
  await show();
}

boot();
