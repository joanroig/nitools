# NITools User Guide

This guide provides a straightforward overview of how to use the NITools graphical user interface (GUI) applications.

## 1. Introduction

NITools is a suite of unofficial, multi-platform tools designed to help you extract, convert, and repurpose Native Instruments content for use in other workflows and devices.

## 2. Installation

For most users, the easiest way to get started is by downloading the pre-built executables for **Windows** and **macOS** from the [Releases page](https://github.com/joanroig/nitools/releases).

Windows packages target 64-bit Windows 10/11. Extract the entire ZIP and open **NITools.exe**. If the required Visual C++ runtime is missing or outdated, the launcher offers **Download and install**, retrieves Microsoft's official installer, verifies its digital signature, and opens it for you. Approve installation only if you want to proceed; Microsoft may request administrator access or a restart. The runtime is installed separately and is not bundled with NITools. An official download-page link is also available for manual or offline setup.

macOS packages require **macOS 13 or newer** and are provided separately for Intel and Apple Silicon. The GUI uses the open-source PySide6 binding. This does not change NITools' GPL license or the rights required for third-party content.

If you are a developer and wish to run NITools from source, please refer to the [Development section in README.md](https://github.com/joanroig/nitools#development) for detailed installation and environment setup instructions.

## 3. Running the NITools Launcher

The `NITools Launcher` is the central entry point for all GUI tools. It allows you to easily access the different exporters.

To start the Launcher:

- **Windows:** Double-click the `NITools.exe` executable (if using a pre-built release).
- **macOS:** After downloading the `.dmg` file, open it and drag `NITools.app` to your Applications folder.
  - If the app does not open: - Go to `System Settings` > `Privacy & Security` and press `Open Anyway`.
  - If it still does not open, double-click the `fix.command` script located in the `.dmg` volume. Then, go to `System Settings` > `Privacy & Security` and press `Open Anyway` again. Finally, open the `NITools.app` from your Applications folder and, if prompted, go to `System Settings` > `Privacy & Security` and press `Open Anyway` one last time.

- **From Source (Python):** Run `uv sync --locked` from the repository, then `./run.ps1` on Windows or `bash run.sh` on macOS (Python 3.13).

Once launched, you will see the main window:

![NITools Launcher](<img/nitools launcher.png>)

_Screenshot of the NITools Launcher main window._

From here, you can select which tool you want to use.

## 4. Groups Exporter

The `Groups Exporter` is designed to extract and process Maschine groups (kits and samples) from `.mxgrp` files.

To open the Groups Exporter, click the "Groups Exporter" button in the Launcher.

### Step 1: Process Groups

This step scans your Native Instruments library for Maschine group files and creates a combined JSON index of their metadata.

The decoder reads serialized sample references and sound slots. It preserves exact filenames, including Unicode characters, and does not assemble paths from extracted text fragments. Unsupported or malformed files are reported as errors.

Validated archive layouts include versions 10 and 12–19. If an earlier build reported "Unsupported Maschine archive version 10", rerun **Process Groups** with the updated app to rebuild the incomplete index.

![Groups Exporter - Build JSON](<img/nitools groups process.png>)
_Screenshot of the Groups Exporter "Process Groups" tab._

1. **Library folder:** Select the root folder of your Native Instruments library (e.g., `D:/Libraries/Native Instruments/`).
2. **Index folder:** Choose where the `all_groups.json` file will be saved (e.g., `./out/`).
3. **Save a text report for each group:** Also save decoded sound names, sample references and source offsets as `.txt` files for troubleshooting.
4. **Click "Process Groups"** to start the process.

### Step 2: Export Groups

After building the JSON, this step processes the extracted group data into cleaned and usable kits, applying various transformations.

Rebuild indexes made with earlier versions in **Step 1** and select a new output folder for the first export. The exporter requires an index from the current structured decoder and rejects older indexes before exporting. Existing files from older exports can contain guessed or substituted samples; disable **Skip existing files** when replacing those exports. Skipping checks whether a destination exists; it does not compare its audio settings. Use a fresh folder or turn skipping off when changing conversion settings.

Every sample zone is exported, including stored takes in Maschine's Audio module. A pad with several zones produces files such as `01_01_Kick.wav` and `01_02_Kick.wav`; the exporter no longer chooses one sample by its note-name suffix. Repeated references remain repeated, and empty slots retain their numbers. Sample export does not apply Maschine effects, envelopes or tuning. Optional instrument rendering can fill instrument pads as described below. The optional matrix remaps pads 1–16; higher cell numbers are preserved.

Relative paths are resolved against the decoded reference root, and absolute paths are used as stored. Maschine's `//Samples/` library namespace resolves under its own library root. Missing references are listed in the log and make the export incomplete; a similar filename elsewhere is never substituted. Audio conversion failures also report an incomplete export and preserve any previous output file. The log shows each kit/group as it starts and finishes. The progress dialog shows completed kits/groups, the current name, and live exported/skipped/problem counts. The final log lists exported, skipped, unresolved, and failed files. Audio conversion uses up to four workers automatically; cancellation stops queued work and discards unfinished files.

![Groups Exporter - Process Groups](<img/nitools groups export.png>)
_Screenshot of the Groups Exporter "Export Groups" tab._

1. **Index file:** This field will automatically populate with the `all_groups.json` generated in Step 1. You can also manually select a different JSON file.
2. **Export folder:** Choose the destination folder for your processed kits (e.g., `./out/groups/`).
3. **Audio settings:**
   - **Skip existing files:** If checked, samples that already exist in the output folder will be skipped.
   - **Trim silence:** Removes silence from the beginning and end of samples.
   - **Normalize:** Normalizes the volume of the samples.
   - **Sample rate:** Convert all samples to a specified sample rate (e.g., `44100`, `48000`).
   - **Bit depth:** Convert all samples to a specified bit depth (e.g., `16`, `24`).
   - **Include preview samples:** Includes the group preview samples in the export.
4. Expand **Pad and instrument options** to access **Pad Reorder Matrix (4x4)**:
   - **Enable matrix reorder:** Check this to reorder pads according to a custom 4x4 matrix. Click "Show Matrix" to configure the mapping (e.g., for SP-404 MK2 compatibility).
5. **Pad Filter Keywords:**
   - **Enable pad filtering:** Check this to filter pads based on keywords. Click "Show Pad Filter Editor" to define keywords for each pad (e.g., "kick" for Pad 1, "snare" for Pad 2).
6. **Fill Blank Pads:**
   - **Fill blank pads:** Check this to fill any empty pads in a group.
   - **Fill blanks path:** Specify a WAV file to use as a default sample, or a folder containing WAVs from which a random sample will be picked.
7. **Click "Export Groups"** to start processing and exporting the groups.

Pad filtering and filling empty slots are disabled for new configurations. Previously saved preferences still apply. Filling blanks only affects identified empty slots; it does not replace missing sample references, instrument pads, or slots whose contents cannot be classified beyond having no sample reference.

### Optional instrument rendering (64-bit)

**macOS status:** Automatic preparation and Maschine rendering are experimental and have not been verified on a real Mac. Direct VST2 DLL rendering is Windows-only and disabled on Mac. See [Mac qualification](MACOS_PORT.md) before relying on unattended batches.

Open **Export Groups → Pad and instrument options**. Both rendering options are off by default. They need the original `.mxgrp` files, matching installed instruments and their licensed content. Rendering rereads each original kit, so existing structured indexes can use the option; rebuild indexes to recover Audio-module samples when exporting with rendering disabled.

- **Render external VST2 instruments:** Load each supported instrument's saved chunk into its installed 64-bit VST2 DLL and render one note. Massive and Reaktor/Monark have been tested. Standard VST2 folders are searched automatically; an additional folder takes precedence. A VST3 installation alone does not satisfy this option. This route renders the instrument's main output without the surrounding Maschine effect chain.
- **Render instruments through Maschine 3:** Use the installed Maschine 3 VST3 to render built-in synths such as Drum Synth and Bass Synth. NITools automatically loads and caches kits when needed. With external rendering also enabled, supported VST2 pads take the direct route and other instrument pads use Maschine. With only Maschine rendering enabled, all identified instrument pads use the prepared kit, including its hosted VSTs and effects.

For a large library:

1. Build/select the Groups index, enable **Render instruments through Maschine 3**, and leave **Automatically prepare uncached kits during export** checked. Export normally: preparation runs only when an instrument pad actually needs rendering. Skipped output files do not start a preparation host.
2. To prepare ahead of time, click **Prepare indexed kits… → Prepare indexed kits**. This queues the indexed kits needing Maschine under your selected rendering options. Sample-only kits are omitted, and valid cached kits are skipped.
3. NITools opens its own Maschine editor and sends each exact `.mxgrp` file to it automatically. Keep this editor untouched. The queue checks the Group and all 16 Sound names, enables Drumkit MIDI routing and saves each verified state immediately. No library search, typing or dragging is needed.
4. Watch live progress and errors in the queue. **Cancel** stops the owned host while retaining completed kits. Run the queue again to resume or retry failures. A stalled or failed kit is reported; the next kit gets a fresh host. Increase **Kit loading timeout** for slow instruments (default 120 seconds, plus up to 30 seconds for a cold host). A `preparation-report.json` in the cache folder records the latest queue run.

The batch queue reuses one warm host, recycling it after 64 prepared kits to bound native resource accumulation. Uncached preparation during export shares the render host for that kit. Changed kit bytes or an updated Maschine plug-in invalidate the cached state automatically. To require prepared states only, turn off automatic preparation.

If automatic loading fails on an unusual setup, **Assisted single kit…** remains available. Select the original kit, click **Open Maschine editor**, load it into the only Group **A1**, leave MIDI routing at its defaults, resolve missing-content messages, then close the editor. NITools validates and caches that state for the same export workflow.

Double-clicking an `.mxgrp` opens standalone Maschine; that does not load NITools' hosted instance. Preparation uses a separate host and never overwrites the original kit. Prepared states stay in the local NITools user cache and are not part of the JSON index or application package. They retain content references; the installed content must remain available.

For unattended CLI preparation from the repository:

```powershell
$env:PYTHONPATH = 'src'
uv run python -m processors.maschine_prepare out/all_groups.json
```

Use `--maschine_cache`, `--maschine_plugin` and `--timeout` to override the cache, installed plug-in or loading deadline. Add `--external_vst2` when direct VST2 rendering will handle those pads. Ctrl+C stops the batch and keeps completed caches. Export's `--render_maschine` also prepares automatically; `--no_auto_prepare` disables that, and `--prepare_timeout` controls its loading deadline.

**VST2 note** affects direct external rendering only. Maschine uses each pad's saved pitch and Drumkit routing. **Velocity**, **Hold** and **Release** apply to both routes. Increase Release for longer tails. Rendering starts at 48 kHz with floating-point audio, then uses the normal trim, normalize, sample-rate and bit-depth options. One file is produced per instrument pad, such as `12_Tom Manhatten.wav`. This is a single-note export, not a multisampled instrument, pattern bounce or complete kit-mix recreation. Existing sample pads still export their original files.

Rendering costs more than copying samples. Direct plug-ins run in bounded parallel workers; Maschine loads once per kit and renders that kit's instrument pads sequentially. Skip existing files avoids synthesizing those files. Use a fresh destination or disable skipping when changing render settings. Cancel stops owned render processes. Missing plug-ins, unavailable prepared states, unsupported layouts, timeouts and silent output are logged as errors; previous output files are preserved.

Automatic file loading and the preparation reader are qualified against Maschine **3.7.1**, its default editor/Ideas layout and project archive version 20. The Windows file-drop adapter depends on that layout and the host's OLE drop target; it is not a public NI batch API. Unknown layouts and non-default routing are rejected where detected. Custom MIDI routing, externally routed audio, missing dependencies and unusual plug-ins may require adjustment in Maschine. The option remains experimental; universal plug-in compatibility and identical effect reproduction are not claimed. Battery and Previews keep their sample/preview export workflows.

## 5. Battery Kits Exporter

Open **Kits Exporter** from the Launcher. In **Process Kits**, select the folder containing `.nbkt` files, choose an index output folder, and click **Process Kits**. The decoder preserves stored cell numbers and each cell's complete sample references.

![Battery Kits - Process](<img/nitools kits process.png>)

In **Export Kits**, choose a fresh output folder and click **Export Kits**. Kits are organized by expansion and kit name. Files retain the original sample name: single-zone cells produce `01_Kick.wav`; cells with several zones produce `01_01_Kick.wav`, `01_02_Kick.wav`, and so on. Cell numbers above 16 are supported. The export options work like the Groups Exporter, including audio conversion, matrix mapping, filtering, and existing-file skipping. **Include preview samples** converts an existing preview when one is available; it does not render a new preview.

Missing files are reported with their exact stored reference and resolution root. Restore the expected library location or correct the explicit reference root in the JSON before retrying. There is no filename matching or replacement option. Old numbered exports are not renamed automatically; use a fresh output folder to avoid mixing old and new filenames. Battery synthesis, modulation, and effects are outside the sample export.

![Battery Kits - Export](<img/nitools kits export.png>)

## 6. Previews Exporter

The `Previews Exporter` converts NKS audio previews (`.ogg` files in `.previews` folders) into standardized WAV files, making them easily browsable outside Native Instruments software.

To open the Previews Exporter, click the "Previews Exporter" button in the Launcher.

### Step 1: Process Previews

This step discovers installed Native Instruments libraries and scans their preview folders. Overlapping library registrations are deduplicated. Progress shows the current library, completed libraries and preview count; scanning can be cancelled inside a library. Scan errors appear in the log and `all_previews.report.json`.

![Previews Exporter - Build JSON](<img/nitools previews process.png>)
_Screenshot of the Previews Exporter "Process Previews" tab._

1. **Index folder:** Choose where the `all_previews.json` file will be saved (e.g., `./out/`).
2. **Click "Process Previews"** to start the process.

### Step 2: Export Previews

After building the JSON, this step processes the extracted preview data into cleaned and usable WAV audio files.

![Previews Exporter - Process Previews](<img/nitools previews export.png>)
_Screenshot of the Previews Exporter "Export Previews" tab._

1. **Index file:** This field will automatically populate with the `all_previews.json` generated in Step 1. You can also manually select a different JSON file.
2. **Export folder:** Choose the destination folder for your processed preview WAVs (e.g., `./out/previews/`).
3. **Audio settings:**
   - **Skip existing files:** If checked, samples that already exist in the output folder will be skipped.
   - **Trim silence:** Removes silence from the beginning and end of preview audio.
   - **Normalize:** Normalizes the volume of the preview audio.
   - **Sample rate:** Convert all previews to a specified sample rate (e.g., `44100`, `48000`).
   - **Bit depth:** Convert all previews to a specified bit depth (e.g., `16`, `24`).
4. **Click "Export Previews"** to start processing and exporting the previews.

All three exporters use the same live progress and cancellation behavior. The compact progress window keeps its size and position as filenames change; hover over shortened text to see the full message. Cancel, Escape and the close button request cancellation and keep the window open until active file operations finish. Large Group scans decode concurrently across up to eight CPU cores; small selections avoid the process startup cost. Previews converts up to four files concurrently and reports exported, skipped, filtered and failed files as it runs. Missing files, conversion failures and output-name collisions make the export incomplete. Failed or cancelled conversions preserve existing output files. Processing an index keeps your chosen export folder. "Skip Maschine group previews" skips `.mxgrp.ogg` files, not every preview in a Maschine library.

The windows use **1 Process** and **2 Export** tabs. Sample rate and bit depth sit together under **Audio settings**. Expand **Pad options** in Kits or **Pad and instrument options** in Groups for the additional controls, or **Content options** for preview exclusions. The heading shows how many options are enabled even when collapsed; collapsing a section does not change its settings.

### Activity and troubleshooting output

The compact **Activity** card shows Ready, Processing, Exporting, Complete, Cancelled or Incomplete and the retained message count. An empty card explains where progress will appear.

- **Follow** jumps to the latest output. Scrolling back pauses following so you can read earlier messages; click Follow to resume.
- **Copy** copies the retained log as plain text, including full paths and error details.
- **Open log…** opens a larger, resizable reader with a snapshot of the retained messages. Select individual messages or use **Copy log**.
- **Clear** empties the visible log and is disabled during processing/export. It does not delete indexes or audio.
- **Activity log** in the footer shows or hides the card.

Only the configured number of recent messages is kept (200 by default); copying or opening the log uses that retained history. Index builders also save a `.report.json` file with the complete list of decoding errors. If an export is incomplete, inspect its unresolved references or conversion errors and retry after correcting them.

## 7. Configuration

From the NITools Launcher, you can access a configuration dialog by clicking the `cog` icon in the top-left corner.

![Configuration Dialog](<img/nitools configuration.png>)
_Screenshot of the Configuration Dialog._

This dialog allows you to adjust global settings for the applications, such as UI style.

## 8. Troubleshooting and Support

If you encounter any issues or have questions, please visit the [NITools GitHub Issues page](https://github.com/joanroig/nitools/issues) to report bugs or seek assistance.

## 9. Content rights and privacy

NITools is GPL-licensed software. Its license allows commercial and personal use of the tool, but does not grant rights to Native Instruments or other third-party software, samples, presets or rendered sounds. Use authorized installations and check the licenses for your content before exporting or sharing. Permission to use sounds in music does not necessarily permit distributing the sounds as a library or sample pack.

The app does not include vendor instruments, factory content or prepared projects. Preview product names are read from local Native Access Service Center XML metadata when available. No product catalog is shipped; unknown product IDs keep the Native Browser Preview Library folder name.

Prepared-state caches, exports and diagnostic reports stay on your computer. They can contain proprietary states, audio or personal paths. Do not attach them to public bug reports. Prefer the error text with private paths removed and a synthetic reproduction. See the repository's legal section and third-party notices for distribution details.
