#!/bin/bash
# create_dmg.sh
# Creates a distributable DMG from a .app bundle.
# Auto-detects architecture for output filename.
#
# Usage:
#   ./create_dmg.sh [APP_PATH] [OUTPUT_DIR] [APP_VERSION]
#
# Arguments:
#   APP_PATH      Path to the .app bundle
#   OUTPUT_DIR    Directory for the .dmg output (default: directory containing APP_PATH)
#   APP_VERSION   Version string (default: DEFAULT_VERSION below)

set -e

# ==================================================================
# Version — update this when bumping the app version
# ==================================================================
DEFAULT_VERSION="1.3.0"

ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="arm64"
else
    ARCH_LABEL="x86_64"
fi

APP_PATH="${1:-./dist_${ARCH_LABEL}/LaserTAG.app}"
OUTPUT_DIR="${2:-$(dirname "$APP_PATH")}"

APP_VERSION="${3:-$DEFAULT_VERSION}"
DMG_VOLUME_NAME="LaserTAG"
DMG_NAME="LaserTAG_v${APP_VERSION}_macOS_${ARCH_LABEL}.dmg"
STAGING_DIR="$(mktemp -d)"

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

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App bundle not found at $APP_PATH"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Creating DMG installer (${ARCH_LABEL})..."

retry_busy cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

retry_busy hdiutil create \
    -volname "$DMG_VOLUME_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$OUTPUT_DIR/$DMG_NAME"

rm -rf "$STAGING_DIR"

echo "Created: $OUTPUT_DIR/$DMG_NAME"
