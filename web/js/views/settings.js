// ตั้งค่า — report defaults, recording defaults, local data (backup/restore/import), look, delete all.
import { call } from "../api.js";
import { h, raw, icon, button, chip, toast, confirmDialog, mascot, busy, debounce } from "../ui.js";
import { importCsv } from "./importer.js";

export async function render(root, params, ctx) {
  let s = ctx.settings;
  const info = await call("data_info");

  const save = async (patch) => {
    s = ctx.settings = await call("save_settings", patch);
    document.body.classList.toggle("no-chars", !s.show_characters);
    saved.textContent = "บันทึกการตั้งค่าแล้ว ✓";
    clearTimeout(save.t); save.t = setTimeout(() => { saved.textContent = ""; }, 2000);
    paint();
  };
  const saved = h("span.hint", { role: "status" });
  const card = (title, ic, ...kids) => h("section.card.sketch.sketch--card", {}, h("h2", {}, raw(icon(ic)), title), ...kids);
  const setting = (label, help, ...kids) => h("div.setting", {}, h("b", {}, label), help ? h("p.hint", { style: { fontSize: "12px" } }, help) : null, ...kids);
  const sw = (label, help, key) => h("div.setting-row", {}, h("div", {}, h("b", {}, label), help ? h("p.hint", { style: { fontSize: "12px" } }, help) : null),
    h("button.switch.sketch", { type: "button", role: "switch", "aria-checked": s[key] ? "true" : "false", "aria-label": label, onclick: () => save({ [key]: !s[key] }) }));
  const textInput = (value, onchange, attrs = {}) => h("span.input.sketch", {}, h("input", { value: value ?? "", ...attrs, onchange: (e) => onchange(e.target.value) }));

  function paint() {
    const cyc = info.cycle;
    const left = h("div.settings__col", {},
      card("รายงานและการส่งออก", "file",
        setting("ชื่อที่แสดงในรายงาน", "ไม่บังคับ ถ้าเว้นว่างจะไม่แสดงชื่อ เหมือนไฟล์เดิม",
          textInput(s.display_name, (v) => save({ display_name: v.trim() }), { placeholder: "เว้นว่างไว้", "aria-label": "ชื่อที่แสดงในรายงาน" })),
        setting("รอบตัดยอด", `รอบปัจจุบัน ${cyc.label}`,
          h("div.chips", {},
            chip("ตามเดือน (1 – สิ้นเดือน)", s.cycle_mode === "month", () => save({ cycle_mode: "month" })),
            chip("ตัดทุกวันที่", s.cycle_mode === "cutoff", () => save({ cycle_mode: "cutoff" })),
            h("span.input.sketch", { style: { width: "72px" } }, h("input", { type: "number", min: 1, max: 28, value: s.cutoff_day, "aria-label": "วันที่ตัดยอด",
              onchange: (e) => save({ cycle_mode: "cutoff", cutoff_day: Math.max(1, Math.min(28, Number(e.target.value) || 20)) }) })))),
        setting("ชื่อหัวรายงาน", `ใช้ {เดือน} กับ {ปี} ได้ แก้ได้อีกตอนส่งออก · ตอนนี้จะได้ “${cyc.title}”`,
          textInput(s.title_pattern, (v) => save({ title_pattern: v || "{เดือน}/{ปี}" }), { "aria-label": "รูปแบบชื่อหัวรายงาน" })),
        setting("หน่วยชั่วโมง", null, h("div.chips", {},
          chip("ทศนิยม 6.75", s.unit === "decimal", () => save({ unit: "decimal" })), chip("ชม.:นาที 6:45", s.unit === "hm", () => save({ unit: "hm" }))))),
      card("การบันทึกเวลา", "clock",
        setting("เวลาพักเริ่มต้นของช่วงใหม่", null, h("div.chips", {},
          ...[[0, "ไม่พัก"], [30, "30 นาที"], [60, "1 ชม."]].map(([m, l]) => chip(l, s.default_break === m, () => save({ default_break: m }))))),
        sw("เตือนเมื่อมีวันที่ลืมกรอก", "แสดงในแถบสัปดาห์บนหน้าบันทึกเวลา", "remind_missing")),
      saved);
    const right = h("div.settings__col", {},
      card("ข้อมูลในเครื่อง", "database",
        h("div.setting-row", {}, h("span.input.sketch", { style: { flex: 1 } }, raw(icon("folder", "ico--sm")), h("span", { style: { fontSize: "14px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }, title: info.db_path }, info.db_path_short)),
          button("เปิดโฟลเดอร์", { small: true, onclick: () => call("reveal", info.db_path) })),
        h("p.hint", { style: { fontSize: "12px" } }, `${info.count} ช่วงเวลา${info.last_backup ? " · สำรองล่าสุด " + info.last_backup : " · ยังไม่เคยสำรอง"}`),
        h("div.chips", {},
          button("สำรองข้อมูล", { icon: "download", small: true, onclick: (e) => busy(e.currentTarget, backup) }),
          button("กู้คืนจากไฟล์สำรอง", { icon: "upload", small: true, onclick: restore })),
        h("div.import-box", {}, h("div.grow", {}, h("b", { style: { font: "var(--text-title)", fontSize: "14px" } }, "นำเข้าจาก Google Sheets (CSV)"),
          h("p.hint", { style: { fontSize: "12px" } }, "ดึงข้อมูลเก่ามาได้เลย: วันที่ · เวลาเริ่ม · เวลาหยุด · หมายเหตุ")),
          button("เลือกไฟล์ CSV", { icon: "upload", small: true, onclick: async () => { if (await importCsv()) refresh(); } }))),
      card("หน้าตา", "sliders",
        sw("แสดงตัวการ์ตูน", "ชอล์กกับแปรงลบ ในหน้าแอปและมุมไฟล์ส่งออก", "show_characters"),
        h("div.cast", {}, ...["idle", "write", "break", "done", "eraser"].map((p) => mascot(p, 62)))),
      h("section.card.sketch.sketch--card.danger-zone", {},
        h("div.grow", {}, h("b", {}, "ลบข้อมูลทั้งหมด"), h("p.hint", { style: { fontSize: "12px" } }, "ลบทุกช่วงเวลาในเครื่องนี้ แนะนำให้สำรองข้อมูลก่อน")),
        button("ลบทั้งหมด…", { icon: "trash", small: true, onclick: deleteAll })));
    root.replaceChildren(h("div.settings", {}, left, right));
  }

  async function refresh() { Object.assign(info, await call("data_info")); paint(); }

  async function backup() {
    const r = await call("backup");
    if (r.cancelled) return;
    if (!r.ok) return toast(r.error, { error: true });
    toast(`สำรองไว้ที่ ${r.name} แล้ว`, { action: "เปิดโฟลเดอร์", onAction: () => call("reveal", r.path) });
    refresh();
  }

  async function restore() {
    const ok = await confirmDialog({ title: "กู้คืนจากไฟล์สำรอง?", body: "ข้อมูลตอนนี้จะถูกแทนที่ด้วยไฟล์ที่เลือก (ระบบจะเก็บสำเนาของข้อมูลปัจจุบันไว้ให้ก่อน)", confirm: "เลือกไฟล์สำรอง", icon: "upload" });
    if (!ok) return;
    const r = await call("restore");
    if (r.cancelled) return;
    if (!r.ok) return toast(r.error, { error: true });
    toast(`กู้คืนแล้ว · ${r.count} ช่วงเวลา`);
    refresh();
  }

  async function deleteAll() {
    const ok = await confirmDialog({ title: `ลบข้อมูลทั้งหมด ${info.count} ช่วงเวลา?`, body: "ทุกช่วงเวลาในเครื่องนี้จะหายไป และกู้คืนไม่ได้ ถ้ายังไม่ได้สำรอง ให้กด “ยกเลิก” แล้วกด “สำรองข้อมูล” ก่อน", confirm: "ลบทั้งหมด", danger: true });
    if (!ok) return;
    await call("delete_all");
    ctx.settings = await call("save_settings", { first_run_done: false });
    location.hash = "#/welcome";
  }

  paint();
}
