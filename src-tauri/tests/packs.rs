//! Content packs: only signed, untouched, safe packs get in; they add to the shop and survive a restart.

use base64::Engine;
use chrono::NaiveDate;
use ed25519_dalek::{Signer, SigningKey};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::path::PathBuf;

use tokbat_lib::api::Api;

const SVG: &str = r##"<svg width="60" height="80" viewBox="0 0 60 80" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 75L30 5L55 75Z" fill="#FFA8B8" stroke="#22304A" stroke-width="4"/></svg>"##;

fn key() -> SigningKey {
    SigningKey::from_bytes(&[7u8; 32])
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
    fn reopen(&mut self) {
        self.api_ = None;
        self.api_ = Some(open(&self.tmp));
    }
}
impl Drop for T {
    fn drop(&mut self) {
        self.api_ = None;
        let _ = std::fs::remove_dir_all(&self.tmp);
    }
}

fn open(tmp: &std::path::Path) -> Api {
    let api = Api::new(tmp.join("worktime.db"), None).unwrap();
    api.set_pack_key(key().verifying_key().to_bytes());
    let now = NaiveDate::from_ymd_opt(2026, 11, 20).unwrap().and_hms_opt(9, 0, 0).unwrap();
    api.set_clock(Box::new(move || now.date()), Box::new(move || now));
    api
}

fn api() -> T {
    let tmp = std::env::temp_dir().join(format!("tokbat-packs-{}-{:x}", std::process::id(), rand::random::<u64>()));
    std::fs::create_dir_all(&tmp).unwrap();
    let t = T { api_: Some(open(&tmp)), tmp };
    t.call("garden_state", json!([]));
    t
}

fn sha(s: &str) -> String {
    Sha256::digest(s.as_bytes()).iter().map(|b| format!("{b:02x}")).collect()
}

/// pack.json text + signature + files, the way tools/make_pack.py writes them.
fn pack(id: &str, version: i64, item_id: &str, file: &str, svg: &str) -> (String, String, Value) {
    let p = json!({"format": 1, "id": id, "version": version, "title": "ของแต่งทดสอบ",
                   "items": [{"id": item_id, "name": "ร่มชายหาด", "cat": "decor", "price": 45, "rarity": "rare", "w": 60.0, "h": 80.0, "file": file, "shelter": true}],
                   "pets": [], "files": {file: sha(svg)}});
    let text = p.to_string();
    let sig = base64::engine::general_purpose::STANDARD.encode(key().sign(text.as_bytes()).to_bytes());
    (text, sig, json!({file: svg}))
}

fn install(t: &T, (text, sig, files): (String, String, Value)) -> Value {
    t.call("pack_install", json!([{"pack": text, "sig": sig, "files": files}]))
}

#[test]
fn a_signed_pack_adds_items_and_survives_a_restart() {
    let mut t = api();
    let r = install(&t, pack("summer", 1, "sun-umbrella", "props/sun-umbrella.svg", SVG));
    assert_eq!(r["ok"], true, "{r}");
    let cat = t.call("garden_catalog", json!([]));
    let it = cat["items"].as_array().unwrap().iter().find(|i| i["id"] == "sun-umbrella").unwrap().clone();
    assert_eq!((it["pack"].as_str(), it["new"].as_bool()), (Some("summer"), Some(true)));
    assert_eq!(t.call("pack_asset", json!(["summer", "props/sun-umbrella.svg"])), json!(SVG));
    assert!(t.api().call("pack_asset", &[json!("summer"), json!("../worktime.db")]).is_err());
    assert_eq!(t.call("shop_buy", json!(["sun-umbrella"]))["ok"], true);
    t.reopen();
    let list = t.call("pack_list", json!([]));
    assert_eq!(list[0]["id"], "summer");
    assert!(t.call("garden_catalog", json!([]))["items"].as_array().unwrap().iter().any(|i| i["id"] == "sun-umbrella"));
}

#[test]
fn a_changed_pack_or_drawing_is_refused() {
    let t = api();
    let (text, sig, files) = pack("summer", 1, "sun-umbrella", "props/sun-umbrella.svg", SVG);
    let cheaper = text.replace("\"price\":45", "\"price\":1");
    assert_ne!(cheaper, text);
    let r = install(&t, (cheaper, sig.clone(), files.clone()));
    assert_eq!(r["ok"], false);
    assert!(r["error"]["message"].as_str().unwrap().contains("ลายเซ็น"));
    let swapped = json!({"props/sun-umbrella.svg": SVG.replace("FFA8B8", "000000")});
    let r = install(&t, (text, sig, swapped));
    assert!(r["error"]["message"].as_str().unwrap().contains("ไม่ตรง"), "{r}");
    assert!(t.call("pack_list", json!([])).as_array().unwrap().is_empty());
}

