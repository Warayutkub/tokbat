# ตอกบัตร

แอปบันทึกเวลาทำงานบนเครื่อง (Windows) — Rust + Tauri 2 + SQLite, หน้าจอ HTML/CSS ใน Edge WebView2
ไม่ต้องใช้อินเทอร์เน็ต ไม่มีบัญชี ข้อมูลอยู่ในเครื่องเท่านั้น

**หน้าเว็บ + ดาวน์โหลด:** https://warayutkub.github.io/tokbat/

ดีไซน์: Figma ไฟล์ `work-time` › section `ตอกบัตร · Prototype · Approved`, `ตอกบัตร · Foundations · Approved`
และหน้าเว็บ `ตอกบัตร หน้าเว็บแนะนำ · Prototype · Approved`

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
- **สวนสัตว์เลี้ยง** (แท็บ "บ้าน", ตั้งแต่ 0.3.0): ทำงานได้เหรียญ ชั่วโมงละ 2 วันละไม่เกิน 16 · เควสต์รายวัน/สัปดาห์/พิเศษ · บัตรสะสม 10 ช่อง → กล่องของขวัญ (บอกโอกาส ไม่ได้ของซ้ำ) ·
  ร้านค้า ของแต่ง 45 ชิ้น สัตว์ 6 ชนิด × 4 สี (เดิน กระโดด บิน เตาะแตะ+ว่ายน้ำ) · ลากวางในลาน · กลางวัน/กลางคืนตามนาฬิกา ฝนตกชั่วโมงละ 15 นาที (ไม่ใช้เน็ต) — ปิดได้ในตั้งค่า ไม่ไปอยู่ในรายงาน

ข้อมูลอยู่ที่ `Documents\ตอกบัตร\worktime.db` (ตั้ง `TOKBAT_DATA_DIR` เพื่อย้ายที่ได้) — ไฟล์เดียวกับเวอร์ชัน Python เดิม ใช้ต่อได้เลย
ถอนการติดตั้งแอปไม่ลบโฟลเดอร์นี้

