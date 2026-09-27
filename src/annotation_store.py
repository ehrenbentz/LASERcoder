# annotation_store.py

import io
import os
import re
import csv
import sys
import json
import time
import codecs
import hashlib
from collections import Counter

from debug_logger import get_logger

logger = get_logger()

EVENT_KEY_HEADERS = ["Event", "Key", "Type", "MEgroup"]

CHUNK_SIZE = 100


# Tolerant CSV reading
#
# Files edited in Excel (especially on macOS) come back in shapes the
# strict readers used to choke on: Mac Roman or Windows-1252 bytes
# instead of UTF-8, CR-only or CRLF line endings, ';' or tab delimiters
# in some locales, trailing blank rows, and '~$' lock files sitting next
# to the real file.  Everything that reads a CSV goes through here so a
# reformatted file degrades to "some rows skipped", never to a crash.

def _is_junk_name(name):
    """OS metadata, resource forks and Office lock files."""
    return name.startswith(("._", "~", "."))


def read_csv_text(path):
    """Return the decoded text of a CSV file, trying UTF-8 (with or
    without BOM) first, then the legacy Excel encodings, and finally
    UTF-8 with replacement characters so decoding never fails."""
    with open(path, "rb") as f:
        data = f.read()
    # Any leftover byte-order mark (double BOMs happen) is stripped so
    # the first header cell never comes back as "﻿Video".
    return _decode_csv_bytes(data, path).lstrip("﻿")


def _decode_csv_bytes(data, path):
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if data.startswith(codecs.BOM_UTF8):
        data = data[len(codecs.BOM_UTF8):]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # Mac Roman and Windows-1252 both accept almost any byte, so pick
    # the decoding whose non-ASCII characters are lowercase letters
    # (accents such as é, ü, ñ as they occur in words) rather than
    # symbols or stray capitals: a lowercase accent in one encoding
    # becomes Ž, È, √ or ¿ in the other.  Ties go to the platform's
    # own Excel default.
    legacy = (("mac_roman", "cp1252") if sys.platform == "darwin"
              else ("cp1252", "mac_roman"))
    best, best_score = None, None
    for enc in legacy:
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        score = sum((1 if c.islower() else 0) if c.isalpha() else -1
                    for c in text if ord(c) > 127)
        if best_score is None or score > best_score:
            best, best_score = (enc, text), score
    if best is not None:
        logger.warning("CSV %s is not UTF-8; decoded as %s", path, best[0])
        return best[1]
    logger.warning("CSV %s: undecodable bytes replaced", path)
    return data.decode("utf-8", errors="replace")


def _csv_delimiter(text):
    """Pick the delimiter from the header line: ',' unless ';' or a tab
    clearly dominates (Excel in some locales writes ';')."""
    first = text.split("\n", 1)[0].split("\r", 1)[0]
    counts = {d: first.count(d) for d in (",", ";", "\t")}
    if not any(counts.values()):
        return ","
    return max(counts, key=counts.get)


def read_csv_lists(path):
    """All rows of a CSV as lists of stripped strings (blank rows dropped)."""
    text = read_csv_text(path)
    reader = csv.reader(io.StringIO(text, newline=""),
                        delimiter=_csv_delimiter(text))
    rows = []
    for row in reader:
        cells = [c.strip() for c in row]
        if any(cells):
            rows.append(cells)
    return rows


def read_csv_dicts(path):
    """All data rows of a CSV as dicts keyed by stripped header names.

    Short rows are padded with '' and surplus cells dropped, so callers
    can use row.get(...) freely.  Blank rows are skipped."""
    text = read_csv_text(path)
    reader = csv.DictReader(io.StringIO(text, newline=""),
                            delimiter=_csv_delimiter(text))
    if reader.fieldnames:
        reader.fieldnames = [
            (h or "").strip() for h in reader.fieldnames]
    rows = []
    for row in reader:
        row.pop(None, None)
        clean = {k: ("" if v is None else v)
                 for k, v in row.items() if k}
        if any(str(v).strip() for v in clean.values()):
            rows.append(clean)
    return rows


