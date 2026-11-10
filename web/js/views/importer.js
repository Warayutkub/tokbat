// CSV import flow shared by ตั้งค่า and the welcome screen: pick file → preview → import.
import { call } from "../api.js";
import { toast, confirmDialog } from "../ui.js";

export async function importCsv() {
  const pre = await call("import_pick");
  if (pre.cancelled) return false;
  if (!pre.ok) { toast(pre.error, { error: true }); return false; }
  if (!pre.count) { toast("ไม่พบแถวเวลาที่อ่านได้ในไฟล์นี้", { error: true }); return false; }
  const bits = [`${pre.count} ช่วงเวลา (${pre.label})`];
  if (pre.duplicates) bits.push(`ข้ามที่มีอยู่แล้ว ${pre.duplicates}`);
  if (pre.skipped) bits.push(`อ่านไม่ได้ ${pre.skipped} แถว`);
  const ok = await confirmDialog({ title: `นำเข้า ${pre.name}?`, body: `พบ ${bits.join(" · ")}`, confirm: "นำเข้า", icon: "upload" });
  if (!ok) return false;
  const r = await call("import_commit", pre.token);
  if (!r.ok) { toast(r.error, { error: true }); return false; }
  toast(`นำเข้าแล้ว ${r.added} ช่วงเวลา${r.conflicts ? ` · ข้าม ${r.conflicts} ช่วงที่ทับกับของเดิม` : ""}`);
  return true;
}
