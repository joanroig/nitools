# NITools User Guide

This guide provides a straightforward overview of how to use the NITools graphical user interface (GUI) applications.

## 1. Introduction

NITools is a suite of unofficial, multi-platform tools designed to help you extract, convert, and repurpose Native Instruments content for use in other workflows and devices.

## 2. Installation

For most users, the easiest way to get started is by downloading the pre-built executables for **Windows** and **macOS** from the [Releases page](https://github.com/joanroig/nitools/releases).

If you are a developer and wish to run NITools from source, please refer to the [Development section in README.md](https://github.com/joanroig/nitools#development) for detailed installation and environment setup instructions.

## 3. Running the NITools Launcher

The `NITools Launcher` is the central entry point for all GUI tools. It allows you to easily access the different exporters.

To start the Launcher:

- **Windows:** Double-click the `NITools.exe` executable (if using a pre-built release).
- **From Source (Python):** Run `src/launcher.py` using your Python environment.

Once launched, you will see the main window:

![NITools Launcher](<img/nitools launcher.png>)

_Screenshot of the NITools Launcher main window._

From here, you can select which tool you want to use.

## 4. Groups Exporter

The `Groups Exporter` is designed to extract and process Maschine groups (kits and samples) from `.mxgrp` files.

To open the Groups Exporter, click the "Groups Exporter" button in the Launcher.

### Step 1: Process Groups

This step scans your Native Instruments library for Maschine group files and creates a combined JSON index of their metadata.

![Groups Exporter - Build JSON](<img/nitools groups export.png>)
_Screenshot of the Groups Exporter "Process Groups" tab._

1. **Input folder:** Select the root folder of your Native Instruments library (e.g., `D:/Libraries/Native Instruments/`).
2. **Output folder:** Choose where the `all_groups.json` file will be saved (e.g., `./out/`).
3. **Generate TXT files:** Check this option if you also want to generate `.txt` files alongside the JSON, containing additional information.
4. **Click "Process Groups"** to start the process.

### Step 2: Export Groups

After building the JSON, this step processes the extracted group data into cleaned and usable kits, applying various transformations.

![Groups Exporter - Process Groups](<img/nitools groups process.png>)
_Screenshot of the Groups Exporter "Export Groups" tab._

1. **JSON file:** This field will automatically populate with the `all_groups.json` generated in Step 1. You can also manually select a different JSON file.
2. **Output folder:** Choose the destination folder for your processed kits (e.g., `./out/groups/`).
3. **Options:**
   - **Skip already processed:** If checked, samples that already exist in the output folder will be skipped.
   - **Trim silence:** Removes silence from the beginning and end of samples.
   - **Normalize:** Normalizes the volume of the samples.
   - **Sample rate:** Convert all samples to a specified sample rate (e.g., `44100`, `48000`).
   - **Bit depth:** Convert all samples to a specified bit depth (e.g., `16`, `24`).
   - **Include preview samples:** Includes the group preview samples in the export.
4. **Pad Reorder Matrix (4x4):**
   - **Enable matrix reorder:** Check this to reorder pads according to a custom 4x4 matrix. Click "Show Matrix" to configure the mapping (e.g., for SP-404 MK2 compatibility).
5. **Pad Filter Keywords:**
   - **Enable pad filtering:** Check this to filter pads based on keywords. Click "Show Pad Filter Editor" to define keywords for each pad (e.g., "kick" for Pad 1, "snare" for Pad 2).
6. **Fill Blank Pads:**
   - **Fill blank pads:** Check this to fill any empty pads in a group.
   - **Fill blanks path:** Specify a WAV file to use as a default sample, or a folder containing WAVs from which a random sample will be picked.
7. **Click "Export Groups"** to start processing and exporting the groups.

## 5. Previews Exporter

The `Previews Exporter` converts NKS audio previews (`.previews` files) into standardized WAV files, making them easily browsable outside Native Instruments software.

To open the Previews Exporter, click the "Previews Exporter" button in the Launcher.

### Step 1: Process Previews

This step scans for NKS preview files and creates a combined JSON index of their metadata.

![Previews Exporter - Build JSON](<img/nitools previews process.png>)
_Screenshot of the Previews Exporter "Process Previews" tab._

1. **Output folder:** Choose where the `previews.json` file will be saved (e.g., `./out/`).
2. **Click "Process Previews"** to start the process.

### Step 2: Export Previews

After building the JSON, this step processes the extracted preview data into cleaned and usable WAV audio files.

![Previews Exporter - Process Previews](<img/nitools previews export.png>)
_Screenshot of the Previews Exporter "Export Previews" tab._

1. **JSON file:** This field will automatically populate with the `previews.json` generated in Step 1. You can also manually select a different JSON file.
2. **Output folder:** Choose the destination folder for your processed preview WAVs (e.g., `./out/previews/`).
3. **Options:**
   - **Skip already processed:** If checked, samples that already exist in the output folder will be skipped.
   - **Trim silence:** Removes silence from the beginning and end of preview audio.
   - **Normalize:** Normalizes the volume of the preview audio.
   - **Sample rate:** Convert all previews to a specified sample rate (e.g., `44100`, `48000`).
   - **Bit depth:** Convert all previews to a specified bit depth (e.g., `16`, `24`).
4. **Click "Export Previews"** to start processing and exporting the previews.

## 6. Configuration

From the NITools Launcher, you can access a configuration dialog by clicking the `cog` icon in the top-left corner.

![Configuration Dialog](<img/nitools configuration.png>)
_Screenshot of the Configuration Dialog._

This dialog allows you to adjust global settings for the applications, such as UI style.

## 7. Troubleshooting and Support

If you encounter any issues or have questions, please visit the [NITools GitHub Issues page](https://github.com/joanroig/nitools/issues) to report bugs or seek assistance.
