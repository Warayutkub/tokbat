// บันทึกเวลา — week strip, 24h timeline, the hours "equation", what was worked on.
import { call } from "../api.js";
import { drawTimeline } from "../timeline.js";
import { h, raw, icon, button, chip, toast, confirmDialog, mascot, loadMascot, busy, hhmm, toMin, fmtHours, hmThai } from "../ui.js";

const BREAKS = [[0, "ไม่พัก"], [30, "30 นาที"], [60, "1 ชม."], [90, "1 ชม. 30 นาที"]];

// A time box commits on blur. When that blur comes from pressing another button, repainting right away would swap
// the button out between mousedown and mouseup and the click would be lost, so the repaint waits for the pointer.
let pointerIsDown = false;
addEventListener("pointerdown", () => { pointerIsDown = true; }, true);
addEventListener("pointerup", () => { pointerIsDown = false; }, true);
addEventListener("pointercancel", () => { pointerIsDown = false; }, true);
function afterPointer(fn) {
  if (!pointerIsDown) return fn();
  addEventListener("pointerup", () => setTimeout(fn, 0), { once: true, capture: true });
}

/** What the user typed in a time box → minutes after midnight, or null. "8:03", "08.03", "0803", "803", "8", "24:00". */
export function parseTyped(text) {
  const t = String(text).trim().replace(/[.,;:\s]+/g, ":");
  let hh, mm;
  let m = t.match(/^(\d{1,2}):(\d{1,2})$/);
  if (m) [hh, mm] = [Number(m[1]), Number(m[2])];
  else if ((m = t.match(/^(\d{1,2})(\d{2})$/))) [hh, mm] = [Number(m[1]), Number(m[2])];
  else if ((m = t.match(/^(\d{1,2}):?$/))) [hh, mm] = [Number(m[1]), 0];
  else return null;
  if (hh === 24 && mm === 0) hh = 0;
  return hh > 23 || mm > 59 ? null : hh * 60 + mm;
}

