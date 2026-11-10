"""Tiny client for the wridge Figma bridge (the tray app must be running, the plugin open on file "work-time")."""
import json
import os
import urllib.request

URL = "http://127.0.0.1:3156/api/tool"
SESSION = os.environ.get("WRIDGE_SESSION", "tokbat-garden")


def call(name, args=None):
    req = urllib.request.Request(URL, data=json.dumps({"name": name, "args": args or {}}).encode(),
                                 headers={"content-type": "application/json", "X-Wridge-Session": SESSION})
    out = json.loads(urllib.request.urlopen(req, timeout=300).read())
    text = "".join(c.get("text", "") for c in out.get("content", []))
    if out.get("isError"):
        raise RuntimeError(f"{name}: {text[:800]}")
    try:
        return json.loads(text)
    except ValueError:
        return text


def open_file(name="work-time"):
    call("use_file", {"file": name})
    info = call("get_document_info")
    if info.get("fileName") != name:
        raise SystemExit(f"Figma file is {info.get('fileName')!r}, expected {name!r}")
    return info
