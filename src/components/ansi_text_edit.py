import re

from PyQt6 import QtGui, QtWidgets


class AnsiTextEdit(QtWidgets.QTextEdit):
    ANSI_COLOR_MAP = {
        "30": "black",
        "31": "red",
        "32": "green",
        "33": "yellow",
        "34": "blue",
        "35": "magenta",
        "36": "cyan",
        "37": "white",
        "90": "gray",  # Bright black
        "91": "red",  # Bright red
        "92": "green",  # Bright green
        "93": "yellow",  # Bright yellow
        "94": "blue",  # Bright blue
        "95": "magenta",  # Bright magenta
        "96": "cyan",  # Bright cyan
        "97": "white",  # Bright white
    }

    ANSI_BACKGROUND_COLOR_MAP = {
        "40": "black",
        "41": "red",
        "42": "green",
        "43": "yellow",
        "44": "blue",
        "45": "magenta",
        "46": "cyan",
        "47": "white",
        "100": "gray",  # Bright black
        "101": "red",  # Bright red
        "102": "green",  # Bright green
        "103": "yellow",  # Bright yellow
        "104": "blue",  # Bright blue
        "105": "magenta",  # Bright magenta
        "106": "cyan",  # Bright cyan
        "107": "white",  # Bright white
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QtGui.QFont("Consolas", 10))  # Monospaced font for better log readability

    def append(self, text):
        html_text = self._ansi_to_html(text)
        super().append(html_text)

    def _ansi_to_html(self, ansi_text):
        # Regex to find ANSI escape codes
        ansi_escape = re.compile(r'\x1b\[([0-9;]*)([ABCDHJKSTfmnsu])')

        parts = []
        last_pos = 0
        current_styles = []

        for match in ansi_escape.finditer(ansi_text):
            # Add text before the escape code
            if match.start() > last_pos:
                parts.append(self._apply_styles(ansi_text[last_pos:match.start()], current_styles))

            params = match.group(1).split(';') if match.group(1) else []
            command = match.group(2)

            if command == 'm':  # SGR (Select Graphic Rendition) command
                for param in params:
                    if param == '0':  # Reset all attributes
                        current_styles = []
                    elif param == '1':  # Bold
                        if 'bold' not in current_styles:
                            current_styles.append('bold')
                    elif param == '3':  # Italic (not directly supported by QTextEdit, but can be simulated with <em>)
                        if 'italic' not in current_styles:
                            current_styles.append('italic')
                    elif param == '4':  # Underline
                        if 'underline' not in current_styles:
                            current_styles.append('underline')
                    elif param in self.ANSI_COLOR_MAP:  # Foreground color
                        self._remove_style_type(current_styles, 'color')
                        current_styles.append(f'color:{self.ANSI_COLOR_MAP[param]}')
                    elif param in self.ANSI_BACKGROUND_COLOR_MAP:  # Background color
                        self._remove_style_type(current_styles, 'background-color')
                        current_styles.append(f'background-color:{self.ANSI_BACKGROUND_COLOR_MAP[param]}')

            last_pos = match.end()

        # Add any remaining text after the last escape code
        if last_pos < len(ansi_text):
            parts.append(self._apply_styles(ansi_text[last_pos:], current_styles))

        return ''.join(parts)

    def _apply_styles(self, text, styles):
        if not styles:
            return text

        html_styles = []
        if 'bold' in styles:
            html_styles.append('font-weight:bold')
        if 'italic' in styles:
            html_styles.append('font-style:italic')
        if 'underline' in styles:
            html_styles.append('text-decoration:underline')

        for style in styles:
            if style.startswith('color:') or style.startswith('background-color:'):
                html_styles.append(style)

        style_str = ';'.join(html_styles)
        return f'<span style="{style_str}">{text}</span>'

    def _remove_style_type(self, current_styles, style_type):
        # Remove any existing style of the same type (e.g., only one foreground color at a time)
        for style in list(current_styles):
            if style.startswith(style_type):
                current_styles.remove(style)
