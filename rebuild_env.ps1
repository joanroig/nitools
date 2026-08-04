param(
    [string]$PythonVersion = ">=3.13",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$env:UV_SYSTEM_CERTS = "true"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
}

$repoDir = $PSScriptRoot
$pyproject = Join-Path $repoDir "pyproject.toml"
if (-not (Test-Path $pyproject)) {
    throw "pyproject.toml not found in $repoDir"
}

$venvDir = Join-Path $repoDir $VenvPath
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment at $venvDir (python=$PythonVersion)"
    & uv venv --python $PythonVersion $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create uv virtual environment."
    }
}

Push-Location $repoDir
try {
    & uv sync --python $venvPython --extra dev
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to sync project dependencies with uv."
    }
}
finally {
    Pop-Location
}

Write-Host "Environment ready (uv): $venvDir"
