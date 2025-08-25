from PyQt6 import QtWidgets

class MatrixEditor(QtWidgets.QWidget):
    def __init__(self, default_matrix, parent=None):
        super().__init__(parent)

        self.grid = []
        main_layout = QtWidgets.QVBoxLayout()
        for row in range(4):
            row_layout = QtWidgets.QHBoxLayout()
            row_widgets = []
            for col in range(4):
                pad_num = row * 4 + col + 1
                container = QtWidgets.QWidget()
                container_layout = QtWidgets.QHBoxLayout()
                container_layout.setContentsMargins(0, 0, 0, 0)
                label = QtWidgets.QLabel(f"Pad {pad_num:02d} → ")
                spin = QtWidgets.QSpinBox()
                spin.setRange(1, 16)
                spin.setValue(default_matrix.get(pad_num, pad_num))
                container_layout.addWidget(label)
                container_layout.addWidget(spin)
                container_layout.addWidget(QtWidgets.QLabel(" "))
                container.setLayout(container_layout)
                row_layout.addWidget(container)
                row_widgets.append(spin)
            self.grid.append(row_widgets)
            main_layout.addLayout(row_layout)
        self.setLayout(main_layout)

    def get_matrix(self):
        matrix = {}
        for row in range(4):
            for col in range(4):
                pad_num = row * 4 + col + 1
                matrix[pad_num] = self.grid[row][col].value()
        return matrix
