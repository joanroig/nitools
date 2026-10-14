"""Experimental Cocoa file-drop adapter for our isolated Maschine editor.

Only views in this process are inspected. No desktop input, Accessibility
permission, shared clipboard or user's standalone Maschine session is used.
The default Ideas/A1 layout must be qualified on a real Mac before release.
"""

from functools import lru_cache
from pathlib import Path
import threading
import time

from formats.maschine import parse_maschine
from formats.maschine_project import project_archive_version, route_kit_preset


def editor_view(windows, archive_version=20):
    """Find one owned editor; v19 uses native Cocoa, v20 uses Qt."""
    if archive_version not in (19, 20):
        raise ValueError('Unsupported Maschine editor archive version')
    candidates = []

    def visit(view):
        if view.isHiddenOrHasHiddenAncestor():
            return
        bounds = view.bounds()
        if archive_version == 19:
            # Maschine 2 predates Qt. Inspect the native drag contract instead
            # of guessing its private Objective-C class name.
            types = {str(value) for value in (view.registeredDraggedTypes() or ())}
            accepts = bool(types & {'public.file-url', 'NSFilenamesPboardType'})
        elif archive_version == 20:
            accepts = 'QNSView' in str(view.className())
        else:
            raise ValueError('Unsupported Maschine editor archive version')
        if accepts and bounds.size.width >= 1000 and bounds.size.height >= 600:
            candidates.append(view)
        for child in view.subviews():
            visit(child)

    for window in windows:
        if window.isVisible() and window.contentView() is not None:
            visit(window.contentView())
    if len(candidates) != 1:
        raise ValueError('Could not identify one Maschine editor; automatic loading requires the default Ideas layout')
    view = candidates[0]
    if view.window().attachedSheet() is not None:
        raise ValueError('Maschine is waiting for a dialog; resolve missing plug-ins or content')
    return view


@lru_cache(maxsize=1)
def drag_info_class():
    import objc
    from AppKit import NSObject, NSPoint

    class NIToolsDraggingInfo(NSObject):
        # Explicit Objective-C signatures are needed for struct/integer returns.
        @objc.typedSelector(NSPoint.__typestr__ + b'@:')
        def draggingLocation(self):
            return self.location

        def draggingPasteboard(self):
            return self.pasteboard

        def draggingDestinationWindow(self):
            return self.destination

        def draggingSource(self):
            return None

        @objc.typedSelector(b'Q@:')
        def draggingSourceOperationMask(self):
            return 1  # NSDragOperationCopy; never move the original kit.

        @objc.typedSelector(b'q@:')
        def draggingSequenceNumber(self):
            return 1

    return NIToolsDraggingInfo


def drop_kit(view, source, archive_version=20):
    from AppKit import NSPasteboard, NSMakePoint, NSFilenamesPboardType
    from Foundation import NSURL

    pasteboard = NSPasteboard.pasteboardWithUniqueName()
    entered = completed = False
    info = drag_info_class().alloc().init()
    try:
        if not pasteboard.writeObjects_([NSURL.fileURLWithPath_(str(Path(source).resolve()))]):
            raise ValueError('Could not put the kit URL on the private drag pasteboard')
        if archive_version == 19:
            pasteboard.addTypes_owner_([NSFilenamesPboardType], None)
            if not pasteboard.setPropertyList_forType_([str(Path(source).resolve())], NSFilenamesPboardType):
                raise ValueError('Could not publish the legacy file list for Maschine 2')
        bounds = view.bounds()
        # AppKit coordinates are logical points, independent of Retina scale.
        drop_y = 180 if archive_version == 19 else 155
        y = drop_y if view.isFlipped() else bounds.size.height - drop_y
        info.location = view.convertPoint_toView_(NSMakePoint(410, y), None)
        info.pasteboard = pasteboard
        info.destination = view.window()
        entered = True
        if not (int(view.draggingEntered_(info)) & 1):
            raise ValueError('Maschine rejected the kit drop; use its default Ideas layout or assisted preparation')
        if not view.prepareForDragOperation_(info) or not view.performDragOperation_(info):
            raise ValueError('Maschine did not load the dropped group')
        completed = True
        view.concludeDragOperation_(info)
    finally:
        if entered and not completed:
            view.draggingExited_(info)
        pasteboard.releaseGlobally()


def load_kit(plugin, source, timeout):
    from AppKit import NSApplication
    from Foundation import NSThread, NSTimer, NSRunLoop, NSRunLoopCommonModes

    if not NSThread.isMainThread():
        raise RuntimeError('Maschine preparation must run on its isolated host main thread')
    decoded = parse_maschine(Path(source).read_bytes())
    archive_version = project_archive_version(plugin.preset_data)
    expected = [sample['name'] for sample in decoded['samples']]
    closed = threading.Event()
    started = time.monotonic()
    dropped = matched = None
    result = error = None
    active = False

    def tick(timer):
        nonlocal dropped, matched, result, error, active
        if active or closed.is_set():
            return
        active = True
        try:
            now = time.monotonic()
            if now - started > timeout:
                raise TimeoutError('Maschine kit loading timed out; check missing plug-ins or content')
            if now - started < 0.5:
                return
            app = NSApplication.sharedApplication()
            if app.modalWindow() is not None:
                raise ValueError('Maschine opened a dialog while loading; resolve missing plug-ins or content')
            view = editor_view(app.windows(), archive_version)
            if dropped is None:
                drop_kit(view, source, archive_version)
                dropped = now
                return
            try:
                state = route_kit_preset(plugin.preset_data, expected, decoded['group'])
            except ValueError:
                matched = None
                return
            if matched is None:
                matched = now
            elif now - matched >= 1:
                result = state
                closed.set()
        except Exception as exc:
            error = exc
            closed.set()
        finally:
            active = False

    timer = NSTimer.timerWithTimeInterval_repeats_block_(0.2, True, tick)
    NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)
    try:
        plugin.show_editor(closed)
    finally:
        timer.invalidate()
    if error is not None:
        raise error
    if result is None:
        raise ValueError('Maschine editor closed before the kit was prepared')
    return result
