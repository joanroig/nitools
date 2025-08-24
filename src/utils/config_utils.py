import json
import logging
import os
import sys

from PyQt6.QtWidgets import QMessageBox

from dialogs.error_dialog import ErrorDialog
from models.config import Config
from utils.constants import CONFIG_FILE
from utils.logger import Logger

logger = Logger.get_logger("ConfigUtils", logging.DEBUG)

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
            file.write(Config().model_dump_json(indent=2))
    try:
        with open(CONFIG_FILE, 'r') as file:
            config_data = json.load(file)

            # Apply migration logic before creating the Config object
            config_data = migrate_config_data(config_data)

            config = Config(**config_data)
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        error_dialog = ErrorDialog(
            title="Configuration Error",
            message="The configuration file may be corrupted. Please repair or delete the configuration file and reopen the application.",
            informative_text=f"Config file location: {CONFIG_FILE}",
            detailed_text=str(e),
            icon=QMessageBox.Icon.Warning
        )
        error_dialog.add_open_location_button(os.path.dirname(CONFIG_FILE))

        error_dialog.exec()
        sys.exit(0)

def save_config(config: Config):
    try:
        with open(CONFIG_FILE, 'w') as file:
            file.write(config.model_dump_json(indent=2))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        logger.error(error)
