"""Operations tab: issue(), transfer(), redeem() and price changes (T1, T3-T6, T9)."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ... import operations as ops
from .widgets import AssetPicker, ValuePicker, hint

MAX_PRICE = 2_000_000_000


def price_input() -> QSpinBox:
    box = QSpinBox()
    box.setRange(0, MAX_PRICE)
    box.setSingleStep(100)
    box.setGroupSeparatorShown(True)
    box.setSuffix(" PLN")
    return box


class OperationsTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.asset_pickers = []
        self.wallet_pickers = []
        self.recipient_pickers = []

        grid = QGridLayout(self)
        grid.addWidget(self._issue_box(), 0, 0)
        grid.addWidget(self._transfer_box(), 0, 1)
        grid.addWidget(self._redeem_box(), 1, 0)
        grid.addWidget(self._price_box(), 1, 1)
        grid.setRowStretch(2, 1)

        context.data_changed.connect(self._update_pickers)

    # --- pickers shared by the forms -----------------------------------------
    def _asset_picker(self) -> AssetPicker:
        picker = AssetPicker()
        self.asset_pickers.append(picker)
        return picker

    def _wallet_picker(self) -> ValuePicker:
        """Acting user = whose local wallet (private key) signs the operation."""
        picker = ValuePicker()
        self.wallet_pickers.append(picker)
        return picker

    def _recipient_picker(self) -> ValuePicker:
        picker = ValuePicker()
        self.recipient_pickers.append(picker)
        return picker

    def _update_pickers(self) -> None:
        for picker in self.asset_pickers:
            picker.set_assets(self.context.assets)
        for picker in self.wallet_pickers:
            picker.set_items([(w.name, w.name) for w in self.context.client_wallets])
        for picker in self.recipient_pickers:
            picker.set_items([(u["name"], u["public_key"]) for u in self.context.clients])

    def _wallet(self, name: str):
        wallet = next((w for w in self.context.wallets if w.name == name), None)
        if wallet is None:
            raise ValueError("no acting user selected (create users in the 'Users & keys' tab)")
        return wallet

    # --- ISSUE -------------------------------------------------------------------
    def _issue_box(self) -> QGroupBox:
        self.issue_title = QLineEdit()
        self.issue_title.setPlaceholderText("e.g. A1 - Sunflowers")
        self.issue_author = QLineEdit()
        self.issue_author.setPlaceholderText("e.g. Vincent van Gogh")
        self.issue_date = QDateEdit(QDate.currentDate())
        self.issue_date.setCalendarPopup(True)
        self.issue_date.setDisplayFormat("yyyy-MM-dd")
        self.issue_price = price_input()
        self.issue_price.setValue(10_000)
        self.issue_owner = self._recipient_picker()
        button = QPushButton("Issue ownership ticket")
        button.clicked.connect(self.issue)

        box = QGroupBox("issue() - new ownership ticket after a purchase")
        form = QFormLayout(box)
        form.addRow(hint("Signed by the Gallery Admin wallet. Only the admin may issue tickets."))
        form.addRow("Artwork title:", self.issue_title)
        form.addRow("Original author:", self.issue_author)
        form.addRow("Accepted by gallery on:", self.issue_date)
        form.addRow("Price:", self.issue_price)
        form.addRow("Owner (buyer):", self.issue_owner)
        form.addRow(button)
        return box

    # Note: widget values are read here, in the UI thread; build() runs in the background.
    def issue(self) -> None:
        title, owner_key = self.issue_title.text().strip(), self.issue_owner.value()
        author = self.issue_author.text()
        accepted_on = self.issue_date.date().toString("yyyy-MM-dd")
        price = self.issue_price.value()

        def build():
            admin = self.context.admin_wallet
            if admin is None:
                raise ValueError("Gallery Admin wallet not found on this computer")
            if not owner_key:
                raise ValueError("choose the owner")
            return admin.sign(ops.issue_payload(admin.public_key, owner_key, title, author,
                                                accepted_on, price))

        owner = self.context.user_name(owner_key) if owner_key else "?"
        self.context.execute(f"ISSUE '{title}' -> {owner}", build)

    # --- TRANSFER -------------------------------------------------------------------
    def _transfer_box(self) -> QGroupBox:
        self.transfer_asset = self._asset_picker()
        self.transfer_signer = self._wallet_picker()
        self.transfer_recipient = self._recipient_picker()
        button = QPushButton("Transfer")
        button.clicked.connect(self.transfer)

        box = QGroupBox("transfer() - sell / hand over the ticket")
        form = QFormLayout(box)
        form.addRow(hint("Signed with the acting user's private key. The nodes accept it only if "
                         "the signer is the current owner."))
        form.addRow("Asset:", self.transfer_asset)
        form.addRow("Acting user (signs):", self.transfer_signer)
        form.addRow("Recipient:", self.transfer_recipient)
        form.addRow(button)
        return box

    def transfer(self) -> None:
        asset_id = self.transfer_asset.value()
        recipient = self.transfer_recipient.value()
        signer = self.transfer_signer.value()

        def build():
            wallet = self._wallet(signer)
            if not recipient:
                raise ValueError("choose the recipient")
            asset = self.context.current_asset(asset_id)
            return wallet.sign(ops.transfer_payload(wallet.public_key, asset_id, asset["version"], recipient))

        description = (f"TRANSFER {str(asset_id)[:8]} by {signer} "
                       f"-> {self.context.user_name(recipient)}")
        self.context.execute(description, build)

    # --- REDEEM -----------------------------------------------------------------------
    def _redeem_box(self) -> QGroupBox:
        self.redeem_asset = self._asset_picker()
        self.redeem_signer = self._wallet_picker()
        button = QPushButton("Redeem (cash out at the current price)")
        button.clicked.connect(self.redeem)

        box = QGroupBox("redeem() - cash out the ticket (status -> REDEEMED)")
        form = QFormLayout(box)
        form.addRow(hint("After REDEEM the ticket can never be transferred or redeemed again. "
                         "The owner is kept in the record."))
        form.addRow("Asset:", self.redeem_asset)
        form.addRow("Acting user (signs):", self.redeem_signer)
        form.addRow(button)
        return box

    def redeem(self) -> None:
        asset_id = self.redeem_asset.value()
        signer = self.redeem_signer.value()

        def build():
            wallet = self._wallet(signer)
            asset = self.context.current_asset(asset_id)
            return wallet.sign(ops.redeem_payload(wallet.public_key, asset_id, asset["version"]))

        self.context.execute(f"REDEEM {str(asset_id)[:8]} by {signer}", build)

    # --- SET_PRICE ------------------------------------------------------------------
    def _price_box(self) -> QGroupBox:
        self.price_asset = self._asset_picker()
        self.price_value = price_input()
        button = QPushButton("Set new price")
        button.clicked.connect(self.set_price)

        box = QGroupBox("Revaluation - update the current price (admin)")
        form = QFormLayout(box)
        form.addRow(hint("The redeem payout always equals the current price of the asset."))
        form.addRow("Asset:", self.price_asset)
        form.addRow("New price:", self.price_value)
        form.addRow(button)
        return box

    def set_price(self) -> None:
        asset_id, price = self.price_asset.value(), self.price_value.value()

        def build():
            admin = self.context.admin_wallet
            if admin is None:
                raise ValueError("Gallery Admin wallet not found on this computer")
            asset = self.context.current_asset(asset_id)
            return admin.sign(ops.set_price_payload(admin.public_key, asset_id, asset["version"], price))

        self.context.execute(f"SET_PRICE {str(asset_id)[:8]} = {price} PLN", build)
