#!/bin/bash
# create_pkg.sh
# Creates a .pkg installer from a .app bundle.
# The .pkg includes a postinstall script that clears quarantine
# attributes so the app launches without Gatekeeper issues.
#
# Usage:
#   ./create_pkg.sh [APP_PATH] [OUTPUT_DIR] [APP_VERSION]
#
# Arguments:
#   APP_PATH      Path to the .app bundle (default: ./output/LaserTAG.app)
#   OUTPUT_DIR    Directory for the .pkg output (default: directory containing APP_PATH)
#   APP_VERSION   Version string, e.g. "1.2.0" (default: 0.0.0)

set -e

APP_PATH="${1:-./output/LaserTAG.app}"
OUTPUT_DIR="${2:-$(dirname "$APP_PATH")}"

APP_NAME="$(basename "$APP_PATH" .app)"
APP_VERSION="${3:-1.2.0}"
PKG_NAME="${APP_NAME}_v${APP_VERSION}_macOS_arm64.pkg"
INSTALL_LOCATION="/Applications"
SCRIPTS_DIR="$(mktemp -d)"

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: App bundle not found at $APP_PATH"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Creating .pkg installer..."

# Create postinstall script to clear quarantine attributes
cat > "$SCRIPTS_DIR/postinstall" << POSTINSTALL
#!/bin/bash
xattr -cr ${INSTALL_LOCATION}/${APP_NAME}.app
POSTINSTALL
chmod +x "$SCRIPTS_DIR/postinstall"

pkgbuild \
    --root "$APP_PATH" \
    --install-location "${INSTALL_LOCATION}/${APP_NAME}.app" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "edu.cornell.ehrenbentz.lasertag" \
    --version "$APP_VERSION" \
    "$OUTPUT_DIR/$PKG_NAME"

rm -rf "$SCRIPTS_DIR"

echo "Created: $OUTPUT_DIR/$PKG_NAME"