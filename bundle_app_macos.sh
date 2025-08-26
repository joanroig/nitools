#!/bin/bash

# Ensure the dist folder exists
distPath="./dist"
distAppPath="$distPath/NITools"

mkdir -p "$distPath"

# Delete previous distribution app folder if it exists
if [ -d "$distAppPath" ]; then
    rm -rf "$distAppPath"
fi

# Fetch version number from src/utils/version.py
VERSION=$(python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)")

# Run PyInstaller to bundle the app
python -m PyInstaller \
    --noconfirm \
    --onefile \
    --noconsole \
    --add-data "./img:img" \
    --add-data "./assets/.wav:assets/.wav" \
    --icon=img/app.icns \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$distAppPath"

# Generate PDFs
python docs/makepdf.py docs/GUIDE.md "$distAppPath/nitools-guide.pdf"

# Change directory to dist
cd "$distPath"

# Create the zip file with the version number
zipName="NITools_macOS_v$VERSION.zip"
zip -r "$zipName" "NITools"

# Return to original directory
cd ".."
