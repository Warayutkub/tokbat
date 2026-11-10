// The 24-hour ruler on the log screen: bars per session, drag the ends, click empty space to add one.
// Minutes are "absolute" for the day being edited: 0 = 00:00 of that day, 1440+ = the next day.
import { hhmm } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";
const H = 192, BASE = 150, BAR_TOP = 88, BAR_H = 50;
const SNAP = 5;

function s(tag, attrs = {}, parent) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) el.setAttribute(k, v);
  parent?.append(el);
  return el;
}

// Listeners live on window, not on the handle: every move redraws the SVG, which replaces the handle,
// and a listener (or pointer capture) on the old handle would stop the drag after the first step.
let refocus = null;
function startDrag(e, onMove, onEnd) {
  e.preventDefault();
  e.stopPropagation();
  document.body.classList.add("is-dragging");
  const move = (ev) => onMove(ev);
  const up = (ev) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    window.removeEventListener("pointercancel", up);
    document.body.classList.remove("is-dragging");
    onEnd?.(ev);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  window.addEventListener("pointercancel", up);
}

/** First hour shown: 06:00 unless something starts earlier. The window is always 24 hours. */
export function windowStart(items) {
  const earliest = Math.min(6 * 60, ...items.map((i) => i.startAbs));
  return Math.floor(earliest / 60) * 60;
}

/**
 * opts: { items:[{id, startAbs, endAbs, breakMin, label, sub, open}], selectedId, editable, errorId,
 *         dayLabel, nextLabel, nowAbs, mascot, onCreate(min), onSelect(id), onDrag(edge, min), onDragEnd() }
 */
