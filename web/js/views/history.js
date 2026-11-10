// ประวัติ — every session in a range, grouped by day; search notes; edit / delete with undo.
import { call } from "../api.js";
import { h, raw, icon, button, chip, toast, confirmDialog, mascot, debounce, fmtHours } from "../ui.js";

export async function render(root, params, ctx) {
  const st = { kind: params.kind || "this", start: params.start, end: params.end, q: params.q || "", data: null };
  if (!st.start) Object.assign(st, await call("period", "cycle", ctx.today, 0));

  async function setKind(kind) {
    st.kind = kind;
    if (kind !== "custom") Object.assign(st, await call("period", "cycle", ctx.today, kind === "prev" ? -1 : 0));
    load();
  }

  async function load() {
    st.data = await call("history", st.start, st.end, st.q);
    paintList();
    summary.textContent = st.q && !st.data.count ? "0 ช่วง" : `${st.data.count} ช่วง · ${fmtHours(st.data.total_min, ctx.settings.unit)} ชม.`;
  }

  const search = h("input", { type: "search", placeholder: "ค้นหาหมายเหตุ", value: st.q, "aria-label": "ค้นหาหมายเหตุ",
    oninput: debounce((e) => { st.q = e.target.value; load(); }, 250) });
  const summary = h("b", { style: { font: "var(--text-title)", fontSize: "14px" } });
  const rangeInputs = h("span.date-range.sketch", {}, raw(icon("calendar", "ico--sm")),
    h("input", { type: "date", value: st.start, "aria-label": "ตั้งแต่วันที่", onchange: (e) => { st.kind = "custom"; st.start = e.target.value; load(); paintToolbar(); } }), "–",
    h("input", { type: "date", value: st.end, "aria-label": "ถึงวันที่", onchange: (e) => { st.kind = "custom"; st.end = e.target.value; load(); paintToolbar(); } }));
  const chipsHost = h("div.chips");
  function paintToolbar() {
    chipsHost.replaceChildren(
      chip("รอบนี้", st.kind === "this", () => setKind("this"), { plain: true }),
      chip("รอบก่อน", st.kind === "prev", () => setKind("prev"), { plain: true }),
      chip("กำหนดช่วง", st.kind === "custom", () => { st.kind = "custom"; paintToolbar(); rangeInputs.querySelector("input").focus(); }, { plain: true }));
    rangeInputs.querySelectorAll("input")[0].value = st.start;
    rangeInputs.querySelectorAll("input")[1].value = st.end;
  }
  const toolbar = h("div.toolbar", {},
    h("label.input.search.sketch", {}, raw(icon("search")), search),
    chipsHost, rangeInputs,
    h("div.toolbar__sum", {}, summary,
      button("ดูรายงานช่วงนี้", { icon: "chart", onclick: () => { location.hash = `#/report?kind=custom&start=${st.start}&end=${st.end}`; } })));
  const list = h("section.list.card.sketch.sketch--card", { "aria-label": "รายการเวลาทำงาน" });
  root.replaceChildren(toolbar, list);
  paintToolbar();

  function paintList() {
    const g = st.data.groups;
    if (!g.length) {
      list.replaceChildren(h("div.empty", {}, mascot("peek", 130),
        h("p.empty__title", {}, st.q ? `ไม่เจอ “${st.q}” ในช่วง ${st.data.label}` : `ช่วง ${st.data.label} ยังไม่มีเวลาที่บันทึก`),
        h("p.hint", {}, st.q ? "ลองคำอื่น หรือขยายช่วงวันที่ให้กว้างขึ้น" : "กรอกเวลาได้ที่หน้าบันทึกเวลา"),
        h("div.empty__actions", {}, st.q
          ? [button("ล้างการค้นหา", { onclick: () => { st.q = ""; search.value = ""; load(); } }),
             button("ค้นทุกช่วงเวลา", { icon: "search", onclick: async () => { Object.assign(st, await call("all_range")); st.kind = "custom"; paintToolbar(); load(); } })]
          : [button("ไปหน้าบันทึกเวลา", { icon: "clock", onclick: () => { location.hash = "#/log"; } }),
             button("ดูทั้งหมดที่เคยบันทึก", { icon: "list", onclick: async () => { Object.assign(st, await call("all_range")); st.kind = "custom"; paintToolbar(); load(); } })])));
      return;
    }
    list.replaceChildren(h("div.list__head", {}, h("span", {}, "วันที่"),
      h("div.hsess", { style: { padding: "0 6px" } }, h("span", {}, "ช่วงเวลา"), h("span", {}, "ชั่วโมง"), h("span", {}, "หมายเหตุ"), h("span"))));
    g.forEach((day, i) => {
      list.append(h("div.hrow", { style: { animationDelay: `${Math.min(i, 12) * 25}ms` } },
        h("div.hrow__date", {}, h("b", {}, day.label), h("span", {}, `รวม ${fmtHours(day.total_min, ctx.settings.unit)} ชม.${day.sessions.length > 1 ? " · " + day.sessions.length + " ช่วง" : ""}`)),
        h("div", {}, ...day.sessions.map((s) => h("div.hsess", {},
          h("span.hsess__t", {}, `${s.start} – ${s.end ?? "ตอนนี้"}`),
          h("span.hsess__h.num", {}, fmtHours(s.minutes, ctx.settings.unit)),
          h("span.hsess__n", { title: s.note }, s.note || "—"),
          h("span.hsess__a", {},
            h("button.icon-btn.icon-btn--sm.sketch", { type: "button", "aria-label": `แก้ช่วง ${s.start}–${s.end}`, onclick: () => { location.hash = `#/log?date=${s.date}&sid=${s.id}`; } }, raw(icon("edit", "ico--sm"))),
            h("button.icon-btn.icon-btn--sm.icon-btn--danger.sketch", { type: "button", "aria-label": `ลบช่วง ${s.start}–${s.end}`, onclick: () => remove(s, day) }, raw(icon("trash", "ico--sm")))))))));
    });
  }

  async function remove(s, day) {
    const ok = await confirmDialog({ title: `ลบช่วง ${s.start}–${s.end ?? "ตอนนี้"} ของ ${day.slash}?`,
      body: `ชั่วโมงช่วงนี้ (${fmtHours(s.minutes, ctx.settings.unit)}) จะหายไปจากรายงานด้วย`, confirm: "ลบช่วงนี้", danger: true });
    if (!ok) return;
    const res = await call("delete_session", s.id);
    await load();
    toast("ลบช่วงแล้ว", { action: "เลิกทำ", onAction: async () => { await call("restore_session", res.deleted); await load(); toast("เอากลับมาแล้ว"); } });
  }

  await load();
}
