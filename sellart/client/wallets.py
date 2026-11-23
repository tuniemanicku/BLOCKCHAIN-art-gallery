"""User-side wallets (accounts).

A wallet is a small JSON file holding a user's Ed25519 key pair. It lives only on
the user's side (runtime/client/wallets/) and the PRIVATE key inside it is
encrypted with the user's password:

    key  = scrypt(password, salt)          (slow on purpose - hard to brute-force)
    file = AES-256-GCM(key, private key)   (any change of the file is detected)

Logging in = decrypting the private key with the password. Nodes never receive
private keys - they only learn the PUBLIC key when the user registers.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .. import operations as ops
from ..config import ADMIN_WALLET_NAME, wallets_dir
from ..crypto import generate_private_key_hex, public_key_from_private

MIN_PASSWORD_LENGTH = 4


class WrongPassword(Exception):
    pass


@dataclass(frozen=True)
class Wallet:
    """A wallet as stored on disk - the private key is still encrypted (locked)."""
    name: str
    public_key: str
    path: Path

    @property
    def is_admin(self) -> bool:
        return self.name == ADMIN_WALLET_NAME

    def unlock(self, password: str) -> "UnlockedWallet":
        data = json.loads(self.path.read_text(encoding="utf-8"))
        key = _derive_key(password, bytes.fromhex(data["salt"]))
        try:
            private_key = AESGCM(key).decrypt(bytes.fromhex(data["nonce"]),
                                              bytes.fromhex(data["encrypted_private_key"]), None)
        except InvalidTag:
            raise WrongPassword("wrong password") from None
        return UnlockedWallet(self.name, self.public_key, self.path, private_key.decode())


@dataclass(frozen=True)
class UnlockedWallet(Wallet):
    """A logged-in wallet: the private key is available in memory and can sign."""
    private_key: str = ""

    def sign(self, payload: dict) -> dict:
        return ops.signed(payload, self.private_key)


def _derive_key(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1).derive(password.encode("utf-8"))


def _file_for(name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "user"
    return wallets_dir() / f"{slug}.json"


def create_wallet(name: str, password: str) -> UnlockedWallet:
    """Generate a new key pair and save it encrypted with the password."""
    name = name.strip()
    if not name:
        raise ValueError("enter a user name")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"the password must have at least {MIN_PASSWORD_LENGTH} characters")
    path = _file_for(name)
    if path.exists():
        raise ValueError(f"an account named '{name}' already exists on this computer")

    private_key = generate_private_key_hex()
    public_key = public_key_from_private(private_key)
    salt, nonce = os.urandom(16), os.urandom(12)
    encrypted = AESGCM(_derive_key(password, salt)).encrypt(nonce, private_key.encode(), None)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "name": name,
        "public_key": public_key,
        "kdf": "scrypt(n=16384,r=8,p=1)",
        "cipher": "AES-256-GCM",
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "encrypted_private_key": encrypted.hex(),
    }, indent=2), encoding="utf-8")
    return UnlockedWallet(name, public_key, path, private_key)


def delete_wallet(wallet: Wallet) -> None:
    """Used when a registration is rejected (e.g. the name is taken on the blockchain)."""
    wallet.path.unlink(missing_ok=True)


def load_wallets() -> list:
    wallets = []
    for path in sorted(wallets_dir().glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        wallets.append(Wallet(data["name"], data["public_key"], path))
    return wallets


def find_wallet(name: str):
    return next((w for w in load_wallets() if w.name == name), None)
