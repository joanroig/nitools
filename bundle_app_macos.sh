#!/bin/bash

# Define base paths
root="$(pwd)"
baseDistPath="$root/dist"
platformDistPath="$baseDistPath/macos/NITools"

# Ensure dist folder exists and remove old distribution
rm -rf "$platformDistPath"
mkdir -p "$platformDistPath"

# Fetch version number from src/utils/version.py
VERSION=$(python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | xargs)

# Run PyInstaller to bundle the app as a macOS .app
python -m PyInstaller \
    --noconfirm \
    --windowed \
    --add-data "resources:resources" \
    --icon=icons/app.icns \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$platformDistPath"

# Remove intermediate folder created by PyInstaller
rm -rf "$platformDistPath/NITools"

# Generate PDF guide inside NITools folder
guidePath="$platformDistPath/nitools-guide.pdf"
python docs/makepdf.py docs/GUIDE.md "$guidePath"

# Create the zip file with the version number
zipName="NITools_macOS_v$VERSION.zip"
(
    cd "$baseDistPath/macos"
    zip -r "$baseDistPath/$zipName" "NITools"
)
