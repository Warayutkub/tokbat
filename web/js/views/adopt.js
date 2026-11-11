// รับมาเลี้ยง — pick an animal, a colour and a name; the preview shows it on its own patch of grass.
import { call } from "../api.js";
import { h, raw, icon, button, toast } from "../ui.js";
import { manifest, petSvg, coinSvg, kinds } from "../garden/art.js";
import { setCoins } from "./garden.js";

const NAMES = ["ส้มจี๊ด", "ข้าวปั้น", "มะลิ", "ถั่วแดง", "โมจิ", "บัวลอย", "ทองหยิบ", "ขนมปัง", "ปุยเมฆ", "ส้มโอ", "ลูกชิ้น", "ปุยฝ้าย", "โกโก้", "มะขาม", "ขนุน", "เต้าหู้", "งาดำ", "ลำไย"];
const MAX = 12;

export async function render(root, params) {
  const [m, st0] = await Promise.all([manifest(), call("garden_state")]);
  let st = st0;
  setCoins(st.balance);
  let species = kinds(m).some((k) => k.id === params.species) ? params.species : "cat";
  let color = null;
  let name = NAMES[Math.floor(Math.random() * NAMES.length)];
  const colorsOf = (sp) => m.pets.filter((p) => p.species === sp);
  const left = h("section.card.sketch.sketch--card");
  const right = h("section.card.sketch.sketch--card.detail.adopt-preview");
  root.append(h("div.shop", { style: { gridTemplateColumns: "1fr 400px" } }, left, right));
  const input = h("input", { value: name, maxlength: MAX, "aria-label": "ชื่อ", oninput: (e) => { name = e.target.value; paintRight(); } });

  async function paintLeft() {
    if (!color || !colorsOf(species).some((c) => c.color === color)) color = colorsOf(species)[0].color;
    const animals = await Promise.all(kinds(m).map(async ({ id: sp, name: label }) => {
      const first = colorsOf(sp)[0];
      const b = h("button.choice.sketch", { type: "button", "aria-pressed": sp === species ? "true" : "false", onclick: () => { species = sp; color = null; paintLeft(); paintRight(); } });
      b.append(await petSvg(sp, first.color), h("b", {}, label), h("span.price", {}, raw(coinSvg(15)), String(st.pet_price)));
      return b;
    }));
    const colors = await Promise.all(colorsOf(species).map(async (p) => {
      const b = h("button.choice.choice--sm.sketch.sketch--soft", { type: "button", "aria-pressed": p.color === color ? "true" : "false", onclick: () => { color = p.color; paintLeft(); paintRight(); } });
      b.append(await petSvg(p.species, p.color), h("b", {}, p.colorName));
      return b;
    }));
    left.replaceChildren(
      h("div.shop__head", {}, h("a.back", { href: "#/shop" }, raw(icon("left", "ico--sm")), "ร้านค้า"), h("h1", {}, "รับมาเลี้ยง")),
      h("p.step-title", {}, "1 · เลือกสัตว์"), h("div.choices.choices--kinds", {}, ...animals),
      h("p.step-title", {}, "2 · เลือกสี"), h("div.choices", {}, ...colors),
      h("p.step-title", {}, "3 · ตั้งชื่อ"),
      h("div.name-row", {}, h("label.field", { style: { width: "320px" } }, h("span.field__label", {}, "ชื่อ"), h("span.input.sketch", {}, input)),
        button("สุ่มชื่อ", { small: true, onclick: () => { name = NAMES[Math.floor(Math.random() * NAMES.length)]; input.value = name; paintRight(); } })),
      h("p.hint", { style: { fontSize: "12px" } }, `เปลี่ยนชื่อทีหลังได้ · ไม่เกิน ${MAX} ตัวอักษร`));
  }

  async function paintRight() {
    const p = m.pets.find((x) => x.species === species && x.color === color);
    const art = h("div.detail__art", { style: { height: "280px" } }, h("span.ground"));
    const svg = await petSvg(species, color);
    svg.classList.add("thing");
    svg.style.height = "220px";
    art.append(h("span.tagline", {}, name.trim() || "…", raw('<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 20C5 15 3 11.5 3 8.6 3 6 5 4 7.4 4c2 0 3.6 1.3 4.6 3 1-1.7 2.6-3 4.6-3C19 4 21 6 21 8.6c0 2.9-2 6.4-9 11.4z" fill="#FFA8B8" stroke="#22304A" stroke-width="1.6"/></svg>')), svg);
    const after = st.balance - st.pet_price;
    const ok = name.trim().length > 0 && [...name.trim()].length <= MAX;
    const btn = button(after >= 0 ? `รับมาเลี้ยง · ${st.pet_price} เหรียญ` : `เหรียญไม่พอ (ขาด ${-after})`,
      { kind: "primary", disabled: after < 0 || !ok, onclick: () => adopt(btn) });
    right.replaceChildren(art,
      h("h2", {}, `${name.trim() || "ยังไม่มีชื่อ"} · ${p.speciesName}${p.colorName}`),
      h("p.hint", {}, "เดินเล่นในลาน หลบฝน และเข้าบ้านไปนอนตอนกลางคืน"),
      h("div.price-box", {},
        h("div", {}, h("span.muted", {}, "ราคา"), h("span.big", {}, raw(coinSvg(20)), `${st.pet_price} เหรียญ`)),
        h("div", {}, h("span.muted", {}, "เหลือหลังรับ"), h("b.num", { style: { color: after < 0 ? "var(--color-danger)" : "" } }, `${after} เหรียญ`))),
      btn);
  }

  async function adopt(btn) {
    btn.disabled = true;
    const r = await call("pet_adopt", { species, color, name: name.trim() });
    if (!r.ok) { toast(r.error.message, { error: true }); btn.disabled = false; return; }
    st = await call("garden_state");
    setCoins(st.balance, true);
    toast(`ยินดีต้อนรับ${r.pet.name}เข้าบ้าน!`);
    location.hash = "#/garden";
  }

  await paintLeft();
  await paintRight();
}
