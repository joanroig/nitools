import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import colorlog

from utils.constants import LOGS_PATH


class Logger:
    _loggers = {}  # Store loggers by name

    @staticmethod
    def get_logger(name="default", level=logging.INFO) -> logging.Logger:
        if name not in Logger._loggers:
            Logger._loggers[name] = Logger(name, level)._logger
        return Logger._loggers[name]

    def __init__(self, name, level=logging.INFO):
        if name in Logger._loggers:
            self._logger = Logger._loggers[name]
            return

        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.propagate = False  # Avoid duplicate logs if root logger exists

        # Colored console handler
        formatter_console = colorlog.ColoredFormatter(
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
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter_console)
        self._logger.addHandler(ch)

        # Ensure logs directory exists
        os.makedirs(LOGS_PATH, exist_ok=True)

        # Rotating file handler (larger maxBytes, avoid locking)
        log_file = os.path.join(LOGS_PATH, 'NITools.log')
        fh = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
            encoding='utf-8',  # Always specify encoding
            delay=True
        )
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self._logger.addHandler(fh)

        Logger._loggers[name] = self._logger

        # Unhandled exceptions logging
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self._logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
