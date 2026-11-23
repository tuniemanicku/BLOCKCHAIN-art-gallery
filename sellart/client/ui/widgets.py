"""Reusable widgets and helpers shared by all tabs."""

from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

RESULT_COLORS = {
    "SUCCESS": "#1e7d32",
    "REJECTED": "#c62828",
    "FAILED": "#ad5b00",
}


# ----------------------------------------------------------------------------
# Running network calls without freezing the window
# ----------------------------------------------------------------------------
class _TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = _TaskSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as error:  # shown to the user, never crashes the UI
            self.signals.failed.emit(str(error))
            return
        self.signals.done.emit(result)


_running_tasks = set()


def run_in_background(function, on_done=None, on_error=None) -> None:
    """Run `function()` in a worker thread; call `on_done(result)` back in the UI thread."""
    task = _Task(function)
    _running_tasks.add(task.signals)

    def finished(*_):
        _running_tasks.discard(task.signals)

    if on_done:
        task.signals.done.connect(on_done)
    if on_error:
        task.signals.failed.connect(on_error)
    task.signals.done.connect(finished)
    task.signals.failed.connect(finished)
    QThreadPool.globalInstance().start(task)


# ----------------------------------------------------------------------------
# Tables
# ----------------------------------------------------------------------------
def make_table(headers: list, stretch_column: int = -1) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_column >= 0:
        header.setSectionResizeMode(stretch_column, QHeaderView.Stretch)
    return table


def table_item(value) -> QTableWidgetItem:
    """A table cell; `value` may be plain text or a (text, color) pair shown in bold."""
    text, color = value if isinstance(value, tuple) else (value, None)
    item = QTableWidgetItem("" if text is None else str(text))
    if color:
        item.setForeground(QColor(color))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
    return item


def fill_table(table: QTableWidget, rows: list) -> None:
    """Replace the whole table content with `rows` (lists of cell values)."""
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, table_item(value))


def status_cell(status: str):
    return status, ("#1e7d32" if status == "ACTIVE" else "#6a1b9a")


def result_cell(result: str):
    return result, RESULT_COLORS.get(result, "#000000")


# ----------------------------------------------------------------------------
# Pickers
# ----------------------------------------------------------------------------
class ValuePicker(QComboBox):
    """Combo box of (label, value) pairs that keeps the selection when refreshed."""

    def __init__(self, editable: bool = False, placeholder: str = ""):
        super().__init__()
        self.setEditable(editable)
        self.setMinimumWidth(260)
        if editable:
            self.lineEdit().setPlaceholderText(placeholder)
        self._items = []

    def set_items(self, items: list) -> None:
        if items == self._items:
            return
        current_value = self.value()
        # keep only text the user typed in (e.g. a pasted ID), never a label of an old item
        typed_text = self.currentText() if self.findText(self.currentText()) < 0 else ""
        self._items = items
        self.blockSignals(True)
        self.clear()
        for label, value in items:
            self.addItem(label, value)
        index = self.findData(current_value)
        if index >= 0:
            self.setCurrentIndex(index)
        elif self.isEditable():
            self.setEditText(typed_text)
        self.blockSignals(False)

    def value(self):
        """Selected value; for an editable picker, typed text that isn't a label is used as-is."""
        text = self.currentText().strip()
        index = self.findText(text)
        if index >= 0:
            return self.itemData(index)
        return text if self.isEditable() and text else None

    def select_value(self, value) -> None:
        index = self.findData(value)
        if index >= 0:
            self.setCurrentIndex(index)
        elif self.isEditable():
            self.setEditText(str(value))


def asset_label(asset: dict) -> str:
    return f"{asset['title']}  ·  {asset['owner_name']}  ·  {asset['status']}  ·  {asset['asset_id'][:8]}"


class AssetPicker(ValuePicker):
    def __init__(self):
        super().__init__(editable=True, placeholder="choose an asset or paste its ID")

    def set_assets(self, assets: list) -> None:
        self.set_items([(asset_label(a), a["asset_id"]) for a in assets])


# ----------------------------------------------------------------------------
# Operation log - every operation result is visible here (SUCCESS / REJECTED / FAILED)
# ----------------------------------------------------------------------------
class OperationLog(QWidget):
    def __init__(self):
        super().__init__()
        self.banner = QLabel("No operation executed yet.")
        self.banner.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.banner.setWordWrap(True)
        font = QFont()
        font.setPointSize(11)
        self.banner.setFont(font)
        self.banner.setStyleSheet("padding: 6px; border-radius: 4px; background: #eeeeee;")
        self.table = make_table(["Time", "Operation", "Node", "Result", "Message"], stretch_column=4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.banner)
        layout.addWidget(self.table)

    def add(self, description: str, result) -> None:
        color = RESULT_COLORS.get(result.result, "#000000")
        self.banner.setText(f"<b style='color:{color}'>{result.result}</b> &nbsp; {description}"
                            f"<br><span style='color:#555'>{result.message}</span>")
        self.banner.setStyleSheet(f"padding: 6px; border-radius: 4px; border: 2px solid {color};")
        self.table.insertRow(0)
        row = [datetime.now().strftime("%H:%M:%S"), description, result.node,
               result_cell(result.result), result.message]
        for column, value in enumerate(row):
            self.table.setItem(0, column, table_item(value))


def hint(text: str) -> QLabel:
    """Small grey explanatory text."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #666;")
    return label


def price_text(price) -> str:
    """1500000 -> '1 500 000'."""
    return f"{price:,}".replace(",", " ") if isinstance(price, int) else "-"
