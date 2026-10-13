"""NITools uses raster widgets; no bundled software OpenGL renderer is needed."""
from PyInstaller.utils.hooks.qt import ensure_single_qt_bindings_package

ensure_single_qt_bindings_package("PySide6")
hiddenimports = ["shiboken6", "inspect", "PySide6.support.deprecated"]
