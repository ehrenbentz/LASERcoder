import os
import csv
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QApplication,
)
from PySide6.QtCore import Qt, QTimer

from config_manager import get_config
from display_utils import center_window
from files_manager import FilesManager
from event_key_editor import EventKeyEditor
import theme


class SetupManager(QDialog):
    """Dialog for managing initial setup of a video annotation session."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager

        self.start_video_flag = False
        self.video_path = None
        self.video_name = ""
        self.event_key_file = None
        self.saved_state = None
        self.start_frame = 0

        self.output_dir = self.config_manager.get_output_dir()
        self.event_key_dir = None
        self.annotations_dir = None
        self.resume_dir = None

        self.annotations_file = ""
        self.session_state_file = ""

        self._event_editor = None
        self._files_manager = None

        self.setWindowTitle("LaserTAG")
        self.setStyleSheet(theme.dialog_stylesheet())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    def setVisible(self, visible):
        """Prevent the SetupManager window from becoming visible.

        On Linux/X11, Qt may attempt to show a parent widget when a
        child modal dialog is exec'd. Since SetupManager is an invisible
        coordinator (all UI lives in child dialogs), suppress any
        attempt to make it visible.
        """
        if visible:
            return
        super().setVisible(False)

    def exec(self):
        """Run the setup flow. The SetupManager itself is never shown;
        all user interaction occurs through child dialogs."""
        self._show_files_manager()
        return self.result()

    # ------------------------------------------------------------------
    # Files manager
    # ------------------------------------------------------------------

    def _show_files_manager(self):
        try:
            if self._event_editor:
                self._event_editor.close()
                self._event_editor = None

            self._files_manager = FilesManager(
                self,
                initial_output_dir=self.config_manager.get_output_dir(),
                initial_video_dir=self.config_manager.get_video_dir(),
            )
            result = self._files_manager.exec()

            if result == QDialog.DialogCode.Accepted:
                fm = self._files_manager
                if fm.output_dir and fm.selected_video_file:
                    self.config_manager.update_output_dir(fm.output_dir)
                    self.config_manager.update_video_dir(
                        fm.selected_video_file)
                    self.output_dir = fm.output_dir
                    self.video_path = fm.selected_video_file
                    self.video_name = Path(self.video_path).stem
                    self._files_manager = None

                    self._init_output_dirs()
                    self._init_file_paths()
                    self._check_existing_session()
                else:
                    QMessageBox.warning(
                        self, "Warning",
                        "No video or output directory selected.")
                    self.done(QDialog.DialogCode.Rejected)
            else:
                self.done(QDialog.DialogCode.Rejected)

        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Error in setup process: {exc}")
            self.done(QDialog.DialogCode.Rejected)

    # ------------------------------------------------------------------
    # Directory and file initialization
    # ------------------------------------------------------------------

    def _init_output_dirs(self):
        try:
            self.event_key_dir = os.path.join(
                self.output_dir, "Event_Keys")
            self.annotations_dir = os.path.join(
                self.output_dir, "Annotations")
            self.resume_dir = os.path.join(self.output_dir, "Resume")
            for d in (self.output_dir, self.event_key_dir,
                      self.annotations_dir, self.resume_dir):
                os.makedirs(d, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Error creating directories: {exc}")
            self.done(QDialog.DialogCode.Rejected)

    def _init_file_paths(self):
        self.annotations_file = os.path.join(
            self.annotations_dir, f"{self.video_name}_Annotations.csv")
        self.session_state_file = os.path.join(
            self.resume_dir, f"{self.video_name}_session_state.json")

    def _create_empty_files(self):
        # Annotations CSV
        temp_ann = self.annotations_file + ".tmp"
        try:
            with open(temp_ann, "w", newline="") as fh:
                csv.writer(fh).writerow([
                    "Video", "Event", "Type", "Mutually_Exclusive",
                    "H_Start", "H_End", "Start", "End", "Duration",
                    "Manual_Edit", "Notes",
                ])
            os.replace(temp_ann, self.annotations_file)
        except (PermissionError, OSError):
            _remove_temp(temp_ann)
            QMessageBox.critical(
                self, "Error",
                "Cannot create annotations file.\n"
                "Is it open in another application?")
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
            with open(temp_state, "w") as fh:
                json.dump(state, fh)
            os.replace(temp_state, self.session_state_file)
        except (PermissionError, OSError):
            _remove_temp(temp_state)
            QMessageBox.critical(
                self, "Error",
                "Cannot create session state file.\n"
                "Is it open in another application?")
            self._show_files_manager()
            return False

        return True

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _check_existing_session(self):
        try:
            if os.path.exists(self.session_state_file):
                try:
                    with open(self.session_state_file, "r") as fh:
                        self.saved_state = json.load(fh)

                    if "timestamp_ms" in self.saved_state:
                        self.saved_state["timestamp_sec"] = (
                            self.saved_state["timestamp_ms"] / 1000.0)

                    if os.path.exists(self.annotations_file):
                        try:
                            with open(self.annotations_file, "r") as fh:
                                fh.read(1)
                        except (PermissionError, OSError):
                            QMessageBox.critical(
                                self, "Error",
                                "Cannot access annotations file.\n"
                                "Is it open in another application?")
                            self._show_files_manager()
                            return

                    self._show_resume_dialog()
                except (PermissionError, OSError):
                    QMessageBox.critical(
                        self, "Error",
                        "Cannot access session state file.\n"
                        "Is it open in another application?")
                    self._show_files_manager()
                except json.JSONDecodeError:
                    QMessageBox.warning(
                        self, "Warning",
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
            QMessageBox.critical(
                self, "Error",
                f"Error checking existing session: {exc}")
            self._show_files_manager()

    def _show_resume_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Resume Session")
        dialog.setWindowFlags(
            dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dialog.setModal(True)
        dialog.setStyleSheet(theme.dialog_stylesheet())
        layout = QVBoxLayout(dialog)

        msg = QLabel(
            f"A previous session was found for {self.video_name}.\n\n"
            "What would you like to do?")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        btn_style = (f"QPushButton {{ padding: 8px 16px; min-width: 100px;"
                     f" background-color: {theme.color('button_bg')};"
                     f" color: {theme.color('button_text')};"
                     f" border: none; border-radius: 4px; }}"
                     f"QPushButton:hover {{ background-color: {theme.color('button_hover')};"
                     f" color: {theme.color('text_on_accent')}; }}"
                     f"QPushButton:pressed {{ background-color: {theme.color('button_pressed')};"
                     f" color: {theme.color('text_on_accent')}; }}")
        btn_row = QHBoxLayout()
        for text, choice in [
            ("Resume", "resume"),
            ("Start Over", "start_over"),
            ("Cancel", "cancel"),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(
                lambda checked, c=choice: self._handle_resume(c, dialog))
            btn_row.addWidget(btn)

        layout.addSpacing(20)
        layout.addLayout(btn_row)

        center_window(dialog, 400, 200)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        dialog.rejected.connect(
            lambda: self._handle_resume("cancel", dialog))
        dialog.exec()

    def _handle_resume(self, choice, dialog):
        try:
            dialog.rejected.disconnect()
        except (TypeError, RuntimeError):
            pass
        dialog.accept()

        if choice == "resume":
            self._resume_session()
        elif choice == "start_over":
            self._confirm_start_over()
        else:
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

    def _confirm_start_over(self):
        reply = QMessageBox.question(
            self, "Confirm Start Over",
            f"Are you sure?\n\nStarting over will delete all current "
            f"annotations for\n{self.video_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply != QMessageBox.StandardButton.Yes:
            self._show_resume_dialog()
            return

        for path in (self.session_state_file, self.annotations_file):
            if os.path.exists(path):
                try:
                    with open(path, "a"):
                        pass
                    os.remove(path)
                except (PermissionError, OSError):
                    QMessageBox.warning(
                        self, "Warning",
                        f"Cannot delete {os.path.basename(path)}.\n"
                        "Is it open in another application?")
                    self._show_resume_dialog()
                    return

        self.start_frame = 0
        self.saved_state = {
            "timestamp_sec": 0.0,
            "coding_start": 0.0,
            "coding_duration": None,
            "coding_end": None,
            "coding_end_reached": False,
            "current_frame": 0,
        }
        if self._create_empty_files():
            self._show_event_key_editor()

    # ------------------------------------------------------------------
    # Event key editor
    # ------------------------------------------------------------------

    def _show_event_key_editor(self):
        try:
            if self._event_editor:
                self._event_editor.close()
                self._event_editor = None

            self._event_editor = EventKeyEditor(
                self,
                self.event_key_dir,
                on_start_video=self._on_start_video,
                on_cancel=self._on_event_key_cancel,
                config_manager=self.config_manager,
            )
            self._event_editor.exec()

            if (self._event_editor
                    and self._event_editor.start_video_flag):
                self.start_video_flag = True
                self.event_key_file = (
                    self._event_editor.event_key_file)
                self._event_editor = None
                self.done(QDialog.DialogCode.Accepted)

        except Exception as exc:
            QMessageBox.critical(
                self, "Error",
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

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            self.start_video_flag = False
            if self.parent():
                QTimer.singleShot(0, self.parent().close)
            else:
                QTimer.singleShot(0, QApplication.quit)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        event.accept()
        if self.parent():
            self.parent().close()
        else:
            QApplication.quit()


def _remove_temp(path):
    """Silently remove a temporary file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
