"""Shared application context: node client, wallets, cached data and operation execution."""

from PySide6.QtCore import QObject, QTimer, Signal

from ...config import load_cluster_config
from ..node_client import AUTO, NodeClient, OperationResult
from ..wallets import load_wallets
from .widgets import run_in_background

REFRESH_INTERVAL_MS = 2000


class AppContext(QObject):
    """Everything the tabs share. Tabs listen to the signals to update themselves."""

    data_changed = Signal()            # users / assets / wallets refreshed
    node_status_changed = Signal(dict)  # node id -> status dict (or None when offline)
    operation_finished = Signal(str, object)  # description, OperationResult

    def __init__(self):
        super().__init__()
        self.config = load_cluster_config()
        self.client = NodeClient(self.config)
        self.read_node = AUTO       # node used for reading state
        self.write_node = AUTO      # node used for sending operations
        self.wallets = load_wallets()
        self.users = []             # registered on the chain: [{"name", "public_key", "is_admin"}]
        self.assets = []
        self.node_status = {}
        self._refreshing = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_INTERVAL_MS)

    # --- convenience lookups -----------------------------------------------
    @property
    def admin_wallet(self):
        return next((w for w in self.wallets if w.is_admin), None)

    @property
    def client_wallets(self) -> list:
        return [w for w in self.wallets if not w.is_admin]

    @property
    def clients(self) -> list:
        """Registered gallery clients (users that can own assets)."""
        return [u for u in self.users if not u["is_admin"]]

    def user_name(self, public_key: str) -> str:
        return next((u["name"] for u in self.users if u["public_key"] == public_key), "unknown")

    # --- periodic refresh ---------------------------------------------------
    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        read_node = self.read_node

        def load():
            status = {node_id: self.client.status(node_id) for node_id in self.config.node_ids}
            try:
                users, assets = self.client.users(read_node), self.client.assets(read_node)
            except Exception:
                users, assets = None, None
            return status, users, assets

        def loaded(result):
            self._refreshing = False
            status, users, assets = result
            self.node_status = status
            self.wallets = load_wallets()
            if users is not None:
                self.users, self.assets = users, assets
            self.node_status_changed.emit(status)
            self.data_changed.emit()

        def failed(_):
            self._refreshing = False

        run_in_background(load, loaded, failed)

    # --- executing operations ------------------------------------------------
    def execute(self, description: str, build_operation, node: str = None, on_done=None) -> None:
        """Build (and sign) an operation in the background, send it and log the result.

        `build_operation()` returns a signed operation dict; it may raise ValueError with
        a message when the operation cannot be prepared (e.g. unknown asset).
        """
        target = node or self.write_node

        def work():
            try:
                operation = build_operation()
            except (ValueError, KeyError) as error:
                return OperationResult("FAILED", f"could not prepare the operation: {error}", target)
            return self.client.submit(operation, target)

        def finished(result):
            self.operation_finished.emit(description, result)
            if on_done:
                on_done(result)
            self.refresh()

        def crashed(message):
            finished(OperationResult("FAILED", message, target))

        run_in_background(work, finished, crashed)

    def current_asset(self, asset_id: str) -> dict:
        """Read the asset (needed for its current version) - raises ValueError if missing."""
        if not asset_id:
            raise ValueError("no asset selected")
        _, asset = self.client.asset(asset_id, self.read_node)
        if asset is None:
            raise ValueError(f"asset {asset_id} does not exist")
        return asset
