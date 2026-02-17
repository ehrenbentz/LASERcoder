#!/bin/bash
# collect_dylibs.sh
# Recursively collects all non-system dylib dependencies and rewrites load paths.
# Usage: ./collect_dylibs.sh /opt/homebrew/lib/libmpv.2.dylib ./libs

set -e

SEED="$1"
DEST="$2"

if [ -z "$SEED" ] || [ -z "$DEST" ]; then
    echo "Usage: $0 <path-to-libmpv.dylib> <output-directory>"
    exit 1
fi

mkdir -p "$DEST"

# Copy the seed library
cp "$SEED" "$DEST/"
echo "Copied: $(basename "$SEED")"

# Track what we have already processed
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
        /usr/lib/*) return 0 ;;
        /System/*) return 0 ;;
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

    # Get all dependencies
    local deps
    deps=$(otool -L "$libpath" | tail -n +2 | awk '{print $1}')

    for dep in $deps; do
        # Skip system libraries
        if is_system_lib "$dep"; then
            continue
        fi

        # Skip self-references
        local depname
        depname="$(basename "$dep")"
        if [ "$depname" = "$libname" ]; then
            continue
        fi

        # Resolve the actual file path
        local resolved="$dep"

        # Handle @loader_path, @rpath, @executable_path (already rewritten)
        case "$dep" in
            @*) continue ;;
        esac

        # If the file does not exist at the stated path, try Homebrew cellar
        if [ ! -f "$resolved" ]; then
            # Try to find it via Homebrew
            resolved=$(find /opt/homebrew -name "$depname" -type f 2>/dev/null | head -n 1)
            if [ -z "$resolved" ] || [ ! -f "$resolved" ]; then
                echo "  WARNING: Cannot find $dep ($depname), skipping"
                continue
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

# Phase 1: Recursively collect all dependencies
echo "=== Phase 1: Collecting dependencies ==="
collect_deps "$DEST/$(basename "$SEED")"

echo ""
echo "=== Phase 2: Rewriting load paths ==="

# Phase 2: Rewrite all load paths to @loader_path/
for lib in "$DEST"/*.dylib; do
    libname="$(basename "$lib")"
    echo "Rewriting: $libname"

    # Fix the library's own install name
    install_name_tool -id "@loader_path/$libname" "$lib" 2>/dev/null || true

    # Get its dependencies and rewrite non-system ones
    deps=$(otool -L "$lib" | tail -n +2 | awk '{print $1}')
    for dep in $deps; do
        if is_system_lib "$dep"; then
            continue
        fi

        depname="$(basename "$dep")"

        # Skip if it is already an @loader_path reference
        case "$dep" in
            @loader_path/*) continue ;;
        esac

        # Only rewrite if we actually have this library
        if [ -f "$DEST/$depname" ]; then
            install_name_tool -change "$dep" "@loader_path/$depname" "$lib" 2>/dev/null || true
        fi
    done
done

echo ""
echo "=== Phase 3: Verification ==="

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
echo "=== Summary ==="
echo "Libraries collected: $(ls "$DEST"/*.dylib | wc -l | tr -d ' ')"
echo "Output directory: $DEST"
ls -lh "$DEST"/*.dylib