"""Dispatch kit preparation without importing another platform's GUI runtime."""

import sys


def load_kit(plugin, source, timeout):
    if sys.platform == 'win32':
        from hosts.maschine_windows import load_kit as load
    elif sys.platform == 'darwin':
        from hosts.maschine_macos import load_kit as load
    else:
        raise ValueError('Automatic Maschine preparation requires Windows or macOS')
    return load(plugin, source, timeout)