export function drawTimeline(svg, opts) {
  const W = svg.clientWidth || 1168;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.replaceChildren();
  const ws = windowStart(opts.items);
  const x = (m) => ((m - ws) / 1440) * W;
  const toMin = (px) => Math.round((ws + (px / W) * 1440) / SNAP) * SNAP;

  // background hit area: click to add a session
  const hit = s("rect", { class: "tl-hit", x: 0, y: 10, width: W, height: BASE, "aria-label": "เพิ่มช่วงเวลา" }, svg);
  hit.addEventListener("click", (e) => {
    if (!opts.onCreate || svg._justDragged) return;   // the click that ends a drag must not add a session
    const r = svg.getBoundingClientRect();
    opts.onCreate(Math.round(toMin(e.clientX - r.left) / 15) * 15);
  });

  // the part after midnight
  const mid = x(1440);
  s("rect", { class: "tl-next", x: mid, y: 14, width: Math.max(0, W - mid), height: BASE - 16, rx: 10 }, svg);
  s("line", { class: "tl-midnight", x1: mid, y1: 14, x2: mid, y2: BASE }, svg);
  s("text", { class: "tl-day-label", x: 6, y: 30 }, svg).textContent = opts.dayLabel;
  const nl = s("text", { class: "tl-next-label", x: mid + 10, y: 30 }, svg);
  nl.textContent = `เที่ยงคืน → ${opts.nextLabel} (วันถัดไป)`;

  // ruler
  s("path", { class: "tl-grid", d: `M0 ${BASE} L${W} ${BASE}`, fill: "none" }, svg);
  const keys = new Set();
  for (const it of opts.items) { keys.add(Math.floor(it.startAbs / 60)); keys.add(Math.floor(it.endAbs / 60)); }
  for (let hr = ws / 60; hr <= ws / 60 + 24; hr++) {
    const px = x(hr * 60);
    s("path", { class: "tl-grid", d: `M${px} ${BASE} L${px} ${BASE - (hr % 3 === 0 ? 14 : 8)}` }, svg);
    const t = s("text", { class: "tl-label" + (keys.has(hr) || hr === 24 ? " tl-label--key" : ""), x: px, y: BASE + 20 }, svg);
    t.textContent = String(hr % 24).padStart(2, "0");
  }

  if (!opts.items.length) {
    const g = s("g", { class: "tl-empty" }, svg);
    const r = s("rect", { x: x(9 * 60), y: 96, width: 480, height: 40, rx: 14 }, g);
    const tx = s("text", { x: x(9 * 60) + 40, y: 121 }, g);
    tx.textContent = "ยังไม่มีช่วงเวลา — กดบนเส้นเวลาตรงเวลาที่เริ่มงาน";
    const plus = s("text", { x: x(9 * 60) + 16, y: 122, style: "font-size:20px" }, g); plus.textContent = "+";
    r.setAttribute("width", tx.getComputedTextLength() + 60);
    g.style.pointerEvents = "none";
    return;
  }

  for (const it of opts.items) {
    const sel = it.id === opts.selectedId;
    const x1 = x(it.startAbs), x2 = x(it.endAbs);
    const bar = s("rect", {
      class: "tl-bar" + (sel ? " tl-bar--sel" : "") + (it.draft ? " tl-bar--draft" : "") + (it.id === opts.errorId ? " tl-bar--error" : "") + (it.open ? " tl-bar--open" : ""),
      x: x1, y: sel ? BAR_TOP : BAR_TOP + 4, width: Math.max(6, x2 - x1), height: sel ? BAR_H : BAR_H - 8, rx: 12,
      tabindex: 0, role: "button", "aria-label": `${it.label} ${it.sub || ""}`,
    }, svg);
    bar.addEventListener("click", (e) => { e.stopPropagation(); if (!svg._justDragged) opts.onSelect?.(it.id); svg._justDragged = false; });
    if (sel && opts.editable && opts.onMove) {
      bar.classList.add("tl-bar--movable");
      bar.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
        const x0 = e.clientX, orig = { start: it.startAbs, end: it.endAbs };
        let moved = false;
        startDrag(e, (ev) => {
          const dx = ev.clientX - x0;
          if (!moved && Math.abs(dx) < 4) return;
          moved = true;
          opts.onMove(Math.round(((dx / W) * 1440) / SNAP) * SNAP, orig);
        }, () => { if (moved) { svg._justDragged = true; setTimeout(() => { svg._justDragged = false; }, 0); opts.onDragEnd?.(); } });
      });
    }
    bar.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); opts.onSelect?.(it.id); } });
    if (it.breakMin > 0 && x2 - x1 > 30) {
      const bw = ((x2 - x1) * it.breakMin) / (it.endAbs - it.startAbs);
      s("rect", { class: "tl-break", x: (x1 + x2) / 2 - bw / 2, y: (sel ? BAR_TOP : BAR_TOP + 4) + 6, width: bw, height: (sel ? BAR_H : BAR_H - 8) - 12, rx: 4, "pointer-events": "none" }, svg);
    }
    if (!sel && x2 - x1 > 150) {
      const t = s("text", { class: "tl-bar-text", x: (x1 + x2) / 2, y: BAR_TOP + 30, "text-anchor": "middle" }, svg);
      t.textContent = `${it.label} · ${it.sub}`;
    }
  }

  const cur = opts.items.find((i) => i.id === opts.selectedId);
  if (!cur) return;
  const err = cur.id === opts.errorId;
  const ends = cur.open ? [["start", cur.startAbs]] : [["start", cur.startAbs], ["end", cur.endAbs]];
  const flags = ends.map(([edge, m]) => flag(svg, x(m), W, edge === "start" ? "เข้างาน" : "ออกงาน", hhmm(m), err && edge === "start"));
  if (flags.length === 2) {
    const [a, b] = flags, gap = a.left + a.w + 6 - b.left;
    if (gap > 0) { a.move(Math.max(0, a.left - gap / 2)); b.move(Math.min(W - b.w, b.left + gap / 2)); }
  }
  for (const [edge, m] of ends) {
    const px = x(m);
    s("line", { class: "tl-stem", x1: px, y1: 62, x2: px, y2: BAR_TOP + 10 }, svg);
    if (!opts.editable) continue;
    const g = s("g", { tabindex: 0, role: "slider", "aria-label": edge === "start" ? "เวลาเข้างาน" : "เวลาออกงาน", "aria-valuetext": hhmm(m) }, svg);
    s("circle", { class: "tl-handle", cx: px, cy: BAR_TOP + BAR_H / 2, r: 13 }, g);
    s("path", { class: "tl-handle-grip", d: `M${px - 3} ${BAR_TOP + 19} v12 M${px + 3} ${BAR_TOP + 19} v12` }, g);
    g.style.cursor = "ew-resize";
    g.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      const r = svg.getBoundingClientRect();
      startDrag(e, (ev) => opts.onDrag?.(edge, toMin(ev.clientX - r.left)), () => {
        svg._justDragged = true;
        setTimeout(() => { svg._justDragged = false; }, 0);
        opts.onDragEnd?.();
      });
    });
    g.addEventListener("keydown", (e) => {
      const step = e.shiftKey ? 30 : 5;
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      refocus = edge;   // the redraw replaces this handle; focus the new one
      opts.onDrag?.(edge, m + (e.key === "ArrowLeft" ? -step : step));
      opts.onDragEnd?.();
    });
    if (refocus === edge) { refocus = null; g.focus(); }
  }
  if (opts.mascotSvg) {
    const endX = x(cur.open ? opts.nowAbs ?? cur.endAbs : cur.endAbs);
    const doc = new DOMParser().parseFromString(opts.mascotSvg, "image/svg+xml").documentElement;
    const m = document.importNode(doc, true);
    for (const [k, v] of Object.entries({ x: Math.min(endX + 2, W - 120), y: 50, width: 132, height: 132 })) m.setAttribute(k, v);
    m.classList.add("mascot");
    m.style.setProperty("--d", "-1.3s");
    m.style.pointerEvents = "none";
    svg.append(m);
  }
}

function flag(svg, cx, W, label, value, error) {
  const g = s("g", { class: "tl-flag" + (error ? " tl-flag--error" : "") }, svg);
  const r = s("rect", { y: 34, height: 28, rx: 14 }, g);
  const t1 = s("text", { y: 53 }, g); t1.textContent = label;
  const t2 = s("text", { class: "v", y: 54 }, g); t2.textContent = value;
  const w1 = t1.getComputedTextLength(), w2 = t2.getComputedTextLength();
  const w = 12 + w1 + 6 + w2 + 12;
  const place = (left) => { r.setAttribute("x", left); t1.setAttribute("x", left + 12); t2.setAttribute("x", left + 12 + w1 + 6); out.left = left; };
  r.setAttribute("width", w);
  const out = { w, left: 0, move: place };
  place(Math.min(W - w, Math.max(0, cx - w / 2)));
  return out;
}
