//! Garden game rules: who earns coins, quests can't be claimed twice, gift boxes never repeat, money can't go below a price.

use chrono::{NaiveDate, NaiveDateTime};
use rusqlite::{Connection, params};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

use tokbat_lib::api::Api;
use tokbat_lib::{db, game};

fn day(d: u32) -> NaiveDate {
    NaiveDate::from_ymd_opt(2026, 11, d).unwrap()
}
fn at(d: u32, h: u32, m: u32) -> NaiveDateTime {
    day(d).and_hms_opt(h, m, 0).unwrap()
}

struct T {
    api_: Option<Api>,
    tmp: PathBuf,
}
impl T {
    fn api(&self) -> &Api {
        self.api_.as_ref().unwrap()
    }
    fn call(&self, m: &str, args: Value) -> Value {
        self.api().call(m, args.as_array().unwrap()).unwrap_or_else(|e| panic!("{m}: {e}"))
    }
    fn clock(&self, d: u32, h: u32, mi: u32) {
        let now = at(d, h, mi);
        self.api().set_clock(Box::new(move || now.date()), Box::new(move || now));
    }
    fn state(&self) -> Value {
        self.call("garden_state", json!([]))
    }
    fn balance(&self) -> i64 {
        self.state()["balance"].as_i64().unwrap()
    }
}
impl Drop for T {
    fn drop(&mut self) {
        self.api_ = None;
        let _ = std::fs::remove_dir_all(&self.tmp);
    }
}

fn api() -> T {
    let tmp = std::env::temp_dir().join(format!("tokbat-game-{}-{:x}", std::process::id(), rand::random::<u64>()));
    std::fs::create_dir_all(&tmp).unwrap();
    let t = T { api_: Some(Api::new(tmp.join("worktime.db"), None).unwrap()), tmp };
    t.clock(10, 9, 0);
    t
}

fn mem() -> Connection {
    db::connect(Path::new(":memory:")).unwrap()
}

#[test]
fn first_visit_starts_the_game_with_welcome_coins_once() {
    let t = api();
    let s = t.state();
    assert_eq!(s["started"], "2026-11-10");
    assert_eq!(s["balance"], game::WELCOME_COINS);
    let starters = s["items"].as_array().unwrap().iter().filter(|i| i["from"] == "starter" && i["x"].is_number()).count();
    assert_eq!(starters, 9, "8 grass tufts + 1 flower patch placed");
    t.state();
    assert_eq!(t.balance(), game::WELCOME_COINS, "welcome is paid once");
}

#[test]
fn timer_work_earns_two_coins_an_hour_up_to_the_cap() {
    let t = api();
    t.state();
    t.clock(10, 9, 0);
    let id = t.call("start_now", json!([]))["session"]["id"].as_i64().unwrap();
    t.clock(10, 13, 45);
    let live = t.state();
    assert_eq!(live["wage"]["today"], 9, "4:45 running = 9 coins (whole half hours)");
    let r = t.call("stop_now", json!([id]));
    assert_eq!(r["session"]["source"], "timer");
    assert_eq!(t.balance(), game::WELCOME_COINS + 9);
    // a long day stops at the cap (8 h = 16)
    t.call("save_session", json!([{"date": "2026-11-10", "start": "14:00", "end": "23:30", "break_min": 0, "note": ""}]));
    assert_eq!(t.state()["wage"]["today"], 16);
    t.call("save_settings", json!([{"coin_cap_hours": 12}]));
    assert_eq!(t.state()["wage"]["today"], 24, "14:15 worked = 28 coins, but the 12 h cap is 24");
}

