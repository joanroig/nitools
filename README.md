<p align="center">
  <a href="https://github.com/joanroig/nitools">
      <img alt="NITools" src="resources/icons/nitools.png" width="140px">
  </a>
</p>

<h1 align="center">NITools</h1>

<p align="center">
  NITools is an unofficial suite to extract, convert, and repurpose Native Instruments content, making it easy to use your kits, samples, and previews on other devices and workflows.
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.13%2B-blue?logo=python&logoColor=white" alt="Python 3.13"/></a>
  <a href="https://github.com/joanroig/nitools/releases"><img src="https://img.shields.io/github/v/release/joanroig/nitools?include_prereleases&label=version"/></a>
  <a href="https://github.com/joanroig/nitools/actions"><img alt="GitHub Actions Status" src="https://img.shields.io/github/actions/workflow/status/joanroig/nitools/create-release.yml?branch=main"></a>
  <a href="https://github.com/joanroig/nitools/issues"><img src="https://img.shields.io/github/issues/joanroig/nitools"></a>
  <a href="https://github.com/joanroig/nitools/blob/main/LICENSE"><img alt="GPL-3.0 License" src="https://img.shields.io/github/license/joanroig/nitools?color=blue"></a>
  <a href="https://github.com/joanroig/nitools/stargazers"><img src="https://img.shields.io/github/stars/joanroig/nitools"></a>
</p>

<p align="center">
  <a href="https://github.com/joanroig/nitools/releases">
    <img alt="Maschine Groups export settings and Activity panel" src="docs/img/nitools%20groups%20export.png">
  </a>
</p>

<p align="center">
  <table align="center" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td valign="middle" style="padding-right: 20px;">
        <a href="http://instagram.com/moaibeats"><img src="resources/icons/moai.png" alt="Moai Beats" width="100"></a>
      </td>
      <td valign="middle" align="left">
        <p align="center"><b>Created by Moai Beats</b></br>Follow and stream to support me •ᴗ•</p>
        <p align="center">
          <a href="https://open.spotify.com/artist/5Zt96vfBQXmUB3fs3Qkm5q">Spotify</a>
          &nbsp;&nbsp;
          <a href="https://music.apple.com/es/artist/moai-beats/1466043534">Apple Music</a>
          &nbsp;&nbsp;
          <a href="https://youtube.com/moaibeats?sub_confirmation=1">YouTube</a>
          &nbsp;&nbsp;
          <a href="https://moaibeats.bandcamp.com">Bandcamp</a>
        </p>
      </td>
    </tr>

  </table>
</p>

## ⬇️ Download

