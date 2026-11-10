// บ้าน — the garden: pets living in it, a slim HUD (today's work, quests, punch card), rewards and decorating.
import { call } from "../api.js";
import { h, raw, icon, button, toast, showDialog, mascot, hm, fmtHours } from "../ui.js";
import { manifest, coinSvg, pawSvg, RARITY, itemSvg, petSvg, SPECIES } from "../garden/art.js";
import { Stage, ZOOMS } from "../garden/stage.js";
import { skyAt } from "../garden/weather.js";
import { startDecorate } from "../garden/decorate.js";

export const setCoins = (n, bump = false) => window.dispatchEvent(new CustomEvent("garden:coins", { detail: { n, bump } }));

const ICON_BRUSH = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4l6 6-9 9-6-6z"/><path d="M5 13l-2 8 8-2"/></svg>';
const ICON_BAG = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8h14l-1 12H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>';
const ICON_CHECK = (fill = "#FFE07A", mark = "#22304A", ring = "#22304A") =>
  `<svg class="quest__icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="${fill}" stroke="${ring}" stroke-width="1.6"/><path d="M7.5 12.3l3 3 6-6.4" stroke="${mark}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const ICON_TODO = '<svg class="quest__icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff" stroke="#9AA8BD" stroke-width="1.6" stroke-dasharray="3 2.4"/></svg>';

export async function render(root, params, ctx) {
  root.classList.add("garden-view");
  const [m, first] = await Promise.all([manifest(), call("garden_state")]);
  let st = first;
  const unit = () => ctx.settings.unit || "decimal";
  setCoins(st.balance);
  if (!st.enabled) {
    root.append(h("section.card.sketch.sketch--card.empty", {}, mascot("idle", 110),
      h("h2.empty__title", {}, "สวนสัตว์เลี้ยงปิดอยู่"), h("p.hint", {}, "เปิดได้ในหน้าตั้งค่า เหรียญ สัตว์ และของแต่งยังเก็บไว้ครบ"),
      h("div.empty__actions", {}, button("ไปหน้าตั้งค่า", { kind: "primary", onclick: () => { location.hash = "#/settings"; } }))));
    return;
  }

  const card = h("div.g-card.sketch.sketch--card");
  root.append(card);
  const stage = new Stage(card, m);
  const hud = h("div.g-hud");
  card.append(hud);
  let panel = null, welcome = null, decor = null;

  // #/garden?sky=day|night|rain|night-rain pins the weather (for screenshots and checking each look)
  const pinned = ["day", "night", "rain", "night-rain"].includes(params.sky) ? { mode: params.sky, night: params.sky.startsWith("night"), rain: params.sky.endsWith("rain") } : null;
  async function sky() { await stage.setSky(pinned || skyAt(new Date(), st.rain)); }
  if (pinned) window.__garden = stage; // with ?sky=… the stage is reachable from the console, to step the pets by hand
  await Promise.all([sky(), stage.setItems(st.items), stage.setPets(st.pets)]);
  stage.onPet = (actor) => petDialog(actor);

  // ---------------------------------------------------------------- HUD
  function workPill() {
    const o = st.open_session;
    const pill = h("div.pill.sketch", { "aria-label": "งานวันนี้" });
    if (o) {
      const started = new Date(`${o.date}T${o.start}:00`);
      const mins = Math.max(0, Math.floor((Date.now() - started.getTime()) / 60000) - (o.break_min || 0));
      pill.append(h("span.dot"), h("span.work-state", {}, "กำลังทำงาน"), h("span.big.num", {}, hm(mins)));
    } else {
      pill.append(h("span.work-state", { style: { color: "var(--color-muted)" } }, st.today_minutes ? "พักอยู่" : "วันนี้ยังไม่เริ่มงาน"));
    }
    if (st.today_minutes) pill.append(h("span.sep", {}, "·"), h("span.muted", {}, `วันนี้ ${fmtHours(st.today_minutes, unit())} ชม.`));
    pill.append(h("span.sep", {}, "·"), h("span.price", { title: `ได้ชั่วโมงละ ${st.wage.rate} เหรียญ วันละไม่เกิน ${st.wage.cap}` }, raw(coinSvg(16)), h("span.num", {}, `${st.wage.today}/${st.wage.cap}`)));
    pill.append(h("button.mini-btn", { type: "button", onclick: o ? stop : start }, o ? "หยุดงาน" : "เริ่มงาน"));
    return pill;
  }

  function paintHud() {
    const q = st.quests;
    const qBtn = h("button.pill.pill--btn.sketch" + (panel ? ".is-on" : ""), { type: "button", "aria-expanded": panel ? "true" : "false", onclick: toggleQuests },
      raw(ICON_CHECK()), "เควสต์", q.ready ? h("span.count", {}, String(q.ready)) : null);
    const pBtn = h("button.pill.pill--btn.sketch", { type: "button", onclick: st.punch.boxes ? openGift : toggleQuests, title: "บัตรสะสม" },
      raw(pawSvg(20, true)), st.punch.boxes ? "เปิดกล่องของขวัญ" : h("span.num", {}, `${st.punch.count}/10`));
    if (st.punch.boxes) pBtn.classList.add("is-on");
    hud.replaceChildren(
      h("div.g-hud__top", {}, workPill(), h("div", { style: { display: "flex", gap: "8px" } }, qBtn, pBtn)),
      h("div.g-hud__bottom", {}, zoomControl(),
        h("div", { style: { display: "flex", gap: "10px" } },
          h("button.pill.pill--btn.sketch", { type: "button", onclick: decorate }, raw(ICON_BRUSH), "ตกแต่ง"),
          h("button.pill.pill--btn.sketch.is-on", { type: "button", onclick: () => { location.hash = "#/shop"; } }, raw(ICON_BAG), "ร้านค้า",
          hasNew() ? h("span.count", { title: "มีของใหม่" }, "ใหม่") : null))));
    if (panel) paintPanel();
    welcome?.remove();
    welcome = null;
    if (!st.pets.length && !decor) {
      welcome = h("div.g-welcome.sketch.sketch--card", {}, mascot("idle", 110),
        h("h2", {}, "ลานนี้ยังว่างอยู่"),
        h("p", {}, `ทำงานได้เหรียญชั่วโมงละ ${st.wage.rate} เหรียญ เอาไปรับสัตว์มาเลี้ยง หรือซื้อของมาแต่งลานได้`),
        h("span.gift-line", {}, raw(coinSvg(22)), `ตอนนี้มี ${st.balance} เหรียญ`),
        button("รับสัตว์ตัวแรก", { kind: "primary", onclick: () => { location.hash = "#/adopt"; } }),
        h("p.hint", { style: { fontSize: "12px" } }, "ปิดเกมได้ในตั้งค่า · สัตว์และของแต่งไม่ไปอยู่ในรายงาน"));
      card.append(welcome);
    }
  }

  function hasNew() {
    const seen = ctx.settings.shop_seen_at || "";
    return m.items.some((i) => i.new && i.installed_at > seen);
  }

  function zoomControl() {
    const i = ZOOMS.indexOf(stage.zoom);
    const step = (d) => { stage.setZoom(ZOOMS[Math.max(0, Math.min(ZOOMS.length - 1, i + d))]); paintHud(); };
    return h("div.zoom.sketch", { role: "group", "aria-label": "ขนาดลาน" },
      h("button", { type: "button", "aria-label": "ย่อ", title: "ย่อ", disabled: i <= 0, onclick: () => step(-1) }, "−"),
      h("button", { type: "button", "aria-label": "ขยาย", title: "ขยาย", disabled: i >= ZOOMS.length - 1, onclick: () => step(1) }, "+"));
  }

  async function refresh() {
    st = await call("garden_state");
    setCoins(st.balance);
    if (!decor) paintHud();
  }

  async function start() {
    const r = await call("start_now");
    if (!r.ok) return toast(r.error?.message || "เริ่มงานไม่ได้", { error: true });
    toast(`เริ่มงานแล้ว ${r.session.start} · ได้เหรียญชั่วโมงละ ${st.wage.rate}`);
    refresh();
  }
  async function stop() {
    const r = await call("stop_now", st.open_session.id);
    if (!r.ok) return toast(r.error?.message || "หยุดงานไม่ได้", { error: true, action: "ไปหน้าบันทึกเวลา", onAction: () => { location.hash = "#/log"; } });
    toast(`บันทึกช่วง ${r.session.start}–${r.session.end} แล้ว · ${fmtHours(r.session.minutes, unit())} ชม.`);
    refresh();
  }

  // ---------------------------------------------------------------- a pet up close: who it is, rename it
  async function petDialog(actor) {
    const p = actor.row;
    const look = m.pets.find((x) => x.species === p.species && x.color === p.color);
    const since = new Date(p.adopted_at.replace(" ", "T"));
    const days = Math.max(0, Math.floor((Date.now() - since.getTime()) / 86400000));
    const art = h("div.pet-card__art");
    art.append(await petSvg(p.species, p.color));
    const input = h("input", { value: p.name, maxlength: 12, "aria-label": "ชื่อ" });
    const err = h("p.field__help.field__help--error", { role: "alert" });
    const save = async () => {
      const r = await call("pet_rename", p.id, input.value);
      if (!r.ok) { err.textContent = r.error.message; return; }
      p.name = r.pet.name;
      actor.tag.querySelector("b").textContent = p.name;
      actor.el.title = p.name;
      const row = st.pets.find((x) => x.id === p.id);
      if (row) row.name = p.name;
      close();
      toast(`ตั้งชื่อใหม่เป็น ${p.name} แล้ว`);
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); });
    const close = showDialog(h("div.dialog__panel.sketch.sketch--card.pet-card", { role: "document" }, art,
      h("h2.dialog__title", {}, p.name),
      h("p.hint", { style: { fontSize: "14px" } }, `${SPECIES[p.species]}สี${look?.colorName || ""} · ${days ? `อยู่ด้วยกันมา ${days} วัน` : "เพิ่งมาอยู่ด้วยวันนี้"}`),
      h("label.field", {}, h("span.field__label", {}, "เปลี่ยนชื่อ"), h("span.input.sketch", {}, input), err),
      h("div.dialog__actions", {}, button("ปิด", { onclick: () => close() }), button("บันทึกชื่อ", { kind: "primary", onclick: save }))));
    input.select();
  }

  // ---------------------------------------------------------------- quests
  function questRow(x) {
    const state = x.claimed ? "claimed" : x.done ? "ready" : "doing";
    const p = x.progress;
    const sub = state === "doing" && p.goal > 1
      ? h("span.quest__sub", {}, h("span.bar", {}, h("i", { style: { width: `${Math.round((p.value / p.goal) * 100)}%` } })),
        p.unit === "min" ? `${fmtHours(p.value, unit())}/${p.goal / 60} ชม.` : `${p.value}/${p.goal}${p.unit === "day" ? " วัน" : ""}`)
      : h("span.quest__sub", {}, `+${x.reward} เหรียญ`);
    const right = state === "ready"
      ? h("button.chip.sketch", { type: "button", "aria-pressed": "true", onclick: (e) => claim(x, e.currentTarget) }, `รับ +${x.reward}`)
      : state === "claimed" ? h("span.hint", { style: { fontSize: "12px" } }, "รับแล้ว")
        : h("span.quest__reward", {}, raw(coinSvg(16)), `+${x.reward}`);
    return h(`div.quest${state === "claimed" ? ".is-claimed" : ""}`, {},
      raw(state === "ready" ? ICON_CHECK() : state === "claimed" ? ICON_CHECK("#E3E9F2", "#66758F", "#9AA8BD") : ICON_TODO),
      h("div.quest__text", {}, h("span.quest__title", {}, x.title), sub), right);
  }

  function slots(count, fresh = -1) {
    return h("div.slots", { "aria-label": `บัตรสะสม ${count} จาก 10 ช่อง` },
      ...Array.from({ length: 10 }, (_, i) => h(`span${i === fresh ? ".is-new" : ""}`, { html: pawSvg(28, i < count) })));
  }

  function paintPanel() {
    const q = st.quests;
    panel.replaceChildren(
      h("div.g-panel__head", {}, h("h2", {}, "เควสต์วันนี้"),
        h("div", { style: { display: "flex", gap: "10px", alignItems: "center" } }, h("span.badge", {}, "รีเซ็ตเที่ยงคืน"),
          h("button.icon-btn.icon-btn--sm", { type: "button", "aria-label": "ปิด", onclick: toggleQuests }, raw(icon("x", "ico--sm"))))),
      ...q.daily.map(questRow),
      h("p.quest-group", {}, "สัปดาห์นี้"), ...q.weekly.map(questRow),
      ...(q.special.some((x) => !x.claimed) ? [h("p.quest-group", {}, "พิเศษ"), ...q.special.filter((x) => !x.claimed).map(questRow)] : []),
      h("div.soft-box", {}, h("div.soft-box__head", {}, "บัตรสะสม", h("span", {}, `${st.punch.count}/10`)), slots(st.punch.count),
        h("p.hint", { style: { fontSize: "12px" } }, st.punch.boxes ? "ครบแล้ว! เปิดกล่องของขวัญได้" : "รับเควสต์ 1 ครั้ง = เจาะ 1 ช่อง · ครบ 10 ช่องได้กล่องของขวัญ"),
        st.punch.boxes ? button("เปิดกล่องของขวัญ", { kind: "primary", small: true, onclick: openGift }) : null));
  }

  function toggleQuests() {
    if (panel) { panel.remove(); panel = null; } else { panel = h("div.g-panel.sketch.sketch--card", { role: "dialog", "aria-label": "เควสต์" }); card.append(panel); paintPanel(); }
    paintHud();
  }

  async function claim(x, btn) {
    btn.disabled = true;
    const r = await call("quest_claim", x.id);
    if (!r.ok) { toast(r.error.message, { error: true }); return refresh(); }
    await refresh();
    setCoins(st.balance, true);
    const full = r.punch.boxes > 0;
    const close = showDialog(h("div.dialog__panel.sketch.sketch--card.reward", { role: "document" },
      h("span.reward__mascot", {}, mascot("done", 120)),
      raw(burstSvg()),
      h("h2", {}, "เควสต์สำเร็จ!"),
      h("p.hint", { style: { fontSize: "14px" } }, x.title),
      h("span.reward-amount", {}, raw(coinSvg(26)), `+${r.coins} เหรียญ`),
      h("div.soft-box", { style: { width: "100%" } }, h("div.soft-box__head", {}, "บัตรสะสม", h("span", {}, full ? "10/10 ครบแล้ว!" : `${r.punch.count}/10`)),
        slots(r.punch.count, r.punch.count - 1), h("p.hint", { style: { fontSize: "13px" } }, full ? "เปิดกล่องของขวัญได้ 1 กล่อง" : `อีก ${10 - r.punch.count} ช่องได้กล่องของขวัญ`)),
      h("div.dialog__actions", {}, ...(full
        ? [button("ไว้ทีหลัง", { onclick: () => close() }), button("เปิดกล่องของขวัญ", { kind: "primary", onclick: () => { close(); openGift(); } })]
        : [button("เยี่ยม!", { kind: "primary", onclick: () => close() })]))));
  }

  // ---------------------------------------------------------------- gift box
  async function openGift() {
    const r = await call("gift_open");
    if (!r.ok) return toast(r.error.message, { error: true });
    await refresh();
    const box = await fetch("garden/base/ui/gift-box.svg").then((x) => x.text());
    const art = h("div.gift-art", {},
      ...[[30, 40, "#FFE07A", 26], [236, 30, "#9CC9FF", 22], [262, 120, "#FFA8B8", 18], [20, 140, "#9CC9FF", 18], [150, 0, "#FFE07A", 22]]
        .map(([x, y, c, s], i) => h("span.spark", { style: { left: `${x}px`, top: `${y}px`, animationDelay: `${i * 0.2}s` }, html: sparkSvg(c, s) })),
      h("div.box.is-shaking", { html: box }));
    let title;
    if (r.item) {
      const d = m.byId[r.item.id];
      const prize = h("div.prize", { style: { width: `${Math.min(170, d.w * 0.7)}px`, height: `${Math.min(150, d.h * 0.7)}px` } });
      prize.append(await itemSvg(d.id));
      art.append(prize);
      title = h("h2", {}, `ได้${d.name}!`, " ", h("span.badge", {}, RARITY[r.rarity] || r.rarity));
    } else {
      title = h("h2", {}, `ได้ ${r.coins} เหรียญ!`);
      setCoins(st.balance, true);
    }
    const odds = st.odds.map((o) => `${RARITY[o.rarity]} ${o.percent}%`).join(" · ");
    const close = showDialog(h("div.dialog__panel.sketch.sketch--card.reward", { role: "document" }, art, title,
      h("p.hint", { style: { fontSize: "14px" } }, r.item ? "เก็บไว้ในถาดของตกแต่งแล้ว" : "ของในกล่องมีครบทุกชิ้นแล้ว เลยได้เหรียญแทน"),
      h("div.odds", {}, `โอกาสในกล่อง: ${odds}`, h("p", {}, "ไม่ได้ของซ้ำกับที่มีอยู่แล้ว · ของในเกมเท่านั้น ไม่มีการใช้เงินจริง")),
      h("div.dialog__actions", {}, button("เก็บไว้ก่อน", { onclick: () => close() }),
        r.item ? button("วางเลย", { kind: "primary", onclick: () => { close(); decorate(); } }) : null)));
  }

  // ---------------------------------------------------------------- decorate
  function decorate() {
    if (decor) return;
    panel?.remove();
    panel = null;
    welcome?.remove();
    hud.hidden = true;
    decor = startDecorate({ card, stage, m, rows: st.items, onExit: async (saved) => {
      decor = null;
      hud.hidden = false;
      if (saved) {
        const placed = st.items.filter((i) => i.x !== null).length;
        st = await call("garden_state");
        const now = st.items.filter((i) => i.x !== null).length;
        toast(now > placed ? `วางของเพิ่ม ${now - placed} ชิ้นแล้ว` : "จัดลานแล้ว");
      }
      await stage.setItems(st.items);
      paintHud();
    } });
  }

  paintHud();
  if (params.decor === "1") decorate();

  const tick = setInterval(sky, 20000);
  const poll = setInterval(() => { if (!decor && !document.hidden) refresh(); }, 60000);
  const clock = setInterval(() => { if (!decor && st.open_session) paintHud(); }, 30000);
  const onKey = (e) => { if (e.key === "Escape" && panel) toggleQuests(); };
  window.addEventListener("keydown", onKey);
  return () => {
    clearInterval(tick); clearInterval(poll); clearInterval(clock);
    window.removeEventListener("keydown", onKey);
    decor?.abort();
    stage.destroy();
  };
}

function burstSvg() {
  const conf = [[30, 30, "#FFE07A", 20], [62, 70, "#FFA8B8", -30], [250, 28, "#9CC9FF", 35], [280, 80, "#FFA8B8", 10], [110, 14, "#9CC9FF", -15],
    [205, 12, "#FFE07A", 60], [20, 92, "#9CC9FF", 50], [296, 46, "#FFE07A", -40]];
  let s = conf.map(([x, y, c, r]) => `<rect class="cf" x="${x - 7}" y="${y - 3}" width="14" height="6" rx="3" fill="${c}" stroke="#22304A" stroke-width="1.3" transform="rotate(${r} ${x} ${y})"/>`).join("");
  for (const [cx, cy, r] of [[124, 70, 24], [178, 64, 28], [150, 92, 22]]) {
    s += `<g class="c"><circle cx="${cx}" cy="${cy}" r="${r}" fill="#FFD54A" stroke="#22304A" stroke-width="2.6"/><circle cx="${cx}" cy="${cy}" r="${(r * 0.58).toFixed(1)}" fill="none" stroke="#D9A21B" stroke-width="2.4"/></g>`;
  }
  return `<svg class="burst" viewBox="0 0 310 120" aria-hidden="true">${s}</svg>`;
}

function sparkSvg(c, s) {
  const pts = Array.from({ length: 8 }, (_, i) => { const a = (Math.PI * i) / 4, r = i % 2 ? 3.4 : 10; return `${(12 + r * Math.cos(a)).toFixed(1)},${(12 + r * Math.sin(a)).toFixed(1)}`; }).join(" ");
  return `<svg width="${s}" height="${s}" viewBox="0 0 24 24" aria-hidden="true"><polygon points="${pts}" fill="${c}" stroke="#22304A" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
}

