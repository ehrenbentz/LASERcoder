#!/bin/bash
# build_LaserTAG_MacOS.sh
# Run from inside LaserTAG/build_MacOS/
#
# Directory structure:
#   LaserTAG/
#     CodeBase/              Python source files including LaserTAG.py
#     build_MacOS/           This script, Icons.icns, collect_dylibs.sh,
#                            create_dmg.sh, create_pkg.sh, Info.plist,
#                            current_version.txt
#       libs_arm64/          Pre-collected dylibs for Apple Silicon
#       libs_x86_64/         Pre-collected dylibs for Intel
#       dist_arm64/          Build output for Apple Silicon
#       dist_x86_64/         Build output for Intel
#
# Auto-detects architecture (arm64 or x86_64) and uses the matching
# libs and output directories. The compiled binary always references
# libs/ (no architecture suffix) so the CodeBase stays universal.
#
# Prerequisites:
#   brew install mpv (only needed if libs_<arch>/ does not exist yet)
#   pip install nuitka PySide6 python-mpv
#
# Usage:
#   cd LaserTAG/build_MacOS
#   ./build_LaserTAG_MacOS.sh

set -e

# ==================================================================
# Auto-detect architecture
# ==================================================================
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="arm64"
else
    ARCH_LABEL="x86_64"
fi

# ==================================================================
# Find Python
# ==================================================================
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: No python3 or python found on PATH"
    exit 1
fi

# ==================================================================
# Read version from current_version.txt
# ==================================================================
if [ ! -f "current_version.txt" ]; then
    echo "ERROR: current_version.txt not found in current directory."
    exit 1
fi

APP_VERSION=$(grep '^VERSION_NUMBER=' current_version.txt | cut -d'=' -f2)

if [ -z "$APP_VERSION" ]; then
    echo "ERROR: Could not parse version from current_version.txt"
    exit 1
fi

# ==================================================================
# Configuration
# ==================================================================
APP_NAME="LaserTAG"
MAIN_SCRIPT="LaserTAG.py"
CODBASE_DIR="../CodeBase"
LIBS_DIR="./libs_${ARCH_LABEL}"
OUTPUT_DIR="./dist_${ARCH_LABEL}"

APP_BUNDLE="${APP_NAME}.app"
SETUP_DMG="${APP_NAME}_v${APP_VERSION}_macOS_${ARCH_LABEL}.dmg"
SETUP_PKG="${APP_NAME}_v${APP_VERSION}_macOS_${ARCH_LABEL}.pkg"
ZIP_NAME="${APP_NAME}_v${APP_VERSION}_macOS_${ARCH_LABEL}_portable.zip"

export COPYFILE_DISABLE=1
export COPY_EXTENDED_ATTRIBUTES_DISABLE=1

# ==================================================================
# Retry helper — retries a command when macOS holds file locks
# (Spotlight indexing, quarantine scanning, etc.)
# ==================================================================
MAX_RETRIES=5
RETRY_DELAY=5

retry_busy() {
    local attempt=1
    local delay="$RETRY_DELAY"
    while true; do
        if "$@" 2>retry_stderr_$$.tmp; then
            rm -f retry_stderr_$$.tmp
            return 0
        fi
        local rc=$?
        local err
        err=$(cat retry_stderr_$$.tmp 2>/dev/null)
        rm -f retry_stderr_$$.tmp
        if echo "$err" | grep -qi "resource busy\|file.*busy"; then
            if [ "$attempt" -ge "$MAX_RETRIES" ]; then
                echo "ERROR: Command still failing after $MAX_RETRIES attempts: $*"
                echo "  $err"
                return $rc
            fi
            echo "  Resource busy (attempt $attempt/$MAX_RETRIES), waiting ${delay}s..."
            sleep "$delay"
            attempt=$((attempt + 1))
            delay=$((delay + 5))
        else
            # Not a busy error — print stderr and fail immediately
            echo "$err" >&2
            return $rc
        fi
    done
}

echo "============================================"
echo "  LaserTAG macOS Build"
echo "  Architecture: ${ARCH_LABEL}"
echo "  Version:      ${APP_VERSION}"
echo "============================================"
echo ""

# ==================================================================
# Verify directory structure
# ==================================================================
if [ ! -d "$CODBASE_DIR" ]; then
    echo "ERROR: CodeBase directory not found at $CODBASE_DIR"
    echo "Run this script from inside LaserTAG/build_MacOS/"
    exit 1
fi

if [ ! -f "$CODBASE_DIR/$MAIN_SCRIPT" ]; then
    echo "ERROR: $MAIN_SCRIPT not found in $CODBASE_DIR/"
    exit 1
fi

if [ ! -f "Icons.icns" ]; then
    echo "ERROR: Icons.icns not found in current directory."
    exit 1
fi

if [ ! -f "Info.plist" ]; then
    echo "ERROR: Info.plist not found in current directory."
    exit 1
