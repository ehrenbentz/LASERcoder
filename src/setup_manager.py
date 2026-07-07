import os
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QApplication,
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal

from config_manager import get_config
from files_manager import FilesManager
from event_key_editor import EventKeyEditor
from dialogs import show_message
from annotation_store import init_annotations_dir


class SetupManager(QObject):
    """Coordinate setup flow"""

    finished = Signal(int)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager

        self.start_video_flag = False
        self.video_path = None
        self.video_name = ""
        self.event_key_file = None
        self.saved_state = None
        self.start_frame = 0
        self.multi_part_files = None
        self.multi_part_video_name = None

        self.output_dir = self.config_manager.get_output_dir()
        self.event_key_dir = None
        self.annotations_dir = None

        self.session_state_file = ""

        self._event_editor = None
        self._files_manager = None

    def start(self):
        """Begin the setup flow by showing the files manager"""
        self._show_files_manager()

    def _finish(self, result):
        """Emit finished signal with result code"""
        self.finished.emit(result)

    # Files manager

    def _show_files_manager(self):
        try:
            if self._event_editor:
                self._event_editor.close()
                self._event_editor = None

            self._files_manager = FilesManager(
                self.parent(),
                initial_output_dir=self.config_manager.get_output_dir(),
                initial_video_dir=self.config_manager.get_video_dir(),
            )

            def _on_files_finished(result):
                if result == QDialog.DialogCode.Accepted:
                    fm = self._files_manager
                    if fm.output_dir and fm.selected_video_file:
                        self.config_manager.update_output_dir(fm.output_dir)
                        if fm.multi_part_files:
                            self.config_manager.config['video_dir'] = (
                                fm.current_video_dir)
                            self.config_manager.save_config()
                        else:
                            self.config_manager.update_video_dir(
                                fm.selected_video_file)
                        self.output_dir = fm.output_dir
                        self.video_path = fm.selected_video_file
                        self.multi_part_files = fm.multi_part_files
                        self.multi_part_video_name = fm.multi_part_video_name
                        if self.multi_part_files:
                            self.video_name = self.multi_part_video_name
                        else:
                            self.video_name = Path(self.video_path).stem
                        self._files_manager = None

                        self._init_output_dirs()
                        self._init_file_paths()
                        self._check_existing_session()
                    else:
                        show_message(
                            self.parent(), "Warning",
                            "No video or output directory selected.")
                        self._finish(QDialog.DialogCode.Rejected)
                else:
                    self._finish(QDialog.DialogCode.Rejected)

            self._files_manager.finished.connect(_on_files_finished)
            self._files_manager.open()

        except Exception as exc:
            show_message(
                self.parent(), "Error", f"Error in setup process: {exc}")
            self._finish(QDialog.DialogCode.Rejected)

    # Directory and file initialization

    def _init_output_dirs(self):
        try:
            self.event_key_dir = os.path.join(
                self.output_dir, "Keys", "Event_Keys")
            self.annotations_dir = os.path.join(
                self.output_dir, "Annotations")
            self.subjects_dir = os.path.join(
                self.output_dir, "Keys", "Subject_Keys")
            self.session_dir = os.path.join(self.output_dir, "Session")
            for d in (self.output_dir, self.event_key_dir,
                      self.annotations_dir, self.subjects_dir,
                      self.session_dir):
                os.makedirs(d, exist_ok=True)

            from debug_logger import get_logger
            dl = get_logger()
            if dl._debug_mode:
                self.debug_dir = os.path.join(self.output_dir, "Debug")
                os.makedirs(self.debug_dir, exist_ok=True)
            dl.switch_to_output_dir(self.output_dir)
        except OSError as exc:
            show_message(
                self.parent(), "Error", f"Error creating directories: {exc}")
            self._finish(QDialog.DialogCode.Rejected)

    def _init_file_paths(self):
        self.video_session_dir = os.path.join(
            self.session_dir, self.video_name)
        self.video_chunks_dir = os.path.join(
            self.video_session_dir, "Chunks")
        self.session_state_file = os.path.join(
            self.video_session_dir,
            f"{self.video_name}_session_state.json")
        self.full_annotations_file = os.path.join(
            self.annotations_dir,
            f"{self.video_name}_Annotations.csv")
        os.makedirs(self.video_chunks_dir, exist_ok=True)

        if self.multi_part_files:
            edl_path = self._write_edl_file()
            if edl_path:
                self.video_path = edl_path
            else:
                self._show_files_manager()
                return

    def _write_edl_file(self):
        missing = [p for p in self.multi_part_files
                   if not os.path.isfile(p)]
        if missing:
            show_message(
                self.parent(), "Missing Files",
                "The following video parts could not be found:\n\n"
                + "\n".join(os.path.basename(p) for p in missing)
                + "\n\nThe multi-part video cannot be loaded.")
            return None
        edl_path = os.path.join(
            self.video_session_dir, f"{self.video_name}.edl")
        with open(edl_path, "w", newline="\n", encoding="utf-8") as f:
            f.write("# mpv EDL v0\n")
            for path in self.multi_part_files:
                # mpv EDL has no percent-decoding; paths containing
                # special characters must use the %<bytelen>%<path>
                # quoting syntax from the EDL spec.
                f.write(f"%{len(path.encode('utf-8'))}%{path}\n")
            f.flush()
            os.fsync(f.fileno())
        return edl_path

    def _create_empty_files(self):
        # Annotations directory (chunked)
        try:
            init_annotations_dir(self.video_chunks_dir, self.video_name)
        except (PermissionError, OSError):
            show_message(
                self.parent(), "Error",
                "Cannot create annotations directory.\n"
                "Check folder permissions.")
            self._show_files_manager()
            return False

        # Session state JSON
        temp_state = self.session_state_file + ".tmp"
        try:
            state = self.saved_state or {
                "timestamp_sec": 0.0,
                "current_frame": 0,
                "coding_start": 0.0,
                "coding_duration": None,
                "coding_end": None,
                "coding_end_reached": False,
            }
            if self.multi_part_files:
                state["multi_part_files"] = self.multi_part_files
            with open(temp_state, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_state, self.session_state_file)
        except (PermissionError, OSError):
            _remove_temp(temp_state)
            show_message(
                self.parent(), "Error",
                "Cannot create session state file.\n"
                "Is it open in another application?")
            self._show_files_manager()
            return False

        return True

    # Session management

    def _check_existing_session(self):
        try:
            if os.path.exists(self.session_state_file):
                try:
                    with open(self.session_state_file, "r",
                              encoding="utf-8") as fh:
                        self.saved_state = json.load(fh)

                    if "timestamp_ms" in self.saved_state:
                        self.saved_state["timestamp_sec"] = (
                            self.saved_state["timestamp_ms"] / 1000.0)

                    if self.saved_state.get("multi_part_files"):
                        self.multi_part_files = (
                            self.saved_state["multi_part_files"])
                        edl_path = self._write_edl_file()
                        if not edl_path:
                            self._show_files_manager()
                            return
                        self.video_path = edl_path

                    ann_exists = (
                        os.path.isdir(self.video_chunks_dir)
                        or os.path.exists(self.full_annotations_file))
                    if ann_exists:
                        try:
                            test_dir = self.video_chunks_dir
                            if os.path.isdir(test_dir):
                                probe = os.path.join(test_dir, ".access_test")
                                with open(probe, "w") as fh:
                                    fh.write("t")
                                os.remove(probe)
                            else:
                                # Binary read: an access probe must not
                                # trip over text decoding.
                                with open(self.full_annotations_file, "rb") as fh:
                                    fh.read(1)
                        except (PermissionError, OSError):
                            show_message(
                                self.parent(), "Error",
                                "Cannot access annotations.\n"
                                "Is the folder or file open in another application?")
                            self._show_files_manager()
                            return

                    self._resume_session()
                except (PermissionError, OSError):
                    show_message(
                        self.parent(), "Error",
                        "Cannot access session state file.\n"
                        "Is it open in another application?")
                    self._show_files_manager()
                except json.JSONDecodeError:
                    show_message(
                        self.parent(), "Warning",
                        "Session state file is corrupted. "
                        "Starting a new session.")
                    if self._create_empty_files():
                        self._show_event_key_editor()
            else:
                self.start_frame = 0
                self.saved_state = None
                if self._create_empty_files():
                    self._show_event_key_editor()
        except Exception as exc:
            show_message(
                self.parent(), "Error",
                f"Error checking existing session: {exc}")
            self._show_files_manager()

    def _resume_session(self):
        if self.saved_state:
            if "current_frame" in self.saved_state:
                self.start_frame = self.saved_state["current_frame"]
            elif "timestamp_ms" in self.saved_state:
                self.start_frame = int(
                    self.saved_state["timestamp_ms"] / 1000.0 * 30)
        else:
            self.start_frame = 0
        self._show_event_key_editor()

    # Event key editor

    def _show_event_key_editor(self):
        try:
            if self._event_editor:
                self._event_editor.close()
                self._event_editor = None

            self._event_editor = EventKeyEditor(
                self.parent(),
                self.event_key_dir,
                on_start_video=self._on_start_video,
                on_cancel=self._on_event_key_cancel,
                config_manager=self.config_manager,
            )

            def _on_editor_finished(_result):
                if (self._event_editor
                        and self._event_editor.start_video_flag):
                    self.start_video_flag = True
                    self.event_key_file = (
                        self._event_editor.event_key_file)
                    self._event_editor = None
                    self._finish(QDialog.DialogCode.Accepted)

            self._event_editor.finished.connect(_on_editor_finished)
            self._event_editor.open()

        except Exception as exc:
            show_message(
                self.parent(), "Error",
                f"Error showing event key editor: {exc}")
            self._event_editor = None
            self._show_files_manager()

    def _on_start_video(self, event_key_file):
        self.event_key_file = event_key_file
        self.start_video_flag = True

    def _on_event_key_cancel(self):
        self._event_editor = None
        self.start_video_flag = False
        self._show_files_manager()


def _remove_temp(path):
    """Silently remove a temporary file if it exists"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