Pre-built executables for **Windows** and **macOS** are available on the [Releases page](https://github.com/joanroig/nitools/releases).

The changes described below are a **local, unreleased 2.0 candidate**. Published downloads still refer to the previous release. The current GUI uses PySide6-Essentials; the candidate targets Windows 10/11 x64 and macOS 13 or later.

### 🛠️ Usage

For a detailed user guide, including GUI screenshots and step-by-step instructions, please refer to the [User Guide](docs/GUIDE.md).

## ✨ Overview

**NITools** is an unofficial, **multi-platform** suite of tools designed to **bulk extract, convert, and repurpose Native Instruments content** for broader workflows.

The initial idea was to export Maschine groups to use them in the Roland SP 404 MK2. Since then, the project evolved to allow configurable parameters to export for other devices and to export more data.

### Key Features

- **GUI & CLI:** Use via graphical interface or command line for maximum flexibility.
- **Portable:** Pre-built executables, no Python installation required.
- **Cross-Platform:** Supports Windows and macOS.
- **Maschine Groups Exporter:** Extract samples from `.mxgrp` files, with optional instrument rendering on Windows through installed VST2 plug-ins or prepared Maschine 2/3 kits.
- **NKS Previews Exporter:** Convert NKS audio previews to WAV for one-shot instruments on other platforms.
- **Battery Kits Exporter:** Decode `.nbkt` cell sample references and export the original sample zones.
- **Consistent workflows:** Kits, Groups and Previews share live progress, cancellation, error reporting and bounded parallel audio conversion.
- **Readable activity:** Follow new messages, pause by scrolling back, copy the retained log, or open it in a larger reader.

### ⚠️ Compatibility Note

The current candidate is qualified locally on Windows only. The macOS port includes
automatic Maschine preparation and rendering through the installed Maschine VST3,
but that adapter and the packaged app still require real-Mac validation. Direct
VST2 DLL rendering remains Windows-only. See [Mac setup and qualification](docs/MACOS_PORT.md).

Run from source on Mac with `bash run.sh` (Python 3.13). See the
[project structure and development commands](docs/PROJECT_STRUCTURE.md).

## Modules

### <img alt="Groups Exporter" src="resources/icons/groups.png" width="16px"> **Groups Exporter (Maschine)**

- Scans a folder for all Maschine group files and parses sample data.
- Configurable normalization, sample rate, bit depth, and silence trimming.
- Pad reorder matrix and filtering options.
- Option to fill blank pads with a default sample.
- Option to include group preview samples.

### <img alt="Groups Exporter" src="resources/icons/previews.png" width="16px"> **Previews Exporter (NKS)**

- Converts NKS `.previews` to standardized WAV files for easy browsing outside NI software.
- Configurable normalization, sample rate, bit depth, and silence trimming.
- Options to skip content from Maschine, Battery, or the large 'Native Browser Preview Library'.
- Option to find the real instrument folder names for previews.

### <img alt="Kits Exporter" src="resources/icons/kits.png" width="16px"> **Battery Kits Exporter**

- Reads serialized cell numbers and complete sample paths instead of reconstructing names from text fragments.
- Exports all visible-grid sample zones, repeated references, empty-slot numbering, and cells above 16.
- Shares audio conversion, matrix, filter, and preview options with the Groups Exporter.
- Reports missing exact paths and conversion failures as incomplete exports; no fuzzy replacements.

Maschine kit decoding now follows native archive field order and tracked object references, with no byte-pattern fallback. See [decoder architecture, validation and limits](docs/MASCHINE_FORMAT.md). Rebuild the Groups index to use the new reader and recover legacy plug-in metadata.

Rebuild old JSON indexes and use a fresh output folder when upgrading from the earlier heuristic parsers. The exporters reject indexes without the current structured-decoder marker. Both exporters preserve every visible-grid sample zone, including Maschine Audio-module takes. Battery cells retained outside the saved grid are kept separately in the index and reported, without inventing export pad numbers. Sample export copies source audio without recreating its native processing. The Groups Exporter also offers experimental instrument rendering. Maschine kits can be prepared automatically during export or in a resumable batch queue; no per-kit manual loading is required for the validated Maschine 2/3 setups. See the [User Guide](docs/GUIDE.md#optional-instrument-rendering-64-bit) for setup and limitations.

See the [2.0 release notes](docs/RELEASE_NOTES_2_0.md) for upgrade instructions and the [verification record](docs/RELEASE_2_0.md) for tested scope and remaining compatibility checks.

## 📦 Development

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**: Required for running the scripts.
- **uv**: Recommended for creating and syncing the project environment from [pyproject.toml](pyproject.toml).
- **VS Code**: Recommended IDE for development and debugging (optional, but useful for quick start configurations).
- **create-dmg**: For macOS executable bundling, install via [Homebrew](https://brew.sh): `brew install create-dmg`.

### Installation

1. **Clone the repository:**

   ```powershell
   git clone https://github.com/joanroig/nitools.git
   cd nitools
   ```

2. **Set up a Python environment with uv:**

   ```powershell
   uv sync --locked
   ```

3. **Launch the app:** `uv sync` installs the local package in editable mode. On Windows:

```powershell
./run.ps1
```

### Overview

| Layer    | Tool                      | Path                                               | Purpose                                                        |
| -------- | ------------------------- | -------------------------------------------------- | -------------------------------------------------------------- |
| Launcher | **GUI: Launcher**         | `src/launcher.py`                                  | Central entry point for all three exporters.                  |
| GUI      | **Groups Exporter GUI**   | `src/apps/groups_exporter_gui.py`                  | Extracts and processes **groups/kits** (pads, instruments).    |
| GUI      | **Previews Exporter GUI** | `src/apps/previews_exporter_gui.py`                | Extracts and processes **audio previews** (short demo sounds). |
| GUI      | **Battery Kits Exporter** | `src/apps/kits_exporter_gui.py`                    | Decodes Battery cells and exports visible-grid sample zones.  |
| CLI      | **Kits Build**            | `src/processors/kits/build_kits_json.py`            | Creates a structured Battery kit index; export from the GUI.  |
| CLI      | **Groups Build**          | `src/processors/groups/build_groups_json.py`       | Extract raw **group/kit metadata** into a JSON index.          |
| CLI      | **Groups Process**        | `src/processors/groups/process_groups_json.py`     | Process groups (trim silence, normalize, etc.).                |
| CLI      | **Previews Build**        | `src/processors/previews/build_previews_json.py`   | Extract raw **preview metadata** into a JSON index.            |
| CLI      | **Previews Process**      | `src/processors/previews/process_previews_json.py` | Process preview audio (trim silence, normalize, etc.).         |

### Quick Start (VS Code)

1. **Run Launcher**
   - Open **Run and Debug** → **"GUI: Launcher"**
   - Runs `src/launcher.py` which can start the GUI tools.

2. **Run GUI Tools Independently**
   - **Groups Exporter GUI**
     - Run config: **"GUI: Groups Exporter"**
     - Runs `src/apps/groups_exporter_gui.py`
     - Handles **Maschine groups/kits** (pad layouts, mappings, kit metadata).
   - **Previews Exporter GUI**
     - Run config: **"GUI: Previews Exporter"**
     - Runs `src/apps/previews_exporter_gui.py`
     - Handles **audio previews** (short WAV samples used for browsing kits).

   ⚡ These GUIs can also be launched from the **Launcher**, but can run independently for development/debugging.

3. **Run CLI Tools**

   The Groups and Previews workflows have CLI commands; Battery also provides a CLI index builder. Battery audio export is available in the GUI.
   - **Groups Build** → Builds `all_groups.json` from library kits.
   - **Groups Process** → Processes `all_groups.json` into individual kits.
   - **Previews Build** → Builds `all_previews.json` from audio previews.
   - **Previews Process** → Processes `all_previews.json` into individual preview files.

### CLI Usage

#### 1. `build_groups_json.py`

Extracts **group/kit metadata** and outputs a combined JSON.

```powershell
uv run --locked python -m processors.groups.build_groups_json <input_folder> <output_folder> --generate_txt <true|false>
```

- `<input_folder>`: Input library folder (e.g. `D:/Libraries/Native Instruments/`)
- `<output_folder>`: Destination folder (e.g. `./out/`)
- `<generate_txt>`: `true` = also generate `.txt` files, `false` = skip

**Example:**

```powershell
uv run --locked python -m processors.groups.build_groups_json "D:/Libraries/Native Instruments/" ./out/ --generate_txt false
```

#### 2. `process_groups_json.py`

Processes **group JSON files** into cleaned/usable kits.

```powershell
uv run --locked python -m processors.groups.process_groups_json <all_groups_json> <groups_output_folder> [options]
```

Options:

- `--trim_silence` → Remove silence
- `--normalize` → Normalize volume
- `--matrix_json <path>` → Optional custom reorder matrix JSON file
- `--enable_matrix` → Enable pad matrix reorder
- `--filter_pads` → Filter groups: pad 1 contains keywords for pad 1, pad 2 for pad 2, pad 3 for pad 3 (case-insensitive)
- `--filter_pads_json <path>` → Optional custom pad filter keywords JSON file
- `--fill_blanks` → Fill empty pads
- `--fill_blanks_path <path>` → Fill blank pads with a specified WAV file, or pick a random file from a folder of WAVs (default is a silence sample file: `resources/audio/.wav`)
- `--sample_rate <rate>` → Convert all samples to this sample rate (e.g., `48000`)
- `--bit_depth <depth>` → Convert all samples to this bit depth (e.g., `16`)
- `--include_preview` → Include preview samples from groups .previews
- `--skip_existing` → Skip processing if output file already exists
- `--render_instruments` → Render supported external VST2 instrument presets using installed 64-bit plug-ins (Windows)
- `--vst2_folder <folder>` → Additional VST2 DLL search folder
- `--render_maschine` → Render internal/other instrument pads through Maschine 2/3; automatically prepare and cache uncached kits
- `--no_auto_prepare` → Restrict Maschine rendering to previously prepared kits
- `--prepare_timeout <seconds>` → Kit loading timeout (default 120; 5–900)
- `--maschine_plugin <file>` / `--maschine_cache <folder>` → Override the detected Maschine 2/3 VST3 or prepared-state cache location
- `--render_note <0–127>` / `--render_velocity <1–127>` → External VST2 note (default 60) and shared velocity (default 100)
- `--render_hold <seconds>` / `--render_tail <seconds>` → Held note and release length (defaults 1 and 2 seconds)

**Example:**

```powershell
uv run --locked python -m processors.groups.process_groups_json ./out/all_groups.json ./out/groups/ --trim_silence --normalize --sample_rate 48000 --bit_depth 24 --include_preview --skip_existing
```

#### 3. `build_previews_json.py`

Extracts **audio preview metadata** and outputs a combined JSON.

```powershell
uv run --locked python -m processors.previews.build_previews_json <output_folder>
```

- `<output_folder>`: Destination folder (e.g. `./out/`)

**Example:**

```powershell
uv run --locked python -m processors.previews.build_previews_json ./out/
```

#### 4. `process_previews_json.py`

Processes **preview JSON files** into cleaned/usable audio previews.

```powershell
uv run --locked python -m processors.previews.process_previews_json <all_previews_json> <previews_output_folder> [options]
```

Options:

- `--trim_silence` → Remove silence
- `--normalize` → Normalize volume
- `--sample_rate <rate>` → Convert all samples to this sample rate (e.g., `48000`)
- `--bit_depth <depth>` → Convert all samples to this bit depth (e.g., `16`)
- `--skip_existing` → Skip processing if output file already exists
- `--skip_maschine_folders` → Skip `.mxgrp.ogg` group previews, retaining other instrument previews in the library
- `--skip_battery_kits` → Skip files ending with .nbkt.ogg (Battery kits)
- `--skip_native_browser_preview_library` → Skip 'Native Browser Preview Library' folder
- `--find_real_instrument_folder` → Find real instrument folder for the Preview Library

**Example:**

```powershell
uv run --locked python -m processors.previews.process_previews_json ./out/all_previews.json ./out/previews/ --trim_silence --normalize --sample_rate 44100 --bit_depth 24 --skip_existing --skip_maschine_folders --skip_battery_kits --skip_native_browser_preview_library
```

#### 5. Battery kit index

```powershell
uv run --locked python -m processors.kits.build_kits_json "D:/Libraries/Native Instruments/" ./out/kits/ --generate_txt false
```

Open **Kits Exporter → 2 Export**, select `./out/kits/all_kits.json`, and choose an export folder. Battery audio export currently uses the GUI.

### Tests

```powershell
uv run --locked python -m unittest discover -s tests -v
```

Tests cover binary decoding, reference resolution, audio failures/cancellation, multiprocessing and the shared GUI. The installed-library corpus test skips when its optional local files are absent. CI runs the portable tests on Windows and macOS; this does not replace native application and installed-library checks.

### Building Executables

The project uses PyInstaller to bundle the application into standalone executables.
The GitHub Actions workflow [create-release.yml](.github/workflows/create-release.yml) automates this process for releases.

- **Windows:**
  The `bundle_app_windows.ps1` PowerShell script is used.
  Run it from PowerShell:

  ```powershell
  ./bundle_app_windows.ps1 -CI
  ```

  `-CI` is optional. The versioned ZIP in `dist/` contains the executable and current PDF guide. Its unpacked contents are in `dist/windows/NITools_v<version>/`.

- **macOS:**
  The `bundle_app_macos.sh` bash script is used, which also leverages `create-dmg` to package the `.app` into a `.dmg` installer.
  For CI builds, it's run with the target architecture and the `--ci` parameter:

  ```bash
  bash ./bundle_app_macos.sh x86_64 --ci # For Intel Macs
  bash ./bundle_app_macos.sh arm64 --ci  # For Apple Silicon Macs
  ```

  To run locally, specify the desired architecture (`x86_64` or `arm64`) and you can omit `--ci`.
  Ensure `create-dmg` is installed (`brew install create-dmg`) before running the macOS bundling script.

Both scripts use locked dependencies and separate build folders per platform/version. They preserve other builds in `dist/`; rebuilding the same version reuses that version's output paths. The release workflow tests and builds the same commit on all three targets, then creates a **draft** with all packages and SHA-256 checksums. It does not automatically publish the release. See the [2.0 release checklist](docs/RELEASE_2_0.md) for remaining qualification and version-bump instructions.

## 🤝 Contributing

Contributions welcome!

- Open an [Issue](https://github.com/joanroig/nitools/issues)
- Submit a Pull Request

Kits and Groups use version-bounded binary decoders for stored sample references. Large Group scans decode across up to eight CPU cores. See [DECISIONS.md](docs/DECISIONS.md) for the supported structures, validation and measured performance.

## ⚖️ Legal and content rights

NITools is an independent interoperability tool, unaffiliated with Native Instruments, Roland, Steinberg or other product vendors. Product names and trademarks identify compatibility; they do not imply endorsement or grant trademark rights.

The release must not include vendor plug-ins, factory kits, presets, samples, preview audio, prepared Maschine projects, activation data, decompiler output or vendor artwork. NITools implements readers for the supported file structures. Optional rendering uses software and content already installed and authorized on the user's computer. It does not supply those products or bypass their activation.

Use only content you are authorized to access, and check the applicable content and software licenses before exporting or sharing anything. A right to use a sound in music does not necessarily permit redistribution as a sample pack, preset, kit or standalone preview. NITools does not grant those rights. Prepared-state caches and exported audio can contain third-party material; keep them out of public issues, pull requests and release packages.

NITools' GPL license permits commercial as well as personal use of the software. It does not relicense the input libraries or grant rights to their extracted or rendered content. Applicable law and third-party agreements still matter; this documentation is not legal clearance for a particular library, reverse-engineering activity or use.

See [third-party notices](THIRD_PARTY_NOTICES.md) for dependency licenses and [the release-content policy](docs/RELEASE_CONTENTS.md) for packaging checks. Warranty and liability are governed by the [GPL license](LICENSE).

## 📜 License

This project is licensed under the [GPL-3.0 License](LICENSE).
