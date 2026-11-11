//! Content packs: new garden items, pet colours and kinds of animal (that move with a gait the app knows),
//! published on GitHub Pages and installed while online.
//!
//! A pack is pack.json + pack.sig + drawings. pack.sig is an ed25519 signature over the exact bytes of pack.json,
//! and pack.json holds the sha256 of every drawing, so one check covers everything. The page downloads a pack;
//! nothing is written until the signature, the hashes, the ids and every drawing pass. The same checks run again
//! when the app starts, so a pack changed on disk is simply not loaded.
//! Packs live in a "packs" folder next to the database. Built by tools/make_pack.py.

use base64::Engine;
use ed25519_dalek::{Signature, VerifyingKey};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

/// Public half of the key in %USERPROFILE%\.tokbat\pack-signing.key (tools/pack_key.py).
pub const PACK_PUBKEY: [u8; 32] = hex32("ca5d9c73da7e89f068491a4272283fc80f9183b078b6e755e0086ed50ea71fa0");
const CATS: [&str; 7] = ["trees", "plants", "homes", "farm", "toys", "decor", "ground"];
const RARITY: [&str; 3] = ["common", "rare", "special"];
const FLAGS: [&str; 4] = ["shelter", "ground", "bed", "light"];
/// How the app can move an animal (web/js/garden/stage.js). A pack's species must use one of these.
pub const GAITS: [&str; 4] = ["walk", "hop", "fly", "waddle"];
const RAIN: [&str; 2] = ["shelter", "play"];
const WATER: [&str; 3] = ["none", "near", "swim"];
/// Items of a pack show "ของใหม่" this long after it arrives.
pub const NEW_DAYS: i64 = 14;

const fn hex32(s: &str) -> [u8; 32] {
    let b = s.as_bytes();
    let mut out = [0u8; 32];
    let mut i = 0;
    while i < 32 {
        out[i] = (val(b[2 * i]) << 4) | val(b[2 * i + 1]);
        i += 1;
    }
    out
}
const fn val(c: u8) -> u8 {
    match c {
        b'0'..=b'9' => c - b'0',
        b'a'..=b'f' => c - b'a' + 10,
        _ => panic!("bad hex"),
    }
}

pub fn valid_id(s: &str) -> bool {
    let b = s.as_bytes();
    !b.is_empty() && b.len() <= 40 && (b[0].is_ascii_lowercase() || b[0].is_ascii_digit()) && b.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == b'-')
}

pub fn valid_path(p: &str) -> bool {
    let Some(rest) = p.strip_prefix("props/").or_else(|| p.strip_prefix("pets/")) else { return false };
    rest.strip_suffix(".svg").is_some_and(|n| {
        let b = n.as_bytes();
        !b.is_empty() && b.len() <= 60 && (b[0].is_ascii_lowercase() || b[0].is_ascii_digit()) && b.iter().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == b'-')
    })
}

/// Why a drawing can't be shown, or None. Same list as tools/garden/slim.py: nothing that runs code or loads from outside.
pub fn unsafe_svg(text: &str) -> Option<&'static str> {
    let t = text.to_ascii_lowercase();
    for needle in ["<script", "<foreignobject", "<iframe", "<!entity", "<!doctype", "javascript:", "data:text/html", "@import"] {
        if t.contains(needle) {
            return Some(needle);
        }
    }
    let b = t.as_bytes();
    let skip_ws = |mut i: usize| {
        while i < b.len() && b[i].is_ascii_whitespace() {
            i += 1;
        }
        i
    };
    for i in 0..b.len() {
        // on…= event handlers
        if b[i].is_ascii_whitespace() && b[i + 1..].starts_with(b"on") {
            let mut j = i + 3;
            while j < b.len() && b[j].is_ascii_lowercase() {
                j += 1;
            }
            if j > i + 3 && skip_ws(j) < b.len() && b[skip_ws(j)] == b'=' {
                return Some("on…=");
            }
        }
        // href / src that is not a local #reference
        for attr in ["href", "src"] {
            if b[i..].starts_with(attr.as_bytes()) && (i == 0 || !b[i - 1].is_ascii_alphanumeric() || b[i - 1] == b':') {
                let j = skip_ws(i + attr.len());
                if j < b.len() && b[j] == b'=' {
                    let k = skip_ws(j + 1);
                    if k + 1 < b.len() && (b[k] == b'"' || b[k] == b'\'') && b[k + 1] != b'#' {
                        return Some("href/src");
                    }
                }
            }
        }
        if b[i..].starts_with(b"url(") {
            let mut k = skip_ws(i + 4);
            if k < b.len() && (b[k] == b'"' || b[k] == b'\'') {
                k += 1;
            }
            if k < b.len() && b[k] != b'#' {
                return Some("url()");
            }
        }
    }
    None
}

