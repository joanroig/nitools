# NITools 2.0 release checklist

Release target as of 2026-10-14: **2.0.0**. The incompatible kit/group index change requires a major version. Local Windows qualification is recorded below; publication requires the GitHub release builds to pass. See [release notes](RELEASE_NOTES_2_0.md) for the user-facing upgrade instructions and compatibility limits.

The latest sequential Maschine kit decoder is source-tested against 5,849 kits and the 109-test suite. The previously qualified Windows package predates this change and needs rebuilding/requalification before distribution. See [decoder scope and evidence](MASCHINE_FORMAT.md).

## Changes for 2.0

- Battery and Maschine indexes use structured binary decoding of stored sample references, cell/slot numbers and sample zones. Missing exact references fail visibly instead of selecting similar filenames.
- Exports retain sample names and every decoded zone, including Battery cells above 16 and Maschine Audio-module takes.
- Groups offers experimental instrument rendering (Windows qualified fixtures; Mac adapter unverified): direct installed VST2 presets, or internal/hosted instruments through the installed Maschine 2/3 VST3. Kits prepare automatically during export or through a resumable batch queue, with an assisted single-kit fallback. Raw sample export remains independent of rendering.
- Large Group scans use up to eight decoder processes; all three audio exporters use bounded parallel conversion. Live progress, cancellation, safe output replacement and incomplete-result reporting are shared.
- All three windows have consistent Process/Export tabs, audio settings, expandable options and a compact Activity card with follow, copy, clear and a larger log reader.
- Release builds use locked dependencies, preserve other local builds and create a draft only after Windows, Intel Mac and Apple Silicon Mac tests/builds pass.

## Upgrade notes

Rebuild existing kit/group indexes with **1 Process**, then select a fresh destination in **2 Export**. Earlier indexes are rejected because their reconstructed paths are not reliable. Old numbered exports are not renamed or removed automatically.

Saved matrix/filter/audio preferences remain active. Review the summary on collapsed options. **Skip existing files** checks existence, not conversion settings; use a fresh folder or disable it when changing settings. Moved libraries need their exact reference locations restored or explicit reference roots corrected. Unsupported serialization layouts are reported, not guessed.

## Verification

| Check | Evidence / result |
| --- | --- |
| Automated suite | 106 tests run on Windows: 105 passed and one Mac-only Cocoa check skipped, Python 3.14.5 and PySide6 6.10.3 (2026-10-14), including parser bounds, resolution, all three exporters, atomic failures, render/preparation cancellation/crashes/timeouts, batch checkpoints and host reuse, prepared-state validation, GUI settings/layout/activity, local product metadata and package-content rules. |
| Installed Maschine corpus | 5,849 groups decoded; 140,354 nonempty references resolved. This is a decoding/resolution check, not an export of every referenced sound. A subsequent native app run also showed 5,849 decoded with zero errors. |
| Raw exports | Earlier qualification exported 5,485 samples from 159 Battery kits and 139 Maschine groups with source/output SHA-256 equality and unchanged input files. |
| Audio-module recovery | All 5,849 installed groups decoded again with zero errors, 2,892 Audio-module pads recovered, and no changes to previously decoded nonempty paths. |
| Instrument rendering | Direct Monark/Reaktor and Massive exports succeeded; Manhattan exported all 16 pads including its internal Tom, with zero missing/omitted pads. The frozen Windows executable rendered Tom and Massive through Maschine plus direct VST2 Massive. The preparation dialog reached Prepared with untouched MIDI routing, then the normal GUI export produced 16 pads and its preview successfully. This is fixture qualification, not universal compatibility or listening acceptance. |
| Automatic preparation | Nine distinct instrument kits prepared automatically across two batches, covering the internal module types in the installed index. The six-kit GUI batch resumed as six cached kits, with no errors. An uncached Manhattan export prepared automatically and produced 16 pads plus preview in 18.84 seconds; the next run skipped all 17 files and the original kit stayed unchanged. The frozen Windows build also prepared an uncached kit, resumed without starting a host, and rendered its internal Tom and hosted Massive successfully. The entire 1,057-kit native-instrument subset has not been batch-qualified. |
| Current Qt workflows | Rebuilt 110 Battery kits, 48 groups and 345 previews; exported 175 readable 48 kHz PCM24 WAVs without errors. These workflow runs used offscreen Qt workers. |
| Frozen multiprocessing | Windows executable decoded 98 representative installed groups, matching serial results, without launching GUI instances in its worker processes. |
| Windows local packaging | Version 2.0.0 rebuilt with PySide6-Essentials 6.10.3, a separate prerequisite launcher, refreshed original home screen and a reviewed 12-page guide. The payload inventory identifies 24 dependency providers and 221 native/data files. Microsoft runtime DLLs and the installer are excluded, including NumPy's renamed runtime. Obsolete source prototypes are removed. Deletion of 16 ignored obsolete build folders/archives was blocked by automatic approval review; those generated files remain. |
| Prerequisite launcher | Checks for installed, outdated and missing runtimes passed, as did rejection of empty/malformed manifests and unsigned files. The actual Microsoft installer downloaded from the configured URL passed Authenticode/publisher validation. Fixed inherited PowerShell 7 module paths interfering with Windows PowerShell's signature cmdlet. No installer was run; clean-machine installation remains unqualified. |
| PySide frozen rendering | The PySide build prepared Manhattan in 36.23 s, resumed from its cache with host startup disabled, and rendered its internal Tom and hosted Massive to finite, non-silent 48 kHz audio. This confirms the binding/package migration for those fixtures, not all kits or listening acceptance. |
| Native Windows UI | Inspected all three Process/Export layouts at the saved window size; inspected the new populated Activity card and larger log reader in the source app. The final PySide Windows package opens from the prerequisite launcher with the original home screen, and Groups, Kits and Previews each open successfully. |
| Release definitions | Both workflows pass actionlint 1.7.12; PowerShell/Bash scripts pass syntax checks; `uv lock --check` passes. Publication is blocked by `packaging/release_review.json` before any release version commit, tag or upload. Ordinary source pushes and local builds remain available. |
| GitHub backlog | No open issues or pull requests in `joanroig/nitools` when checked on 2026-10-13. This does not replace the pending release checks. |
| Performance | Matched full-library Group indexing improved from 275.20 s to 14.75 s; a normal Qt worker run took 21.76 s. All three exporters share the faster audio path. See [DECISIONS.md](DECISIONS.md) for benchmark conditions and export comparisons. |

