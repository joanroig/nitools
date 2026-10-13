"""Compact activity card shared by all exporter windows."""

from PySide6 import QtCore, QtWidgets


class ActivityPanel(QtWidgets.QFrame):
    def __init__(self, log_output, parent=None):
        super().__init__(parent)
        self.setObjectName('activityPanel')
        self.setMinimumHeight(96)
        self.log_output = log_output
        self.busy = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        toolbar = QtWidgets.QFrame()
        toolbar.setObjectName('activityToolbar')
        row = QtWidgets.QHBoxLayout(toolbar)
        row.setContentsMargins(10, 5, 10, 5)
        row.setSpacing(8)
        title = QtWidgets.QLabel('Activity')
        title.setProperty('class', 'section-title')
        self.status = QtWidgets.QLabel('Ready')
        self.status.setObjectName('activityStatus')
        self.count = QtWidgets.QLabel()
        self.count.setObjectName('activityCount')
        row.addWidget(title)
        row.addWidget(self.status)
        row.addWidget(self.count)
        row.addStretch()

        self.follow_button = QtWidgets.QToolButton()
        self.follow_button.setText('Follow')
        self.follow_button.setCheckable(True)
        self.follow_button.setChecked(True)
        self.follow_button.setToolTip('Follow new messages. Scrolling back pauses following; click to jump to the latest.')
        self.follow_button.toggled.connect(log_output.set_follow_output)
        log_output.follow_changed.connect(self.follow_button.setChecked)
        self.copy_button = QtWidgets.QToolButton()
        self.copy_button.setText('Copy')
        self.copy_button.setToolTip('Copy the retained log as plain text')
        self.copy_button.clicked.connect(self.copy_log)
        self.clear_button = QtWidgets.QToolButton()
        self.clear_button.setText('Clear')
        self.clear_button.setToolTip('Clear the visible log')
        self.clear_button.clicked.connect(log_output.clear)
        self.open_button = QtWidgets.QToolButton()
        self.open_button.setText('Open log…')
        self.open_button.setToolTip('Read the log in a larger, resizable window')
        self.open_button.clicked.connect(self.open_log)
        for button in (self.follow_button, self.copy_button, self.clear_button, self.open_button):
            row.addWidget(button)
        layout.addWidget(toolbar)

        self.pages = QtWidgets.QStackedWidget()
        self.pages.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Ignored)
        self.empty = QtWidgets.QWidget()
        empty_layout = QtWidgets.QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(12, 6, 12, 6)
        empty_layout.setSpacing(3)
        empty_layout.addStretch()
        heading = QtWidgets.QLabel('No activity yet')
        heading.setProperty('class', 'section-title')
        hint = QtWidgets.QLabel('Process a library or export audio to see progress here.')
        for label in (heading, hint):
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(label)
        empty_layout.addStretch()
        self.pages.addWidget(self.empty)
        log_output.setObjectName('activityLog')
        log_output.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        log_output.document().setDocumentMargin(10)
        self.pages.addWidget(log_output)
        layout.addWidget(self.pages)
        log_output.textChanged.connect(self._refresh)
        self._refresh()

    def set_status(self, text, busy=False):
        self.busy = busy
        self.status.setText(text)
        self.status.setProperty('busy', busy)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self._refresh()

    def _refresh(self):
        has_messages = not self.log_output.document().isEmpty()
        self.pages.setCurrentWidget(self.log_output if has_messages else self.empty)
        retained = self.log_output.document().blockCount() if has_messages else 0
        self.count.setText(f'{retained} message' + ('' if retained == 1 else 's') if has_messages else '')
        self.count.setToolTip(f'Most recent {self.log_output.max_log_lines} messages are retained.')
        self.copy_button.setEnabled(has_messages)
        self.open_button.setEnabled(has_messages)
        self.clear_button.setEnabled(has_messages and not self.busy)

    def copy_log(self):
        QtWidgets.QApplication.clipboard().setText(self.log_output.toPlainText())

    def open_log(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Activity log')
        dialog.setWindowIcon(self.window().windowIcon())
        dialog.setWindowFlags(dialog.windowFlags() | QtCore.Qt.WindowType.WindowMaximizeButtonHint)
        dialog.resize(900, 520)
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QtWidgets.QLabel(f'Most recent {self.log_output.max_log_lines} messages · Select text to copy individual messages.'))
        viewer = QtWidgets.QTextEdit()
        viewer.setReadOnly(True)
        viewer.setFont(self.log_output.font())
        # A separate document keeps this viewer's wrapping/selection from
        # changing the compact log's layout or scroll position.
        viewer.setDocument(self.log_output.document().clone(viewer))
        layout.addWidget(viewer)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        copy = buttons.addButton('Copy log', QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(viewer.toPlainText()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.show()
        viewer.verticalScrollBar().setValue(viewer.verticalScrollBar().maximum())
        dialog.exec()
        dialog.deleteLater()
