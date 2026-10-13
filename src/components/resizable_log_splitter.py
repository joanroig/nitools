from PySide6 import QtCore, QtWidgets

from models.config import Config
from utils import config_utils


class ResizableLogSplitter(QtWidgets.QSplitter):
    def __init__(self, config: Config, tabs_widget: QtWidgets.QTabWidget, log_output_widget: QtWidgets.QWidget, parent=None):
        super().__init__(QtCore.Qt.Orientation.Vertical, parent)
        self.setObjectName('exporterSplitter')
        self.config = config
        self.tabs_widget = tabs_widget
        self.log_output_widget = log_output_widget

        self.addWidget(self.tabs_widget)
        self.addWidget(self.log_output_widget)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(8)

        # Extra window space belongs to the form. Saved sizes from older
        # layouts must not let an empty log squeeze the settings out of view.
        self.setStretchFactor(0, 1)
        self.setStretchFactor(1, 0)
        self.log_output_widget.setMaximumHeight(140)

        # Load and apply saved splitter sizes
        log_height = self.config.log_panel_sizes[-1] if self.config.log_panel_sizes else 140
        self.setSizes([540, max(96, min(log_height, 140))])

        # Connect splitterMoved signal to save sizes
        self.splitterMoved.connect(self.save_log_panel_sizes)

    def resizeEvent(self, event):
        # Keep the log readable at small sizes and bounded at larger ones.
        # This also applies when it is shown again after being hidden.
        self.log_output_widget.setMaximumHeight(max(96, self.height() // 4))
        super().resizeEvent(event)
        form_height, log_height = self.sizes()
        limit = self.log_output_widget.maximumHeight()
        if log_height > limit:
            self.setSizes([form_height + log_height - limit, limit])

    def save_log_panel_sizes(self):
        self.config.log_panel_sizes = self.sizes()
        config_utils.save_config(self.config)
