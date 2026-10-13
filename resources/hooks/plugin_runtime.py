"""PyInstaller hook: choose the installed C++ runtime before Qt's hook runs.

Qt wheels can bundle an older MSVC runtime than installed audio instruments
require. Worker processes must bind to the installed redistributable first.
The application UI and system installation are not modified.
"""

import sys

if sys.platform == 'win32':
    import json
    import os
    from pathlib import Path
    import shutil

    _root = Path(sys._MEIPASS)
    _system = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
    _aliases = json.loads((_root / 'runtime-aliases.json').read_text(encoding='utf-8'))
    for _relative, _system_name in _aliases.items():
        _target = (_root / _relative).resolve()
        if not _target.is_relative_to(_root.resolve()) or Path(_system_name).name != _system_name:
            raise RuntimeError('Invalid runtime alias in the application package')
        _target.parent.mkdir(parents=True, exist_ok=True)
        # Each spawn worker uses the same private extraction folder. Publish
        # atomically; another process may already have completed this alias.
        if not _target.exists():
            _temporary = _target.with_name(_target.name + '.' + str(os.getpid()) + '.tmp')
            shutil.copyfile(_system / _system_name, _temporary)
            try:
                _temporary.replace(_target)
            except PermissionError:
                if not _target.is_file():
                    raise
                _temporary.unlink(missing_ok=True)

if sys.platform == 'win32' and '--multiprocessing-fork' in sys.argv:
    import ctypes
    import os
    from pathlib import Path

    _system = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'
    _runtime_handles = []
    for _name in ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
                  'msvcp140_atomic_wait.dll', 'concrt140.dll'):
        _library = _system / _name
        if _library.is_file():
            try:
                _runtime_handles.append(ctypes.WinDLL(str(_library)))
            except OSError:
                # Sample-only workers still work without an instrument's
                # runtime. The renderer reports any actual load failure.
                pass
