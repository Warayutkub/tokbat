// รายงาน — totals, stacked daily chart, rows, and the export panel (A4 PDF / PNG like the user's sheet).
import { call } from "../api.js";
import { h, raw, icon, button, chip, toast, mascot, busy, showDialog, debounce } from "../ui.js";

const COLS = [["date", "วันที่"], ["start", "เวลาเริ่ม"], ["end", "เวลาหยุด"], ["hours", "ชั่วโมง"], ["note", "หมายเหตุ"], ["break", "เวลาพัก"]];

export async function render(root, params, ctx) {
  const s0 = ctx.settings;
  const st = { kind: params.kind || "cycle", offset: 0, start: params.start, end: params.end, title: null, titleEdited: false,
    unit: s0.unit, columns: [...s0.report_columns], footnote: s0.report_footnote, timestamp: s0.report_timestamp, mascot: s0.report_mascot, rep: null };

  async function period() {
    if (st.kind === "custom" && st.start) return;
    Object.assign(st, await call("period", st.kind, ctx.today, st.offset));
    if (!st.titleEdited) st.title = null;
  }
  const opts = () => ({ start: st.start, end: st.end, title: st.title, unit: st.unit, columns: st.columns, footnote: st.footnote, timestamp: st.timestamp, mascot: st.mascot });

  async function load() {
    await period();
    st.rep = await call("report", st.start, st.end, st.unit);
    if (!st.title) st.title = st.rep.default_title;
    paint();
  }
  const persist = debounce(() => call("save_settings", { unit: st.unit, report_columns: st.columns, report_footnote: st.footnote, report_timestamp: st.timestamp, report_mascot: st.mascot }).then((s) => { ctx.settings = s; }), 400);

  function paint() {
    const r = st.rep;
    root.replaceChildren(h("div.row.grow", {}, board(r), exportPanel(r)));
  }

  function board(r) {
    const head = h("div.board__head", {},
      h("div", {}, h("p.hint", {}, `รายงาน · ${r.label}`), h("h1.board__title", {}, st.title)),
      h("div.chips", {},
        chip("สัปดาห์", st.kind === "week", () => { st.kind = "week"; st.offset = 0; load(); }, { plain: true }),
        chip(ctx.settings.cycle_mode === "month" ? "เดือน" : "รอบตัดยอด", st.kind === "cycle", () => { st.kind = "cycle"; st.offset = 0; load(); }, { plain: true }),
        chip("กำหนดช่วง", st.kind === "custom", () => { st.kind = "custom"; paint(); root.querySelector(".date-range input")?.focus(); }, { plain: true }),
        st.kind === "custom"
          ? h("span.date-range.sketch", {}, raw(icon("calendar", "ico--sm")),
              h("input", { type: "date", value: st.start, "aria-label": "ตั้งแต่วันที่", onchange: (e) => { st.start = e.target.value; load(); } }), "–",
              h("input", { type: "date", value: st.end, "aria-label": "ถึงวันที่", onchange: (e) => { st.end = e.target.value; load(); } }))
          : h("span.date-range.sketch", {},
              h("button", { type: "button", "aria-label": "ช่วงก่อนหน้า", onclick: () => { st.offset--; load(); } }, raw(icon("left", "ico--sm"))),
              h("span", {}, r.label_short),
              h("button", { type: "button", "aria-label": "ช่วงถัดไป", onclick: () => { st.offset++; load(); } }, raw(icon("right", "ico--sm"))))));
    if (!r.sessions) {
      return h("section.board.card.sketch.sketch--card", {}, head, h("div.empty", {}, mascot("break", 150),
        h("p.empty__title", {}, `${r.label} ยังไม่มีเวลาที่บันทึก`),
        h("p.hint", {}, "ลองเลือกช่วงอื่น หรือกรอกย้อนหลังจากหน้าบันทึกเวลา"),
        h("div.empty__actions", {}, button("ไปหน้าบันทึกเวลา", { icon: "clock", onclick: () => { location.hash = "#/log"; } }),
          r.latest ? button("ดูช่วงล่าสุดที่มีข้อมูล", { onclick: () => { st.kind = "custom"; st.start = r.latest.start; st.end = r.latest.end; load(); } }) : null)));
    }
    const max = Math.max(1, ...r.per_day.map((d) => d.day_min + d.night_min));
    const many = r.per_day.length > 31;
    const chart = h("div.chart", { role: "img", "aria-label": `ชั่วโมงรายวัน รวม ${r.total} ชม.` },
      ...r.per_day.map((d, i) => {
        const t = d.day_min + d.night_min;
        const stack = h("div.chart__stack");
        if (d.night_min) stack.append(h("div.chart__seg.chart__seg--night", { style: { height: `${(d.night_min / max) * 116}px`, animationDelay: `${i * 18}ms` } }));
        if (d.day_min) stack.append(h("div.chart__seg.chart__seg--day", { style: { height: `${(d.day_min / max) * 116}px`, animationDelay: `${i * 18}ms` } }));
        if (!t) stack.append(h("div.chart__seg.chart__seg--none"));
        return h("div.chart__col", { title: `${d.weekday} ${d.day} · ${d.total} ชม.` }, !many && t ? h("span.chart__v.num", {}, d.total) : null, stack, h("span.chart__d.num", {}, many && d.day % 5 && d.day !== 1 ? "" : d.day));
      }));
    const rows = r.rows.map((x) => h(`tr${x.overnight ? ".night" : ""}`, {},
      h("td", {}, x.date_slash), h("td.num", {}, `${x.start} – ${x.end}`), h("td.h.num", {}, x.hours_text), h("td.note", {}, x.note)));
    return h("section.board.card.sketch.sketch--card", {}, head,
      h("div.numbers", {},
        h("div", {}, h("div.numbers__total", {}, h("span.big.num", {}, r.total), h("b", { style: { font: "600 20px var(--font)", marginLeft: "8px" } }, "ชม.")),
          h("p.hint", {}, `= ${r.total_hm} (คิดจากนาทีจริง)`)),
        stat(r.days, "วันที่ทำงาน"), r.days_off ? stat(r.days_off, "วันหยุด", "var(--color-night-text)") : null, stat(r.sessions, "ช่วงเวลา"), stat(r.avg, "เฉลี่ย ชม./วัน", "var(--color-work-text)"), stat(r.overnight, "ช่วงข้ามวัน", "var(--color-night-text)")),
      chart,
      h("div.legend", {}, h("span", {}, h("i", { style: { background: "var(--color-work)" } }), "ช่วงกลางวัน"), h("span", {}, h("i", { style: { background: "var(--color-night)" } }), "ช่วงข้ามวัน (เลิกหลังเที่ยงคืน)")),
      h("div.rtable", {}, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "วันที่"), h("th", {}, "เวลาเริ่ม–หยุด"), h("th", {}, "ชั่วโมง"), h("th", {}, "หมายเหตุ"))), h("tbody", {}, ...rows))));
  }
  const stat = (v, l, c) => h("div.stat", { style: { paddingBottom: "16px" } }, h("b.num", { style: c ? { color: c } : {} }, v), h("span", {}, l));

  function exportPanel(r) {
    const empty = !r.sessions;
    const thumb = empty ? h("div.thumb.thumb--empty", {}, "ไม่มีข้อมูล") : h("button.thumb", { type: "button", "aria-label": "ดูตัวอย่างเต็มหน้า", onclick: preview });
    if (!empty) refreshThumb(thumb);
    const titleInput = h("input", { value: st.title, "aria-label": "ชื่อหัวรายงาน", oninput: debounce((e) => { st.title = e.target.value; st.titleEdited = true; refreshThumb(thumb); }, 300) });
    const cols = COLS.map(([k, l]) => chip(l, st.columns.includes(k), () => {
      st.columns = st.columns.includes(k) ? st.columns.filter((c) => c !== k) : [...st.columns, k];
      persist(); paint();
    }));
    const opt = (key, label) => h("label.check", {}, h("input", { type: "checkbox", checked: st[key], onchange: (e) => { st[key] = e.target.checked; persist(); refreshThumb(thumb); } }),
      h("span.check__box.sketch", {}, raw(icon("check", "ico--sm"))), label);
    const pdfBtn = button("บันทึกเป็น PDF", { kind: "primary", icon: "download", disabled: empty, onclick: (e) => doExport(e.currentTarget, "pdf") });
    const pngBtn = button("PNG", { icon: "image", disabled: empty, onclick: (e) => doExport(e.currentTarget, "png") });
    pdfBtn.style.flex = "1";
    return h("aside.export.card.sketch.sketch--card", { "aria-label": "ส่งออกรายงาน" },
      h("div.board__head", {}, h("h2", { style: { font: "var(--text-h2)" } }, "ส่งออกรายงาน"), h("span.hint", {}, "PDF / PNG · กระดาษ A4")),
      h("div.export__top", {}, thumb, h("div.export__fields", {},
        h("label.field", {}, h("span.field__label", {}, "ชื่อหัวรายงาน"), h("span.input.sketch", {}, titleInput)),
        h("div.field", {}, h("span.field__label", {}, "ช่วงวันที่"), h("span.input.sketch", {}, raw(icon("calendar", "ico--sm")), h("span", {}, r.label))),
        h("div.field", {}, h("span.field__label", {}, "หน่วยชั่วโมง"), h("div.chips", {},
          chip("ทศนิยม 6.75", st.unit === "decimal", () => { st.unit = "decimal"; persist(); load(); }),
          chip("ชม.:นาที 6:45", st.unit === "hm", () => { st.unit = "hm"; persist(); load(); }))))),
      h("span.field__label", {}, "คอลัมน์ในตาราง"), h("div.chips", {}, ...cols),
      h("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } },
        opt("footnote", "บรรทัดอธิบายหน่วยทศนิยมท้ายตาราง"), opt("timestamp", "วันเวลาที่พิมพ์ที่ท้ายกระดาษ"), opt("mascot", "ตัวการ์ตูนเล็กมุมกระดาษ")),
      h("div.grow"),
      recent(r),
      empty ? h("p.reason", {}, raw(icon("alert", "ico--sm")), "ช่วงนี้ไม่มีข้อมูล จึงยังส่งออกไม่ได้") : null,
      h("div.export__buttons", {}, pngBtn, pdfBtn));
  }

  function recent(r) {
    if (!r.recent?.length) return null;
    return h("div.recent", {}, h("span.field__label", {}, "ส่งออกล่าสุด"),
      ...r.recent.map((x) => h("div.recent__row", {}, raw(icon(x.format === "png" ? "image" : "file", "ico--sm")), h("span", { title: x.path }, x.name), h("span.muted", {}, x.when))));
  }

  async function refreshThumb(el) {
    const html = await call("report_preview", opts());
    const frame = h("iframe", { title: "ตัวอย่างไฟล์ส่งออก", tabindex: -1, srcdoc: html });
    el.replaceChildren(frame);
  }

  async function preview() {
    const html = await call("report_preview", opts());
    showDialog(h("iframe.preview-full", { title: "ตัวอย่างไฟล์ส่งออก", srcdoc: html }));
  }

  async function doExport(btn, fmt) {
    const res = await busy(btn, () => call("export_report", { ...opts(), format: fmt }));
    if (res.cancelled) return;
    if (!res.ok) { toast(res.error, { error: true, action: "ลองอีกครั้ง", onAction: () => doExport(btn, fmt) }); return; }
    toast(`บันทึก ${res.name} แล้ว`, { action: "เปิดโฟลเดอร์", onAction: () => call("reveal", res.path) });
    st.rep.recent = res.recent;
    const host = root.querySelector(".recent");
    const fresh = recent(st.rep);
    if (host && fresh) host.replaceWith(fresh); else if (fresh) root.querySelector(".export .grow")?.after(fresh);
  }

  await load();
}
