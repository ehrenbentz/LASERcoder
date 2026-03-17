import os
import csv

import shutil

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QLineEdit, QRadioButton, QScrollArea, QFrame, QMessageBox, QComboBox,
    QButtonGroup, QGridLayout, QInputDialog, QApplication, QSizePolicy,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer
from display_utils import get_screen_geometry, center_window, is_os_junk
from dialogs import show_message, get_text
import theme

class EventKeyEditor(QDialog):
    """Dialog for editing event key definitions."""

    def __init__(self, parent, event_key_dir, on_start_video, on_cancel,
                 config_manager):
        super().__init__(parent)

        self.event_key_dir = event_key_dir
        self._on_start_video_cb = on_start_video
        self._on_cancel_cb = on_cancel
        self.config_manager = config_manager

        self.event_key_file = None
        self.events = [["", "", "point", ""] for _ in range(30)]
        self._event_key_files = {}
        self._new_dialog_open = False
        self._initializing = False
        self.start_video_flag = False

        self._name_entries = []
        self._key_entries = []
        self._type_groups = []
        self._me_group_entries = []
        self._combo = None

        self.setWindowTitle("Event Key Editor")
        theme.apply_dialog_theme(self)

        self._screen = get_screen_geometry()
        self._editor_w = int(self._screen["width"] * 0.5)
        self._editor_h = int(self._screen["height"] * 0.8)

        self._setup_ui()

        if parent:
            parent.showMaximized()

        self._initialize_event_key()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        main_layout.addWidget(self._create_file_selection())
        main_layout.addWidget(self._create_column_headers())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        content = QWidget()
        self._create_event_entries(content)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        main_layout.addWidget(self._create_control_buttons())

        note = QLabel(
            "Note: 'w', 'a', 's', 'd' are reserved for video navigation. "
            "Do not assign these keys to a event.")
        note.setWordWrap(True)
        main_layout.addWidget(note)

        min_w = min(600, int(self._screen["width"] * 0.45))
        min_h = min(400, int(self._screen["height"] * 0.5))
        self.setMinimumSize(min_w, min_h)
        self.resize(self._editor_w, self._editor_h)

    def _create_file_selection(self):
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        label = QLabel("Select Event Key File:")
        label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, stretch=1)

        new_btn = QPushButton("New Event Key File")
        new_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        new_btn.clicked.connect(self._new_event_key_file)
        layout.addWidget(new_btn)

        load_btn = QPushButton("Load Event Key File")
        load_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        load_btn.clicked.connect(self._load_event_key_file)
        layout.addWidget(load_btn)

        return frame

    def _create_column_headers(self):
        frame = QWidget()
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        for col, (text, width) in enumerate([
            ("Event", 300), ("Key", 75), ("Type", None), ("ME Group", 120),
        ]):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight: bold;")
            if width:
                lbl.setFixedWidth(width)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            else:
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl, 0, col)

        layout.setColumnStretch(2, 1)
        return frame

    def _create_event_entries(self, parent):
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        for row in range(30):
            name_entry = QLineEdit()
            name_entry.setFixedWidth(300)
            name_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            name_entry.setTextMargins(0, 0, 0, 0)
            layout.addWidget(name_entry, row, 0)
            self._name_entries.append(name_entry)

            key_entry = QLineEdit()
            key_entry.setFixedWidth(75)
            key_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(key_entry, row, 1)
            self._key_entries.append(key_entry)

            type_widget = QWidget()
            type_layout = QHBoxLayout(type_widget)
            type_layout.setContentsMargins(0, 0, 0, 0)
            type_layout.setSpacing(5)
            type_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            group = QButtonGroup()
            point_radio = QRadioButton("Point")
            state_radio = QRadioButton("State")
            group.addButton(point_radio)
            group.addButton(state_radio)
            point_radio.setChecked(True)
            type_layout.addWidget(point_radio)
            type_layout.addWidget(state_radio)
            layout.addWidget(type_widget, row, 2)
            self._type_groups.append(group)

            me_entry = QLineEdit()
            me_entry.setFixedWidth(120)
            me_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(me_entry, row, 3)
            self._me_group_entries.append(me_entry)

        layout.setColumnStretch(2, 1)

    def _create_control_buttons(self):
        frame = QWidget()
        layout = QHBoxLayout(frame)

        for text, slot in [
            ("Save", self._save_events),
            ("Rename", self._rename_event_key),
            ("Delete", self._delete_event_key),
            ("Back", self._on_cancel),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch()
        start_btn = QPushButton("Start Video")
        start_btn.clicked.connect(self._start_video)
        start_btn.setStyleSheet("font-weight: bold;")
        layout.addWidget(start_btn)

        return frame

    # ------------------------------------------------------------------
    # Event key file management
    # ------------------------------------------------------------------

    def _initialize_event_key(self):
        files = self._get_event_files()
        last_key = self.config_manager.get_last_event_key()

        if last_key and os.path.exists(
                os.path.join(self.event_key_dir, last_key)):
            self.event_key_file = os.path.join(
                self.event_key_dir, last_key)
            self._refresh_combo()
            self._combo.setCurrentText(
                last_key.replace("_events.csv", ""))
            self._load_events()
            self._update_entries()
        elif files:
            self.event_key_file = os.path.join(
                self.event_key_dir, files[0])
            self._refresh_combo()
            self._combo.setCurrentText(
                files[0].replace("_events.csv", ""))
            self._load_events()
            self._update_entries()
        else:
            # Defer so the editor is fully visible before asking.
            QTimer.singleShot(100, self._prompt_no_event_key)

    def _prompt_no_event_key(self):
        """Show a dialog when no event key files exist."""
        dlg = QDialog(self)
        dlg.setWindowTitle("No Event Key Found")
        theme.apply_dialog_theme(dlg)

        layout = QVBoxLayout(dlg)
        label = QLabel(
            "No event key files were found.\n\n"
            "Would you like to create a new event key\n"
            "or load an existing one?")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create")
        load_btn = QPushButton("Load")
        create_btn.clicked.connect(lambda: dlg.done(1))
        load_btn.clicked.connect(lambda: dlg.done(2))
        btn_row.addWidget(create_btn)
        btn_row.addWidget(load_btn)
        layout.addSpacing(10)
        layout.addLayout(btn_row)

        dlg.resize(340, 180)

        def _on_finished(result):
            dlg.deleteLater()
            if result == 1:
                self._new_event_key_file()
            elif result == 2:
                self._load_event_key_file()

        dlg.finished.connect(_on_finished)
        dlg.open()

    def _load_event_key_file(self):
        """Import an existing event key CSV via a system file dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Event Key File", "",
            "Event Key Files (*.csv);;All Files (*)")
        if not path:
            return

        basename = os.path.basename(path)
        if not basename.endswith("_events.csv"):
            basename = (os.path.splitext(basename)[0]
                        + "_events.csv")
        dest = os.path.join(self.event_key_dir, basename)

        if os.path.exists(dest):
            reply = show_message(
                self, "File Exists",
                f"'{basename}' already exists.\nOverwrite it?",
                icon="question")
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            shutil.copy2(path, dest)
        except OSError as exc:
            show_message(
                self, "Error", f"Failed to copy file: {exc}")
            return

        self.event_key_file = dest
        self._refresh_combo()
        self._combo.setCurrentText(
            basename.replace("_events.csv", ""))
        self._load_events()
        self._update_entries()
        self.config_manager.update_last_event_key(basename)

    def _get_event_files(self):
        files = [f for f in os.listdir(self.event_key_dir)
                 if f.endswith("_events.csv") and not is_os_junk(f)]
        self._event_key_files = {
            f: os.path.join(self.event_key_dir, f) for f in files}

        last_key = self.config_manager.get_last_event_key()
        if last_key and last_key in files:
            files.remove(last_key)
            files.insert(0, last_key)
        return files

    def _refresh_combo(self):
        self._combo.clear()
        files = self._get_event_files()
        if files:
            self._combo.addItems(
                [f.replace("_events.csv", "") for f in files])
        else:
            self._combo.addItem("No file found")

    def _load_events(self):
        if not os.path.exists(self.event_key_file):
            self.events = [["", "", "point", ""] for _ in range(30)]
            return True

        if not self._check_file_access(self.event_key_file):
            show_message(
                self, "Error",
                "Cannot access event key file.\n"
                "Is it open in another application?")
            self.events = [["", "", "point", ""] for _ in range(30)]
            return False

        try:
            with open(self.event_key_file, "r") as fh:
                self.events = []
                for row in csv.reader(fh):
                    while len(row) < 4:
                        row.append("")
                    self.events.append(row)
                while len(self.events) < 30:
                    self.events.append(["", "", "point", ""])
            return True
        except OSError as exc:
            show_message(
                self, "Error", f"Error loading events: {exc}")
            self.events = [["", "", "point", ""] for _ in range(30)]
            return False

    def _update_entries(self):
        for i, event in enumerate(self.events):
            if i >= len(self._name_entries):
                break
            name, key, btype, me_group = (event + [""] * 4)[:4]
            self._name_entries[i].setText(name)
            self._key_entries[i].setText(key)
            radios = self._type_groups[i].buttons()
            if btype == "state":
                radios[1].setChecked(True)
            else:
                radios[0].setChecked(True)
            self._me_group_entries[i].setText(me_group)

    def _on_combo_changed(self, text):
        if text and text != "No file found":
            filename = f"{text}_events.csv"
            self.event_key_file = os.path.join(
                self.event_key_dir, filename)
            self._load_events()
            self._update_entries()
            self.config_manager.update_last_event_key(filename)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_event_key_file(self):
        if self._new_dialog_open:
            return
        self._new_dialog_open = True

        name, ok = get_text(
            self, "New Event Key File",
            "Enter a name for the new Event Key file:\n"
            "(Use only letters, numbers, and underscores)")

        if ok and name:
            name = name.strip()
            if not name:
                show_message(
                    self, "No Name Entered",
                    "You must enter a name for the Event Key file.")
                self._new_dialog_open = False
                return

            if not name.replace("_", "").isalnum():
                show_message(
                    self, "Invalid Characters",
                    "File name can only contain letters, numbers, "
                    "and underscores.")
                self._new_dialog_open = False
                return

            filename = (f"{name}_events.csv"
                        if not name.endswith("_events.csv") else name)
            path = os.path.join(self.event_key_dir, filename)

            if not self._check_file_access(path, for_writing=True):
                show_message(
                    self, "Error",
                    "Cannot create event key file.\n"
                    "Check folder permissions or if a file with the "
                    "same name is open.")
                self._new_dialog_open = False
                return

            temp = path + ".tmp"
            try:
                with open(temp, "w", newline="") as fh:
                    writer = csv.writer(fh)
                    for _ in range(30):
                        writer.writerow(["", "", "point", ""])
                os.replace(temp, path)

                self.event_key_file = path
                self._event_key_files[filename] = path
                self._refresh_combo()
                self._combo.setCurrentText(name)
                self._load_events()
                self._update_entries()
            except OSError as exc:
                _remove_temp(temp)
                show_message(
                    self, "Error", f"Error creating file: {exc}")

        self._new_dialog_open = False

    def _rename_event_key(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            show_message(
                self, "No Selection",
                "Please select a Event Key file to rename.")
            return

        if not self._check_file_access(
                self.event_key_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot access the current event key file.\n"
                "Is it open in another application?")
            return

        new_name, ok = get_text(
            self, "Rename Event Key File",
            "Enter new name for the Event Key file:\n"
            "(Use only letters, numbers, and underscores)",
            text=current)

        if not ok or not new_name:
            return

        new_name = new_name.strip()
        if not new_name:
            show_message(
                self, "No Name Entered",
                "You must enter a name for the Event Key file.")
            return

        if not new_name.replace("_", "").isalnum():
            show_message(
                self, "Invalid Characters",
                "File name can only contain letters, numbers, "
                "and underscores.")
            return

        new_filename = f"{new_name}_events.csv"
        old_path = self.event_key_file
        new_path = os.path.join(self.event_key_dir, new_filename)

        if os.path.exists(new_path):
            show_message(
                self, "File Exists",
                "A file with this name already exists.")
            return

        if not self._check_file_access(new_path, for_writing=True):
            show_message(
                self, "Error",
                "Cannot create file at the new location.\n"
                "Check folder permissions.")
            return

        temp = new_path + ".tmp"
        try:
            with open(old_path, "rb") as src:
                with open(temp, "wb") as dst:
                    dst.write(src.read())
            os.replace(temp, new_path)

            try:
                os.remove(old_path)
            except OSError:
                pass

            self.event_key_file = new_path
            self._refresh_combo()
            self._combo.setCurrentText(new_name)
        except OSError as exc:
            _remove_temp(temp)
            show_message(
                self, "Error", f"Failed to rename the file: {exc}")

    def _delete_event_key(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            show_message(
                self, "No Selection",
                "Please select a Event Key file to delete.")
            return

        if not self._check_file_access(
                self.event_key_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot access the event key file for deletion.\n"
                "Is it open in another application?")
            return

        reply = show_message(
            self, "Delete Confirmation",
            f"Are you sure you want to delete '{current}'?",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(self.event_key_file)
            files = self._get_event_files()
            if files:
                self._refresh_combo()
                display = files[0].replace("_events.csv", "")
                self._combo.setCurrentText(display)
                self.event_key_file = os.path.join(
                    self.event_key_dir, files[0])
                self._load_events()
                self._update_entries()
            else:
                self._combo.clear()
                self._combo.addItem("No file found")
                self._new_event_key_file()
        except OSError as exc:
            show_message(
                self, "Error", f"Failed to delete the file: {exc}")

    def _save_events(self):
        if (not self.event_key_file
                or self._combo.currentText() == "No file found"):
            self._new_event_key_file()
            return False

        if not self._check_file_access(
                self.event_key_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot save to event key file.\n"
                "Is it open in another application?")
            return False

        temp = self.event_key_file + ".tmp"
        try:
            with open(temp, "w", newline="") as fh:
                writer = csv.writer(fh)
                for i in range(30):
                    writer.writerow([
                        self._name_entries[i].text(),
                        self._key_entries[i].text(),
                        ("state"
                         if self._type_groups[i].buttons()[1].isChecked()
                         else "point"),
                        self._me_group_entries[i].text(),
                    ])
            os.replace(temp, self.event_key_file)
            self.config_manager.update_last_event_key(
                os.path.basename(self.event_key_file))
            return True
        except OSError as exc:
            _remove_temp(temp)
            show_message(
                self, "Error", f"Error saving events: {exc}")
            return False

    # ------------------------------------------------------------------
    # Start / cancel
    # ------------------------------------------------------------------

    def _start_video(self):
        if not any(e.text().strip() for e in self._name_entries):
            show_message(
                self, "No Events Defined",
                "Please add events before starting the video.")
            return

        if not self._save_events():
            return

        reserved = {"w", "a", "s", "d"}
        assigned = set()
        for entry in self._key_entries:
            key = entry.text().strip().lower()
            if key:
                if key in reserved:
                    show_message(
                        self, "Invalid Shortcut Key",
                        f"The key '{key}' is reserved for video "
                        "navigation.\nPlease assign a different key.")
                    return
                if key in assigned:
                    show_message(
                        self, "Duplicate Shortcut Key",
                        f"The key '{key}' is assigned to multiple "
                        "events.\nPlease assign unique keys.")
                    return
                assigned.add(key)

        self.config_manager.update_last_event_key(
            os.path.basename(self.event_key_file))
        self.start_video_flag = True
        self._on_start_video_cb(self.event_key_file)
        self.done(QDialog.DialogCode.Accepted)

    def _on_cancel(self):
        current = self._current_events()
        if current != self.events:
            dlg = QMessageBox(self)
            theme.apply_dialog_theme(dlg)
            dlg.setWindowTitle("Unsaved Changes")
            dlg.setText("You have unsaved changes. Save before going back?")
            dlg.setIcon(QMessageBox.Icon.Question)
            dlg.setStandardButtons(
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            dlg.setDefaultButton(QMessageBox.StandardButton.Save)
            def _on_reply(reply):
                dlg.deleteLater()
                if reply == QMessageBox.StandardButton.Save:
                    if not self._save_events():
                        return
                elif reply == QMessageBox.StandardButton.Cancel:
                    return
                self._do_cancel()

            dlg.finished.connect(_on_reply)
            dlg.open()
            return

        self._do_cancel()

    def _do_cancel(self):
        self.start_video_flag = False
        self.hide()
        self.done(QDialog.DialogCode.Rejected)
        self._on_cancel_cb()
        self.deleteLater()

    def _current_events(self):
        result = []
        for i in range(30):
            result.append([
                self._name_entries[i].text(),
                self._key_entries[i].text(),
                ("state"
                 if self._type_groups[i].buttons()[1].isChecked()
                 else "point"),
                self._me_group_entries[i].text(),
            ])
        return result

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        event.ignore()
        self._on_closing()

    def _on_closing(self):
        if not self._initializing:
            self._initializing = True
            try:
                self._on_cancel()
            finally:
                self._initializing = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_closing()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # File access helpers
    # ------------------------------------------------------------------

    def _check_file_access(self, path, for_writing=False):
        try:
            if for_writing:
                if os.path.exists(path):
                    with open(path, "a"):
                        pass
                else:
                    probe = path + ".access_test"
                    try:
                        with open(probe, "w") as fh:
                            fh.write("test")
                        os.remove(probe)
                    except OSError:
                        _remove_temp(probe)
                        return False
            else:
                if os.path.exists(path):
                    with open(path, "r") as fh:
                        fh.read(1)
                else:
                    return False
            return True
        except (PermissionError, OSError):
            return False


def _remove_temp(path):
    """Silently remove a temporary file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
