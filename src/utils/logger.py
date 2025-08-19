import logging
import os
from logging.handlers import RotatingFileHandler

import colorlog

from utils.constants import LOGS_PATH


class Logger:
    _loggers = {}  # Dictionary to hold loggers by name

    @staticmethod
    def get_logger(name="default", level=logging.INFO) -> logging.Logger:
        """Static method to get (or create) a logger by name."""
        if name not in Logger._loggers:
            Logger._loggers[name] = Logger(name, level)._logger  # Create and store the logger
        return Logger._loggers[name]

    def __init__(self, name, level=logging.INFO):
        if name in Logger._loggers:
            raise Exception(f"Logger with name '{name}' already exists. Use get_logger().")

        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        self._logger.addHandler(ch)

        if not os.path.exists(LOGS_PATH):
            os.makedirs(LOGS_PATH)

        # File handler with rotation
        fh = RotatingFileHandler(os.path.join(LOGS_PATH, 'NITools.log'), maxBytes=1024 * 1024, backupCount=5)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(fh)

        # Store the logger in the dictionary
        Logger._loggers[name] = self._logger
