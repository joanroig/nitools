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

        # Help button (at the left)
        self.help_button = QtWidgets.QPushButton()
        self.help_button.setIcon(QtGui.QIcon(get_bundled_path("img/icons/question.png")))
        self.help_button.clicked.connect(self._show_help_popup)
        self.help_button.setToolTip("Help")
        layout.addWidget(self.help_button)

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
        self.show_terminal_button.setToolTip("Click to toggle the terminal visibility.")
        layout.addWidget(self.show_terminal_button)

        self.setLayout(layout)

    def _show_help_popup(self):
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Help")
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)

        msg_box.setText(
            "Hover over buttons and elements to see tooltips with explanations.\n"
            "For more details, visit the project's documentation."
        )

        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()
