//! Garden game: coins, quests, the punch card and gift boxes, the shop, pets and decorating.
//!
//! Coins = wages worked out from sessions every time (never stored, so editing a session corrects them)
//! + the ledger (welcome gift, quest rewards, purchases). Wages: 2 coins an hour up to a daily cap, only for
//! sessions from the timer or typed by hand, on or after the day the game started; a hand entry counts only if
//! it was typed within 7 days of its date. Imports and older data never earn.
//! The catalogue (items, prices, rarity, pets) is the art pack's manifest, shared with the web UI.

use chrono::{Datelike, Days, NaiveDate, NaiveDateTime, Timelike};
use rand::Rng;
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Map, Value, json};
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

use crate::repo::{Repo, iso, parse_iso};
use crate::timecalc as tc;

pub const MANIFEST_JSON: &str = include_str!("../../web/garden/base/manifest.json");
pub const RATE_PER_HOUR: i64 = 2;
pub const WELCOME_COINS: i64 = 150;
pub const PET_PRICE: i64 = 60;
pub const BACKFILL_DAYS: i64 = 7;
pub const NAME_MAX: usize = 12;
/// Gift box odds, shown to the player as they are.
pub const ODDS: [(&str, u32); 3] = [("common", 70), ("rare", 25), ("special", 5)];
/// Coins instead of an item once every item of the box is already owned.
pub const GIFT_FALLBACK_COINS: i64 = 15;

pub fn manifest() -> &'static Value {
    static M: OnceLock<Value> = OnceLock::new();
    M.get_or_init(|| serde_json::from_str(MANIFEST_JSON).expect("garden manifest"))
}

/// `cat` is the catalogue in use: the built-in manifest plus installed packs (see packs::merge).
pub fn item<'a>(cat: &'a Value, id: &str) -> Option<&'a Value> {
    cat["items"].as_array()?.iter().find(|i| i["id"] == id)
}

fn pet_exists(cat: &Value, species: &str, color: &str) -> bool {
    cat["pets"].as_array().is_some_and(|a| a.iter().any(|p| p["species"] == species && p["color"] == color))
}

fn err(code: &str, message: &str) -> Value {
    json!({"ok": false, "error": {"code": code, "message": message}})
}

// ---------------------------------------------------------------- settings
pub struct Rules {
    pub enabled: bool,
    pub started: Option<NaiveDate>,
    pub cap_coins: i64,
}

pub fn rules(s: &Map<String, Value>) -> Rules {
    let hours = s.get("coin_cap_hours").and_then(Value::as_i64).unwrap_or(8).clamp(1, 24);
    Rules {
        enabled: s.get("game_enabled").and_then(Value::as_bool).unwrap_or(true),
        started: s.get("game_started").and_then(Value::as_str).and_then(parse_iso),
        cap_coins: hours * RATE_PER_HOUR,
    }
}

// ---------------------------------------------------------------- work that earns
#[derive(Default, Clone, Copy)]
pub struct DayWork {
    /// minutes that earn coins (timer + timely hand entries), the open session counted up to now
    pub minutes: i64,
    pub sessions: i64,
    pub with_note: i64,
    pub break_min: i64,
    pub timer: bool,
}

fn minutes_of(date: NaiveDate, start: i64, end: Option<i64>, brk: i64, now: NaiveDateTime) -> i64 {
    match end {
        Some(e) => tc::net_minutes(start, e, brk).unwrap_or(0),
        None => {
            let started = date.and_hms_opt(0, 0, 0).unwrap() + chrono::Duration::minutes(start);
            let m = (now - started).num_minutes();
            if (0..24 * 60).contains(&m) { (m - brk).max(0) } else { 0 }
        }
    }
}

