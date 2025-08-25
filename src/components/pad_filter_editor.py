from PyQt6 import QtWidgets


class PadFilterEditor(QtWidgets.QWidget):
    def __init__(self, default_filter, parent=None):
        super().__init__(parent)
        self.pad_select = QtWidgets.QComboBox()
        self.pad_select.addItems([str(i) for i in range(1, 17)])
        self.keyword_list = QtWidgets.QListWidget()
        self.keyword_input = QtWidgets.QLineEdit()
        self.add_btn = QtWidgets.QPushButton('Add')
        self.remove_btn = QtWidgets.QPushButton('Remove Selected')
        self.pad_filters = {i: default_filter.get(i, [])[:] for i in range(1, 17)}
        self.pad_select.currentIndexChanged.connect(self.load_pad_keywords)
        self.add_btn.clicked.connect(self.add_keyword)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.load_pad_keywords()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('Pad (1-16):'))
        layout.addWidget(self.pad_select)
        layout.addWidget(QtWidgets.QLabel('Keywords:'))
        layout.addWidget(self.keyword_list)
        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addWidget(self.keyword_input)
        hlayout.addWidget(self.add_btn)
        layout.addLayout(hlayout)
        layout.addWidget(self.remove_btn)
        self.setLayout(layout)

    def load_pad_keywords(self):
        pad = int(self.pad_select.currentText())
        self.keyword_list.clear()
        for kw in self.pad_filters.get(pad, []):
            self.keyword_list.addItem(kw)

    def add_keyword(self):
        pad = int(self.pad_select.currentText())
        kw = self.keyword_input.text().strip()
        if kw:
            self.pad_filters.setdefault(pad, []).append(kw)
            self.keyword_input.clear()
            self.load_pad_keywords()

    def remove_selected(self):
        pad = int(self.pad_select.currentText())
        selected = self.keyword_list.selectedItems()
        for item in selected:
            self.pad_filters[pad].remove(item.text())
        self.load_pad_keywords()

    def get_pad_filter(self):
        return {pad: kws for pad, kws in self.pad_filters.items() if kws}
