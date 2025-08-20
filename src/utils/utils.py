import re
import uuid
from datetime import datetime

from utils.enums import Style
import qdarktheme


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

def set_font_properties(widget, point_size=None, bold=None, italic=None):
    """
    Sets font properties for a given widget.
    Args:
        widget (QtWidgets.QWidget): The widget whose font is to be modified.
        point_size (int, optional): The font size in points. Defaults to None.
        bold (bool, optional): Whether the font should be bold. Defaults to None.
        italic (bool, optional): Whether the font should be italic. Defaults to None.
    """
    font = widget.font()
    if point_size is not None:
        font.setPointSize(point_size)
    if bold is not None:
        font.setBold(bold)
    if italic is not None:
        font.setItalic(italic)
    widget.setFont(font)

def apply_style(style):
    if style == Style.AUTO:
        qdarktheme.setup_theme("auto")
    elif style == Style.LIGHT:
        qdarktheme.setup_theme("light")
    elif style == Style.DARK:
        qdarktheme.setup_theme("dark")
