#!/bin/bash
# create_deb.sh
# Creates a .deb package from the Nuitka standalone output.
# Auto-detects architecture for the package metadata.
#
# Can be run from build_LaserTAG_Linux.sh or independently:
#   ./create_deb.sh                                                     # uses defaults
#   ./create_deb.sh ./dist_Linux_amd64_v1_3_1/LaserTAG.dist ./dist_Linux_amd64_v1_3_1 1.3.1
#
# Arguments:
#   APP_DIR       Path to the Nuitka .dist directory
#   OUTPUT_DIR    Directory for the .deb output (default: directory containing APP_DIR)
#   APP_VERSION   Version string (read from current_version.txt)

set -e

# ==================================================================
# Version — read from current_version.txt if no argument provided
# ==================================================================
if [ -z "$3" ]; then
    VERSION_FILE="../current_version.txt"
    if [ ! -f "$VERSION_FILE" ]; then
        echo "ERROR: No version argument provided and current_version.txt not found at $VERSION_FILE"
        exit 1
    fi
    APP_VERSION=$(grep '^VERSION_NUMBER=' "$VERSION_FILE" | cut -d'=' -f2 | tr -d '\r')
    if [ -z "$APP_VERSION" ]; then
        echo "ERROR: Could not parse version from $VERSION_FILE"
        exit 1
    fi
else
    APP_VERSION="$3"
fi

# ==================================================================
# Auto-detect architecture (dpkg naming: amd64, arm64, etc.)
# ==================================================================
if command -v dpkg &>/dev/null; then
    DEB_ARCH=$(dpkg --print-architecture)
else
    MACHINE=$(uname -m)
    case "$MACHINE" in
        x86_64)  DEB_ARCH="amd64" ;;
        aarch64) DEB_ARCH="arm64" ;;
        *)       DEB_ARCH="$MACHINE" ;;
    esac
fi

# ==================================================================
# Arguments and configuration
# ==================================================================
VER_UNDERSCORED=$(echo "$APP_VERSION" | tr '.' '_')
APP_DIR="${1:-./dist_Linux_${DEB_ARCH}_v${VER_UNDERSCORED}/LaserTAG.dist}"
OUTPUT_DIR="${2:-$(dirname "$APP_DIR")}"
APP_NAME="LaserTAG"
DEB_NAME="${APP_NAME}_v${APP_VERSION}_linux_${DEB_ARCH}.deb"
INSTALL_DIR="/opt/${APP_NAME}"

# ==================================================================
# Validate inputs
# ==================================================================
if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: Application directory not found at $APP_DIR"
    echo ""
    echo "Usage: $0 [APP_DIR] [OUTPUT_DIR] [APP_VERSION]"
    echo "  APP_DIR defaults to ./dist_Linux_v${VER_UNDERSCORED}/LaserTAG.dist"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Creating .deb package (${DEB_ARCH})..."
echo "  Source:  $APP_DIR"
echo "  Output:  $OUTPUT_DIR/$DEB_NAME"
echo "  Version: $APP_VERSION"
echo ""

# ==================================================================
# Create staging directory
# ==================================================================
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

# Application files
mkdir -p "${STAGING}${INSTALL_DIR}"
cp -a "$APP_DIR"/. "${STAGING}${INSTALL_DIR}/"
chmod 755 "${STAGING}${INSTALL_DIR}/${APP_NAME}"

# Symlink in /usr/local/bin
mkdir -p "${STAGING}/usr/local/bin"
ln -s "${INSTALL_DIR}/${APP_NAME}" "${STAGING}/usr/local/bin/lasertag"

# Desktop entry
mkdir -p "${STAGING}/usr/share/applications"
if [ -f "lasertag.desktop" ]; then
    cp "lasertag.desktop" "${STAGING}/usr/share/applications/"
fi

# Icon
mkdir -p "${STAGING}/usr/share/icons/hicolor/256x256/apps"
if [ -f "laser.png" ]; then
    cp "laser.png" "${STAGING}/usr/share/icons/hicolor/256x256/apps/lasertag.png"
fi

# ==================================================================
# DEBIAN control file
# ==================================================================
mkdir -p "${STAGING}/DEBIAN"

cat > "${STAGING}/DEBIAN/control" << EOF
Package: lasertag
Version: ${APP_VERSION}
Section: science
Priority: optional
Architecture: ${DEB_ARCH}
Depends: libgl1, libegl1
Maintainer: Ehren Bentz <ehren.bentz@cornell.edu>
Homepage: https://github.com/ehrenbentz/LaserTAG
Description: Lightweight annotation software for ethology research and Tracking Animals Gooder
 LaserTAG is a free, open-source desktop application for behavioral
 annotation of video recordings. Designed for researchers in ethology,
 animal behavior, ecology, and psychology.
EOF

# ==================================================================
# DEBIAN postinst script
# ==================================================================
cat > "${STAGING}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
exit 0
EOF
chmod 755 "${STAGING}/DEBIAN/postinst"

# ==================================================================
# DEBIAN prerm script
# ==================================================================
cat > "${STAGING}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
rm -f /usr/local/bin/lasertag
exit 0
EOF
chmod 755 "${STAGING}/DEBIAN/prerm"

# ==================================================================
# DEBIAN postrm script
# ==================================================================
cat > "${STAGING}/DEBIAN/postrm" << 'EOF'
#!/bin/bash
update-desktop-database /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
exit 0
EOF
chmod 755 "${STAGING}/DEBIAN/postrm"

# ==================================================================
# Build the .deb
# ==================================================================
dpkg-deb --build "$STAGING" "$OUTPUT_DIR/$DEB_NAME"

echo ""
echo "Created: $OUTPUT_DIR/$DEB_NAME"
