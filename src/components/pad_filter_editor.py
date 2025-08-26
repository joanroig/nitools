from PyQt6 import QtCore, QtWidgets

from models.pad_filter_config import PadFilterConfig


class PadFilterEditor(QtWidgets.QWidget):
    pad_filter_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.table = QtWidgets.QTableWidget(16, 2)
        self.table.setHorizontalHeaderLabels(["Pad", "Keywords (comma-separated)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Initialize table rows
        for pad_num in range(1, 17):
            self._set_pad_row(pad_num)

        self.table.resizeRowsToContents()
        self._adjust_table_height()

        self.table.itemChanged.connect(self._on_item_changed)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def _set_pad_row(self, pad_num):
        pad_item = QtWidgets.QTableWidgetItem(str(pad_num))
        pad_item.setFlags(pad_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(pad_num - 1, 0, pad_item)

        self.table.setItem(pad_num - 1, 1, QtWidgets.QTableWidgetItem())

    def _adjust_table_height(self):
        total_height = self.table.horizontalHeader().height() + sum(
            self.table.rowHeight(i) for i in range(self.table.rowCount())
        )
        self.table.setFixedHeight(total_height)

    def _on_item_changed(self, item):
        if item.column() == 1:
            self.pad_filter_changed.emit()

    def get_pad_filter(self) -> PadFilterConfig:
        pad_data = {}
        for row in range(16):
            keywords_item = self.table.item(row, 1)
            if keywords_item:
                keywords = [kw.strip().lower() for kw in keywords_item.text().split(",") if kw.strip()]
                if keywords:
                    pad_data[row + 1] = keywords
        self._pad_filter_config.pads = pad_data
        return self._pad_filter_config

    def set_pad_filter(self, pad_filter_config: PadFilterConfig):
        # Disconnect to prevent signal emission during programmatic update
        self.table.itemChanged.disconnect(self._on_item_changed)
        self._pad_filter_config = pad_filter_config

        for row in range(16):
            keywords_item = self.table.item(row, 1)
            if keywords_item:
                keywords_item.setText(", ".join(self._pad_filter_config.pads.get(row + 1, [])))

        self.table.resizeRowsToContents()
        self._adjust_table_height()
        # Reconnect after update
        self.table.itemChanged.connect(self._on_item_changed)
