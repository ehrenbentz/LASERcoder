#!/bin/bash
# create_logo.sh
# Generates OS-specific app icons from a source PNG.
#
# Outputs:
#   icons/laser.ico           Windows icon (16/32/48/64/128/256px)
#   icons/Icons.icns          macOS icon set
#   icons/LASERcoder_*.png    Individual PNG sizes for Linux
#
# Prerequisites:
#   - ImageMagick (convert/magick command)
#   - iconutil (macOS only, for .icns generation)
#     On Linux, install icnsutils: sudo apt install icnsutils
#
# Usage:
#   cd icons
#   ./create_logo.sh logo.png
#   ./create_logo.sh              # defaults to LASERcoder_256.png

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="${1:-$SCRIPT_DIR/LASERcoder_256.png}"

if [ ! -f "$SOURCE" ]; then
    echo "ERROR: Source image not found: $SOURCE"
    echo "Usage: $0 [source.png]"
    exit 1
fi

# Find ImageMagick
if command -v magick &>/dev/null; then
    CONVERT="magick"
elif command -v convert &>/dev/null; then
    CONVERT="convert"
else
    echo "ERROR: ImageMagick not found. Install it:"
    echo "  macOS:   brew install imagemagick"
    echo "  Ubuntu:  sudo apt install imagemagick"
    echo "  Windows: https://imagemagick.org/script/download.php"
    exit 1
fi

SIZES=(16 32 48 64 128 256)

echo "Source: $SOURCE"
echo ""

# ==================================================================
# Generate individual PNGs
# ==================================================================
echo "Generating PNGs..."
for s in "${SIZES[@]}"; do
    OUT="$SCRIPT_DIR/LASERcoder_${s}.png"
    $CONVERT "$SOURCE" -resize "${s}x${s}" "$OUT"
    echo "  ${s}x${s} -> $(basename "$OUT")"
done

# ==================================================================
# Generate Windows .ico
# ==================================================================
echo ""
echo "Generating Windows .ico..."
ICO_INPUTS=()
for s in "${SIZES[@]}"; do
    ICO_INPUTS+=("$SCRIPT_DIR/LASERcoder_${s}.png")
done
$CONVERT "${ICO_INPUTS[@]}" "$SCRIPT_DIR/laser.ico"
echo "  -> laser.ico"

# ==================================================================
# Generate macOS .icns
# ==================================================================
echo ""
echo "Generating macOS .icns..."

if command -v iconutil &>/dev/null; then
    # macOS native method
    ICONSET="$SCRIPT_DIR/LASERcoder.iconset"
    mkdir -p "$ICONSET"

    ICNS_SIZES=(16 32 64 128 256 512)
    for s in "${ICNS_SIZES[@]}"; do
        $CONVERT "$SOURCE" -resize "${s}x${s}" "$ICONSET/icon_${s}x${s}.png"
        s2=$((s * 2))
        $CONVERT "$SOURCE" -resize "${s2}x${s2}" "$ICONSET/icon_${s}x${s}@2x.png"
    done

    iconutil -c icns -o "$SCRIPT_DIR/Icons.icns" "$ICONSET"
    rm -rf "$ICONSET"
    echo "  -> Icons.icns (via iconutil)"

elif command -v png2icns &>/dev/null; then
    # Linux fallback via icnsutils
    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT

    # png2icns requires specific sizes: 16, 32, 48, 128, 256, 512
    PNG2ICNS_SIZES=(16 32 48 128 256 512)
    INPUTS=()
    for s in "${PNG2ICNS_SIZES[@]}"; do
        OUT="$TMPDIR/icon_${s}.png"
        $CONVERT "$SOURCE" -resize "${s}x${s}" "$OUT"
        INPUTS+=("$OUT")
    done

    png2icns "$SCRIPT_DIR/Icons.icns" "${INPUTS[@]}"
    echo "  -> Icons.icns (via png2icns)"
else
    echo "  SKIPPED: iconutil (macOS) or png2icns (Linux) not found."
    echo "  Install icnsutils on Linux: sudo apt install icnsutils"
    echo "  On macOS, iconutil is built in."
fi

# ==================================================================
# Summary
# ==================================================================
echo ""
echo "============================================"
echo "  Logo Generation Complete"
echo "============================================"
for s in "${SIZES[@]}"; do
    [ -f "$SCRIPT_DIR/LASERcoder_${s}.png" ] && echo "  PNG ${s}px:  LASERcoder_${s}.png"
done
[ -f "$SCRIPT_DIR/laser.ico" ] && echo "  Windows:    laser.ico"
[ -f "$SCRIPT_DIR/Icons.icns" ] && echo "  macOS:      Icons.icns"
echo "============================================"
