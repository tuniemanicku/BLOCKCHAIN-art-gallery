"""Issue tickets tab (gallery administrator): issue() and price revaluation."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
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


class IssueTab(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context

        columns = QHBoxLayout()
        columns.addWidget(self._issue_box(), 1)
        columns.addWidget(self._price_box(), 1)
        layout = QVBoxLayout(self)
        layout.addLayout(columns)
        layout.addStretch(1)

        context.data_changed.connect(self._update_pickers)

    def _update_pickers(self) -> None:
        self.issue_owner.set_items([(u["name"], u["public_key"]) for u in self.context.clients])
        self.price_asset.set_assets([a for a in self.context.assets if a["status"] == ops.ACTIVE])

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
        self.issue_owner = ValuePicker()
        button = QPushButton("Issue ownership ticket")
        button.clicked.connect(self.issue)

        box = QGroupBox("issue() - new ownership ticket after a purchase")
        form = QFormLayout(box)
        form.addRow(hint("Signed with the Gallery Admin key - only the administrator can issue "
                         "tickets. The new ticket is ACTIVE and belongs to the buyer."))
        form.addRow("Artwork title:", self.issue_title)
        form.addRow("Original author:", self.issue_author)
        form.addRow("Accepted by gallery on:", self.issue_date)
        form.addRow("Price:", self.issue_price)
        form.addRow("Owner (buyer):", self.issue_owner)
        form.addRow(button)
        return box

    def issue(self) -> None:
        # Widget values are read here, in the UI thread; build() runs in the background.
        title, owner_key = self.issue_title.text().strip(), self.issue_owner.value()
        author = self.issue_author.text()
        accepted_on = self.issue_date.date().toString("yyyy-MM-dd")
        price = self.issue_price.value()
        admin = self.context.wallet

        def build():
            if not owner_key:
                raise ValueError("choose the owner (clients must register first)")
            return admin.sign(ops.issue_payload(admin.public_key, owner_key, title, author,
                                                accepted_on, price))

        owner = self.context.user_name(owner_key) if owner_key else "?"
        self.context.execute(f"ISSUE '{title}' -> {owner}", build)

    # --- SET_PRICE ------------------------------------------------------------------
    def _price_box(self) -> QGroupBox:
        self.price_asset = AssetPicker()
        self.price_value = price_input()
        button = QPushButton("Set new price")
        button.clicked.connect(self.set_price)

        box = QGroupBox("Revaluation - update the current price")
        form = QFormLayout(box)
        form.addRow(hint("The redeem payout always equals the current price of the asset. "
                         "Only ACTIVE tickets can be revalued."))
        form.addRow("Asset:", self.price_asset)
        form.addRow("New price:", self.price_value)
        form.addRow(button)
        return box

    def set_price(self) -> None:
        asset_id, price, admin = self.price_asset.value(), self.price_value.value(), self.context.wallet

        def build():
            asset = self.context.current_asset(asset_id)
            return admin.sign(ops.set_price_payload(admin.public_key, asset_id, asset["version"], price))

        self.context.execute(f"SET_PRICE {str(asset_id)[:8]} = {price} PLN", build)
