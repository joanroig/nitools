import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMessageBox

from utils.constants import LOGS_PATH
from utils.dialog_utils import open_path


class ExportCompleteDialog(QMessageBox):
    def __init__(self, parent=None, output_folder=None, log_content=None, title="Export Complete", message="Export process finished."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(message)
        self.setIcon(QMessageBox.Icon.Information)

        self.output_folder = output_folder
        self.log_content = log_content

        open_folder_button = self.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        open_logs_button = self.addButton("Open Logs", QMessageBox.ButtonRole.ActionRole)
        ok_button = self.addButton(QMessageBox.StandardButton.Ok)

        # Disconnect the default auto-close behavior for custom buttons
        try:
            open_folder_button.clicked.disconnect()
        except TypeError:
            pass
        try:
            open_logs_button.clicked.disconnect()
        except TypeError:
            pass

        open_folder_button.clicked.connect(self._open_folder)
        open_logs_button.clicked.connect(self._open_logs)
        ok_button.clicked.connect(self.accept)

        self.exec()

    def _open_folder(self):
        if self.output_folder and os.path.isdir(self.output_folder):
            open_path(self.output_folder)
        else:
            QMessageBox.warning(self, "Error", "Export folder not found.")

    def _open_logs(self):
        log_file_path = os.path.join(LOGS_PATH, 'NITools.log')
        if os.path.exists(log_file_path):
            open_path(log_file_path)
        else:
            QMessageBox.information(self, "No Logs", "No log file available.")


def show_export_complete_dialog(parent, output_folder, log_content, title="Export Complete", message="Export process finished."):
    QtWidgets.QApplication.instance().beep()
    ExportCompleteDialog(parent, output_folder, log_content, title, message)
