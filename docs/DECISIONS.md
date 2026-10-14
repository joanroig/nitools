# Binary sample-reference decoding

NITools exports the original samples referenced by supported Battery kits and Maschine groups. Sample export retains every stored zone without applying effects, envelopes, velocity/key ranges or tuning. Groups additionally offers opt-in instrument rendering on Windows, through installed VST2 instruments or prepared Maschine 3 states; this separate path is described below.

## Data flow

| Stage | Battery `.nbkt` | Maschine `.mxgrp` |
| --- | --- | --- |
| Container | Bounded NI Hsin object/class records | Bounded NI Hsin object/class records |
| Payload | FastLZ level 1/2 decoder, then inner NI document | Portable Boost archive, validated profiles for versions 10 and 12–19 |
| References | Length-delimited legacy chunks; UTF-16 component path table | Complete length-prefixed UTF-8 strings in validated sample-reference records |
| Assignment | Zone-to-cell and zone-to-sample-table indexes; stored grid dimensions | Ordered 16-Sound vector; validated Channel and sample-map frames |
| Output | Every cell's sample zones, including duplicate references | Every Sound's sample references, including duplicate references |

The runtime does not depend on Rea, Ghidra, Java, or Native Instruments executables. Rea/Ghidra are research tools for investigating native serialization; the app uses small deterministic Python readers. No native code or proprietary kit fixtures are bundled.

## Battery

`src/formats/ni_container.py` follows NI object lengths and base-class lengths, with bounds and nesting checks. The compressed object contains an explicit compressed length. FastLZ decoding starts after its five-byte header, handles extended lengths and far references, and rejects invalid back-references rather than padding damaged output.

`src/formats/battery.py` follows the decompressed document's chunk lengths and counts. Chunk 75 contains the path table: parent-directory, directory, and filename tokens with UTF-16 text. Joining these serialized components is the format's path representation; names are never repaired or inferred from neighboring text.

The kit contains a fixed 128-cell capacity with a stored visible row/column count. Cell IDs use a 16-column internal stride; exported pad numbers use the visible grid in row-major order. A zone contains a cell ID and a sample-table index. Sample-table order is **not** pad order. Empty cells retain their positions, and grids larger than 4 by 4 are supported.

The reader currently supports the observed Battery 4 container, path-table version 2, and known cell/zone property layouts. Unknown path tokens, property sizes, invalid indexes, malformed lengths, and zones outside the stored grid fail explicitly.

## Maschine

`src/formats/maschine.py` is a partial reader for the observed portable archive versions, not a complete implementation of every Boost class used by Maschine. It validates the archive signature/version, Group header, 16-Sound vector, tracked Channel name-property frames, sample-reference class metadata, object IDs, string lengths, and decoded reference counts. `maschine_modules.py` also reads Audio-module Take/FileLocation records and PluginHost identity/length-delimited state. Instrument DSP and unrelated effect data remain opaque.

Boost archive versions and NI Group/Sound class versions are independent. Profiles cover the observed combinations instead of calculating one version from another. Older parameter records have different object-ID counts and variable-width integer values. The Sampler and Zone class IDs come from their actual registrations; earlier plugins can register common base classes and change those IDs. Library display names and product identifiers may differ. Empty FileLocation records count as serialized zones but produce no missing-file request. Groups containing only instruments, effects or external MIDI keep all sixteen slots with no fabricated sample references.

The reader locates validated binary frames inside that version-bounded archive. It does not extract printable text, merge path fragments, infer multisamples from nearby library names, deduplicate references, or select a representative note by filename. Unknown frame layouts are unsupported; the supported version set should only expand with new fixtures and structural evidence.

Targeted Ghidra analysis of Maschine 2 (SHA-256 `29cbc4c6f085f1d0d8ac8ff6302d39a988085adf3e0c455360c369f536923216`) confirms the Group's `ObjectVector<Sound>` member and the Sampler's `ObjectVector<Zone>` member. The native vector loader reads a declared count and deserializes entries in order. Research scripts, symbol mappings, and pseudocode stay in ignored `tmp/rea-feasibility/`; they are not application dependencies.

Stored path strings, path kinds and offsets are retained in `sample_references`. Resolution translates the known `//Samples/` and legacy `/Samples/` library namespaces for alias paths to the selected library's `Samples` directory without altering the stored reference. A moved library uses the library root discovered from the group location. Absolute FileLocation paths remain absolute; unavailable paths fail instead of triggering a basename search.

