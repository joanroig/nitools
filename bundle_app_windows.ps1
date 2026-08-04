param(
    [switch]$CI
)

$ErrorActionPreference = "Stop"
$env:UV_SYSTEM_CERTS = "true"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
}

$repoDir = $PSScriptRoot
$env:PYTHONPATH = (Join-Path $repoDir "src")

# Define base paths
$BaseDistPath = Join-Path $repoDir "dist"
$PlatformDistPath = Join-Path $BaseDistPath "windows\NITools"

# Ensure dist folder exists and remove old distribution
Remove-Item $PlatformDistPath -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $PlatformDistPath -Force | Out-Null

# Fetch version number from src/utils/version.py
$VERSION = & uv run --project $repoDir python -c "from utils.version import APP_VERSION; print(APP_VERSION)" |
    ForEach-Object { $_.Trim() }

# Run PyInstaller to bundle the app as a single Windows .exe
& uv run --project $repoDir python -m PyInstaller `
    --noconfirm `
    --onefile `
    --noconsole `
    --add-data "resources;resources" `
    --icon=icons/app.ico `
    ./src/launcher.py `
    -n "NITools" `
    --distpath $PlatformDistPath

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

# Generate PDF guide
$GuidePath = Join-Path $PlatformDistPath "nitools-guide.pdf"
& uv run --project $repoDir python docs/makepdf.py docs/GUIDE.md $GuidePath
if ($LASTEXITCODE -ne 0) {
    throw "PDF guide generation failed."
}

# Create the zip file with the version number
$ZipName = "NITools_Windows_v$VERSION.zip"
$ZipPath = Join-Path $BaseDistPath $ZipName
Compress-Archive -Path $PlatformDistPath -DestinationPath $ZipPath -Force
