# Ensure the dist folder exists
$distPath = "./dist"
$distAppPath = Join-Path $distPath "NITools"

if (-not (Test-Path $distPath)) {
    New-Item -ItemType Directory -Path $distPath | Out-Null
}

# Delete previous distribution app folder if it exists
if (Test-Path $distAppPath) {
    Remove-Item $distAppPath -Recurse -Force
}

# Fetch version number from src/utils/version.py
$VERSION = python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | ForEach-Object { $_.Trim() }

# Run PyInstaller to bundle the app
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --noconsole `
    --add-data "./img;img" `
    --add-data "./assets/.wav;assets/.wav" `
    --icon=img/app.ico `
    ./src/launcher.py `
    -n "NITools" `
    --distpath $distAppPath

# Generate PDFs
python docs/makepdf.py docs/GUIDE.md "$distAppPath/nitools-guide.pdf"

# Change directory to dist
Set-Location $distPath

# Create the zip file with the version number
$zipName = "NITools_Windows_v$VERSION.zip"
Compress-Archive -Path "NITools" -DestinationPath $zipName -Force

# Return to original directory
Set-Location ".."
