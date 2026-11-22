"""Blockchain tab: browse the blocks stored by a chosen node."""

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .widgets import ValuePicker, fill_table, hint, make_table, run_in_background

COLUMNS = ["#", "Kind", "Operation", "Asset", "Signed by", "Term", "Leader", "Time (UTC)", "Hash", "Previous hash"]


class ChainTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.blocks = []

        self.node_picker = ValuePicker()
        self.node_picker.setMinimumWidth(90)
        self.node_picker.set_items([(f"node {n}", n) for n in context.config.node_ids])
        load_button = QPushButton("Load blocks")
        load_button.clicked.connect(self.load)
        self.info = QLabel("")
        top = QHBoxLayout()
        top.addWidget(QLabel("Show the chain stored by:"))
        top.addWidget(self.node_picker)
        top.addWidget(load_button)
        top.addWidget(self.info, 1)

        self.table = make_table(COLUMNS, stretch_column=8)
        self.table.itemSelectionChanged.connect(self._show_block)
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setFont(QFont("Consolas", 9))

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.raw)

        layout = QVBoxLayout(self)
        layout.addWidget(hint("Every block stores one entry and the hash of the previous block, so "
                              "changing any old block would break all later hashes. LEADER blocks "
                              "mark a new leader elected by the consensus."))
        layout.addLayout(top)
        layout.addWidget(splitter, 1)

    def load(self) -> None:
        node = self.node_picker.value()
        run_in_background(lambda: self.context.client.chain(node),
                          lambda blocks: self._fill(node, blocks),
                          lambda error: self.info.setText(f"Node {node} not reachable: {error}"))

    def _fill(self, node: str, blocks: list) -> None:
        self.blocks = blocks
        self.info.setText(f"{len(blocks)} committed blocks on node {node}")
        rows = []
        for block in blocks:
            payload = (block.get("operation") or {}).get("payload") or {}
            rows.append([
                block["index"], block["kind"], payload.get("type", "-"),
                (payload.get("asset_id") or "-")[:8],
                self.context.user_name(payload["signer"]) if payload else "-",
                block["term"], block["leader"], block["timestamp"], block["hash"], block["prev_hash"],
            ])
        fill_table(self.table, rows)

    def _show_block(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self.blocks):
            self.raw.setPlainText(json.dumps(self.blocks[rows[0].row()], indent=2, ensure_ascii=False))