#[test]
fn a_signed_pack_still_cannot_bring_scripts_or_clash() {
    let t = api();
    let evil = SVG.replace("<path", "<script>alert(1)</script><path");
    let r = install(&t, pack("summer", 1, "sun-umbrella", "props/sun-umbrella.svg", &evil));
    assert!(r["error"]["message"].as_str().unwrap().contains("ไม่ปลอดภัย"), "{r}");
    let r = install(&t, pack("summer", 1, "tree-round", "props/tree-round.svg", SVG));
    assert!(r["error"]["message"].as_str().unwrap().contains("ซ้ำ"), "built-in id: {r}");
    let r = install(&t, pack("summer", 1, "sun-umbrella", "../evil.svg", SVG));
    assert_eq!(r["ok"], false, "path outside the pack");
    let wrong_key = SigningKey::from_bytes(&[9u8; 32]);
    let (text, _, files) = pack("summer", 1, "sun-umbrella", "props/sun-umbrella.svg", SVG);
    let sig = base64::engine::general_purpose::STANDARD.encode(wrong_key.sign(text.as_bytes()).to_bytes());
    assert_eq!(install(&t, (text, sig, files))["ok"], false, "someone else's key");
}

#[test]
fn newer_versions_replace_older_ones_never_the_other_way() {
    let t = api();
    assert_eq!(install(&t, pack("summer", 2, "sun-umbrella", "props/sun-umbrella.svg", SVG))["ok"], true);
    assert_eq!(install(&t, pack("summer", 1, "sun-umbrella", "props/sun-umbrella.svg", SVG))["ok"], false);
    assert_eq!(install(&t, pack("summer", 3, "sun-umbrella", "props/sun-umbrella.svg", SVG))["version"], 3);
    // a second pack can't take the first one's item id
    assert_eq!(install(&t, pack("autumn", 1, "sun-umbrella", "props/sun-umbrella.svg", SVG))["ok"], false);
}

#[test]
fn a_pack_can_add_a_pet_colour() {
    let t = api();
    let file = "pets/cat-pink.svg";
    let p = json!({"format": 1, "id": "pink", "version": 1, "title": "แมวสีชมพู", "items": [],
                   "pets": [{"species": "cat", "color": "pink", "colorName": "ชมพู", "speciesName": "แมว", "w": 60.0, "h": 80.0, "file": file}],
                   "files": {file: sha(SVG)}});
    let text = p.to_string();
    let sig = base64::engine::general_purpose::STANDARD.encode(key().sign(text.as_bytes()).to_bytes());
    assert_eq!(install(&t, (text, sig, json!({file: SVG})))["ok"], true);
    let r = t.call("pet_adopt", json!([{"species": "cat", "color": "pink", "name": "ชมพู่"}]));
    assert_eq!(r["pet"]["color"], "pink", "{r}");
}

fn signed(p: Value, files: Value) -> (String, String, Value) {
    let text = p.to_string();
    let sig = base64::engine::general_purpose::STANDARD.encode(key().sign(text.as_bytes()).to_bytes());
    (text, sig, files)
}

#[test]
fn a_pack_can_add_a_kind_of_animal_that_moves_like_one_the_app_knows() {
    let t = api();
    let file = "pets/goose-white.svg";
    let goose = |gait: &str| json!({"format": 1, "id": "geese", "version": 1, "title": "ห่าน", "items": [],
        "species": [{"id": "goose", "name": "ห่าน", "gait": gait, "size": 0.95, "speed": 36, "rain": "play", "water": "swim"}],
        "pets": [{"species": "goose", "color": "white", "colorName": "ขาว", "speciesName": "ห่าน", "w": 60.0, "h": 80.0, "file": file}],
        "files": {file: sha(SVG)}});
    assert_eq!(install(&t, signed(goose("teleport"), json!({file: SVG})))["ok"], false, "a gait the app can't play");
    assert_eq!(install(&t, signed(goose("waddle"), json!({file: SVG})))["ok"], true);
    let cat = t.call("garden_catalog", json!([]));
    let sp = cat["species"].as_array().unwrap().iter().find(|s| s["id"] == "goose").cloned().unwrap();
    assert_eq!((sp["gait"].as_str(), sp["pack"].as_str()), (Some("waddle"), Some("geese")));
    assert_eq!(t.call("pet_adopt", json!([{"species": "goose", "color": "white", "name": "ห่านน้อย"}]))["pet"]["species"], "goose");
    // a pet of a kind nobody added is refused
    let stray = json!({"format": 1, "id": "stray", "version": 1, "title": "x", "items": [],
        "pets": [{"species": "dragon", "color": "red", "colorName": "แดง", "speciesName": "มังกร", "w": 60.0, "h": 80.0, "file": "pets/dragon-red.svg"}],
        "files": {"pets/dragon-red.svg": sha(SVG)}});
    assert_eq!(install(&t, signed(stray, json!({"pets/dragon-red.svg": SVG})))["ok"], false);
}

#[test]
fn pack_items_can_carry_perches_and_water_but_only_sane_numbers() {
    let t = api();
    let file = "props/birdbath.svg";
    let bath = |perch: Value| json!({"format": 1, "id": "bath", "version": 1, "title": "อ่างนก",
        "items": [{"id": "birdbath", "name": "อ่างน้ำนก", "cat": "decor", "price": 20, "rarity": "common", "w": 60.0, "h": 80.0, "file": file,
                   "perch": perch, "water": [0.5, 0.2, 0.4, 0.1]}],
        "pets": [], "files": {file: sha(SVG)}});
    assert_eq!(install(&t, signed(bath(json!([[0.5, 3.0]])), json!({file: SVG})))["ok"], false, "perch outside the drawing");
    assert_eq!(install(&t, signed(bath(json!([[0.2, 0.1], [0.8, 0.1]])), json!({file: SVG})))["ok"], true);
}
