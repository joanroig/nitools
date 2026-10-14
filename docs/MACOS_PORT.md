# macOS port and qualification

The port is implemented but **has not been run with Maschine on a real Mac**.
It must not be advertised as qualified full macOS support yet.

## Setup

Use macOS 13 or newer, Python 3.13 and `uv`. Both Intel and Apple Silicon have
matching Pedalboard wheels for Python 3.13. The app and installed plug-ins must
use compatible architectures. Run `uv sync --locked --python 3.13`, then `bash run.sh`.

Install/authorize Maschine 3 and the instruments/content required by your kits
separately. No NI software or prepared template is included. NITools looks for
`Maschine 3.vst3` in the user and system `Library/Audio/Plug-Ins/VST3` locations;
the Browse button can select another `.vst3` bundle.

## Rendering and automatic preparation

Enable **Render instruments through Maschine 3** in Groups Export. This route
handles internal synths and instruments hosted by Maschine. The separate direct
VST2 DLL route remains Windows-only and is disabled in the Mac UI.

The Cocoa adapter opens only NITools' isolated hosted editor. It targets A1 in
the default Ideas layout through a private file-URL pasteboard and the editor's
drag destination, then verifies the group and all 16 sound names in captured
state. It does not send desktop mouse/keyboard input, change the shared
clipboard, attach to standalone Maschine, or request Accessibility access.
Unexpected layouts, ambiguous views, dialogs or mismatched states fail the kit.

The same queue, timeout/cancellation, cache validation, resume, host recycling
and MIDI rendering logic are shared with Windows. Mac cache keys include the
bundle executable identity and running architecture. Existing Windows cache
keys are preserved. Assisted preparation remains available as a fallback.

The adapter relies on Maschine's Qt/Cocoa view and default layout, not a public
NI batch API. Apple documents the [drag-destination lifecycle](https://developer.apple.com/documentation/appkit/nsdraggingdestination).
That API documentation and synthetic tests do not establish that Maschine
accepts these events on the target system.

## Required real-Mac check

From the repository on each target architecture, run:

```bash
uv run --locked --python 3.13 python scripts/qualify_macos.py "/path/to/Kit.mxgrp"
```

Use a kit with both an internal synth and a hosted instrument. The command
prepares the kit, checks cache-only resume without host creation, renders every
instrument pad and checks finite non-silent audio and unchanged source bytes.
Use a fresh `--output` directory to test cold preparation; the default is
`tmp/macos-qualification`. Listen to the WAVs and check GUI cancellation, missing
content, unusual layouts and a multiple-kit batch separately.

The output contains licensed state/audio and must remain private. CI runs the
synthetic suite on Windows, Intel Mac and Apple Silicon, including a Mac-only
Cocoa bridge check. CI cannot qualify Maschine without its installed/licensed
software. No CI job or release has been dispatched from this local checkout.

Build using `bash bundle_app_macos.sh arm64 --ci` or `x86_64 --ci`. Publication
remains gated by `packaging/release_review.json` and the release checklist.

The Tests workflow has an optional **package** input for building test artifacts without creating a release. It is off by default and has not been run for this change.
