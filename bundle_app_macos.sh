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


# Get target architecture from argument
if [ -z "$TARGET_ARCH" ]; then
    echo "Error: Target architecture (x86_64 or arm64) must be provided as the first argument."
    exit 1
fi

# Conditionally activate Conda environment
if [ "$CI_MODE" = false ]; then
    echo "Activating Conda environment 'nitools'..."
    # Initialize conda for the current shell session
    # This assumes conda is installed and initialized for the shell
    eval "$(conda shell.bash hook)"
    conda activate nitools
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
guidePath="$platformDistPath/nitools-guide.pdf" # Place guide directly in the dist folder
python docs/makepdf.py docs/GUIDE.md "$guidePath"

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
