#!/bin/bash
# build_LaserTAG_Linux.sh
# Run from inside LaserTAG/build_Linux/
#
# Directory structure:
#   LaserTAG/
#     current_version.txt    Shared version file
#     src/                   Python source files including LaserTAG.py
#     build_Linux/           This script, create_deb.sh, lasertag.desktop,
#                            laser.png
#       dist_Linux_<arch>_v#_#_#/  Build output (arch + version-stamped, created by this script)
#         LaserTAG.dist/       Complete application folder
#           LaserTAG             Main executable
#         LaserTAG_v{ver}_linux_amd64.deb
#         LaserTAG_v{ver}_linux_amd64_portable.tar.gz
#
# Prerequisites:
#   pip install nuitka PySide6 python-mpv
#   libmpv.so.2 must be present in this directory (build_Linux/)
#
# Usage:
#   cd LaserTAG/build_Linux
#   ./build_LaserTAG_Linux.sh

set -e

# ==================================================================
# Auto-detect architecture
# ==================================================================
MACHINE=$(uname -m)
case "$MACHINE" in
    x86_64)  ARCH_LABEL="amd64" ;;
    aarch64) ARCH_LABEL="arm64" ;;
    *)       ARCH_LABEL="$MACHINE" ;;
esac

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
# Verify Nuitka
# ==================================================================
if ! $PYTHON -m nuitka --version &>/dev/null; then
    echo "ERROR: Nuitka not installed. Run: pip install nuitka"
    exit 1
fi

# ==================================================================
# Read version from current_version.txt
# ==================================================================
VERSION_FILE="../current_version.txt"
if [ ! -f "$VERSION_FILE" ]; then
    echo "ERROR: current_version.txt not found at $VERSION_FILE"
    exit 1
fi

APP_VERSION=$(grep '^VERSION_NUMBER=' "$VERSION_FILE" | cut -d'=' -f2 | tr -d '\r')

if [ -z "$APP_VERSION" ]; then
    echo "ERROR: Could not parse version from current_version.txt"
    exit 1
fi

# ==================================================================
# Configuration
# ==================================================================
APP_NAME="LaserTAG"
MAIN_SCRIPT="LaserTAG.py"
SOURCE_DIR="../src"
VER_UNDERSCORED=$(echo "$APP_VERSION" | tr '.' '_')
OUTPUT_DIR="./dist_Linux_${ARCH_LABEL}_v${VER_UNDERSCORED}"

DEB_NAME="${APP_NAME}_v${APP_VERSION}_linux_${ARCH_LABEL}.deb"
TAR_NAME="${APP_NAME}_v${APP_VERSION}_linux_${ARCH_LABEL}_portable.tar.gz"

echo "============================================"
echo "  LaserTAG Linux Build"
echo "  Architecture: ${ARCH_LABEL}"
echo "  Version:      ${APP_VERSION}"
echo "============================================"
echo ""

# ==================================================================
# Verify directory structure
# ==================================================================
if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: source directory not found at $SOURCE_DIR"
    echo "Run this script from inside LaserTAG/build_Linux/"
    exit 1
fi

if [ ! -f "$SOURCE_DIR/$MAIN_SCRIPT" ]; then
    echo "ERROR: $MAIN_SCRIPT not found in $SOURCE_DIR/"
    exit 1
fi

if [ ! -f "laser.png" ]; then
    echo "ERROR: laser.png not found in current directory."
    echo "Convert from build_Windows/laser.ico or provide a 256x256 PNG."
    exit 1
fi

# ==================================================================
# Verify libmpv.so.2
# ==================================================================
if [ ! -f "libmpv.so.2" ]; then
    echo "ERROR: libmpv.so.2 not found in current directory (build_Linux/)."
    exit 1
fi

