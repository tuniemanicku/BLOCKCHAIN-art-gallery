"""Users & keys tab: create users (key pair generated locally) and show where keys are stored."""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import operations as ops
from ...config import wallets_dir
from ..node_client import OperationResult
from ..wallets import create_wallet, find_wallet
from .widgets import fill_table, hint, make_table

DEMO_USERS = ("Alice", "Bob", "Charlie")


class UsersTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("user name, e.g. Alice")
        create_button = QPushButton("Create user")
        create_button.clicked.connect(lambda: self.create_user(self.name_input.text().strip()))
        demo_button = QPushButton("Create Alice, Bob and Charlie")
        demo_button.clicked.connect(self.create_demo_users)

        create_row = QHBoxLayout()
        create_row.addWidget(QLabel("Name:"))
        create_row.addWidget(self.name_input, 1)
        create_row.addWidget(create_button)
        create_row.addWidget(demo_button)

        create_box = QGroupBox("New user")
        create_layout = QVBoxLayout(create_box)
        create_layout.addWidget(hint(
            "Creating a user generates an Ed25519 key pair ON THIS COMPUTER. The private key is "
            "saved only in the user's local wallet file. The nodes receive just the public key, "
            "inside a REGISTER_USER operation signed by the new key itself."))
        create_layout.addLayout(create_row)

        self.wallet_table = make_table(["User", "Public key", "Private key stored in (user side)",
                                        "Registered on the blockchain"], stretch_column=2)
        open_folder = QPushButton("Open wallet folder")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(wallets_dir()))))
        wallets_box = QGroupBox("Local wallets (private keys - never sent to any node)")
        wallets_layout = QVBoxLayout(wallets_box)
        wallets_layout.addWidget(self.wallet_table)
        wallets_layout.addWidget(open_folder)

        self.chain_users_table = make_table(["User", "Public key", "Role"], stretch_column=1)
        chain_box = QGroupBox("Users registered on the blockchain (public keys only)")
        QVBoxLayout(chain_box).addWidget(self.chain_users_table)

        layout = QVBoxLayout(self)
        layout.addWidget(create_box)
        layout.addWidget(wallets_box, 1)
        layout.addWidget(chain_box, 1)

        context.data_changed.connect(self._update_tables)

    def create_user(self, name: str) -> None:
        if not name:
            return
        wallet = find_wallet(name)
        if wallet is None:
            try:
                wallet = create_wallet(name)
            except ValueError as error:
                self.context.operation_finished.emit(
                    f"CREATE USER {name}", OperationResult("FAILED", str(error)))
                return
        payload = ops.register_user_payload(wallet.public_key, name)
        self.context.execute(f"REGISTER_USER {name}", lambda: wallet.sign(payload))
        self.name_input.clear()

    def create_demo_users(self) -> None:
        for name in DEMO_USERS:
            self.create_user(name)

    def _update_tables(self) -> None:
        registered = {u["public_key"] for u in self.context.users}
        fill_table(self.wallet_table, [
            [w.name, w.public_key, str(w.path),
             ("yes", "#1e7d32") if w.public_key in registered else ("no", "#c62828")]
            for w in self.context.wallets
        ])
        fill_table(self.chain_users_table, [
            [u["name"], u["public_key"], "gallery administrator" if u["is_admin"] else "client"]
            for u in self.context.users
        ])

