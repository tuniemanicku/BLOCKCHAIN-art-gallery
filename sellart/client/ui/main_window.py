"""Main window of the Sellart desktop application."""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QTabWidget,
    QToolBar,
)

from ..node_client import AUTO
from .context import AppContext
from .tab_assets import AssetsTab
from .tab_chain import ChainTab
from .tab_network import NetworkTab
from .tab_operations import OperationsTab
from .tab_security import SecurityTab
from .tab_users import UsersTab
from .widgets import OperationLog, ValuePicker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sellart - art gallery ownership tickets")
        self.resize(1400, 900)
        self.context = AppContext()

        self._build_toolbar()

        tabs = QTabWidget()
        tabs.addTab(AssetsTab(self.context), "Assets")
        tabs.addTab(OperationsTab(self.context), "Operations")
        tabs.addTab(UsersTab(self.context), "Users && keys")
        tabs.addTab(SecurityTab(self.context), "Security tests")
        tabs.addTab(NetworkTab(self.context), "Network && nodes")
        tabs.addTab(ChainTab(self.context), "Blockchain")
        self.setCentralWidget(tabs)

        self.operation_log = OperationLog()
        dock = QDockWidget("Operation results (SUCCESS / REJECTED / FAILED)")
        dock.setWidget(self.operation_log)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.context.operation_finished.connect(self.operation_log.add)

        self.context.node_status_changed.connect(self._update_cluster_summary)
        self.context.refresh()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Connection")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        node_items = [("Auto (first available)", AUTO)] + [
            (f"node {n}", n) for n in self.context.config.node_ids]

        self.read_picker = ValuePicker()
        self.read_picker.set_items(node_items)
        self.read_picker.currentIndexChanged.connect(self._read_node_changed)
        self.write_picker = ValuePicker()
        self.write_picker.set_items(node_items)
        self.write_picker.currentIndexChanged.connect(
            lambda: setattr(self.context, "write_node", self.write_picker.value()))

        toolbar.addWidget(QLabel("  Read state from: "))
        toolbar.addWidget(self.read_picker)
        toolbar.addWidget(QLabel("    Send operations via: "))
        toolbar.addWidget(self.write_picker)
        toolbar.addSeparator()
        self.cluster_summary = QLabel("")
        toolbar.addWidget(self.cluster_summary)

    def _read_node_changed(self) -> None:
        self.context.read_node = self.read_picker.value()
        self.context.refresh()

    def _update_cluster_summary(self, status: dict) -> None:
        parts = []
        for node_id, info in status.items():
            if info is None:
                parts.append(f"<span style='color:#c62828'>{node_id}: offline</span>")
            else:
                role = info["role"].lower()
                parts.append(f"<span style='color:#1e7d32'>{node_id}: {role}</span>")
        self.cluster_summary.setText("   Cluster:  " + "  |  ".join(parts))


def run_app() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")                                  # same look on every platform
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)   # colours below assume a light theme
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
