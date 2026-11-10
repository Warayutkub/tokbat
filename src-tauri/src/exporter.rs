//! Report HTML → PDF / PNG with Microsoft Edge running headless. Works offline.
//! PNG takes two passes (same as wridge): one to measure the page height, one to take the screenshot.

use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};
use std::time::{Duration, Instant};

const FONTS: [(&str, &[u8]); 3] = [
    ("IBMPlexSansThaiLooped-Regular.ttf", include_bytes!("../../web/fonts/IBMPlexSansThaiLooped-Regular.ttf")),
    ("IBMPlexSansThaiLooped-Medium.ttf", include_bytes!("../../web/fonts/IBMPlexSansThaiLooped-Medium.ttf")),
    ("IBMPlexSansThaiLooped-SemiBold.ttf", include_bytes!("../../web/fonts/IBMPlexSansThaiLooped-SemiBold.ttf")),
];
const PAGE_WIDTH: u32 = 794; // A4 at 96 dpi

pub fn find_edge() -> Option<PathBuf> {
    let mut c = vec![];
    for var in ["ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"] {
        if let Ok(base) = std::env::var(var) {
            c.push(PathBuf::from(base).join("Microsoft/Edge/Application/msedge.exe"));
        }
    }
    c.into_iter().find(|p| p.is_file())
}

/// A folder with report.html and the fonts it needs (relative "fonts/" links).
struct Workdir(PathBuf);
impl Workdir {
    fn new(html: &str) -> Result<Self, String> {
        let dir = std::env::temp_dir().join(format!("tokbat-export-{}-{}", std::process::id(), rand::random::<u32>()));
        std::fs::create_dir_all(dir.join("fonts")).map_err(|e| e.to_string())?;
        for (name, bytes) in FONTS {
            std::fs::write(dir.join("fonts").join(name), bytes).map_err(|e| e.to_string())?;
        }
        std::fs::write(dir.join("report.html"), html).map_err(|e| e.to_string())?;
        Ok(Self(dir))
    }
    fn url(&self) -> String {
        format!("file:///{}", self.0.join("report.html").to_string_lossy().replace('\\', "/"))
    }
}
impl Drop for Workdir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// One headless run with its own fresh profile and none of the WebView2 settings our window passes down.
fn run_edge(edge: &Path, work: &Path, args: &[String]) -> Result<Output, String> {
    let mut cmd = Command::new(edge);
    for (k, _) in std::env::vars_os() {
        let k = k.to_string_lossy().to_string();
        if k.starts_with("WEBVIEW2_") || k.starts_with("CHROME_") {
            cmd.env_remove(&k);
        }
    }
    cmd.args(["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--run-all-compositor-stages-before-draw", "--allow-file-access-from-files"])
        // a profile per run: a second run on the same profile is handed to the first (still exiting) Edge and ignored
        .arg(format!("--user-data-dir={}", work.join(format!("profile-{}", rand::random::<u32>())).display()))
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // no console window
    }
    cmd.output().map_err(|e| format!("เปิด Microsoft Edge ไม่ได้ ({e})"))
}

/// Edge may hand the job to a background process and return early: wait for the file to be complete.
fn wait_for(file: &Path, check: impl Fn(&[u8]) -> bool) -> bool {
    let deadline = Instant::now() + Duration::from_secs(60);
    let mut last = 0;
    while Instant::now() < deadline {
        if let Ok(bytes) = std::fs::read(file) {
            if !bytes.is_empty() && bytes.len() == last && check(&bytes) {
                return true;
            }
            last = bytes.len();
        }
        std::thread::sleep(Duration::from_millis(250));
    }
    false
}

pub fn export(html: &str, target: &Path, format: &str) -> Result<PathBuf, String> {
    let edge = find_edge().ok_or("ไม่พบ Microsoft Edge ในเครื่อง จึงสร้างไฟล์ไม่ได้")?;
    let work = Workdir::new(html)?;
    let out = work.0.join(if format == "png" { "report.png" } else { "report.pdf" });
    if format == "png" {
        // pass 1: how tall the page is (the page writes it into the DOM once fonts are in)
        let dom = run_edge(&edge, &work.0, &["--virtual-time-budget=8000".into(), format!("--window-size={PAGE_WIDTH},1123"), "--dump-dom".into(), work.url()])?;
        let text = String::from_utf8_lossy(&dom.stdout);
        let height: u32 = text.split("data-height=\"").nth(1).and_then(|s| s.split('"').next()).and_then(|s| s.parse().ok()).unwrap_or(1123).clamp(400, 16000);
        run_edge(&edge, &work.0, &["--virtual-time-budget=8000".into(), format!("--window-size={PAGE_WIDTH},{height}"), "--force-device-scale-factor=2".into(), format!("--screenshot={}", out.display()), work.url()])?;
        if !wait_for(&out, |b| b.ends_with(&[0xAE, 0x42, 0x60, 0x82])) {
            return Err("สร้างรูป PNG ไม่สำเร็จ ลองบันทึกใหม่อีกครั้ง".into());
        }
    } else {
        run_edge(&edge, &work.0, &["--virtual-time-budget=8000".into(), "--no-pdf-header-footer".into(), format!("--print-to-pdf={}", out.display()), work.url()])?;
        if !wait_for(&out, |b| b.len() > 1024 && b[b.len().saturating_sub(1024)..].windows(5).any(|w| w == b"%%EOF")) {
            return Err("สร้าง PDF ไม่สำเร็จ ลองบันทึกใหม่อีกครั้ง".into());
        }
    }
    if let Some(dir) = target.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    std::fs::copy(&out, target).map_err(|e| format!("บันทึกไฟล์ไม่สำเร็จ ({e}) ลองเลือกโฟลเดอร์อื่น"))?;
    Ok(target.to_path_buf())
}
