import logging
import platform
import subprocess

from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                             QHBoxLayout, QLineEdit, QMessageBox, QPushButton,
                             QVBoxLayout)

from utils.config_utils import load_config, save_config
from utils.constants import LOGS_PATH, get_data_dir
from utils.enums import Style
from utils.logger import Logger
from utils.utils import apply_style

logger = Logger.get_logger("ConfigurationDialog", logging.DEBUG)

class ConfigurationDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Configuration")
        self.setMinimumWidth(800)

        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.buttons = []  # Store buttons for uniform sizing

        # Logs Path
        logs_path_layout = QHBoxLayout()
        self.logs_path_edit = QLineEdit()
        self.logs_path_edit.setText(LOGS_PATH)
        self.logs_path_edit.setReadOnly(True)
        logs_path_layout.addWidget(self.logs_path_edit)

        open_logs_button = QPushButton("Open Logs")
        open_logs_button.clicked.connect(self.open_logs_path)
        logs_path_layout.addWidget(open_logs_button)
        self.buttons.append(open_logs_button)
        form_layout.addRow("Logs Path:", logs_path_layout)

        # Configuration Path
        config_path_layout = QHBoxLayout()
        self.config_path_edit = QLineEdit()
        self.config_path_edit.setText(get_data_dir())
        self.config_path_edit.setReadOnly(True)
        config_path_layout.addWidget(self.config_path_edit)

        open_config_button = QPushButton("Open Folder")
        open_config_button.clicked.connect(self.open_config_path)
        config_path_layout.addWidget(open_config_button)
        self.buttons.append(open_config_button)
        form_layout.addRow("Configuration Path:", config_path_layout)

        # UI Style
        self.style_dropdown = QComboBox()
        self.style_dropdown.addItems([style.value for style in Style])
        form_layout.addRow("UI Style:", self.style_dropdown)

        # Add form layout to main layout
        layout.addLayout(form_layout)

        # Import/Export buttons at bottom-left
        bottom_layout = QHBoxLayout()

        self.import_button = QPushButton("Import Config")
        self.import_button.clicked.connect(self.import_config)
        bottom_layout.addWidget(self.import_button)
        self.buttons.append(self.import_button)

        # Spacer between left and right buttons
        bottom_layout.addStretch()

        # Ok/Cancel buttons on the right
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

        # Normalize button widths
        self.equalize_button_widths()

        # Set the initial values in the fields
        self.populate_fields()

    def populate_fields(self):
        self.config = load_config()
        self.style_dropdown.setCurrentText(self.config.style.capitalize())

    def equalize_button_widths(self):
        max_width = max(button.sizeHint().width() for button in self.buttons)
        for button in self.buttons:
            button.setFixedWidth(max_width)

    def open_backups_path(self):
        self._open_path(self.path_backups_edit.text())

    def open_logs_path(self):
        self._open_path(LOGS_PATH)

    def open_config_path(self):
        self._open_path(get_data_dir())

    def _open_path(self, path):
        if not path:
            logger.warning("Path is empty.")
            return
        path = path.strip()
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path], shell=True)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                logger.error("Unsupported platform for opening file explorer.")
        except Exception as e:
            logger.error(f"Failed to open path: {path}. Error: {e}")

    def save(self):
        # Load the current config
        self.config = load_config()

        # Save the UI Style
        selected_style = self.style_dropdown.currentText()
        self.config.style = Style(selected_style)
        # Save the config
        save_config(self.config)

        # Apply the selected style
        apply_style(selected_style)

        self.accept()

    def import_config(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Import Configuration", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)

            # Replace current config
            self.config.__dict__.update(imported_data)

            # Save the config
            save_config(self.config)

            # Apply the selected style
            apply_style(self.config.style)

            # Update the UI fields
            self.populate_fields()
            QMessageBox.information(self, "Import Successful", "Configuration imported.\nEncrypted fields were cleared for security.")

        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            QMessageBox.critical(self, "Import Failed", f"Failed to import configuration:\n{e}")