## Index and export contract

New indexes carry `parser: "structured-v1"`; old heuristic indexes must be rebuilt. Builders produce a `.report.json` sidecar listing decoded files and per-file errors. A partially decoded library returns a failure status even when its successfully decoded records are saved.

The shared exporter resolves a complete reference against its explicit `sample_root`. There is no fuzzy matching, filename repair, or cross-library search. Missing files and audio conversion errors make the run incomplete and appear in the log. The exporter retains repeated references and each sample-bearing pad's original number unless the user enables matrix remapping.

Both exporters retain the sample stem: single-zone cells use `NN_Sample.wav`; layered cells use `NN_ZZ_Sample.wav`. This naming preserves pad and zone order while making the files recognizable. Expansion and kit/group names form the output folders. Colliding destination folders or invalid matrix mappings fail explicitly. Existing-file skipping is an explicit option; use a fresh folder for the first export after rebuilding an old index.

Preview export converts an existing preview to WAV. It never renders instruments or effects. Filling blank slots is optional and does not resolve missing references. New configurations disable pad filtering and blank filling; existing saved preferences remain in effect.

## Verification

Synthetic tests cover malformed containers, FastLZ extensions/back-references, Unicode paths, cell/zone assignments, duplicate layers, missing paths, output collisions, and GUI worker success/failure reporting. They contain no proprietary library data. Run:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Local corpus qualification is kept under ignored `tmp/structured-qualification/`, with JSON indexes, exported samples, source/output SHA-256 manifests, and result summaries. It establishes compatibility with those input files; it is not a claim that every historical or future NI serialization variant is supported.

On 2026-10-13, all 159 local Battery kits and 139 Maschine groups decoded and exported successfully. All 5,485 raw sample exports matched their resolved source files by SHA-256, with zero missing references or export errors and unchanged input kit/group files. Offscreen Qt workflow checks rebuilt both complete indexes and exported 112 converted WAVs (including two previews) at 48 kHz / PCM24. These checks verify code, GUI worker behavior, and audio readability; native application playback and instrument/effect reproduction are not part of them.


## Performance and live progress

FastLZ back-references copy byte ranges or repeated overlap patterns in bulk. Maschine frame candidates are found with an overlapping binary lookahead; all existing structural checks still run, and UTF-8 decoding waits until the candidate satisfies those checks. The optimized builders produced identical JSON data across the local 298-file corpus.

Audio conversion uses at most four threads and eight pending jobs. Source resolution, collision checks, pad/zone naming, collection order, and counters remain on the coordinating worker. The queue drains before reporting a kit complete. Cancellation is checked before conversion and before replacing the destination; the exporter waits for active jobs to stop and removes their temporary files. Raw copies remain sequential. Audio metadata and samples are read through one libsndfile handle.

Each kit/group logs a start and completion line. Qt receives progress with the current collection and cumulative exported/skipped/problem counts; file updates are limited to ten per second, while collection boundaries always update. The progress dialog stays open until the worker has finished.

One local before/after comparison on 2026-10-13 (Ryzen 9 5900X, existing filesystem cache, fresh destination folders, 48 kHz / PCM24 with trimming, normalization and previews) measured:

| Operation | Before | After |
| --- | ---: | ---: |
| Index 159 Battery kits | 7.98 s | 2.16 s |
| Index 139 Maschine groups | 8.68 s | 5.57 s |
| Export Battery samples + previews | 62.06 s | 39.04 s |
| Export Maschine samples + previews | 56.78 s | 32.06 s |

All 5,783 converted files had identical SHA-256 hashes after accounting for Battery's newly retained filenames. Timing varies with storage, file lengths, options and concurrent activity. Benchmarks and manifests are under ignored `tmp/performance-20261013/`.

## Unified workflows and expanded installed-library check

Kits, Groups and Previews share `ExporterWorkflow` for operation identity, progress, completion checks and cancellation. Controls remain disabled until the QThread has stopped; closing an active window requests cancellation and waits. Processing retains the chosen export destination. All builders report discovery and processing progress and produce index reports; an empty or incomplete index is a failure. The log widget uses Qt's bounded block storage and escapes filenames before HTML rendering.