def _headers_match(row, headers):
    """Case- and whitespace-insensitive header row check."""
    return ([c.strip().lower() for c in row[:len(headers)]]
            == [h.lower() for h in headers])


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

        first = True
        for row in read_csv_lists(self.event_key_file):
            if first:
                first = False
                if _headers_match(row, EVENT_KEY_HEADERS):
                    continue
            if len(row) < 3:
                continue
            name = row[0].strip()
            key = row[1].strip().lower()
            btype = row[2].strip().lower()
            me_group = row[3].strip() if len(row) > 3 else ""

            if not name:
                continue
            if btype not in ("state", "point"):
                logger.warning("Event '%s' has unknown type '%s'; "
                               "treated as point", name, btype)
                btype = "point"

            # Events without a shortcut key get a synthetic
            # internal key so they remain clickable via buttons
            # but unreachable from the keyboard.
            if not key:
                key = f"__nokey_{len(self.events)}"

            if btype == "state":
                self.state_event_keys[key] = name
                if me_group:
                    self.me_groups[key] = me_group
            else:
                self.point_event_keys[key] = name

            self.event_map[key] = {"Event": name, "Type": btype.capitalize()}
            self.events.append((name, key, btype, me_group))


    # Chunk management

    def _get_chunk_files(self):
        """Return chunk filenames sorted by numeric chunk index.

        Numeric sort keeps ordering correct past 999 chunks, where a
        plain lexicographic sort would place chunk_1000 before chunk_101.
        """
        if not os.path.isdir(self.annotations_dir):
            return []
        return sorted(
            (f for f in os.listdir(self.annotations_dir)
             if f.endswith(".csv") and "_chunk_" in f
             and not _is_junk_name(f)),
            key=lambda f: (_chunk_index(f), f))

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
                with open(temp, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(row)
                    f.flush()
                    os.fsync(f.fileno())
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
                    rows = read_csv_dicts(chunk_path)
                except OSError as exc:
                    logger.warning("Cannot read chunk %s: %s", chunk_path, exc)
                    continue
                for row in rows:
                    try:
                        self._parse_annotation_row(row)
                    except Exception as exc:  # one bad row must not sink the load
                        logger.warning("Skipping unreadable annotation row "
                                       "in %s: %s (%s)", chunk_name, row, exc)

    def _parse_annotation_row(self, row):
        """Parse one CSV row into state_events or point_events.

        Tolerates Excel edits: times are taken from the machine columns
        when they parse, else from the human-readable columns; rows with
        no usable event name or (for points) no usable time are skipped.
        """
        atype = row.get("Type", "").strip().lower()
        name = row.get("Event", "").strip()
        if not name:
            return
        notes = row.get("Notes", "")
        subject = row.get("Subject", "").strip() or "NA"

        if not atype:
            # Type column lost: a row with an End or Duration is a state
            end_cell = row.get("End", "").strip()
            dur_cell = row.get("Duration", "").strip()
            atype = ("state" if (end_cell and end_cell != "NA")
                     or (dur_cell and dur_cell != "NA") else "point")

        if atype == "state":
            start_time = _time_from_cells(row.get("Start"), row.get("H_Start"))
            end_time = _time_from_cells(row.get("End"), row.get("H_End"))

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
            human = row.get("H_Start", "").strip()
            seconds = _time_from_cells(row.get("Start"), human)
            if seconds is None:
                logger.warning("Point row without a usable time skipped: %s", row)
                return
            try:
                parse_time(human)
            except (ValueError, TypeError):
                human = format_time_human(seconds)
            self.point_events.append({
                "Event": name,
                "Subject": subject,
                "time": human,
                "Manual_Edit": row.get("Manual_Edit", "False"),
                "Notes": notes,
            })

    def append_annotation(self, record):
        """Append a single annotation to the current chunk (atomic)."""
        return self.append_annotations([record])

    def append_annotations(self, records):
        """Append one or more annotations to the current chunk (atomic).

        Reads the last chunk (~100 rows max), appends the new rows, and
        writes back atomically via temp+replace.  Only the last chunk
        (plus any new chunks the rows spill into) is touched — never the
        full annotation set.  All rows are written in one pass so a
        multi-subject annotation lands on disk together.
        """
        try:
            records = list(records)
            if not records:
                return True
            for record in records:
                record.setdefault("Subject", "NA")
                record.setdefault("Notes", "")

            os.makedirs(self.annotations_dir, exist_ok=True)

            chunks = self._get_chunk_files()

            # Read existing rows from the last chunk
            existing = []
            chunk_name = None
            if chunks:
                chunk_name = chunks[-1]
                last_path = self._chunk_path(chunk_name)
                if os.path.exists(last_path):
                    existing = read_csv_dicts(last_path)

            # Next index for any new chunk (max existing index + 1,
            # robust against gaps left by deleted chunks)
            next_idx = (_chunk_index(chunks[-1]) + 1) if chunks else 0

            pending = list(records)
            if chunk_name is not None and len(existing) < CHUNK_SIZE:
                # Fill the current chunk first — atomic rewrite of ~100 rows
                room = CHUNK_SIZE - len(existing)
                existing.extend(pending[:room])
                pending = pending[room:]
                self._write_chunk_atomic(chunk_name, existing)

            while pending:
                batch, pending = pending[:CHUNK_SIZE], pending[CHUNK_SIZE:]
                new_name = f"{self.video_name}_chunk_{next_idx:03d}.csv"
                self._write_chunk_atomic(new_name, batch)
                next_idx += 1

            return True
        except (PermissionError, OSError, ValueError):
            # ValueError covers UnicodeEncodeError so encoding surprises
            # surface through the write-error UI instead of crashing.
            return False

    def update_state_event_end(self, event_name, end_time, subject=None):
        """Close a single started state event row (see
        :meth:`update_state_event_ends`)."""
        return self.update_state_event_ends(
            event_name, end_time, [subject] if subject is not None else None)

    def update_state_event_ends(self, event_name, end_time, subjects=None):
        """Set the end time on open state rows for *event_name*.

        One row is closed per entry in *subjects* (a state started with
        several active subjects is stored as one row per subject).  For
        each subject, a row whose Subject matches is preferred; if none
        exists anywhere, the search falls back to any still-open row for
        the event (open rows from older sessions may predate subject
        tracking).  When *subjects* is None or empty a single row is
        closed by event name alone.

        Chunks are scanned newest-first and each touched chunk is
        rewritten once.  Returns True if every requested row was found.
        """
        try:
            h_end = format_time_human(end_time)
            end_str = format_time_machine(end_time)
            wanted = list(subjects) if subjects else [None]

            chunk_names = list(reversed(self._get_chunk_files()))
            loaded = {}     # chunk_name -> rows
            claimed = set() # (chunk_name, row index) already closed here
            dirty = set()

            def rows_for(name):
                if name not in loaded:
                    path = self._chunk_path(name)
                    loaded[name] = (read_csv_dicts(path)
                                    if os.path.exists(path) else [])
                return loaded[name]

            def find_open_row(want_subject):
                for name in chunk_names:
                    for idx, row in enumerate(rows_for(name)):
                        if (name, idx) in claimed:
                            continue
                        end_val = row.get("End", "").strip()
                        if not (row.get("Event", "").strip() == event_name
                                and row.get("Type", "").strip().lower() == "state"
                                and (end_val == "NA" or end_val == "")):
                            continue
                        if (want_subject is not None
                                and row.get("Subject", "").strip() != want_subject):
                            continue
                        return name, idx
                return None

            all_found = True
            for subj in wanted:
                hit = find_open_row(subj)
                if hit is None and subj is not None:
                    hit = find_open_row(None)
                if hit is None:
                    all_found = False
                    continue
                name, idx = hit
                row = loaded[name][idx]
                try:
                    dur = end_time - float(row.get("Start", "").strip())
                except (ValueError, TypeError):
                    dur = 0
                row["End"] = end_str
                row["H_End"] = h_end
                row["Duration"] = format_time_machine(dur)
                claimed.add(hit)
                dirty.add(name)

            for name in dirty:
                self._write_chunk_atomic(name, loaded[name])

            return all_found
        except (PermissionError, OSError, ValueError):
            return False

    def save_sorted_annotations(self):
        """Rewrite all chunk files from in-memory data."""
        try:
            os.makedirs(self.annotations_dir, exist_ok=True)
            self._write_chunks_from_memory()
            return True
        except (PermissionError, OSError, ValueError):
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
        except (PermissionError, OSError, ValueError) as exc:
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
            with open(temp, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for row in all_rows:
                    writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
            # Remember what we wrote so a later edit of this file in
            # another program can be recognised (see
            # detect_full_file_changes).
            self._merge_and_write({"full_file_hash": _file_fingerprint(path)})
            return True
        except (PermissionError, OSError, ValueError) as exc:
            logger.warning("Failed to write full annotations file: %s", exc)
            return False

    # External edits of the full annotations file

    def _parse_rows_to_lists(self, rows):
        """Parse CSV row dicts into (state_events, point_events) without
        touching this store's own lists."""
        saved = (self.state_events, self.point_events)
        self.state_events, self.point_events = [], []
        try:
            for row in rows:
                try:
                    self._parse_annotation_row(row)
                except Exception as exc:
                    logger.warning("Skipping unreadable row %s: %s", row, exc)
            return self.state_events, self.point_events
        finally:
            self.state_events, self.point_events = saved

    def detect_full_file_changes(self):
        """Report edits made to the full annotations file outside LASERcoder.

        The file is normally a mirror of the chunk files (the working
        copy).  If its content no longer matches what LASERcoder last
        wrote, the two are compared annotation by annotation.  Returns
        None when there is nothing to reconcile (no file, unchanged, or
        only formatting differs), else a dict with:
            added / removed: lists of annotation keys (see
                             annotation_key) present in only one side
            file_state / file_point: the file's parsed annotations,
                             ready for apply_external_annotations()
        """
        path = self.full_annotations_file
        if not path or not os.path.isfile(path):
            return None

        current = _file_fingerprint(path)
        stored = self._read_session_key("full_file_hash", None)
        if stored is not None and stored == current:
            return None
        if stored is None:
            # Sessions from before fingerprinting: only consider the
            # file edited if it is newer than every chunk (a crash before
            # the debounced full-file write leaves it *older*).
            try:
                chunk_mtime = max(
                    (os.path.getmtime(self._chunk_path(c))
                     for c in self._get_chunk_files()), default=0.0)
                if os.path.getmtime(path) <= chunk_mtime + 1.0:
                    return None
            except OSError:
                return None

        try:
            rows = read_csv_dicts(path)
        except (OSError, ValueError) as exc:
            logger.warning("Cannot read %s for comparison: %s", path, exc)
            return None
        file_state, file_point = self._parse_rows_to_lists(rows)

        mine = Counter(annotation_key(e) for e in self.state_events)
        mine.update(annotation_key(e) for e in self.point_events)
        theirs = Counter(annotation_key(e) for e in file_state)
        theirs.update(annotation_key(e) for e in file_point)
        added = sorted((theirs - mine).elements(), key=_key_sort)
        removed = sorted((mine - theirs).elements(), key=_key_sort)
        if not added and not removed:
            return None
        return {
            "added": added,
            "removed": removed,
            "file_state": file_state,
            "file_point": file_point,
        }

    def apply_external_annotations(self, file_state, file_point):
        """Replace the working copy with annotations from the full file."""
        try:
            self.state_events = sorted(
                file_state,
                key=lambda e: e["start_time"] if e["start_time"] is not None else 0)
            self.point_events = sorted(
                file_point, key=lambda e: _safe_parse_time(e["time"]))
            os.makedirs(self.annotations_dir, exist_ok=True)
            self._write_chunks_from_memory()
            return self.write_full_annotations_file()
        except (PermissionError, OSError, ValueError) as exc:
            logger.warning("Applying external annotations failed: %s", exc)
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
            st = evt["start_time"]
            et = evt["end_time"]
            # An imported row can lack a Start; keep it as NA rather
            # than crashing every subsequent rewrite with float(None).
            start = format_time_machine(st) if st is not None else "NA"
            end = format_time_machine(et) if et is not None else "NA"
            dur = (format_time_machine(et - st)
                   if et is not None and st is not None else "NA")
            h_start = format_time_human(st) if st is not None else "NA"
            h_end = format_time_human(et) if et is not None else "NA"
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

        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError, OSError):
                data = {}

        data.update(updates)

        try:
            # Inside the guard: a detached output drive raises here, and
            # an escaping exception would kill the auto-save timer chain.
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temp = path + ".tmp"
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
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
            with open(path, "r", encoding="utf-8") as f:
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
            with open(path, "r", encoding="utf-8") as f:
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
        """Remember the subject file used for this video.

        Only the file name is stored: subject files live in
        Keys/Subject_Keys under the output directory, and an absolute
        path would break as soon as the project moved to another
        machine or operating system."""
        name = (os.path.basename(str(subject_file_path).replace("\\", "/"))
                if subject_file_path else None)
        self._merge_and_write({"subject_file": name})

    def load_subject_file(self):
        """Resolve the remembered subject file to an existing path.

        Accepts the bare file name written by current versions and the
        absolute path written by older ones; both are looked up in the
        project's Keys/Subject_Keys folder first so a moved project
        still finds its subjects.  Returns None if nothing exists."""
        stored = self._read_session_key("subject_file", None)
        if not stored:
            return None
        name = os.path.basename(stored.replace("\\", "/"))
        candidates = [os.path.join(self.output_dir, "Keys", "Subject_Keys", name)]
        if os.path.isabs(stored):
            candidates.append(stored)
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None


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

def _file_fingerprint(path):
    """SHA-1 of a file's bytes, or None if unreadable."""
    try:
        h = hashlib.sha1()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 16), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _safe_parse_time(value):
    try:
        return parse_time(value)
    except (ValueError, TypeError):
        return 0.0