/// Earning work per day between `from` and `to` (inclusive).
pub fn work_by_day(con: &Connection, from: NaiveDate, to: NaiveDate, now: NaiveDateTime) -> HashMap<NaiveDate, DayWork> {
    let mut out: HashMap<NaiveDate, DayWork> = HashMap::new();
    let Ok(mut st) = con.prepare(
        "SELECT work_date, start_min, end_min, break_min, note, source, created_at FROM sessions
         WHERE work_date BETWEEN ?1 AND ?2 AND source IN ('timer', 'manual')",
    ) else {
        return out;
    };
    let rows = st.query_map(params![iso(from), iso(to)], |r| {
        Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?, r.get::<_, Option<i64>>(2)?, r.get::<_, i64>(3)?, r.get::<_, String>(4)?, r.get::<_, String>(5)?, r.get::<_, String>(6)?))
    });
    let Ok(rows) = rows else { return out };
    for (date, start, end, brk, note, source, created) in rows.filter_map(Result::ok) {
        let Some(d) = parse_iso(&date) else { continue };
        if source == "manual" {
            let typed = created.get(..10).and_then(parse_iso).unwrap_or(d);
            if (typed - d).num_days() > BACKFILL_DAYS {
                continue;
            }
        }
        let w = out.entry(d).or_default();
        w.minutes += minutes_of(d, start, end, brk, now);
        w.sessions += 1;
        w.with_note += i64::from(!note.trim().is_empty());
        w.break_min += brk;
        w.timer |= source == "timer";
    }
    out
}

pub fn wage(minutes: i64, cap_coins: i64) -> i64 {
    (minutes * RATE_PER_HOUR / 60).clamp(0, cap_coins)
}

pub fn balance(con: &Connection, r: &Rules, today: NaiveDate, now: NaiveDateTime) -> i64 {
    let ledger: i64 = con.query_row("SELECT COALESCE(SUM(delta), 0) FROM coin_ledger", [], |x| x.get(0)).unwrap_or(0);
    let Some(started) = r.started else { return ledger };
    let wages: i64 = work_by_day(con, started, today, now).values().map(|w| wage(w.minutes, r.cap_coins)).sum();
    wages + ledger
}

