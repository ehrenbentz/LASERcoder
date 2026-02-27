#!/bin/bash
# build_LaserTAG_MacOS.sh
# Run from inside LaserTAG/build_MacOS/
#
# Directory structure:
#   LaserTAG/
#     CodeBase/          Python source files including LaserTAG.py
#     build_MacOS/       This script, libs/, Icons.icns, collect_dylibs.sh,
#                        create_dmg.sh, create_pkg.sh, Info.plist
#       output/          Created by this script: .build, .dist, .app,
#                        .dmg, .pkg
#
# Prerequisites:
#   brew install mpv (only needed if libs/ directory does not exist yet)
#   pip install nuitka PySide6 python-mpv
#
# Usage:
#   cd LaserTAG/build_MacOS
#   ./build_LaserTAG_MacOS.sh

set -e

APP_NAME="LaserTAG"
MAIN_SCRIPT="LaserTAG.py"
CODBASE_DIR="../CodeBase"
LIBS_DIR="./libs"
OUTPUT_DIR="./output"

export COPYFILE_DISABLE=1
export COPY_EXTENDED_ATTRIBUTES_DISABLE=1

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
# Collect dylibs (only if libs/ does not exist)
# ==================================================================
if [ ! -d "$LIBS_DIR" ] || [ -z "$(ls "$LIBS_DIR"/*.dylib 2>/dev/null)" ]; then
    echo "Collecting dylibs from Homebrew mpv..."

    LIBMPV_PATH="/opt/homebrew/lib/libmpv.2.dylib"
    if [ ! -f "$LIBMPV_PATH" ]; then
        echo "ERROR: libmpv not found at $LIBMPV_PATH"
        echo "Install it with: brew install mpv"
        exit 1
    fi

    if [ ! -f "./collect_dylibs.sh" ]; then
        echo "ERROR: collect_dylibs.sh not found in current directory."
        exit 1
    fi
    chmod +x ./collect_dylibs.sh
    ./collect_dylibs.sh "$LIBMPV_PATH" "$LIBS_DIR"

    echo ""
    rm -f "$LIBS_DIR/Python"
    rm -f "$LIBS_DIR/libvapoursynth-script.0.dylib"
    echo 'void* getVSScriptAPI(int version) { return 0; }' \
        | cc -shared -o "$LIBS_DIR/libvapoursynth-script.0.dylib" -x c - -arch arm64
    install_name_tool -id "@loader_path/libvapoursynth-script.0.dylib" \
        "$LIBS_DIR/libvapoursynth-script.0.dylib"

    echo ""
    echo "Codesigning all dylibs..."
    for lib in "$LIBS_DIR"/*.dylib; do
        chmod 755 "$lib"
        codesign --force --sign - "$lib"
    done
    echo "Signed $(ls "$LIBS_DIR"/*.dylib | wc -l | tr -d ' ') libraries."

else
    echo "libs/ directory exists, skipping dylib collection"
    echo "  (Delete libs/ and re-run to regenerate from Homebrew)"
fi

# ==================================================================
# Prepare output directory
# ==================================================================
echo ""
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Copy Python source into output for Nuitka to compile
cp "$CODBASE_DIR"/*.py "$OUTPUT_DIR/"

# Copy build resources into output
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

python -m nuitka \
    --standalone \
    --macos-create-app-bundle \
    --macos-app-icon=Icons.icns \
    --macos-app-name="$APP_NAME" \
    --output-filename="$APP_NAME" \
    --enable-plugin=pyside6 \
    "--include-data-files=libs/*.dylib=libs/" \
    "$MAIN_SCRIPT"

# Clean up source copies (keep only build artifacts)
rm -f *.py *.icns
rm -rf libs

## Replace Nuitka's auto-generated Info.plist with our custom one
echo ""
echo "Installing custom Info.plist..."
cp ../Info.plist "${APP_NAME}.app/Contents/Info.plist"
cd ..

# ==================================================================
# Create installers
# ==================================================================
chmod +x ./create_dmg.sh
./create_dmg.sh "$OUTPUT_DIR/${APP_NAME}.app" "$OUTPUT_DIR"

chmod +x ./create_pkg.sh
./create_pkg.sh "$OUTPUT_DIR/${APP_NAME}.app" "$OUTPUT_DIR"

# ==================================================================
# Summary
# ==================================================================
APP_VERSION="v1.2.0"
DMG_NAME="${APP_NAME}_${APP_VERSION}_macOS_arm64.dmg"
PKG_NAME="${APP_NAME}_${APP_VERSION}_macOS_arm64.pkg"

echo ""
echo "============================================"
echo "  Build Complete"
echo "============================================"
echo "  App bundle:  $OUTPUT_DIR/${APP_NAME}.app"
echo "  DMG:         $OUTPUT_DIR/${DMG_NAME}"
echo "  PKG:         $OUTPUT_DIR/${PKG_NAME}"
echo ""
echo "  --- Installing locally ---"
echo "  cp -R $OUTPUT_DIR/${APP_NAME}.app /Applications/"
echo ""
echo "  --- Distributing to others ---"
echo "  Option A: Send ${DMG_NAME}. They open it and drag"
echo "    ${APP_NAME}.app to the Applications folder."
echo ""
echo "  Option B: Send ${PKG_NAME}. They double-click to"
echo "    install. The pkg clears quarantine automatically."
echo ""
echo "  --- If macOS blocks the app ---"
echo "  This app is not signed with an Apple Developer ID,"
echo "  so macOS Gatekeeper will block it on first launch."
echo ""
echo "  Option 1 (GUI):"
echo "    Right-click ${APP_NAME}.app > Open > click Open"
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