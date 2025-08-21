from PyQt6 import QtCore, QtGui, QtWidgets

from components.version_label import VersionLabel
from utils.bundle_utils import get_bundled_path


class BottomBanner(QtWidgets.QWidget):
    terminal_toggled = QtCore.pyqtSignal(bool)

    def __init__(self, initial_terminal_state, parent=None):
        super().__init__(parent)
        self.initial_terminal_state = initial_terminal_state
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Left spacer (nothing at the left)
        layout.addStretch(1)

        # Version Label (in the middle)
        version = VersionLabel()
        layout.addWidget(version)

        # Right spacer
        layout.addStretch(1)

        # Terminal button (at the right)
        self.show_terminal_button = QtWidgets.QPushButton()
        self.show_terminal_button.setIcon(QtGui.QIcon(get_bundled_path("img/icons/terminal.png")))
        self.show_terminal_button.setCheckable(True)
        self.show_terminal_button.setChecked(self.initial_terminal_state)
        self.show_terminal_button.toggled.connect(self.terminal_toggled.emit)
        layout.addWidget(self.show_terminal_button)

        self.setLayout(layout)
