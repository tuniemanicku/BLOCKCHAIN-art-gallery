"""Signed operations (transactions) and blocks - the data format of the blockchain.

A signed operation looks like this:

    {
      "payload": {
        "op_id":         "6f1c...",          unique operation id (replay protection)
        "type":          "TRANSFER",         REGISTER_USER | ISSUE | TRANSFER | REDEEM | SET_PRICE
        "signer":        "<public key hex>", key that authorises the operation
        "asset_id":      "3b9e...",          (not used by REGISTER_USER)
        "asset_version": 2,                  state of the asset the operation is based on
        "data":          {...},              type specific fields, see builders below
        "created_at":    "2026-11-22T10:00:00+00:00"
      },
      "signature": "<Ed25519 signature of canonical_json(payload)>"
    }

A block wraps exactly one entry of the replicated log:

    {
      "index": 5, "term": 2, "prev_hash": "...", "timestamp": "...",
      "leader": "B", "kind": "OPERATION" | "LEADER" | "GENESIS",
      "operation": {...signed operation...} | null,
      "info": {...}                          (genesis data / leader notes)
      "hash": sha256(canonical_json(all the fields above))
    }
"""

import uuid
from datetime import datetime, timezone

from .config import ADMIN_WALLET_NAME
from .crypto import sha256_hex, sign

# ----------------------------------------------------------------------------
# Operation types and asset statuses
# ----------------------------------------------------------------------------
REGISTER_USER = "REGISTER_USER"
ISSUE = "ISSUE"
TRANSFER = "TRANSFER"
REDEEM = "REDEEM"
SET_PRICE = "SET_PRICE"

ACTIVE = "ACTIVE"
REDEEMED = "REDEEMED"

# Block kinds
GENESIS = "GENESIS"
LEADER = "LEADER"
OPERATION = "OPERATION"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ----------------------------------------------------------------------------
# Building operations (client side)
# ----------------------------------------------------------------------------
def _payload(op_type: str, signer: str, asset_id=None, asset_version=None, data=None) -> dict:
    return {
        "op_id": uuid.uuid4().hex,
        "type": op_type,
        "signer": signer,
        "asset_id": asset_id,
        "asset_version": asset_version,
        "data": data or {},
        "created_at": utc_now(),
    }


def register_user_payload(public_key: str, name: str) -> dict:
    return _payload(REGISTER_USER, signer=public_key, data={"name": name})


def issue_payload(admin_public_key: str, recipient: str, title: str, author: str,
                  accepted_on: str, price: int) -> dict:
    return _payload(
        ISSUE,
        signer=admin_public_key,
        asset_id=uuid.uuid4().hex,
        asset_version=0,
        data={
            "recipient": recipient,
            "title": title,
            "author": author,
            "accepted_on": accepted_on,
            "price": price,
        },
    )


def transfer_payload(owner_public_key: str, asset_id: str, asset_version: int, recipient: str) -> dict:
    return _payload(TRANSFER, signer=owner_public_key, asset_id=asset_id,
                    asset_version=asset_version, data={"recipient": recipient})


def redeem_payload(owner_public_key: str, asset_id: str, asset_version: int) -> dict:
    return _payload(REDEEM, signer=owner_public_key, asset_id=asset_id, asset_version=asset_version)


def set_price_payload(admin_public_key: str, asset_id: str, asset_version: int, price: int) -> dict:
    return _payload(SET_PRICE, signer=admin_public_key, asset_id=asset_id,
                    asset_version=asset_version, data={"price": price})


def signed(payload: dict, private_key_hex) -> dict:
    """Attach a signature. `private_key_hex=None` produces an UNSIGNED operation (for tests)."""
    signature = sign(private_key_hex, payload) if private_key_hex else ""
    return {"payload": payload, "signature": signature}


# ----------------------------------------------------------------------------
# Blocks (node side)
# ----------------------------------------------------------------------------
HASHED_BLOCK_FIELDS = ("index", "term", "prev_hash", "timestamp", "leader", "kind", "operation", "info")


def block_hash(block: dict) -> str:
    return sha256_hex({field: block.get(field) for field in HASHED_BLOCK_FIELDS})


def make_block(index: int, term: int, prev_hash: str, leader: str, kind: str,
               operation=None, info=None, timestamp=None) -> dict:
    block = {
        "index": index,
        "term": term,
        "prev_hash": prev_hash,
        "timestamp": timestamp or utc_now(),
        "leader": leader,
        "kind": kind,
        "operation": operation,
        "info": info or {},
    }
    block["hash"] = block_hash(block)
    return block


def genesis_block(cluster_config) -> dict:
    """Identical on every node: derived only from the shared cluster configuration."""
    return make_block(
        index=0,
        term=0,
        prev_hash="0" * 64,
        leader="-",
        kind=GENESIS,
        info={
            "cluster_name": cluster_config.cluster_name,
            "admin_public_key": cluster_config.admin_public_key,
            "admin_name": ADMIN_WALLET_NAME,
        },
        timestamp=cluster_config.created_at,
    )