`AudioExporter` provides atomic output writes, a bounded conversion queue and cancellation checks to all three exporters. Previews now reports missing files and conversion failures instead of returning success, checks output containment/source overwrite/collisions, handles unmatched instrument IDs without stale state, and deduplicates overlapping library scans. Distinct previews with the same destination are reported instead of silently overwriting one another. No basename search is used.

The expanded 2026-10-13 check read all **5,849** `.mxgrp` files installed under `D:\Libraries\Native Instruments`, including the version-10 Amplified Funk files. All decoded successfully and all **140,354** nonempty sample references resolved to existing files. This checks reference decoding and resolution, not 140,354 rendered/exported sounds. The installed preview scan indexed **210,012** unique files. A matched 120-preview conversion took **3.58 s** with the previous serial exporter and **1.12 s** with the shared exporter; every resulting WAV was byte-identical.

The test suite has 62 passing tests, including synthetic legacy layouts, optional parameter values, empty zones, incorrect zone counts, preview failures/collisions, and live process/export/cancel GUI checks across all three tools. Offscreen GUI workers additionally indexed 110 Battery kits, 48 Amplified Funk groups and 345 previews, then produced 175 readable 48 kHz PCM24 WAVs without errors. Evidence, screenshots and qualification scripts remain under ignored `tmp/unified-exporters/`. Native app playback and macOS qualification are not included.

## Full-library Group speed regression and fixed progress geometry

A subsequent profile identified Channel-name candidate scanning as over 98% of decode time. The initial version-10 support tried almost every zero byte in legacy plugin payloads. Candidate selection now requires a canonical tracked ID, the known name-property metadata and following parameter IDs in the binary filter. Every existing integer, string length, UTF-8, property-order and sample-zone check still runs. This does not introduce a fallback path extractor.

Scans of at least 64 groups use a Windows-compatible spawn process pool, capped at eight workers and two pending batches per worker, with 16 files per batch. The coordinator consumes results in source order and owns logs, TXT filenames and the index. This preserves deterministic outputs and bounds queued work. Cancellation drops queued batches and waits for active workers before releasing the GUI. The frozen launcher dispatches multiprocessing workers before importing Qt or running the single-instance check.

Matched full-library runs on 2026-10-13, with TXT diagnostics enabled, logging disabled for the timing comparison, cached inputs and fresh output folders, measured:

| Group builder | Elapsed | Groups indexed |
| --- | ---: | ---: |
| Original heuristic builder | 16.36 s | 5,661 |
| Structured builder before this fix | 275.20 s | 5,849 |
| Optimized decoder, four workers | 17.77 s | 5,849 |
| Optimized decoder, eight workers | 14.75 s | 5,849 |

All 5,849 records from each optimized run exactly matched the preceding structured builder, excluding only the different TXT destination paths. The original builder omitted 188 groups, so its speed is context rather than an equivalent correctness result. These are index-builder timings, not audio-export timings or a promise of identical results on other storage.

All three workflows now use a fixed-size progress dialog with two reserved text lines, middle elision and full-text tooltips. Updating progress does not resize or recenter it. Cancellation leaves a visible disabled Cancel button until the worker stops. Qt progress signals are limited to ten per second while retaining initialization and completion updates.

The suite now has 66 passing tests, including long/empty/Unicode Channel names, integer-width boundaries, actual spawned decoding, per-file failures, ordered results, bounded cancellation and stable dialog geometry after user movement. The three offscreen GUI workflows also rebuilt their indexes and exported 175 readable WAVs again. A separate full Group run through the actual Qt worker, with normal logging and TXT output enabled, finished in 21.76 seconds with 5,849 records, zero errors, 159 observed progress updates and unchanged dialog geometry. The packaged Windows executable also decoded 98 representative installed files through its embedded process pool, matching serial results and bypassing GUI startup in worker processes. The GUI check is offscreen, not native UI/playback acceptance. Benchmark snapshots and current evidence are in ignored `tmp/groups-speed-fix/`.

## Exporter UI polish

The exporters share headings, numbered workflow tabs, a compact two-column audio layout and expandable pad/content options. Existing preferences remain active when a section is collapsed; its heading and tooltip summarize enabled options. Actions stay outside the scrollable form. The activity panel provides status and clearing, respects the configured line limit, preserves a user's scroll position, and reserves warning/error colors for problems. Filenames are escaped in uncolored log messages as well as colored ones. Primary actions respect the configured accent color.

