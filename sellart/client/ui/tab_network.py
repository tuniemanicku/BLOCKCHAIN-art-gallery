"""Network tab: node status, stopping/starting nodes, partitions and per-node reads (T11, T12, T14)."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...launcher import start_node_process
from ..node_client import NodeUnavailable
from .widgets import AssetPicker, fill_table, hint, make_table, run_in_background, status_cell

NODE_COLUMNS = ["Node", "Address", "Online", "Role", "Term", "Leader", "Committed blocks",
                "Last committed block hash", "Blocked peers (partition)"]
ROLE_COLORS = {"LEADER": "#1565c0", "FOLLOWER": "#444444", "CANDIDATE": "#ad5b00"}


class NetworkTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        node_ids = context.config.node_ids

        # --- node status ---------------------------------------------------------
        self.node_table = make_table(NODE_COLUMNS, stretch_column=7)
        node_buttons = QHBoxLayout()
        for node_id in node_ids:
            start = QPushButton(f"Start {node_id}")
            stop = QPushButton(f"Stop {node_id}")
            start.clicked.connect(lambda _=False, n=node_id: self.start_node(n))
            stop.clicked.connect(lambda _=False, n=node_id: self.stop_node(n))
            node_buttons.addWidget(start)
            node_buttons.addWidget(stop)
        node_buttons.addStretch(1)
        nodes_box = QGroupBox("Nodes - each is a separate process with its own database file")
        nodes_layout = QVBoxLayout(nodes_box)
        nodes_layout.addWidget(self.node_table)
        nodes_layout.addLayout(node_buttons)

        # --- partitions ------------------------------------------------------------
        partition_row = QHBoxLayout()
        for node_id in node_ids:
            rest = ",".join(n for n in node_ids if n != node_id)
            button = QPushButton(f"Split network:  {node_id} | {rest}")
            button.clicked.connect(lambda _=False, n=node_id: self.isolate(n))
            partition_row.addWidget(button)
        heal = QPushButton("Heal network (reconnect all)")
        heal.clicked.connect(self.heal)
        partition_row.addWidget(heal)
        self.partition_info = QLabel("")
        partition_box = QGroupBox("Network partition (simulated)")
        partition_layout = QVBoxLayout(partition_box)
        partition_layout.addWidget(hint(
            "A split makes the nodes drop all node-to-node messages between the two groups "
            "(both directions). The application can still talk to every node. The minority side "
            "cannot reach a majority, so it refuses new operations; after healing it adopts the "
            "majority's chain automatically."))
        partition_layout.addLayout(partition_row)
        partition_layout.addWidget(self.partition_info)

        # --- compare nodes ------------------------------------------------------------
        self.compare_asset = AssetPicker()
        compare_button = QPushButton("Read this asset from EVERY node")
        compare_button.clicked.connect(self.compare)
        compare_row = QHBoxLayout()
        compare_row.addWidget(QLabel("Asset:"))
        compare_row.addWidget(self.compare_asset, 1)
        compare_row.addWidget(compare_button)
        self.compare_table = make_table(["Node", "Owner", "Status", "Version", "Price (PLN)", "Note"],
                                        stretch_column=5)
        compare_box = QGroupBox("Replication check - the same asset read directly from each node")
        compare_layout = QVBoxLayout(compare_box)
        compare_layout.addLayout(compare_row)
        compare_layout.addWidget(self.compare_table)

        layout = QVBoxLayout(self)
        layout.addWidget(nodes_box, 1)
        layout.addWidget(partition_box)
        layout.addWidget(compare_box, 1)

        context.node_status_changed.connect(self._update_nodes)
        context.data_changed.connect(lambda: self.compare_asset.set_assets(context.assets))

    # ------------------------------------------------------------------------
    def _update_nodes(self, status: dict) -> None:
        rows = []
        for node_id in self.context.config.node_ids:
            info = status.get(node_id)
            address = self.context.config.nodes[node_id]
            if info is None:
                rows.append([node_id, address, ("offline", "#c62828"), "-", "-", "-", "-", "-", "-"])
                continue
            rows.append([
                node_id, address, ("online", "#1e7d32"),
                (info["role"], ROLE_COLORS.get(info["role"])), info["term"], info["leader"] or "-",
                info["commit_index"] + 1, info["last_committed_hash"],
                ", ".join(info["blocked_peers"]) or "-",
            ])
        fill_table(self.node_table, rows)

    def start_node(self, node_id: str) -> None:
        if self.context.node_status.get(node_id):
            self.partition_info.setText(f"Node {node_id} is already running.")
            return
        start_node_process(node_id)
        self.partition_info.setText(f"Node {node_id} starting - it will synchronise automatically.")

    def stop_node(self, node_id: str) -> None:
        client = self.context.client
        run_in_background(lambda: client.shutdown(node_id),
                          lambda ok: self.partition_info.setText(
                              f"Node {node_id} stopped." if ok else f"Node {node_id} was not running."))

    def isolate(self, node_id: str) -> None:
        node_ids = self.context.config.node_ids
        others = [n for n in node_ids if n != node_id]
        plan = {node_id: others, **{n: [node_id] for n in others}}
        self._apply_partition(plan, f"Network split: {node_id} | {','.join(others)}")

    def heal(self) -> None:
        self._apply_partition({n: [] for n in self.context.config.node_ids}, "Network healed.")

    def _apply_partition(self, plan: dict, message: str) -> None:
        client = self.context.client

        def apply():
            unreachable = [n for n, blocked in plan.items() if not client.set_partition(n, blocked)]
            return unreachable

        def done(unreachable):
            note = f"  (not reachable, not changed: {', '.join(unreachable)})" if unreachable else ""
            self.partition_info.setText(message + note)
            self.context.refresh()

        run_in_background(apply, done)

    def compare(self) -> None:
        asset_id = self.compare_asset.value()
        client, node_ids = self.context.client, self.context.config.node_ids

        def read_all():
            rows = []
            for node_id in node_ids:
                try:
                    _, asset = client.asset(asset_id, node_id)
                except NodeUnavailable:
                    rows.append([node_id, "-", "-", "-", "-", ("node offline", "#c62828")])
                    continue
                if asset is None:
                    rows.append([node_id, "-", "-", "-", "-", "asset not found on this node"])
                else:
                    rows.append([node_id, asset["owner_name"], status_cell(asset["status"]),
                                 asset["version"], asset["price"], "read from this node's own database"])
            return rows

        run_in_background(read_all, lambda rows: fill_table(self.compare_table, rows))