def annotation_key(evt):
    """Comparable identity of an in-memory annotation, tolerant of the
    formatting differences a spreadsheet round-trip introduces."""
    notes = (evt.get("Notes") or "").strip()
    subject = (evt.get("Subject") or "NA").strip() or "NA"
    if "start_time" in evt:
        st = evt.get("start_time")
        et = evt.get("end_time")
        return ("State", evt.get("Event", "").strip(), subject,
                round(st, 2) if st is not None else None,
                round(et, 2) if et is not None else None, notes)
    return ("Point", evt.get("Event", "").strip(), subject,
            round(_safe_parse_time(evt.get("time")), 2), None, notes)


def _key_sort(key):
    return (key[3] if key[3] is not None else -1, key[0], key[1], key[2])


def describe_annotation_key(key):
    """One-line human description of an annotation_key tuple."""
    kind, event, subject, start, end, notes = key
    who = f" [{subject}]" if subject and subject != "NA" else ""
    if kind == "State":
        span = (f"{format_time_human(start)} – "
                f"{format_time_human(end) if end is not None else 'open'}"
                if start is not None else "no start time")
    else:
        span = format_time_human(start or 0)
    text = f"{event}{who}  {span}"
    if notes:
        text += f"  ({notes[:30]}{'…' if len(notes) > 30 else ''})"
    return text


