# migration.py
#
# One-shot upgrades of a project (output) directory written by an
# earlier LASERcoder version.  Each step is versioned; a marker file in
# the project's Session folder records the last step applied so nothing
# runs twice.  (Up to 1.7.x the marker sat in the project root; it is
# moved into Session the first time the project is opened.)
#
# To add a step for a future format change: bump MIGRATION_VERSION,
# add an `if done < N:` block in migrate_output_dir_if_needed, and
# delete steps once every user is past them.
#
# History
#   1  (removed) 1.6 -> 1.7 layout move: Event_Keys/, Subjects/, Resume/,
#      Summary/ into Keys/, Session/, Annotations/Summaries/.  Projects
#      that still have the old layout must be opened once with 1.7.x.
#   2  Multi-subject annotations: one row with "A;B" in Subject becomes
#      one row per subject.  Session state stores the subject file by
#      name instead of an absolute path.

import os
import csv
import json

from debug_logger import get_logger

logger = get_logger()

MIGRATION_VERSION = 2
_MARKER = ".lasercoder_migration"

# Old-layout folders from before step 1; used only to warn.
_PRE_17_DIRS = ("Event_Keys", "Subjects", "Resume", "Summary")


def migrate_output_dir_if_needed(output_dir):
    """Bring *output_dir* up to the current on-disk format.

    Returns True if any file was rewritten (the caller refreshes its
    listings).  Safe to call on every open: after the first run the
    marker short-circuits everything.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return False
    # Backups made by LASERcoder are frozen copies; never rewrite them.
    if os.path.isfile(os.path.join(output_dir, ".no_project")):
        return False

    # A folder with none of the project subfolders holds nothing to
    # migrate.  Nothing is written into it: merely selecting a folder
    # as the project directory must not leave a marker behind.  A root
    # marker left there by an earlier version is removed.
    if not any(os.path.isdir(os.path.join(output_dir, d))
               for d in ("Session", "Annotations") + _PRE_17_DIRS):
        _remove_legacy_marker(output_dir)
        return False

    done = _read_marker(output_dir)
    if done >= MIGRATION_VERSION:
        _relocate_legacy_marker(output_dir, done)
        return False

    if any(os.path.isdir(os.path.join(output_dir, d)) for d in _PRE_17_DIRS):
        logger.warning(
            "Project %s uses the pre-1.7 folder layout, which this "
            "version no longer migrates. Open it once with LASERcoder "
            "1.7.x first.", output_dir)

    changed = False
    if done < 2:
        logger.info("Migrating project to format 2: %s", output_dir)
        changed |= _split_multi_subject_rows(output_dir)
        changed |= _normalise_session_state(output_dir)

    _write_marker(output_dir, MIGRATION_VERSION)
    return changed


# Step 2: one row per subject

def _annotation_files(output_dir):
    """Every annotation CSV LASERcoder maintains: chunk files (the
    working copy), the per-video full files, and combined files."""
    from display_utils import is_os_junk

    session_dir = os.path.join(output_dir, "Session")
    if os.path.isdir(session_dir):
        for video in sorted(os.listdir(session_dir)):
            chunks = os.path.join(session_dir, video, "Chunks")
            if not os.path.isdir(chunks) or is_os_junk(video):
                continue
            for f in sorted(os.listdir(chunks)):
                if f.endswith(".csv") and "_chunk_" in f and not is_os_junk(f):
                    yield os.path.join(chunks, f)

    ann_dir = os.path.join(output_dir, "Annotations")
    if os.path.isdir(ann_dir):
        for f in sorted(os.listdir(ann_dir)):
            if f.endswith("_Annotations.csv") and not is_os_junk(f):
                yield os.path.join(ann_dir, f)
        combined = os.path.join(ann_dir, "Combined_Annotations")
        if os.path.isdir(combined):
            for f in sorted(os.listdir(combined)):
                if f.endswith(".csv") and not is_os_junk(f):
                    yield os.path.join(combined, f)


def _split_multi_subject_rows(output_dir):
    """Rewrite annotation CSVs whose Subject cell holds 'A;B' as one
    row per subject.  Returns True if any file changed."""
    from annotation_store import read_csv_dicts

    changed = False
    for path in _annotation_files(output_dir):
        try:
            rows = read_csv_dicts(path)
        except (OSError, ValueError) as exc:
            logger.warning("Migration: cannot read %s: %s", path, exc)
            continue
        if not rows or not any(";" in (r.get("Subject") or "") for r in rows):
            continue

        out = []
        for row in rows:
            subject = (row.get("Subject") or "").strip()
            parts = [s.strip() for s in subject.split(";") if s.strip()]
            if len(parts) <= 1:
                out.append(row)
                continue
            for s in parts:
                copy = dict(row)
                copy["Subject"] = s
                out.append(copy)

        fieldnames = list(rows[0].keys())
        if _write_csv_atomic(path, fieldnames, out):
            logger.info("Migration: split multi-subject rows in %s "
                        "(%d -> %d rows)", path, len(rows), len(out))
            changed = True
    return changed


def _normalise_session_state(output_dir):
    """Store the subject file by name only (absolute paths broke when a
    project moved between machines).  Returns True if any file changed."""
    from display_utils import is_os_junk

    changed = False
    session_dir = os.path.join(output_dir, "Session")
    if not os.path.isdir(session_dir):
        return False
    for video in sorted(os.listdir(session_dir)):
        if is_os_junk(video):
            continue
        path = os.path.join(session_dir, video, f"{video}_session_state.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning("Migration: cannot read %s: %s", path, exc)
            continue
        stored = data.get("subject_file")
        if not isinstance(stored, str) or not stored:
            continue
        name = os.path.basename(stored.replace("\\", "/"))
        if name == stored:
            continue
        data["subject_file"] = name
        if _write_json_atomic(path, data):
            changed = True
    return changed


# Helpers

def _marker_path(output_dir):
    """The marker lives in Session/, so it travels with the project
    and nothing is added to the project root."""
    return os.path.join(output_dir, "Session", _MARKER)


def _legacy_marker_path(output_dir):
    """Where the marker was kept up to 1.7.x: the project root."""
    return os.path.join(output_dir, _MARKER)


def _read_marker_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return int(fh.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def _read_marker(output_dir):
    return max(_read_marker_file(_marker_path(output_dir)),
               _read_marker_file(_legacy_marker_path(output_dir)))


def _write_marker(output_dir, version):
    """Record *version* in Session/ and drop any root marker.  Returns
    True on success."""
    path = _marker_path(output_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            fh.write(f"{version}\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(path + ".tmp", path)
    except OSError as exc:
        logger.warning("Migration: cannot write marker in %s: %s",
                       output_dir, exc)
        return False
    # Only once the new marker is safely written
    _remove_legacy_marker(output_dir)
    return True


def _remove_legacy_marker(output_dir):
    try:
        os.remove(_legacy_marker_path(output_dir))
    except OSError:
        pass


def _relocate_legacy_marker(output_dir, version):
    """Move a root marker written by an earlier version into Session/."""
    if not os.path.isfile(_legacy_marker_path(output_dir)):
        return
    if _read_marker_file(_marker_path(output_dir)) >= version:
        _remove_legacy_marker(output_dir)
    else:
        _write_marker(output_dir, version)


def _write_csv_atomic(path, fieldnames, rows):
    temp = path + ".tmp"
    try:
        with open(temp, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, path)
        return True
    except OSError as exc:
        logger.warning("Migration: cannot write %s: %s", path, exc)
        try:
            os.remove(temp)
        except OSError:
            pass
        return False


def _write_json_atomic(path, data):
    temp = path + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, path)
        return True
    except OSError as exc:
        logger.warning("Migration: cannot write %s: %s", path, exc)
        try:
            os.remove(temp)
        except OSError:
            pass
        return False