#[test]
fn imports_older_days_and_late_backfills_earn_nothing() {
    let t = api();
    t.clock(20, 9, 0);
    t.state(); // game starts on the 20th
    // before the game started
    t.call("save_session", json!([{"date": "2026-11-15", "start": "09:00", "end": "17:00", "break_min": 0, "note": ""}]));
    // imported, after the start
    t.call("save_session", json!([{"date": "2026-11-20", "start": "01:00", "end": "05:00", "break_min": 0, "note": "", "source": "import"}]));
    assert_eq!(t.balance(), game::WELCOME_COINS);
    // typed on the 29th for the 20th: more than 7 days late
    t.clock(29, 9, 0);
    t.call("save_session", json!([{"date": "2026-11-20", "start": "09:00", "end": "13:00", "break_min": 0, "note": ""}]));
    assert_eq!(t.balance(), game::WELCOME_COINS);
    // typed on the 29th for the 23rd: counts
    t.call("save_session", json!([{"date": "2026-11-23", "start": "09:00", "end": "13:00", "break_min": 0, "note": ""}]));
    assert_eq!(t.balance(), game::WELCOME_COINS + 8);
}

#[test]
fn editing_a_timer_entry_by_hand_makes_it_manual() {
    let t = api();
    t.state();
    let id = t.call("start_now", json!([]))["session"]["id"].as_i64().unwrap();
    t.clock(10, 11, 0);
    t.call("stop_now", json!([id]));
    let r = t.call("save_session", json!([{"id": id, "date": "2026-11-10", "start": "09:00", "end": "11:00", "break_min": 0, "note": "แก้หมายเหตุ"}]));
    assert_eq!(r["session"]["source"], "timer", "only the note changed");
    let r = t.call("save_session", json!([{"id": id, "date": "2026-11-10", "start": "08:00", "end": "11:00", "break_min": 0, "note": ""}]));
    assert_eq!(r["session"]["source"], "manual");
}

#[test]
fn quests_claim_once_and_only_when_done() {
    let t = api();
    t.state();
    let daily = t.state()["quests"]["daily"].as_array().unwrap().clone();
    assert_eq!(daily.len(), 3);
    let work = daily.iter().find(|q| q["id"].as_str().unwrap().starts_with("work_")).unwrap().clone();
    let id = work["id"].as_str().unwrap().to_string();
    let r = t.call("quest_claim", json!([id]));
    assert_eq!(r["error"]["code"], "not_done");
    let goal = work["progress"]["goal"].as_i64().unwrap();
    t.call("save_session", json!([{"date": "2026-11-10", "start": "00:30", "end": format!("{:02}:30", goal / 60), "break_min": 0, "note": "ทำงาน"}]));
    let r = t.call("quest_claim", json!([id]));
    assert_eq!(r["ok"], true, "{r}");
    assert_eq!(r["punch"]["count"], 1);
    assert_eq!(t.call("quest_claim", json!([id]))["error"]["code"], "claimed");
    let coins = t.balance();
    assert_eq!(coins, game::WELCOME_COINS + work["reward"].as_i64().unwrap() + goal / 30);
    // same quests all day
    t.clock(10, 18, 0);
    let again: Vec<String> = t.state()["quests"]["daily"].as_array().unwrap().iter().map(|q| q["id"].as_str().unwrap().to_string()).collect();
    assert_eq!(again, daily.iter().map(|q| q["id"].as_str().unwrap().to_string()).collect::<Vec<_>>());
}

#[test]
fn a_day_off_has_the_rest_quest() {
    let t = api();
    t.state();
    t.call("mark_day_off", json!(["2026-11-10"]));
    let d = t.state()["quests"]["daily"].clone();
    assert_eq!(d[0]["id"], "rest_day");
    assert_eq!(t.call("quest_claim", json!(["rest_day"]))["coins"], 5);
}

