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
# PyInstaller will create NITools.app inside this path
platformDistPath="$baseDistPath/macos${ARCH_SUFFIX}" # e.g., dist/macos_x86_64

# Ensure dist folder exists and remove old distribution for this architecture
rm -rf "$platformDistPath"
mkdir -p "$platformDistPath"

# Fetch version number from src/utils/version.py
VERSION=$(python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | xargs)

# Run PyInstaller to bundle the app as a macOS .app
# MACOSX_DEPLOYMENT_TARGET ensures compatibility with older macOS versions
MACOSX_DEPLOYMENT_TARGET=11.0 python -m PyInstaller \
    --noconfirm \
    --windowed \
    --add-data "resources:resources" \
    --icon=icons/app.icns \
    --target-arch "$TARGET_ARCH" \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$platformDistPath"

# The .app bundle is now at "$platformDistPath/NITools.app"

# Generate PDF guide next to the .app bundle for inclusion in DMG
# app_resources_path="$platformDistPath/NITools.app/Contents/Resources" # No longer needed
# mkdir -p "$app_resources_path" # Ensure the directory exists # No longer needed
guidePath="$platformDistPath/nitools-guide.pdf" # Place guide directly in the dist folder
python docs/makepdf.py docs/GUIDE.md "$guidePath"

# Create helper script to remove quarantine attributes
HELPER_SCRIPT_NAME="remove_quarantine.sh"
helperScriptPath="$platformDistPath/$HELPER_SCRIPT_NAME"
cat <<EOF > "$helperScriptPath"
#!/bin/bash
APP_NAME="NITools.app"
echo "Removing quarantine attributes from \$APP_NAME..."
xattr -cr "\$APP_NAME"
echo "Done. You can now launch \$APP_NAME."
EOF
chmod +x "$helperScriptPath"

# Create the DMG file
dmgName="NITools_macOS${ARCH_SUFFIX}_v$VERSION.dmg"
dmgPath="$baseDistPath/$dmgName" # Output DMG to the main dist folder

# Ensure the .app bundle exists before creating DMG
if [ ! -d "$platformDistPath/NITools.app" ]; then
    echo "Error: NITools.app not found at $platformDistPath/NITools.app"
    exit 1
fi

create-dmg \
    --volname "NITools v$VERSION" \
    --window-size 700 400 \
    --app-drop-link 600 185 \
    --icon "NITools.app" 200 185 \
    --add-file "nitools-guide.pdf" "$guidePath" 300 185 \
    --add-file "$HELPER_SCRIPT_NAME" "$helperScriptPath" 400 185 \
    "$dmgPath" \
    "$platformDistPath/NITools.app"


# Clean up the intermediate .app bundle directory after DMG creation
rm -rf "$platformDistPath"
