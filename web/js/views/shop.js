// ร้านค้า — items by category, details on the right, price and what's left after buying.
import { call } from "../api.js";
import { h, raw, icon, button, chip, toast } from "../ui.js";
import { manifest, itemSvg, coinSvg, CATS, RARITY, speciesName } from "../garden/art.js";
import { setCoins } from "./garden.js";
import { stamp } from "../garden/packs.js";

export async function render(root, params, ctx) {
  const [m, st0] = await Promise.all([manifest(), call("garden_state")]);
  let st = st0;
  let cat = CATS.some(([k]) => k === params.cat) ? params.cat : "trees";
  let sel = m.byId[params.item] ? params.item : null;
  setCoins(st.balance);
  // the shop has been seen: the "new" dot on the garden's shop button goes away
  call("save_settings", { shop_seen_at: stamp() }).then((s) => { ctx.settings = s; });
  if (!params.item) sel = m.items.find((i) => i.new)?.id ?? sel;
  if (!params.cat && sel) cat = m.byId[sel].cat;

  const owned = () => st.items.reduce((a, r) => ((a[r.item] = (a[r.item] || 0) + 1), a), {});
  const left = h("section.card.sketch.sketch--card");
  const right = h("section.card.sketch.sketch--card.detail");
  root.append(h("div.shop", {}, left, right));

  async function paintLeft() {
    const list = m.items.filter((i) => i.cat === cat);
    if (!sel || m.byId[sel].cat !== cat) sel = list[0]?.id;
    const have = owned();
    const cards = await Promise.all(list.map(async (d) => {
      const art = h("div.product__art");
      art.append(await itemSvg(d.id));
      return h("button.product.sketch", { type: "button", "aria-pressed": d.id === sel ? "true" : "false", onclick: () => { sel = d.id; paintLeft(); paintRight(); } },
        art, h("span.product__name", {}, d.name, d.new ? h("span.badge.badge--accent", {}, "ของใหม่") : have[d.id] ? h("small", {}, `มีแล้ว ${have[d.id]}`) : null),
        h("span.price", {}, raw(coinSvg(16)), String(d.price)));
    }));
    left.replaceChildren(
      h("div.shop__head", {}, h("a.back", { href: "#/garden" }, raw(icon("left", "ico--sm")), "บ้าน"), h("h1", {}, "ร้านค้า")),
      h("div.chips", {}, chip("สัตว์", false, () => { location.hash = "#/adopt"; }, { plain: true }),
        ...CATS.map(([k, label]) => chip(m.items.some((i) => i.cat === k && i.new) ? `${label} •` : label, k === cat, () => { cat = k; sel = null; paintLeft(); paintRight(); }, { plain: true }))),
      h("div.shop__grid", {}, ...cards),
      h("p.hint", { style: { fontSize: "12px" } }, "ทุกชิ้นเป็นของในเกม ได้จากเหรียญที่ทำงานเท่านั้น ไม่มีการใช้เงินจริง"));
  }

  async function paintRight() {
    const d = m.byId[sel];
    if (!d) { right.replaceChildren(); return; }
    const art = h("div.detail__art", {}, h("span.ground"));
    const svg = await itemSvg(d.id);
    svg.classList.add("thing");
    art.append(svg);
    const notes = [
      `หมวด${CATS.find(([k]) => k === d.cat)[1]}`, `ของ${RARITY[d.rarity]}`,
      d.ground ? "อยู่ใต้ทุกอย่าง สัตว์เดินทับได้" : null,
      d.shelter ? "สัตว์มาหลบฝนได้" : null,
      d.bed ? `เป็นที่นอนของ${d.bed.map((s) => speciesName(m, s)).join(" ")}` : null,
      d.light ? "มีไฟตอนกลางคืน" : null,
      d.perch ? "นกมาเกาะได้" : null,
      d.water ? "เป็ดลงว่ายได้ กบชอบมานั่งริมขอบ" : null,
    ].filter(Boolean).join(" · ");
    const after = st.balance - d.price;
    const buy = button(after >= 0 ? `ซื้อ ${d.price} เหรียญ` : `เหรียญไม่พอ (ขาด ${-after})`, { kind: "primary", disabled: after < 0, onclick: () => doBuy(d, buy) });
    right.replaceChildren(art,
      h("h2", {}, d.name, d.new ? h("span.badge.badge--accent", {}, "ของใหม่") : null, owned()[d.id] ? h("span.badge", {}, `มีแล้ว ${owned()[d.id]}`) : null),
      h("p.hint", {}, notes),
      h("div.price-box", {},
        h("div", {}, h("span.muted", {}, "ราคา"), h("span.big", {}, raw(coinSvg(20)), `${d.price} เหรียญ`)),
        h("div", {}, h("span.muted", {}, "มีอยู่"), h("b.num", {}, `${st.balance} เหรียญ`)),
        h("div", {}, h("span.muted", {}, "เหลือหลังซื้อ"), h("b.num", { style: { color: after < 0 ? "var(--color-danger)" : "" } }, `${after} เหรียญ`))),
      buy);
  }

  async function doBuy(d, btn) {
    btn.disabled = true;
    const r = await call("shop_buy", d.id);
    if (!r.ok) { toast(r.error.message, { error: true }); btn.disabled = false; return; }
    st = await call("garden_state");
    setCoins(st.balance, true);
    toast(`ซื้อ${d.name}แล้ว · เหลือ ${st.balance} เหรียญ`, { action: "ไปวาง", onAction: () => { location.hash = "#/garden?decor=1"; } });
    paintLeft();
    paintRight();
  }

  await paintLeft();
  await paintRight();
}