# ==================================================================
# Prepare output directory
# ==================================================================
echo ""
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Copy Python source into output for Nuitka to compile
cp "$SOURCE_DIR"/*.py "$OUTPUT_DIR/"

# Copy local libmpv for bundling
cp libmpv.so.2 "$OUTPUT_DIR/"
chmod 755 "$OUTPUT_DIR/libmpv.so.2"

# ==================================================================
# Compile with Nuitka
# ==================================================================
echo ""
echo "Compiling with Nuitka..."
cd "$OUTPUT_DIR"

$PYTHON -m nuitka \
    --standalone \
    --assume-yes-for-downloads \
    --remove-output \
    --output-filename="$APP_NAME" \
    --enable-plugin=pyside6 \
    --nofollow-import-to=PIL \
    --nofollow-import-to=PySide6.QtWebEngineWidgets \
    --nofollow-import-to=PySide6.QtWebEngineCore \
    --nofollow-import-to=PySide6.QtWebEngine \
    --nofollow-import-to=PySide6.QtWebChannel \
    --nofollow-import-to=PySide6.QtWebSockets \
    --nofollow-import-to=PySide6.QtQuick \
    --nofollow-import-to=PySide6.QtQuick3D \
    --nofollow-import-to=PySide6.QtQml \
    --nofollow-import-to=PySide6.Qt3DCore \
    --nofollow-import-to=PySide6.Qt3DRender \
    --nofollow-import-to=PySide6.Qt3DInput \
    --nofollow-import-to=PySide6.Qt3DLogic \
    --nofollow-import-to=PySide6.Qt3DExtras \
    --nofollow-import-to=PySide6.Qt3DAnimation \
    --nofollow-import-to=PySide6.QtBluetooth \
    --nofollow-import-to=PySide6.QtNfc \
    --nofollow-import-to=PySide6.QtRemoteObjects \
    --nofollow-import-to=PySide6.QtSensors \
    --nofollow-import-to=PySide6.QtSerialPort \
    --nofollow-import-to=PySide6.QtSerialBus \
    --nofollow-import-to=PySide6.QtTest \
    --nofollow-import-to=PySide6.QtPositioning \
    --nofollow-import-to=PySide6.QtMultimedia \
    --nofollow-import-to=PySide6.QtMultimediaWidgets \
    --nofollow-import-to=PySide6.QtDesigner \
    --nofollow-import-to=PySide6.QtHelp \
    --nofollow-import-to=PySide6.QtSql \
    --nofollow-import-to=PySide6.QtXml \
    --nofollow-import-to=PySide6.QtPdf \
    --nofollow-import-to=PySide6.QtPdfWidgets \
    --nofollow-import-to=PySide6.QtHttpServer \
    --nofollow-import-to=PySide6.QtSpatialAudio \
    --nofollow-import-to=PySide6.QtTextToSpeech \
    --nofollow-import-to=PySide6.QtVirtualKeyboard \
    --nofollow-import-to=PySide6.QtDataVisualization \
    --nofollow-import-to=PySide6.QtGraphs \
    --nofollow-import-to=PySide6.QtScxml \
    --nofollow-import-to=PySide6.QtStateMachine \
    --linux-icon=../laser.png \
    --include-data-files=libmpv.so.2=libmpv.so.2 \
    "$MAIN_SCRIPT"

# ==================================================================
# Clean up staged source from output
# ==================================================================
rm -f *.py
rm -f libmpv.so.2

# ==================================================================
# Remove unused Qt runtime libraries not caught by --nofollow-import-to
# ==================================================================
echo ""
echo "Removing unused Qt runtime libraries..."
DIST_DIR="${APP_NAME}.dist"
rm -f "${DIST_DIR}"/libQt6Pdf*.so* 2>/dev/null
rm -f "${DIST_DIR}"/PySide6/Qt/plugins/imageformats/libqpdf*.so 2>/dev/null
rm -f "${DIST_DIR}"/libQt63DCore*.so* 2>/dev/null
rm -f "${DIST_DIR}"/PySide6/Qt3DCore*.so 2>/dev/null

cd ..

# ==================================================================
# Create .deb installer
# ==================================================================
if [ -f "./create_deb.sh" ]; then
    chmod +x ./create_deb.sh
    ./create_deb.sh "$OUTPUT_DIR/${APP_NAME}.dist" "$OUTPUT_DIR" "$APP_VERSION"
else
    echo "WARNING: create_deb.sh not found. Skipping .deb creation."
fi

# ==================================================================
# Create portable .tar.gz
# ==================================================================
echo ""
echo "Creating portable tarball..."

tar -czf "$OUTPUT_DIR/$TAR_NAME" -C "$OUTPUT_DIR" "${APP_NAME}.dist"
echo "Tarball created: $OUTPUT_DIR/$TAR_NAME"

# ==================================================================
# Clean up build artifacts
# ==================================================================
echo ""
echo "Cleaning up..."
rm -rf "$OUTPUT_DIR/${APP_NAME}.dist"

# ==================================================================
# Summary
# ==================================================================
echo ""
echo "============================================"
echo "  Build Complete (${ARCH_LABEL})"
echo "============================================"
[ -f "$OUTPUT_DIR/$DEB_NAME" ] && echo "  .deb:        $OUTPUT_DIR/$DEB_NAME"
[ -f "$OUTPUT_DIR/$TAR_NAME" ] && echo "  Portable:    $OUTPUT_DIR/$TAR_NAME"
echo ""
echo "  --- Installing .deb ---"
echo "  sudo dpkg -i $OUTPUT_DIR/$DEB_NAME"
echo ""
echo "  --- Portable usage ---"
echo "  tar xzf $OUTPUT_DIR/$TAR_NAME"
echo "  ./${APP_NAME}.dist/${APP_NAME}"
echo "============================================"