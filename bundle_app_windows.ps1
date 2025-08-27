# Paths
$distPath = "./dist"
$distAppPath = Join-Path $distPath "NITools"

# Ensure dist folder exists and remove old distribution
New-Item -ItemType Directory -Path $distPath -Force | Out-Null
if (Test-Path $distAppPath) {
    Remove-Item $distAppPath -Recurse -Force
}

# Fetch version number from src/utils/version.py
$VERSION = python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | ForEach-Object { $_.Trim() }

# Run PyInstaller to bundle the app as a single Windows .exe
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --noconsole `
    --add-data "resources;resources" `
    --icon=icons/app.ico `
    ./src/launcher.py `
    -n "NITools" `
    --distpath $distAppPath

# Generate PDF guide
python docs/makepdf.py docs/GUIDE.md "$distAppPath/nitools-guide.pdf"

# Change directory to dist
Set-Location $distPath

# Create the zip file with the version number
$zipName = "NITools_Windows_v$VERSION.zip"
Compress-Archive -Path "NITools" -DestinationPath $zipName -Force

# Return to original directory
Set-Location ".."