fn sha256(text: &str) -> String {
    Sha256::digest(text.as_bytes()).iter().map(|b| format!("{b:02x}")).collect()
}

fn unit(v: &Value) -> bool {
    v.as_f64().is_some_and(|x| (0.0..=1.0).contains(&x))
}

/// Bird perches ([[x, y], …] as fractions of the drawing) and a water area ([cx, cy, rx, ry]) on an item.
fn spots_ok(it: &Value) -> bool {
    let perch = it.get("perch").is_none_or(|v| v.as_array().is_some_and(|a| a.len() <= 8 && a.iter().all(|p| p.as_array().is_some_and(|q| q.len() == 2 && q.iter().all(unit)))));
    let water = it.get("water").is_none_or(|v| v.as_array().is_some_and(|a| a.len() == 4 && a.iter().all(unit)));
    perch && water
}

/// A new kind of animal: an id, a name and a gait the app knows; size is its share of the pet box.
fn species_ok(sp: &Value) -> bool {
    let txt = |k: &str| sp[k].as_str().unwrap_or("");
    valid_id(txt("id")) && !txt("name").trim().is_empty() && GAITS.contains(&txt("gait"))
        && sp["size"].as_f64().is_some_and(|x| (0.3..=1.2).contains(&x))
        && sp.get("speed").is_none_or(|v| v.as_f64().is_some_and(|x| (10.0..=200.0).contains(&x)))
        && sp.get("rain").is_none_or(|v| RAIN.contains(&v.as_str().unwrap_or("")))
        && sp.get("water").is_none_or(|v| WATER.contains(&v.as_str().unwrap_or("")))
        && sp.as_object().is_some_and(|o| o.keys().all(|k| ["id", "name", "gait", "size", "speed", "rain", "water"].contains(&k.as_str())))
}

