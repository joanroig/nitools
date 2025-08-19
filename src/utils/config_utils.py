import json
import logging
import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QPushButton

from models.config import Config, ConfigEncoder
from utils.bundle_utils import get_bundled_path
from utils.constants import CONFIG_FILE
from utils.enums import Style
from utils.logger import Logger
from utils.version import CONFIG_VERSION

logger = Logger.get_logger("ConfigUtils", logging.DEBUG)

DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "style": Style.DARK,
}

def migrate_config_data(data: dict) -> dict:

    # Future migrations can be chained like this:
    #
    # original_version = data.get("version", "1.0")
    # if original_version == "1.0":
    #   ...
    return data

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as file:
            json.dump(DEFAULT_CONFIG, file)
    try:
        with open(CONFIG_FILE, 'r') as file:
            config_data = json.load(file)

            # Apply migration logic before creating the Config object
            config_data = migrate_config_data(config_data)

            config = Config(**config_data)
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        error_dialog = QMessageBox()
        error_dialog.setWindowIcon(QIcon(get_bundled_path('img/logos/nitools.png')))
        error_dialog.setIcon(QMessageBox.Icon.Warning)
        error_dialog.setWindowTitle("Configuration Error")
        error_dialog.setText("The configuration file may be corrupted. Please repair or delete the configuration file and reopen the application.")
        error_dialog.setInformativeText(f"Config file location: {CONFIG_FILE}")
        error_dialog.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        open_button = QPushButton("Open Config Location")
        open_button.clicked.connect(lambda: os.startfile(os.path.dirname(CONFIG_FILE)))
        error_dialog.addButton(open_button, QMessageBox.ButtonRole.ActionRole)

        error_dialog.addButton(QMessageBox.StandardButton.Ok)

        error_dialog.setDetailedText(str(e))
        error_dialog.setTextFormat(Qt.TextFormat.PlainText)

        error_dialog.exec()
        sys.exit(0)

def save_config(config: Config):
    try:
        with open(CONFIG_FILE, 'w') as file:
            json.dump(config, file, indent=2, cls=ConfigEncoder)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        logger.error(error)
