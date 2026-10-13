"""Prepare one original kit in an isolated Maschine editor."""

import multiprocessing
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from processors.maschine_render import prepare_job, stop_process


class PrepareMaschineDialog(QtWidgets.QDialog):
    def __init__(self, source, options, parent=None):
        super().__init__(parent)
        self.source = str(Path(source).resolve())
        self.options = options.model_copy()
        self.process = self.connection = None
        self.setWindowTitle('Prepare kit for Maschine rendering')
        self.setFixedSize(640, 350)
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel(Path(source).stem)
        title.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title)
        instructions = QtWidgets.QLabel(
            '1. Open the Maschine editor below.\n'
            '2. Load the selected kit into Group A1 using its library, or drag the .mxgrp from its folder. '
            'Keep one Group, leave MIDI routing at its defaults, and wait for the instruments to load.\n'
            '3. Close the editor window. NITools checks the kit and prepares its pad routing.\n\n'
            'You only need to do this once per kit. Later exports reuse the saved state. '
            'Use the editor opened here; opening the kit in standalone Maschine does not prepare it.')
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        path = QtWidgets.QLineEdit(self.source)
        path.setReadOnly(True)
        layout.addWidget(path)
        folder_button = QtWidgets.QPushButton('Open kit folder')
        folder_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(Path(self.source).parent))))
        layout.addWidget(folder_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        self.status = QtWidgets.QLabel('Ready to open Maschine 3.')
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(48)
        layout.addWidget(self.status)
        layout.addStretch()
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        self.start_button = QtWidgets.QPushButton('Open Maschine editor')
        self.start_button.clicked.connect(self.start)
        buttons.addWidget(self.start_button)
        self.close_button = QtWidgets.QPushButton('Close')
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.poll)

    def start(self):
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe(duplex=False)
        self.process = context.Process(target=prepare_job,
            args=(child, self.source, self.options), name='NITools-prepare-Maschine')
        try:
            self.process.start()
        except Exception as exc:
            self.finish(False, str(exc))
            return
        finally:
            child.close()
        self.status.setText('Opening Maschine 3… This may take a little while.')
        self.start_button.setEnabled(False)
        self.close_button.setText('Cancel preparation')
        self.timer.start()

    def poll(self):
        try:
            while self.connection.poll():
                kind, text = self.connection.recv()
                if kind == 'status':
                    self.status.setText(text)
                else:
                    self.finish(kind == 'done', text)
                    return
            if not self.process.is_alive():
                self.finish(False, f'Maschine closed without saving a prepared kit (exit {self.process.exitcode}).')
        except (EOFError, OSError) as exc:
            self.finish(False, f'Maschine host disconnected: {exc}')

    def finish(self, success, message):
        self.cleanup()
        self.status.setText('Prepared. You can now export this kit with Maschine rendering enabled.'
                            if success else f'Could not prepare kit: {message}')
        self.status.setToolTip(message)
        self.start_button.setText('Prepare again' if success else 'Retry')
        self.start_button.setEnabled(True)
        self.close_button.setText('Done' if success else 'Close')

    def cleanup(self):
        self.timer.stop()
        stop_process(self.process)
        self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def done(self, result):
        self.cleanup()
        super().done(result)
