// Small DOM helpers + the product's own Toast / Dialog (never alert/confirm).
const ICONS = {
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1.2"/><circle cx="4.5" cy="12" r="1.2"/><circle cx="4.5" cy="18" r="1.2"/>',
  chart: '<path d="M4 20h16M7 16v-5M12 16V6M17 16V9"/>',
  sliders: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2.5"/><circle cx="15" cy="17" r="2.5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  left: '<path d="M15 6l-6 6 6 6"/>', right: '<path d="M9 6l6 6-6 6"/>', down: '<path d="M6 9l6 6 6-6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M5 20h14"/>',
  edit: '<path d="M4 20l4-1 11-11-3-3L5 16z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-11 9"/>',
  file: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5"/>',
  note: '<path d="M5 4h14v16H5z"/><path d="M9 9h6M9 13h6M9 17h3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>',
  folder: '<path d="M3 6h6l2 2h10v11H3z"/>',
  database: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  coffee: '<path d="M5 9h11v5a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4z"/><path d="M16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 3v3M12 3v3"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  spinner: '<path d="M12 3a9 9 0 1 0 9 9"/>',
};

export function icon(name, cls = "") {
  return `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

/** h("button.btn.btn--primary", {onclick}, "บันทึก") — tag with .classes, attrs/handlers, children (strings are HTML-escaped unless raw()) */
export function h(spec, attrs = {}, ...children) {
  const [tag, ...classes] = spec.split(".");
  const el = document.createElement(tag || "div");
  if (classes.length) el.className = classes.join(" ");
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "html") el.innerHTML = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
export const raw = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content; };

// Mascots are inlined (not <img>) so css/mascots.css can move their parts. Cached per pose.
const svgCache = new Map();
export function loadMascot(pose) {
  if (!svgCache.has(pose)) svgCache.set(pose, fetch(`img/chars/anim/${pose}.svg`).then((r) => r.text()));
  return svgCache.get(pose);
}
export const randomDelay = () => `-${(Math.random() * 6).toFixed(2)}s`;
export function mascot(pose, size, cls = "") {
  const el = h(`span.mascot${cls ? "." + cls : ""}`, { style: `width:${size}px;height:${size}px;--d:${randomDelay()}`, "aria-hidden": "true", "data-pose": pose });
  loadMascot(pose).then((t) => { el.innerHTML = t; });
  return el;
}
export function hydrateMascots(root = document) {
  root.querySelectorAll("span.mascot[data-pose]:empty").forEach((el) => {
    el.style.setProperty("--d", randomDelay());
    loadMascot(el.dataset.pose).then((t) => { el.innerHTML = t; });
  });
}

export function button(label, { kind = "", icon: ic, small, onclick, disabled, title } = {}) {
  const cls = ["btn", "sketch", kind && `btn--${kind}`, small && "btn--sm"].filter(Boolean).join(".");
  return h(`button.${cls}`, { type: "button", onclick, disabled, title }, ic ? raw(icon(ic)) : null, label);
}

export function chip(label, pressed, onclick, { plain } = {}) {
  return h(`button.chip.sketch${plain ? ".chip--plain" : ""}`, { type: "button", "aria-pressed": pressed ? "true" : "false", onclick },
    pressed && !plain ? raw(icon("check", "ico--sm")) : null, label);
}

export async function busy(btn, fn) {
  const old = btn.innerHTML;
  btn.classList.add("is-loading");
  btn.setAttribute("aria-busy", "true");
  btn.innerHTML = `${icon("spinner")} กำลังทำ…`;
  try { return await fn(); } finally { btn.classList.remove("is-loading"); btn.removeAttribute("aria-busy"); btn.innerHTML = old; }
}

// ---------- toast ----------
export function toast(message, { action, onAction, error = false, timeout } = {}) {
  const box = document.getElementById("toasts");
  const t = h("div.toast" + (error ? ".toast--error" : ""), { role: error ? "alert" : "status" },
    raw(icon(error ? "alert" : "check")), h("span", {}, message));
  const close = () => { t.classList.add("is-leaving"); setTimeout(() => t.remove(), 160); };
  if (action) t.append(h("button.toast__action", { type: "button", onclick: () => { close(); onAction?.(); } }, action));
  if (error) t.append(h("button", { type: "button", "aria-label": "ปิด", onclick: close }, raw(icon("x", "ico--sm"))));
  box.append(t);
  if (!error) setTimeout(close, timeout ?? 5000);
  return close;
}

// ---------- dialog ----------
export function confirmDialog({ title, body, confirm = "ยืนยัน", danger = false, icon: ic = danger ? "trash" : null }) {
  return new Promise((resolve) => {
    const dlg = document.getElementById("dialog");
    const done = (v) => { dlg.close(); resolve(v); };
    const cancelBtn = button("ยกเลิก", { onclick: () => done(false) });
    const okBtn = button(confirm, { kind: danger ? "danger" : "primary", icon: ic, onclick: () => done(true) });
    dlg.replaceChildren(h("div.dialog__panel.sketch.sketch--card", { role: "document" },
      h("h2.dialog__title", { id: "dlg-title" }, title),
      body ? h("p.dialog__body", {}, body) : null,
      h("div.dialog__actions", {}, cancelBtn, okBtn)));
    dlg.setAttribute("aria-labelledby", "dlg-title");
    dlg.onclick = (e) => { if (e.target === dlg) done(false); };
    dlg.oncancel = (e) => { e.preventDefault(); done(false); };
    dlg.showModal();
    cancelBtn.focus();
  });
}

export function showDialog(content, { onClose } = {}) {
  const dlg = document.getElementById("dialog");
  dlg.replaceChildren(content);
  const close = () => { dlg.close(); onClose?.(); };
  dlg.onclick = (e) => { if (e.target === dlg) close(); };
  dlg.oncancel = (e) => { e.preventDefault(); close(); };
  dlg.showModal();
  return close;
}

export function debounce(fn, ms = 300) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export const pad2 = (n) => String(n).padStart(2, "0");
export const hhmm = (min) => `${pad2(Math.floor((((min % 1440) + 1440) % 1440) / 60))}:${pad2((((min % 1440) + 1440) % 1440) % 60)}`;
export const toMin = (s) => { const [a, b] = String(s).split(":").map(Number); return a * 60 + b; };
export const decHours = (min) => (Math.round((min / 60) * 100 + 1e-9) / 100).toFixed(2);
export const hm = (min) => `${Math.floor(min / 60)}:${pad2(min % 60)}`;
export const fmtHours = (min, unit) => (unit === "hm" ? hm(min) : decHours(min));
export const hmThai = (min) => `${Math.floor(min / 60)} ชม. ${min % 60} นาที`;
