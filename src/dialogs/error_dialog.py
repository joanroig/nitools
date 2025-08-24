import os
import platform
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QPushButton

from utils.bundle_utils import get_bundled_path
from utils.constants import LOGS_PATH


class ErrorDialog(QMessageBox):
    """
    A custom QMessageBox for displaying application errors with consistent styling
    and optional features like opening a file location.
    """

    def __init__(self, parent=None, title="Error", message="", informative_text="", detailed_text="", icon=QMessageBox.Icon.Warning, buttons=QMessageBox.StandardButton.Ok):
        super().__init__(icon, title, message, buttons, parent)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if informative_text:
            self.setInformativeText(informative_text)
        if detailed_text:
            self.setDetailedText(detailed_text)
            self.setTextFormat(Qt.TextFormat.PlainText)

        # Set window icon for the dialog itself
        app_icon_path = get_bundled_path('img/logos/nitools.png')
        if app_icon_path:
            self.setWindowIcon(QIcon(app_icon_path))

        self.add_open_log_button()

    def add_open_location_button(self, path):
        open_button = QPushButton("Open Location")
        self.addButton(open_button, QMessageBox.ButtonRole.NoRole)

        # Disconnect the default auto-close behavior
        try:
            open_button.clicked.disconnect()
        except TypeError:
            pass

        # Connect custom slot
        open_button.clicked.connect(lambda: self._open_path(path))

    def add_open_log_button(self):
        log_file_path = os.path.join(LOGS_PATH, 'NITools.log')
        if os.path.exists(log_file_path):
            open_log_button = QPushButton("Open Log File")
            self.addButton(open_log_button, QMessageBox.ButtonRole.ActionRole)

            # Disconnect the default auto-close behavior
            try:
                open_log_button.clicked.disconnect()
            except TypeError:
                pass

            # Connect custom slot
            open_log_button.clicked.connect(lambda: self._open_path(log_file_path))

    def _open_path(self, path):
        """
        Internal helper to open a given path using the appropriate system command.
        """
        if not path:
            return
        path = path.strip()
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                # Fallback for Linux/other Unix-like systems
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"Failed to open path: {path}. Error: {e}")
