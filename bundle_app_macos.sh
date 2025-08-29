#!/bin/bash

# Enable fail-fast: stop execution immediately if any command fails
set -euo pipefail

# Define base paths
root="$(pwd)"
baseDistPath="$root/dist"

# Get target architecture from argument
TARGET_ARCH=$1
if [ -z "$TARGET_ARCH" ]; then
    echo "Error: Target architecture (x86_64 or arm64) must be provided as an argument."
    exit 1
fi

# Define architecture-specific paths
ARCH_SUFFIX="_${TARGET_ARCH}"
archSpecificRootPath="$baseDistPath/macos${ARCH_SUFFIX}" # e.g., dist/macos_x86_64
platformDistPath="$archSpecificRootPath/NITools" # e.g., dist/macos_x86_64/NITools

# Ensure dist folder exists and remove old distribution for this architecture
rm -rf "$archSpecificRootPath"
mkdir -p "$platformDistPath"

# Fetch version number from src/utils/version.py
VERSION=$(python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | xargs)

# Run PyInstaller to bundle the app as a macOS .app
python -m PyInstaller \
    --noconfirm \
    --windowed \
    --add-data "resources:resources" \
    --icon=icons/app.icns \
    --target-arch "$TARGET_ARCH" \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$platformDistPath"

# Remove intermediate folder created by PyInstaller
rm -rf "$platformDistPath/NITools"

# Generate PDF guide inside NITools folder
guidePath="$platformDistPath/nitools-guide.pdf"
python docs/makepdf.py docs/GUIDE.md "$guidePath"

# Create the zip file with the version number and architecture
zipName="NITools_macOS${ARCH_SUFFIX}_v$VERSION.zip"
(
    cd "$archSpecificRootPath"
    zip -r "$baseDistPath/$zipName" "NITools"
)
