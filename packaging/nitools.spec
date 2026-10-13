# Reproducible packaging inputs. Microsoft runtime DLLs are excluded on Windows.
from pathlib import Path
import os
import sys
from PyInstaller.config import CONF

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "packaging"))
from bundle_policy import checked_resources, without_microsoft_runtime

windows = sys.platform == "win32"
data = checked_resources(root / "resources") + [(str(root / "pyproject.toml"), ".")]
hooks = [str(root / "resources/hooks/plugin_runtime.py")] if windows else []
a = Analysis([str(root / "src/launcher.py")], pathex=[str(root / "src")],
    binaries=[], datas=data, hiddenimports=[],
    hookspath=[str(root / "packaging/hooks")], runtime_hooks=hooks,
    excludes=["PyQt6", "PyQt5", "PySide2", "pymupdf", "fitz", "markdown_pdf"], noarchive=False)
if windows:
    a.binaries = without_microsoft_runtime(a.binaries, Path(CONF['workpath']))
    a.datas += [("runtime-aliases.json", str(Path(CONF['workpath']) / "runtime-aliases.json"), "DATA")]
pyz = PYZ(a.pure)
if windows:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="NIToolsApp",
        debug=False, strip=False, upx=False, console=False,
        icon=str(root / "icons/app.ico"))
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NITools",
        debug=False, strip=False, upx=False, console=False,
        target_arch=os.environ["NITOOLS_TARGET_ARCH"])
    collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="NITools")
    app = BUNDLE(collection, name="NITools.app", icon=str(root / "icons/app.icns"),
        bundle_identifier="com.moaibeats.nitools")