/// Everything a pack must be before it touches the disk. `taken` = item ids and pet colours that already exist
/// elsewhere; `species` = kinds of animal that already exist (the pack may add more).
pub fn check(key: &[u8; 32], pack_text: &str, sig_b64: &str, files: &HashMap<String, String>, taken_items: &HashSet<String>, taken_pets: &HashSet<String>, species: &HashSet<String>) -> Result<Value, String> {
    let vk = VerifyingKey::from_bytes(key).map_err(|_| "กุญแจตรวจแพ็กเสีย")?;
    let sig = base64::engine::general_purpose::STANDARD.decode(sig_b64.trim()).map_err(|_| "ลายเซ็นอ่านไม่ได้")?;
    let sig = Signature::from_slice(&sig).map_err(|_| "ลายเซ็นอ่านไม่ได้")?;
    vk.verify_strict(pack_text.as_bytes(), &sig).map_err(|_| "ลายเซ็นไม่ตรง แพ็กนี้ไม่ได้มาจากผู้สร้างแอป")?;
    let p: Value = serde_json::from_str(pack_text).map_err(|_| "pack.json อ่านไม่ได้")?;
    if p["format"] != 1 {
        return Err("แพ็กรุ่นนี้แอปยังอ่านไม่ได้ อัปเดตแอปก่อนนะ".into());
    }
    let id = p["id"].as_str().unwrap_or("");
    if !valid_id(id) || p["version"].as_i64().unwrap_or(0) < 1 || p["title"].as_str().unwrap_or("").trim().is_empty() {
        return Err("ข้อมูลแพ็กไม่ครบ".into());
    }
    let listed: HashMap<String, String> = p["files"].as_object().map(|o| o.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap_or("").to_string())).collect()).unwrap_or_default();
    let mut used = HashSet::new();
    let mut need_file = |f: &Value| -> Result<(), String> {
        let f = f.as_str().unwrap_or("");
        if !valid_path(f) || !listed.contains_key(f) {
            return Err(format!("ไฟล์ {f} ไม่ถูกต้อง"));
        }
        used.insert(f.to_string());
        Ok(())
    };
    let mut ids = HashSet::new();
    for it in p["items"].as_array().cloned().unwrap_or_default() {
        let iid = it["id"].as_str().unwrap_or("");
        if !valid_id(iid) || taken_items.contains(iid) || !ids.insert(iid.to_string()) {
            return Err(format!("รหัสของ {iid} ซ้ำหรือไม่ถูกต้อง"));
        }
        let ok = CATS.contains(&it["cat"].as_str().unwrap_or("")) && RARITY.contains(&it["rarity"].as_str().unwrap_or(""))
            && (1..=500).contains(&it["price"].as_i64().unwrap_or(0)) && !it["name"].as_str().unwrap_or("").trim().is_empty()
            && it["w"].as_f64().is_some_and(|w| w > 0.0 && w < 2000.0) && it["h"].as_f64().is_some_and(|h| h > 0.0 && h < 2000.0)
            && spots_ok(&it)
            && it.as_object().is_some_and(|o| o.keys().all(|k| ["id", "name", "cat", "price", "rarity", "w", "h", "file", "perch", "water"].contains(&k.as_str()) || FLAGS.contains(&k.as_str())));
        if !ok {
            return Err(format!("ข้อมูลของ {iid} ไม่ถูกต้อง"));
        }
        need_file(&it["file"])?;
    }
    let mut kinds = species.clone();
    for sp in p["species"].as_array().cloned().unwrap_or_default() {
        let sid = sp["id"].as_str().unwrap_or("");
        if !species_ok(&sp) || !kinds.insert(sid.to_string()) {
            return Err(format!("ชนิดสัตว์ {sid} ซ้ำหรือไม่ถูกต้อง"));
        }
    }
    for pet in p["pets"].as_array().cloned().unwrap_or_default() {
        let sp = pet["species"].as_str().unwrap_or("");
        let color = pet["color"].as_str().unwrap_or("");
        let key = format!("{sp}-{color}");
        if !kinds.contains(sp) || !valid_id(color) || taken_pets.contains(&key) || pet["colorName"].as_str().unwrap_or("").trim().is_empty() {
            return Err(format!("สัตว์ {key} ซ้ำหรือไม่ถูกต้อง"));
        }
        need_file(&pet["file"])?;
    }
    if ids.is_empty() && p["pets"].as_array().is_none_or(Vec::is_empty) {
        return Err("แพ็กว่าง".into());
    }
    for (path, hash) in &listed {
        let text = files.get(path).ok_or_else(|| format!("ขาดไฟล์ {path}"))?;
        if sha256(text) != *hash {
            return Err(format!("ไฟล์ {path} ไม่ตรงกับที่เซ็นไว้"));
        }
        if let Some(why) = unsafe_svg(text) {
            return Err(format!("ไฟล์ {path} มีสิ่งที่ไม่ปลอดภัย ({why})"));
        }
    }
    if used.len() != listed.len() || files.len() != listed.len() {
        return Err("รายการไฟล์ในแพ็กไม่ตรงกัน".into());
    }
    Ok(p)
}

