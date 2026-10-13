"""A compact progress window whose geometry never follows changing filenames."""

from PySide6 import QtCore, QtWidgets


class ProgressDialog(QtWidgets.QDialog):
    canceled = QtCore.Signal()

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Please wait')
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setSizeGripEnabled(False)
        self._message = ''
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.label = QtWidgets.QLabel()
        self.label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
        self.label.setFixedHeight(self.fontMetrics().lineSpacing() * 2 + 4)
        layout.addWidget(self.label)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.setFixedSize(max(480, self.fontMetrics().horizontalAdvance('M') * 40), layout.sizeHint().height())
        layout.activate()
        self.setLabelText(message)

    def setLabelText(self, message):
        self._message = message
        lines = message.splitlines()
        if len(lines) > 2:
            lines = [lines[0], ' · '.join(lines[1:])]
        self.label.setText('\n'.join(self.label.fontMetrics().elidedText(
            line, QtCore.Qt.TextElideMode.ElideMiddle, self.label.width()) for line in lines))
        self.label.setToolTip(message)

    def labelText(self):
        return self._message

    def setRange(self, minimum, maximum):
        self.bar.setRange(minimum, maximum)

    def setValue(self, value):
        self.bar.setValue(value)

    def maximum(self):
        return self.bar.maximum()

    def value(self):
        return self.bar.value()

    def set_cancelling(self):
        self.cancel_button.setEnabled(False)
        self.setLabelText('Cancelling…\nFinishing active file operations.')

    def reject(self):
        # Escape and the title-bar close button request cancellation too. Keep
        # the window visible until the worker has actually released its files.
        if self.cancel_button.isEnabled():
            self.canceled.emit()
