"""Security tests tab: signatures (T7), replay (T8) and conflicting operations (T13, T14).

Operations are prepared first and kept in memory, so the very same signed
operation (same op_id, same signature) can be sent again or saved to a file.
"""

import json

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ... import operations as ops
from ...crypto import verify_signature
from .widgets import AssetPicker, ValuePicker, hint, run_in_background

SIGN_AS_OWNER, NO_SIGNATURE, SIGN_AS_OTHER = range(3)


class SecurityTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.prepared = None            # operation for T7/T8
        self.conflicting = [None, None]  # two operations for T13/T14

        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)
        self.json_view.setFont(QFont("Consolas", 9))
        self.json_view.setPlaceholderText("The prepared operation (payload + signature) appears here.")
        json_box = QGroupBox("Prepared operation - exactly what is sent to the node")
        json_layout = QVBoxLayout(json_box)
        json_layout.addWidget(self.json_view)
        json_layout.addWidget(hint(
            "How nodes verify it (sellart/ledger.py, Ledger.validate): the signature must be a valid "
            "Ed25519 signature of canonical_json(payload) made with the private key matching "
            "payload.signer, the signer must be the current owner, the op_id must not have been "
            "executed before, and asset_version must equal the asset's current version."))

        left = QVBoxLayout()
        left.addWidget(self._authorisation_box())
        left.addWidget(self._conflict_box())
        left.addStretch(1)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addWidget(json_box, 1)

        context.data_changed.connect(self._update_pickers)

    # =========================================================================
    # T7 / T8 - authorisation and replay
    # =========================================================================
    def _authorisation_box(self) -> QGroupBox:
        self.auth_asset = AssetPicker()
        self.auth_owner = ValuePicker()
        self.auth_recipient = ValuePicker()
        self.other_signer = ValuePicker()

        self.signature_mode = QButtonGroup(self)
        modes = QVBoxLayout()
        for mode_id, text in [(SIGN_AS_OWNER, "signed with the owner's own private key"),
                              (NO_SIGNATURE, "no signature")]:
            button = QRadioButton(text)
            self.signature_mode.addButton(button, mode_id)
            modes.addWidget(button)
        other_row = QHBoxLayout()
        other_button = QRadioButton("signed with the private key of:")
        self.signature_mode.addButton(other_button, SIGN_AS_OTHER)
        other_row.addWidget(other_button)
        other_row.addWidget(self.other_signer, 1)
        modes.addLayout(other_row)
        self.signature_mode.button(SIGN_AS_OWNER).setChecked(True)

        prepare = QPushButton("1. Prepare transfer")
        send = QPushButton("2. Send")
        resend = QPushButton("Send the SAME operation again (replay)")
        verify = QPushButton("Check signature locally")
        save = QPushButton("Save to file…")
        load = QPushButton("Load from file…")
        prepare.clicked.connect(self.prepare_transfer)
        send.clicked.connect(lambda: self._send_prepared("SEND"))
        resend.clicked.connect(lambda: self._send_prepared("REPLAY"))
        verify.clicked.connect(self.check_signature)
        save.clicked.connect(self.save_operation)
        load.clicked.connect(self.load_operation)

        buttons = QGridLayout()
        buttons.addWidget(prepare, 0, 0)
        buttons.addWidget(send, 0, 1)
        buttons.addWidget(resend, 1, 0, 1, 2)
        buttons.addWidget(verify, 2, 0)
        buttons.addWidget(save, 2, 1)
        buttons.addWidget(load, 3, 1)
        self.signature_result = QLabel("")

        box = QGroupBox("Authorisation and replay (T7, T8)")
        form = QFormLayout(box)
        form.addRow("Asset:", self.auth_asset)
        form.addRow("On behalf of (payload.signer):", self.auth_owner)
        form.addRow("Recipient:", self.auth_recipient)
        form.addRow("Signature:", modes)
        form.addRow(buttons)
        form.addRow(self.signature_result)
        return box

    def prepare_transfer(self) -> None:
        asset_id, recipient = self.auth_asset.value(), self.auth_recipient.value()
        owner = self._wallet(self.auth_owner.value())
        mode = self.signature_mode.checkedId()
        other = self._wallet(self.other_signer.value())
        if not (asset_id and recipient and owner):
            self.signature_result.setText("Choose the asset, the owner and the recipient first.")
            return
        if mode == SIGN_AS_OTHER and other is None:
            self.signature_result.setText("Choose whose key should sign.")
            return

        def build():
            asset = self.context.current_asset(asset_id)
            payload = ops.transfer_payload(owner.public_key, asset_id, asset["version"], recipient)
            key = {SIGN_AS_OWNER: owner.private_key, NO_SIGNATURE: None,
                   SIGN_AS_OTHER: other.private_key if other else None}[mode]
            return ops.signed(payload, key)

        def prepared(operation):
            self.prepared = operation
            self._show(operation)
            self.signature_result.setText("Operation prepared - not sent yet.")

        run_in_background(build, prepared, lambda e: self.signature_result.setText(f"Error: {e}"))

    def _send_prepared(self, label: str) -> None:
        if self.prepared is None:
            self.signature_result.setText("Prepare or load an operation first.")
            return
        operation = self.prepared
        payload = operation["payload"]
        description = (f"{label} {payload['type']} {str(payload.get('asset_id'))[:8]} "
                       f"(op {payload['op_id'][:8]}, signature: "
                       f"{operation['signature'][:12] + '…' if operation['signature'] else 'none'})")
        self.context.execute(description, lambda: operation)

    def check_signature(self) -> None:
        if self.prepared is None:
            return
        payload, signature = self.prepared["payload"], self.prepared["signature"]
        signer = self.context.user_name(payload["signer"])
        if verify_signature(payload["signer"], payload, signature):
            self.signature_result.setText(f"Signature is VALID for the signer's public key ({signer}).")
        else:
            self.signature_result.setText(f"Signature is NOT valid for the signer's public key "
                                          f"({signer}) - the node will reject it.")

    def save_operation(self) -> None:
        if self.prepared is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save operation", "operation.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.prepared, file, indent=2)
            self.signature_result.setText(f"Saved to {path}")

    def load_operation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load operation", "", "JSON (*.json)")
        if path:
            with open(path, encoding="utf-8") as file:
                self.prepared = json.load(file)
            self._show(self.prepared)
            self.signature_result.setText(f"Loaded from {path}")

    # =========================================================================
    # T13 / T14 - conflicting operations
    # =========================================================================
    def _conflict_box(self) -> QGroupBox:
        self.conflict_asset = AssetPicker()
        self.conflict_owner = ValuePicker()
        self.recipients = [ValuePicker(), ValuePicker()]
        self.nodes = [ValuePicker(), ValuePicker()]
        node_items = [(f"node {n}", n) for n in self.context.config.node_ids]
        for picker in self.nodes:
            picker.setMinimumWidth(90)
            picker.set_items(node_items)
        self.nodes[1].setCurrentIndex(1)

        prepare = QPushButton("1. Prepare both (same starting state)")
        send_both = QPushButton("2. Send both at the same time")
        send_first = QPushButton("Send #1 only")
        send_second = QPushButton("Send #2 only")
        prepare.clicked.connect(self.prepare_conflict)
        send_both.clicked.connect(lambda: self.send_conflicting([0, 1]))
        send_first.clicked.connect(lambda: self.send_conflicting([0]))
        send_second.clicked.connect(lambda: self.send_conflicting([1]))
        self.conflict_summary = QLabel("")
        self.conflict_summary.setWordWrap(True)

        box = QGroupBox("Conflicting operations (T13, T14)")
        form = QFormLayout(box)
        form.addRow(hint("Both transfers are signed by the owner and based on the same asset version. "
                         "Each is valid alone, but only one can become part of the blockchain."))
        form.addRow("Asset:", self.conflict_asset)
        form.addRow("Owner (signs both):", self.conflict_owner)
        for number in range(2):
            row = QHBoxLayout()
            row.addWidget(self.recipients[number], 1)
            row.addWidget(QLabel("send via"))
            row.addWidget(self.nodes[number])
            form.addRow(f"Operation #{number + 1} recipient:", row)
        buttons = QGridLayout()
        buttons.addWidget(prepare, 0, 0, 1, 2)
        buttons.addWidget(send_both, 1, 0, 1, 2)
        buttons.addWidget(send_first, 2, 0)
        buttons.addWidget(send_second, 2, 1)
        form.addRow(buttons)
        form.addRow(self.conflict_summary)
        return box

    def prepare_conflict(self) -> None:
        asset_id = self.conflict_asset.value()
        owner = self._wallet(self.conflict_owner.value())
        recipients = [picker.value() for picker in self.recipients]
        if not (asset_id and owner and all(recipients)):
            self.conflict_summary.setText("Choose the asset, the owner and both recipients first.")
            return

        def build():
            asset = self.context.current_asset(asset_id)
            return [owner.sign(ops.transfer_payload(owner.public_key, asset_id, asset["version"], r))
                    for r in recipients]

        def prepared(operations):
            self.conflicting = operations
            self._show(operations)
            lines = [f"#{i + 1}: {owner.name} -> {self.context.user_name(op['payload']['data']['recipient'])}"
                     f"  (asset version {op['payload']['asset_version']}, op {op['payload']['op_id'][:8]})"
                     for i, op in enumerate(operations)]
            self.conflict_summary.setText("Prepared, not sent yet:\n" + "\n".join(lines))

        run_in_background(build, prepared, lambda e: self.conflict_summary.setText(f"Error: {e}"))

    def send_conflicting(self, numbers: list) -> None:
        if None in self.conflicting:
            self.conflict_summary.setText("Prepare both operations first.")
            return
        for number in numbers:  # each call runs in its own thread -> sent concurrently
            operation, node = self.conflicting[number], self.nodes[number].value()
            recipient = self.context.user_name(operation["payload"]["data"]["recipient"])
            self.context.execute(f"CONFLICT #{number + 1}: TRANSFER "
                                 f"{operation['payload']['asset_id'][:8]} -> {recipient} via node {node}",
                                 lambda op=operation: op, node=node)

    # =========================================================================
    def _update_pickers(self) -> None:
        for picker in (self.auth_asset, self.conflict_asset):
            picker.set_assets(self.context.assets)
        wallets = [(w.name, w.name) for w in self.context.client_wallets]
        for picker in (self.auth_owner, self.other_signer, self.conflict_owner):
            picker.set_items(wallets)
        clients = [(u["name"], u["public_key"]) for u in self.context.clients]
        for picker in (self.auth_recipient, *self.recipients):
            picker.set_items(clients)

    def _wallet(self, name):
        return next((w for w in self.context.wallets if w.name == name), None)

    def _show(self, data) -> None:
        self.json_view.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))