Offscreen checks cover all three windows in dark/light themes at 900×780 and 800×600, with expanded options and activity logs. The 67-test suite passes, including preference retention, collapse/expand, log visibility/clearing and scroll retention. Real GUI workers rebuilt the same 110-kit, 48-group and 345-preview selections and exported 175 readable 48 kHz PCM24 files with zero errors. Screenshots and results are in ignored `tmp/ui-polish/`; native desktop interaction and playback are not covered by these checks.

The initial UI checks missed the owner's saved `[302, 422]` divider sizes: the native 800×749 window gave most of its space to an empty log and clipped the audio controls. The shared splitter now restores a compact log height, directs additional space to the form and bounds Activity to a quarter of the splitter (with a 96-pixel minimum). Sample rate and bit depth labels sit beside their fields to save another row. Existing export preferences are retained.

The 68-test suite includes the real stylesheet, all three exporters, saved `[302, 422]` and `[10, 1000]` layouts, resizing to 800×600/800×749/1200×900, expansion and log visibility. At 800×749 the complete common export form is visible without scrolling; at 800×600 the form can scroll and the action stays outside it. On 2026-10-13, the packaged `NITools-layoutfix-20261013` executable was also opened and inspected on the Windows desktop: Process and Export tabs in all three tools, plus scrolling expanded Group options and hiding/reopening Activity. This native check verifies the layout, not a new audio export or playback run. Build and regression evidence is in ignored `tmp/ui-layout-fix/`.

## Activity reader and 2.0 release preparation

The log now sits in one compact Activity card with a status badge, retained message count and an explanatory empty state. Follow pauses when scrolling back; appending output preserves selection and scroll. Copy and Clear act on retained messages; Clear is disabled while busy. Open log creates a resizable snapshot using a cloned document so wrapping in the reader cannot disturb the compact view. Light/dark warning colors use foreground lightness, since the new transparent log background is not a reliable theme indicator.

The 68 tests were extended to cover these controls, selection preservation and reader isolation. Current Qt workflows again indexed 110 kits, 48 groups and 345 previews and exported 175 readable 48 kHz PCM24 WAVs without errors. The activity build's frozen process pool matched serial decoding for 98 installed files. Native Windows inspection also confirmed the populated card and larger reader after the owner's complete 5,849-group run. Evidence is in ignored `tmp/activity-panel/` and `tmp/release2-audit/`.

The release audit found that the old workflow force-pushed a tag before testing/building and published independently from matrix jobs, while bundlers deleted the entire `dist/` and `build/` trees. Tests now precede each build, every platform checks out the same commit, artifacts are collected before creating one draft, and existing tags are never overwritten. Bundlers use version/platform-specific paths and locked dependencies; the lockfile's project version was corrected without changing dependency versions. README commands, guide screenshots and upgrade instructions have been refreshed. Remaining platform and release checks are recorded explicitly in [RELEASE_2_0.md](RELEASE_2_0.md).

The revised Windows bundler completed from a different working directory and preserved seven earlier build folders. Its ZIP passed integrity checks and the executable again matched serial decoding for 98 files. The PDF guide uses fixed-height image containers to move screenshots intact across page breaks; compression reduced its size while preserving the images. All ten rendered pages were reviewed, including current Launcher, Configuration and all six workflow-tab screenshots. Workflow actionlint, bundler syntax, lockfile consistency and the 68-test suite pass locally. No GitHub issue or pull request was open at the final check; GitHub runner execution, native macOS and clean-machine/playback acceptance remain unverified.

## Optional instrument rendering and Audio-module recovery

The original `.mxgrp` remains the authority. `maschine_modules.py` reads length-delimited PluginHost identity/state and Audio-module Take vectors inside each Sound's bounds. Instrument chunks are included only for rendering, not written into indexes. Built-in synth modules are identified separately from effects and input slots. Audio takes now follow their stored FileLocation records, preserving counts and exact paths.

Direct external rendering uses the public VST2 ABI in a disposable Windows process. It checks plug-in IDs and state support, keeps MIDI buffers alive through the audio callback, compensates reported latency, and rejects invalid or silent audio. Plug-in crashes and timeouts become pad errors instead of terminating the GUI. The normal exporter still controls skipping, conversion and atomic output replacement.

