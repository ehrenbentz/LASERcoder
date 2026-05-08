# annotation_store.py

import os
import csv
import json
import time

from debug_logger import get_logger

logger = get_logger()

EVENT_KEY_HEADERS = ["Event", "Key", "Type", "MEgroup"]

CHUNK_SIZE = 100


class AnnotationStore:
    """
    Handles all annotation data persistence: chunked CSV and json session state.

    Annotations are stored as chunked CSV files in a per-video directory:
        {output_dir}/Annotations/{video_name}/{video_name}_chunk_000.csv

    Legacy single-file format ({video_name}_Annotations.csv) is auto-migrated
    on load.
    """

    CSV_HEADERS = [
        "Video", "Event", "Subject", "Type", "Mutually_Exclusive",
        "H_Start", "H_End", "Start", "End", "Duration",
        "Manual_Edit", "Notes",
    ]

    def __init__(self, video_name, annotations_dir, full_annotations_file,
                 event_key_file, output_dir):
        self.video_name = video_name
        self.annotations_dir = annotations_dir
        self.full_annotations_file = full_annotations_file
        self.event_key_file = event_key_file
        self.output_dir = output_dir

        # File access cache (avoid repeated test-file creation)
        self._access_ok = False
        self._access_checked_at = 0.0

        # Annotation data
        self.state_events = []
        self.point_events = []

        # Event definitions
        self.events = []
        self.state_event_keys = {}   # key -> name
        self.point_event_keys = {}   # key -> name
        self.me_groups = {}         # key -> ME group name
        self.event_map = {}      # key -> {"Event": ..., "Type": ...}


    # Event definitions

    def load_events(self):
        """Read event key CSV and populate lookup structures"""
        logger.info("Loading events from %s", self.event_key_file)
        self.events.clear()
        self.state_event_keys.clear()
        self.point_event_keys.clear()
        self.me_groups.clear()
        self.event_map.clear()

        with open(self.event_key_file, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            first = True
            for row in reader:
                if first:
                    first = False
                    if row[:len(EVENT_KEY_HEADERS)] == EVENT_KEY_HEADERS:
                        continue
                if not row or len(row) < 3:
                    continue
                name = row[0].strip()
                key = row[1].strip().lower()
                btype = row[2].strip().lower()
                me_group = row[3].strip() if len(row) > 3 else ""

                if not name:
                    continue

                # Events without a shortcut key get a synthetic
                # internal key so they remain clickable via buttons
                # but unreachable from the keyboard.
                if not key:
                    key = f"__nokey_{len(self.events)}"

                if btype == "state":
                    self.state_event_keys[key] = name
                    if me_group:
                        self.me_groups[key] = me_group
                elif btype == "point":
                    self.point_event_keys[key] = name

                self.event_map[key] = {"Event": name, "Type": btype.capitalize()}
                self.events.append((name, key, btype, me_group))


    # Chunk management

    def _get_chunk_files(self):
        """Return sorted list of chunk filenames in the annotations dir."""
        if not os.path.isdir(self.annotations_dir):
            return []
        return sorted(
            f for f in os.listdir(self.annotations_dir)
            if f.endswith(".csv") and "_chunk_" in f)

    def _chunk_path(self, filename):
        return os.path.join(self.annotations_dir, filename)

    def _write_chunk_atomic(self, chunk_name, rows, _retries=2):
        """Write a single chunk file atomically (temp + replace).

        Retries on transient I/O errors (e.g. slow USB drives).
        """
        path = self._chunk_path(chunk_name)
        temp = path + ".tmp"
        last_exc = None
        for attempt in range(_retries + 1):
            try:
                with open(temp, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
                os.replace(temp, path)
                return
            except OSError as exc:
                last_exc = exc
                if attempt < _retries:
                    time.sleep(0.1 * (attempt + 1))
        try:
            if os.path.exists(temp):
                os.remove(temp)
        except OSError:
            pass
        raise last_exc


    # Annotation CSV (chunked)

    def load_annotations(self):
        """Load annotations from chunked directory."""
        logger.info("Loading annotations from %s", self.annotations_dir)
        self.state_events.clear()
        self.point_events.clear()

        if is_chunked_annotations_dir(self.annotations_dir):
            for chunk_name in self._get_chunk_files():
                chunk_path = self._chunk_path(chunk_name)
                try:
                    with open(chunk_path, "r", newline="",
                              encoding="utf-8-sig") as f:
                        for row in csv.DictReader(f):
                            self._parse_annotation_row(row)
                except OSError:
                    pass

    def _parse_annotation_row(self, row):
        """Parse one CSV row into state_events or point_events."""
        atype = row.get("Type", "").strip().lower()
        name = row.get("Event", "").strip()
        notes = row.get("Notes", "")
        subject = row.get("Subject", "").strip() or "NA"

        if atype == "state":
            raw_start = row.get("Start", "").strip()
            raw_end = row.get("End", "").strip()
            start_time = (float(raw_start)
                          if raw_start and raw_start != "NA" else None)
            end_time = (float(raw_end)
                        if raw_end and raw_end != "NA" else None)

            self.state_events.append({
                "Event": name,
                "Subject": subject,
                "start_time": start_time,
                "end_time": end_time,
                "Type": "State",
                "Mutually_Exclusive": row.get("Mutually_Exclusive", "False"),
                "Notes": notes,
            })

        elif atype == "point":
            self.point_events.append({
                "Event": name,
                "Subject": subject,
                "time": row.get("H_Start", "").strip(),
                "Manual_Edit": row.get("Manual_Edit", "False"),
                "Notes": notes,
            })

    def append_annotation(self, record):
        """Append a single annotation to the current chunk (atomic).

        Reads the last chunk (~100 rows max), appends the new row, and
        writes back atomically via temp+replace.  Only the last chunk is
        touched — never the full annotation set.
        """
        try:
            record.setdefault("Subject", "NA")
            record.setdefault("Notes", "")

            os.makedirs(self.annotations_dir, exist_ok=True)

            chunks = self._get_chunk_files()

            # Read existing rows from the last chunk
            existing = []
            if chunks:
                last_path = self._chunk_path(chunks[-1])
                if os.path.exists(last_path):
                    with open(last_path, "r", newline="",
                              encoding="utf-8-sig") as f:
                        existing = list(csv.DictReader(f))

            if not chunks or len(existing) >= CHUNK_SIZE:
                # Start a new chunk
                chunk_name = f"{self.video_name}_chunk_{len(chunks):03d}.csv"
                self._write_chunk_atomic(chunk_name, [record])
            else:
                # Append to existing chunk — atomic rewrite of ~100 rows
                existing.append(record)
                self._write_chunk_atomic(chunks[-1], existing)

            return True
        except (PermissionError, OSError):
            return False

    def update_state_event_end(self, event_name, end_time):
        """Update a single started state event's end time in its chunk.

        Scans chunks in reverse (newest first) to find the row with
        matching Event name and End='NA', then rewrites only that chunk.
        Returns True on success.
        """
        try:
            h_end = format_time_human(end_time)
            end_str = format_time_machine(end_time)

            for chunk_name in reversed(self._get_chunk_files()):
                chunk_path = self._chunk_path(chunk_name)
                if not os.path.exists(chunk_path):
                    continue

                with open(chunk_path, "r", newline="",
                          encoding="utf-8-sig") as f:
                    rows = list(csv.DictReader(f))

                for row in rows:
                    end_val = row.get("End", "").strip()
                    if (row.get("Event", "").strip() == event_name
                            and row.get("Type", "").strip().lower() == "state"
                            and (end_val == "NA" or end_val == "")):
                        start_str = row.get("Start", "").strip()
                        try:
                            start_val = float(start_str)
                            dur = end_time - start_val
                        except (ValueError, TypeError):
                            dur = 0
                        row["End"] = end_str
                        row["H_End"] = h_end
                        row["Duration"] = format_time_machine(dur)
                        self._write_chunk_atomic(chunk_name, rows)
                        return True

            return False
        except (PermissionError, OSError):
            return False

    def save_sorted_annotations(self):
        """Rewrite all chunk files from in-memory data."""
        try:
            os.makedirs(self.annotations_dir, exist_ok=True)
            self._write_chunks_from_memory()
            return True
        except (PermissionError, OSError):
            return False

    def import_annotations(self, rows, mode="merge"):
        """Import external annotation rows into this store.

        Args:
            rows: list of CSV row dicts (pre-filtered to this video).
            mode: "merge" (combine, skip duplicates) or "replace" (overwrite).

        Returns:
            (success, imported_count, skipped_count)
        """
        try:
            if mode == "replace":
                self.state_events.clear()
                self.point_events.clear()

            existing_state = set()
            existing_point = set()
            if mode == "merge":
                for evt in self.state_events:
                    existing_state.add(
                        (evt["Event"], evt.get("Subject", "NA"),
                         evt["start_time"]))
                for evt in self.point_events:
                    existing_point.add(
                        (evt["Event"], evt.get("Subject", "NA"),
                         evt["time"]))

            imported = 0
            skipped = 0
            for row in rows:
                s_len = len(self.state_events)
                p_len = len(self.point_events)

                self._parse_annotation_row(row)

                if len(self.state_events) > s_len:
                    evt = self.state_events[-1]
                    key = (evt["Event"], evt.get("Subject", "NA"),
                           evt["start_time"])
                    if mode == "merge" and key in existing_state:
                        self.state_events.pop()
                        skipped += 1
                    else:
                        existing_state.add(key)
                        imported += 1
                elif len(self.point_events) > p_len:
                    evt = self.point_events[-1]
                    key = (evt["Event"], evt.get("Subject", "NA"),
                           evt["time"])
                    if mode == "merge" and key in existing_point:
                        self.point_events.pop()
                        skipped += 1
                    else:
                        existing_point.add(key)
                        imported += 1

            self.state_events.sort(
                key=lambda e: e["start_time"] if e["start_time"] else 0)
            self.point_events.sort(
                key=lambda e: parse_time(e["time"]))

            os.makedirs(self.annotations_dir, exist_ok=True)
            self._write_chunks_from_memory()
            self.write_full_annotations_file()

            return True, imported, skipped
        except (PermissionError, OSError) as exc:
            logger.warning("Import annotations failed: %s", exc)
            return False, 0, 0

    def write_full_annotations_file(self):
        """Write a consolidated CSV of all annotations to the user-facing path.

        Returns True on success, False on failure.
        """
        try:
            all_rows = self._build_all_rows()
            path = self.full_annotations_file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temp = path + ".tmp"
            with open(temp, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for row in all_rows:
                    writer.writerow(row)
            os.replace(temp, path)
            return True
        except (PermissionError, OSError) as exc:
            logger.warning("Failed to write full annotations file: %s", exc)
            return False

    def _write_chunks_from_memory(self):
        """Rebuild all chunk files from state_events + point_events.

        Write order is crash-safe:
          1. Write all new chunk files (atomic temp+replace each).
          2. Delete old chunk files not in the new set.
        """
        all_rows = self._build_all_rows()

        old_files = set(self._get_chunk_files())

        # 1. Write new chunks
        new_files = set()
        if not all_rows:
            first = f"{self.video_name}_chunk_000.csv"
            self._write_chunk_atomic(first, [])
            new_files.add(first)
        else:
            idx = 0
            for i in range(0, len(all_rows), CHUNK_SIZE):
                batch = all_rows[i:i + CHUNK_SIZE]
                name = f"{self.video_name}_chunk_{idx:03d}.csv"
                self._write_chunk_atomic(name, batch)
                new_files.add(name)
                idx += 1

        # 2. Remove old chunk files no longer needed
        for old in old_files - new_files:
            path = self._chunk_path(old)
            try:
                os.remove(path)
            except OSError:
                pass

    def _build_all_rows(self):
        """Format all in-memory annotations as CSV row dicts."""
        rows = []
        for evt in self.state_events:
            start = format_time_machine(evt["start_time"])
            end = (format_time_machine(evt["end_time"])
                   if evt["end_time"] is not None else "NA")
            dur = (format_time_machine(evt["end_time"] - evt["start_time"])
                   if evt["end_time"] is not None else "NA")
            h_start = format_time_human(evt["start_time"])
            h_end = (format_time_human(evt["end_time"])
                     if evt["end_time"] is not None else "NA")
            rows.append({
                "Video": self.video_name,
                "Event": evt["Event"],
                "Subject": evt.get("Subject", "NA"),
                "Type": evt.get("Type", "State"),
                "Mutually_Exclusive": evt.get("Mutually_Exclusive", "False"),
                "H_Start": h_start, "H_End": h_end,
                "Start": start, "End": end, "Duration": dur,
                "Manual_Edit": str(evt.get("Manual_Edit", False)),
                "Notes": evt.get("Notes", ""),
            })
        for evt in self.point_events:
            time_machine = format_time_machine(parse_time(evt["time"]))
            rows.append({
                "Video": self.video_name,
                "Event": evt["Event"],
                "Subject": evt.get("Subject", "NA"),
                "Type": evt.get("Type", "Point"),
                "Mutually_Exclusive": evt.get("Mutually_Exclusive", "False"),
                "H_Start": evt["time"], "H_End": "NA",
                "Start": time_machine, "End": "NA", "Duration": "NA",
                "Manual_Edit": str(evt.get("Manual_Edit", False)),
                "Notes": evt.get("Notes", ""),
            })
        return rows


    # Session state file (shared read/write helper)

    def _session_state_path(self):
        return os.path.join(
            os.path.dirname(self.annotations_dir),
            f"{self.video_name}_session_state.json")

    def _merge_and_write(self, updates):
        """
        Read session state JSON, merge updates, write back with indentation

        """
        path = self._session_state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError, OSError):
                data = {}

        data.update(updates)

        try:
            temp = path + ".tmp"
            with open(temp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(temp, path)
            return True
        except (PermissionError, OSError):
            if os.path.exists(path + ".tmp"):
                try:
                    os.remove(path + ".tmp")
                except OSError:
                    pass
            return False

    def save_session_state(self, current_time, coding_start, coding_duration,
                           coding_end, coding_end_reached,
                           limit_timeline_to_coding=False):
        """
        Persist the current session state to JSON
.
        """
        if current_time is None or current_time < 0:
            return False

        return self._merge_and_write({
            "timestamp_sec": float(current_time),
            "coding_start": coding_start,
            "coding_duration": coding_duration,
            "coding_end": coding_end,
            "coding_end_reached": coding_end_reached,
            "limit_timeline_to_coding": limit_timeline_to_coding,
        })

    def load_session_state(self):
        """Load session state from JSON"""
        path = self._session_state_path()

        if not os.path.exists(path):
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError, OSError):
            return None

        # Normalise old ms-based format
        if "timestamp_ms" in data:
            data["timestamp_sec"] = data.pop("timestamp_ms") / 1000.0

        result = {
            "timestamp_sec": _safe_float(data.get("timestamp_sec"), 0),
            "coding_start": _safe_float(data.get("coding_start"), 0),
            "coding_duration": _safe_float_or_none(data.get("coding_duration")),
            "coding_end": _safe_float_or_none(data.get("coding_end")),
            "coding_end_reached": bool(data.get("coding_end_reached", False)),
            "limit_timeline_to_coding": bool(data.get("limit_timeline_to_coding", False)),
            "completed": bool(data.get("completed", False)),
        }

        # Derive coding_end when absent but start + duration exist
        if result["coding_end"] is None and result["coding_duration"] is not None:
            result["coding_end"] = result["coding_start"] + result["coding_duration"]

        return result

    def mark_completed(self):
        return self._merge_and_write({"completed": True})

    def unmark_completed(self):
        return self._merge_and_write({"completed": False})


    # Visualization settings

    def _read_session_key(self, key, default):
        path = self._session_state_path()
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError, OSError):
            return default
        return data.get(key, default)

    def save_viz_colors(self, color_map):
        """Save event color selections {name: hex_string}"""
        self._merge_and_write({"viz_event_colors": color_map})

    def load_viz_colors(self):
        """Load saved event colors. Returns {name: hex_string} or {}"""
        return self._read_session_key("viz_event_colors", {})

    def save_viz_unchecked(self, unchecked_list):
        """Save list of unchecked event names"""
        self._merge_and_write({"viz_unchecked_events": unchecked_list})

    def load_viz_unchecked(self):
        """Load list of unchecked event names. Returns [] if none"""
        return self._read_session_key("viz_unchecked_events", [])

    def save_video_settings(self, settings):
        """Save per-video display settings (brightness, contrast, etc.)"""
        self._merge_and_write({"video_settings": settings})

    def load_video_settings(self):
        """Load per-video display settings. Returns None if not set"""
        return self._read_session_key("video_settings", None)

    def save_audio_settings(self, settings):
        """Save per-video audio settings (volume, delay, pitch, etc.)"""
        self._merge_and_write({"audio_settings": settings})

    def load_audio_settings(self):
        """Load per-video audio settings. Returns None if not set"""
        return self._read_session_key("audio_settings", None)

    def save_viz_options(self, options):
        """Save visualization option checkboxes {name: bool}"""
        self._merge_and_write({"viz_options": options})

    def load_viz_options(self):
        """Load visualization option checkboxes. Returns {} if none"""
        return self._read_session_key("viz_options", {})

    # Subject tracking

    def save_active_subjects(self, subject_list):
        """Save the list of currently active subject names"""
        self._merge_and_write({"active_subjects": subject_list})

    def load_active_subjects(self):
        """Load the list of active subject names. Returns [] if none"""
        return self._read_session_key("active_subjects", [])

    def save_subject_file(self, subject_file_path):
        """Save the path to the subject file used for this video"""
        self._merge_and_write({"subject_file": subject_file_path})

    def load_subject_file(self):
        """Load the subject file path. Returns None if not set"""
        return self._read_session_key("subject_file", None)


    # File access check

    def check_file_access(self):
        """Return True if the annotations directory can be written to.

        Result is cached for 30 seconds to avoid repeated test-file
        creation on the hot path (each test is 3+ filesystem ops).
        """
        now = time.monotonic()
        if self._access_ok and (now - self._access_checked_at) < 30:
            return True

        try:
            logger.debug("Checking file access: %s", self.annotations_dir)
            parent = os.path.dirname(self.annotations_dir)
            if not os.path.isdir(parent):
                self._access_ok = False
                return False

            os.makedirs(self.annotations_dir, exist_ok=True)
            temp = os.path.join(self.annotations_dir, ".access_test")
            with open(temp, "w") as f:
                f.write("test")
            os.remove(temp)
            self._access_ok = True
            self._access_checked_at = now
            return True
        except (PermissionError, OSError) as exc:
            logger.warning("File access check failed: %s", exc)
            self._access_ok = False
            return False


# Module-level helpers

def is_chunked_annotations_dir(path):
    """Return True if path is a directory containing chunk CSV files."""
    if not os.path.isdir(path):
        return False
    return any(f.endswith(".csv") and "_chunk_" in f
               for f in os.listdir(path))


def read_all_annotation_rows(path):
    """Read all annotation rows from a chunked directory or legacy file.

    Args:
        path: A per-video directory containing chunk CSVs,
              or a legacy single CSV file path.

    Returns:
        List of dicts with CSV_HEADERS keys.
    """
    if is_chunked_annotations_dir(path):
        rows = []
        for fname in sorted(os.listdir(path)):
            if fname.endswith(".csv") and "_chunk_" in fname:
                chunk_path = os.path.join(path, fname)
                try:
                    with open(chunk_path, "r", newline="",
                              encoding="utf-8-sig") as f:
                        rows.extend(csv.DictReader(f))
                except OSError:
                    pass
        return rows
    elif os.path.isfile(path):
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        except OSError:
            pass
    return []


def validate_import_csv(file_path):
    """Validate that an external CSV has the expected annotation headers.

    Returns:
        (rows, video_names, error) — error is None on success.
    """
    try:
        with open(file_path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return [], set(), "The selected file is empty."
    except OSError as exc:
        return [], set(), f"Could not read file: {exc}"

    header_stripped = [h.strip() for h in header]
    expected = set(AnnotationStore.CSV_HEADERS)
    optional = {"Subject"}
    found = set(header_stripped)
    missing = expected - found - optional
    if missing:
        return [], set(), (
            "The selected file does not have the expected annotation format.\n"
            f"Missing columns: {', '.join(sorted(missing))}")

    rows = read_all_annotation_rows(file_path)
    if not rows:
        return [], set(), "The file contains no annotation data."

    if "Subject" not in found:
        for row in rows:
            row.setdefault("Subject", "NA")

    video_names = {row.get("Video", "").strip() for row in rows}
    video_names.discard("")
    if not video_names:
        return [], set(), "No video names found in the Video column."

    return rows, video_names, None


def init_annotations_dir(annotations_dir, video_name):
    """Create an empty chunked annotations directory for a new session."""
    os.makedirs(annotations_dir, exist_ok=True)

    chunk_name = f"{video_name}_chunk_000.csv"
    chunk_path = os.path.join(annotations_dir, chunk_name)
    temp = chunk_path + ".tmp"
    with open(temp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AnnotationStore.CSV_HEADERS)
        writer.writeheader()
    os.replace(temp, chunk_path)


# Module-level time helpers used by AnnotationStore and VideoAnnotator

def format_time_human(elapsed):
    """Format seconds as ``Xm Y.YYs``"""
    minutes, seconds = divmod(float(elapsed), 60)
    return f"{int(minutes)}m{seconds:04.2f}s"


def format_time_machine(elapsed):
    """Format seconds as a decimal string with two decimals"""
    return f"{float(elapsed):.2f}"


def parse_time(time_str):
    """Parse a human-readable time string (``Xm Y.YYs``) into seconds"""
    if "m" in time_str and "s" in time_str:
        m, s = time_str.split("m")
        return int(m) * 60 + float(s.rstrip("s"))
    return float(time_str)


def _safe_float(value, default):
    if value is None or value == "null":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_float_or_none(value):
    if value is None or value == "null":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
