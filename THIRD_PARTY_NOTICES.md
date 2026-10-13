# Third-party notices

NITools is distributed under GPL-3.0; see `LICENSE`. This covers NITools' code;
it does not relicense third-party code, input libraries or rendered sounds.
Python dependencies are recorded in `pyproject.toml` and `uv.lock`. Platform
packages can contain different subsets of those dependencies.

## Runtime dependencies

The principal dependencies include:

| Component | License family | Upstream |
| --- | --- | --- |
| CPython | PSF and bundled third-party notices | https://www.python.org/ |
| PySide6-Essentials and Shiboken6 | LGPL-3.0 / GPL-3.0, with component-specific terms | https://doc.qt.io/qtforpython-6/licenses.html |
| Qt 6 runtime | LGPL-3.0; module-specific and third-party terms also apply | https://www.qt.io/licensing/ |
| Pedalboard, including JUCE and its VST3 hosting code | GPL-3.0 and included third-party terms | https://github.com/spotify/pedalboard |
| NumPy and OpenBLAS | BSD and included third-party terms | https://github.com/numpy/numpy |
| SoundFile | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| libsndfile and codec dependencies | LGPL-2.1 and included third-party terms | https://github.com/libsndfile/libsndfile |
| python-soxr / libsoxr | BSD-3-Clause / LGPL-2.1-or-later | https://github.com/dofuuz/python-soxr |
| Pydantic / pydantic-core | MIT | https://github.com/pydantic/pydantic |
| PyQtDarkTheme fork | MIT | https://github.com/5yutan5/PyQtDarkTheme |
| PyInstaller runtime | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/en/stable/license.html |

This table is a summary, not a replacement for the full notices or an exhaustive
bill of materials. Build tools such as markdown-pdf/PyMuPDF are separate from the
application runtime; do not accidentally bundle them when generating the guide.
The package's `licenses/` directory and `DEPENDENCIES.json` inventory preserve
the installed dependency notices and exact versions. A release still needs the
corresponding-source review described in `docs/RELEASE_CONTENTS.md`. Supplemental
PySide/Qt license texts and module attribution records are retained from the
verified source archives listed in `packaging/notices/sources.json` and copied
to `licenses/upstream/`. They supplement the incomplete wheel notices; they do
not establish complete corresponding-source availability for the whole app.

## Instrument hosting

Maschine VST3 hosting uses [Pedalboard](https://github.com/spotify/pedalboard),
copyright Spotify AB, under GPL-3.0. Pedalboard includes its own third-party
components and notices in its upstream source. Its top-level license alone does
not document every embedded component. Preserve its `NOTICE` and provide source
for the matching dependency revision, including submodules, when distributing
the binary.

VST is a trademark of Steinberg Media Technologies GmbH. NITools' VST2 host
implements the VST2 plug-in interface; it does not include the proprietary VST2
SDK. Pedalboard's VST3 hosting code includes open-source SDK components under
their upstream terms; this is distinct from proprietary instrument plug-ins.
Maschine, Massive, Reaktor and other Native Instruments software, presets and
licensed content are supplied by the user. None are included in NITools.

## Microsoft runtime

Windows packages exclude Microsoft C/C++ runtime DLLs and the redistributable
installer. The open-source NITools bootstrap uses Windows' existing .NET
Framework. If the required C/C++ runtime is missing or older than the build's
requirements, it offers to download the official installer directly from
Microsoft, verifies its Authenticode signature and publisher, and opens it only
after the user selects installation. Microsoft's terms apply to that separate
installation. NumPy runtime filename aliases are copied from installed System32
DLLs locally at application startup; those DLL bytes are not in our package.

## Project resources

NITools' application artwork and design sources are part of this project. The
bundled WAV is only zero-valued PCM silence. Vendor software screenshots and
the former third-party product catalog are excluded from the 2.0 candidate.
The four music-service icons on the original home screen are retained locally
at the maintainer's request; their distribution provenance/terms remain a
release-review item. Those third-party marks are not relicensed by NITools.
