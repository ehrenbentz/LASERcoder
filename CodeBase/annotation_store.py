import os
import csv
import json

from debug_logger import get_logger

logger = get_logger()


class AnnotationStore:
    """
    Handles all annotation data persistence: csv and json session state.

    """

    def __init__(self, video_name, annotations_file, session_state_file,
                 event_key_file, output_dir):
        self.video_name = video_name
        self.annotations_file = annotations_file
        self.session_state_file = session_state_file
        self.event_key_file = event_key_file
        self.output_dir = output_dir

        # Annotation data
        self.state_events = []
        self.point_events = []

        # Behaviour definitions
        self.events = []
        self.state_event_keys = {}   # key -> name
        self.point_event_keys = {}   # key -> name
        self.me_groups = {}         # key -> ME group name
        self.event_map = {}      # key -> {"Event": …, "Type": …}

    CSV_HEADERS = [
        "Video", "Event", "Type", "Mutually_Exclusive",
        "H_Start", "H_End", "Start", "End", "Duration",
        "Manual_Edit", "Notes",
    ]

    # ------------------------------------------------------------------
    # Behaviour definitions
    # ------------------------------------------------------------------

    def load_events(self):
        """Read behaviour key CSV and populate lookup structures."""
        logger.info("Loading events from %s", self.event_key_file)
        self.events.clear()
        self.state_event_keys.clear()
        self.point_event_keys.clear()
        self.me_groups.clear()
        self.event_map.clear()

        with open(self.event_key_file, "r", newline="", encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if not row or len(row) < 3:
                    continue
                name = row[0].strip()
                key = row[1].strip().lower()
                btype = row[2].strip().lower()
                me_group = row[3].strip() if len(row) > 3 else ""

                if not name or not key:
                    continue

                if btype == "state":
                    self.state_event_keys[key] = name
                    if me_group:
                        self.me_groups[key] = me_group
                elif btype == "point":
                    self.point_event_keys[key] = name

                self.event_map[key] = {"Event": name, "Type": btype.capitalize()}
                self.events.append((name, key, btype, me_group))

    # ------------------------------------------------------------------
    # Annotation CSV
    # ------------------------------------------------------------------

    def load_annotations(self):
        """Read annotations CSV into *state_events* and *point_events*."""
        logger.info("Loading annotations from %s", self.annotations_file)
        self.state_events.clear()
        self.point_events.clear()

        if not os.path.exists(self.annotations_file):
            return

        with open(self.annotations_file, "r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                atype = row.get("Type", "").strip().lower()
                name = row.get("Event", "").strip()
                notes = row.get("Notes", "")

                if atype == "state":
                    raw_start = row.get("Start", "").strip()
                    raw_end = row.get("End", "").strip()
                    start_time = float(raw_start) if raw_start and raw_start != "NA" else None
                    end_time = float(raw_end) if raw_end and raw_end != "NA" else None

                    self.state_events.append({
                        "Event": name,
                        "start_time": start_time,
                        "end_time": end_time,
                        "Type": "State",
                        "Mutually_Exclusive": row.get("Mutually_Exclusive", "False"),
                        "Notes": notes,
                    })

                elif atype == "point":
                    self.point_events.append({
                        "Event": name,
                        "time": row.get("H_Start", "").strip(),
                        "Manual_Edit": row.get("Manual_Edit", "False"),
                        "Notes": notes,
                    })

    def append_annotation(self, record):
        """Append a single annotation record to the CSV file.

        """
        try:
            rows = []
            if os.path.exists(self.annotations_file):
                with open(self.annotations_file, "r", newline="", encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        row.setdefault("Notes", "")
                        rows.append(row)

            record.setdefault("Notes", "")
            rows.append(record)

            temp = self.annotations_file + ".tmp"
            with open(temp, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            os.replace(temp, self.annotations_file)
            return True
        except (PermissionError, OSError):
            if os.path.exists(self.annotations_file + ".tmp"):
                try:
                    os.remove(self.annotations_file + ".tmp")
                except OSError:
                    pass
            return False

    def save_sorted_annotations(self):
        """Rewrite the full annotations CSV from in-memory data.

        """
        try:
            temp = self.annotations_file + ".tmp"
            with open(temp, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

                for evt in self.state_events:
                    start = format_time_machine(evt["start_time"])
                    end = format_time_machine(evt["end_time"]) if evt["end_time"] is not None else "NA"
                    dur = format_time_machine(evt["end_time"] - evt["start_time"]) if evt["end_time"] is not None else "NA"
                    h_start = format_time_human(evt["start_time"])
                    h_end = format_time_human(evt["end_time"]) if evt["end_time"] is not None else "NA"
                    writer.writerow([
                        self.video_name,
                        evt["Event"],
                        evt.get("Type", "State"),
                        evt.get("Mutually_Exclusive", "False"),
                        h_start, h_end, start, end, dur,
                        str(evt.get("Manual_Edit", False)),
                        evt.get("Notes", ""),
                    ])

                for evt in self.point_events:
                    time_machine = format_time_machine(parse_time(evt["time"]))
                    writer.writerow([
                        self.video_name,
                        evt["Event"],
                        evt.get("Type", "Point"),
                        evt.get("Mutually_Exclusive", "False"),
                        evt["time"], "NA",
                        time_machine, "NA", "NA",
                        str(evt.get("Manual_Edit", False)),
                        evt.get("Notes", ""),
                    ])

            os.replace(temp, self.annotations_file)
            return True
        except (PermissionError, OSError):
            if os.path.exists(self.annotations_file + ".tmp"):
                try:
                    os.remove(self.annotations_file + ".tmp")
                except OSError:
                    pass
            return False

    # ------------------------------------------------------------------
    # Session state JSON
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Session state file (shared read/write helper)
    # ------------------------------------------------------------------

    def _session_state_path(self):
        return os.path.join(
            self.output_dir, "Resume",
            f"{self.video_name}_session_state.json")

    def _merge_and_write(self, updates):
        """Read session state JSON, merge updates, write back with indentation.

        Returns True on success.
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
                           coding_end, coding_end_reached):
        """Persist the current session state to JSON.

        Returns True on success.
        """
        if current_time is None or current_time <= 0:
            return False

        return self._merge_and_write({
            "timestamp_sec": float(current_time),
            "coding_start": coding_start,
            "coding_duration": coding_duration,
            "coding_end": coding_end,
            "coding_end_reached": coding_end_reached,
        })

    def load_session_state(self):
        """Load session state from JSON."""
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
            "completed": bool(data.get("completed", False)),
        }

        # Derive coding_end when absent but start + duration exist
        if result["coding_end"] is None and result["coding_duration"] is not None:
            result["coding_end"] = result["coding_start"] + result["coding_duration"]

        return result

    def mark_completed(self):
        """Mark the current video as completed in the session state."""
        return self._merge_and_write({"completed": True})

    def unmark_completed(self):
        """Remove the completed mark from the session state."""
        return self._merge_and_write({"completed": False})

    # ------------------------------------------------------------------
    # Visualization settings (stored in the same session state JSON)
    # ------------------------------------------------------------------

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
        """Save event color selections {name: hex_string}."""
        self._merge_and_write({"viz_event_colors": color_map})

    def load_viz_colors(self):
        """Load saved event colors. Returns {name: hex_string} or {}."""
        return self._read_session_key("viz_event_colors", {})

    def save_viz_unchecked(self, unchecked_list):
        """Save list of unchecked event names."""
        self._merge_and_write({"viz_unchecked_events": unchecked_list})

    def load_viz_unchecked(self):
        """Load list of unchecked event names. Returns [] if none."""
        return self._read_session_key("viz_unchecked_events", [])

    def save_video_settings(self, settings):
        """Save per-video display settings (brightness, contrast, etc.)."""
        self._merge_and_write({"video_settings": settings})

    def load_video_settings(self):
        """Load per-video display settings. Returns None if not set."""
        return self._read_session_key("video_settings", None)

    def save_viz_options(self, options):
        """Save visualization option checkboxes {name: bool}."""
        self._merge_and_write({"viz_options": options})

    def load_viz_options(self):
        """Load visualization option checkboxes. Returns {} if none."""
        return self._read_session_key("viz_options", {})

    # ------------------------------------------------------------------
    # File access check
    # ------------------------------------------------------------------

    def check_file_access(self):
        """Return True if the annotations file can be read and written.

        Checks that the parent directory still exists first — on macOS,
        file operations on a disconnected external volume can block
        indefinitely, so we verify the directory is reachable before
        attempting any I/O.
        """
        try:
            logger.debug("Checking file access: %s", self.annotations_file)
            parent = os.path.dirname(self.annotations_file)
            if not os.path.isdir(parent):
                return False
            if os.path.exists(self.annotations_file):
                with open(self.annotations_file, "r", newline="") as f:
                    f.read(1)

            temp = self.annotations_file + ".access_test"
            with open(temp, "w") as f:
                f.write("test")
            os.remove(temp)
            return True
        except (PermissionError, OSError) as exc:
            logger.warning("File access check failed: %s", exc)
            return False


# ======================================================================
# Module-level time helpers (used by AnnotationStore and VideoAnnotator)
# ======================================================================

def format_time_human(elapsed):
    """Format seconds as ``Xm Y.YYs``."""
    minutes, seconds = divmod(float(elapsed), 60)
    return f"{int(minutes)}m{seconds:04.2f}s"


def format_time_machine(elapsed):
    """Format seconds as a decimal string with two decimals."""
    return f"{float(elapsed):.2f}"


def parse_time(time_str):
    """Parse a human-readable time string (``Xm Y.YYs``) into seconds."""
    if "m" in time_str and "s" in time_str:
        m, s = time_str.split("m")
        return int(m) * 60 + float(s.rstrip("s"))
    return float(time_str)


# ======================================================================
# Internal helpers
# ======================================================================

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