#[derive(Clone)]
pub struct Installed {
    pub pack: Value,
    pub installed_at: String,
}

type Taken = (HashSet<String>, HashSet<String>, HashSet<String>);

/// Item ids, pet colours (species-color) and species that exist outside the pack being checked.
fn taken(base: &Value, others: &[Installed], skip: &str) -> Taken {
    let ids = |v: &Value, key: &str| -> Vec<String> { v[key].as_array().into_iter().flatten().filter_map(|i| i["id"].as_str().map(String::from)).collect() };
    let pet_keys = |v: &Value| -> Vec<String> { v["pets"].as_array().into_iter().flatten().map(|p| format!("{}-{}", p["species"].as_str().unwrap_or(""), p["color"].as_str().unwrap_or(""))).collect() };
    let (mut items, mut pets, mut species): Taken = (ids(base, "items").into_iter().collect(), pet_keys(base).into_iter().collect(), ids(base, "species").into_iter().collect());
    for o in others.iter().filter(|o| o.pack["id"] != skip) {
        items.extend(ids(&o.pack, "items"));
        pets.extend(pet_keys(&o.pack));
        species.extend(ids(&o.pack, "species"));
    }
    (items, pets, species)
}

/// Checks, then writes the pack into dir/<id> (replacing an older version).
pub fn install(dir: &Path, key: &[u8; 32], base: &Value, others: &[Installed], pack_text: &str, sig: &str, files: &HashMap<String, String>, now: &str) -> Result<Installed, String> {
    let id = serde_json::from_str::<Value>(pack_text).ok().and_then(|v| v["id"].as_str().map(String::from)).unwrap_or_default();
    let (ti, tp, ts) = taken(base, others, &id);
    let p = check(key, pack_text, sig, files, &ti, &tp, &ts)?;
    let version = p["version"].as_i64().unwrap_or(0);
    if let Some(old) = others.iter().find(|o| o.pack["id"] == p["id"]) {
        if old.pack["version"].as_i64().unwrap_or(0) > version {
            return Err("มีแพ็กนี้รุ่นใหม่กว่าอยู่แล้ว".into());
        }
    }
    let target = dir.join(&id);
    let tmp = dir.join(format!(".{id}.part"));
    let _ = std::fs::remove_dir_all(&tmp);
    let write = || -> std::io::Result<()> {
        std::fs::create_dir_all(&tmp)?;
        for (path, text) in files {
            let f = tmp.join(path);
            std::fs::create_dir_all(f.parent().unwrap())?;
            std::fs::write(f, text.as_bytes())?;
        }
        std::fs::write(tmp.join("pack.json"), pack_text.as_bytes())?;
        std::fs::write(tmp.join("pack.sig"), sig.trim().as_bytes())?;
        std::fs::write(tmp.join("installed.json"), json!({"installed_at": now}).to_string())?;
        let _ = std::fs::remove_dir_all(&target);
        std::fs::rename(&tmp, &target)
    };
    write().map_err(|e| {
        let _ = std::fs::remove_dir_all(&tmp);
        format!("บันทึกแพ็กไม่ได้: {e}")
    })?;
    Ok(Installed { pack: p, installed_at: now.to_string() })
}

