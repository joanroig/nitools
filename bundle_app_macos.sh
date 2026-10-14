#!/bin/bash

# Enable fail-fast: stop execution immediately if any command fails
set -euo pipefail

# Define base paths
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"
baseDistPath="$root/dist"

# Initialize CI flag
CI_MODE=false

# TARGET_ARCH is the first argument
TARGET_ARCH="${1:-}"

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
if [[ "$TARGET_ARCH" != "x86_64" && "$TARGET_ARCH" != "arm64" ]]; then
    echo "Error: Target architecture must be x86_64 or arm64."
    exit 1
fi

export PYTHONPATH="$root/src"
export NITOOLS_TARGET_ARCH="$TARGET_ARCH"
export UV_PYTHON=3.13

# Fetch the version before selecting architecture/version-specific build paths.
VERSION=$(uv run --locked --group build --project "$root" python -c "from utils.version import APP_VERSION; print(APP_VERSION)")

# Define architecture-specific paths
ARCH_SUFFIX="_${TARGET_ARCH}"
# PyInstaller will create NITools.app inside this path
platformDistPath="$baseDistPath/macos${ARCH_SUFFIX}_v$VERSION"
buildPath="$root/build/macos${ARCH_SUFFIX}_v$VERSION"
mkdir -p "$platformDistPath" "$buildPath"

# Run PyInstaller to bundle the app as a macOS .app
# Match the minimum supported by the locked PySide6 universal2 wheel.
MACOSX_DEPLOYMENT_TARGET=13.0 uv run --locked --group build --project "$root" python -m PyInstaller \
    --clean \
    --noconfirm \
    "$root/packaging/nitools.spec" \
    --workpath "$buildPath" \
    --distpath "$platformDistPath"

# The .app bundle is now at "$platformDistPath/NITools.app"
uv run --locked --group build --project "$root" python packaging/collect_licenses.py "$buildPath/nitools" "$platformDistPath/NITools.app/Contents/Resources"
cp LICENSE THIRD_PARTY_NOTICES.md "$platformDistPath/NITools.app/Contents/Resources/"

# Resource additions change the bundle seal. Ad-hoc signing is not notarization.
codesign --force --deep --sign - "$platformDistPath/NITools.app"
codesign --verify --deep --strict "$platformDistPath/NITools.app"

# Generate PDF guide next to the .app bundle for inclusion in DMG
guidePath="$platformDistPath/nitools-guide.pdf" # Place guide directly in the dist folder
uv run --locked --group build --project "$root" python packaging/make_guide.py docs/GUIDE.md "$guidePath"

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
    --icon-size 100 \
    --app-drop-link 550 200 \
    --icon "NITools.app" 150 200 \
    --add-file "fix.command" "$helperScriptPath" 150 550 \
    --add-file "nitools-guide.pdf" "$guidePath" 550 550 \
    "$dmgPath" \
    "$platformDistPath/NITools.app"
