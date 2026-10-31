"""Production Firewall page: the iptables rules of production_eshop's own
network namespace (core/production_firewall.py).

Only connection OPENINGS are filtered -- replies and loopback always pass --
so each row says who may open a connection: inbound, the edge to Apache;
outbound, PHP to the database, the internet on 443, a mail relay, ... Anything
without a rule is dropped (inbound) or rejected (outbound). Built-in rules can
be switched off, custom rules added and removed.

Edits save to patterns/production_firewall.json at once; "Apply to
production" sends the ruleset to the selected stack's production_eshop, which
enforces it at once and keeps it across restarts. "Check" reads what the
container enforces, with the address each peer resolved to and the packet
count of every rule."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import production_firewall as pfw
from core.docker_ctl import targets_for
from core.state import AppState
from ui import theme
from ui.common import ErrorBanner, Job, TargetSelector, confirm, muted_label, set_status

_ROLE_KEY = Qt.ItemDataRole.UserRole
_COLUMNS = ["Rule", "Peer", "Protocol", "Ports", "Resolved to", "Packets", "Description"]
_PEER_SUGGESTIONS = ["reverse_proxy", "production_database", "internet", "local-subnets", "any"]


class ProductionFirewallPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.settings = pfw.FirewallSettings.load()
        self._status: pfw.FirewallStatus | None = None
        self._jobs: set[Job] = set()

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Production:"))
        self.target_combo = TargetSelector(lambda: targets_for("edge", state))
        bar.addWidget(self.target_combo)
        self.check_btn = QPushButton("Check")
        self.check_btn.setToolTip("Read the ruleset production_eshop enforces, with resolved peers and counters")
        bar.addWidget(self.check_btn)
        self.apply_btn = QPushButton("Apply to production")
        self.apply_btn.setToolTip("Send this ruleset to production_eshop: enforced at once, kept across restarts")
        bar.addWidget(self.apply_btn)
        self.sync_label = QLabel("")
        bar.addWidget(self.sync_label, stretch=1)
        layout.addLayout(bar)
        self.error_banner = ErrorBanner()
        layout.addWidget(self.error_banner)

        layout.addWidget(muted_label(
            "Firewall inside the production WordPress container. Only connection openings are filtered "
            "(replies and loopback always pass): inbound, only the listed peers may connect to Apache; "
            "outbound, PHP may open connections only to the listed peers. Everything else is dropped "
            "inbound and refused outbound. Apache and PHP cannot change these rules themselves."))

        top = QHBoxLayout()
        self.enabled_check = QCheckBox("Firewall enabled")
        self.enabled_check.setToolTip("Off: the chains stay in place but accept everything")
        top.addWidget(self.enabled_check)
        top.addStretch()
        self.live_label = muted_label("")
        top.addWidget(self.live_label)
        layout.addLayout(top)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)

        self.tables: dict[str, QTableWidget] = {}
        for direction, title in (("inbound", "Inbound — who may connect to production"),
                                 ("outbound", "Outbound — where production may connect")):
            layout.addWidget(QLabel(f"<b>{title}</b>"))
            table = QTableWidget(0, len(_COLUMNS))
            table.setHorizontalHeaderLabels(_COLUMNS)
            header = table.horizontalHeader()
            for col in range(len(_COLUMNS) - 1):
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(len(_COLUMNS) - 1, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setVisible(False)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.itemChanged.connect(self._on_item_changed)
            table.itemSelectionChanged.connect(lambda d=direction: self._on_selection(d))
            layout.addWidget(table, stretch=1 if direction == "inbound" else 2)
            self.tables[direction] = table

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Add rule:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("outbound", "outbound")
        self.direction_combo.addItem("inbound", "inbound")
        add_row.addWidget(self.direction_combo)
        self.peer_combo = QComboBox()
        self.peer_combo.setEditable(True)
        self.peer_combo.addItems(_PEER_SUGGESTIONS)
        self.peer_combo.setCurrentText("")
        self.peer_combo.lineEdit().setPlaceholderText("container, IPv4/CIDR, internet…")
        self.peer_combo.setToolTip(
            "A container or service name (resolved on every apply, on every network production is on), "
            "an IPv4 address or CIDR, 'internet' (outbound: anything outside private ranges), "
            "'local-subnets' (the stack networks production is on) or 'any'")
        add_row.addWidget(self.peer_combo, stretch=1)
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(pfw.PROTOS)
        add_row.addWidget(self.proto_combo)
        self.ports_edit = QLineEdit()
        self.ports_edit.setPlaceholderText("443 or 465,587 or 8000-8100")
        add_row.addWidget(self.ports_edit)
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("description (optional)")
        add_row.addWidget(self.label_edit, stretch=1)
        self.add_btn = QPushButton("Add")
        add_row.addWidget(self.add_btn)
        layout.addLayout(add_row)

        buttons = QHBoxLayout()
        self.remove_btn = QPushButton("Remove custom rule")
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.setToolTip("Firewall on, every built-in rule at its default (custom rules are kept)")
        self.status = QLabel("")
        buttons.addWidget(self.remove_btn)
        buttons.addWidget(self.reset_btn)
        buttons.addWidget(self.status, stretch=1)
        layout.addLayout(buttons)

        self.check_btn.clicked.connect(self.check)
        self.apply_btn.clicked.connect(self.apply)
        self.target_combo.currentIndexChanged.connect(self.check)
        self.enabled_check.toggled.connect(self._on_enabled_toggled)
        self.add_btn.clicked.connect(self._add)
        self.ports_edit.returnPressed.connect(self._add)
        self.remove_btn.clicked.connect(self._remove)
        self.reset_btn.clicked.connect(self._reset)

        self.reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reload()
        self.check()

    def rebuild_targets(self) -> None:
        self.target_combo.rebuild()

    # -- local state ---------------------------------------------------------
    def reload(self) -> None:
        self.settings = pfw.FirewallSettings.load()
        self._fill()

    def _document(self) -> dict | None:
        try:
            doc = pfw.build_document(self.settings)
        except pfw.FirewallError as e:
            self.error_banner.set_error(str(e))
            return None
        return doc

    def _layer(self) -> str:
        return self._status.layer if self._status else pfw.active_layer()

    def _fill(self) -> None:
        self.enabled_check.blockSignals(True)
        self.enabled_check.setChecked(self.settings.enabled)
        self.enabled_check.blockSignals(False)
        try:
            rules = self.settings.rules()
        except pfw.FirewallError as e:
            self.error_banner.set_error(str(e))
            rules = []
        colors = theme.scheme_colors()
        muted = QColor(colors["fg_muted"])
        layer = self._layer()
        resolved = self._status.resolved if self._status else {}
        for direction, table in self.tables.items():
            table.blockSignals(True)
            table.setRowCount(0)
            for r in (r for r in rules if r.direction == direction):
                row = table.rowCount()
                table.insertRow(row)
                id_item = QTableWidgetItem(r.id)
                id_item.setData(_ROLE_KEY, r.key)
                id_item.setFlags(id_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                id_item.setCheckState(Qt.CheckState.Checked if r.enabled else Qt.CheckState.Unchecked)
                tip = "custom rule" if r.custom else "built-in rule"
                if r.layer:
                    tip += f"; applies only in the {r.layer} honeypot layer"
                id_item.setToolTip(tip)
                hits = self._status.hits(direction, r.id) if self._status else None
                cells = [id_item, QTableWidgetItem(r.peer), QTableWidgetItem(r.proto),
                         QTableWidgetItem(r.ports), QTableWidgetItem(self._resolved_text(r, resolved)),
                         QTableWidgetItem("" if hits is None else str(hits)), QTableWidgetItem(r.label)]
                for col, item in enumerate(cells):
                    if not r.active_in(layer) or not self.settings.enabled:
                        item.setForeground(muted)
                    table.setItem(row, col, item)
            table.blockSignals(False)
        self._update_warnings()
        self._refresh_sync()

    def _resolved_text(self, rule: pfw.FirewallRule, resolved: dict) -> str:
        if not self._status:
            return ""
        if rule.peer in ("any", "internet"):
            return "anywhere" if rule.peer == "any" else "public addresses"
        if rule.peer not in resolved:
            return "(apply to resolve)"
        return ", ".join(resolved[rule.peer]) or "unresolved — rule inactive"

    def _update_warnings(self) -> None:
        doc = self._document()
        warnings = pfw.lockout_warnings(doc, self._layer()) if doc else []
        self.warning_label.setVisible(bool(warnings))
        self.warning_label.setText("\n".join(f"⚠ {w}" for w in warnings))
        self.warning_label.setStyleSheet(f"color: {theme.scheme_colors()['danger']};")

    def _save(self, what: str) -> None:
        try:
            self.settings.save()
        except OSError as e:
            QMessageBox.critical(self, "Production firewall", f"Could not write {self.settings.path}:\n{e}")
            return
        self._fill()
        set_status(self.status, f"{what} (saved; apply to production to enforce)")

    # -- edits ---------------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        self.settings.set_enabled(item.data(_ROLE_KEY), enabled)
        self._save(f"{item.data(_ROLE_KEY)} {'enabled' if enabled else 'disabled'}")

    def _on_enabled_toggled(self, checked: bool) -> None:
        self.settings.enabled = checked
        self._save("firewall " + ("enabled" if checked else "disabled"))

    def _on_selection(self, direction: str) -> None:
        # One selection across both tables, so "Remove" knows which rule.
        other = self.tables["outbound" if direction == "inbound" else "inbound"]
        if self.tables[direction].selectedItems():
            other.blockSignals(True)
            other.clearSelection()
            other.blockSignals(False)

    def _selected_key(self) -> str | None:
        for table in self.tables.values():
            rows = {i.row() for i in table.selectedItems()}
            if rows:
                return table.item(rows.pop(), 0).data(_ROLE_KEY)
        return None

    def _add(self) -> None:
        try:
            record = self.settings.add_custom(
                self.direction_combo.currentData(), self.peer_combo.currentText(),
                self.proto_combo.currentText(), self.ports_edit.text(), self.label_edit.text())
        except (ValueError, pfw.FirewallError) as e:
            set_status(self.status, str(e), color=theme.scheme_colors()["danger"])
            return
        self.peer_combo.setCurrentText("")
        self.ports_edit.clear()
        self.label_edit.clear()
        self._save(f"added {record['direction']} rule {record['id']}")

    def _remove(self) -> None:
        key = self._selected_key()
        if not key or not self.settings.remove_custom(key):
            set_status(self.status, "select a custom rule to remove (built-in rules can only be disabled)")
            return
        self._save(f"{key} removed")

    def _reset(self) -> None:
        if not confirm(self, "Reset production firewall",
                       "Switch the firewall on and restore every built-in rule to its default? "
                       "Custom rules are kept."):
            return
        self.settings.reset()
        self._save("built-in rules reset")

    # -- container -----------------------------------------------------------
    def _run(self, fn, on_done) -> None:
        job = Job(fn, self)
        self._jobs.add(job)

        def finished(result, error):
            self._jobs.discard(job)
            on_done(result, error)
        job.done.connect(finished)
        job.start()

    def check(self) -> None:
        remote = self.target_combo.current_remote()
        set_status(self.sync_label, "checking production…")
        self._run(lambda: pfw.get_status(remote), self._on_status)

    def _on_status(self, status, error: str) -> None:
        if error:
            self._status = None
            self.error_banner.set_error(error, prefix="⚠ Could not read the production firewall: ")
            set_status(self.sync_label, "")
            self.live_label.setText("")
            self._fill()
            return
        self.error_banner.set_error(None)
        self._status = status
        self._fill()

    def _refresh_sync(self) -> None:
        """The sync label and live summary from the last status (no round trip)."""
        s = self._status
        if s is None:
            return
        colors = theme.scheme_colors()
        drops = s.hits("inbound", "default")
        rejects = s.hits("outbound", "default")
        live = [f"{s.layer} layer", f"applied {s.applied_at}" if s.applied_at else "never applied"]
        if drops is not None:
            live.append(f"{drops} inbound dropped, {rejects or 0} outbound refused")
        if s.ipv6 is False:
            live.append("IPv6 rules not loaded")
        self.live_label.setText(" · ".join(live))
        doc = self._document()
        if not s.hooked or s.enforced_fingerprint != s.fingerprint:
            set_status(self.sync_label, "NOT enforced: the container's rules are not loaded (see its logs)",
                       color=colors["danger"])
        elif doc is not None and pfw.fingerprint(doc) == s.fingerprint:
            text = "production enforces this ruleset" if s.document["enabled"] else \
                "production runs this ruleset (firewall off)"
            set_status(self.sync_label, text, color=colors["success" if s.document["enabled"] else "warning"])
        elif s.source == "default":
            set_status(self.sync_label, "production runs the image default (nothing applied yet)",
                       color=colors["warning"])
        else:
            set_status(self.sync_label, "production differs from this ruleset (not applied yet)",
                       color=colors["warning"])

    def apply(self) -> None:
        doc = self._document()
        if doc is None:
            return
        warnings = pfw.lockout_warnings(doc, self._layer())
        if warnings and not confirm(self, "Apply production firewall",
                                    "\n\n".join(warnings) + "\n\nApply anyway?"):
            return
        remote = self.target_combo.current_remote()
        set_status(self.sync_label, "applying…")

        def work():
            pfw.apply_document(remote, doc)
            return pfw.get_status(remote)

        def done(status, error):
            if error:
                self.error_banner.set_error(error, prefix="⚠ Could not apply the production firewall: ")
                set_status(self.sync_label, "")
                return
            self._on_status(status, "")
        self._run(work, done)
