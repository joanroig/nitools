"""Automatic kit preparation with live progress and resumable cancellation."""

from PySide6 import QtWidgets

from processors.maschine_prepare import prepare_index
from utils.worker_utils import WorkerThread


class PrepareMaschineBatchDialog(QtWidgets.QDialog):
    def __init__(self, index, options, parent=None):
        super().__init__(parent)
        self.index, self.options = index, options.model_copy()
        self.worker = None
        self.code = None
        self.closing = False
        self.setWindowTitle('Prepare Maschine kits')
        self.setFixedSize(700, 460)
        layout = QtWidgets.QVBoxLayout(self)
        description = QtWidgets.QLabel(
            'Prepare all kits in the selected index that need Maschine rendering. '
            'Kits load automatically in a separate Maschine editor. Valid cached kits are skipped; '
            'you can cancel and resume later. Keep the automatic editor untouched while it works.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.status = QtWidgets.QLabel('Ready. Your original kits are kept unchanged.')
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(42)
        layout.addWidget(self.status)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1500)
        layout.addWidget(self.log, 1)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self.start_button = QtWidgets.QPushButton('Prepare indexed kits')
        self.start_button.setProperty('class', 'accent')
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        self.close_button = QtWidgets.QPushButton('Close')
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def start(self):
        self.code = None
        self.worker = WorkerThread(prepare_index, dict(json_path=self.index, options=self.options), 'MaschinePreparer')
        # Worker logs contain ANSI colours for the main activity panel; this
        # compact preparation view displays the same messages as plain text.
        self.worker.output_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.finished_signal.connect(self.remember_result)
        self.worker.finished.connect(self.finished_work)
        self.start_button.setEnabled(False)
        self.close_button.setText('Cancel')
        self.status.setText('Opening the preparation queue…')
        self.worker.start()

    def append_log(self, message):
        import re
        self.log.appendPlainText(re.sub(r'\x1b\[[0-9;]*m', '', message))

    def on_progress(self, done, total, message):
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.status.setText(message)
        self.status.setToolTip(message)

    def remember_result(self, code):
        self.code = code

    def finished_work(self):
        self.start_button.setEnabled(True)
        self.start_button.setText('Resume / retry')
        self.close_button.setText('Close')
        self.close_button.setEnabled(True)
        self.status.setText('Prepared. Ready to export.' if self.code == 0 else
                            'Cancelled. Prepared kits are saved; resume whenever you want.' if self.code == -1 else
                            'Finished with errors. See the log; successful kits are saved.')
        if self.closing:
            super().reject()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.worker.request_cancel()
            self.status.setText('Cancelling… Prepared kits will be kept.')
            self.close_button.setEnabled(False)
            return
        super().reject()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.reject()
            event.ignore()
        else:
            super().closeEvent(event)