#[test]
fn buying_needs_enough_coins_and_a_shortened_day_can_go_negative() {
    let t = api();
    t.state();
    let r = t.call("shop_buy", json!(["dog-house"]));
    assert_eq!(r["ok"], true);
    assert_eq!(t.balance(), game::WELCOME_COINS - 50);
    t.call("shop_buy", json!(["rabbit-hutch"]));
    t.call("shop_buy", json!(["cat-tower"]));
    assert_eq!(t.balance(), 5);
    let r = t.call("shop_buy", json!(["coconut"]));
    assert_eq!(r["error"]["code"], "coins", "5 left, coconut is 35");
    assert_eq!(t.call("shop_buy", json!(["nope"]))["error"]["code"], "no_item");
    // earn, spend, then shorten the day: the balance follows the hours
    let s = t.call("save_session", json!([{"date": "2026-11-10", "start": "00:00", "end": "08:00", "break_min": 0, "note": ""}]));
    assert_eq!(t.balance(), 5 + 16);
    t.call("shop_buy", json!(["mailbox"]));
    assert_eq!(t.balance(), 3);
    let id = s["session"]["id"].as_i64().unwrap();
    t.call("save_session", json!([{"id": id, "date": "2026-11-10", "start": "00:00", "end": "01:00", "break_min": 0, "note": ""}]));
    assert_eq!(t.balance(), 3 - 14);
    assert_eq!(t.call("shop_buy", json!(["ball"]))["error"]["code"], "coins");
}

#[test]
fn adopting_checks_the_pet_the_name_and_the_price() {
    let t = api();
    t.state();
    assert_eq!(t.call("pet_adopt", json!([{"species": "cat", "color": "purple", "name": "ม่วง"}]))["error"]["code"], "no_pet");
    assert_eq!(t.call("pet_adopt", json!([{"species": "cat", "color": "orange", "name": "   "}]))["error"]["code"], "name");
    assert_eq!(t.call("pet_adopt", json!([{"species": "cat", "color": "orange", "name": "ชื่อยาวเกินสิบสองตัวอักษร"}]))["error"]["code"], "name");
    let r = t.call("pet_adopt", json!([{"species": "cat", "color": "orange", "name": "ส้มจี๊ด"}]));
    assert_eq!(r["pet"]["name"], "ส้มจี๊ด");
    assert_eq!(t.balance(), game::WELCOME_COINS - game::PET_PRICE);
    assert_eq!(t.call("pet_adopt", json!([{"species": "dog", "color": "gold", "name": "ทองดี"}]))["pet"]["name"], "ทองดี");
    assert_eq!(t.call("pet_adopt", json!([{"species": "rabbit", "color": "white", "name": "ปุย"}]))["error"]["code"], "coins", "30 left, a pet is 60");
    let pid = r["pet"]["id"].as_i64().unwrap();
    assert_eq!(t.call("pet_rename", json!([pid, "จี๊ด"]))["pet"]["name"], "จี๊ด");
    // the special quest notices
    let sp = t.state()["quests"]["special"].clone();
    assert_eq!(sp[0]["id"], "first_pet");
    assert_eq!(sp[0]["done"], true);
}

#[test]
fn decor_places_and_stores_pieces() {
    let t = api();
    t.state();
    let id = t.call("shop_buy", json!(["bench"]))["id"].as_i64().unwrap();
    let r = t.call("decor_save", json!([[{"id": id, "x": 540, "y": 470, "flip": true}]]));
    assert_eq!(r["saved"], 1);
    let it = t.state()["items"].as_array().unwrap().iter().find(|i| i["id"] == id).unwrap().clone();
    assert_eq!((it["x"].as_f64(), it["flip"].as_bool()), (Some(540.0), Some(true)));
    t.call("decor_save", json!([[{"id": id, "x": null, "y": null, "flip": false}]]));
    let it = t.state()["items"].as_array().unwrap().iter().find(|i| i["id"] == id).unwrap().clone();
    assert!(it["x"].is_null(), "back in the tray");
}