Internal synthesis uses the user's installed Maschine 3 VST3 through Pedalboard. Its saved-state interface accepts complete projects; opening an `.mxgrp` in standalone Maschine does not populate the hosted plug-in. `maschine_loader.py` automates the editor's native Windows OLE file-drop path on the isolated host's main thread, targeting A1 in a fresh project's default Ideas layout. It sends no desktop mouse/keyboard input and never attaches to standalone Maschine. The in-process OLE target property and layout are version-sensitive and qualified on Maschine 3.7.1, not a public NI batch API. `maschine_project.py` verifies the NI/VST3 containers, archive version 20, Group name and all 16 Sound names, then enables the validated Drumkit routing property and updates container lengths. It accepts both untouched and overridden Off states. Unknown layouts fail rather than guessing. No proprietary template is shipped; an empty project comes from the installed engine itself. Assisted single-kit preparation remains a fallback.

Prepared project states are keyed by original kit bytes and installed plug-in identity/size/mtime, with checksum receipts. A kit or plug-in change requires preparation again. One isolated Maschine process is reused for the instrument pads of a kit, restoring saved state before each note. MIDI notes 48–63 address pads 1–16 at their saved pitches. Custom routing and non-primary outputs are outside the qualified setup. This produces a single rendered note per identified instrument pad; sample pads retain their raw-source behavior.

Automatic preparation is enabled within the opt-in Maschine rendering route. It is lazy, so skipped output files never trigger a host. The separate indexed preparation queue reuses a warm host across kits, resets to its empty project between files, and recycles the process after 64 preparations. A parent-enforced per-kit deadline handles native hangs; cancellation, crashes and errors discard only the owned host. Successful states are atomic checkpoints, failed kits are retryable, and the cache's preparation-report.json records the latest batch. Sample-only kits and kits handled entirely by the selected direct VST2 route are skipped. NI documents Group file drops in [Managing Sounds, Groups, and your Project](https://docs.native-instruments.com/ni-tech-manuals/maschine-software-manual/en/managing-sounds%2C-groups%2C-and-your-project).

Windows frozen workers preload the installed system C++ runtime before PyInstaller's Qt hook, since the older runtime bundled with Qt caused Maschine initialization to fail. The bundler restricts its build-time PATH to avoid collecting unrelated native runtimes. `pedalboard.midi_utils`, loaded dynamically by the native host, is explicitly imported so frozen MIDI rendering includes it. Pedalboard's license/metadata and project notices accompany release builds.

Local evidence on 2026-10-13: all 5,849 installed groups decoded with zero errors and no changes to previously decoded nonempty paths; 2,892 Audio-module pads gained their stored sample references. Real external renders succeeded for Monark Balatonic (Reaktor 6) and Massive Godown; the two-kit export produced 51 WAVs without errors. Manhattan Kit produced all 16 pads, including its internal Tom synth and Massive instrument, in 13.77 seconds, with zero missing/omitted pads and unchanged source bytes. Repeating with skipping enabled skipped all 16 without rendering. The preparation dialog reached Prepared after loading the matching kit with untouched MIDI routing. The Windows executable rendered Tom and Massive through Maschine, plus Massive directly through VST2: three finite, nonsilent 48 kHz renders in 14.19 seconds. The 83-test suite covers bounds, wrong-kit/version rejection, cache tampering, child reuse, crashes, timeout, cancellation and settings persistence. These checks demonstrate these fixtures and mechanisms, not every NI instrument or listening acceptance. Research, proprietary states and output audio stay in ignored `tmp/instrument-render/`.

A subsequent native Windows GUI export using the freshly prepared state completed with 17 WAVs (all 16 pads and the existing preview), zero errors and zero omitted pads. Silent-pad errors leave the host available for the remaining instruments; crashes and timeouts discard the failed host.

Automatic preparation evidence on 2026-10-13: Balatonic, Manhattan and Godown prepared in one reused host; Apio was correctly omitted as sample-only. A separate six-kit GUI batch (Catacama, Chelas, Dour, Milchweg, BAP, BT) completed with zero errors and resumed with six cache hits. These kits cover all internal synth module types found in the installed index. An empty-cache full Manhattan export prepared automatically, produced 17 valid WAVs in 18.84 seconds, preserved the original source hash, and skipped all 17 files on rerun without rendering. The packaged Windows app prepared Manhattan from scratch in 17.26 seconds, verified a cache-only rerun without host startup, then produced finite non-silent 48 kHz Tom and Massive renders. The index contains 1,057 kits needing the native route; this full set has not been rendered or listening-qualified. The expanded suite has 90 tests, including batch recovery and cancellation. No preparation requires manually loading each kit in the supported setup.

