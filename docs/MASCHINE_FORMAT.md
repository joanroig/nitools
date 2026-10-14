# Maschine kit decoding

The `.mxgrp` reader follows the serialized object graph sequentially. It does not search for Sound frames, module names, sample suffixes or Zone byte patterns. Ghidra analysis of the locally installed Maschine 2 archive loaders established the field order and class-version branches; Rea is a research aid, not a runtime dependency.

The implementation has three layers:

- `src/formats/portable_archive.py`: bounded portable integers and UTF-8, class registration, tracked object references, pointers and recursion/object limits.
- `src/formats/maschine_schema.py`: explicit readers for Group, Sound, mixing/routing parameters, sampler zones, Audio takes, plug-in state, internal synthesis, effects and supporting collections. Unknown schemas fail with an archive offset. Length-prefixed binary state remains opaque.
- `src/formats/maschine.py`: projects decoded objects into the existing exporter/index contract. Stored paths, library aliases, pad order and names remain exact. Plug-in state bytes are returned only when requested by the rendering route.

`parser: structured-v1` identifies the existing JSON contract, not the implementation. New results additionally contain `format_details.decoder: sequential-boost-v2`. Rebuild the Groups index to record this provenance and recover legacy PluginHost version 0 metadata. Existing compatible indexes remain usable. Diagnostic source offsets now point to serialized object records, not pattern matches.

## Scope

This is a kit extraction projection, not a complete Maschine project/DSP implementation. It consumes every Sound and its module chain, then reads the Group name. Group effects, patterns and other trailing records after that point are not decoded or validated. Nonempty snapshot maps and nonempty event-ordering trees are explicitly unsupported; none occurred within the consumed portion of the checked library. Unknown future versions are errors, not triggers for a heuristic fallback.

Prepared-project MIDI routing is separate: `maschine_project.py` still uses the bounded legacy frame locator in `maschine_project_frames.py`. The kit decoder never imports it. That patching route is not a full Project deserializer. Native rendering still requires the user's installed and licensed Maschine/plugins; no synthesis or effects DSP is reproduced here.

## Local validation, 2026-10-14

The production reader decoded all **5,849 installed kits**, covering archive versions 10 and 12–19, without errors. SHA-256 checks confirmed comparison inputs had not changed. Compared with the saved previous-decoder baseline, every kit name, Sound name, pad order, sample path, alias, library field, empty-zone count and sample object ID matched. Legacy PluginHost version 0 metadata improved for **198 instrument records**. Diagnostic offsets and decoder provenance intentionally differ.

An eight-process production comparison initially took **54.0 seconds**, versus **8.3 seconds** for the earlier scanner baseline on this machine. This is a substantial indexing cost for consuming complete Sound structures; it is not an audio-export benchmark. Exporting an existing index retains the existing audio workers. Instrument rendering rereads source kits and therefore also incurs the new decoding cost.

Across 20 real kits, all 26 previously supported VST2 state chunks compared byte-for-byte equal. Synthetic fixtures exercise Unicode/empty names, multiple/empty zones, class tracking, malformed vectors, truncation, unknown schemas and opaque chunks containing fake sample/class markers. Audio module versions 0–7 and Take versions 0–2 have synthetic boundary coverage. The full Python suite passed 109 tests with one real-Cocoa-only skip. This does not qualify Mac runtime behavior or every third-party plug-in.

Tests generate original synthetic archives in Python. Installed kits, executables, native decompilation output, extracted state and corpus reports remain outside tracked source. No proprietary binary, sample or preset was added. The prior packaged executable must be rebuilt to include this reader; source tests do not qualify that older executable.
