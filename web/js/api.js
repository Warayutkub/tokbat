// One way to talk to the Rust side: Tauri's invoke inside the app, or HTTP when the dev server (--serve) runs the page.
export async function call(method, ...args) {
  if (!window.TOKBAT_HTTP && window.__TAURI__) {
    return window.__TAURI__.core.invoke("api", { method, args });
  }
  const res = await fetch(`/api/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(args),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
