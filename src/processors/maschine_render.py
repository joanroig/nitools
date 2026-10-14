"""Reusable Maschine states and isolated internal-instrument rendering."""

import hashlib
import json
import logging
import multiprocessing
import os
import platform
import plistlib
import sys
from pathlib import Path
import tempfile
import threading
import time

from appdirs import user_cache_dir

from formats.maschine import parse_maschine
from formats.maschine_project import route_kit_preset


def plugin_path(options):
    if options.maschine_plugin:
        candidates = [Path(options.maschine_plugin)]
    else:
        roots = ([Path.home() / 'Library/Audio/Plug-Ins/VST3', Path('/Library/Audio/Plug-Ins/VST3')]
                 if sys.platform == 'darwin' else
                 [Path(os.environ.get('CommonProgramFiles', r'C:\Program Files\Common Files')) / 'VST3'])
        # Prefer 3 when both are installed. An explicit selection never falls
        # back to a different engine if it is missing or cannot load the kit.
        candidates = [root / f'Maschine {version}.vst3' for version in (3, 2) for root in roots]
    for path in candidates:
        if path.suffix.lower() == '.vst3' and (path.is_dir() if sys.platform == 'darwin' else path.is_file()):
            plugin_binary(path)  # Reject malformed bundles before opening a host.
            return path.resolve()
    raise ValueError('Maschine 2 or 3 VST3 was not found. Select its installed .vst3 bundle on macOS or file on Windows.')


def plugin_binary(path):
    path = Path(path)
    if not path.is_dir():
        return path
    try:
        metadata = plistlib.loads((path / 'Contents/Info.plist').read_bytes())
        name = metadata['CFBundleExecutable']
        if not isinstance(name, str) or name in {'', '.', '..'} or '/' in name or '\\' in name:
            raise ValueError('Invalid executable name')
        binary = path / 'Contents/MacOS' / name
        if not binary.is_file():
            raise ValueError('Bundle executable is missing')
        return binary
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f'Invalid Maschine VST3 bundle: {path}: {exc}') from exc


def cache_paths(source, options):
    source = Path(source)
    plugin = plugin_path(options)
    binary = plugin_binary(plugin)
    identity = f'{plugin}|{binary.stat().st_size}|{binary.stat().st_mtime_ns}'
    if sys.platform == 'darwin':
        identity = f'darwin|{platform.machine()}|{identity}'
    fingerprint = identity.encode()
    key = hashlib.sha256(source.read_bytes() + fingerprint).hexdigest()
    folder = cache_folder(options)
    return folder / (key + '.vstpreset'), folder / (key + '.json')


def cache_folder(options):
    return Path(options.cache_folder) if options.cache_folder else Path(user_cache_dir('NITools', False)) / 'maschine'


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.nitools-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_prepared(source, preset, options):
    decoded = parse_maschine(Path(source).read_bytes())
    names = [s['name'] for s in decoded['samples']]
    routed = route_kit_preset(preset, names, decoded['group'])
    target, receipt = cache_paths(source, options)
    _atomic_write(target, routed)
    _atomic_write(receipt, json.dumps(dict(schema=1, source=str(Path(source).resolve()),
        group=decoded['group'], sha256=hashlib.sha256(routed).hexdigest()), indent=2).encode())
    return target


def load_prepared(source, options):
    target, receipt = cache_paths(source, options)
    if not target.is_file() or not receipt.is_file():
        raise ValueError('Kit is not prepared for Maschine rendering. Use Prepare kit in Pad and instrument options first.')
    if target.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Prepared Maschine state is too large')
    data = target.read_bytes()
    metadata = json.loads(receipt.read_text(encoding='utf-8'))
    if metadata.get('schema') != 1 or metadata.get('sha256') != hashlib.sha256(data).hexdigest():
        raise ValueError('Prepared Maschine state is damaged; prepare the kit again')
    decoded = parse_maschine(Path(source).read_bytes())
    return route_kit_preset(data, [s['name'] for s in decoded['samples']], decoded['group'])


