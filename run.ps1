$ErrorActionPreference = "Stop"
$env:UV_SYSTEM_CERTS = "true"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
}

$repoDir = $PSScriptRoot
$env:PYTHONPATH = (Join-Path $repoDir "src")

& uv run --project $repoDir python (Join-Path $repoDir "src\launcher.py")
if ($LASTEXITCODE -ne 0) {
    throw "NITools run failed."
}
