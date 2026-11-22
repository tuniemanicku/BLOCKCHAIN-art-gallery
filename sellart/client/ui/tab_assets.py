"""Assets tab: list of tickets, current state of one asset and its full history (T1, T2, T9)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...crypto import short_key
from .widgets import fill_table, hint, make_table, run_in_background, status_cell

ASSET_COLUMNS = ["Title", "Original author", "Owner", "Status", "Price (PLN)", "Accepted on", "Asset ID (uuid)"]
HISTORY_COLUMNS = ["#", "Operation", "From (previous owner)", "To (recipient)", "Operation ID",
                   "Block", "Time (UTC)", "Note"]
DETAIL_FIELDS = [
    ("asset_id", "Asset ID (uuid)"),
    ("title", "Title"),
    ("author", "Original author"),
    ("owner_name", "Owner"),
    ("owner", "Owner public key"),
    ("status", "Status"),
    ("price", "Current price (PLN)"),
    ("accepted_on", "Accepted by gallery on"),
    ("issued_at", "Ticket issued at (UTC)"),
    ("redeemed_value", "Paid out on redeem (PLN)"),
    ("version", "Version (operations applied)"),
]


class AssetsTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.assets_by_row = []

        # --- lookup bar -------------------------------------------------------
        self.asset_id_input = QLineEdit()
        self.asset_id_input.setPlaceholderText("asset ID (uuid) - or click a row below")
        show_button = QPushButton("Show state && history")
        owner_button = QPushButton("Read owner")
        show_button.clicked.connect(self.show_selected_asset)
        owner_button.clicked.connect(self.read_owner)
        self.answer = QLabel("")
        self.answer.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.answer.setStyleSheet("font-size: 14px; font-weight: bold;")

        lookup = QHBoxLayout()
        lookup.addWidget(QLabel("Asset ID:"))
        lookup.addWidget(self.asset_id_input, 1)
        lookup.addWidget(show_button)
        lookup.addWidget(owner_button)

        # --- all assets ---------------------------------------------------------
        self.assets_table = make_table(ASSET_COLUMNS, stretch_column=0)
        self.assets_table.itemSelectionChanged.connect(self._row_selected)

        # --- details + history -------------------------------------------------
        self.detail_labels = {}
        details_form = QFormLayout()
        for key, label in DETAIL_FIELDS:
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.detail_labels[key] = value
            details_form.addRow(f"{label}:", value)
        self.details_source = hint("")
        details_box = QGroupBox("Current state of the asset")
        details_layout = QVBoxLayout(details_box)
        details_layout.addLayout(details_form)
        details_layout.addWidget(self.details_source)

        self.history_table = make_table(HISTORY_COLUMNS, stretch_column=7)
        history_box = QGroupBox("History (chronological, read from the blockchain)")
        QVBoxLayout(history_box).addWidget(self.history_table)

        bottom = QSplitter(Qt.Horizontal)
        bottom.addWidget(details_box)
        bottom.addWidget(history_box)
        bottom.setStretchFactor(1, 2)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.assets_table)
        splitter.addWidget(bottom)

        layout = QVBoxLayout(self)
        layout.addLayout(lookup)
        layout.addWidget(self.answer)
        layout.addWidget(splitter, 1)

        context.data_changed.connect(self._update_assets_table)

    # ------------------------------------------------------------------------
    def _update_assets_table(self) -> None:
        if self.context.assets == self.assets_by_row:
            return
        selected_id = self.asset_id_input.text().strip()
        self.assets_by_row = list(self.context.assets)
        fill_table(self.assets_table, [
            [a["title"], a["author"], a["owner_name"], status_cell(a["status"]),
             f"{a['price']:,}".replace(",", " "), a["accepted_on"], a["asset_id"]]
            for a in self.assets_by_row
        ])
        if selected_id:
            self.show_selected_asset()

    def _row_selected(self) -> None:
        rows = self.assets_table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self.assets_by_row):
            self.asset_id_input.setText(self.assets_by_row[rows[0].row()]["asset_id"])
            self.show_selected_asset()

    def read_owner(self) -> None:
        asset_id = self.asset_id_input.text().strip()
        client, node = self.context.client, self.context.read_node

        def shown(result):
            node_id, asset = result
            if asset:
                self.answer.setText(f"Owner of {asset_id[:8]}…: {asset['owner_name']}  "
                                    f"(key {short_key(asset['owner'])}, read from node {node_id})")
            else:
                self.answer.setText(f"Asset {asset_id} does not exist.")

        run_in_background(lambda: client.asset(asset_id, node), shown,
                          lambda error: self.answer.setText(f"Read failed: {error}"))

    def show_selected_asset(self) -> None:
        asset_id = self.asset_id_input.text().strip()
        if not asset_id:
            return
        client, node = self.context.client, self.context.read_node

        def load():
            node_id, asset = client.asset(asset_id, node)
            history = client.history(asset_id, node_id) if asset else []
            return node_id, asset, history

        run_in_background(load, self._show_details,
                          lambda error: self.details_source.setText(f"Read failed: {error}"))

    def _show_details(self, result) -> None:
        node_id, asset, history = result
        if asset is None:
            for label in self.detail_labels.values():
                label.setText("-")
            self.details_source.setText("Asset not found.")
            self.history_table.setRowCount(0)
            return
        for key, label in self.detail_labels.items():
            value = asset.get(key)
            label.setText("-" if value is None else str(value))
        color = "#1e7d32" if asset["status"] == "ACTIVE" else "#6a1b9a"
        self.detail_labels["status"].setStyleSheet(f"color: {color}; font-weight: bold;")
        self.details_source.setText(f"Read from node {node_id} (its own copy of the blockchain).")
        fill_table(self.history_table, [
            [number, entry["type"], entry["from_name"] or "-", entry["to_name"] or "-",
             entry["op_id"], f"#{entry['block_index']}", entry["timestamp"], entry["note"]]
            for number, entry in enumerate(history, start=1)
        ])
