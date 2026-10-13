"""Common worker lifecycle and progress UI for Kits, Groups and Previews."""

import json
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtWidgets import QMessageBox

from components.progress_dialog import ProgressDialog
from dialogs.error_dialog import ErrorDialog
from dialogs.export_complete_dialog import show_export_complete_dialog
from utils.worker_utils import WorkerThread


class ExporterWorkflow:
    def show_loading(self, message):
        self.cancelled = False
        self.progress_dialog = ProgressDialog(message, self)
        self.progress_dialog.canceled.connect(self.cancel_worker)
        self.progress_dialog.show()

    def hide_loading(self):
        if self.progress_dialog:
            self.progress_dialog.blockSignals(True)
            self.progress_dialog.done(0)
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

    def on_worker_progress(self, completed, total, message):
        if self.progress_dialog and not self.cancelled:
            self.progress_dialog.setLabelText(message)
            self.progress_dialog.setRange(0, total)
            self.progress_dialog.setValue(completed)

    def cancel_worker(self):
        if self.worker and self.worker.isRunning():
            if self.cancelled:
                return
            self.cancelled = True
            self.worker.request_cancel()
            if self.progress_dialog:
                self.progress_dialog.set_cancelling()
            self.log_output.append('Cancellation requested; finishing active file operations...')
        else:
            self.hide_loading()

    def stop_before_close(self, event):
        if self.worker and self.worker.isRunning():
            self._close_when_finished = True
            self.cancel_worker()
            event.ignore()
            return True
        return False

    def on_worker_output(self, text):
        self.log_output.append(text)
        self.has_output = True

    def run_worker(self, target_callable, kwargs, logger_name=None):
        self.active_operation = 'Process' if logger_name and logger_name.endswith('Builder') else 'Export'
        self._active_output_folder = self.proc_output_folder.text().strip()
        self._close_when_finished = False
        self.activity_panel.set_status('Processing…' if self.active_operation == 'Process' else 'Exporting…', busy=True)
        self.tabs.setEnabled(False)
        self.run_build_btn.setEnabled(False)
        self.run_process_btn.setEnabled(False)
        self.has_output = False
        self._worker_code = 1
        self.worker = WorkerThread(target_callable, kwargs, logger_name)
        self.worker.output_signal.connect(self.on_worker_output)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self._remember_result)
        # QThread.finished guarantees the worker has stopped before another
        # operation or a window close can discard its reference.
        self.worker.finished.connect(self._worker_stopped)
        self.worker.start()

    def _remember_result(self, code):
        self._worker_code = code

    def _worker_stopped(self):
        self.on_subprocess_finished(self._worker_code)

    def on_subprocess_finished(self, code):
        self.hide_loading()
        context = self.active_operation
        self.activity_panel.set_status('Cancelled' if self.cancelled or code == -1 else 'Complete' if code == 0 else 'Incomplete')
        self.log_output.append(f'{context} finished with code {code}\n')
        self.tabs.setEnabled(True)
        self.run_build_btn.setEnabled(True)
        self.on_json_path_changed()
        if getattr(self, '_close_when_finished', False):
            self.close()
            return
        QtWidgets.QApplication.instance().beep()
        if self.cancelled or code == -1:
            self.log_output.append(f'{context} cancelled by user.\n')
            QMessageBox.information(self, f'{context} Cancelled', f'The {context.lower()} was cancelled.')
        elif code != 0:
            detail = ' The index report in the output folder lists affected files.' if context == 'Process' else ''
            self._show_failure(context, f'The {context.lower()} is incomplete. Check the errors below.' + detail)
        elif context == 'Process':
            try:
                if not self.last_built_json_path:
                    raise ValueError('No output index was produced.')
                data = json.loads(Path(self.last_built_json_path).read_text(encoding='utf-8'))
                if not isinstance(data, list) or not data:
                    raise ValueError('The output index contains no records.')
                self.json_path.setText(self.last_built_json_path)
                self.tabs.setCurrentIndex(1)
                self.log_output.append(f'Done — {len(data)} records indexed.\n')
                QMessageBox.information(self, 'Process Complete', f'{len(data)} records indexed. Ready to export.')
            except (ValueError, OSError) as exc:
                self._show_failure(context, f'Could not verify the output index: {exc}')
        else:
            self.log_output.append('Done\n')
            show_export_complete_dialog(parent=self, output_folder=self._active_output_folder,
                                        log_content=self.log_output.toPlainText(), title='Export Complete',
                                        message='Export finished successfully.')
        self.cancelled = False

    def _show_failure(self, context, message):
        self.activity_panel.set_status('Incomplete')
        self.log_output.append(message + '\n')
        ErrorDialog(parent=self, title=f'{context} Incomplete', message=message,
                    detailed_text='\n'.join(self.log_output.toPlainText().splitlines()[-30:]),
                    icon=QMessageBox.Icon.Critical).exec()