export async function render(root, params, ctx) {
  const st = { date: params.date || ctx.today, day: null, sel: params.sid ? Number(params.sid) : null, draft: null, error: null, editing: null };
  const unit = () => ctx.settings.unit;

  async function load(keepSel = true) {
    st.writeSvg ??= await loadMascot("write");
    st.day = await call("day", st.date);
    const ses = st.day.sessions;
    if (!keepSel || !ses.some((x) => x.id === st.sel)) st.sel = ses.length ? ses[ses.length - 1].id : null;
    if (st.draft?.id && !ses.some((x) => x.id === st.draft.id)) st.draft = null;
    if (!st.draft || st.draft.id) st.draft = st.sel ? fromSession(ses.find((x) => x.id === st.sel)) : null;
    paint();
  }

  // a draft is the session being edited, in absolute minutes for this day
  function fromSession(x) {
    const start = toMin(x.start);
    let end = x.end === null ? null : toMin(x.end);
    if (end !== null && end <= start) end += 1440;
    return { id: x.id, start, end, break_min: x.break_min, note: x.note, open: x.open };
  }
  const span = (d) => (d.end === null ? 0 : d.end - d.start);
  const net = (d) => Math.max(0, span(d) - d.break_min);
  const KEYS = ["start", "end", "break_min", "note"];
  const touched = (dr) => !dr.orig || KEYS.some((k) => (dr.orig[k] ?? "") !== (dr[k] ?? ""));
  const dirty = () => {
    if (!st.draft) return false;
    if (!st.draft.id) return true;
    const o = fromSession(st.day.sessions.find((x) => x.id === st.draft.id));
    return ["start", "end", "break_min", "note"].some((k) => o[k] !== st.draft[k]);
  };

  function items() {
    const list = st.day.sessions.map((x, i) => {
      const d = st.draft && st.draft.id === x.id ? st.draft : fromSession(x);
      const nowAbs = st.day.now_abs;
      return { id: x.id, startAbs: d.start, endAbs: d.end ?? Math.max(nowAbs, d.start + 15), breakMin: d.break_min, open: x.open,
        label: `ช่วง ${i + 1}`, sub: x.open ? "กำลังทำงาน" : `${hhmm(d.start)}–${hhmm(d.end)} · ${fmtHours(net(d), unit())} ชม.` };
    });
    if (st.draft && !st.draft.id) list.push({ id: "draft", draft: true, startAbs: st.draft.start, endAbs: st.draft.end, breakMin: st.draft.break_min, label: "ช่วงใหม่", sub: "" });
    return list;
  }
  const selId = () => (st.draft && !st.draft.id ? "draft" : st.sel);

  // ---------------- paint ----------------
  function paint() {
    const d = st.day;
    root.replaceChildren(weekStrip(d), timelineCard(d), bottom(d));
    redrawTimeline();
  }

  function weekStrip(d) {
    const days = d.week.days.map((w) => h(`button.day${w.date === st.date ? ".day--sel.sketch.sketch--soft" : ""}${w.state === "done" ? ".day--done" : ""}${w.state === "future" ? ".day--future" : ""}${w.state === "miss" ? ".day--miss" : ""}${w.state === "off" ? ".day--off" : ""}`,
      { type: "button", "aria-pressed": w.date === st.date ? "true" : "false", onclick: () => go(w.date) },
      h("span.day__wd", {}, w.wd), h("span.day__n.num", {}, w.n), h("span.day__sub", {}, w.date === st.date && !w.minutes && w.state !== "off" ? (d.sessions.length ? `${d.sessions.length} ช่วง` : "ยังไม่กรอก") : w.sub)));
    const strip = h("section.week.card.sketch.sketch--card", { "aria-label": "สัปดาห์" },
      h("div.week__label", {}, h("b", {}, d.week.is_current ? "สัปดาห์นี้" : "สัปดาห์"), h("span", {}, d.week.label)),
      h("button.icon-btn.sketch", { type: "button", "aria-label": "สัปดาห์ก่อน", onclick: () => go(d.week.prev) }, raw(icon("left"))),
      ...days,
      h("button.icon-btn.sketch", { type: "button", "aria-label": "สัปดาห์ถัดไป", onclick: () => go(d.week.next) }, raw(icon("right"))),
      h("div.grow"));
    if (d.missing) {
      strip.append(h("div.missing.sketch", {},
        h("button", { type: "button", onclick: () => go(d.missing.date) }, h("b", {}, `ลืมกรอก ${d.missing.label}`), " กรอก →"),
        h("button.missing__off", { type: "button", title: "วันนั้นไม่ได้ทำงาน (ไม่ต้องเตือนอีก)", "aria-label": `${d.missing.label} ไม่ได้ทำงาน ไม่ต้องเตือนอีก`,
          onclick: () => markOff(d.missing.date, d.missing.label) }, raw(icon("x", "ico--sm")))));
    } else if (!d.is_today) {
      strip.append(button(`กลับไปวันนี้`, { icon: "arrow", small: true, onclick: () => go(ctx.today) }));
    }
    return strip;
  }

  function timelineCard(d) {
    const n = d.sessions.length + (st.draft && !st.draft.id ? 1 : 0);
    const over = items().some((i) => i.endAbs > 1440);
    const head = h("div.timeline__head", {}, h("b.card-title", {}, d.is_today ? "ไทม์ไลน์วันนี้" : `ไทม์ไลน์ ${d.label}`),
      n ? h("span.badge", {}, `${n} ช่วง`) : null, over ? h("span.badge.badge--night", {}, "ข้ามวัน") : null,
      !d.is_today && d.is_past ? h("span.badge.badge--accent", {}, "กรอกย้อนหลัง") : null,
      d.off ? h("span.badge.badge--off", {}, "วันหยุด") : null,
      h("span.hint", {}, n ? "กดที่ว่างบนเส้นเวลาเพื่อเพิ่มช่วงใหม่ · ลากหัว–ท้ายแท่งเพื่อปรับ" : "กดที่ว่างบนเส้นเวลาเพื่อเริ่มช่วงแรก"));
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", "เส้นเวลา 24 ชั่วโมง");
    st.svg = svg;
    return h("section.timeline.card.sketch.sketch--card", {}, head, svg);
  }

  function redrawTimeline() {
    if (!st.svg) return;
    drawTimeline(st.svg, {
      items: items(), selectedId: selId(), editable: !!st.draft && !st.draft.open, errorId: st.error ? selId() : null,
      dayLabel: st.day.label_short, nextLabel: st.day.next_label, nowAbs: st.day.now_abs, mascotSvg: ctx.settings.show_characters ? st.writeSvg : null,
      onCreate: (m) => newDraft(m),
      onSelect: (id) => select(id),
      onDrag: (edge, m) => {
        const dr = st.draft;
        if (edge === "start") dr.start = Math.max(0, Math.min(m, (dr.end ?? m + 5) - 5, 1435));
        else dr.end = Math.max(dr.start + 5, Math.min(m, dr.start + 1435));
        st.error = null;
        redrawTimeline();
        refreshEquation();
      },
      onMove: (delta, orig) => {
        const dr = st.draft, len = orig.end - orig.start;
        dr.start = Math.max(0, Math.min(orig.start + delta, 1435));
        if (dr.end !== null) dr.end = dr.start + len;
        st.error = null;
        redrawTimeline();
        refreshEquation();
      },
      onDragEnd: () => {},
    });
  }

  // Before moving to another session, adding one or changing day: keep what was edited. An untouched new session is
  // dropped; edits are saved (the save toast has undo). If saving fails (e.g. overlap) we stay and the red box says why.
  let leaving = null;
  function leaveDraft() {
    leaving ??= (async () => {
      const dr = st.draft;
      if (!dr || (!dr.id && !touched(dr)) || (dr.id && !dirty())) return true;
      return save();
    })().finally(() => { leaving = null; });
    return leaving;
  }

  // m: start minute, or a function that picks it once the current session is out of the way
  async function newDraft(m) {
    if (!(await leaveDraft())) return;
    const at = typeof m === "function" ? m() : m;
    const start = Math.max(0, Math.min(at, 1435));
    const end = Math.min(start + 120, start + 1435), break_min = ctx.settings.default_break || 0;
    st.draft = { id: null, start, end, break_min, note: "", orig: { start, end, break_min, note: "" } };
    st.error = null;
    paint();
  }
  // after the last session, rounded up to the half hour, with an hour's gap
  function nextStart() {
    const last = st.day.sessions.at(-1);
    if (!last) return 9 * 60;
    const end = toMin(last.end ?? last.start) + (last.end && toMin(last.end) <= toMin(last.start) ? 1440 : 0);
    return Math.min(Math.ceil((end + 60) / 30) * 30, 1435);
  }
  async function select(id) {
    if (id === "draft" || (st.draft && st.draft.id === id)) return;   // already editing it: keep unsaved changes
    if (!(await leaveDraft())) return;
    const x = st.day.sessions.find((s) => s.id === id);
    if (!x) return;
    st.sel = id;
    st.draft = fromSession(x);
    st.error = null;
    paint();
  }
  async function go(date) {
    if (!(await leaveDraft())) return;
    location.hash = `#/log?date=${date}`;
  }

  async function markOff(date, label) {
    await call("mark_day_off", date);
    await load();
    toast(`${label} เป็นวันหยุดแล้ว`, { action: "เลิกทำ", onAction: async () => { await call("unmark_day_off", date); await load(); } });
  }
  async function unmarkOff() {
    const d = st.day;
    await call("unmark_day_off", d.date);
    await load();
    toast(`${d.is_today ? "วันนี้" : d.label_short} ไม่ใช่วันหยุดแล้ว`, { action: "เลิกทำ", onAction: async () => { await call("mark_day_off", d.date); await load(); } });
  }

  // ---------------- bottom ----------------
  function bottom(d) {
    if (!d.sessions.length && !st.draft) return startFirst(d);
    return h("div.row.bottom", {}, equationCard(d), taskCard(d));
  }

  function dayOff(d) {
    return h("section.start-first.day-off.card.sketch.sketch--card.rise", {},
      mascot("break", 190),
      h("div.grow", {},
        h("h2", {}, d.is_today ? "วันนี้หยุด" : `${d.label} หยุด`),
        h("p.hint", { style: { fontSize: "15px", margin: "8px 0 18px" } },
          "ไม่นับเป็นวันลืมกรอก · ถ้าได้ทำงานวันนี้ก็เพิ่มช่วงได้เลย เครื่องหมายหยุดจะหายเอง"),
        h("div.chips", {},
          button("ยกเลิกวันหยุด", { icon: "x", onclick: (e) => busy(e.currentTarget, unmarkOff) }),
          button("เพิ่มช่วงแรก", { icon: "plus", onclick: () => newDraft(9 * 60) }))));
  }

  function startFirst(d) {
    if (d.off) return dayOff(d);
    const now = d.now_hhmm;
    return h("section.start-first.card.sketch.sketch--card.rise", {},
      mascot("idle", 190),
      h("div.grow", {},
        h("h2", {}, d.is_today ? "วันนี้ยังไม่ได้บันทึกเลย" : `${d.label} ยังไม่มีเวลาที่บันทึก`),
        h("p.hint", { style: { fontSize: "15px", margin: "8px 0 18px" } },
          d.is_today ? "เพิ่มช่วงแรกได้ 2 แบบ: กรอกเวลาเอง หรือกดเริ่มงานตอนนี้ แล้วค่อยกดเลิกงานทีหลัง" : "กดบนเส้นเวลาด้านบน หรือกดปุ่มด้านล่างเพื่อกรอกย้อนหลัง"),
        h("div.chips", {},
          button("เพิ่มช่วงแรก", { kind: "primary", icon: "plus", onclick: () => newDraft(9 * 60) }),
          d.is_today ? button(`เริ่มงานตอนนี้ (${now})`, { icon: "clock", onclick: async (e) => { await busy(e.currentTarget, () => call("start_now")); await load(false); } }) : null,
          button(d.is_today ? "วันนี้หยุด" : "วันนั้นหยุด", { icon: "coffee", onclick: (e) => busy(e.currentTarget, () => markOff(d.date, d.is_today ? "วันนี้" : d.label_short)) }))));
  }

  let eqHost;
  function equationCard(d) {
    eqHost = h("section.equation.card.sketch.sketch--card", { "aria-label": "เวลาทำงานสุทธิ" });
    refreshEquation();
    return eqHost;
  }

  function refreshEquation() {
    if (!eqHost) return;
    const d = st.day, dr = st.draft;
    const pills = d.sessions.map((x, i) => h(`button.session-pill.sketch${st.error && dr && dr.id === x.id ? ".session-pill--error" : ""}`,
      { type: "button", "aria-pressed": dr && dr.id === x.id ? "true" : "false", onclick: () => select(x.id) },
      dr && dr.id === x.id ? `${i + 1} · ${hhmm(dr.start)}–${dr.end === null ? "ตอนนี้" : hhmm(dr.end)}` : `${i + 1} · ${x.start}–${x.end ?? "ตอนนี้"}`));
    if (dr && !dr.id) pills.push(h(`button.session-pill.sketch${st.error ? ".session-pill--error" : ""}`, { type: "button", "aria-pressed": "true" }, `ใหม่ · ${hhmm(dr.start)}–${hhmm(dr.end)}`));
    const add = h("button.session-pill.sketch", { type: "button", onclick: () => newDraft(nextStart) }, raw(icon("plus", "ico--sm")), "เพิ่มช่วง");
    // one session: nothing to switch between, so only "+ เพิ่มช่วง"; the very first (unsaved) one: no row at all
    const count = pills.length;
    const kids = [];
    if (count > 1) kids.push(h("div.sessions", {}, h("b", {}, "ช่วงเวลา"), ...pills, add));
    else if (d.sessions.length) kids.push(h("div.sessions", {}, h("button.session-pill.sketch", { type: "button", onclick: () => newDraft(nextStart) },
      raw(icon("plus", "ico--sm")), d.is_today ? "เพิ่มอีกช่วงในวันนี้" : "เพิ่มอีกช่วงในวันเดียวกัน")));
    if (dr) {
      const errStart = st.error?.code === "overlap";
      kids.push(h("div.eq", {},
        dr.open ? h("div.eq__term", {}, h("span.eq__open", {}, "ยังไม่เลิก"), h("small", {}, "กำลังทำงาน"))
          : timeTerm("end", dr.end, dr.end >= 1440 ? "ออกงาน (วันถัดไป)" : "ออกงาน"),
        h("span.eq__op", {}, "−"),
        timeTerm("start", dr.start, errStart ? "เข้างาน · ทับช่วงอื่น" : "เข้างาน", errStart),
        h("span.eq__op", {}, "−"),
        h("div.eq__term.eq__term--break", {}, h("button.num", { type: "button", onclick: () => eqHost.querySelector(".break-chips .chip")?.focus() }, hhmm(dr.break_min).replace(/^0/, "")), h("small", {}, dr.break_min ? "พัก" : "ไม่พัก")),
        h("span.eq__op", {}, "="),
        h("div.eq__term", {}, h(`span.eq__result.num${st.error || dr.open ? ".eq__result--dim" : ""}`, {}, dr.open ? "…" : fmtHours(net(dr), unit())),
          h("small", {}, `ชม. (${dr.id ? "ช่วง " + (d.sessions.findIndex((x) => x.id === dr.id) + 1) : "ช่วงใหม่"})`))));
      const custom = !BREAKS.some(([m]) => m === dr.break_min);
      kids.push(h("div.chips.break-chips", {}, h("b", { style: { font: "var(--text-title)", fontSize: "14px" } }, "พัก"),
        ...BREAKS.map(([m, l]) => chip(l, dr.break_min === m, () => { dr.break_min = m; st.error = null; redrawTimeline(); refreshEquation(); })),
        custom ? chip(`${dr.break_min} นาที`, true, () => {}) : null,
        h("label.input.sketch", { style: { width: "150px", padding: "6px 10px" } }, h("input", { type: "number", min: 0, step: 1, placeholder: "กำหนดเอง", "aria-label": "เวลาพักเป็นนาที",
          onchange: (e) => { const v = Math.max(0, Number(e.target.value) || 0); dr.break_min = v; st.error = null; redrawTimeline(); refreshEquation(); } }), h("span.hint", {}, "นาที"))));
      if (st.error) {
        kids.push(h("div.alert", { role: "alert" }, raw(icon("alert")), h("span.grow", {}, st.error.message),
          st.error.suggest_start ? button(`เปลี่ยนเป็น ${st.error.suggest_start}`, { small: true, onclick: () => { dr.start = toMin(st.error.suggest_start); if (dr.end !== null && dr.end <= dr.start) dr.end += 1440; st.error = null; redrawTimeline(); refreshEquation(); } }) : null));
      } else {
        const total = d.sessions.reduce((a, x) => a + (dr.id === x.id ? net(dr) : x.minutes), 0) + (dr.id ? 0 : net(dr));
        const n = d.sessions.length + (dr.id ? 0 : 1);
        const parts = d.sessions.map((x) => fmtHours(dr.id === x.id ? net(dr) : x.minutes, unit()));
        if (!dr.id) parts.push(fmtHours(net(dr), unit()));
        kids.push(h("div.daytotal", {}, h("span", {}, `${d.is_today ? "วันนี้" : d.label_short} รวม ${n} ช่วง`),
          n > 1 ? h("span.muted.num", {}, `${parts.join(" + ")} =`) : null, h("b.num", {}, `${fmtHours(total, unit())} ชม.`), h("span.muted", {}, `(${hmThai(total)})`)));
      }
    }
    eqHost.replaceChildren(...kids);
    refreshTask();
  }

  function timeTerm(edge, m, label, error) {
    const wrap = h(`div.eq__term${error ? ".eq__term--error" : ""}`);
    const show = () => {
      const b = h("button.num", { type: "button", title: "กดเพื่อพิมพ์เวลา", onclick: () => edit() }, hhmm(m));
      wrap.replaceChildren(b, h("small", {}, label));
    };
    // A plain text box (not <input type=time>): any minute, no picker icon covering the digits.
    // Accepts 8:03, 08.03, 0803, 803 or 8. ↑/↓ = ±1 minute, Shift = ±15.
    const edit = () => {
      const inp = h("input.num.time-input", { type: "text", inputmode: "numeric", value: hhmm(m % 1440), "aria-label": label,
        maxlength: 5, autocomplete: "off", spellcheck: "false", placeholder: "00:00" });
      const hint = h("small", {}, label);
      let closed = false;
      const done = () => {
        if (closed) return;
        if (!inp.value.trim()) { closed = true; return show(); }
        const v = parseTyped(inp.value);
        if (v === null) {
          inp.classList.add("time-input--bad");
          hint.textContent = "พิมพ์แบบ 08:03";
          inp.focus();
          return;
        }
        closed = true;
        const dr = st.draft;
        if (edge === "start") { dr.start = v; if (dr.end !== null) { let e = dr.end % 1440; dr.end = e <= v ? e + 1440 : e; } }
        else { dr.end = v <= dr.start ? v + 1440 : v; }
        st.error = null;
        afterPointer(() => { redrawTimeline(); refreshEquation(); });
      };
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); done(); }
        else if (e.key === "Escape") { closed = true; show(); }
        else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
          e.preventDefault();
          const cur = parseTyped(inp.value) ?? m % 1440;
          const step = (e.shiftKey ? 15 : 1) * (e.key === "ArrowUp" ? 1 : -1);
          inp.value = hhmm((((cur + step) % 1440) + 1440) % 1440);
          inp.classList.remove("time-input--bad");
          hint.textContent = label;
        }
      });
      inp.addEventListener("input", () => { inp.classList.remove("time-input--bad"); hint.textContent = label; });
      inp.addEventListener("blur", () => { if (!closed && parseTyped(inp.value) === null && inp.value.trim()) { closed = true; show(); } else done(); });
      wrap.replaceChildren(inp, hint);
      inp.focus();
      inp.select();
    };
    show();
    return wrap;
  }

  let taskHost;
  function taskCard() {
    taskHost = h("section.task.card.sketch.sketch--card");
    refreshTask();
    return taskHost;
  }
  function refreshTask() {
    if (!taskHost || !st.draft) return;
    const dr = st.draft, d = st.day;
    const idx = dr.id ? d.sessions.findIndex((x) => x.id === dr.id) + 1 : null;
    const clearHost = h("span");
    const paintClear = () => clearHost.replaceChildren(clearButton());
    const ta = h("textarea", { "aria-label": "ทำอะไรไปบ้าง", placeholder: "เช่น ออกแบบหน้าจอ แก้บั๊ก", oninput: (e) => { dr.note = e.target.value; paintClear(); } });
    ta.value = dr.note || "";
    paintClear();
    const saveBtn = dr.open
      ? button("เลิกงานตอนนี้", { kind: "primary", icon: "check", onclick: (e) => busy(e.currentTarget, stopNow) })
      : button("บันทึก", { kind: "primary", icon: "check", onclick: (e) => busy(e.currentTarget, save) });
    taskHost.replaceChildren(
      h("b.card-title", {}, `${idx ? "ช่วง " + idx : "ช่วงใหม่"} ทำอะไร (ไปขึ้นในช่องหมายเหตุ)`),
      ta,
      h("div.task__actions", {}, mascot("eraser", 66), clearHost, h("div.grow"), saveBtn));
  }

  // what "clear" means depends on the session: drop a new one, undo edits, cancel a started one, or delete a saved one
  function clearButton() {
    const dr = st.draft;
    if (dr.open) return button("ยกเลิกการเริ่มงาน", { kind: "danger-line", icon: "x", onclick: cancelStart });
    if (!dr.id) return button("ยกเลิก", { icon: "x", onclick: clear });
    if (dirty()) return button("ยกเลิกที่แก้", { icon: "x", onclick: clear });
    return button("ลบช่วงนี้", { kind: "danger-line", icon: "trash", onclick: removeCurrent });
  }

  // ---------------- actions ----------------
  function clear() {
    if (!st.draft) return;
    if (!st.draft.id) st.draft = st.sel ? fromSession(st.day.sessions.find((x) => x.id === st.sel)) : null;
    else st.draft = fromSession(st.day.sessions.find((x) => x.id === st.draft.id));
    st.error = null;
    paint();
  }

  async function removeCurrent() {
    const dr = st.draft, idx = st.day.sessions.findIndex((x) => x.id === dr.id) + 1;
    const ok = await confirmDialog({ title: `ลบช่วง ${idx} (${hhmm(dr.start)}–${hhmm(dr.end)}) ของ ${st.day.label_short}?`,
      body: `ชั่วโมงช่วงนี้ (${fmtHours(net(dr), unit())}) จะหายไปจากรายงานด้วย`, confirm: "ลบช่วงนี้", danger: true });
    if (!ok) return;
    const res = await call("delete_session", dr.id);
    st.draft = null;
    await load(false);
    toast("ลบช่วงแล้ว", { action: "เลิกทำ", onAction: async () => { await call("restore_session", res.deleted); st.sel = res.deleted.id; st.draft = null; await load(); toast("เอากลับมาแล้ว"); } });
  }

  async function cancelStart() {
    const dr = st.draft;
    const ok = await confirmDialog({ title: `ยกเลิกการเริ่มงานตอน ${hhmm(dr.start)}?`, body: "ช่วงที่กำลังจับเวลาอยู่จะถูกลบทิ้ง", confirm: "ยกเลิกการเริ่มงาน", danger: true, icon: "x" });
    if (!ok) return;
    const res = await call("delete_session", dr.id);
    st.draft = null;
    await load(false);
    toast("ยกเลิกการเริ่มงานแล้ว", { action: "เลิกทำ", onAction: async () => { await call("restore_session", res.deleted); st.draft = null; await load(); } });
  }

  function payload(dr) {
    return { id: dr.id || null, date: st.date, start: hhmm(dr.start), end: dr.end === null ? null : hhmm(dr.end), break_min: dr.break_min, note: dr.note || "" };
  }

  async function save() {
    const dr = st.draft;
    const res = await call("save_session", payload(dr));
    if (!res.ok) {
      st.error = res.error;
      redrawTimeline(); refreshEquation();
      eqHost?.querySelector(".alert")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return false;
    }
    st.error = null;
    st.sel = res.session.id;
    st.draft = null;
    await load();
    const idx = st.day.sessions.findIndex((x) => x.id === res.session.id) + 1;
    toast(`บันทึกช่วง ${idx} แล้ว · ${st.day.is_today ? "วันนี้" : st.day.label_short} รวม ${fmtHours(st.day.total_min, unit())} ชม.`, {
      action: "เลิกทำ",
      onAction: async () => {
        if (res.previous) await call("save_session", { ...res.previous });
        else await call("delete_session", res.session.id);
        st.draft = null;
        await load(false);
        toast("ย้อนกลับแล้ว");
      },
    });
    return true;
  }

  async function stopNow() {
    const res = await call("stop_now", st.draft.id);
    if (!res.ok) { st.error = res.error; refreshEquation(); return; }
    st.draft = null;
    await load();
    toast(`เลิกงานแล้ว · ช่วงนี้ ${fmtHours(res.session.minutes, unit())} ชม.`);
  }

  window.addEventListener("resize", redrawTimeline, { once: false });
  await load();
  return () => window.removeEventListener("resize", redrawTimeline);
}
