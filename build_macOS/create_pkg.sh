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
# Can be run from build_LASERcoder_MacOS.sh or independently:
#   ./create_pkg.sh                                                     # uses defaults
#   ./create_pkg.sh ./dist_macOS_arm64_v1_3_0/LASERcoder.app ./dist_macOS_arm64_v1_3_0 1.3.0
#
# Arguments:
#   APP_PATH      Path to the .app bundle
#   OUTPUT_DIR    Directory for the .pkg output (default: directory containing APP_PATH)
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
# Detect hardware architecture
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
VER_UNDERSCORED=$(echo "$APP_VERSION" | tr '.' '_')
APP_PATH="${1:-./dist_macOS_${ARCH_LABEL}_v${VER_UNDERSCORED}/LASERcoder.app}"
OUTPUT_DIR="${2:-$(dirname "$APP_PATH")}"
APP_NAME="LASERcoder"
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
    echo "  APP_PATH defaults to ./dist_macOS_v${VER_UNDERSCORED}/${APP_NAME}.app"
    exit 1
fi

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

mkdir -p "$OUTPUT_DIR"

echo "Creating .pkg installer (${ARCH_LABEL})..."
echo "  Source:  $APP_PATH"
echo "  Output:  $OUTPUT_DIR/$PKG_NAME"
echo "  Version: $APP_VERSION"
echo ""

# ==================================================================
# Stage the .app inside a root directory for pkgbuild
# ==================================================================
APP_BUNDLE="$(basename "$APP_PATH")"
retry_busy cp -R "$APP_PATH" "$PKG_ROOT/${APP_BUNDLE}"

# ==================================================================
# Create preinstall script
# Removes any existing .app at the install target before the new
# files are written. This prevents the "relocated" behavior where
# macOS moves the install to a different location when it detects
# a conflict.
# ==================================================================
cat > "$SCRIPTS_DIR/preinstall" << EOF
#!/bin/bash
# \$2 is the install target path, passed by the macOS installer
TARGET_APP="\$2/${APP_BUNDLE}"
if [ -d "\$TARGET_APP" ]; then
    rm -rf "\$TARGET_APP" 2>/dev/null || true
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
cat > "$SCRIPTS_DIR/postinstall" << EOF
#!/bin/bash
TARGET_APP="\$2/${APP_BUNDLE}"
if [ -d "\$TARGET_APP" ]; then
    xattr -cr "\$TARGET_APP" 2>/dev/null || true
    chmod -R 755 "\$TARGET_APP" 2>/dev/null || true
    chown -R root:admin "\$TARGET_APP" 2>/dev/null || true
fi
exit 0
EOF
chmod +x "$SCRIPTS_DIR/postinstall"

# ==================================================================
# Build the .pkg
# ==================================================================
retry_busy pkgbuild \
    --root "$PKG_ROOT" \
    --install-location "${INSTALL_LOCATION}" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "edu.cornell.ehrenbentz.lasercoder" \
    --version "$APP_VERSION" \
    "$OUTPUT_DIR/$PKG_NAME"

# ==================================================================
# Clean up temp directories
# ==================================================================
rm -rf "$SCRIPTS_DIR" "$PKG_ROOT"

echo ""
echo "Created: $OUTPUT_DIR/$PKG_NAME"