/// Every pack in dir that still passes every check.
pub fn load_all(dir: &Path, key: &[u8; 32], base: &Value) -> Vec<Installed> {
    let mut out: Vec<Installed> = vec![];
    let Ok(rd) = std::fs::read_dir(dir) else { return out };
    let mut dirs: Vec<PathBuf> = rd.filter_map(Result::ok).map(|e| e.path()).filter(|p| p.is_dir() && !p.file_name().is_some_and(|n| n.to_string_lossy().starts_with('.'))).collect();
    dirs.sort();
    for d in dirs {
        let (Ok(text), Ok(sig)) = (std::fs::read_to_string(d.join("pack.json")), std::fs::read_to_string(d.join("pack.sig"))) else { continue };
        let Ok(meta) = serde_json::from_str::<Value>(&text) else { continue };
        let files: HashMap<String, String> = meta["files"].as_object().map(|o| o.keys().filter(|k| valid_path(k)).filter_map(|k| std::fs::read_to_string(d.join(k)).ok().map(|t| (k.clone(), t))).collect()).unwrap_or_default();
        let id = meta["id"].as_str().unwrap_or("").to_string();
        let (ti, tp, ts) = taken(base, &out, &id);
        if let Ok(p) = check(key, &text, &sig, &files, &ti, &tp, &ts) {
            let at = std::fs::read_to_string(d.join("installed.json")).ok().and_then(|t| serde_json::from_str::<Value>(&t).ok()).and_then(|v| v["installed_at"].as_str().map(String::from)).unwrap_or_default();
            out.push(Installed { pack: p, installed_at: at });
        }
    }
    out
}

/// One drawing of an installed pack (the page shows it inline, like the built-in art).
pub fn asset(dir: &Path, packs: &[Installed], pack_id: &str, path: &str) -> Option<String> {
    let p = packs.iter().find(|p| p.pack["id"] == pack_id)?;
    if !valid_path(path) || p.pack["files"].get(path).is_none() {
        return None;
    }
    std::fs::read_to_string(dir.join(pack_id).join(path)).ok()
}

/// The built-in catalogue plus every installed pack; pack items carry their pack id, when it arrived and "new".
pub fn merge(base: &Value, packs: &[Installed], today: chrono::NaiveDate) -> Value {
    let mut cat = base.clone();
    for p in packs {
        let id = p.pack["id"].clone();
        let new = chrono::NaiveDateTime::parse_from_str(&p.installed_at, "%Y-%m-%d %H:%M:%S").map(|t| (today - t.date()).num_days() < NEW_DAYS).unwrap_or(false);
        let tag = |mut v: Value| {
            v["pack"] = id.clone();
            v["installed_at"] = json!(p.installed_at);
            v["new"] = json!(new);
            v
        };
        let items: Vec<Value> = p.pack["items"].as_array().cloned().unwrap_or_default().into_iter().map(tag).collect();
        let pets: Vec<Value> = p.pack["pets"].as_array().cloned().unwrap_or_default().into_iter().map(tag).collect();
        let species: Vec<Value> = p.pack["species"].as_array().cloned().unwrap_or_default().into_iter().map(tag).collect();
        cat["items"].as_array_mut().unwrap().extend(items);
        cat["pets"].as_array_mut().unwrap().extend(pets);
        if let Some(list) = cat["species"].as_array_mut() {
            list.extend(species);
        }
    }
    cat
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spots_unsafe_svg() {
        assert_eq!(unsafe_svg(r##"<svg><path d="M0 0" fill="url(#g)"/><use href="#a"/></svg>"##), None);
        assert!(unsafe_svg("<svg><script>alert(1)</script></svg>").is_some());
        assert!(unsafe_svg(r#"<svg><rect onload ="x()"/></svg>"#).is_some());
        assert!(unsafe_svg(r#"<svg><image href="https://evil.example/x.png"/></svg>"#).is_some());
        assert!(unsafe_svg(r#"<svg><image xlink:href='http://x'/></svg>"#).is_some());
        assert!(unsafe_svg(r#"<svg><rect fill="url(http://x)"/></svg>"#).is_some());
        assert!(unsafe_svg("<svg><foreignObject/></svg>").is_some());
    }

    #[test]
    fn paths_and_ids() {
        assert!(valid_path("props/sun-umbrella.svg") && valid_path("pets/cat-pink.svg"));
        assert!(!valid_path("../props/x.svg") && !valid_path("props/../x.svg") && !valid_path("props/X.svg") && !valid_path("other/x.svg"));
        assert!(valid_id("spring-2027") && !valid_id("-x") && !valid_id("Spring") && !valid_id(""));
    }
}
