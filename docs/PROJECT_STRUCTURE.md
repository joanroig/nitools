# Project structure

| Location | Responsibility |
| --- | --- |
| `src/launcher.py`, `src/apps/` | Launcher and the three exporter windows |
| `src/components/`, `src/dialogs/` | Shared workflow, progress/activity, controls and dialogs |
| `src/formats/` | Bounded binary decoding and exact sample-reference resolution |
| `src/processors/` | Indexing, export, preparation queues and render orchestration |
| `src/hosts/` | Windows/Cocoa editor adapters, direct Windows VST2 host and isolated-worker runtime |
| `src/models/`, `src/utils/` | Configuration models and shared supporting utilities |
| `tests/` | Synthetic regression tests; no NI library fixtures |
| `packaging/` | PyInstaller specification/hooks, prerequisite launcher, guide generation, inventory and notices |
| `scripts/` | Maintainer environment/version tools and real-Mac qualification command |
| `resources/`, `icons/` | App resources and platform application icons |
| `docs/` | Usage, architecture decisions, verification and publication requirements |

The small root `run.ps1`/`run.sh` and `bundle_app_*` scripts are stable entry
points. Runtime dependencies are in `project.dependencies`; PyInstaller and
PDF tooling are in the `build` dependency group. Tests use standard-library
`unittest` and do not require pytest.

Use `uv sync --locked` for the application or `uv sync --locked --group build`
for packaging. macOS uses Python 3.13 to obtain binary wheels on both Intel and
Apple Silicon; run `bash run.sh`. Run tests with
`uv run --locked python -m unittest discover -s tests -v`.

To deliberately update a dependency, use `uv lock --upgrade-package NAME`,
review the lockfile and dependency notices, then sync/test. The former custom
script that rewrote version constraints to PyPI's newest versions is removed.

Legacy `src/processors/kits/old/` experiments, the obsolete UPID generation
debug action and unused development dependencies are removed. Earlier commits
retain source history. `in/`, `out/`, local research in `tmp/`, caches and the
current build are ignored local data, not source or release inputs; do not
delete them as part of source cleanup.
