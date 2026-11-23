"""Starting node processes and resetting the environment to a clean state."""

import os
import shutil
import subprocess
import sys

from .client.node_client import NodeClient
from .client.wallets import create_wallet
from .config import ADMIN_WALLET_NAME, PROJECT_ROOT, node_dir, runtime_dir, save_cluster_config

MANAGE_SCRIPT = PROJECT_ROOT / "manage.py"


def start_node_process(node_id: str) -> subprocess.Popen:
    """Start one node as an independent OS process (own console window on Windows)."""
    command = [sys.executable, str(MANAGE_SCRIPT), "node", node_id]
    if os.name == "nt":
        return subprocess.Popen(command, cwd=PROJECT_ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
    log_file = node_dir(node_id) / "node.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as output:
        return subprocess.Popen(command, cwd=PROJECT_ROOT, stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True)


def running_nodes(cluster_config) -> list:
    client = NodeClient(cluster_config)
    return [node_id for node_id in cluster_config.node_ids if client.status(node_id)]


def reset_environment(admin_password: str) -> None:
    """Delete all node data and wallets, then create a fresh admin key and cluster config.

    The admin wallet is encrypted with `admin_password`; user accounts are created later
    by the users themselves (registration in the desktop application).
    """
    from .config import cluster_file, load_cluster_config

    if cluster_file().exists():
        still_running = running_nodes(load_cluster_config())
        if still_running:
            raise SystemExit(f"Stop the running nodes first: {', '.join(still_running)}")

    if runtime_dir().exists():
        shutil.rmtree(runtime_dir())
    admin = create_wallet(ADMIN_WALLET_NAME, admin_password)
    config = save_cluster_config(admin.public_key)

    print(f"Clean environment created in {runtime_dir()}")
    print(f"  admin account: '{ADMIN_WALLET_NAME}', wallet {admin.path}")
    print(f"  nodes        : {', '.join(f'{k}={v}' for k, v in config.nodes.items())}")
