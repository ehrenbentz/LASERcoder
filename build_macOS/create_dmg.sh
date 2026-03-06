#!/bin/bash
# create_dmg.sh
# Creates a distributable DMG from a .app bundle.
# Auto-detects architecture for output filename.
#
# Usage:
#   ./create_dmg.sh [APP_PATH] [OUTPUT_DIR] [APP_VERSION]
#
# Arguments:
#   APP_PATH      Path to the .app bundle (default: ./output/LaserTAG.app)
#   OUTPUT_DIR    Directory for the .dmg output (default: directory containing APP_PATH)
#   APP_VERSION   Version string, e.g. "1.2.0" (default: 1.2.0)

set -e

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="arm64"
else
    ARCH_LABEL="x86_64"
fi

APP_PATH="${1:-./output/LaserTAG.app}"
OUTPUT_DIR="${2:-$(dirname "$APP_PATH")}"

APP_NAME="$(basename "$APP_PATH" .app)"
APP_VERSION="${3:-1.2.0}"
DMG_NAME="${APP_NAME}_v${APP_VERSION}_macOS_${ARCH_LABEL}.dmg"
STAGING_DIR="$(mktemp -d)"

export COPYFILE_DISABLE=1
export COPY_EXTENDED_ATTRIBUTES_DISABLE=1

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App bundle not found at $APP_PATH"
    exit 1
fi

# Rename the app if Nuitka named it main.app
if [ -d "$(dirname "$APP_PATH")/main.app" ] && [ ! -d "$APP_PATH" ]; then
    mv "$(dirname "$APP_PATH")/main.app" "$APP_PATH"
fi

mkdir -p "$OUTPUT_DIR"

echo "Creating DMG installer (${ARCH_LABEL})..."

cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$OUTPUT_DIR/$DMG_NAME"

rm -rf "$STAGING_DIR"

echo "Created: $OUTPUT_DIR/$DMG_NAME"
