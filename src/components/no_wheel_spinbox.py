from PyQt6 import QtGui, QtWidgets


class NoWheelSpinBox(QtWidgets.QSpinBox):
    """
    A QSpinBox subclass that ignores wheel events.
    """

    def wheelEvent(self, event: QtGui.QWheelEvent):
        # Ignore wheel events to prevent changing the value with the scroll wheel
        event.ignore()