Local scripts, reports and screenshots are under ignored `tmp/`; proprietary library files are not included in the repository. The public tests use synthetic fixtures. See [GUIDE.md](GUIDE.md) for usage and troubleshooting.

## Release gates

- **Local only at the maintainer's request (2026-10-14).** Do not push, create a tag, dispatch a release build or publish a release without a new instruction.
- Resolve distribution terms/provenance for the original home screen's music-service icons. They are retained in the local candidate to preserve the maintainer's design; no claim of redistribution clearance is made.
- Complete the dependency corresponding-source review and native third-party notices. In particular, identify the Windows libsndfile wheel's statically linked codec versions/build inputs, and cover Pedalboard's submodules and Qt's third-party components. Current installed wheel notices alone are insufficient to call this complete.
- Qualify the new Windows prerequisite launcher on a clean machine, including installer cancellation/failure and restart handling. Download/signature verification and local installed-runtime behavior can be checked separately; do not claim a real installation was tested if it was not.
- Run the committed release workflow on GitHub and require all three jobs to pass. Local syntax checks do not prove GitHub runner execution.
- Windows local package and PDF checks are complete; inspect each CI-built platform artifact separately after the remaining review items are closed.
- Keep instrument rendering experimental and publish the known compatibility limits alongside the downloads.

## Continuing compatibility checks

- Listen to representative internal synth kits and third-party instruments. Current real-engine evidence covers the named fixtures, not every module, custom MIDI routing or effect chain.
- On **Intel and Apple Silicon Macs**, open the packaged app and verify library discovery, processing, export, cancellation and audio playback with installed libraries. Native macOS behavior, including automatic kit preparation and internal/hosted instrument rendering, has not been qualified here. Follow `docs/MACOS_PORT.md`.
- Open the Windows ZIP on a clean Windows machine without this development environment and verify launch, processing/export and playback. Local packaged-worker and source-GUI checks do not establish clean-machine readiness or listening acceptance.

These checks define the unqualified scope disclosed in the release notes. Compatibility is demonstrated for the tested corpus; it is not a guarantee for every historical or future NI file layout.

## Release procedure

1. Keep the intended changes, including version **2.0.0**, in local commits for now. After renewed authorization and closure of the gates above, review the complete outgoing range and push the release branch.
2. Run **Create Release** from that branch with **none** to build the committed 2.0.0 version. For future releases, the workflow can bump and update the version and lockfile together.
3. All platforms test/build the exact version commit. Only after all jobs succeed does the workflow create a draft containing the Windows ZIP, both Mac DMGs and `SHA256SUMS.txt`.
4. Verify the draft package list and checksums, review the release notes and their explicit compatibility limits, then publish the draft.

If a build fails after the version commit, fix the branch and rerun with **none** to retain 2.0.0. Existing tags are rejected; the workflow never force-updates a release tag. Publishing is a separate manual action.

Maschine 2 support was added locally after the restructure: Windows 2.18.4 cold preparation, cache-only resume, internal Tom and hosted Massive rendering passed with unchanged source bytes. Discovery prefers 3, then 2; explicit plug-in paths do not fall back. Both engines retain separate caches. Mac automatic loading includes a legacy Cocoa adapter for Maschine 2; both engine adapters await real-Mac testing.

**Startup recovery, 2026-10-14:** the Maschine 3 timeout was traced to a 12-byte Boost Interprocess file stuck at initialization state zero, before kit loading. Its only live holder was our diagnostic child. After stopping that child and preserving the exact inactive file as a backup, Maschine 3 loaded normally. Original NI settings and databases were restored unchanged after diagnostic experiments. Cold preparation, cache-only resume and internal Tom/hosted Massive rendering then passed in two source cycles. Normal hosts now receive an exit request and up to five seconds for cleanup; measured successful Maschine 3 shutdowns took 3.04 and 4.26 seconds. Cancellation and job deadlines are unchanged. Shared vendor files are never automatically removed by the app. Maschine 2 cold preparation and both renders also passed. Mac adapters are ready for local testing, not yet runtime-qualified.

The rebuilt Windows payload passed cold preparation, cache-only resume and internal Tom/hosted Massive rendering with both installed engines: Maschine 2.18.4 in 30.62 s and Maschine 3.7.1 in 35.01 s total. The 106-test suite passed with one real-Cocoa skip; all six GUI tests passed after the final help-text update. The 343-entry ZIP and 235-entry executable payload passed content checks, and the regenerated 12-page guide was visually reviewed. Only the resolved Maschine 3 timeout gate was removed; owner testing, Mac qualification and distribution review remain pending. Nothing was pushed or released.
