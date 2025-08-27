import logging
import os
import sys
from concurrent_log_handler import ConcurrentRotatingFileHandler as RotatingFileHandler

import colorlog

from utils.constants import LOGS_PATH


class Logger:
    _loggers = {}
    _file_handler = None

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
        self._logger.propagate = False

        # Console handler
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

        # Shared file handler
        if Logger._file_handler is None:
            os.makedirs(LOGS_PATH, exist_ok=True)
            log_file = os.path.join(LOGS_PATH, 'NITools.log')
            Logger._file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8'
            )
            Logger._file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        self._logger.addHandler(Logger._file_handler)

        Logger._loggers[name] = self._logger

        # Unhandled exceptions logging
        sys.excepthook = self.handle_exception

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't log keyboard interrupts
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self._logger.critical("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
