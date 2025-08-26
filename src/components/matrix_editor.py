from PyQt6 import QtCore, QtWidgets
from components.no_wheel_spinbox import NoWheelSpinBox
from models.matrix_config import MatrixConfig


class MatrixEditor(QtWidgets.QWidget):
    matrix_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = []
        main_layout = QtWidgets.QVBoxLayout()
        for row in range(4):
            row_layout = QtWidgets.QHBoxLayout()
            row_widgets = [self._create_pad_widget(row, col, row_layout) for col in range(4)]
            self.grid.append(row_widgets)
            main_layout.addLayout(row_layout)
        self.setLayout(main_layout)

    def _create_pad_widget(self, row, col, parent_layout):
        pad_num = row * 4 + col + 1
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QtWidgets.QLabel(f"Pad {pad_num:02d} → ")
        spin = NoWheelSpinBox()
        spin.setRange(1, 16)
        spin.valueChanged.connect(self.matrix_changed.emit)

        layout.addWidget(label)
        layout.addWidget(spin)
        layout.addWidget(QtWidgets.QLabel(" "))  # spacer

        parent_layout.addWidget(container)
        return spin

    def get_matrix(self) -> MatrixConfig:
        for row in range(4):
            for col in range(4):
                pad_num = row * 4 + col + 1
                self._matrix_config.pads[pad_num] = self.grid[row][col].value()
        return self._matrix_config

    def set_matrix(self, matrix_config: MatrixConfig):
        self._matrix_config = matrix_config
        for row in range(4):
            for col in range(4):
                spin = self.grid[row][col]
                # Block signals to prevent triggering matrix_changed during programmatic update
                spin.blockSignals(True)
                pad_num = row * 4 + col + 1
                spin.setValue(self._matrix_config.pads.get(pad_num, pad_num))
                spin.blockSignals(False)
