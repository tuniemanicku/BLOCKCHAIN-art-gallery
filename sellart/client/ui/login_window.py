"""Start window: sign in to an existing account or register a new client account.

Every successful sign-in opens a separate session window for that user. Several
sessions can be open at once (handy for a demonstration with Alice, Bob, Charlie
and the gallery administrator on one computer); in real use each person runs the
application on their own computer with their own wallet.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import operations as ops
from ...config import load_cluster_config
from ..node_client import NodeClient
from ..wallets import WrongPassword, create_wallet, delete_wallet, load_wallets
from .session_window import SessionWindow
from .widgets import ValuePicker, hint, run_in_background


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sellart - sign in")
        self.setMinimumWidth(520)
        self.client = NodeClient(load_cluster_config())
        self.sessions = {}  # user name -> open SessionWindow

        title = QLabel("Sellart - art gallery ownership tickets")
        title.setStyleSheet("font-size: 17px; font-weight: bold;")

        # --- sign in -------------------------------------------------------------
        self.account_picker = ValuePicker()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.sign_in)
        sign_in_button = QPushButton("Sign in")
        sign_in_button.setDefault(True)
        sign_in_button.clicked.connect(self.sign_in)
        sign_in_box = QGroupBox("Sign in")
        sign_in_form = QFormLayout(sign_in_box)
        sign_in_form.addRow("Account:", self.account_picker)
        sign_in_form.addRow("Password:", self.password_input)
        sign_in_form.addRow(sign_in_button)

        # --- register --------------------------------------------------------------
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("e.g. Alice")
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_password_repeat = QLineEdit()
        self.new_password_repeat.setEchoMode(QLineEdit.Password)
        self.new_password_repeat.returnPressed.connect(self.register)
        self.register_button = QPushButton("Register and sign in")
        self.register_button.clicked.connect(self.register)
        register_box = QGroupBox("New client account")
        register_form = QFormLayout(register_box)
        register_form.addRow(hint(
            "Registration generates your key pair on this computer. The private key is saved only "
            "in your wallet file, encrypted with your password. The nodes receive just your public "
            "key in a REGISTER_USER operation signed by your new key."))
        register_form.addRow("User name:", self.new_name)
        register_form.addRow("Password:", self.new_password)
        register_form.addRow("Repeat password:", self.new_password_repeat)
        register_form.addRow(self.register_button)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint("Clients manage their own tickets. The Gallery Admin account issues new "
                              "tickets and supervises the network. Each sign-in opens its own window."))
        layout.addWidget(sign_in_box)
        layout.addWidget(register_box)
        layout.addWidget(self.status)
        layout.addStretch(1)

        self.reload_accounts()

    # ------------------------------------------------------------------------
    def reload_accounts(self, select: str = None) -> None:
        wallets = sorted(load_wallets(), key=lambda w: (not w.is_admin, w.name.lower()))
        self.account_picker.set_items(
            [(f"{w.name}  (gallery administrator)" if w.is_admin else w.name, w.name) for w in wallets])
        if select:
            self.account_picker.select_value(select)

    def _show(self, message: str, error: bool = False) -> None:
        self.status.setStyleSheet(f"color: {'#c62828' if error else '#1e7d32'};")
        self.status.setText(message)

    def sign_in(self) -> None:
        name = self.account_picker.value()
        wallet = next((w for w in load_wallets() if w.name == name), None)
        if wallet is None:
            return self._show("Choose an account.", error=True)
        try:
            unlocked = wallet.unlock(self.password_input.text())
        except WrongPassword:
            return self._show("Wrong password.", error=True)
        self.password_input.clear()
        if unlocked.is_admin:
            return self._open_session(unlocked)

        def check_registration():
            users = self.client.users()
            if any(u["public_key"] == unlocked.public_key for u in users):
                return None
            # Registration did not reach the blockchain earlier (e.g. nodes were offline).
            payload = ops.register_user_payload(unlocked.public_key, unlocked.name)
            return self.client.submit(unlocked.sign(payload))

        def checked(result):
            if result is not None and not result.ok:
                return self._show(f"Your account is not registered yet: {result.message}", error=True)
            self._open_session(unlocked)

        run_in_background(check_registration, checked,
                          lambda error: self._show(f"No node is reachable ({error}). "
                                                   f"Start the nodes first.", error=True))

    def register(self) -> None:
        name, password = self.new_name.text().strip(), self.new_password.text()
        if password != self.new_password_repeat.text():
            return self._show("The passwords differ.", error=True)
        try:
            wallet = create_wallet(name, password)
        except ValueError as error:
            return self._show(str(error), error=True)

        self.register_button.setEnabled(False)
        self._show(f"Registering {name}…")
        payload = ops.register_user_payload(wallet.public_key, wallet.name)

        def registered(result):
            self.register_button.setEnabled(True)
            if not result.ok:
                delete_wallet(wallet)  # nothing was stored on the chain - allow another try
                return self._show(f"Registration {result.result}: {result.message}", error=True)
            for field in (self.new_name, self.new_password, self.new_password_repeat):
                field.clear()
            self.reload_accounts(select=wallet.name)
            self._open_session(wallet)

        def failed(error):
            delete_wallet(wallet)
            self.register_button.setEnabled(True)
            self._show(f"Registration failed: {error}", error=True)

        run_in_background(lambda: self.client.submit(wallet.sign(payload)), registered, failed)

    def _open_session(self, wallet) -> None:
        window = self.sessions.get(wallet.name)
        if window is not None:
            window.raise_()
            window.activateWindow()
            return self._show(f"{wallet.name} is already signed in.")
        window = SessionWindow(wallet, on_close=lambda: self.sessions.pop(wallet.name, None))
        self.sessions[wallet.name] = window
        window.show()
        self._show(f"Signed in as {wallet.name}. You can sign in other accounts here as well.")

