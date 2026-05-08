# migration.py

import os
import csv
import shutil

from debug_logger import get_logger

logger = get_logger()

EVENT_KEY_HEADERS = ["Event", "Key", "Type", "MEgroup"]
SUBJECT_KEY_HEADERS = ["SubjectID", "Key", "MEgroup", "Color"]


def migrate_output_dir_if_needed(output_dir):
    """Migrate an old-layout output directory to the new structure.

    Old layout:
        Event_Keys/, Subjects/, Resume/, Summary/,
        Annotations/{VideoName}/ (chunks), Annotations/{VideoName}_Annotations.csv

    New layout:
        Keys/Event_Keys/, Keys/Subject_Keys/, Session/{VideoName}/,
        Session/{VideoName}/Chunks/, Annotations/Summaries/,
        Annotations/Combined_Annotations/

    Safe: skips files that already exist at the destination, logs warnings
    on failure, never removes non-empty directories.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return False

    headers_migrated = migrate_key_headers_if_needed(output_dir)

    old_event_keys = os.path.join(output_dir, "Event_Keys")
    old_subjects = os.path.join(output_dir, "Subjects")
    old_resume = os.path.join(output_dir, "Resume")
    old_summary = os.path.join(output_dir, "Summary")

    has_old = any(os.path.isdir(d) for d in (
        old_event_keys, old_subjects, old_resume, old_summary))
    if not has_old:
        return headers_migrated

    logger.info("Migrating output directory: %s", output_dir)

    # Keys
    _migrate_dir_contents(
        old_event_keys,
        os.path.join(output_dir, "Keys", "Event_Keys"))
    _migrate_dir_contents(
        old_subjects,
        os.path.join(output_dir, "Keys", "Subject_Keys"))

    # Session state + waveform cache
    if os.path.isdir(old_resume):
        for fname in os.listdir(old_resume):
            src = os.path.join(old_resume, fname)
            if not os.path.isfile(src):
                continue
            if fname.endswith("_session_state.json"):
                video_name = fname.removesuffix("_session_state.json")
                dest_dir = os.path.join(output_dir, "Session", video_name)
                _move_file(src, dest_dir, fname)
            elif fname.endswith(".npy"):
                # Waveform cache — leave in place for fallback.
                # New code will write to Session/{video}/ and fall back
                # to Resume/ if not found.
                pass

    # Annotation chunks
    ann_dir = os.path.join(output_dir, "Annotations")
    if os.path.isdir(ann_dir):
        for name in os.listdir(ann_dir):
            subdir = os.path.join(ann_dir, name)
            if not os.path.isdir(subdir):
                continue
            # Check if this subdirectory contains chunk files
            chunk_files = [
                f for f in os.listdir(subdir)
                if f.endswith(".csv") and "_chunk_" in f]
            if not chunk_files:
                continue
            # Move chunk files to Session/{video_name}/Chunks/
            dest_chunks = os.path.join(
                output_dir, "Session", name, "Chunks")
            for cf in chunk_files:
                _move_file(os.path.join(subdir, cf), dest_chunks, cf)
            # Remove the now-empty annotation subdirectory
            _rmdir_if_empty(subdir)

    # Legacy single-file annotations -> chunks
    if os.path.isdir(ann_dir):
        for fname in os.listdir(ann_dir):
            if not fname.endswith("_Annotations.csv"):
                continue
            src_path = os.path.join(ann_dir, fname)
            if not os.path.isfile(src_path):
                continue
            video_name = fname.removesuffix("_Annotations.csv")
            chunks_dir = os.path.join(
                output_dir, "Session", video_name, "Chunks")
            # Skip if chunks already exist
            if (os.path.isdir(chunks_dir)
                    and any(f.endswith(".csv") and "_chunk_" in f
                            for f in os.listdir(chunks_dir))):
                continue
            # Read legacy CSV, split into chunks
            _split_csv_to_chunks(src_path, video_name, chunks_dir)

    # Summaries
    if os.path.isdir(old_summary):
        old_ind = os.path.join(old_summary, "Individual_summaries")
        old_comb = os.path.join(old_summary, "Combined_summaries")
        old_combined_ann = os.path.join(old_summary, "Combined_Annotations")

        new_summaries = os.path.join(ann_dir, "Summaries")
        _migrate_dir_contents(
            old_ind,
            os.path.join(new_summaries, "Individual_Summaries"))
        _migrate_dir_contents(
            old_comb,
            os.path.join(new_summaries, "Combined_Summaries"))
        _migrate_dir_contents(
            old_combined_ann,
            os.path.join(ann_dir, "Combined_Annotations"))

    # Cleanup empty old directories
    for d in (old_event_keys, old_subjects, old_resume, old_summary):
        _rmdir_if_empty(d)

    logger.info("Migration complete: %s", output_dir)
    return True


def _migrate_dir_contents(src_dir, dest_dir):
    """Move all files from src_dir into dest_dir."""
    if not os.path.isdir(src_dir):
        return
    for fname in os.listdir(src_dir):
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src):
            _move_file(src, dest_dir, fname)
        elif os.path.isdir(src):
            # Recurse for nested directories (e.g. Summary subdirs)
            sub_dest = os.path.join(dest_dir, fname)
            _migrate_dir_contents(src, sub_dest)
            _rmdir_if_empty(src)
    _rmdir_if_empty(src_dir)


def _move_file(src, dest_dir, fname):
    """Move a single file, skipping if destination already exists."""
    dest = os.path.join(dest_dir, fname)
    if os.path.exists(dest):
        return
    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(src, dest)
    except (OSError, shutil.Error) as exc:
        logger.warning("Migration: failed to move %s -> %s: %s",
                       src, dest, exc)


def _split_csv_to_chunks(csv_path, video_name, chunks_dir):
    """Read a legacy single-file CSV and write as chunks."""
    import csv
    from annotation_store import AnnotationStore, CHUNK_SIZE
    try:
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return
        os.makedirs(chunks_dir, exist_ok=True)
        for i in range(0, len(rows), CHUNK_SIZE):
            batch = rows[i:i + CHUNK_SIZE]
            chunk_name = f"{video_name}_chunk_{i // CHUNK_SIZE:03d}.csv"
            path = os.path.join(chunks_dir, chunk_name)
            temp = path + ".tmp"
            with open(temp, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=AnnotationStore.CSV_HEADERS)
                writer.writeheader()
                for row in batch:
                    writer.writerow(row)
            os.replace(temp, path)
        logger.info("Split %s into %d chunks for %s",
                     csv_path, (len(rows) - 1) // CHUNK_SIZE + 1,
                     video_name)
    except Exception as exc:
        logger.warning("Failed to split %s into chunks: %s",
                        csv_path, exc)


def _rmdir_if_empty(path):
    """Remove a directory only if it is empty."""
    try:
        if os.path.isdir(path) and not os.listdir(path):
            os.rmdir(path)
    except OSError:
        pass


def migrate_key_headers_if_needed(output_dir):
    """Prepend header rows to any legacy headerless event/subject key CSVs."""
    if not output_dir or not os.path.isdir(output_dir):
        return False

    changed = False

    events_dir = os.path.join(output_dir, "Keys", "Event_Keys")
    if os.path.isdir(events_dir):
        for fname in os.listdir(events_dir):
            if fname.endswith("_events.csv"):
                path = os.path.join(events_dir, fname)
                if _prepend_header_if_missing(path, EVENT_KEY_HEADERS):
                    changed = True

    subjects_dir = os.path.join(output_dir, "Keys", "Subject_Keys")
    if os.path.isdir(subjects_dir):
        for fname in os.listdir(subjects_dir):
            if fname.endswith("_subjects.csv"):
                path = os.path.join(subjects_dir, fname)
                if _prepend_header_if_missing(path, SUBJECT_KEY_HEADERS):
                    changed = True

    return changed


def _prepend_header_if_missing(path, headers):
    """Prepend a header row to a CSV if it isn't already the first row."""
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
    except OSError as exc:
        logger.warning("Header migration: failed to read %s: %s", path, exc)
        return False

    if rows and rows[0][:len(headers)] == headers:
        return False

    temp = path + ".tmp"
    try:
        with open(temp, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        os.replace(temp, path)
        logger.info("Header migration: prepended header to %s", path)
        return True
    except OSError as exc:
        logger.warning("Header migration: failed to write %s: %s", path, exc)
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            pass
        return False
