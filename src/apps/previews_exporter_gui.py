import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets


class PreviewsExporterGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Previews Exporter")

        icon_path = self.get_asset_path('logos/previews.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        self.setLayout(QtWidgets.QVBoxLayout())
        label = QtWidgets.QLabel("Previews Exporter GUI - Work in Progress")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout().addWidget(label)
        self.resize(500, 300)

    def get_asset_path(self, asset_name):
        # Assets are in ../../img relative to this script
        base_path = os.path.dirname(__file__)
        return os.path.abspath(os.path.join(base_path, '..', '..', 'img', asset_name))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = PreviewsExporterGUI()
    gui.show()
    sys.exit(app.exec())
