"""Clients tab (gallery administrator): users registered on the blockchain.

Clients register themselves; the administrator sees only their names and public keys.
"""

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from ... import operations as ops
from .widgets import fill_table, hint, make_table, price_text


class ClientsTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.table = make_table(["User", "Role", "Active tickets", "Value of active tickets (PLN)",
                                 "Public key"], stretch_column=4)
        box = QGroupBox("Users registered on the blockchain")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(hint("Clients create their accounts themselves in the sign-in window. "
                                  "Private keys stay in the clients' own encrypted wallets - the "
                                  "administrator never receives them."))
        box_layout.addWidget(self.table)
        QVBoxLayout(self).addWidget(box)
        context.data_changed.connect(self._update)

    def _update(self) -> None:
        rows = []
        for user in self.context.users:
            owned = [a for a in self.context.assets
                     if a["owner"] == user["public_key"] and a["status"] == ops.ACTIVE]
            rows.append([user["name"], "gallery administrator" if user["is_admin"] else "client",
                         "-" if user["is_admin"] else len(owned),
                         "-" if user["is_admin"] else price_text(sum(a["price"] for a in owned)),
                         user["public_key"]])
        fill_table(self.table, rows)
