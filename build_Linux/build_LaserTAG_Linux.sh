#!/bin/bash
# build_LaserTAG_Linux.sh
# Run from inside LaserTAG/build_Linux/
#
# Directory structure:
#   LaserTAG/
#     CodeBase/              Python source files including LaserTAG.py
#     build_Linux/           This script, create_deb.sh, lasertag.desktop,
#                            laser.png
#       dist_Linux/          Build output (created by this script)
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
OUTPUT_DIR="./dist_Linux"

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
if [ ! -d "$CODBASE_DIR" ]; then
    echo "ERROR: CodeBase directory not found at $CODBASE_DIR"
    echo "Run this script from inside LaserTAG/build_Linux/"
    exit 1
fi

if [ ! -f "$CODBASE_DIR/$MAIN_SCRIPT" ]; then
    echo "ERROR: $MAIN_SCRIPT not found in $CODBASE_DIR/"
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
cp "$CODBASE_DIR"/*.py "$OUTPUT_DIR/"

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
    --output-filename="$APP_NAME" \
    --enable-plugin=pyside6 \
    --nofollow-import-to=PIL \
    --linux-icon=../laser.png \
    --include-data-files=libmpv.so.2=libmpv.so.2 \
    "$MAIN_SCRIPT"

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
rm -rf "$OUTPUT_DIR/${APP_NAME}.build"
rm -rf "$OUTPUT_DIR/${APP_NAME}.dist"
rm -f "$OUTPUT_DIR"/*.py
rm -f "$OUTPUT_DIR/libmpv.so.2"

# ==================================================================
# Summary
# ==================================================================
echo ""
echo "============================================"
echo "  Build Complete (${ARCH_LABEL})"
echo "============================================"
echo "  App folder:  $OUTPUT_DIR/${APP_NAME}.dist/"
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
