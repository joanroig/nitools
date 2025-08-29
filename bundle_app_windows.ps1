# Enable fail-fast: stop execution immediately if any command fails
$ErrorActionPreference = "Stop"

# Define base paths
$Root = Get-Location
$BaseDistPath = Join-Path $Root "dist"
$PlatformDistPath = Join-Path $BaseDistPath "windows\NITools"

# Ensure dist folder exists and remove old distribution
Remove-Item $PlatformDistPath -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $PlatformDistPath -Force | Out-Null

# Fetch version number from src/utils/version.py
$VERSION = python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" |
    ForEach-Object { $_.Trim() }

# Run PyInstaller to bundle the app as a single Windows .exe
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --noconsole `
    --add-data "resources;resources" `
    --icon=icons/app.ico `
    ./src/launcher.py `
    -n "NITools" `
    --distpath $PlatformDistPath

# Generate PDF guide
$GuidePath = Join-Path $PlatformDistPath "nitools-guide.pdf"
python docs/makepdf.py docs/GUIDE.md $GuidePath

# Create the zip file with the version number
$ZipName = "NITools_Windows_v$VERSION.zip"
$ZipPath = Join-Path $BaseDistPath $ZipName
Compress-Archive -Path $PlatformDistPath -DestinationPath $ZipPath -Force
