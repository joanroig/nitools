"""Collect only image formats used by NITools, avoiding unused PDF/codecs."""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if "imageformats" not in Path(source).parts
            or Path(source).stem.removeprefix("lib") in {"qjpeg", "qico", "qsvg"}]
