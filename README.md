# ตอกบัตร

แอปบันทึกเวลาทำงานบนเครื่อง (Windows) — Rust + Tauri 2 + SQLite, หน้าจอ HTML/CSS ใน Edge WebView2
ไม่ต้องใช้อินเทอร์เน็ต ไม่มีบัญชี ข้อมูลอยู่ในเครื่องเท่านั้น

ดีไซน์: Figma ไฟล์ `work-time` › section `ตอกบัตร · Prototype · Approved` และ `ตอกบัตร · Foundations · Approved`

## ทำอะไรได้
- กรอกเวลาเข้า–ออก หลายช่วงต่อวัน ลากหัว–ท้ายแท่งบนไทม์ไลน์ 24 ชม. หรือพิมพ์เวลาเอง
- ข้ามเที่ยงคืนได้ (เช่น 21:00 → 03:00) — ชั่วโมงนับเป็นของวันที่เริ่มงาน
- เวลาพักหักออกอัตโนมัติ · ช่องหมายเหตุ (ทำอะไรไปบ้าง)
- กรอกย้อนหลังได้ทุกวัน · เตือนวันที่ลืมกรอก
- เริ่มงานตอนนี้ / เลิกงานตอนนี้
- ประวัติ: ค้นหมายเหตุ แก้ ลบ (มีเลิกทำ)
- รายงาน: รอบตัดยอด (ตามเดือน หรือตัดทุกวันที่ N) ชั่วโมงรวมคิดจากนาทีจริง
- ส่งออก A4 เป็น **PDF** หรือ **PNG** แบบเดียวกับชีตเดิม (วันที่ · เวลาเริ่ม · เวลาหยุด · ชั่วโมงทศนิยม · หมายเหตุ)
- สำรอง / กู้คืนไฟล์ข้อมูล · นำเข้า CSV จาก Google Sheets

ข้อมูลอยู่ที่ `Documents\ตอกบัตร\worktime.db` (ตั้ง `TOKBAT_DATA_DIR` เพื่อย้ายที่ได้) — ไฟล์เดียวกับเวอร์ชัน Python เดิม ใช้ต่อได้เลย
ถอนการติดตั้งแอปไม่ลบโฟลเดอร์นี้

## ติดตั้ง
```
npm install
npm run build
```
ได้ตัวติดตั้งไฟล์เดียวที่ `src-tauri/target/release/bundle/nsis/` (ติดตั้งให้ผู้ใช้คนเดียว ไม่ต้องสิทธิ์แอดมิน)

## พัฒนา
ต้องมี Rust (stable) + Node.js
- `npm run serve` — เปิดหน้าจอในเบราว์เซอร์ธรรมดาที่ http://127.0.0.1:5177 ข้อมูลไปที่ `.dev-data/` (ไม่แตะข้อมูลจริง)
  ปุ่มบันทึกไฟล์จะเซฟลง `.dev-data/exports/` · นำเข้า CSV ใช้ `fixtures/sample-sheet.csv` (หรือ `TOKBAT_DEV_OPEN`)
- `npm run dev` — เปิดหน้าต่างแอปจริงแบบ dev
- `npm test` — เทสต์ทั้งหมด (รวมส่งออก PDF/PNG จริงผ่าน Edge) ชุดเดียวกับเวอร์ชัน Python
- `tokbat.exe --selftest <โฟลเดอร์>` — เปิดหน้าต่างแบบซ่อนบนข้อมูลชั่วคราว ตรวจหน้าจอ ส่งออก PDF+PNG แล้วเขียน `results.json`
- `web/dev-mascots.html` (ผ่าน `npm run serve`) — ดูการขยับของตัวละคร ติ๊ก debug เพื่อดูสีแยกชิ้น

### ตัวละคร
`web/img/chars/character-*.svg` ส่งออกจาก Figma (ลายแปรง GRINDHOUSE) → `python tools/split_mascots.py`
แยกเป็นชิ้น (`p-fig › p-face › p-eye-l › p-pupil` ฯลฯ) ลง `web/img/chars/anim/` แล้ว `web/css/mascots.css` ทำให้ขยับ
(กะพริบตา กลอกตา หายใจ โบกมือ zz ไอน้ำ กระดาษสี) — ถ้าวาดตัวละครใหม่ใน Figma ต้องแก้ `SPEC` ในสคริปต์ให้ตรงลำดับเลเยอร์

### Design tokens
`web/css/tokens.css` เขียนตาม Foundations ใน Figma (wridge `get_tokens` อ่านได้เฉพาะ *หน้า* ชื่อ Foundations)

## โครง
```
web/                    หน้าจอ (ES modules ไม่มี build step) — js/api.js เรียก Rust ผ่าน invoke("api")
src-tauri/
  src/main.rs           เปิดแอป · --selftest · --serve
  src/lib.rs            หน้าต่าง Tauri · ตัวเลือกไฟล์ · คำสั่ง api · self-test
  src/api.rs            เมธอดที่หน้าจอเรียก (คืน JSON) ชื่อ/รูปแบบเดียวกับ Python เดิม
  src/repo.rs           อ่าน/เขียน SQLite · ตรวจเวลาทับกัน
  src/db.rs             schema + migration (PRAGMA user_version)
  src/timecalc.rs       คณิตเวลา: ข้ามวัน, ทศนิยม half-up, ทับกัน
  src/thaidate.rs       วันที่ไทย พ.ศ. · รอบตัดยอด
  src/report.rs         ตัวเลขรายงาน + หน้า A4 (templates/report.html, minijinja)
  src/exporter.rs       HTML → PDF / PNG ด้วย Edge headless (PNG วัดความสูงหน้าก่อน แล้วถ่ายที่ 2x)
  src/csv_io.rs         อ่าน CSV จาก Google Sheets (UTF-8/UTF-16/TIS-620)
  src/serve.rs          เซิร์ฟเวอร์สำหรับพัฒนา
  tests/                เทสต์ (ชุดเดียวกับ legacy-python/tests)
fixtures/               ชีตตัวอย่าง รูปแบบเดียวกับชีตที่ใช้อยู่ (ข้อมูลสมมติ ใช้ในเทสต์)
legacy-python/          เวอร์ชัน Python เดิม (pywebview) เก็บไว้อ้างอิง
tools/                  สคริปต์แยกชิ้นตัวละคร · ทำไอคอน
```

- เครื่องที่จะใช้ต้องมี Microsoft Edge (+ WebView2 Runtime) ซึ่ง Windows 10/11 มีอยู่แล้ว
- ถ้าแอปเปิดไม่ขึ้น ดู `Documents\ตอกบัตร\error.log`
