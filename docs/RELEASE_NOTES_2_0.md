# NITools 2.0.0

**Unreleased draft.** This version is being kept in local commits. No 2.0 tag, push or release is authorized at present.

The GUI now uses PySide6-Essentials (LGPL) instead of PyQt6. NITools itself remains GPL-licensed. macOS packages require macOS 13 or later.

Windows packages exclude Microsoft runtime DLLs. Open `NITools.exe` after extracting the complete ZIP; its launcher offers a verified download from Microsoft when the runtime is missing or outdated. Vendor software screenshots and the old bundled product catalog have been removed. Preview product names are resolved from local Native Access metadata when available. The original home screen is preserved; its music-service icon provenance remains part of the review required before publication.

NITools 2.0 replaces the old path-recovery heuristics with structured Battery and Maschine decoders, improves bulk export speed and progress, and adds optional instrument rendering on Windows.

## Upgrade from 1.x

**Rebuild your kit and group JSON indexes using the Process tab.** Old indexes are rejected because they do not contain the validated sample references used by this release. Use a fresh export folder: exported files now include their sample names, and previous numbered files are not renamed or deleted.

Saved audio, matrix and filter preferences remain active. Review those settings before exporting. Skip existing files checks file existence, so disable it or choose a new destination when changing audio or render settings.

## Changes

- Decode complete stored sample references, original pad/cell numbers and multiple sample zones. Missing files are reported with their exact references instead of guessing replacements.
- Support Battery cells above 16, older supported Maschine archive versions and Maschine Audio-module samples.
- Process large Maschine libraries with bounded parallel decoding. All three exporters share parallel audio conversion, live progress, cancellation and atomic output writes.
- Export readable filenames such as `01_Kick.wav` and `01_02_Kick.wav`; preserve slot numbering and separate sample zones.
- Use consistent Process/Export tabs and audio settings across Groups, Kits and Previews. The Activity panel supports following new messages, copying logs and opening a larger reader.
- Optionally render external VST2 instruments from their saved presets on 64-bit Windows.
- Optionally render internal Maschine synths and hosted instruments through the installed Maschine 3 VST3. Kits load automatically during export or through a resumable preparation queue. Successful preparations are cached; failed kits are reported and can be retried.

## Compatibility and limits

- Sample and preview export target Windows and macOS. The release workflow is configured to test/build Windows, Intel macOS and Apple Silicon macOS, but the current candidate has only been built and tested locally on Windows. macOS packaging and library workflows remain unverified.
- **Instrument rendering is experimental and Windows-only.** Automatic preparation has been tested with Maschine 3.7.1 and its default hosted-editor layout. The matching installed plug-ins and licensed content are required. No Native Instruments software, samples or presets are included.
- Instrument export renders one note per identified instrument pad. It is not a multisampled instrument or a pattern bounce. Sample pads continue to export their source audio. Direct VST2 rendering does not reproduce surrounding Maschine effects.
- Unknown file layouts, missing content, loading timeouts and failed renders are reported as incomplete work. Support is demonstrated for the tested files, not every historical or future NI format or plug-in.
- Windows and macOS packages are not signed/notarized. Independent clean-machine and listening checks remain outside the completed local qualification.

See the included PDF or [User Guide](GUIDE.md) for setup, automatic preparation, command-line options and troubleshooting.
