"""User-side wallets.

A wallet is a small JSON file holding a user's Ed25519 key pair. It lives only on
the user's side (runtime/client/wallets/). Nodes never receive private keys - they
only learn the PUBLIC key when the user registers, and verify signatures with it.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .. import operations as ops
from ..config import ADMIN_WALLET_NAME, wallets_dir
from ..crypto import generate_private_key_hex, public_key_from_private


@dataclass(frozen=True)
class Wallet:
    name: str
    public_key: str
    private_key: str
    path: Path

    @property
    def is_admin(self) -> bool:
        return self.name == ADMIN_WALLET_NAME

    def sign(self, payload: dict) -> dict:
        return ops.signed(payload, self.private_key)


def _file_for(name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return wallets_dir() / f"{slug}.json"


def create_wallet(name: str) -> Wallet:
    path = _file_for(name)
    if path.exists():
        raise ValueError(f"A wallet named '{name}' already exists: {path}")
    private_key = generate_private_key_hex()
    wallet = Wallet(name, public_key_from_private(private_key), private_key, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "public_key": wallet.public_key,
                                "private_key": private_key}, indent=2), encoding="utf-8")
    return wallet


def load_wallets() -> list:
    wallets = []
    for path in sorted(wallets_dir().glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        wallets.append(Wallet(data["name"], data["public_key"], data["private_key"], path))
    return wallets


def find_wallet(name: str):
    return next((w for w in load_wallets() if w.name == name), None)
