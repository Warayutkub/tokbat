"""The key that signs content packs (ed25519).

  python tools/pack_key.py            create the key if there is none, print the public key
  python tools/pack_key.py --public   print the public key of the existing key

The private key lives OUTSIDE the repo: %USERPROFILE%\\.tokbat\\pack-signing.key (or TOKBAT_PACK_KEY).
Back it up somewhere safe. Never commit it. Lose it and packs signed with a new key need a new app version
(the public key is built into the app: PACK_PUBKEY in src-tauri/src/packs.rs).
"""
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def key_path():
    return Path(os.environ.get("TOKBAT_PACK_KEY") or Path.home() / ".tokbat" / "pack-signing.key")


def load():
    p = key_path()
    if not p.exists():
        raise SystemExit(f"no signing key at {p} — run: python tools/pack_key.py")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(p.read_text(encoding="ascii").strip()))


def public_hex(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


if __name__ == "__main__":
    p = key_path()
    if "--public" in sys.argv or p.exists():
        print("public key:", public_hex(load()))
        if p.exists() and "--public" not in sys.argv:
            print(f"(key already exists at {p}; not replaced)")
        sys.exit(0)
    p.parent.mkdir(parents=True, exist_ok=True)
    k = Ed25519PrivateKey.generate()
    raw = k.private_bytes_raw().hex()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(raw + "\n")
    print(f"created {p}")
    print("public key:", public_hex(k))
