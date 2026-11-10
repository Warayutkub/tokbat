// ตอกบัตร landing: living mascots (same SVG parts + CSS as the app), reveals, the overnight bar, screenshot tabs.
(() => {
  const root = document.documentElement;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- mascots: inline the split SVG when it comes near the screen, each with its own rhythm ----------
  const svgCache = new Map();
  const loadSvg = (pose) => {
    if (!svgCache.has(pose)) svgCache.set(pose, fetch(`img/chars/${pose}.svg`).then((r) => (r.ok ? r.text() : "")));
    return svgCache.get(pose);
  };
  const hydrate = (el) => {
    el.style.setProperty("--d", `-${(Math.random() * 6).toFixed(2)}s`);
    loadSvg(el.dataset.pose).then((svg) => { el.innerHTML = svg; });
  };
  const mascots = document.querySelectorAll(".mascot[data-pose]");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { io.unobserve(e.target); hydrate(e.target); }
    }, { rootMargin: "300px 0px" });
    mascots.forEach((m) => io.observe(m));
  } else {
    mascots.forEach(hydrate);
  }

  // ---------- hero: start once the fonts are in, so lines never jump ----------
  const count = document.querySelector(".count");
  const bar = document.querySelector(".overnight");
  const callout = document.querySelector(".callout");
  // the number follows the bar: 22:00→00:00 (2 h) in 0.7 s, then 00:00→03:00 (3 h) in 1.0 s
  function countUp(delay = 1100) {
    if (!count || still) return;
    const t0 = performance.now() + delay;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const frame = (now) => {
      const t = now - t0;
      let v;
      if (t < 0) v = 0;
      else if (t < 700) v = 2 * (t / 700);
      else if (t < 700 + 1000) v = 2 + 3 * ease((t - 700) / 1000);
      else v = 5;
      count.textContent = v.toFixed(2);
      bar?.classList.toggle("at-midnight", t > 640 && t < 1000);
      if (t < 1700) requestAnimationFrame(frame);
    };
    count.textContent = "0.00";
    requestAnimationFrame(frame);
  }
  const start = () => { root.classList.add("is-ready"); countUp(); };
  let started = false;
  const go = () => { if (!started) { started = true; start(); } };
  (document.fonts?.ready ?? Promise.resolve()).then(() => setTimeout(go, 30));
  setTimeout(go, 1500); // slow font: go anyway

  // hovering the card plays the moment again
  let replaying = false;
  callout?.addEventListener("pointerenter", () => {
    if (still || replaying || !root.classList.contains("is-ready")) return;
    replaying = true;
    callout.classList.add("is-replaying", "is-rerun");
    requestAnimationFrame(() => requestAnimationFrame(() => {
      callout.classList.remove("is-replaying"); // bars refill straight away (is-rerun drops the load delay)
      countUp(0);
      setTimeout(() => { replaying = false; }, 1900);
    }));
  });

  // ---------- sections reveal as they come in ----------
  const reveals = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && !still) {
    const ro = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("is-in"); ro.unobserve(e.target); }
    }, { rootMargin: "0px 0px -12% 0px", threshold: 0.12 });
    reveals.forEach((el) => ro.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("is-in"));
  }

  // ---------- header: a line once scrolled; nav underlines the section you are in ----------
  const header = document.querySelector(".site-header");
  const onScroll = () => header?.classList.toggle("is-scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  const links = [...document.querySelectorAll(".nav a")];
  const byId = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  if ("IntersectionObserver" in window) {
    const so = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((a) => a.classList.remove("is-active"));
        byId.get(e.target.id)?.classList.add("is-active");
      }
    }, { rootMargin: "-45% 0px -50% 0px" });
    document.querySelectorAll("main section[id]").forEach((s) => so.observe(s));
  }

  // ---------- newest release from GitHub (same idea as the wridge site): version, size, date, direct download ----------
  // The page ships with the current numbers and Releases-page links, so nothing breaks if the API is slow,
  // rate-limited (60 calls/hour per visitor) or there is no release yet.
  const KEY = "tokbat-latest";
  const applyRelease = (r) => {
    document.querySelectorAll("[data-download]").forEach((a) => { a.href = r.url; });
    document.querySelectorAll("[data-version]").forEach((el) => { el.textContent = r.version; });
    document.querySelectorAll("[data-size]").forEach((el) => { el.textContent = r.size; });
    document.querySelectorAll("[data-date]").forEach((el) => { el.textContent = r.date; });
    document.querySelectorAll("[data-date-wrap]").forEach((el) => { el.hidden = !r.date; });
  };
  try { const c = JSON.parse(sessionStorage.getItem(KEY)); if (c) applyRelease(c); } catch { /* storage blocked */ }
  fetch("https://api.github.com/repos/Warayutkub/tokbat/releases/latest", { headers: { Accept: "application/vnd.github+json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((rel) => {
      const exe = rel.assets?.find((a) => /setup\.exe$/i.test(a.name));
      if (!exe) return;
      const when = new Date(rel.published_at || exe.updated_at);
      const r = {
        url: exe.browser_download_url,
        version: rel.tag_name.replace(/^v/, ""),
        size: `${(exe.size / 1048576).toFixed(1)} MB`,
        date: isNaN(when) ? "" : when.toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "numeric" }),
      };
      applyRelease(r);
      try { sessionStorage.setItem(KEY, JSON.stringify(r)); } catch { /* storage blocked */ }
    })
    .catch(() => { /* keep the Releases page link and the numbers in the HTML */ });

  // ---------- screenshot tabs (WAI-ARIA tabs: click, arrows, Home/End) ----------
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  function select(tab, focus = false) {
    for (const t of tabs) {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute("aria-controls"));
      if (!panel) continue;
      if (on && panel.hidden) {
        panel.hidden = false;
        panel.classList.remove("is-entering");
        void panel.offsetWidth; // restart the entrance
        panel.classList.add("is-entering");
      } else if (!on) {
        panel.hidden = true;
      }
    }
    if (focus) tab.focus();
    tab.scrollIntoView({ block: "nearest", inline: "nearest", behavior: still ? "auto" : "smooth" });
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => select(t));
    t.addEventListener("keydown", (e) => {
      const n = tabs.length;
      const go = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: n - 1 }[e.key];
      if (go === undefined) return;
      e.preventDefault();
      select(tabs[(go + n) % n], true);
    });
  });
})();
