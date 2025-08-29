from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from utils.style_utils import set_font_properties
from utils.version import APP_VERSION_TEXT


class VersionLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText(APP_VERSION_TEXT)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(False)
        self.setOpenExternalLinks(True)
        set_font_properties(self, point_size=8)