fi

# ==================================================================
# Collect dylibs (only if libs_<arch>/ does not exist)
# ==================================================================
if [ ! -d "$LIBS_DIR" ] || [ -z "$(ls "$LIBS_DIR"/*.dylib 2>/dev/null)" ]; then
    if [ ! -f "./collect_dylibs.sh" ]; then
        echo "ERROR: collect_dylibs.sh not found in current directory."
        exit 1
    fi
    chmod +x ./collect_dylibs.sh
    ./collect_dylibs.sh "$LIBS_DIR"
else
    echo "${LIBS_DIR}/ directory exists, skipping dylib collection"
    echo "  (Delete ${LIBS_DIR}/ and re-run to regenerate from Homebrew)"
fi

# ==================================================================
# Prepare output directory
# ==================================================================
echo ""
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Copy Python source into output for Nuitka to compile
cp "$CODBASE_DIR"/*.py "$OUTPUT_DIR/"

# Copy build resources into output (libs/ without arch suffix for the binary)
cp Icons.icns "$OUTPUT_DIR/"
cp -R "$LIBS_DIR" "$OUTPUT_DIR/libs"
chmod 755 "$OUTPUT_DIR"/libs/*.dylib

# ==================================================================
# Compile with Nuitka
# ==================================================================
echo ""
echo "Compiling with Nuitka..."
cd "$OUTPUT_DIR"

find . -name '._*' -delete

$PYTHON -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-icon=Icons.icns \
    --macos-app-name="$APP_NAME" \
    --output-filename="$APP_NAME" \
    --enable-plugin=pyside6 \
    --nofollow-import-to=PIL \
    "--include-data-files=libs/*.dylib=libs/" \
    "$MAIN_SCRIPT"

# Clean up source copies (keep only build artifacts)
rm -f *.py *.icns
rm -rf libs

## Replace Nuitka's auto-generated Info.plist with our custom one
## and stamp the version from APP_VERSION
echo ""
echo "Installing custom Info.plist (v${APP_VERSION})..."
sed "s/__APP_VERSION__/${APP_VERSION}/g" ../Info.plist \
    > "${APP_NAME}.app/Contents/Info.plist"

cd ..

# ==================================================================
# Create installers
# ==================================================================
chmod +x ./create_dmg.sh
./create_dmg.sh "$OUTPUT_DIR/${APP_BUNDLE}" "$OUTPUT_DIR" "$APP_VERSION"

chmod +x ./create_pkg.sh
./create_pkg.sh "$OUTPUT_DIR/${APP_BUNDLE}" "$OUTPUT_DIR" "$APP_VERSION"

# ==================================================================
# Create portable .zip for release upload
# ==================================================================
echo ""
echo "Creating portable zip..."

pushd "$OUTPUT_DIR" > /dev/null
if retry_busy zip -r -y "$ZIP_NAME" "${APP_BUNDLE}"; then
    echo "Zip created: $OUTPUT_DIR/$ZIP_NAME"
else
    echo "WARNING: Failed to create zip file."
fi
popd > /dev/null

# ==================================================================
# Clean up Nuitka build artifacts
# ==================================================================
echo ""
echo "Cleaning up..."
rm -rf "$OUTPUT_DIR/${APP_NAME}.build"
rm -rf "$OUTPUT_DIR/${APP_NAME}.dist"
rm -rf "$OUTPUT_DIR/${APP_NAME}.app"

echo ""
echo "============================================"
echo "  Build Complete (${ARCH_LABEL})"
echo "============================================"
[ -f "$OUTPUT_DIR/${SETUP_DMG}" ] && echo "  DMG:         $OUTPUT_DIR/${SETUP_DMG}"
[ -f "$OUTPUT_DIR/${SETUP_PKG}" ] && echo "  PKG:         $OUTPUT_DIR/${SETUP_PKG}"
[ -f "$OUTPUT_DIR/$ZIP_NAME" ] && echo "  Portable:    $OUTPUT_DIR/${ZIP_NAME}"
echo ""
echo "  --- Installing locally ---"
echo "  Open ${SETUP_DMG} and drag to Applications, or"
echo "  double-click ${SETUP_PKG} to install."
echo ""
echo "  --- If macOS blocks the app ---"
echo "  This app is not signed with an Apple Developer ID,"
echo "  so macOS Gatekeeper will block it on first launch."
echo ""
echo "  Option 1 (GUI):"
echo "    Right-click ${APP_BUNDLE} > Open > click Open"
echo "    in the dialog. Only needed once."
echo ""
echo "  Option 2 (Terminal):"
echo "    xattr -cr /Applications/${APP_NAME}.app"
echo ""
echo "  Option 3 (System Settings):"
echo "    After a blocked launch attempt, open System Settings,"
echo "    go to Privacy and Security, scroll down, and click"
echo "    Open Anyway next to the ${APP_NAME} message."
echo "============================================"