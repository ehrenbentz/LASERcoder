"""Video lengths for the start dialog's video list.

Lengths are read with a headless mpv instance on a worker thread and
remembered per project in Session/video_lengths.json, so each file is
only opened once.
"""

import json
import locale
import os
import threading

from PySide6.QtCore import QCoreApplication, QThread, Signal

from debug_logger import get_logger

logger = get_logger()

CACHE_FILE = "video_lengths.json"

# Seconds to wait for one file before it is reported as unreadable
_PROBE_TIMEOUT = 5.0

# Every probe that has not finished yet.  Keeps a probe alive after the
# dialog that started it has gone, and lets the application wait for
# stragglers when it quits (a QThread destroyed while running aborts
# the process).
_live_probes = set()
_quit_hooked = False


def _finish_probes_on_quit():
    probes = list(_live_probes)
    for probe in probes:
        probe.stop()
    for probe in probes:
        probe.wait(int((_PROBE_TIMEOUT + 2) * 1000))

# mpv event ids (client API): a file starts loading / playback of a
# file ends (which includes "could not be opened")
_EVENT_START_FILE = 6
_EVENT_END_FILE = 7


def _cache_key(path):
    return os.path.normcase(os.path.abspath(path))


def _file_stamp(path):
    """(size, modification time) used to tell when a file has changed."""
    st = os.stat(path)
    return st.st_size, int(st.st_mtime)


class VideoLengthCache:
    """Lengths of the videos used with one project.

    An entry is valid only while the file's size and modification time
    are unchanged.  With *create_session* the project's Session folder
    is created for the cache file if it is missing; without it the
    cache is only written when that folder already exists.
    """

    def __init__(self, output_dir, create_session=False):
        self.output_dir = output_dir
        self._create_session = create_session
        self._session_dir = (os.path.join(output_dir, "Session")
                             if output_dir else "")
        self._entries = {}
        self._failed = {}   # in memory only, so a bad file is retried
        self._dirty = False
        self._load()

    def _path(self):
        return os.path.join(self._session_dir, CACHE_FILE)

    def _load(self):
        if not self._session_dir:
            return
        try:
            with open(self._path(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            entries = data.get("videos", {})
            if isinstance(entries, dict):
                self._entries = {
                    k: v for k, v in entries.items()
                    if isinstance(v, dict)}
        except (OSError, ValueError, AttributeError):
            self._entries = {}

    def get(self, path):
        """Length in seconds, -1.0 if the file could not be read in
        this run, or None if it has not been probed yet."""
        try:
            size, mtime = _file_stamp(path)
        except OSError:
            return -1.0
        key = _cache_key(path)
        entry = self._entries.get(key)
        if (entry and entry.get("size") == size
                and entry.get("mtime") == mtime):
            try:
                return float(entry["length"])
            except (KeyError, TypeError, ValueError):
                pass
        if self._failed.get(key) == (size, mtime):
            return -1.0
        return None

    def set(self, path, length):
        """Record a probe result (*length* < 0 means unreadable)."""
        try:
            size, mtime = _file_stamp(path)
        except OSError:
            return
        key = _cache_key(path)
        if length is None or length < 0:
            self._failed[key] = (size, mtime)
            return
        self._entries[key] = {
            "size": size, "mtime": mtime, "length": round(length, 3)}
        self._dirty = True

    def save(self):
        """Write the cache atomically.  Returns True if it was written."""
        if not self._dirty or not self._session_dir:
            return False
        if not os.path.isdir(self._session_dir):
            if not (self._create_session
                    and os.path.isdir(self.output_dir)):
                return False
        path = self._path()
        temp = path + ".tmp"
        try:
            os.makedirs(self._session_dir, exist_ok=True)
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump({"videos": self._entries}, fh, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp, path)
            self._dirty = False
            return True
        except OSError as exc:
            logger.warning("Could not save video lengths: %s", exc)
            try:
                os.remove(temp)
            except OSError:
                pass
            return False


def _event_id(event):
    """Numeric id of an mpv event, for old (dict) and new (object)
    python-mpv event formats."""
    try:
        eid = getattr(event, "event_id", None)
        if eid is None and isinstance(event, dict):
            eid = event.get("event_id")
        return int(getattr(eid, "value", eid))
    except (TypeError, ValueError):
        return None


class VideoLengthProbe(QThread):
    """Reads the length of each file in *paths* with headless mpv.

    Emits probed(path, seconds) once per file, in order; seconds is
    negative when the file could not be read.
    """

    probed = Signal(str, float)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self._paths = list(paths)
        self._stop = False
        self._wake = threading.Event()

        global _quit_hooked
        _live_probes.add(self)
        self.finished.connect(lambda: _live_probes.discard(self))
        app = QCoreApplication.instance()
        if app is not None and not _quit_hooked:
            app.aboutToQuit.connect(_finish_probes_on_quit)
            _quit_hooked = True

    def stop(self):
        """Ask the thread to finish after the file it is on."""
        self._stop = True
        self._wake.set()

    def _create_player(self):
        import mpv

        locale.setlocale(locale.LC_NUMERIC, "C")
        try:
            # Nothing is displayed or played: the file is opened paused
            # with null outputs, which is enough for mpv to report its
            # length.
            return mpv.MPV(
                vo="null", ao="null", pause=True, idle=True,
                config=False, ytdl=False, load_scripts=False,
                hwdec="no", audio_display="no", sub_auto="no",
                audio_file_auto="no", input_default_bindings=False,
                input_vo_keyboard=False, terminal=False)
        except Exception as exc:
            logger.debug("mpv probe options rejected (%s); using basic", exc)
            return mpv.MPV(vo="null", ao="null", pause=True, idle=True)

    def run(self):
        try:
            player = self._create_player()
        except Exception as exc:
            logger.warning("Video length probe unavailable: %s", exc)
            for path in self._paths:
                if self._stop:
                    break
                self.probed.emit(path, -1.0)
            return

        # Events arrive in order on mpv's event thread.  A length or an
        # end-of-file is only attributed to the current file once that
        # file's own start event has been seen, so a late event from
        # the previous file can never be mistaken for it.
        state = {"started": False, "length": None}

        def on_event(event):
            eid = _event_id(event)
            if eid == _EVENT_START_FILE:
                state["started"] = True
            elif eid == _EVENT_END_FILE and state["started"]:
                self._wake.set()

        def on_length(_name, value):
            if state["started"] and value is not None and value > 0:
                state["length"] = float(value)
                self._wake.set()

        try:
            player.register_event_callback(on_event)
            player.observe_property("duration", on_length)
            for path in self._paths:
                if self._stop:
                    break
                state["started"] = False
                state["length"] = None
                self._wake.clear()
                try:
                    player.command("loadfile", path, "replace")
                    self._wake.wait(_PROBE_TIMEOUT)
                except Exception as exc:
                    logger.debug("Length probe failed for %s: %s", path, exc)
                if self._stop:
                    break
                length = state["length"]
                self.probed.emit(path, length if length else -1.0)
        finally:
            try:
                player.terminate()
            except Exception:
                pass