def _chunk_index(fname):
    """Extract the numeric chunk index from a chunk filename (-1 if none)."""
    m = re.search(r"_chunk_(\d+)\.csv$", fname)
    return int(m.group(1)) if m else -1


def is_chunked_annotations_dir(path):
    """Return True if path is a directory containing chunk CSV files."""
    if not os.path.isdir(path):
        return False
    return any(f.endswith(".csv") and "_chunk_" in f and not _is_junk_name(f)
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
        names = [f for f in os.listdir(path)
                 if f.endswith(".csv") and "_chunk_" in f
                 and not _is_junk_name(f)]
        for fname in sorted(names, key=lambda f: (_chunk_index(f), f)):
            chunk_path = os.path.join(path, fname)
            try:
                rows.extend(read_csv_dicts(chunk_path))
            except OSError as exc:
                logger.warning("Cannot read %s: %s", chunk_path, exc)
        return rows
    elif os.path.isfile(path):
        try:
            return read_csv_dicts(path)
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
    return []


def validate_import_csv(file_path):
    """Validate that an external CSV has the expected annotation headers.

    Returns:
        (rows, video_names, error) — error is None on success.
    """
    try:
        lists = read_csv_lists(file_path)
    except OSError as exc:
        return [], set(), f"Could not read file: {exc}"
    if not lists:
        return [], set(), "The selected file is empty."
    header = lists[0]

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
    with open(temp, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=AnnotationStore.CSV_HEADERS)
        writer.writeheader()
        f.flush()
        os.fsync(f.fileno())
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
    """Parse a human-readable time string (``Xm Y.YYs``) into seconds.

    Raises ValueError for anything unparsable (including ``NA``).
    """
    if time_str is None:
        raise ValueError("no time")
    s = str(time_str).strip()
    if "m" in s and "s" in s:
        m, sec = s.split("m", 1)
        return int(m.strip() or 0) * 60 + float(sec.strip().rstrip("s").strip())
    return float(s)


def _time_from_cells(machine, human):
    """Seconds from a Start/End cell, falling back to the H_Start/H_End
    cell.  Returns None when neither parses (``NA``, blank, or a value
    Excel reformatted beyond recognition)."""
    for raw in (machine, human):
        if raw is None:
            continue
        s = str(raw).strip()
        if not s or s.upper() == "NA":
            continue
        try:
            return float(s)
        except ValueError:
            pass
        try:
            return parse_time(s)
        except (ValueError, TypeError):
            pass
        # European-locale decimal comma ("12,5")
        if "," in s and "." not in s:
            try:
                return float(s.replace(",", "."))
            except ValueError:
                pass
    return None


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
