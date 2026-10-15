"""Runtime setup used only by isolated, disposable plug-in workers."""

import os
import sys


def ensure_standard_streams():
    """Windowed workers must be able to report errors and exit without a popup."""
    if not getattr(sys, 'frozen', False):
        return
    # Windowed executables have no standard streams. Native/Python hosts may
    # still write diagnostics while loading an instrument.
    for name in ('stdout', 'stderr'):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, 'w'))


def prepare_plugin_host():
    ensure_standard_streams()
    if not getattr(sys, 'frozen', False):
        return
    if sys.platform == 'win32':
        import ctypes
        # PyInstaller prioritizes its extraction folder for DLL dependencies.
        # Installed plug-ins need the normal Windows search order. All Python
        # host dependencies must be imported before clearing this worker's path.
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
