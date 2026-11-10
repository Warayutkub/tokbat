// App updates (only inside the installed app): check GitHub Releases at most once a day when the setting is on,
// tell the user, and install only when they say so — the app closes for a moment and opens the new version.
import { toast, confirmDialog } from "./ui.js";

const CHECKED = "tokbat.update.checked";
const EVERY = 20 * 3600 * 1000;
export const canUpdate = () => !!window.__TAURI__ && !window.TOKBAT_HTTP;
const invoke = (cmd) => window.__TAURI__.core.invoke(cmd);

/** {available, version, current} | {error} — quiet: no toast when there's nothing new or no connection. */
export async function checkUpdate({ force = false, quiet = true } = {}) {
  if (!canUpdate()) return { error: "dev" };
  if (!force && Date.now() - Number(localStorage.getItem(CHECKED) || 0) < EVERY) return { skipped: true };
  let r;
  try {
    r = await invoke("update_check");
  } catch (e) {
    if (!quiet) toast("เช็กอัปเดตไม่ได้ ต่อเน็ตอยู่ไหม", { error: true });
    return { error: String(e) };
  }
  localStorage.setItem(CHECKED, String(Date.now()));
  if (r.available) {
    toast(`มีตอกบัตรเวอร์ชันใหม่ ${r.version}`, { action: "อัปเดตเลย", onAction: install, timeout: 30000 });
  } else if (!quiet) {
    toast(`ใช้เวอร์ชันล่าสุดอยู่แล้ว (${r.current})`);
  }
  return r;
}

export async function install() {
  const ok = await confirmDialog({
    title: "อัปเดตตอนนี้?",
    body: "แอปจะดาวน์โหลดตัวติดตั้งที่เซ็นรับรองแล้ว ปิดตัวเองสักครู่ แล้วเปิดเวอร์ชันใหม่ให้ ข้อมูลอยู่ครบ และช่วงที่จับเวลาอยู่ก็นับต่อ",
    confirm: "อัปเดต",
    icon: "download",
  });
  if (!ok) return;
  const close = toast("กำลังดาวน์โหลดอัปเดต…", { timeout: 600000 });
  try {
    await invoke("update_install");
  } catch (e) {
    close();
    toast(`อัปเดตไม่สำเร็จ: ${e}`, { error: true });
  }
}
