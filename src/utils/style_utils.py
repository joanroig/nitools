import os

import qdarktheme

from utils.bundle_utils import get_bundled_path
from utils.config_utils import load_config
from utils.enums import Style


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
    css_file_path = get_bundled_path('resources/style.css')

    additional_qss = ""
    if os.path.exists(css_file_path):
        with open(css_file_path, 'r') as f:
            additional_qss = f.read()

    config = load_config()
    custom_color = config.custom_color
    enable_custom_color = config.enable_custom_color

    custom_colors_dict = {}
    if enable_custom_color:
        custom_colors_dict = {"primary": custom_color}

    if style == Style.AUTO:
        qdarktheme.setup_theme("auto", additional_qss=additional_qss, custom_colors=custom_colors_dict)
    elif style == Style.LIGHT:
        qdarktheme.setup_theme("light", additional_qss=additional_qss, custom_colors=custom_colors_dict)
    elif style == Style.DARK:
        qdarktheme.setup_theme("dark", additional_qss=additional_qss, custom_colors=custom_colors_dict)
