#!/usr/bin/env bash
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$root/src"
# Python 3.13 has locked binary wheels for both Intel and Apple Silicon Macs.
exec uv run --locked --python 3.13 --project "$root" python "$root/src/launcher.py"
