"""Session window - the interface of ONE signed-in user.

* a client sees:        My assets, Browse assets, Security tests, My account
* the administrator:    Issue tickets, Browse assets, Clients, Network & nodes, Blockchain

Both share the operation results panel and the node selectors in the toolbar.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QToolBar,
)

from ...crypto import short_key
from ..node_client import AUTO
from .context import AppContext
from .tab_account import AccountTab
from .tab_assets import AssetsTab
from .tab_chain import ChainTab
from .tab_clients import ClientsTab
from .tab_issue import IssueTab
from .tab_my_assets import MyAssetsTab
from .tab_network import NetworkTab
from .tab_security import SecurityTab
from .widgets import OperationLog, ValuePicker

CLIENT_TABS = [(MyAssetsTab, "My assets"), (AssetsTab, "Browse assets"),
               (SecurityTab, "Security tests"), (AccountTab, "My account")]
ADMIN_TABS = [(IssueTab, "Issue tickets"), (AssetsTab, "Browse assets"), (ClientsTab, "Clients"),
              (NetworkTab, "Network && nodes"), (ChainTab, "Blockchain")]


class SessionWindow(QMainWindow):
    def __init__(self, wallet, on_close=None):
        super().__init__()
        self.on_close = on_close
        self.context = AppContext(wallet)
        role = "gallery administrator" if wallet.is_admin else "client"
        self.setWindowTitle(f"Sellart - {wallet.name} ({role})")
        self.resize(1400, 900)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._build_toolbar(wallet, role)

        tabs = QTabWidget()
        for tab_class, title in (ADMIN_TABS if wallet.is_admin else CLIENT_TABS):
            tabs.addTab(tab_class(self.context), title)
        self.setCentralWidget(tabs)

        self.operation_log = OperationLog()
        dock = QDockWidget("Operation results (SUCCESS / REJECTED / FAILED)")
        dock.setWidget(self.operation_log)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.context.operation_finished.connect(self.operation_log.add)

        self.context.node_status_changed.connect(self._update_cluster_summary)
        self.context.refresh()

    def _build_toolbar(self, wallet, role: str) -> None:
        toolbar = QToolBar("Session")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        identity = QLabel(f"  Signed in as <b>{wallet.name}</b> ({role}, key {short_key(wallet.public_key)})  ")
        toolbar.addWidget(identity)
        toolbar.addSeparator()

        node_items = [("Auto (first available)", AUTO)] + [
            (f"node {n}", n) for n in self.context.config.node_ids]
        self.read_picker = ValuePicker()
        self.read_picker.setMinimumWidth(170)
        self.read_picker.set_items(node_items)
        self.read_picker.currentIndexChanged.connect(self._read_node_changed)
        self.write_picker = ValuePicker()
        self.write_picker.setMinimumWidth(170)
        self.write_picker.set_items(node_items)
        self.write_picker.currentIndexChanged.connect(
            lambda: setattr(self.context, "write_node", self.write_picker.value()))

        toolbar.addWidget(QLabel("  Read state from: "))
        toolbar.addWidget(self.read_picker)
        toolbar.addWidget(QLabel("  Send operations via: "))
        toolbar.addWidget(self.write_picker)
        toolbar.addSeparator()
        self.cluster_summary = QLabel("")
        toolbar.addWidget(self.cluster_summary)
        toolbar.addSeparator()
        sign_out = QPushButton("Sign out")
        sign_out.clicked.connect(self.close)
        toolbar.addWidget(sign_out)

    def _read_node_changed(self) -> None:
        self.context.read_node = self.read_picker.value()
        self.context.refresh()

    def _update_cluster_summary(self, status: dict) -> None:
        parts = []
        for node_id, info in status.items():
            if info is None:
                parts.append(f"<span style='color:#c62828'>{node_id}: offline</span>")
            else:
                parts.append(f"<span style='color:#1e7d32'>{node_id}: {info['role'].lower()}</span>")
        self.cluster_summary.setText("  Cluster:  " + "  |  ".join(parts) + "  ")

    def closeEvent(self, event) -> None:
        """Signing out: the decrypted private key is dropped together with the window."""
        self.context.stop()
        if self.on_close:
            self.on_close()
        super().closeEvent(event)


def run_app() -> None:
    from .login_window import LoginWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")                                  # same look on every platform
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)   # colours assume a light theme
    login = LoginWindow()
    login.show()
    sys.exit(app.exec())
