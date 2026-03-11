#!/bin/bash
# collect_dylibs.sh
# Recursively collects all non-system dylib dependencies of libmpv
# and rewrites load paths for bundling.
#
# Also:
#   - Removes the Python framework library (not needed at runtime)
#   - Creates a vapoursynth stub (mpv links against it but does not use it)
#   - Codesigns all collected dylibs
#
# Auto-detects architecture and Homebrew prefix.
# Creates an architecture-labeled output directory (libs_x86_64/ or libs_arm64/).
#
# Usage:
#   ./collect_dylibs.sh              # auto-detect everything
#   ./collect_dylibs.sh ./custom_dir # override output directory

set -e

# Detect architecture and Homebrew prefix
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="arm64"
    ARCH_FLAG="-arch arm64"
else
    ARCH_LABEL="x86_64"
    ARCH_FLAG="-arch x86_64"
fi

if command -v brew >/dev/null 2>&1; then
    BREW_PREFIX="$(brew --prefix)"
else
    if [ "$ARCH" = "arm64" ]; then
        BREW_PREFIX="/opt/homebrew"
    else
        BREW_PREFIX="/usr/local"
    fi
fi

# Detect libmpv
SEED="${BREW_PREFIX}/lib/libmpv.2.dylib"
if [ ! -f "$SEED" ]; then
    echo "ERROR: libmpv not found at $SEED"
    echo "Install it with: brew install mpv"
    exit 1
fi

# Output directory: use argument if provided, otherwise libs_<arch>
DEST="${1:-./libs_${ARCH_LABEL}}"

echo "Architecture:    $ARCH_LABEL"
echo "Homebrew prefix: $BREW_PREFIX"
echo "Seed library:    $SEED"
echo "Output dir:      $DEST"
echo ""

mkdir -p "$DEST"

# Copy the seed library
cp "$SEED" "$DEST/"
echo "Copied: $(basename "$SEED")"

# Track progress
PROCESSED=()

is_processed() {
    local name="$1"
    for p in "${PROCESSED[@]}"; do
        if [ "$p" = "$name" ]; then
            return 0
        fi
    done
    return 1
}

is_system_lib() {
    local path="$1"
    case "$path" in
        /usr/lib/*|/System/*) return 0 ;;
        *) return 1 ;;
    esac
}

collect_deps() {
    local libpath="$1"
    local libname
    libname="$(basename "$libpath")"

    if is_processed "$libname"; then
        return
    fi
    PROCESSED+=("$libname")

    echo "Processing: $libname"

    local deps
    deps=$(otool -L "$libpath" | tail -n +2 | awk '{print $1}')

    for dep in $deps; do
        if is_system_lib "$dep"; then
            continue
        fi

        local depname
        depname="$(basename "$dep")"
        if [ "$depname" = "$libname" ]; then
            continue
        fi

        # Skip already-rewritten paths
        case "$dep" in
            @*) continue ;;
        esac

        # Resolve actual file path
        local resolved="$dep"

        if [ ! -f "$resolved" ]; then
            # Try Homebrew lib directory first (fast)
            if [ -f "${BREW_PREFIX}/lib/$depname" ]; then
                resolved="${BREW_PREFIX}/lib/$depname"
            else
                # Fall back to searching the entire Homebrew tree
                resolved=$(find "$BREW_PREFIX" -name "$depname" -type f 2>/dev/null | head -n 1)
                if [ -z "$resolved" ] || [ ! -f "$resolved" ]; then
                    echo "  WARNING: Cannot find $dep ($depname), skipping"
                    continue
                fi
            fi
        fi

        # Copy if not already in dest
        if [ ! -f "$DEST/$depname" ]; then
            cp "$resolved" "$DEST/$depname"
            echo "  Copied: $depname"
        fi

        # Recurse
        collect_deps "$DEST/$depname"
    done
}

# ==================================================================
# Phase 1: Recursively collect all dependencies
# ==================================================================
echo ""
echo "Collecting dependencies..."
collect_deps "$DEST/$(basename "$SEED")"

# ==================================================================
# Phase 2: Remove Python framework and create vapoursynth stub
# ==================================================================
echo ""
echo "Cleaning up..."

# Remove Python framework library (collected as a transitive dep but not needed)
rm -f "$DEST/Python"
rm -f "$DEST/Python3"

# Replace vapoursynth with a stub (mpv links against it but LaserTAG does not use it)
rm -f "$DEST/libvapoursynth-script.0.dylib"
echo 'void* getVSScriptAPI(int version) { return 0; }' \
    | cc -shared -o "$DEST/libvapoursynth-script.0.dylib" -x c - $ARCH_FLAG
install_name_tool -id "@loader_path/libvapoursynth-script.0.dylib" \
    "$DEST/libvapoursynth-script.0.dylib"

# ==================================================================
# Phase 3: Rewrite all load paths to @loader_path/
# ==================================================================
echo ""
echo "Rewriting load paths..."

for lib in "$DEST"/*.dylib; do
    libname="$(basename "$lib")"
    echo "Rewriting: $libname"

    install_name_tool -id "@loader_path/$libname" "$lib" 2>/dev/null || true

    deps=$(otool -L "$lib" | tail -n +2 | awk '{print $1}')
    for dep in $deps; do
        if is_system_lib "$dep"; then
            continue
        fi

        depname="$(basename "$dep")"

        case "$dep" in
            @loader_path/*) continue ;;
        esac

        if [ -f "$DEST/$depname" ]; then
            install_name_tool -change "$dep" "@loader_path/$depname" "$lib" 2>/dev/null || true
        fi
    done
done

# ==================================================================
# Phase 4: Codesign all dylibs
# ==================================================================
echo ""
echo "Codesigning all dylibs..."

for lib in "$DEST"/*.dylib; do
    chmod 755 "$lib"
    codesign --force --sign - "$lib"
done
echo "Signed $(ls "$DEST"/*.dylib | wc -l | tr -d ' ') libraries."

# ==================================================================
# Phase 5: Verify
# ==================================================================
echo ""
echo "Verifying..."

ERRORS=0
for lib in "$DEST"/*.dylib; do
    libname="$(basename "$lib")"
    deps=$(otool -L "$lib" | tail -n +2 | awk '{print $1}')
    for dep in $deps; do
        if is_system_lib "$dep"; then
            continue
        fi
        case "$dep" in
            @loader_path/*) continue ;;
        esac
        echo "  UNRESOLVED in $libname: $dep"
        ERRORS=$((ERRORS + 1))
    done
done

if [ "$ERRORS" -eq 0 ]; then
    echo "All dependencies resolved successfully."
else
    echo "$ERRORS unresolved dependencies found. Review the warnings above."
fi

echo ""
echo "Done. Collected $(ls "$DEST"/*.dylib | wc -l | tr -d ' ') dylibs into $DEST"
echo ""
