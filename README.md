<p align="center">
  <a href="https://github.com/joanroig/nitools">
      <img alt="NITools" src="img/logos/nitools.png" width="140px">
  </a>
</p>

<h1 align="center">NITools</h1>

<p align="center">
  Unofficial tools to transform <b>Native Instruments</b> resources for use on other devices and workflows.
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
  <table align="center" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td valign="middle" style="padding-right: 20px;">
        <a href="http://instagram.com/moaibeats"><img src="img/icons/moai.png" alt="Moai Beats" width="100"></a>
      </td>
      <td valign="middle" align="left">
        <p align="center"><b>Created by Moai Beats</b></br>Follow and stream to support me •ᴗ•</p>
        <p align="center">
          <a href="https://open.spotify.com/artist/5Zt96vfBQXmUB3fs3Qkm5q"><img src="img/icons/spotify.png" alt="Spotify" width="40"></a>
          &nbsp;&nbsp;
          <a href="https://music.apple.com/es/artist/moai-beats/1466043534"><img src="img/icons/applemusic.png" alt="Apple Music" width="40"></a>
          &nbsp;&nbsp;
          <a href="http://youtube.com/moaibeats?sub_confirmation=1"><img src="img/icons/youtube.png" alt="YouTube" width="40"></a>
          &nbsp;&nbsp;
          <a href="https://moaibeats.bandcamp.com"><img src="img/icons/bandcamp.png" alt="Bandcamp" width="40"></a>
        </p>
      </td>
    </tr>

  </table>
</p>

## ⬇️ Download

