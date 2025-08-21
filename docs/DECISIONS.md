# Parsing Decisions

This document outlines the key decisions and parsing rules applied to extract the maximum amount of usable data from `.mxgrp` files.

The initial focus was on **Battery** since it exclusively supports sample files. However, extracting sample paths from Battery proved more difficult than from **Maschine**.  
For this reason, the **Maschine Parser** was implemented first, prioritizing sample extraction while discarding internal sound generators and VST references.

## Maschine vs. Battery

Maschine can use internal sound generators (e.g., for a Kick), while Battery relies entirely on sample files:

![Maschine vs Battery Kit Comparison](img/maschine%20vs%20battery.png)

Because of the complexity of exporting anything else than samples, all non-sample properties are ignored during extraction.

## Maschine `.mxgrp` Parsing Rules

Maschine can have single samples or multiple samples assigned to a pad, samples can be assigned to regions. To simplify, we call pads with single samples `sample` and pads with multiple samples `multisample`.

The goal is to get a 16-sound pack for each Maschine group, so in the final export the tool will select the best sample from each multisample.

- **Expansion Name**  
  Extracted from the two lines following the keyword `serialization::archive`.

  - If these two lines differ, the parent folder name is used as a fallback.

- **Kit Name**  
  Always derived from the `.mxgrp` file name, trimmed to remove spaces.

- **Pad Assignment**  
  Pads are assigned sequentially starting from **1** for each sample or multisample.

  - No wraparound occurs (pad numbers can exceed 16).
  - A warning is printed if more than 16 pads are detected.

- **Sample Path Handling**

  - Sample paths split across multiple lines are merged.  
    (e.g., if a line does not end with `.wav` but the next line does, and the path begins with `Samples/`, `//Samples/`, or `*Samples/`).
  - Only paths starting with `Samples/`, `//Samples/`, or `*Samples/` are considered valid.
  - All other paths (e.g., `C:/`, `/Users/`, VST references) are ignored.

- **Multisample Detection**

  - A multisample is identified when a sample’s preceding line matches the expansion name  
    (or appears within the previous 4 lines, skipping garbage lines).
  - Consecutive samples with this property are grouped into a multisample.
  - If a multisample contains only one sample, it is downgraded to a regular sample.

- **Multisample Export**

  When exporting multisamples, the goal is to select a single representative sample per multisample. The selection follows a priority order based on note designation in the filename:

  1. First, select the sample ending with `_C4` (case-insensitive).
  2. If `_C4` is not found, select `_C3`.
  3. If neither `_C4` nor `_C3` exists, select the sample ending with `_C*`, where `*` is any **single digit** (e.g., `_C1`, `_C5`).
  4. If no samples match the above, select the first sample in the multisample.

  This ensures consistency in exported kits, prioritizing central octave samples (`C3`, `C4`) while maintaining a fallback for any single-note multisample.

- **Cleanup Rules**

  - Consecutive duplicate sample paths are removed.
  - Empty multisamples are deleted.
  - Kits with no valid samples are skipped, with a warning printed.
  - Garbage lines (length = 4 or containing disallowed characters) are ignored during multisample grouping.

- **Output Format**  
  Each parsed kit outputs:
  - Expansion name
  - Kit name
  - Base path
  - List of samples, including:
    - Type (sample or multisample)
    - Name
    - Pad number
    - File paths
