#!/bin/bash

# Paths
distPath="./dist"
distAppPath="$distPath/NITools"

# Ensure dist folder exists and remove old distribution
mkdir -p "$distPath"
if [ -d "$distAppPath" ]; then
    rm -rf "$distAppPath"
fi

# Fetch version number from src/utils/version.py
VERSION=$(python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)")

# Run PyInstaller to bundle the app as a macOS .app
python -m PyInstaller \
    --noconfirm \
    --windowed \
    --add-data "resources:resources" \
    --icon=icons/app.icns \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$distAppPath" \
    --osx-bundle-identifier "com.moaibeats.nitools"

# Generate PDF guide
python docs/makepdf.py docs/GUIDE.md "$distAppPath/nitools-guide.pdf"

# Change directory to dist
cd "$distPath"

# Create the zip file with the version number
zipName="NITools_macOS_v$VERSION.zip"
zip -r "$zipName" "NITools"

# Return to original directory
cd ".."
