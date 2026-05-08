import os
import csv
import shutil

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QMessageBox, QComboBox,
    QGridLayout, QApplication, QSizePolicy, QFileDialog, QCheckBox,
    QColorDialog, QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from display_utils import get_screen_geometry, is_os_junk
from dialogs import show_message, get_text
import theme
from debug_logger import get_logger

logger = get_logger()

SUBJECT_KEY_HEADERS = ["SubjectID", "Key", "MEgroup", "Color"]


class SubjectEditor(QDialog):
    """Dialog for editing subject definitions"""

    def __init__(self, parent, subjects_dir, current_event_keys,
                 config_manager, on_done_callback):
        super().__init__(parent)

        self.subjects_dir = subjects_dir
        self.current_event_keys = current_event_keys
        self.config_manager = config_manager
        self._on_done_cb = on_done_callback

        self.subject_file = None
        self.subjects = [["", "", "", ""] for _ in range(30)]
        self._subject_files = {}
        self._new_dialog_open = False
        self._initializing = False
        self._done_called = False

        self._name_entries = []
        self._key_entries = []
        self._me_group_entries = []
        self._color_buttons = []
        self._subject_colors = [""] * 30
        self._combo = None
        self._deleted_rows = []
        self._undo_delete_btn = None

        self.setWindowTitle("Subject Editor")
        theme.apply_dialog_theme(self)

        self._screen = get_screen_geometry()
        self._editor_w = int(self._screen["width"] * 0.4)
        self._editor_h = int(self._screen["height"] * 0.6)

        self._setup_ui()

        self._initialize_subject_file()

    # UI setup

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
        self._create_subject_entries(content)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        me_row = QHBoxLayout()
        self._all_me_checkbox = QCheckBox(
            "All subjects are mutually exclusive")
        self._all_me_checkbox.setChecked(
            self.config_manager.get_all_subjects_mutually_exclusive())
        self._all_me_checkbox.toggled.connect(self._on_all_me_toggled)
        me_row.addWidget(self._all_me_checkbox)
        me_row.addStretch()
        main_layout.addLayout(me_row)

        main_layout.addWidget(self._create_control_buttons())

        min_w = min(500, int(self._screen["width"] * 0.35))
        min_h = min(400, int(self._screen["height"] * 0.5))
        self.setMinimumSize(min_w, min_h)
        self.resize(self._editor_w, self._editor_h)

    def _create_file_selection(self):
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        label = QLabel("Select Subject File:")
        label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, stretch=1)

        new_btn = QPushButton("New Subject File")
        new_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        new_btn.clicked.connect(self._new_subject_file)
        layout.addWidget(new_btn)

        load_btn = QPushButton("Load Subject File")
        load_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        load_btn.clicked.connect(self._load_subject_file)
        layout.addWidget(load_btn)

        return frame

    def _create_column_headers(self):
        frame = QWidget()
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        for col, (text, width) in enumerate([
            ("Subject", 300), ("Key", 75),
            ("MEgroup", 120), ("Color", 60), ("", 30),
        ]):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight: bold;")
            if width:
                lbl.setFixedWidth(width)
                lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(lbl, 0, col)

        return frame

    def _create_subject_entries(self, parent):
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

            me_entry = QLineEdit()
            me_entry.setFixedWidth(120)
            me_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(me_entry, row, 2)
            self._me_group_entries.append(me_entry)

            color_btn = QPushButton()
            color_btn.setFixedSize(40, 25)
            color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            color_btn.clicked.connect(
                lambda checked, r=row: self._pick_subject_color(r))
            color_btn.setContextMenuPolicy(
                Qt.ContextMenuPolicy.CustomContextMenu)
            color_btn.customContextMenuRequested.connect(
                lambda pos, r=row: self._clear_subject_color(r, pos))
            layout.addWidget(color_btn, row, 3)
            self._color_buttons.append(color_btn)

            delete_btn = QPushButton("x")
            delete_btn.setFixedSize(25, 25)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setStyleSheet(
                "QPushButton { padding: 0px; font-size: 9px;"
                " font-weight: normal; }")
            delete_btn.clicked.connect(
                lambda checked, r=row: self._delete_subject_row(r))
            layout.addWidget(delete_btn, row, 4)

    def _create_control_buttons(self):
        frame = QWidget()
        layout = QHBoxLayout(frame)

        for text, slot in [
            ("Save", self._save_subjects),
            ("Rename", self._rename_subject_file),
            ("Delete", self._delete_subject_file),
            ("Unload Subjects", self._unload_subjects),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        self._undo_delete_btn = QPushButton("Undo Delete")
        self._undo_delete_btn.clicked.connect(self._undo_delete_row)
        self._undo_delete_btn.setEnabled(False)
        layout.addWidget(self._undo_delete_btn)

        layout.addStretch()
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self._on_done)
        done_btn.setStyleSheet("font-weight: bold;")
        layout.addWidget(done_btn)

        return frame

    # Subject file management

    def _initialize_subject_file(self):
        files = self._get_subject_files()
        last_key = self.config_manager.get_last_subject_file()

        if last_key and os.path.exists(
                os.path.join(self.subjects_dir, last_key)):
            self.subject_file = os.path.join(
                self.subjects_dir, last_key)
            self._refresh_combo()
            self._combo.setCurrentText(
                last_key.removesuffix("_subjects.csv"))
            self._load_subjects()
            self._update_entries()
        elif files:
            self.subject_file = os.path.join(
                self.subjects_dir, files[0])
            self._refresh_combo()
            self._combo.setCurrentText(
                files[0].removesuffix("_subjects.csv"))
            self._load_subjects()
            self._update_entries()
        else:
            self._refresh_combo()

    def _get_subject_files(self):
        if not os.path.isdir(self.subjects_dir):
            return []
        files = [f for f in os.listdir(self.subjects_dir)
                 if f.endswith("_subjects.csv") and not is_os_junk(f)]
        self._subject_files = {
            f: os.path.join(self.subjects_dir, f) for f in files}

        last_key = self.config_manager.get_last_subject_file()
        if last_key and last_key in files:
            files.remove(last_key)
            files.insert(0, last_key)
        return files

    def _refresh_combo(self):
        self._combo.blockSignals(True)
        self._combo.clear()
        files = self._get_subject_files()
        if files:
            self._combo.addItems(
                [f.removesuffix("_subjects.csv") for f in files])
        else:
            self._combo.addItem("No file found")
        self._combo.blockSignals(False)

    def _load_subjects(self):
        self._deleted_rows.clear()
        self._update_undo_button()
        if not self.subject_file or not os.path.exists(self.subject_file):
            self.subjects = [["", "", "", ""] for _ in range(30)]
            return True

        if not self._check_file_access(self.subject_file):
            show_message(
                self, "Error",
                "Cannot access subject file.\n"
                "Is it open in another application?")
            self.subjects = [["", "", "", ""] for _ in range(30)]
            return False

        try:
            with open(self.subject_file, "r", newline="",
                       encoding="utf-8-sig") as fh:
                reader = csv.reader(fh)
                self.subjects = []
                first = True
                for row in reader:
                    if first:
                        first = False
                        if row[:len(SUBJECT_KEY_HEADERS)] == SUBJECT_KEY_HEADERS:
                            continue
                    while len(row) < 4:
                        row.append("")
                    self.subjects.append(row[:4])
                while len(self.subjects) < 30:
                    self.subjects.append(["", "", "", ""])
            return True
        except OSError as exc:
            show_message(
                self, "Error", f"Error loading subjects: {exc}")
            self.subjects = [["", "", "", ""] for _ in range(30)]
            return False

    def _update_entries(self):
        for i, subject in enumerate(self.subjects):
            if i >= len(self._name_entries):
                break
            name, key, me_group, color = (subject + [""] * 4)[:4]
            self._name_entries[i].setText(name)
            self._key_entries[i].setText(key)
            self._me_group_entries[i].setText(me_group)
            self._subject_colors[i] = color
            if i < len(self._color_buttons):
                self._update_color_button(i)

    def _on_combo_changed(self, text):
        if text and text != "No file found":
            filename = f"{text}_subjects.csv"
            self.subject_file = os.path.join(
                self.subjects_dir, filename)
            self._load_subjects()
            self._update_entries()
            self.config_manager.set_last_subject_file(filename)

    # File operations

    def _new_subject_file(self):
        if self._new_dialog_open:
            return
        self._new_dialog_open = True

        name, ok = get_text(
            self, "New Subject File",
            "Enter a name for the new Subject file:\n"
            "(Use only letters, numbers, and underscores)")

        if ok and name:
            name = name.strip()
            if not name:
                show_message(
                    self, "No Name Entered",
                    "You must enter a name for the Subject file.")
                self._new_dialog_open = False
                return

            if not name.replace("_", "").isalnum():
                show_message(
                    self, "Invalid Characters",
                    "File name can only contain letters, numbers, "
                    "and underscores.")
                self._new_dialog_open = False
                return

            filename = (f"{name}_subjects.csv"
                        if not name.endswith("_subjects.csv") else name)
            path = os.path.join(self.subjects_dir, filename)

            if not self._check_file_access(path, for_writing=True):
                show_message(
                    self, "Error",
                    "Cannot create subject file.\n"
                    "Check folder permissions or if a file with the "
                    "same name is open.")
                self._new_dialog_open = False
                return

            temp = path + ".tmp"
            try:
                with open(temp, "w", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(SUBJECT_KEY_HEADERS)
                    for _ in range(30):
                        writer.writerow(["", "", "", ""])
                os.replace(temp, path)

                self.subject_file = path
                self._subject_files[filename] = path
                self._refresh_combo()
                self._combo.setCurrentText(name)
                self._load_subjects()
                self._update_entries()
            except OSError as exc:
                _remove_temp(temp)
                show_message(
                    self, "Error", f"Error creating file: {exc}")

        self._new_dialog_open = False

    def _load_subject_file(self):
        """Import an existing subject CSV via a system file dialog"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Subject File", "",
            "Subject Files (*.csv);;All Files (*)")
        if not path:
            return

        basename = os.path.basename(path)
        if not basename.endswith("_subjects.csv"):
            basename = (os.path.splitext(basename)[0]
                        + "_subjects.csv")
        dest = os.path.join(self.subjects_dir, basename)

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

        self.subject_file = dest
        self._refresh_combo()
        self._combo.setCurrentText(
            basename.removesuffix("_subjects.csv"))
        self._load_subjects()
        self._update_entries()
        self.config_manager.set_last_subject_file(basename)

    def _save_subjects(self):
        if (not self.subject_file
                or self._combo.currentText() == "No file found"):
            if not self._create_file_for_save():
                return False

        if not self._check_file_access(
                self.subject_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot save to subject file.\n"
                "Is it open in another application?")
            return False

        temp = self.subject_file + ".tmp"
        try:
            with open(temp, "w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(SUBJECT_KEY_HEADERS)
                for i in range(30):
                    writer.writerow([
                        self._name_entries[i].text(),
                        self._key_entries[i].text(),
                        self._me_group_entries[i].text(),
                        self._subject_colors[i],
                    ])
            os.replace(temp, self.subject_file)
            self.config_manager.set_last_subject_file(
                os.path.basename(self.subject_file))
            return True
        except OSError as exc:
            _remove_temp(temp)
            show_message(
                self, "Error", f"Error saving subjects: {exc}")
            return False

    def _rename_subject_file(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            show_message(
                self, "No Selection",
                "Please select a Subject file to rename.")
            return

        if not self._check_file_access(
                self.subject_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot access the current subject file.\n"
                "Is it open in another application?")
            return

        new_name, ok = get_text(
            self, "Rename Subject File",
            "Enter new name for the Subject file:\n"
            "(Use only letters, numbers, and underscores)",
            text=current)

        if not ok or not new_name:
            return

        new_name = new_name.strip()
        if not new_name:
            show_message(
                self, "No Name Entered",
                "You must enter a name for the Subject file.")
            return

        if not new_name.replace("_", "").isalnum():
            show_message(
                self, "Invalid Characters",
                "File name can only contain letters, numbers, "
                "and underscores.")
            return

        new_filename = f"{new_name}_subjects.csv"
        old_path = self.subject_file
        new_path = os.path.join(self.subjects_dir, new_filename)

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

            self.subject_file = new_path
            self._refresh_combo()
            self._combo.setCurrentText(new_name)
        except OSError as exc:
            _remove_temp(temp)
            show_message(
                self, "Error", f"Failed to rename the file: {exc}")

    def _delete_subject_file(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            show_message(
                self, "No Selection",
                "Please select a Subject file to delete.")
            return

        if not self._check_file_access(
                self.subject_file, for_writing=True):
            show_message(
                self, "Error",
                "Cannot access the subject file for deletion.\n"
                "Is it open in another application?")
            return

        reply = show_message(
            self, "Delete Confirmation",
            f"Are you sure you want to delete '{current}'?",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(self.subject_file)
            files = self._get_subject_files()
            if files:
                self._refresh_combo()
                display = files[0].removesuffix("_subjects.csv")
                self._combo.setCurrentText(display)
                self.subject_file = os.path.join(
                    self.subjects_dir, files[0])
                self._load_subjects()
                self._update_entries()
            else:
                self.subject_file = None
                self._combo.clear()
                self._combo.addItem("No file found")
                self.subjects = [["", "", "", ""] for _ in range(30)]
                self._update_entries()
        except OSError as exc:
            show_message(
                self, "Error", f"Failed to delete the file: {exc}")

    # Done / Back

    def _has_entered_data(self):
        """Return True if the user has entered any subject data."""
        return any(e.text().strip() for e in self._name_entries)

    def _create_file_for_save(self):
        """Prompt for a file name and set self.subject_file without
        clearing entry fields.  Returns True if a file was established."""
        name, ok = get_text(
            self, "Save Subject File",
            "Enter a name for the new Subject file:\n"
            "(Use only letters, numbers, and underscores)")

        if not ok or not name:
            return False

        name = name.strip()
        if not name:
            show_message(
                self, "No Name Entered",
                "You must enter a name for the Subject file.")
            return False

        if not name.replace("_", "").isalnum():
            show_message(
                self, "Invalid Characters",
                "File name can only contain letters, numbers, "
                "and underscores.")
            return False

        filename = (f"{name}_subjects.csv"
                    if not name.endswith("_subjects.csv") else name)
        path = os.path.join(self.subjects_dir, filename)

        if os.path.exists(path):
            reply = show_message(
                self, "File Exists",
                f"'{name}' already exists.\nOverwrite it?",
                icon="question")
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if not self._check_file_access(path, for_writing=True):
            show_message(
                self, "Error",
                "Cannot create subject file.\n"
                "Check folder permissions.")
            return False

        self.subject_file = path
        self._refresh_combo()
        self._combo.setCurrentText(name)
        return True

    def _on_done(self):
        if not self.subject_file or self._combo.currentText() == "No file found":
            if self._has_entered_data():
                if not self._save_subjects():
                    return
            else:
                self._done_called = True
                self._on_done_cb(None)
                self.done(QDialog.DialogCode.Accepted)
                return
        else:
            if not self._save_subjects():
                return

        # Validate hotkeys
        reserved = {",", "."}
        if self.config_manager.get_wasd_navigation():
            reserved.update({"w", "a", "s", "d"})

        assigned = {}
        for i in range(30):
            name = self._name_entries[i].text().strip()
            key = self._key_entries[i].text().strip().lower()
            if not name or not key:
                continue

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
                    f"subjects ('{assigned[key]}' and '{name}').\n"
                    "Please assign unique keys.")
                return

            if key in self.current_event_keys:
                show_message(
                    self, "Shortcut Key Conflict",
                    f"The key '{key}' is already assigned to an event.\n"
                    "Please assign a different key for subject "
                    f"'{name}'.")
                return

            assigned[key] = name

        self.config_manager.set_last_subject_file(
            os.path.basename(self.subject_file))
        self._done_called = True
        self._on_done_cb(self.subject_file)
        self.done(QDialog.DialogCode.Accepted)

    def _unload_subjects(self):
        self._done_called = True
        self._on_done_cb("__unload__")
        self.done(QDialog.DialogCode.Accepted)

    def _on_back(self):
        self._save_subjects()
        self._done_called = True
        self._on_done_cb(None)
        self.done(QDialog.DialogCode.Rejected)

    # Window events

    def closeEvent(self, event):
        event.ignore()
        self._on_closing()

    def _on_closing(self):
        if not self._initializing:
            self._initializing = True
            try:
                self._on_back()
            finally:
                self._initializing = False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_closing()
        else:
            super().keyPressEvent(event)

    def _on_all_me_toggled(self, checked):
        self.config_manager.set_all_subjects_mutually_exclusive(checked)

    # Color management

    def _update_color_button(self, row):
        if row >= len(self._color_buttons):
            return
        btn = self._color_buttons[row]
        color = self._subject_colors[row]
        if color:
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color};"
                f" border: 1px solid #888; }}"
                f"QPushButton:hover {{ border: 2px solid white; }}")
            btn.setToolTip(color)
        else:
            btn.setStyleSheet(
                "QPushButton { background-color: transparent;"
                " border: 1px dashed #666; }"
                "QPushButton:hover { border: 1px dashed white; }")
            btn.setToolTip("Click to set color")

    def _pick_subject_color(self, row):
        initial = (QColor(self._subject_colors[row])
                   if self._subject_colors[row] else QColor("#008080"))
        color = QColorDialog.getColor(initial, self, "Subject Color")
        if color.isValid():
            self._subject_colors[row] = color.name()
            self._update_color_button(row)

    def _clear_subject_color(self, row, pos):
        menu = QMenu(self)
        clear_action = menu.addAction("Clear Color")
        action = menu.exec(
            self._color_buttons[row].mapToGlobal(pos))
        if action == clear_action:
            self._subject_colors[row] = ""
            self._update_color_button(row)

    def _delete_subject_row(self, row):
        """Remove a subject row, shifting rows below it up by one."""
        if row < 0 or row >= len(self._name_entries):
            return
        self._deleted_rows.append({
            "row": row,
            "name": self._name_entries[row].text(),
            "key": self._key_entries[row].text(),
            "me": self._me_group_entries[row].text(),
            "color": self._subject_colors[row],
        })
        self._update_undo_button()
        last = len(self._name_entries) - 1
        for i in range(row, last):
            self._name_entries[i].setText(self._name_entries[i + 1].text())
            self._key_entries[i].setText(self._key_entries[i + 1].text())
            self._me_group_entries[i].setText(
                self._me_group_entries[i + 1].text())
            self._subject_colors[i] = self._subject_colors[i + 1]
            self._update_color_button(i)
        self._name_entries[last].clear()
        self._key_entries[last].clear()
        self._me_group_entries[last].clear()
        self._subject_colors[last] = ""
        self._update_color_button(last)

    def _undo_delete_row(self):
        """Restore the most recently deleted subject row."""
        if not self._deleted_rows:
            return
        rec = self._deleted_rows.pop()
        row = rec["row"]
        last = len(self._name_entries) - 1
        if row > last:
            self._update_undo_button()
            return
        for i in range(last, row, -1):
            self._name_entries[i].setText(
                self._name_entries[i - 1].text())
            self._key_entries[i].setText(
                self._key_entries[i - 1].text())
            self._me_group_entries[i].setText(
                self._me_group_entries[i - 1].text())
            self._subject_colors[i] = self._subject_colors[i - 1]
            self._update_color_button(i)
        self._name_entries[row].setText(rec["name"])
        self._key_entries[row].setText(rec["key"])
        self._me_group_entries[row].setText(rec["me"])
        self._subject_colors[row] = rec["color"]
        self._update_color_button(row)
        self._update_undo_button()

    def _update_undo_button(self):
        if self._undo_delete_btn is not None:
            self._undo_delete_btn.setEnabled(bool(self._deleted_rows))

    # File access helpers

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
    """Silently remove a temporary file if it exists"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
