"""Optional, isolated rendering of external instruments from a Maschine kit."""

import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time

from models.render_options import RenderOptions
from processors.vst2_host import render_job


class InstrumentRenderer:
    def __init__(self, options):
        self.options = options
        self.native_session = None
        self.native_error = None
        if sys.platform != 'win32' or sys.maxsize <= 2**32:
            raise ValueError('Instrument rendering currently requires 64-bit Windows')
        program_files = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
        roots = ([Path(options.plugin_folder)] if options.plugin_folder else []) + [
            program_files / 'Vstplugins', program_files / 'Steinberg/VstPlugins',
            program_files / 'Native Instruments/VSTPlugins 64 bit',
            program_files / 'Common Files/VST2',
        ]
        if options.enabled and options.plugin_folder and not Path(options.plugin_folder).is_dir():
            raise ValueError(f'VST2 folder does not exist: {options.plugin_folder}')
        self.plugins = {}
        for root in roots if options.enabled else []:
            if root.is_dir():
                for path in root.rglob('*.dll'):
                    # Explicit custom folder takes precedence over default roots.
                    self.plugins.setdefault(path.stem.casefold(), path.resolve())

    def prepare_record(self, record, samples):
        self.close_record()
        self.native_error = None
        if self.options.native_enabled and any(self.use_native(s.get('instrument', {})) for s in samples if s.get('instrument')):
            from processors.maschine_render import NativeSession
            try:
                self.native_session = NativeSession(record['source_file'], self.options)
            except Exception as exc:
                self.native_error = str(exc)

    def use_native(self, instrument):
        return self.options.native_enabled and (not self.options.enabled or instrument.get('render_support') != 'vst2')

    def close_record(self):
        if self.native_session is not None:
            self.native_session.close()
            self.native_session = None

    def render(self, instrument, output, worker=None, progress=None, pad=None):
        name = instrument.get('name', instrument.get('module', 'Unknown instrument'))
        if self.use_native(instrument):
            if self.native_session is None:
                raise ValueError(self.native_error or 'Maschine kit is not prepared')
            if not isinstance(pad, int) or not 1 <= pad <= 16:
                raise ValueError('Invalid Maschine pad number')
            return self.native_session.render(pad, output, worker)
        if instrument.get('render_support') != 'vst2':
            reason = instrument.get('reason', 'requires rendering inside Maschine')
            raise ValueError(f'{name}: {reason}')
        plugin = self.plugins.get(name.casefold())
        if plugin is None:
            raise ValueError(f'{name}: matching 64-bit VST2 DLL is not installed in the selected/default folders')
        state = instrument.get('state')
        if not isinstance(state, bytes) or not state:
            raise ValueError(f'{name}: saved instrument state is unavailable; the original .mxgrp is required')
        options = self.options.model_dump(include={'note', 'velocity', 'hold', 'tail'})
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=render_job, args=(
            child, str(plugin), state, instrument['vst_id'], str(output), options,
        ), name='NITools-instrument-render')
        started = time.monotonic()
        try:
            process.start()
            child.close()
            while process.is_alive():
                if worker and worker.cancel_requested():
                    return False
                if time.monotonic() - started > self.options.timeout:
                    raise TimeoutError(f'{name}: render timed out after {self.options.timeout:g}s')
                if progress:
                    progress()
                process.join(0.1)
            if process.exitcode != 0:
                raise RuntimeError(f'{name}: plug-in process exited with code {process.exitcode}')
            if not parent.poll():
                raise RuntimeError(f'{name}: renderer returned no result')
            error = parent.recv()
            if error:
                raise RuntimeError(f'{name}: {error}')
            if not Path(output).is_file():
                raise RuntimeError(f'{name}: renderer produced no audio file')
            return True
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join()
                process.close()
            parent.close()
            child.close()


def export_instrument(exporter, renderer, sample, target):
    """Use the same conversion, atomic replace and skip rules as sample export."""
    if exporter._worker and exporter._worker.cancel_requested():
        return 'cancelled'
    if exporter.skip_existing and target.is_file():
        return 'skipped'
    exporter.logger.info('[%s] Rendering pad %s: %s', exporter._current_name,
                         sample['pad'], sample.get('name', 'Instrument'))
    try:
        with tempfile.TemporaryDirectory(prefix='nitools-render-') as temporary:
            rendered = Path(temporary) / 'render.wav'
            if not renderer.render(sample['instrument'], rendered, exporter._worker, pad=sample['pad']):
                return 'cancelled'
            return exporter._write_sample(rendered, target)
    except Exception as exc:
        exporter.logger.error('[%s] pad %s (%s): %s', exporter._current_name,
                              sample['pad'], sample.get('name', ''), exc)
        return 'errors'
