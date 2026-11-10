// Decorating: drag pieces from the tray onto the grass, drag them around, flip them or put them back.
// Nothing is saved until "เสร็จ"; "ยกเลิก" puts the garden back the way it was.
import { call } from "../api.js";
import { h, raw, button, chip, toast } from "../ui.js";
import { itemSvg, CATS } from "./art.js";
import { W, FEET_MIN, FEET_MAX } from "./stage.js";

const ICON_FLIP = '<svg class="ico ico--sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v18"/><path d="M9 6L3 12l6 6z"/><path d="M15 6l6 6-6 6z"/></svg>';
const ICON_STORE = '<svg class="ico ico--sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h16v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/><path d="M3 5h18v4H3zM10 13h4"/></svg>';

export function startDecorate({ card, stage, m, rows, onExit }) {
  const original = rows.map((r) => ({ ...r }));
  const live = new Map(rows.map((r) => [r.id, { ...r }]));
  const changed = new Set();
  let cat = "all";
  let selected = null;
  stage.setDecor(true);

  const banner = h("div.g-banner.sketch", {}, raw(ICON_BRUSH), h("b", {}, "โหมดตกแต่ง"),
    h("span", {}, "ลากของจากถาดมาวาง · คลิกของบนลานเพื่อย้าย กลับด้าน หรือเก็บ"),
    button("ยกเลิก", { small: true, onclick: () => exit(false) }),
    button("เสร็จ", { kind: "primary", small: true, onclick: () => exit(true) }));
  const top = h("div.g-hud", { style: { justifyContent: "flex-start" } }, banner);
  const tools = h("div.g-tools.sketch", { hidden: true },
    h("button", { type: "button", onclick: () => flip() }, raw(ICON_FLIP), "กลับด้าน"),
    h("button", { type: "button", onclick: () => store() }, raw(ICON_STORE), "เก็บเข้าถาด"));
  const tray = h("div.g-tray.sketch.sketch--card");
  card.append(top, tools, tray);

  // ---------------------------------------------------------------- tray
  async function paintTray() {
    const inTray = [...live.values()].filter((r) => r.x === null);
    const groups = new Map();
    for (const r of inTray) {
      const d = m.byId[r.item];
      if (!d || (cat !== "all" && d.cat !== cat)) continue;
      if (!groups.has(r.item)) groups.set(r.item, []);
      groups.get(r.item).push(r);
    }
    const tiles = await Promise.all([...groups.entries()].map(async ([id, list]) => {
      const d = m.byId[id];
      const art = h("div.tile__art");
      art.append(await itemSvg(id));
      const t = h("div.tile.sketch.sketch--soft", { role: "button", tabindex: "0", title: `ลาก${d.name}ไปวางบนลาน` }, art,
        h("span.tile__name", {}, d.name), h("span.tile__n", {}, `×${list.length}`));
      t.addEventListener("pointerdown", (e) => dragNew(e, id));
      t.addEventListener("keydown", (e) => { if (e.key === "Enter") dropAt(id, W / 2, 640); });
      return t;
    }));
    tray.replaceChildren(
      h("div.g-tray__head", {}, h("div.chips", {}, chip("ทั้งหมด", cat === "all", () => { cat = "all"; paintTray(); }, { plain: true }),
        ...CATS.map(([k, label]) => chip(label, cat === k, () => { cat = k; paintTray(); }, { plain: true }))),
        h("span.hint", { style: { fontSize: "13px" } }, `ของในถาด ${inTray.length} ชิ้น`)),
      h("div.g-tray__items", {}, ...(tiles.length ? tiles : [h("p.tray-empty", {}, inTray.length ? "หมวดนี้ไม่มีของในถาด" : "ถาดว่างแล้ว · ซื้อของเพิ่มได้ที่ร้านค้า")])));
  }

  // ---------------------------------------------------------------- placing
  const clampPos = (d, x, y) => ({
    x: Math.max(-d.w * 0.4, Math.min(W - d.w * 0.6, x)),
    y: Math.max(FEET_MIN - 70 - d.h, Math.min(FEET_MAX + 6 - d.h, y)),
  });

  async function dropAt(id, cx, cy) {
    const row = [...live.values()].find((r) => r.item === id && r.x === null);
    if (!row) return;
    const d = m.byId[id];
    Object.assign(row, clampPos(d, cx - d.w / 2, cy - d.h + 6));
    changed.add(row.id);
    const it = await stage.addItem(row);
    paintTray();
    select(it);
  }

  function dragNew(e, id) {
    if (e.button !== 0) return;
    e.preventDefault();
    const d = m.byId[id];
    const ghost = h("div.g-ghost", { style: { width: `${d.w * stage.s}px`, height: `${d.h * stage.s}px` } });
    itemSvg(id).then((s) => ghost.append(s));
    document.body.append(ghost);
    document.body.classList.add("is-dragging");
    const move = (ev) => { Object.assign(ghost.style, { left: `${ev.clientX - (d.w * stage.s) / 2}px`, top: `${ev.clientY - d.h * stage.s + 6}px` }); };
    move(e);
    const up = (ev) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      ghost.remove();
      document.body.classList.remove("is-dragging");
      const r = stage.el.getBoundingClientRect();
      const tr = tray.getBoundingClientRect();
      const inside = ev.clientX > r.left && ev.clientX < r.right && ev.clientY > r.top && ev.clientY < tr.top;
      if (!inside) return;
      const p = stage.toWorld(ev.clientX, ev.clientY);
      dropAt(id, p.x, p.y);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  function select(it) {
    stage.layer.querySelectorAll(".g-item.is-selected").forEach((e) => e.classList.remove("is-selected"));
    selected = it;
    if (!it) { tools.hidden = true; return; }
    it.el.classList.add("is-selected");
    placeTools();
  }

  function placeTools() {
    if (!selected) return;
    const r = selected.el.getBoundingClientRect();
    const c = card.getBoundingClientRect();
    tools.hidden = false;
    Object.assign(tools.style, { left: `${r.left - c.left + r.width / 2}px`, top: `${Math.max(56, r.top - c.top - 12)}px` });
  }

  function onDown(e) {
    const el = e.target.closest(".g-item");
    if (!el || e.button !== 0) { if (!e.target.closest(".g-tools")) select(null); return; }
    e.preventDefault();
    const it = stage.items.get(Number(el.dataset.id));
    if (!it) return;
    select(it);
    const start = stage.toWorld(e.clientX, e.clientY);
    const from = { x: it.row.x, y: it.row.y };
    let moved = false;
    el.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const p = stage.toWorld(ev.clientX, ev.clientY);
      if (!moved && Math.hypot(p.x - start.x, p.y - start.y) < 3) return;
      moved = true;
      el.classList.add("is-dragging");
      tools.hidden = true;
      Object.assign(it.row, clampPos(it.def, from.x + p.x - start.x, from.y + p.y - start.y));
      stage.place(it);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.classList.remove("is-dragging");
      if (moved) {
        Object.assign(live.get(it.row.id), { x: it.row.x, y: it.row.y });
        changed.add(it.row.id);
        stage.place(it);
      }
      placeTools();
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  }
  stage.el.addEventListener("pointerdown", onDown);

  function flip() {
    if (!selected) return;
    selected.row.flip = !selected.row.flip;
    live.get(selected.row.id).flip = selected.row.flip;
    changed.add(selected.row.id);
    stage.place(selected);
  }

  function store() {
    if (!selected) return;
    const id = selected.row.id;
    Object.assign(live.get(id), { x: null, y: null });
    changed.add(id);
    stage.removeItem(id);
    select(null);
    paintTray();
  }

  const onKey = (e) => {
    if (e.key === "Escape") select(null);
    if ((e.key === "Delete" || e.key === "Backspace") && selected && !e.target.closest("input")) store();
  };
  window.addEventListener("keydown", onKey);
  const onResize = () => placeTools();
  window.addEventListener("resize", onResize);

  function cleanup() {
    stage.el.removeEventListener("pointerdown", onDown);
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", onResize);
    select(null);
    top.remove(); tools.remove(); tray.remove();
    stage.setDecor(false);
  }

  async function exit(save) {
    if (save && changed.size) {
      const list = [...changed].map((id) => live.get(id)).map((r) => ({ id: r.id, x: r.x, y: r.y, flip: !!r.flip }));
      const r = await call("decor_save", list);
      if (!r.ok) return toast("บันทึกการจัดลานไม่สำเร็จ", { error: true });
    }
    cleanup();
    if (!save) rows.splice(0, rows.length, ...original);
    onExit(save && changed.size > 0);
  }

  paintTray();
  return { abort: () => cleanup() };
}

const ICON_BRUSH = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4l6 6-9 9-6-6z"/><path d="M5 13l-2 8 8-2"/></svg>';
