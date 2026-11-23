"""My assets tab (clients): own tickets, transfer() and redeem().

Operations are always signed with the private key of the logged-in user. The
asset field also accepts any pasted asset ID - the nodes, not the application,
decide whether the user is allowed to act on it (see test T4).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ... import operations as ops
from .tab_assets import AssetDetails
from .widgets import AssetPicker, ValuePicker, fill_table, hint, make_table, price_text, status_cell

COLUMNS = ["Title", "Original author", "Status", "Current price (PLN)", "Accepted on", "Asset ID (uuid)"]


class MyAssetsTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.assets_by_row = []

        self.summary = QLabel("")
        self.summary.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.table = make_table(COLUMNS, stretch_column=0)
        self.table.itemSelectionChanged.connect(self._row_selected)
        table_box = QGroupBox("Tickets you own")
        table_layout = QVBoxLayout(table_box)
        table_layout.addWidget(self.summary)
        table_layout.addWidget(self.table)

        actions = QVBoxLayout()
        actions.addWidget(self._transfer_box())
        actions.addWidget(self._redeem_box())
        actions.addStretch(1)
        actions_widget = QWidget()
        actions_widget.setLayout(actions)
        actions_widget.setMaximumWidth(520)

        top = QHBoxLayout()
        top.addWidget(table_box, 1)
        top.addWidget(actions_widget)
        top_widget = QWidget()
        top_widget.setLayout(top)

        top_widget.setMinimumHeight(actions_widget.sizeHint().height() + 30)  # forms never clipped

        self.details = AssetDetails(context)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.details)
        splitter.setChildrenCollapsible(False)

        QVBoxLayout(self).addWidget(splitter)
        context.data_changed.connect(self._update)

    # --- forms -------------------------------------------------------------------
    def _transfer_box(self) -> QGroupBox:
        self.transfer_asset = AssetPicker()
        self.transfer_recipient = ValuePicker()
        button = QPushButton("Transfer")
        button.clicked.connect(self.transfer)
        box = QGroupBox("transfer() - sell / hand over a ticket")
        form = QFormLayout(box)
        form.addRow(hint("Signed with your private key. The nodes accept it only if you are the "
                         "current owner. You may also paste the ID of any other asset."))
        form.addRow("Asset:", self.transfer_asset)
        form.addRow("Recipient:", self.transfer_recipient)
        form.addRow(button)
        return box

    def _redeem_box(self) -> QGroupBox:
        self.redeem_asset = AssetPicker()
        button = QPushButton("Redeem (cash out at the current price)")
        button.clicked.connect(self.redeem)
        box = QGroupBox("redeem() - cash out a ticket (status -> REDEEMED)")
        form = QFormLayout(box)
        form.addRow(hint("You receive the current price of the artwork. A redeemed ticket can never "
                         "be transferred or redeemed again; you stay recorded as its owner."))
        form.addRow("Asset:", self.redeem_asset)
        form.addRow(button)
        return box

    # --- actions -------------------------------------------------------------------
    def transfer(self) -> None:
        asset_id, recipient = self.transfer_asset.value(), self.transfer_recipient.value()
        wallet = self.context.wallet

        def build():
            if not recipient:
                raise ValueError("choose the recipient")
            asset = self.context.current_asset(asset_id)
            return wallet.sign(ops.transfer_payload(wallet.public_key, asset_id, asset["version"], recipient))

        self.context.execute(f"TRANSFER {str(asset_id)[:8]} by {wallet.name} -> "
                             f"{self.context.user_name(recipient)}", build)

    def redeem(self) -> None:
        asset_id, wallet = self.redeem_asset.value(), self.context.wallet

        def build():
            asset = self.context.current_asset(asset_id)
            return wallet.sign(ops.redeem_payload(wallet.public_key, asset_id, asset["version"]))

        self.context.execute(f"REDEEM {str(asset_id)[:8]} by {wallet.name}", build)

    # --- refresh -------------------------------------------------------------------
    def _update(self) -> None:
        mine = self.context.my_assets
        active = [a for a in mine if a["status"] == ops.ACTIVE]
        for picker in (self.transfer_asset, self.redeem_asset):
            picker.set_assets(active)
        self.transfer_recipient.set_items([(u["name"], u["public_key"]) for u in self.context.other_clients])

        value = sum(a["price"] for a in active)
        self.summary.setText(f"{len(active)} active ticket(s), current value {price_text(value)} PLN"
                             f"  ·  {len(mine) - len(active)} redeemed")
        if mine == self.assets_by_row:
            return
        self.assets_by_row = list(mine)
        fill_table(self.table, [
            [a["title"], a["author"], status_cell(a["status"]), price_text(a["price"]),
             a["accepted_on"], a["asset_id"]]
            for a in mine
        ])
        if self.details.asset_id:
            self.details.show_asset(self.details.asset_id)

    def _row_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows and rows[0].row() < len(self.assets_by_row):
            asset_id = self.assets_by_row[rows[0].row()]["asset_id"]
            self.details.show_asset(asset_id)
            for picker in (self.transfer_asset, self.redeem_asset):
                picker.select_value(asset_id)
