"""HTTP client used by the desktop application to talk to the nodes."""

from dataclasses import dataclass, field

import requests

AUTO = "Auto"            # pick the first node that answers (fail-over)
READ_TIMEOUT = 1.0
WRITE_TIMEOUT = 12.0


@dataclass
class OperationResult:
    result: str                  # SUCCESS | REJECTED | FAILED
    message: str
    node: str = "-"
    details: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.result == "SUCCESS"


class NodeUnavailable(Exception):
    pass


class NodeClient:
    def __init__(self, cluster_config):
        self.nodes = dict(cluster_config.nodes)

    def _order(self, node: str) -> list:
        return list(self.nodes) if node in (None, AUTO) else [node]

    # --- reads --------------------------------------------------------------
    def get(self, path: str, node: str = AUTO, timeout: float = READ_TIMEOUT):
        """GET from the given node (or the first reachable one). Returns (node_id, json or None)."""
        last_error = None
        for node_id in self._order(node):
            try:
                response = requests.get(self.nodes[node_id] + path, timeout=timeout)
            except requests.RequestException as error:
                last_error = error
                continue
            return node_id, (response.json() if response.status_code == 200 else None)
        raise NodeUnavailable(f"node {node} is not reachable" if node != AUTO
                              else "no node is reachable") from last_error

    def status(self, node_id: str):
        try:
            return self.get("/status", node_id, timeout=0.6)[1]
        except NodeUnavailable:
            return None

    def asset(self, asset_id: str, node: str = AUTO):
        node_id, data = self.get(f"/assets/{asset_id}", node)
        return node_id, (data or {}).get("asset")

    def history(self, asset_id: str, node: str = AUTO) -> list:
        return (self.get(f"/assets/{asset_id}/history", node)[1] or {}).get("history", [])

    def assets(self, node: str = AUTO) -> list:
        return (self.get("/assets", node)[1] or {}).get("assets", [])

    def users(self, node: str = AUTO) -> list:
        return (self.get("/users", node)[1] or {}).get("users", [])

    def chain(self, node: str = AUTO) -> list:
        return (self.get("/chain", node)[1] or {}).get("blocks", [])

    # --- writes -------------------------------------------------------------
    def submit(self, operation: dict, node: str = AUTO) -> OperationResult:
        for node_id in self._order(node):
            try:
                response = requests.post(f"{self.nodes[node_id]}/operations",
                                         json={"operation": operation}, timeout=WRITE_TIMEOUT)
                data = response.json()
            except (requests.RequestException, ValueError):
                continue
            return OperationResult(data.get("result", "FAILED"), data.get("message", ""),
                                   node_id, data)
        target = f"node {node}" if node != AUTO else "any node"
        return OperationResult("FAILED", f"could not connect to {target}", node or AUTO)

    def set_partition(self, node_id: str, blocked: list) -> bool:
        try:
            requests.post(f"{self.nodes[node_id]}/admin/network", json={"blocked": blocked}, timeout=1)
            return True
        except requests.RequestException:
            return False

    def shutdown(self, node_id: str) -> bool:
        try:
            requests.post(f"{self.nodes[node_id]}/admin/shutdown", json={}, timeout=1)
            return True
        except requests.RequestException:
            return False
