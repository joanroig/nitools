from PyQt6 import QtCore, QtWidgets

from models.config import Config
from utils import config_utils


class ResizableLogSplitter(QtWidgets.QSplitter):
    def __init__(self, config: Config, tabs_widget: QtWidgets.QTabWidget, log_output_widget: QtWidgets.QTextEdit, parent=None):
        super().__init__(QtCore.Qt.Orientation.Vertical, parent)
        self.config = config
        self.tabs_widget = tabs_widget
        self.log_output_widget = log_output_widget

        self.addWidget(self.tabs_widget)
        self.addWidget(self.log_output_widget)

        self.setStretchFactor(0, 3)  # Give tabs more space initially
        self.setStretchFactor(1, 1)  # Give log_output less space initially

        # Load and apply saved splitter sizes
        if self.config.log_panel_sizes:
            self.setSizes(self.config.log_panel_sizes)

        # Connect splitterMoved signal to save sizes
        self.splitterMoved.connect(self.save_log_panel_sizes)

    def save_log_panel_sizes(self):
        self.config.log_panel_sizes = self.sizes()
        config_utils.save_config(self.config)
