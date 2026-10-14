"""Resumable batch preparation with one warm Maschine host and crash recovery."""

import argparse
import json
import logging
import multiprocessing
from pathlib import Path
import sys
import time

from formats.maschine import parse_maschine
from models.render_options import RenderOptions
from processors.maschine_render import _atomic_write, cache_folder, load_prepared, plugin_path, save_prepared, stop_process

logger = logging.getLogger('MaschinePreparer')


def _prepare_job(connection, plugin_file, options):
    try:
        from pedalboard import load_plugin
        from processors.maschine_loader import load_kit
        from hosts.runtime import prepare_plugin_host
        prepare_plugin_host()
        plugin = load_plugin(plugin_file, initialization_timeout=30)
        blank = plugin.preset_data
        while True:
            source = connection.recv()
            if source is None:
                return
            plugin.preset_data = blank
            state = load_kit(plugin, source, options.prepare_timeout)
            connection.send(('done', str(save_prepared(source, state, options))))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send(('error', str(exc)))
    finally:
        connection.close()


class PreparationSession:
    def __init__(self, options):
        if sys.platform not in {'win32', 'darwin'} or sys.maxsize <= 2**32:
            raise ValueError('Automatic Maschine preparation requires 64-bit Windows or macOS')
        if sys.platform != 'win32' and options.enabled:
            raise ValueError('Direct VST2 rendering requires Windows; disable it and render all instruments through Maschine on macOS')
        self.options = options
        self.plugin = str(plugin_path(options))
        self.process = self.connection = None
        self.completed = 0

    def prepare(self, source, worker=None):
        if worker and worker.cancel_requested():
            return 'cancelled'
        try:
            load_prepared(source, self.options)
            return 'cached'
        except (ValueError, OSError):
            pass
        try:
            # Bound native resource accumulation during very large libraries.
            if self.completed >= 64:
                self.close()
            cold = self.process is None
            if cold:
                context = multiprocessing.get_context('spawn')
                self.connection, child = context.Pipe()
                self.process = context.Process(target=_prepare_job, args=(child, self.plugin, self.options),
                                               name='NITools-Maschine-preparation')
                try:
                    self.process.start()
                finally:
                    child.close()
            self.connection.send(str(Path(source).resolve()))
            started = time.monotonic()
            limit = self.options.prepare_timeout + (30 if cold else 0)
            while not self.connection.poll(0.1):
                if worker and worker.cancel_requested():
                    self.close(graceful=False)
                    return 'cancelled'
                if not self.process.is_alive():
                    raise RuntimeError(f'Maschine preparation host exited with code {self.process.exitcode}')
                if time.monotonic() - started > limit:
                    raise TimeoutError(f'Maschine preparation timed out after {limit:g}s')
            kind, message = self.connection.recv()
            if kind != 'done':
                raise RuntimeError(message)
            # Verify the committed cache in the parent too.
            load_prepared(source, self.options)
            self.completed += 1
            return 'prepared'
        except Exception:
            self.close(graceful=False)
            raise

    def close(self, graceful=True):
        stop_process(self.process, self.connection if graceful else None)
        self.process = None
        self.completed = 0
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def prepare_index(json_path, options, worker_instance=None):
    """Prepare only kits with instruments using Maschine under these options.

    Content-addressed validated caches are the checkpoint. The report is written
    after every kit; failed entries are retried on the next run.
    """
    records = json.loads(Path(json_path).read_text(encoding='utf-8'))
    if not isinstance(records, list) or not records:
        raise ValueError('Choose a non-empty Groups index from the Process step')
    session = PreparationSession(options)
    report = dict(index=str(Path(json_path).resolve()), prepared=0, cached=0, unnecessary=0, errors=0, cancelled=False, results=[])
    seen = set()
    report_path = cache_folder(options) / 'preparation-report.json'
    try:
        for number, record in enumerate(records, 1):
            if worker_instance and worker_instance.cancel_requested():
                report['cancelled'] = True
                break
            source = record.get('source_file', '') if isinstance(record, dict) else ''
            source = source if isinstance(source, str) else ''
            label = Path(source).stem or f'Record {number}'
            if worker_instance:
                worker_instance.report_progress(number - 1, len(records), f'Preparing {number}/{len(records)} — {label}')
            entry = dict(source=source)
            try:
                if not source or Path(source).suffix.lower() != '.mxgrp':
                    raise ValueError('The index is missing an original .mxgrp path; rebuild it first')
                identity = str(Path(source).resolve()).casefold()
                if identity in seen:
                    continue
                seen.add(identity)
                decoded = parse_maschine(Path(source).read_bytes())
                needed = any(s.get('instrument') and (not options.enabled or s['instrument'].get('render_support') != 'vst2')
                             for s in decoded['samples'])
                if not needed:
                    report['unnecessary'] += 1
                    continue
                logger.info('[%s/%s] Preparing %s', number, len(records), source)
                outcome = session.prepare(source, worker_instance)
                if outcome == 'cancelled':
                    report['cancelled'] = True
                    break
                entry['status'] = outcome
                report[outcome] += 1
                logger.info('[%s/%s] %s: %s', number, len(records), outcome.capitalize(), label)
            except Exception as exc:
                entry.update(status='error', error=str(exc))
                report['errors'] += 1
                logger.error('[%s/%s] %s: %s', number, len(records), label, exc)
            report['results'].append(entry)
            _atomic_write(report_path, json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8'))
    except KeyboardInterrupt:
        report['cancelled'] = True
        raise
    finally:
        session.close()
        _atomic_write(report_path, json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8'))
    logger.info('Preparation %s: %s prepared, %s cached, %s did not need Maschine, %s errors.%s',
                'cancelled' if report['cancelled'] else 'finished', report['prepared'], report['cached'],
                report['unnecessary'], report['errors'], f' Report: {report_path}' if report_path else '')
    if worker_instance and not report['cancelled']:
        worker_instance.report_progress(len(records), len(records), 'Preparation finished')
    return -1 if report['cancelled'] else 1 if report['errors'] else 0


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description='Automatically prepare indexed Maschine kits for rendering')
    parser.add_argument('json_path')
    parser.add_argument('--maschine_plugin', default='')
    parser.add_argument('--maschine_cache', default='')
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--external_vst2', action='store_true', help='Skip kits whose instruments can all use direct VST2 rendering')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    try:
        sys.exit(prepare_index(args.json_path, RenderOptions(native_enabled=True, enabled=args.external_vst2,
            maschine_plugin=args.maschine_plugin, cache_folder=args.maschine_cache, prepare_timeout=args.timeout)))
    except KeyboardInterrupt:
        sys.exit(130)
