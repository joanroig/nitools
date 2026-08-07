from PyQt6 import QtGui, QtWidgets


class NoWheelComboBox(QtWidgets.QComboBox):
    """A QComboBox subclass that ignores mouse wheel events."""

    def wheelEvent(self, event: QtGui.QWheelEvent):
        # Ignore wheel events to prevent changing the value with the scroll wheel
        event.ignore()
