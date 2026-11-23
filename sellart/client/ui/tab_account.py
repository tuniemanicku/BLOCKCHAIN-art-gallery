"""My account tab: who is logged in and where the private key is kept (test T7)."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from .widgets import hint


class AccountTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        wallet = context.wallet

        self.registered = QLabel("checking…")
        fields = [
            ("User name:", wallet.name),
            ("Public key (known to the nodes):", wallet.public_key),
            ("Private key stored in (your side only):", str(wallet.path)),
            ("Private key protection:", "encrypted with your password (scrypt + AES-256-GCM)"),
        ]
        box = QGroupBox("Your account")
        form = QFormLayout(box)
        for label, value in fields:
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label, value_label)
        form.addRow("Registered on the blockchain:", self.registered)
        open_folder = QPushButton("Open wallet folder")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(wallet.path.parent))))
        form.addRow(open_folder)

        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(hint(
            "Your key pair was generated on this computer when you registered. The private key never "
            "leaves your wallet file and is decrypted only in memory after you sign in with your "
            "password. Every operation you make is signed with it; the nodes verify the signature "
            "with your public key. Neither the nodes' databases nor the gallery administrator know "
            "your private key - keep your password and wallet file safe."))
        layout.addStretch(1)
        context.data_changed.connect(self._update)

    def _update(self) -> None:
        registered = any(u["public_key"] == self.context.wallet.public_key for u in self.context.users)
        self.registered.setText("yes" if registered else "no")
        self.registered.setStyleSheet(f"color: {'#1e7d32' if registered else '#c62828'}; font-weight: bold;")
