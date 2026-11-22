"""Cryptographic primitives: canonical JSON, SHA-256 hashing and Ed25519 signatures.

Every signature and every block hash in the system is computed over the
*canonical JSON* form of a dictionary, so that all nodes (and the independent
verifier) obtain exactly the same bytes for the same data.
"""

import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def canonical_json(data) -> bytes:
    """Deterministic JSON encoding: sorted keys, no whitespace, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data) -> str:
    return hashlib.sha256(canonical_json(data)).hexdigest()


def generate_private_key_hex() -> str:
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return raw.hex()


def public_key_from_private(private_key_hex: str) -> str:
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def sign(private_key_hex: str, payload: dict) -> str:
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return key.sign(canonical_json(payload)).hex()


def verify_signature(public_key_hex: str, payload: dict, signature_hex: str) -> bool:
    """Return True only if `signature_hex` is a valid signature of `payload` by the key."""
    if not public_key_hex or not signature_hex:
        return False
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), canonical_json(payload))
        return True
    except (ValueError, InvalidSignature):
        return False


def short_key(public_key_hex: str) -> str:
    """Human-friendly fingerprint of a public key, e.g. 'a1b2c3d4…'."""
    return (public_key_hex or "")[:8] + "…"