Pre-built executables for **Windows** and **macOS** are available on the [Releases page](https://github.com/joanroig/nitools/releases).

## ✨ Overview

**NITools** is an unofficial, **multi-platform** suite of tools designed to **bulk extract, convert, and repurpose Native Instruments content** for broader workflows.

The initial idea was to export Maschine groups to use them in the Roland SP 404 MK2. Since then, the project evolved to allow configurable parameters to export for other devices and to export more data.

### Key Features

- **GUI & CLI:** Use via graphical interface or command line for maximum flexibility.
- **Portable:** Pre-built executables, no Python installation required.
- **Cross-Platform:** Supports Windows and macOS.
- **Maschine Groups Exporter:** Extract and process kits/samples from `.mxgrp` files, ignoring internal VSTs and FX.
- **NKS Previews Exporter:** Convert NKS audio previews to WAV for one-shot instruments on other platforms.
- **Battery Kits Exporter (WIP):** Early-stage tool to parse `.nbkt` kits for future export support.

## Modules

### <img alt="Groups Exporter" src="img/logos/groups.png" width="16px"> **Groups Exporter (Maschine)**

- Scans a folder for all Maschine group files and parses sample data.
- Configurable normalization, sample rate, bit depth, and silence trimming.
- Customizable export naming to optimize bulk loading (e.g., Roland SP-404 MK2).
- Pad reorder matrix and filtering options.
- Option to fill blank pads with a default sample.
- Option to include group preview samples.

### <img alt="Groups Exporter" src="img/logos/previews.png" width="16px"> **Previews Exporter (NKS)**

- Converts NKS `.previews` to standardized WAV files for easy browsing outside NI software.
- Configurable normalization, sample rate, bit depth, and silence trimming.

### <img alt="Kits Exporter" src="img/logos/kits.png" width="16px"> **Previews Exporter (NKS)**

- Planned tool for exporting Battery kits, similar in functionality to the Maschine Groups Exporter.

## 📦 Development

### Installation

1. **Clone the repository:**

   ```powershell
   git clone https://github.com/joanroig/nitools.git
   cd nitools
   ```

2. **Set up a Python environment (recommended):**

   - **Conda (recommended):**

     Use the script [rebuild_env.ps1](rebuild_env.ps1), or manually execute:

     ```powershell
     conda env create -f environment.yml
     conda activate nitools
     ```

   - **Venv:**

     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1   # Windows
     # source .venv/bin/activate    # macOS/Linux
     pip install -r requirements.txt
     ```

3. **Install dependencies (if not using conda):**

```powershell
pip install -r requirements.txt
```

### 🛠️ Usage

#### Overview

| Layer    | Tool                      | Path                                               | Purpose                                                        |
| -------- | ------------------------- | -------------------------------------------------- | -------------------------------------------------------------- |
| Launcher | **GUI: Launcher**         | `src/launcher.py`                                  | Central entry point; can launch both GUIs.                     |
| GUI      | **Groups Exporter GUI**   | `src/apps/groups_exporter_gui.py`                  | Extracts and processes **groups/kits** (pads, instruments).    |
| GUI      | **Previews Exporter GUI** | `src/apps/previews_exporter_gui.py`                | Extracts and processes **audio previews** (short demo sounds). |
| CLI      | **Groups Build**          | `src/processors/groups/build_groups_json.py`       | Extract raw **group/kit metadata** into a JSON index.          |
| CLI      | **Groups Process**        | `src/processors/groups/process_groups_json.py`     | Process groups (trim silence, normalize, etc.).                |
| CLI      | **Previews Build**        | `src/processors/previews/build_previews_json.py`   | Extract raw **preview metadata** into a JSON index.            |
| CLI      | **Previews Process**      | `src/processors/previews/process_previews_json.py` | Process preview audio (trim silence, normalize, etc.).         |

#### Quick Start (VS Code)

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

   There are 4 CLI processors that can be launched directly (the GUIs internally call these):

   - **Groups Build** → Builds `all_groups.json` from library kits.
   - **Groups Process** → Processes `all_groups.json` into individual kits.
   - **Previews Build** → Builds `all_previews.json` from audio previews.
   - **Previews Process** → Processes `all_previews.json` into individual preview files.

#### CLI Usage

##### 1. `build_groups_json.py`

Extracts **group/kit metadata** and outputs a combined JSON.

```powershell
python src/processors/groups/build_groups_json.py <input_folder> <output_folder> <generate_txt>
```

- `<input_folder>`: Input library folder (e.g. `D:/Libraries/Native Instruments/`)
- `<output_folder>`: Destination folder (e.g. `./out/`)
- `<generate_txt>`: `true` = also generate `.txt` files, `false` = skip

**Example:**

```powershell
python src/processors/groups/build_groups_json.py D:/Libraries/Native Instruments/ ./out/ false
```

##### 2. `process_groups_json.py`

Processes **group JSON files** into cleaned/usable kits.

```powershell
python src/processors/groups/process_groups_json.py <all_groups_json> <groups_output_folder> [options]
```

Options:

- `--trim_silence` → Remove silence
- `--normalize` → Normalize volume
- `--matrix_json <path>` → Optional custom reorder matrix JSON file
- `--enable_matrix` → Enable pad matrix reorder
- `--filter_pads` → Filter groups: pad 1 contains keywords for pad 1, pad 2 for pad 2, pad 3 for pad 3 (case-insensitive)
- `--filter_pads_json <path>` → Optional custom pad filter keywords JSON file
- `--fill_blanks` → Fill empty pads
- `--fill_blanks_path <path>` → Fill blank pads with a specified WAV file, or pick a random file from a folder of WAVs (default is a silence sample file: `./assets/.wav`)
- `--sample_rate <rate>` → Convert all samples to this sample rate (e.g., `48000`)
- `--bit_depth <depth>` → Convert all samples to this bit depth (e.g., `16`)
- `--include_preview` → Include preview samples from groups .previews

**Example:**

```powershell
python src/processors/groups/process_groups_json.py ./out/all_groups.json ./out/groups/ --trim_silence --normalize --enable_matrix --filter_pads --fill_blanks --fill_blanks_path ./assets/.wav --sample_rate 44100 --bit_depth 24 --include_preview
```

##### 3. `build_previews_json.py`

Extracts **audio preview metadata** and outputs a combined JSON.

```powershell
python src/processors/previews/build_previews_json.py <output_folder>
```

- `<output_folder>`: Destination folder (e.g. `./out/`)

**Example:**

```powershell
python src/processors/previews/build_previews_json.py ./out/
```

##### 4. `process_previews_json.py`

Processes **preview JSON files** into cleaned/usable audio previews.

```powershell
python src/processors/previews/process_previews_json.py <all_previews_json> <previews_output_folder> [options]
```

Options:

- `--trim_silence` → Remove silence
- `--normalize` → Normalize volume
- `--sample_rate <rate>` → Convert all samples to this sample rate (e.g., `48000`)
- `--bit_depth <depth>` → Convert all samples to this bit depth (e.g., `16`)

**Example:**

```powershell
python src/processors/previews/process_previews_json.py ./out/previews.json ./out/previews/ --trim_silence --normalize --sample_rate 44100 --bit_depth 24
```

## 🤝 Contributing

Contributions welcome!

- Open an [Issue](https://github.com/joanroig/nitools/issues)
- Submit a Pull Request

The tools development was focused on extracting sample paths from binary files instead of doing proper decompiling. See the document [DECISIONS.md](docs/DECISIONS.md) for more insights on how the processing was built if you plan to enhance it.

## ⚖️ Legal Disclaimer

This project is an **independent, open-source tool** developed for educational and interoperability purposes.

- It is **not affiliated with, endorsed by, or connected to Native Instruments GmbH**, **Roland Corporation**, or any other company.
- All product names, trademarks, and brands mentioned (e.g. _Native Instruments_, _Roland_, _Maschine_, _Battery_, etc) are the property of their respective owners and are used strictly for **identification and compatibility purposes**.
- This project does **not** contain any proprietary source code, file formats, or assets from Native Instruments or Roland.

The software is intended to be used **only with legitimately purchased content** and exclusively for personal use. Users are responsible for ensuring compliance with the license terms of their software and content libraries.

The authors do **not encourage, condone, or accept responsibility** for:

- Any unauthorized distribution or misuse of copyrighted material,
- Any violation of third-party license agreements or terms of service,
- Any data loss or damage arising from the use of this tool.

This software is provided **“as is”**, without warranty of any kind.

## 📜 License

This project is licensed under the [GPL-3.0 License](LICENSE).
