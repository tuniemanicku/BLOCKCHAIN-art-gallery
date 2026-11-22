"""HTTP interface of a node (JSON over HTTP, Python standard library only).

Client API
  GET  /status                    node role, term, leader, chain height
  GET  /assets                    all assets (committed state of THIS node)
  GET  /assets/<id>               one asset: owner, status, price, ...
  GET  /assets/<id>/history       chronological ISSUE / TRANSFER / REDEEM history
  GET  /users                     registered users (name + public key)
  GET  /chain                     committed blocks (raw, signed) - used by the verifier
  GET  /operations/<op_id>        is this operation committed?
  POST /operations                submit a signed operation  {"operation": {...}}

Demo / administration
  POST /admin/network             simulate a partition       {"blocked": ["B", "C"]}
  POST /admin/shutdown            stop this node process

Node-to-node (Raft)
  POST /raft/vote, /raft/append, /raft/commit_index
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import load_cluster_config, node_dir
from .consensus import RaftNode, log
from .storage import NodeStorage


class NodeRequestHandler(BaseHTTPRequestHandler):
    node: RaftNode = None        # set by run_node()
    server_ref = None

    # --- routing ----------------------------------------------------------
    def do_GET(self):
        if not self.path.startswith("/status"):
            self.node.catch_up_before_read()   # see RaftNode.catch_up_before_read
        routes = [
            (r"/status", lambda: self.node.status()),
            (r"/assets", self._list_assets),
            (r"/assets/(?P<asset_id>[\w-]+)", self._get_asset),
            (r"/assets/(?P<asset_id>[\w-]+)/history", self._get_history),
            (r"/users", self._list_users),
            (r"/chain", lambda: {"node_id": self.node.id, "blocks": self.node.committed_chain()}),
            (r"/operations/(?P<op_id>[\w-]+)", lambda op_id: self.node.operation_status(op_id)),
        ]
        self._dispatch(routes)

    def do_POST(self):
        routes = [
            (r"/operations", self._submit_operation),
            (r"/raft/vote", lambda: self.node.handle_request_vote(self.body)),
            (r"/raft/append", lambda: self.node.handle_append_entries(self.body)),
            (r"/raft/commit_index", lambda: self.node.handle_commit_index()),
            (r"/admin/network", self._set_network),
            (r"/admin/shutdown", self._shutdown),
        ]
        self._dispatch(routes)

    def _dispatch(self, routes):
        path = self.path.split("?")[0].rstrip("/") or "/"
        self.body = self._read_body()
        # Simulated partition: traffic from a blocked peer is dropped.
        sender = self.body.get("sender")
        if sender and self.node.is_blocked(sender):
            return self._send(503, {"error": "network partition (simulated)"})
        for pattern, handler in routes:
            match = re.fullmatch(pattern, path)
            if match:
                try:
                    result = handler(**match.groupdict())
                except KeyError as missing:
                    return self._send(400, {"error": f"missing field {missing}"})
                if result is None:
                    return self._send(404, {"error": "not found"})
                return self._send(200, result)
        self._send(404, {"error": f"unknown endpoint {path}"})

    # --- handlers -----------------------------------------------------------
    def _list_assets(self):
        with self.node.lock:
            ledger = self.node.committed_ledger
            return {"assets": [ledger.asset_view(asset_id) for asset_id in ledger.assets]}

    def _get_asset(self, asset_id):
        with self.node.lock:
            asset = self.node.committed_ledger.asset_view(asset_id)
        return {"asset": asset, "read_from_node": self.node.id} if asset else None

    def _get_history(self, asset_id):
        with self.node.lock:
            history = self.node.committed_ledger.history.get(asset_id)
        return {"asset_id": asset_id, "history": list(history)} if history else None

    def _list_users(self):
        with self.node.lock:
            return {"users": self.node.committed_ledger.users_view()}

    def _submit_operation(self):
        return self.node.submit(self.body["operation"], forwarded=self.body.get("forwarded", False))

    def _set_network(self):
        self.node.set_partition(self.body.get("blocked", []))
        return self.node.status()

    def _shutdown(self):
        log(self.node.id, "shutdown requested")
        self.node.stop()
        threading.Thread(target=self.server_ref.shutdown, daemon=True).start()
        return {"stopped": self.node.id}

    # --- helpers ------------------------------------------------------------
    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _send(self, status: int, data: dict):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence default per-request logging
        pass


def run_node(node_id: str) -> None:
    config = load_cluster_config()
    if node_id not in config.nodes:
        raise SystemExit(f"Unknown node '{node_id}'. Known nodes: {', '.join(config.node_ids)}")

    storage = NodeStorage(node_dir(node_id) / "node.db")
    node = RaftNode(node_id, config, storage)

    server = ThreadingHTTPServer(("127.0.0.1", config.port_of(node_id)), NodeRequestHandler)
    server.daemon_threads = True
    NodeRequestHandler.node = node
    NodeRequestHandler.server_ref = server

    node.start()
    log(node_id, f"listening on {config.nodes[node_id]}  (data: {node_dir(node_id)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        server.server_close()
        log(node_id, "stopped")
