import re
import uuid
from datetime import datetime

from PyQt6 import QtGui
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from utils.enums import Style


def unique_id():
    """Get unique ID"""
    return uuid.uuid4().hex

def sanitize(path):
    """Replace all characters other than letters and numbers with underscores"""
    sanitized_path = re.sub(r'[^a-zA-Z0-9]', '_', path)
    return sanitized_path

def get_current_datetime():
    """Returns the current datetime formatted as YYYY_MM_DD_HH_MM."""
    return datetime.now().strftime('%Y_%m_%d_%H_%M')

def apply_style(style):
    if style == Style.LIGHT:
        QApplication.setStyle("windowsvista")
        light_palette = QtGui.QPalette()
        light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(255, 255, 255))
        light_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(0, 0, 0))
        QApplication.setPalette(light_palette)
    elif style == Style.DARK:
        QApplication.setStyle("Fusion")
        dark_palette = QtGui.QPalette()

        # Normal colors
        dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(40, 44, 52))
        dark_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(220, 220, 220))
        dark_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(30, 34, 40))
        dark_palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(44, 49, 60))
        dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(255, 255, 220))
        dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(0, 0, 0))
        dark_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(220, 220, 220))
        dark_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53, 53, 53))
        dark_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(220, 220, 220))
        dark_palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(255, 0, 0))
        dark_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(19, 64, 108))
        dark_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))

        # Disabled colors
        dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Button, QtGui.QColor(80, 80, 80))
        dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(130, 130, 130))
        dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor(130, 130, 130))
        dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(130, 130, 130))
        QApplication.setPalette(dark_palette)
