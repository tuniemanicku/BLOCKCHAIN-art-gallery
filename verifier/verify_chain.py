"""Independent verifier of the Sellart blockchain (requirement R10).

This program deliberately does NOT import any code of the Sellart application.
It re-implements, from the documented data format, everything needed to check
the chain on its own:

  1. downloads the committed blocks from every node separately (each node serves
     its OWN copy from its OWN database) - or reads a previously exported file,
  2. recomputes every block hash and checks the hash links (tamper evidence),
  3. checks the Ed25519 signature of every operation (authorisation),
  4. replays ownership rules to compute owner and status of every asset,
  5. compares the results of all sources.

Usage:
  python verifier/verify_chain.py                         all assets, all nodes from runtime/cluster.json
  python verifier/verify_chain.py --asset 3b9e...         one asset
  python verifier/verify_chain.py --node http://127.0.0.1:8002 --node http://127.0.0.1:8003
  python verifier/verify_chain.py --export chain.json     save node A's chain to a file
  python verifier/verify_chain.py --file chain.json       verify an exported file offline
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

RUNTIME_DIR = Path(os.environ.get("SELLART_HOME", Path(__file__).resolve().parent.parent / "runtime"))
DEFAULT_CLUSTER_FILE = RUNTIME_DIR / "cluster.json"
BLOCK_FIELDS = ("index", "term", "prev_hash", "timestamp", "leader", "kind", "operation", "info")


# --------------------------------------------------------------------------
# Format primitives (independent re-implementation)
# --------------------------------------------------------------------------
def canonical(data) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_block_hash(block: dict) -> str:
    return hashlib.sha256(canonical({f: block.get(f) for f in BLOCK_FIELDS})).hexdigest()


def signature_is_valid(public_key_hex: str, payload: dict, signature_hex: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(signature_hex), canonical(payload))
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


# --------------------------------------------------------------------------
# Verification and replay
# --------------------------------------------------------------------------
class ChainError(Exception):
    pass


def verify_and_replay(blocks: list) -> dict:
    """Return {"assets": {...}, "users": {...}, "tip": hash, "height": n} or raise ChainError."""
    if not blocks or blocks[0].get("kind") != "GENESIS":
        raise ChainError("chain does not start with a genesis block")

    admin_key = blocks[0]["info"]["admin_public_key"]
    users = {admin_key: blocks[0]["info"]["admin_name"]}
    assets = {}
    seen_op_ids = set()

    for position, block in enumerate(blocks):
        if block["index"] != position:
            raise ChainError(f"block #{position}: wrong index {block['index']}")
        if compute_block_hash(block) != block["hash"]:
            raise ChainError(f"block #{position}: hash mismatch - the block was modified")
        if position > 0 and block["prev_hash"] != blocks[position - 1]["hash"]:
            raise ChainError(f"block #{position}: broken link to the previous block")
        if block["kind"] != "OPERATION":
            continue

        operation = block["operation"]
        payload, signature = operation["payload"], operation.get("signature", "")
        signer, kind, asset_id = payload["signer"], payload["type"], payload.get("asset_id")
        where = f"block #{position} ({kind})"

        if not signature_is_valid(signer, payload, signature):
            raise ChainError(f"{where}: invalid signature")
        if payload["op_id"] in seen_op_ids:
            raise ChainError(f"{where}: operation replayed")
        seen_op_ids.add(payload["op_id"])

        if kind == "REGISTER_USER":
            users[signer] = payload["data"]["name"]
        elif kind == "ISSUE":
            if signer != admin_key:
                raise ChainError(f"{where}: issued by someone other than the gallery admin")
            assets[asset_id] = {"owner": payload["data"]["recipient"], "status": "ACTIVE",
                                "title": payload["data"]["title"], "version": 1,
                                "operations": 1}
        else:
            asset = assets.get(asset_id)
            if asset is None:
                raise ChainError(f"{where}: unknown asset")
            if asset["status"] != "ACTIVE":
                raise ChainError(f"{where}: operation on a REDEEMED asset")
            if payload.get("asset_version") != asset["version"]:
                raise ChainError(f"{where}: stale asset version")
            if kind in ("TRANSFER", "REDEEM") and signer != asset["owner"]:
                raise ChainError(f"{where}: signed by someone who is not the owner")
            if kind == "SET_PRICE" and signer != admin_key:
                raise ChainError(f"{where}: price changed by someone other than the admin")
            if kind == "TRANSFER":
                asset["owner"] = payload["data"]["recipient"]
            elif kind == "REDEEM":
                asset["status"] = "REDEEMED"
            asset["version"] += 1
            asset["operations"] += 1

    return {"assets": assets, "users": users, "tip": blocks[-1]["hash"], "height": len(blocks)}


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def fetch_chain(url: str) -> list:
    response = requests.get(f"{url.rstrip('/')}/chain", timeout=3)
    response.raise_for_status()
    return response.json()["blocks"]


def default_node_urls() -> list:
    if not DEFAULT_CLUSTER_FILE.exists():
        sys.exit("No --node/--file given and runtime/cluster.json not found.")
    return list(json.loads(DEFAULT_CLUSTER_FILE.read_text(encoding="utf-8"))["nodes"].values())


def describe(asset_id: str, asset: dict, users: dict) -> str:
    owner = users.get(asset["owner"], asset["owner"][:8] + "...")
    return (f"asset {asset_id}  '{asset['title']}'  owner = {owner}  status = {asset['status']}  "
            f"({asset['operations']} operations)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent verifier of the Sellart blockchain")
    parser.add_argument("--node", action="append", help="node base URL (repeatable)")
    parser.add_argument("--file", action="append", help="exported chain JSON file (repeatable)")
    parser.add_argument("--asset", help="show only this asset id")
    parser.add_argument("--export", help="save the chain of the first source to this file and exit")
    args = parser.parse_args()

    sources = []  # (label, loader)
    for path in args.file or []:
        sources.append((f"file {path}", lambda p=path: json.loads(Path(p).read_text(encoding="utf-8"))))
    for url in args.node or ([] if args.file else default_node_urls()):
        sources.append((f"node {url}", lambda u=url: fetch_chain(u)))

    if args.export:
        label, loader = sources[0]
        Path(args.export).write_text(json.dumps(loader(), indent=2), encoding="utf-8")
        print(f"Chain from {label} saved to {args.export}")
        return 0

    results = {}
    for label, loader in sources:
        print(f"\n=== {label}")
        try:
            state = verify_and_replay(loader())
        except requests.RequestException:
            print("    UNREACHABLE")
            continue
        except ChainError as error:
            print(f"    VERIFICATION FAILED: {error}")
            continue
        print(f"    chain OK: {state['height']} blocks, all hashes and signatures valid")
        print(f"    tip hash: {state['tip']}")
        shown = {args.asset: state["assets"].get(args.asset)} if args.asset else state["assets"]
        for asset_id, asset in shown.items():
            print("    " + (describe(asset_id, asset, state["users"]) if asset
                           else f"asset {asset_id} not found"))
        results[label] = {aid: (a["owner"], a["status"]) if a else None for aid, a in shown.items()}

    print()
    if len(results) < 2:
        print("Only one verified source - nothing to compare.")
    elif len({json.dumps(r, sort_keys=True) for r in results.values()}) == 1:
        print(f"RESULT: all {len(results)} verified sources report the SAME owner and status.")
    else:
        print("RESULT: sources DISAGREE (a node may still be synchronising - run again).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
