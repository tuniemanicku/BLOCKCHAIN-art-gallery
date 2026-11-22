"""Locations of runtime files and the shared cluster configuration.

Runtime layout (everything below is created by `python manage.py reset`):

    runtime/
      cluster.json            public cluster description (node addresses, admin PUBLIC key)
      node-A/node.db          persistent state of node A (its own copy of the blockchain)
      node-B/node.db          ...
      node-C/node.db          ...
      client/wallets/*.json   user-side wallets with PRIVATE keys (never sent to any node)

The runtime directory can be changed with the SELLART_HOME environment variable
(used by the automated acceptance test to run an isolated cluster).
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_NODES = {
    "A": "http://127.0.0.1:8001",
    "B": "http://127.0.0.1:8002",
    "C": "http://127.0.0.1:8003",
}

ADMIN_WALLET_NAME = "Gallery Admin"


def runtime_dir() -> Path:
    return Path(os.environ.get("SELLART_HOME", PROJECT_ROOT / "runtime"))


def cluster_file() -> Path:
    return runtime_dir() / "cluster.json"


def node_dir(node_id: str) -> Path:
    return runtime_dir() / f"node-{node_id}"


def wallets_dir() -> Path:
    return runtime_dir() / "client" / "wallets"


@dataclass(frozen=True)
class ClusterConfig:
    cluster_name: str
    created_at: str
    admin_public_key: str
    nodes: dict  # node id -> base URL

    @property
    def node_ids(self) -> list:
        return sorted(self.nodes)

    def peers_of(self, node_id: str) -> dict:
        return {nid: url for nid, url in self.nodes.items() if nid != node_id}

    def port_of(self, node_id: str) -> int:
        return int(self.nodes[node_id].rsplit(":", 1)[1])


def load_cluster_config() -> ClusterConfig:
    path = cluster_file()
    if not path.exists():
        raise SystemExit(
            f"Cluster configuration not found: {path}\n"
            "Run `python manage.py reset` first to create a clean environment."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return ClusterConfig(**data)


def save_cluster_config(admin_public_key: str, nodes: dict = None) -> ClusterConfig:
    config = ClusterConfig(
        cluster_name="sellart-gallery",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        admin_public_key=admin_public_key,
        nodes=dict(nodes or DEFAULT_NODES),
    )
    cluster_file().parent.mkdir(parents=True, exist_ok=True)
    cluster_file().write_text(json.dumps(config.__dict__, indent=2), encoding="utf-8")
    return config