## PySide migration and local distribution review (2026-10-14)

The GUI uses PySide6-Essentials 6.10.3 and Shiboken, retaining the original
launcher design and support icons. All 96 regression tests pass with the new
binding. The PySide Windows package also prepared and rendered the internal Tom
and hosted Massive fixtures, including a cache-only resume without a host.

Windows packages exclude Microsoft runtime DLLs, including NumPy's renamed DLL.
A small source-built .NET Framework launcher detects required System32 versions
and offers Microsoft's installer when needed. It verifies Authenticode and the
Microsoft publisher before opening the installer. Signature validation must
discard inherited PowerShell 7 module paths so Windows PowerShell resolves its
own built-in cmdlet. Installed/outdated/missing runtime checks, malformed
manifests and signed/unsigned installer checks passed; no installation was run.

The former product catalog and vendor software screenshots are removed; preview
names now come from local Service Center metadata. Packages include an actual
payload inventory, wheel notices and supplemental license/attribution texts from
the pinned Qt/PySide source archives. These are not a complete corresponding-source
delivery. Home-screen icon provenance and remaining native dependency source
coverage are recorded as publication gates. The release workflow stops before
version commits or tags while those gates remain open. Work remains local until
the maintainer tests the candidate and explicitly decides whether to push.


## 2026-10-14: source structure and experimental Mac host

Removed the 15 obsolete Battery parser prototypes and dependency-rewrite script. Native host adapters now live in `src/hosts`, maintenance tools in `scripts`, and guide generation in `packaging`. Runtime and build dependencies are separate; all references and debug commands were updated. Inputs, exports and research are preserved. Automatic approval review rejected deletion of 16 ignored obsolete build outputs, so those outputs remain.

Mac preparation uses a private Cocoa file-URL drop into the isolated hosted Maschine editor and validates the captured group/sound state. Plugin bundle executable and architecture enter cache identity; Windows cache identity is unchanged. Mac routes hosted instruments through Maschine and disables the direct Windows VST2 DLL route, including imported Windows preferences. Python 3.13 has Pedalboard wheels for both Mac architectures. Tests and optional package-only CI cover Windows and both Mac architectures; no workflow was dispatched. Mac runtime/preparation is explicitly unqualified until tested with licensed Maschine on real hardware. See MACOS_PORT.md for the check command.

Local suite: 102 tests run, 101 passed and the real-Cocoa check skipped on Windows. Publication remains disabled and no push or release is authorized.

The rebuilt Windows executable reused the existing preparation cache without host creation, then rendered Manhattan internal Tom and hosted Massive to finite non-silent 48 kHz WAVs (33.15 s total). The refreshed 343-entry ZIP passed integrity checks, dependency inventory retained 24 providers/221 payload files, and the updated 12-page guide was visually reviewed.


## 2026-10-14: Maschine 2 host support

Inspected installed Maschine 2.18.4 VST3 state: project archive 19 has the same validated Group Boolean routing structure as archive 20. Added bounded v19 support without accepting unknown older schemas. Its Windows editor uses NIVSTChildWindow and A1 at logical (410, 180), versus Qt and (410, 155) for Maschine 3. Automatic selection prefers 3, then 2; an explicit path overrides discovery without fallback. Plugin identity already separates cached states. No proprietary state or audio enters source control.

A cold Windows Maschine 2.18.4 run prepared Manhattan, resumed without creating a host, and rendered internal Tom and hosted Massive to finite non-silent 48 kHz audio with unchanged source kit bytes (20.46 seconds total). This is a fixture check, not qualification of every kit/version. Mac Maschine 2 automatic loading remains unsupported because its older native editor needs a real-Mac adapter; assisted state preparation and rendering use the shared reader. No push or release.