def prepare_job(connection, source, options):
    """Own GUI process: closing Maschine's editor captures its loaded kit."""
    try:
        from pedalboard import load_plugin
        from hosts.runtime import prepare_plugin_host
        prepare_plugin_host()
        plugin = load_plugin(str(plugin_path(options)), initialization_timeout=30)
        connection.send(('status', 'Maschine is open. Load the selected kit into A1, then close its editor.'))
        plugin.show_editor()
        path = save_prepared(source, plugin.preset_data, options)
        connection.send(('done', str(path)))
    except Exception as exc:
        connection.send(('error', str(exc)))
    finally:
        connection.close()


def _native_job(connection, plugin_file, state, source=None, options=None):
    try:
        from pedalboard import load_plugin
        import pedalboard.midi_utils  # Imported dynamically by the native host; retain in frozen builds.
        import numpy as np
        import soundfile as sf
        from hosts.runtime import prepare_plugin_host
        prepare_plugin_host()
        plugin = load_plugin(plugin_file, initialization_timeout=30)
        if state is None:
            from processors.maschine_loader import load_kit
            state = load_kit(plugin, source, options.prepare_timeout)
            save_prepared(source, state, options)
        while True:
            request = connection.recv()
            if request is None:
                return
            pad, output, options = request
            try:
                plugin.preset_data = state
                note = 47 + pad  # Maschine Drumkit mode: pads 1–16 are MIDI 48–63.
                audio = plugin([(bytes([0x90, note, options['velocity']]), 0.0),
                                (bytes([0x80, note, 0]), options['hold'])],
                               sample_rate=48000, duration=options['hold'] + options['tail'],
                               num_channels=2, buffer_size=512, reset=True)
                if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-7:
                    raise ValueError('Maschine produced invalid audio or silence; check the loaded kit and installed content')
                sf.write(output, audio.T, 48000, subtype='FLOAT')
                connection.send(None)
            except Exception as exc:
                connection.send(str(exc))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        connection.send(str(exc))
    finally:
        connection.close()


def stop_process(process, connection=None):
    if process is not None and process.pid is not None:
        # Let an idle host destroy the plug-in and close its browser database.
        # Cancellation/errors pass no connection and still stop immediately.
        if process.is_alive() and connection is not None:
            try:
                connection.send(None)
            except (BrokenPipeError, EOFError, OSError):
                pass
            process.join(5)
        if process.is_alive():
            if connection is not None:
                logging.getLogger('MaschineHost').warning('Maschine did not close cleanly within 5s; stopping its isolated host')
            process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join()
        process.close()


class NativeSession:
    """One isolated Maschine host per kit, reused for all its internal pads."""
    def __init__(self, source, options):
        self.source = str(Path(source).resolve())
        try:
            self.state = load_prepared(source, options)
        except (ValueError, OSError):
            if not options.auto_prepare:
                raise
            self.state = None
        self.options = options
        self.plugin = str(plugin_path(options))
        self.lock = threading.Lock()
        self.process = None
        self.connection = None
        self.failed = False

    def render(self, pad, output, worker):
        with self.lock:
            if worker and worker.cancel_requested():
                return False
            if self.failed:
                raise RuntimeError('Maschine host failed earlier in this kit')
            try:
                first_render = self.process is None
                if self.process is None:
                    context = multiprocessing.get_context('spawn')
                    self.connection, child = context.Pipe()
                    self.process = context.Process(target=_native_job, args=(child, self.plugin, self.state, self.source, self.options), name='NITools-Maschine-render')
                    try:
                        self.process.start()
                    finally:
                        child.close()
                self.connection.send((pad, str(output), self.options.model_dump(include={'velocity', 'hold', 'tail'})))
                started = time.monotonic()
                while not self.connection.poll(0.1):
                    if worker and worker.cancel_requested():
                        self.close(graceful=False)
                        return False
                    if not self.process.is_alive():
                        raise RuntimeError(f'Maschine host exited with code {self.process.exitcode}')
                    limit = self.options.timeout + (self.options.prepare_timeout if first_render and self.state is None else 0)
                    if time.monotonic() - started > limit:
                        raise TimeoutError(f'Maschine preparation/render timed out after {limit:g}s')
                error = self.connection.recv()
            except Exception:
                self.failed = True
                self.close(graceful=False)
                raise
            # A pad may be silent or have missing content while the next pad
            # remains usable. Only transport/process failures discard the host.
            if error:
                raise RuntimeError(error)
            return True

    def close(self, graceful=True):
        stop_process(self.process, self.connection if graceful else None)
        self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
