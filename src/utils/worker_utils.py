import logging

from PyQt6 import QtCore


class QtSignalHandler(logging.Handler, QtCore.QObject):
    """
    A logging handler that emits log records as a PyQt signal,
    adding ANSI escape codes for colored output based on log level.
    """
    log_signal = QtCore.pyqtSignal(str)

    # ANSI color codes for different log levels
    ANSI_COLORS = {
        'DEBUG': '\x1b[36m',    # Cyan
        'INFO': '\x1b[32m',     # Green
        'WARNING': '\x1b[33m',  # Yellow
        'ERROR': '\x1b[31m',    # Red
        'CRITICAL': '\x1b[1;31m'  # Bold Red
    }
    RESET_COLOR = '\x1b[0m'  # ANSI reset code

    def __init__(self, parent=None):
        super().__init__()
        QtCore.QObject.__init__(self, parent)
        # Use a standard formatter to get the basic log message (level: message)
        self.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

    def emit(self, record):
        # Get the formatted message from the base handler's formatter
        formatted_message = self.format(record)

        # Apply ANSI color based on log level
        level_name = record.levelname
        ansi_prefix = self.ANSI_COLORS.get(level_name, '')

        # Emit the ANSI-colored message, ensuring it's reset at the end
        self.log_signal.emit(f"{ansi_prefix}{formatted_message}{self.RESET_COLOR}")


class WorkerThread(QtCore.QThread):
    output_signal = QtCore.pyqtSignal(str)
    finished_signal = QtCore.pyqtSignal(int)

    def __init__(self, target_callable, kwargs, logger_name=None):
        super().__init__()
        self.target_callable = target_callable
        self.kwargs = kwargs
        self.logger_name = logger_name
        self._cancel_requested = False  # New cancellation flag

    def request_cancel(self):
        """Sets the cancellation flag."""
        self._cancel_requested = True

    def cancel_requested(self):
        """Checks if cancellation has been requested."""
        return self._cancel_requested

    def run(self):
        return_code = 1  # Assume failure by default
        handler = None
        target_logger = None
        original_level = None

        if self.logger_name:
            target_logger = logging.getLogger(self.logger_name)
            handler = QtSignalHandler()
            handler.log_signal.connect(self.output_signal)
            target_logger.addHandler(handler)
            original_level = target_logger.level
            target_logger.setLevel(logging.INFO)  # Capture INFO and above messages

        try:
            # Pass the worker instance itself to the target callable
            # so it can check for cancellation requests.
            self.kwargs['worker_instance'] = self
            result = self.target_callable(**self.kwargs)
            if isinstance(result, int):
                return_code = result
            else:
                return_code = 0
        except Exception as e:
            # If an exception occurs, ensure it's logged to the GUI
            if target_logger:
                target_logger.exception("An unexpected error occurred in worker thread.")
            else:
                self.output_signal.emit(f"An unexpected error occurred in worker: {e}\n")
            return_code = 1
        finally:
            if target_logger and handler:
                target_logger.removeHandler(handler)
                target_logger.setLevel(original_level)  # Restore original logger level
            self.finished_signal.emit(return_code)
