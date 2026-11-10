// เริ่มใช้งานครั้งแรก — nothing recorded yet.
import { call } from "../api.js";
import { h, raw, icon, button, mascot } from "../ui.js";
import { importCsv } from "./importer.js";

export async function render(root, params, ctx) {
  const start = async () => { ctx.settings = await call("save_settings", { first_run_done: true }); location.hash = "#/log"; };
  root.replaceChildren(h("section.welcome.card.sketch.sketch--card.grow.rise", {},
    h("div", { style: { display: "flex", alignItems: "flex-end" } }, mascot("idle", 230), mascot("eraser", 120)),
    h("div", { style: { width: "520px" } },
      h("h1", {}, "ยินดีต้อนรับสู่ตอกบัตร"),
      h("p", { style: { margin: "10px 0 22px" } }, "ยังไม่มีเวลาที่บันทึกไว้ เริ่มกรอกเวลาวันนี้ได้เลย หรือดึงข้อมูลเก่าจาก Google Sheets มาต่อก็ได้"),
      h("div.chips", {},
        button("เริ่มบันทึกวันนี้", { kind: "primary", icon: "plus", onclick: start }),
        button("นำเข้าไฟล์ CSV", { icon: "upload", onclick: async () => { if (await importCsv()) { ctx.settings = await call("save_settings", { first_run_done: true }); location.hash = "#/history"; } } })),
      h("p.hint", { style: { marginTop: "22px", display: "flex", gap: "6px", alignItems: "center" } }, raw(icon("lock", "ico--sm")), "ข้อมูลทั้งหมดเก็บในเครื่องนี้เท่านั้น ไม่ต้องสมัครบัญชี"))));
}
