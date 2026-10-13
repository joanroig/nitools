"""Load a group into our own Maschine 3 editor using its Windows file drop.

This runs on the isolated host's main thread. No foreground input, library
search, standalone Maschine instance, or user's document is involved. The
Windows OLE target property and Maschine 3 editor layout are version-sensitive;
an accepted drop is never treated as proof of loading: the project is decoded
and checked before returning it.
"""

import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import threading
import time
import uuid

from formats.maschine import parse_maschine
from formats.maschine_project import route_kit_preset


def _guid(value):
    return (C.c_byte * 16).from_buffer_copy(uuid.UUID(value).bytes_le)


def _method(pointer, slot, result, *arguments):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result, C.c_void_p, *arguments)(table[slot])


class _FileDrop:
    """Main-thread OLE operations restricted to windows in this host process."""
    def __init__(self):
        self.user = C.WinDLL('user32', use_last_error=True)
        self.kernel = C.WinDLL('kernel32')
        self.shell = C.WinDLL('shell32')
        self.callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        self.timer_callback = C.WINFUNCTYPE(None, W.HWND, W.UINT, C.c_size_t, W.DWORD)
        self.user.EnumThreadWindows.argtypes = [W.DWORD, self.callback, W.LPARAM]
        self.user.EnumChildWindows.argtypes = [W.HWND, self.callback, W.LPARAM]
        self.user.GetPropW.argtypes = [W.HWND, W.LPCWSTR]
        self.user.GetPropW.restype = C.c_void_p
        self.user.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
        self.user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        self.user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
        self.user.GetDpiForWindow.argtypes = [W.HWND]
        self.user.IsWindowEnabled.argtypes = [W.HWND]
        self.user.SetTimer.argtypes = [W.HWND, C.c_size_t, W.UINT, self.timer_callback]
        self.user.SetTimer.restype = C.c_size_t
        self.user.KillTimer.argtypes = [W.HWND, C.c_size_t]

    def target(self):
        targets = []

        @self.callback
        def child(hwnd, _):
            owner = W.DWORD()
            self.user.GetWindowThreadProcessId(hwnd, C.byref(owner))
            if owner.value != self.kernel.GetCurrentProcessId():
                return True
            name = C.create_unicode_buffer(256)
            self.user.GetClassNameW(hwnd, name, 256)
            if name.value.startswith('Qt') and 'NI_' in name.value and 'QWindowIcon{' in name.value:
                pointer = self.user.GetPropW(hwnd, 'OleDropTargetInterface')
                rect = W.RECT()
                self.user.GetWindowRect(hwnd, C.byref(rect))
                scale = (self.user.GetDpiForWindow(hwnd) or 96) / 96
                if pointer and rect.right - rect.left >= 1000 * scale and rect.bottom - rect.top >= 600 * scale:
                    targets.append((hwnd, pointer, rect, scale))
            return True

        @self.callback
        def top(hwnd, parameter):
            child(hwnd, parameter)
            self.user.EnumChildWindows(hwnd, child, 0)
            return True

        self.user.EnumThreadWindows(self.kernel.GetCurrentThreadId(), top, 0)
        if len(targets) != 1:
            raise ValueError('Could not identify the Maschine 3 group editor; automatic loading requires its default layout')
        return targets[0]

    def data_object(self, source):
        shell_item, data = C.c_void_p(), C.c_void_p()
        iid = _guid('43826d1e-e718-42ee-bc55-a1e261c37bfe')  # IShellItem
        self.shell.SHCreateItemFromParsingName.argtypes = [W.LPCWSTR, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)]
        result = self.shell.SHCreateItemFromParsingName(str(Path(source).resolve()), None, C.byref(iid), C.byref(shell_item))
        if result < 0:
            raise OSError(f'Could not open kit for file drop (HRESULT {result:#x})')
        try:
            handler = _guid('b8c0bd9f-ed24-455c-83e6-d5390c4fe8c4')  # BHID_DataObject
            iid = _guid('0000010e-0000-0000-c000-000000000046')  # IDataObject
            result = _method(shell_item, 3, C.c_long, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))(
                shell_item, None, C.byref(handler), C.byref(iid), C.byref(data))
            if result < 0:
                raise OSError(f'Could not create kit file drop (HRESULT {result:#x})')
            return data
        finally:
            _method(shell_item, 2, W.ULONG)(shell_item)

    def drop(self, source):
        hwnd, pointer, rect, scale = self.target()
        if not self.user.IsWindowEnabled(hwnd):
            raise ValueError('Maschine is waiting for a dialog; check its installed plug-ins and content')
        data = self.data_object(source)
        entered = False
        try:
            # A1 in Maschine 3's fresh project/Ideas layout. No mouse movement.
            point = W.POINT(rect.left + round(410 * scale), rect.top + round(155 * scale))
            effect = W.DWORD(1)  # Copy, never move the source.
            result = _method(pointer, 3, C.c_long, C.c_void_p, W.DWORD, W.POINT, C.POINTER(W.DWORD))(
                pointer, data, 1, point, C.byref(effect))
            entered = True
            if result < 0 or effect.value != 1:
                raise ValueError('Maschine did not accept the group file drop; use the default editor layout or assisted preparation')
            result = _method(pointer, 6, C.c_long, C.c_void_p, W.DWORD, W.POINT, C.POINTER(W.DWORD))(
                pointer, data, 0, point, C.byref(effect))
            entered = False
            if result < 0 or effect.value != 1:
                raise ValueError('Maschine could not load the dropped group')
        finally:
            if entered:
                _method(pointer, 5, C.c_long)(pointer)
            _method(data, 2, W.ULONG)(data)


def load_kit(plugin, source, timeout):
    """Pump the editor until the exact kit is loaded; return verified state.

    The supervising process enforces the timeout even if a native call hangs.
    Each call starts from a fresh project supplied by the caller.
    """
    decoded = parse_maschine(Path(source).read_bytes())
    expected = [sample['name'] for sample in decoded['samples']]
    api = _FileDrop()
    closed = threading.Event()
    started = time.monotonic()
    dropped = matched = None
    result = error = None
    active = False

    @api.timer_callback
    def tick(hwnd, message, timer_id, clock):
        nonlocal active, dropped, matched, result, error
        if active or closed.is_set():
            return
        active = True
        try:
            now = time.monotonic()
            if now - started > timeout:
                raise TimeoutError('Maschine kit loading timed out; check missing plug-ins or content')
            if now - started < 0.5:
                return
            if dropped is None:
                api.drop(source)
                dropped = time.monotonic()
                return
            editor, *_ = api.target()
            if not api.user.IsWindowEnabled(editor):
                raise ValueError('Maschine opened a dialog while loading; check missing plug-ins or content')
            try:
                preset = route_kit_preset(plugin.preset_data, expected, decoded['group'])
            except ValueError:
                matched = None
                return
            # Keep pumping after names become visible so asynchronous plug-in
            # initialization and content loading can finish before capture.
            if matched is None:
                matched = now
            elif now - matched >= 1.0:
                result = preset
                closed.set()
        except Exception as exc:
            error = exc
            closed.set()
        finally:
            active = False

    timer = api.user.SetTimer(None, 0, 200, tick)
    if not timer:
        raise C.WinError(C.get_last_error())
    try:
        plugin.show_editor(closed)
    finally:
        api.user.KillTimer(None, timer)
    if error:
        raise error
    if result is None:
        raise ValueError('Maschine editor closed before the kit was prepared')
    return result