#[test]
fn gift_boxes_need_ten_claims_and_never_repeat_an_item() {
    let con = mem();
    assert_eq!(game::open_gift(&con, game::manifest(), 0, 0)["error"]["code"], "no_box");
    let total = game::manifest()["items"].as_array().unwrap().len();
    for i in 0..(total + 3) * 10 {
        con.execute("INSERT INTO quest_claims (period, quest_id, coins) VALUES (?1, 'x', 1)", params![format!("p{i}")]).unwrap();
    }
    assert_eq!(game::punch(&con)["count"], 10, "a full card stays full until opened");
    let mut seen = std::collections::HashSet::new();
    for k in 0..total {
        let r = game::open_gift(&con, game::manifest(), (k as u32 * 37) % 100, k as u64 * 7919);
        let id = r["item"]["id"].as_str().unwrap().to_string();
        assert!(seen.insert(id.clone()), "duplicate {id}");
    }
    // everything owned now: coins instead
    let r = game::open_gift(&con, game::manifest(), 50, 1);
    assert_eq!(r["coins"], game::GIFT_FALLBACK_COINS);
    assert!(r["item"].is_null());
}

#[test]
fn gift_odds_pick_the_rarity_by_roll() {
    let con = mem();
    for i in 0..30 {
        con.execute("INSERT INTO quest_claims (period, quest_id, coins) VALUES (?1, 'x', 1)", params![format!("p{i}")]).unwrap();
    }
    assert_eq!(game::open_gift(&con, game::manifest(), 10, 0)["rarity"], "common");
    assert_eq!(game::open_gift(&con, game::manifest(), 80, 0)["rarity"], "rare");
    assert_eq!(game::open_gift(&con, game::manifest(), 97, 0)["rarity"], "special");
}

#[test]
fn upgrading_marks_existing_sessions_as_legacy() {
    let con = Connection::open_in_memory().unwrap();
    con.execute_batch(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, work_date TEXT NOT NULL, start_min INTEGER NOT NULL, end_min INTEGER,
            break_min INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')));
         CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
         CREATE TABLE days_off (work_date TEXT PRIMARY KEY);
         CREATE TABLE exports (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL, format TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')));
         INSERT INTO sessions (work_date, start_min, end_min) VALUES ('2026-11-01', 540, 1020);
         PRAGMA user_version = 1;",
    )
    .unwrap();
    assert_eq!(db::migrate(&con).unwrap(), 3);
    let source: String = con.query_row("SELECT source FROM sessions", [], |r| r.get(0)).unwrap();
    assert_eq!(source, "legacy");
    con.execute("INSERT INTO sessions (work_date, start_min, end_min) VALUES ('2026-11-02', 540, 600)", []).unwrap();
    let fresh: String = con.query_row("SELECT source FROM sessions WHERE work_date = '2026-11-02'", [], |r| r.get(0)).unwrap();
    assert_eq!(fresh, "manual");
}

#[test]
fn halving_prices_refunds_what_was_bought_before() {
    let con = mem();
    con.execute_batch(
        "INSERT INTO coin_ledger (delta, kind, ref) VALUES (150, 'welcome', 'welcome'), (-120, 'adopt', 'cat-orange'),
            (-25, 'buy', 'bench'), (-5, 'buy', 'grass-tuft'), (10, 'quest', '2026-11-01 use_timer'), (30, 'gift', 'all-owned');
         PRAGMA user_version = 2;",
    )
    .unwrap();
    assert_eq!(db::migrate(&con).unwrap(), 3);
    let (n, sum): (i64, i64) = con.query_row("SELECT COUNT(*), SUM(delta) FROM coin_ledger WHERE kind = 'refund'", [], |r| Ok((r.get(0)?, r.get(1)?))).unwrap();
    assert_eq!((n, sum), (3, 60 + 12 + 2)); // the new price is half, rounded up: 120 → 60, 25 → 13, 5 → 3
    assert_eq!(db::migrate(&con).unwrap(), 3); // once only
    let again: i64 = con.query_row("SELECT COUNT(*) FROM coin_ledger WHERE kind = 'refund'", [], |r| r.get(0)).unwrap();
    assert_eq!(again, 3);
    assert_eq!(game::PET_PRICE, 60);
}
