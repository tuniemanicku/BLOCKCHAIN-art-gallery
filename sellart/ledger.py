"""Deterministic state machine of the gallery: users, assets and their history.

The ledger state is *never stored as the source of truth*. Every node computes it
by replaying the blocks of its own copy of the blockchain, in order. Because the
rules below are deterministic, every node that holds the same chain computes the
same state.

`validate()` returns a human readable reason when an operation must be rejected.
"""

import copy
import re

from . import operations as ops
from .crypto import verify_signature

MAX_NAME_LENGTH = 32
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class OperationRejected(Exception):
    """Raised when an operation breaks a rule of the ledger."""


class Ledger:
    def __init__(self, genesis: dict):
        info = genesis["info"]
        self.admin_key = info["admin_public_key"]
        self.users = {self.admin_key: info["admin_name"]}  # public key -> display name
        self.assets = {}          # asset id -> asset state (dict)
        self.history = {}         # asset id -> list of history entries
        self.executed_ops = {}    # op id -> block index (replay protection)

    def copy(self) -> "Ledger":
        return copy.deepcopy(self)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def name_of(self, public_key: str) -> str:
        return self.users.get(public_key, "unknown")

    def asset_view(self, asset_id: str):
        asset = self.assets.get(asset_id)
        if asset is None:
            return None
        return {**asset, "owner_name": self.name_of(asset["owner"])}

    def users_view(self) -> list:
        return [{"name": name, "public_key": key, "is_admin": key == self.admin_key}
                for key, name in self.users.items()]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, operation: dict) -> None:
        """Raise OperationRejected if the signed operation cannot be applied now."""
        payload = operation.get("payload") or {}
        op_type = payload.get("type")
        signer = payload.get("signer")
        op_id = payload.get("op_id")

        if not op_id:
            raise OperationRejected("operation has no op_id")
        if not operation.get("signature"):
            raise OperationRejected("missing signature - the operation is not authorised")
        if not verify_signature(signer, payload, operation["signature"]):
            raise OperationRejected("invalid signature - it was not created with the signer's private key")
        if op_id in self.executed_ops:
            raise OperationRejected(
                f"replay detected - operation {op_id[:8]}... was already executed in block "
                f"#{self.executed_ops[op_id]}")

        checks = {
            ops.REGISTER_USER: self._check_register_user,
            ops.ISSUE: self._check_issue,
            ops.TRANSFER: self._check_transfer,
            ops.REDEEM: self._check_redeem,
            ops.SET_PRICE: self._check_set_price,
        }
        if op_type not in checks:
            raise OperationRejected(f"unknown operation type: {op_type}")
        checks[op_type](payload)

    def _check_register_user(self, payload):
        name = str(payload["data"].get("name", "")).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise OperationRejected(f"user name must have 1-{MAX_NAME_LENGTH} characters")
        if payload["signer"] in self.users:
            raise OperationRejected("this public key is already registered")
        if name.lower() in (n.lower() for n in self.users.values()):
            raise OperationRejected(f"user name '{name}' is already taken")

    def _check_issue(self, payload):
        data = payload["data"]
        if payload["signer"] != self.admin_key:
            raise OperationRejected("only the gallery administrator can issue assets")
        if not payload.get("asset_id"):
            raise OperationRejected("asset id is missing")
        if payload["asset_id"] in self.assets:
            raise OperationRejected("an asset with this id already exists")
        if data.get("recipient") not in self.users or data.get("recipient") == self.admin_key:
            raise OperationRejected("recipient is not a registered gallery client")
        if not str(data.get("title", "")).strip() or not str(data.get("author", "")).strip():
            raise OperationRejected("title and original author are required")
        if not DATE_PATTERN.match(str(data.get("accepted_on", ""))):
            raise OperationRejected("acceptance date must have the format YYYY-MM-DD")
        self._check_price(data.get("price"))

    def _check_transfer(self, payload):
        asset = self._check_owner_action(payload)
        recipient = payload["data"].get("recipient")
        if recipient not in self.users or recipient == self.admin_key:
            raise OperationRejected("recipient is not a registered gallery client")
        if recipient == asset["owner"]:
            raise OperationRejected("recipient already owns this asset")

    def _check_redeem(self, payload):
        self._check_owner_action(payload)

    def _check_set_price(self, payload):
        if payload["signer"] != self.admin_key:
            raise OperationRejected("only the gallery administrator can change the price")
        self._check_asset_state(payload)
        self._check_price(payload["data"].get("price"))

    def _check_owner_action(self, payload) -> dict:
        asset = self._check_asset_state(payload)
        if payload["signer"] != asset["owner"]:
            raise OperationRejected(
                f"{self.name_of(payload['signer'])} is not the current owner "
                f"(owner: {self.name_of(asset['owner'])})")
        return asset

    def _check_asset_state(self, payload) -> dict:
        asset = self.assets.get(payload.get("asset_id"))
        if asset is None:
            raise OperationRejected("asset does not exist")
        if asset["status"] == ops.REDEEMED:
            raise OperationRejected("asset is already REDEEMED - it cannot be transferred or redeemed again")
        if payload.get("asset_version") != asset["version"]:
            raise OperationRejected(
                f"conflict - the operation was prepared for asset version {payload.get('asset_version')}, "
                f"but the asset is already at version {asset['version']} (another operation won)")
        return asset

    @staticmethod
    def _check_price(price):
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            raise OperationRejected("price must be a non-negative whole number (PLN)")

    # ------------------------------------------------------------------
    # Applying blocks
    # ------------------------------------------------------------------
    def apply_block(self, block: dict) -> None:
        """Apply one block. Only OPERATION blocks change the state."""
        if block["kind"] != ops.OPERATION:
            return
        operation = block["operation"]
        self.validate(operation)
        payload = operation["payload"]
        handler = {
            ops.REGISTER_USER: self._apply_register_user,
            ops.ISSUE: self._apply_issue,
            ops.TRANSFER: self._apply_transfer,
            ops.REDEEM: self._apply_redeem,
            ops.SET_PRICE: self._apply_set_price,
        }[payload["type"]]
        handler(payload, block)
        self.executed_ops[payload["op_id"]] = block["index"]

    def _apply_register_user(self, payload, block):
        self.users[payload["signer"]] = payload["data"]["name"].strip()

    def _apply_issue(self, payload, block):
        data = payload["data"]
        asset_id = payload["asset_id"]
        self.assets[asset_id] = {
            "asset_id": asset_id,
            "title": data["title"].strip(),
            "author": data["author"].strip(),
            "accepted_on": data["accepted_on"],
            "price": data["price"],
            "owner": data["recipient"],
            "status": ops.ACTIVE,
            "version": 1,
            "issued_at": block["timestamp"],
            "redeemed_value": None,
        }
        self._record(payload, block, previous_owner=None, new_owner=data["recipient"])

    def _apply_transfer(self, payload, block):
        asset = self.assets[payload["asset_id"]]
        previous_owner = asset["owner"]
        asset["owner"] = payload["data"]["recipient"]
        asset["version"] += 1
        self._record(payload, block, previous_owner=previous_owner, new_owner=asset["owner"])

    def _apply_redeem(self, payload, block):
        asset = self.assets[payload["asset_id"]]
        asset["status"] = ops.REDEEMED
        asset["redeemed_value"] = asset["price"]
        asset["version"] += 1
        self._record(payload, block, previous_owner=asset["owner"], new_owner=None,
                     note=f"paid out {asset['price']} PLN")

    def _apply_set_price(self, payload, block):
        asset = self.assets[payload["asset_id"]]
        old_price = asset["price"]
        asset["price"] = payload["data"]["price"]
        asset["version"] += 1
        self._record(payload, block, previous_owner=None, new_owner=None,
                     note=f"price {old_price} -> {asset['price']} PLN")

    def _record(self, payload, block, previous_owner, new_owner, note=""):
        self.history.setdefault(payload["asset_id"], []).append({
            "op_id": payload["op_id"],
            "type": payload["type"],
            "asset_id": payload["asset_id"],
            "from": previous_owner,
            "from_name": self.name_of(previous_owner) if previous_owner else None,
            "to": new_owner,
            "to_name": self.name_of(new_owner) if new_owner else None,
            "signer_name": self.name_of(payload["signer"]),
            "block_index": block["index"],
            "block_hash": block["hash"],
            "timestamp": block["timestamp"],
            "note": note,
        })