## ติดตั้ง
ดาวน์โหลด `tokbat_x64-setup.exe` จาก [Releases](https://github.com/Warayutkub/tokbat/releases/latest) (ติดตั้งให้ผู้ใช้คนเดียว ไม่ต้องสิทธิ์แอดมิน)

สร้างเอง:
```
npm install
npm run build
```
ได้ตัวติดตั้งที่ `src-tauri/target/release/bundle/nsis/`

### ออกเวอร์ชันใหม่
แก้ `version` ใน `src-tauri/tauri.conf.json` และ `src-tauri/Cargo.toml` → เขียนบันทึกรุ่นที่ `.github/release-notes/v0.3.1.md` → commit → push tag เช่น `git tag v0.3.1 && git push origin v0.3.1`
GitHub Actions (`.github/workflows/release.yml`) จะรันเทสต์ สร้างตัวติดตั้ง แล้วแนบใน release ชื่อ `tokbat_x64-setup.exe` (ชื่อคงที่ ปุ่มดาวน์โหลดบนหน้าเว็บจึงลิงก์ตรงได้)

### อัปเดตแอปอัตโนมัติ (ตั้งแต่ 0.3.0)
- แอปเช็ก `releases/latest/download/latest.json` วันละครั้ง (ตั้งค่า › เวอร์ชันแอป) ถ้ามีเวอร์ชันใหม่จะถามก่อน แล้วติดตั้งแบบเห็นแถบความคืบหน้าและเปิดตัวใหม่ให้
- ตัวติดตั้งต้องเซ็นด้วยกุญแจอัปเดต: กุญแจลับอยู่ที่ `%USERPROFILE%\.tokbat\updater.key` (สร้างด้วย `npx tauri signer generate`) กุญแจสาธารณะอยู่ใน `tauri.conf.json › plugins.updater.pubkey`
- ก่อน push tag ต้องมี repo secret **`TAURI_SIGNING_PRIVATE_KEY`** (เนื้อไฟล์ updater.key) และ **`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`** (ว่างได้) — ไม่มีแล้ว workflow จะหยุดตั้งแต่ขั้นแรก
- CI build ด้วย `--config src-tauri/tauri.release.conf.json` (เปิด `createUpdaterArtifacts`) แล้วสร้าง `latest.json` แนบใน release; `npm run build` ในเครื่องไม่ต้องใช้กุญแจ
- สำรองกุญแจทั้งสอง (updater.key และ pack-signing.key) ไว้ที่ปลอดภัย ถ้าหาย เครื่องที่ติดตั้งไปแล้วจะอัปเดตเองไม่ได้ ต้องดาวน์โหลดตัวติดตั้งใหม่เอง

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

### สวนสัตว์เลี้ยง
- กติกาทั้งหมดอยู่ฝั่ง Rust (`src-tauri/src/game.rs`): ค่าแรงคิดใหม่จากช่วงเวลาทุกครั้ง (ไม่เก็บ) + สมุดเหรียญ `coin_ledger`
  ได้เหรียญเฉพาะ `sessions.source` = `timer` หรือ `manual` ที่กรอกภายใน 7 วัน ตั้งแต่วันที่เริ่มเกม (`import` และ `legacy` = 0) — เทสต์ใน `tests/game.rs`
- ภาพอยู่ใน `web/garden/base/` (ส่งออกจาก Figma section `ของตกแต่ง (props) · คอลเลกชัน · Approved` และ `ลานหญ้า + สัตว์เลี้ยง · Direction · Approved`
  พร้อมลายแปรง) · `manifest.json` คือแคตตาล็อก (ราคา ความหายาก ที่นอน ที่หลบฝน) ที่ทั้งหน้าจอและ Rust อ่าน
- ชิ้นส่วนสัตว์เป็น class ตามชื่อเลเยอร์ใน Figma (`leg-*`, `tail`, `head`, `eye-l` …) → `web/css/garden.css` ทำให้เดิน กระดิกหาง กะพริบตา
- หน้าจอ: `web/js/views/{garden,shop,adopt}.js`, `web/js/garden/{stage,decorate,weather,art}.js`
- ดูอากาศแต่ละแบบ: `http://127.0.0.1:5177/#/garden?sky=day|night|rain|night-rain`
- เครื่องมือวาด: `tools/garden/` — `draw.py`/`props.py`/`scene.py` สร้างภาพลายเส้น (SVG) ไปลง Figma, `export.py` ส่งออกจาก Figma (พร้อมแปรง) แล้วย่อไฟล์ด้วย `slim.py`

### แพ็กของใหม่ (เพิ่มของแต่ง/สีสัตว์โดยไม่ต้องออกแอปรุ่นใหม่)
1. วาดและผ่านขั้นอนุมัติใน Figma ก่อน แล้วส่งออก: `python tools/garden/export.py --within <section id> --prefix "Prop/" --out <โฟลเดอร์>/props`
   สัตว์สีใหม่: `--node <id ใน Figma>=cat-<สี> --out <โฟลเดอร์>/pets` (ลายปื้นของแมววาดด้วย `coat()` ใน `tools/garden/draw.py`)
2. เขียน `<โฟลเดอร์>/pack.src.json` (ตัวอย่างอยู่หัวไฟล์ `tools/make_pack.py`) — รหัสต้องไม่ซ้ำของเดิม
   สัตว์ชนิดใหม่ใส่ใน `"species"` ของแพ็กได้ ถ้าใช้ท่าที่แอปรู้จัก (`walk` `hop` `fly` `waddle`) ส่วนของแต่งใส่ `"perch"` (จุดที่นกเกาะ) และ `"water"` (พื้นที่น้ำ) ได้ — ดู `species` ใน `web/garden/base/manifest.json`
   ต้นฉบับของแต่ละแพ็กเก็บไว้ที่ `tools/packs/<id>/` (เช่น `tools/packs/cats-1/` แมวสามสี สลิดขาว สลิด วัว)
3. `python tools/make_pack.py <โฟลเดอร์>` → ได้ `docs/packs/<id>/` (pack.json + pack.sig + ภาพ) และรายการใน `docs/packs/index.json`
4. commit + push → หน้าเว็บอัปเดต → แอปเช็กวันละครั้งตอนต่อเน็ต (ถ้าเปิด "ของใหม่อัตโนมัติ") หรือกด "เช็กของใหม่ตอนนี้" ในตั้งค่า
- แอปเก็บแพ็กไว้ที่ `packs\` ข้างไฟล์ข้อมูล และติดตั้งเฉพาะแพ็กที่ลายเซ็น ed25519 ตรง hash ของทุกไฟล์ตรง และภาพไม่มีสคริปต์หรือลิงก์ออกนอก (`src-tauri/src/packs.rs`, เทสต์ `tests/packs.rs`)
- **กุญแจลับสำหรับเซ็นแพ็ก** อยู่ที่ `%USERPROFILE%\.tokbat\pack-signing.key` (สร้างด้วย `python tools/pack_key.py`) — สำรองไว้ที่ปลอดภัย ห้าม commit
  ถ้ากุญแจหาย ต้องสร้างใหม่และออกแอปรุ่นใหม่ที่มี `PACK_PUBKEY` ใหม่ใน `src-tauri/src/packs.rs`
- ทดสอบในเครื่อง: build แพ็กลง `web/packs-test` แล้วตั้ง `localStorage["tokbat.packs.index"] = "/packs-test/index.json"` ในหน้า `npm run serve` (ลบทั้งสองอย่างเมื่อเสร็จ)

### หน้าเว็บ (GitHub Pages จากโฟลเดอร์ `docs/`)
- ขึ้นเว็บอัตโนมัติด้วย `.github/workflows/pages.yml` ทุกครั้งที่ push การแก้ใน `docs/` ไป main (ตั้งค่า repo: Pages → Source = GitHub Actions)
- `docs/index.html`, `docs/css/site.css`, `docs/js/site.js` เขียนเอง ไม่มี build step
- `python tools/build_site.py` คัดของจากแอปมาให้: สี (`tokens.css`), การขยับของตัวละคร (`mascots.css` + SVG), ฟอนต์เป็น WOFF2,
  ภาพหน้าจอเป็น WebP จาก `build-assets/site/*.png` — ภาพพวกนี้ถ่ายจากข้อมูลสมมติ (`--serve 5178 --data .demo-data`) ห้ามใช้ข้อมูลจริง
- ดูในเครื่อง: `python -m http.server 5180 --directory docs`

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
  src/game.rs           สวนสัตว์เลี้ยง: เหรียญ เควสต์ บัตรสะสม กล่องของขวัญ ร้านค้า สัตว์ การจัดลาน
  src/packs.rs          แพ็กของใหม่: ตรวจลายเซ็น/hash/ภาพ ติดตั้ง รวมแคตตาล็อก
  src/timecalc.rs       คณิตเวลา: ข้ามวัน, ทศนิยม half-up, ทับกัน
  src/thaidate.rs       วันที่ไทย พ.ศ. · รอบตัดยอด
  src/report.rs         ตัวเลขรายงาน + หน้า A4 (templates/report.html, minijinja)
  src/exporter.rs       HTML → PDF / PNG ด้วย Edge headless (PNG วัดความสูงหน้าก่อน แล้วถ่ายที่ 2x)
  src/csv_io.rs         อ่าน CSV จาก Google Sheets (UTF-8/UTF-16/TIS-620)
  src/serve.rs          เซิร์ฟเวอร์สำหรับพัฒนา
  tests/                เทสต์ (ชุดเดียวกับ legacy-python/tests)
fixtures/               ชีตตัวอย่าง รูปแบบเดียวกับชีตที่ใช้อยู่ (ข้อมูลสมมติ ใช้ในเทสต์)
legacy-python/          เวอร์ชัน Python เดิม (pywebview) เก็บไว้อ้างอิง
docs/                   หน้าเว็บแนะนำ (GitHub Pages)
tools/                  สคริปต์แยกชิ้นตัวละคร · ทำไอคอน · เตรียมไฟล์หน้าเว็บ · ทำ/เซ็นแพ็ก (make_pack, pack_key)
  garden/               วาดและส่งออกภาพในสวน
```

- เครื่องที่จะใช้ต้องมี Microsoft Edge (+ WebView2 Runtime) ซึ่ง Windows 10/11 มีอยู่แล้ว
- ถ้าแอปเปิดไม่ขึ้น ดู `Documents\ตอกบัตร\error.log`

## License
โค้ดใช้ [MIT](LICENSE) · ตัวการ์ตูน ไอคอน และชื่อ "ตอกบัตร" สงวนสิทธิ์ ([NOTICE.md](NOTICE.md)) · ฟอนต์ IBM Plex Sans Thai Looped ใช้ OFL 1.1
