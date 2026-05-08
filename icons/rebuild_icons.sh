#!/bin/bash
# rebuild_icons.sh
# Compiles icons.qrc into src/icons_rc.py using PySide6's rcc tool.
#
# Run from inside the icons/ directory:
#   cd icons
#   ./rebuild_icons.sh
#
# Prerequisites:
#   pip install PySide6

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QRC_FILE="$SCRIPT_DIR/icons.qrc"
OUTPUT_FILE="$SCRIPT_DIR/../src/icons_rc.py"

if [ ! -f "$QRC_FILE" ]; then
    echo "ERROR: icons.qrc not found at $QRC_FILE"
    exit 1
fi

# Find pyside6-rcc
if command -v pyside6-rcc &>/dev/null; then
    RCC=pyside6-rcc
else
    # Try via python module
    PYTHON=""
    if command -v python3 &>/dev/null; then
        PYTHON=python3
    elif command -v python &>/dev/null; then
        PYTHON=python
    else
        echo "ERROR: No python3 or python found on PATH"
        exit 1
    fi

    if $PYTHON -c "from PySide6.scripts.pyside_tool import rcc" 2>/dev/null; then
        RCC="$PYTHON -m PySide6.scripts.pyside_tool rcc"
    else
        echo "ERROR: pyside6-rcc not found. Install PySide6: pip install PySide6"
        exit 1
    fi
fi

echo "Compiling $QRC_FILE -> $OUTPUT_FILE"

cd "$SCRIPT_DIR"
$RCC "$QRC_FILE" -o "$OUTPUT_FILE"

echo "Done. Generated $(wc -l < "$OUTPUT_FILE") lines in $(basename "$OUTPUT_FILE")"
