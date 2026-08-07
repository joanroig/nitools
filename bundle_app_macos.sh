#!/bin/bash

# Enable fail-fast: stop execution immediately if any command fails
set -euo pipefail

# Define base paths
root="$(pwd)"
baseDistPath="$root/dist"

# Initialize CI flag
CI_MODE=false

# TARGET_ARCH is the first argument
TARGET_ARCH="$1"

# Check if the second argument is --ci
if [ "${2:-}" == "--ci" ]; then
    CI_MODE=true
fi

# Ensure uv is available
if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv was not found in PATH. Install uv from https://docs.astral.sh/uv/."
    exit 1
fi

# Get target architecture from argument
if [ -z "$TARGET_ARCH" ]; then
    echo "Error: Target architecture (x86_64 or arm64) must be provided as the first argument."
    exit 1
fi

export PYTHONPATH="$root/src"

# Define architecture-specific paths
ARCH_SUFFIX="_${TARGET_ARCH}"
# PyInstaller will create NITools.app inside this path
platformDistPath="$baseDistPath/macos${ARCH_SUFFIX}" # e.g., dist/macos_x86_64

# Ensure dist/build folders are clean so PyInstaller does not reuse stale caches
rm -rf "$platformDistPath"
rm -rf "$root/build"
rm -rf "$root/dist"
mkdir -p "$platformDistPath"

# Fetch version number from src/utils/version.py
VERSION=$(uv run --project "$root" python -c "from src.utils.version import APP_VERSION; print(APP_VERSION)" | xargs)

# Run PyInstaller to bundle the app as a macOS .app
# MACOSX_DEPLOYMENT_TARGET ensures compatibility with older macOS versions
MACOSX_DEPLOYMENT_TARGET=11.0 uv run --project "$root" python -m PyInstaller \
    --clean \
    --noconfirm \
    --windowed \
    --add-data "resources:resources" \
    --add-data "pyproject.toml:." \
    --icon=icons/app.icns \
    --target-arch "$TARGET_ARCH" \
    ./src/launcher.py \
    -n "NITools" \
    --distpath "$platformDistPath"

# The .app bundle is now at "$platformDistPath/NITools.app"

# Generate PDF guide next to the .app bundle for inclusion in DMG
guidePath="$platformDistPath/nitools-guide.pdf" # Place guide directly in the dist folder
uv run --project "$root" python docs/makepdf.py docs/GUIDE.md "$guidePath"

# Create helper script to remove quarantine attributes
HELPER_SCRIPT_NAME="fix.command"
helperScriptPath="$platformDistPath/$HELPER_SCRIPT_NAME"
cat <<EOF > "$helperScriptPath"
#!/bin/bash
APP_PATH="/Applications/NITools.app"
echo "Removing quarantine attributes from \$APP_PATH..."
xattr -cr "\$APP_PATH"
echo "Done! You can now launch NITools."
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
    --window-size 700 750 \
    --background "docs/img/dmg-background.jpg" \
    --icon-size 100 \
    --app-drop-link 550 200 \
    --icon "NITools.app" 150 200 \
    --add-file "fix.command" "$helperScriptPath" 150 550 \
    --add-file "nitools-guide.pdf" "$guidePath" 550 550 \
    "$dmgPath" \
    "$platformDistPath/NITools.app"
