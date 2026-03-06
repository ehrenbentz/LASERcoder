#!/bin/bash
# create_pkg.sh
# Creates a .pkg installer from a .app bundle.
# Auto-detects architecture for output filename.
#
# Handles existing installations gracefully:
#   - When run from the GUI Installer, the postinstall script removes any
#     existing .app at the install location before the new one is placed.
#   - The postinstall clears quarantine and fixes permissions.
#   - All postinstall operations are fault-tolerant (never causes install failure).
#
# Can be run from build_LaserTAG_MacOS.sh or independently:
#   ./create_pkg.sh                                          # uses defaults
#   ./create_pkg.sh ./output/LaserTAG.app ./output 1.2.0    # explicit args
#
# Arguments:
#   APP_PATH      Path to the .app bundle (default: ./output/LaserTAG.app)
#   OUTPUT_DIR    Directory for the .pkg output (default: directory containing APP_PATH)
#   APP_VERSION   Version string (default: 1.2.0)

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
# Arguments and configuration
# ==================================================================
APP_PATH="${1:-./output/LaserTAG.app}"
OUTPUT_DIR="${2:-$(dirname "$APP_PATH")}"
APP_NAME="$(basename "$APP_PATH" .app)"
APP_VERSION="${3:-1.2.0}"
PKG_NAME="${APP_NAME}_v${APP_VERSION}_macOS_${ARCH_LABEL}.pkg"
INSTALL_LOCATION="/Applications"
SCRIPTS_DIR="$(mktemp -d)"
PKG_ROOT="$(mktemp -d)"

# ==================================================================
# Validate inputs
# ==================================================================
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App bundle not found at $APP_PATH"
    echo ""
    echo "Usage: $0 [APP_PATH] [OUTPUT_DIR] [APP_VERSION]"
    echo "  APP_PATH defaults to ./output/${APP_NAME}.app"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Creating .pkg installer (${ARCH_LABEL})..."
echo "  Source:  $APP_PATH"
echo "  Output:  $OUTPUT_DIR/$PKG_NAME"
echo "  Version: $APP_VERSION"
echo ""

# ==================================================================
# Stage the .app inside a root directory for pkgbuild
# ==================================================================
cp -R "$APP_PATH" "$PKG_ROOT/${APP_NAME}.app"

# ==================================================================
# Create preinstall script
# Removes any existing .app at the install target before the new
# files are written. This prevents the "relocated" behavior where
# macOS moves the install to a different location when it detects
# a conflict.
# ==================================================================
cat > "$SCRIPTS_DIR/preinstall" << 'EOF'
#!/bin/bash
# $2 is the install target path, passed by the macOS installer
TARGET_APP="$2/LaserTAG.app"
if [ -d "$TARGET_APP" ]; then
    rm -rf "$TARGET_APP" 2>/dev/null || true
fi
exit 0
EOF
chmod +x "$SCRIPTS_DIR/preinstall"

# ==================================================================
# Create postinstall script
# Clears quarantine attributes and fixes permissions so the app
# launches without Gatekeeper issues. All operations are
# fault-tolerant to prevent install failures.
#
# $2 = install target path (passed by macOS installer)
# ==================================================================
cat > "$SCRIPTS_DIR/postinstall" << 'EOF'
#!/bin/bash
TARGET_APP="$2/LaserTAG.app"
if [ -d "$TARGET_APP" ]; then
    xattr -cr "$TARGET_APP" 2>/dev/null || true
    chmod -R 755 "$TARGET_APP" 2>/dev/null || true
    chown -R root:admin "$TARGET_APP" 2>/dev/null || true
fi
exit 0
EOF
chmod +x "$SCRIPTS_DIR/postinstall"

# ==================================================================
# Build the .pkg
# ==================================================================
pkgbuild \
    --root "$PKG_ROOT" \
    --install-location "${INSTALL_LOCATION}" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "edu.cornell.ehrenbentz.lasertag" \
    --version "$APP_VERSION" \
    "$OUTPUT_DIR/$PKG_NAME"

# ==================================================================
# Clean up temp directories
# ==================================================================
rm -rf "$SCRIPTS_DIR" "$PKG_ROOT"

echo ""
echo "Created: $OUTPUT_DIR/$PKG_NAME"