// ---------------------------------------------------------------- quests
struct Rng64(u64);
impl Rng64 {
    fn seeded(text: &str) -> Self {
        let mut h: u64 = 0xcbf29ce484222325;
        for b in text.bytes() {
            h ^= b as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
        Rng64(h | 1)
    }
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn below(&mut self, n: u64) -> u64 {
        self.next() % n
    }
}

pub fn week_start(d: NaiveDate) -> NaiveDate {
    d - Days::new(d.weekday().num_days_from_monday() as u64)
}

fn q(id: &str, title: &str, reward: i64, kind: &str, period: &str, value: i64, goal: i64, unit: &str) -> Value {
    json!({"id": id, "title": title, "reward": reward, "kind": kind, "period": period,
           "progress": {"value": value.min(goal), "goal": goal, "unit": unit}, "done": value >= goal, "claimed": false})
}

/// Today's three quests (the same all day: picked with the date as the seed), or the rest-day quest on a day off.
pub fn daily(con: &Connection, today: NaiveDate, now: NaiveDateTime) -> Vec<Value> {
    let period = iso(today);
    let off: bool = con.query_row("SELECT 1 FROM days_off WHERE work_date = ?", [&period], |_| Ok(())).optional().ok().flatten().is_some();
    let w = work_by_day(con, today, today, now).get(&today).copied().unwrap_or_default();
    if off && w.sessions == 0 {
        return vec![q("rest_day", "วันพักผ่อน · พักให้เต็มที่", 5, "daily", &period, 1, 1, "")];
    }
    let mut rng = Rng64::seeded(&format!("quests-{period}"));
    let tier = match rng.below(10) {
        0..=2 => (2, 3),
        3..=7 => (4, 5),
        _ => (6, 8),
    };
    let work = q(&format!("work_{}h", tier.0), &format!("ทำงานครบ {} ชั่วโมง", tier.0), tier.1, "daily", &period, w.minutes, tier.0 * 60, "min");
    let mut others = vec![
        q("use_timer", "จับเวลาด้วยปุ่มเริ่มงาน", 3, "daily", &period, i64::from(w.timer), 1, ""),
        q("notes_all", "เขียนว่าทำอะไรครบทุกช่วง", 3, "daily", &period, if w.sessions > 0 && w.with_note == w.sessions { 1 } else { 0 }, 1, ""),
        q("take_break", "พักอย่างน้อย 15 นาที", 3, "daily", &period, if w.break_min >= 15 || w.sessions >= 2 { 1 } else { 0 }, 1, ""),
    ];
    let drop = rng.below(3) as usize;
    others.remove(drop);
    let mut out = vec![work];
    out.extend(others);
    out
}

pub fn weekly(con: &Connection, today: NaiveDate, now: NaiveDateTime) -> Vec<Value> {
    let ws = week_start(today);
    let period = format!("W{}", iso(ws));
    let days = work_by_day(con, ws, ws + Days::new(6), now);
    let worked = days.values().filter(|w| w.minutes > 0).count() as i64;
    let total: i64 = days.values().map(|w| w.minutes).sum();
    vec![
        q("week_5days", "ทำงานครบ 5 วันในสัปดาห์นี้", 15, "weekly", &period, worked, 5, "day"),
        q("week_20h", "ทำงานรวม 20 ชั่วโมงในสัปดาห์นี้", 15, "weekly", &period, total, 20 * 60, "min"),
    ]
}

pub fn special(con: &Connection) -> Vec<Value> {
    let pets: i64 = con.query_row("SELECT COUNT(*) FROM pets", [], |r| r.get(0)).unwrap_or(0);
    let placed: i64 = con.query_row("SELECT COUNT(*) FROM owned_items WHERE x IS NOT NULL AND got_from != 'starter'", [], |r| r.get(0)).unwrap_or(0);
    vec![
        q("first_pet", "รับสัตว์ตัวแรกมาเลี้ยง", 10, "special", "once", pets, 1, ""),
        q("place_5", "วางของตกแต่งในลาน 5 ชิ้น", 10, "special", "once", placed, 5, ""),
    ]
}

fn claimed(con: &Connection) -> HashSet<(String, String)> {
    con.prepare("SELECT period, quest_id FROM quest_claims")
        .and_then(|mut s| s.query_map([], |r| Ok((r.get(0)?, r.get(1)?))).map(|r| r.filter_map(Result::ok).collect()))
        .unwrap_or_default()
}

pub fn quests(con: &Connection, today: NaiveDate, now: NaiveDateTime) -> Value {
    let done = claimed(con);
    let mark = |mut list: Vec<Value>| -> Vec<Value> {
        for x in &mut list {
            let key = (x["period"].as_str().unwrap_or("").to_string(), x["id"].as_str().unwrap_or("").to_string());
            x["claimed"] = json!(done.contains(&key));
        }
        list
    };
    let (d, w, s) = (mark(daily(con, today, now)), mark(weekly(con, today, now)), mark(special(con)));
    let ready = d.iter().chain(&w).chain(&s).filter(|x| x["done"] == true && x["claimed"] == false).count();
    json!({"daily": d, "weekly": w, "special": s, "ready": ready})
}

pub fn claim(con: &Connection, quest_id: &str, today: NaiveDate, now: NaiveDateTime) -> Value {
    let all = quests(con, today, now);
    let found = ["daily", "weekly", "special"].iter().flat_map(|k| all[*k].as_array().cloned().unwrap_or_default()).find(|x| x["id"] == quest_id);
    let Some(x) = found else { return err("no_quest", "ไม่มีเควสต์นี้ในรอบนี้แล้ว") };
    if x["claimed"] == true {
        return err("claimed", "รับรางวัลเควสต์นี้ไปแล้ว");
    }
    if x["done"] != true {
        return err("not_done", "ยังทำเควสต์นี้ไม่ครบ");
    }
    let period = x["period"].as_str().unwrap_or("");
    let coins = x["reward"].as_i64().unwrap_or(0);
    let ok = con.execute("INSERT INTO quest_claims (period, quest_id, coins) VALUES (?1, ?2, ?3)", params![period, quest_id, coins]).is_ok()
        && con.execute("INSERT INTO coin_ledger (delta, kind, ref) VALUES (?1, 'quest', ?2)", params![coins, format!("{period}:{quest_id}")]).is_ok();
    if !ok {
        return err("claimed", "รับรางวัลเควสต์นี้ไปแล้ว");
    }
    let p = punch(con);
    json!({"ok": true, "quest": x, "coins": coins, "punch": p})
}

// ---------------------------------------------------------------- punch card + gift boxes
pub fn punch(con: &Connection) -> Value {
    let claims: i64 = con.query_row("SELECT COUNT(*) FROM quest_claims", [], |r| r.get(0)).unwrap_or(0);
    let opened: i64 = con.query_row("SELECT COUNT(*) FROM gifts", [], |r| r.get(0)).unwrap_or(0);
    let boxes = (claims / 10 - opened).max(0);
    // a full card stays full until its box is opened
    let count = if boxes > 0 { 10 } else { claims % 10 };
    json!({"count": count, "boxes": boxes, "claims": claims})
}

fn owned_ids(con: &Connection) -> HashSet<String> {
    con.prepare("SELECT DISTINCT item_id FROM owned_items")
        .and_then(|mut s| s.query_map([], |r| r.get(0)).map(|r| r.filter_map(Result::ok).collect()))
        .unwrap_or_default()
}

/// Opens one box: rarity by ODDS, then an item of that rarity the player doesn't own yet (no duplicates).
/// Falls back to the nearest rarity that still has something new, or coins once everything is owned.
pub fn open_gift(con: &Connection, cat: &Value, roll: u32, pick: u64) -> Value {
    if punch(con)["boxes"].as_i64().unwrap_or(0) < 1 {
        return err("no_box", "ยังไม่มีกล่องของขวัญให้เปิด");
    }
    let mut acc = 0;
    let mut rarity = "common";
    for (r, w) in ODDS {
        acc += w;
        if roll % 100 < acc {
            rarity = r;
            break;
        }
    }
    let owned = owned_ids(con);
    let items = cat["items"].as_array().cloned().unwrap_or_default();
    let order: Vec<&str> = match rarity {
        "special" => vec!["special", "rare", "common"],
        "rare" => vec!["rare", "special", "common"],
        _ => vec!["common", "rare", "special"],
    };
    for r in order {
        let pool: Vec<&Value> = items.iter().filter(|i| i["rarity"] == r && !owned.contains(i["id"].as_str().unwrap_or(""))).collect();
        if pool.is_empty() {
            continue;
        }
        let it = pool[(pick % pool.len() as u64) as usize];
        let id = it["id"].as_str().unwrap_or("");
        con.execute("INSERT INTO owned_items (item_id, got_from) VALUES (?1, 'gift')", [id]).ok();
        con.execute("INSERT INTO gifts (item_id, rarity) VALUES (?1, ?2)", [id, r]).ok();
        return json!({"ok": true, "item": it, "rarity": r, "rolled": rarity, "punch": punch(con)});
    }
    con.execute("INSERT INTO gifts (item_id, rarity) VALUES ('', 'coins')", []).ok();
    con.execute("INSERT INTO coin_ledger (delta, kind, ref) VALUES (?1, 'gift', 'all-owned')", [GIFT_FALLBACK_COINS]).ok();
    json!({"ok": true, "item": null, "coins": GIFT_FALLBACK_COINS, "rarity": "coins", "punch": punch(con)})
}

pub fn open_gift_random(con: &Connection, cat: &Value) -> Value {
    let mut rng = rand::rng();
    open_gift(con, cat, rng.random_range(0..100), rng.random())
}

// ---------------------------------------------------------------- shop, pets, decor
pub fn buy(con: &Connection, cat: &Value, item_id: &str, coins: i64) -> Value {
    let Some(it) = item(cat, item_id) else { return err("no_item", "ไม่มีของชิ้นนี้ในร้าน") };
    let price = it["price"].as_i64().unwrap_or(0);
    if coins < price {
        return err("coins", &format!("เหรียญไม่พอ ขาดอีก {} เหรียญ", price - coins));
    }
    con.execute("INSERT INTO coin_ledger (delta, kind, ref) VALUES (?1, 'buy', ?2)", params![-price, item_id]).ok();
    con.execute("INSERT INTO owned_items (item_id, got_from) VALUES (?1, 'shop')", [item_id]).ok();
    json!({"ok": true, "item": it, "price": price, "id": con.last_insert_rowid()})
}

pub fn adopt(con: &Connection, cat: &Value, species: &str, color: &str, name: &str, coins: i64) -> Value {
    if !pet_exists(cat, species, color) {
        return err("no_pet", "ไม่มีสัตว์สีนี้");
    }
    let name = name.trim();
    if name.is_empty() || name.chars().count() > NAME_MAX {
        return err("name", &format!("ตั้งชื่อ 1–{NAME_MAX} ตัวอักษร"));
    }
    if coins < PET_PRICE {
        return err("coins", &format!("เหรียญไม่พอ ขาดอีก {} เหรียญ", PET_PRICE - coins));
    }
    con.execute("INSERT INTO coin_ledger (delta, kind, ref) VALUES (?1, 'adopt', ?2)", params![-PET_PRICE, format!("{species}-{color}")]).ok();
    con.execute("INSERT INTO pets (species, color, name) VALUES (?1, ?2, ?3)", params![species, color, name]).ok();
    json!({"ok": true, "pet": pet(con, con.last_insert_rowid())})
}

fn pet(con: &Connection, id: i64) -> Option<Value> {
    con.query_row("SELECT id, species, color, name, adopted_at FROM pets WHERE id = ?", [id], |r| {
        Ok(json!({"id": r.get::<_, i64>(0)?, "species": r.get::<_, String>(1)?, "color": r.get::<_, String>(2)?, "name": r.get::<_, String>(3)?, "adopted_at": r.get::<_, String>(4)?}))
    })
    .optional()
    .ok()
    .flatten()
}

pub fn pets(con: &Connection) -> Vec<Value> {
    let ids: Vec<i64> = con.prepare("SELECT id FROM pets ORDER BY id").and_then(|mut s| s.query_map([], |r| r.get(0)).map(|r| r.filter_map(Result::ok).collect())).unwrap_or_default();
    ids.into_iter().filter_map(|id| pet(con, id)).collect()
}

pub fn rename_pet(con: &Connection, id: i64, name: &str) -> Value {
    let name = name.trim();
    if name.is_empty() || name.chars().count() > NAME_MAX {
        return err("name", &format!("ตั้งชื่อ 1–{NAME_MAX} ตัวอักษร"));
    }
    if con.execute("UPDATE pets SET name = ?1 WHERE id = ?2", params![name, id]).unwrap_or(0) == 0 {
        return err("no_pet", "ไม่พบสัตว์ตัวนี้");
    }
    json!({"ok": true, "pet": pet(con, id)})
}

pub fn items(con: &Connection) -> Vec<Value> {
    con.prepare("SELECT id, item_id, x, y, flip, got_from, scale FROM owned_items ORDER BY id")
        .and_then(|mut s| {
            s.query_map([], |r| {
                Ok(json!({"id": r.get::<_, i64>(0)?, "item": r.get::<_, String>(1)?, "x": r.get::<_, Option<f64>>(2)?, "y": r.get::<_, Option<f64>>(3)?,
                          "flip": r.get::<_, i64>(4)? != 0, "from": r.get::<_, String>(5)?, "scale": r.get::<_, f64>(6)?}))
            })
            .map(|r| r.filter_map(Result::ok).collect())
        })
        .unwrap_or_default()
}

/// Decorating ends with one save: [{id, x, y, flip, scale}] — x/y null puts the piece back in the tray; scale 0.5–2.
pub fn save_decor(con: &Connection, changes: &Value) -> Value {
    let world = &manifest()["world"];
    let (w, h) = (world["w"].as_f64().unwrap_or(1280.0), world["h"].as_f64().unwrap_or(800.0));
    let mut n = 0;
    for c in changes.as_array().cloned().unwrap_or_default() {
        let Some(id) = c["id"].as_i64() else { continue };
        // the lawn runs half a scene past each side of the drawn scene (web/js/garden/stage.js LAWN)
        let (x, y) = (c["x"].as_f64().map(|v| v.clamp(-w / 2.0 - 200.0, w * 1.5)), c["y"].as_f64().map(|v| v.clamp(-200.0, h)));
        let (x, y) = if x.is_some() && y.is_some() { (x, y) } else { (None, None) };
        let scale = c["scale"].as_f64().unwrap_or(1.0).clamp(0.5, 2.0);
        n += con.execute("UPDATE owned_items SET x = ?1, y = ?2, flip = ?3, scale = ?4 WHERE id = ?5", params![x, y, i64::from(c["flip"] == true), scale, id]).unwrap_or(0);
    }
    json!({"ok": true, "saved": n})
}

/// First visit with the game on: today becomes the start date, the welcome coins and a few tufts of grass.
pub fn start(repo: &Repo, today: NaiveDate) {
    repo.save_settings(&json!({"game_started": iso(today)}));
    let con = repo.con;
    if con.execute("INSERT OR IGNORE INTO coin_ledger (delta, kind, ref) VALUES (?1, 'welcome', 'welcome')", [WELCOME_COINS]).unwrap_or(0) == 1 {
        for (x, y) in [(70.0, 392.0), (380.0, 362.0), (640.0, 430.0), (930.0, 370.0), (1180.0, 380.0), (110.0, 660.0), (300.0, 700.0), (980.0, 480.0)] {
            con.execute("INSERT INTO owned_items (item_id, x, y, got_from) VALUES ('grass-tuft', ?1, ?2, 'starter')", params![x, y]).ok();
        }
        con.execute("INSERT INTO owned_items (item_id, x, y, got_from) VALUES ('flower-patch', 760, 560, 'starter')", []).ok();
    }
}

/// Everything the garden screen needs in one call.
pub fn state(repo: &Repo, today: NaiveDate, now: NaiveDateTime) -> Value {
    let s = repo.settings();
    let mut r = rules(&s);
    if r.enabled && r.started.is_none() {
        start(repo, today);
        r = rules(&repo.settings());
    }
    let con = repo.con;
    let w = work_by_day(con, today, today, now).get(&today).copied().unwrap_or_default();
    let all_today: i64 = repo.on(today).iter().map(|x| x["minutes"].as_i64().unwrap_or(0)).sum::<i64>()
        + repo.open_session().filter(|o| o["date"] == iso(today)).map(|o| {
            let st = tc::parse_hhmm(o["start"].as_str().unwrap_or("00:00")).unwrap_or(0);
            minutes_of(today, st, None, o["break_min"].as_i64().unwrap_or(0), now)
        }).unwrap_or(0);
    json!({
        "enabled": r.enabled,
        "started": r.started.map(iso),
        "now": now.format("%Y-%m-%dT%H:%M:%S").to_string(),
        "minute_of_day": now.hour() * 60 + now.minute(),
        "balance": balance(con, &r, today, now),
        "wage": {"today": wage(w.minutes, r.cap_coins), "cap": r.cap_coins, "rate": RATE_PER_HOUR, "minutes": w.minutes},
        "today_minutes": all_today,
        "open_session": repo.open_session(),
        "quests": quests(con, today, now),
        "punch": punch(con),
        "pets": pets(con),
        "items": items(con),
        "odds": ODDS.iter().map(|(k, v)| json!({"rarity": k, "percent": v})).collect::<Vec<_>>(),
        "pet_price": PET_PRICE,
        "rain": s.get("rain").and_then(Value::as_bool).unwrap_or(true),
        "day": today.day(),
    })
}
