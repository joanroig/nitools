import logging
import os
import sys
import traceback
import webbrowser

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QSharedMemory, Qt  # Add QSharedMemory
from PyQt6.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)

from apps.groups_exporter_gui import GroupsExporterGUI
from apps.previews_exporter_gui import PreviewsExporterGUI
from components.version_label import VersionLabel
from dialogs.configuration_dialog import ConfigurationDialog
from utils import logger
from utils.bundle_utils import get_bundled_path
from utils.logger import Logger


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NITools")

        self.resize(460, 480)
        self.setMinimumSize(460, 480)
        self.setMaximumSize(460, 480)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        self.tool_windows = []

        self.init_ui()

    def init_ui(self):
        # Create a top header container for the config button and centered title
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Add config button to the far left
        config_button = self._create_config_button()
        header_layout.addWidget(config_button)

        # Add a stretch to push the title to the center
        header_layout.addStretch()

        # Add the centered title widget
        centered_title_widget = self._create_centered_title_widget()
        header_layout.addWidget(centered_title_widget)

        # Add another stretch to keep the title centered
        header_layout.addStretch()

        # Add a fixed-width spacer to balance the config button on the left
        # The width should ideally match the config_button's effective width
        dummy_spacer_width = config_button.sizeHint().width()
        header_layout.addSpacerItem(QtWidgets.QSpacerItem(dummy_spacer_width, 0, QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Minimum))

        self.layout.addWidget(header_widget)  # Add the new header widget to the main layout
        self.layout.addSpacing(10)

        self._create_tool_buttons()

        self.layout.addStretch()

        self.layout.addWidget(self._create_bottom_banner())

        version = VersionLabel()
        self.layout.addWidget(version)

    def _create_centered_title_widget(self):
        # --- Title at the top ---
        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(10)

        title_image_label = QtWidgets.QLabel()
        icon_path = get_bundled_path('img/logos/nitools.png')
        if os.path.exists(icon_path):
            pixmap = QtGui.QPixmap(icon_path).scaled(48, 48, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                     QtCore.Qt.TransformationMode.SmoothTransformation)
            title_image_label.setPixmap(pixmap)
        title_layout.addWidget(title_image_label)

        title_text_layout = QtWidgets.QVBoxLayout()
        title_text_layout.setSpacing(2)
        title_label = QtWidgets.QLabel("NITools Launcher")
        font = title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        title_label.setFont(font)

        subtitle_label = QtWidgets.QLabel("Unofficial tools to convert NI resources")
        subtitle_font = subtitle_label.font()
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("font-style: italic; color: gray;")

        title_text_layout.addWidget(title_label)
        title_text_layout.addWidget(subtitle_label)
        title_layout.addLayout(title_text_layout)

        return title_container

    def _create_tool_buttons(self):
        # --- Tool Buttons ---
        self.groups_button = self.create_tool_button(
            "Groups Exporter",
            "Export Maschine groups, i.e. to be used with SP 404 MK2",
            get_bundled_path('img/logos/groups.png'),
            self.launch_groups_exporter
        )
        self.layout.addWidget(self.groups_button)

        self.previews_button = self.create_tool_button(
            "Previews Exporter",
            "Gather and export all NKS audio previews as .wav files",
            get_bundled_path('img/logos/previews.png'),
            self.launch_previews_exporter
        )
        self.layout.addWidget(self.previews_button)

        self.kits_button = self.create_tool_button(
            "Kits Exporter",
            "Battery Kits exporter, work in progress...",
            get_bundled_path('img/logos/kits.png'),
            None
        )
        self.kits_button.setEnabled(False)
        self.kits_button.setToolTip("This feature is not yet implemented.")

        self.layout.addWidget(self.kits_button)

    def _create_bottom_banner(self):
        # --- Bottom banner ---
        banner = QtWidgets.QFrame()
        banner.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        banner_layout = QtWidgets.QHBoxLayout(banner)
        banner_layout.setContentsMargins(15, 10, 15, 10)
        banner_layout.setSpacing(10)

        creator_label = QtWidgets.QLabel("Follow and stream to support me •ᴗ•")
        creator_label.setStyleSheet("font-weight: bold;")
        banner_layout.addWidget(creator_label)
        banner_layout.addStretch()  # Add growing space here

        # Clickable icons
        for name, url, icon_file in [
            ("Spotify", "https://open.spotify.com/artist/5Zt96vfBQXmUB3fs3Qkm5q", "img/icons/spotify.png"),
            ("Apple Music", "https://music.apple.com/es/artist/moai-beats/1466043534", "img/icons/applemusic.png"),
            ("YouTube", "http://youtube.com/moaibeats?sub_confirmation=1", "img/icons/youtube.png"),
            ("Bandcamp", "https://moaibeats.bandcamp.com", "img/icons/bandcamp.png")
        ]:
            btn = QtWidgets.QPushButton()
            btn.setToolTip(f"Listen on {name}")
            icon_path = get_bundled_path(icon_file)
            if os.path.exists(icon_path):
                btn.setIcon(QtGui.QIcon(icon_path))
                btn.setIconSize(QtCore.QSize(32, 32))
            btn.setFlat(True)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            # Make buttons circular and hide default style
            btn.setStyleSheet("border-radius: 12px; background-color: transparent;")
            btn.clicked.connect(lambda checked, url=url: webbrowser.open(url))
            banner_layout.addWidget(btn)

        banner_layout.addStretch()
        return banner

    def create_tool_button(self, title, description, icon_path, on_click):
        button = QtWidgets.QPushButton()
        button.setMinimumHeight(70)
        button.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))

        layout = QtWidgets.QHBoxLayout(button)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        icon_label = QtWidgets.QLabel()
        if os.path.exists(icon_path):
            pixmap = QtGui.QPixmap(icon_path).scaled(48, 48, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                     QtCore.Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(1)  # reduce vertical spacing between title & subtitle
        title_label = QtWidgets.QLabel(title)
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)

        description_label = QtWidgets.QLabel(description)
        desc_font = description_label.font()
        desc_font.setPointSize(9)
        description_label.setFont(desc_font)
        description_label.setStyleSheet("font-style: italic;")

        text_layout.addWidget(title_label)
        text_layout.addWidget(description_label)
        layout.addLayout(text_layout)

        layout.addStretch()

        arrow_icon_label = QtWidgets.QLabel()
        # Use custom arrow icon
        arrow_icon_path = get_bundled_path('img/icons/arrow-right.png')
        if os.path.exists(arrow_icon_path):
            arrow_pixmap = QtGui.QPixmap(arrow_icon_path).scaled(24, 24, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                                                 QtCore.Qt.TransformationMode.SmoothTransformation)
            arrow_icon_label.setPixmap(arrow_pixmap)

        layout.addWidget(arrow_icon_label)

        if on_click:
            button.clicked.connect(on_click)

        return button

    def _create_config_button(self):
        config_btn = QtWidgets.QPushButton()
        config_btn.setToolTip("Open Configuration")
        icon_path = get_bundled_path('img/icons/cog.png')
        if os.path.exists(icon_path):
            config_btn.setIcon(QtGui.QIcon(icon_path))
            config_btn.setIconSize(QtCore.QSize(24, 24))  # Adjust size as needed
        config_btn.setFlat(True)
        config_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        config_btn.setStyleSheet("border-radius: 12px; background-color: transparent;")
        config_btn.clicked.connect(self.launch_config)  # Connect to a new method for config
        return config_btn

    def launch_tool(self, tool_class):
        tool_window = tool_class()
        self.tool_windows.append(tool_window)
        tool_window.show()

    def launch_groups_exporter(self):
        self.launch_tool(GroupsExporterGUI)

    def launch_previews_exporter(self):
        self.launch_tool(PreviewsExporterGUI)

    def launch_config(self):
        dialog = ConfigurationDialog(self)
        dialog.exec()

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error_msg = f"An unexpected error occurred:\n{exc_value}"
    trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(trace)

    try:
        if QApplication.instance() is not None:
            error_dialog = QMessageBox(None)
            error_dialog.setWindowTitle("Unexpected Error")
            error_dialog.setIcon(QMessageBox.Icon.Warning)

            # Main message
            error_dialog.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            error_dialog.setText(error_msg)

            # Expandable traceback
            if trace:
                error_dialog.setDetailedText(trace)
                error_dialog.setTextFormat(Qt.TextFormat.PlainText)

            error_dialog.exec()

    except Exception as dialog_error:
        logger.error(f"Failed to show error dialog: {dialog_error}")


def main():
    sys.excepthook = handle_exception
    app = QtWidgets.QApplication(sys.argv)

    # Single instance check
    unique_key = "NIToolsLauncherSingleInstance"
    app.shared_memory = QSharedMemory(unique_key)  # Store on app to keep it alive

    icon_path = get_bundled_path('img/logos/nitools.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))

    if app.shared_memory.attach():
        # Another instance is running
        QMessageBox.warning(None, "NITools Launcher", "NITools Launcher is already running.")
        sys.exit(0)
    else:
        # No other instance, try to create it
        if not app.shared_memory.create(1):  # Create a segment of 1 byte
            # Failed to create, possibly due to permissions or another race condition
            QMessageBox.critical(None, "NITools Launcher", "Could not start NITools Launcher. Another instance might be starting or there's a permission issue.")
            sys.exit(1)

    main_window = MainGUI()
    main_window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