The rebuilt Windows package also passed cold Maschine 2 preparation (11.60 s), cache-only resume, and internal Tom/hosted Massive rendering (21.06 s total). The 104-test suite passed with one Cocoa-only skip; ZIP/payload checks and the updated 12-page guide review passed. An additional cold Maschine 3 source regression timed out at 90 seconds before its editor opened; a diagnostic run confirmed the same timeout inside Pedalboard load_plugin, before the NITools loading adapter executes. This does not invalidate the earlier Maschine 3 fixtures, but that fresh check must not be reported as passing.

The current frozen Maschine 3 cached-state render also timed out after 90 s. Earlier Maschine 3 results remain historical evidence only; current initialization/render timeout is an open release gate. No increase to timeouts or automatic cross-engine fallback was introduced to hide the failure. Maschine 2 remains explicitly selectable and passed the same packaged fixture.


## 2026-10-14: Maschine 3 startup recovery and Mac 2 adapter

The earlier initialization gate was traced using native stacks to an orphaned 12-byte Boost Interprocess file with an unset initialization sentinel. Restart Manager showed only our diagnostic host held it. After that child stopped, the exact inactive file was renamed to preserve it; no shared directory was cleared. Maschine 3 immediately loaded again. Database/settings reset experiments did not help and were fully restored. No binary patch or timeout increase was used.

Both preparation and render sessions now request normal worker exit, allowing native cleanup, before bounded termination. Diagnostic joins measured successful Maschine 3 cleanup at 3.04 s and 4.26 s, so the normal grace period is five seconds; active cancellation and failed jobs retain immediate termination. Regression tests prove worker-finally cleanup actually runs. Shared vendor IPC recovery is not automated. Two fresh source Maschine 3 cycles and a fresh Maschine 2 cycle prepared Manhattan, resumed cache-only and rendered internal Tom and hosted Massive with finite non-silent 48 kHz audio and unchanged source bytes.

The Mac adapter chooses archive 19/20 from validated state. Version 19 identifies a native file-drop view and publishes the legacy file list alongside the URL; version 20 uses the Qt view. Synthetic tests cover selection, drag types and logical coordinates; neither replaces real-Mac qualification. The Mac check script now runs two host cycles and documents explicit commands for both engines. Publication remains disabled.

The rebuilt Windows payload passed cold preparation, cache-only resume and internal Tom/hosted Massive rendering with both installed engines: Maschine 2.18.4 in 30.62 s and Maschine 3.7.1 in 35.01 s total. The 106-test suite passed with one real-Cocoa skip; all six GUI tests passed after the final help-text update. The 343-entry ZIP and 235-entry executable payload passed content checks, and the regenerated 12-page guide was visually reviewed. Only the resolved Maschine 3 timeout gate was removed; owner testing, Mac qualification and distribution review remain pending. Nothing was pushed or released.


## 2026-10-14: Sequential Maschine kit deserialization

Replaced the kit frame/Zone/module scanners with a bounded Boost archive reader and named schema readers derived from local Ghidra analysis of the native loaders. All 5,849 installed kits passed production decoding and baseline comparison for names, paths, aliases, order and sample IDs; 198 legacy PluginHost records gained metadata. Twenty real kits preserved all 26 VST2 state chunks byte-for-byte. The full 109-test suite passed with one Cocoa-only skip. The initial production comparison took 54.0 s versus the scanner baseline's 8.3 s; indexing is more expensive and this is not an export speed claim.

The projection deliberately ends after the Group name, after consuming all Sounds. Prepared-project routing retains its separate bounded frame locator; it is not described as fully deserialized. Schema limits, provenance, upgrade instructions and private-artifact boundaries are recorded in [MASCHINE_FORMAT.md](MASCHINE_FORMAT.md). No proprietary artifacts were added, no package was rebuilt in this change, and nothing was pushed or released.


### Sequential reader performance follow-up

Profiling identified portable integer slicing and repeated parameter-family string checks as hot paths. Direct bounded integer decoding and a parameter-type lookup reduced the full eight-process 5,849-kit comparison from 54.1 s to 29.1 s, with exactly identical comparison results. A 101-kit single-process sample fell from 6.34 s to 3.45 s. All 109 tests passed (one Cocoa-only skip); additional signed/unsigned width and truncation cases passed in the focused archive suite. Maschine retains its existing eight-process pool; Battery indexing is sequential, while audio export uses bounded parallelism. No parallelism changes or heuristic fallbacks were introduced. The old kit scanners are deleted; the active prepared-project routing locator remains isolated and necessary. Private research files and the older packaged build remain local and are not part of this source change.
