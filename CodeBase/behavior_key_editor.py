import os
import csv

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton,
    QLineEdit, QRadioButton, QScrollArea, QFrame, QMessageBox, QComboBox,
    QButtonGroup, QGridLayout, QInputDialog, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt
from display_utils import get_screen_geometry, center_window
import theme

class BehaviorKeyEditor(QDialog):
    """Dialog for editing behavior key definitions."""

    def __init__(self, parent, behavior_key_dir, on_start_video, on_cancel,
                 config_manager):
        super().__init__(parent)

        self.behavior_key_dir = behavior_key_dir
        self._on_start_video_cb = on_start_video
        self._on_cancel_cb = on_cancel
        self.config_manager = config_manager

        self.behavior_key_file = None
        self.behaviors = [["", "", "point", ""] for _ in range(30)]
        self._behavior_key_files = {}
        self._new_dialog_open = False
        self._initializing = False
        self.start_video_flag = False

        self._name_entries = []
        self._key_entries = []
        self._type_groups = []
        self._me_group_entries = []
        self._combo = None

        self.setWindowTitle("Behavior Key Editor")
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(theme.dialog_stylesheet())

        self._screen = get_screen_geometry()
        self._editor_w = int(self._screen["width"] * 0.5)
        self._editor_h = int(self._screen["height"] * 0.8)

        self._setup_ui()
        self._initialize_behavior_key()

        if parent:
            parent.showMaximized()

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
        self._create_behavior_entries(content)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        main_layout.addWidget(self._create_control_buttons())

        note = QLabel(
            "Note: 'w', 'a', 's', 'd' are reserved for video navigation. "
            "Do not assign these keys to a behavior.")
        note.setWordWrap(True)
        main_layout.addWidget(note)

        min_w = min(600, int(self._screen["width"] * 0.45))
        min_h = min(400, int(self._screen["height"] * 0.5))
        self.setMinimumSize(min_w, min_h)
        self.resize(self._editor_w, self._editor_h)
        center_window(self, self._editor_w, self._editor_h, self._screen)

    def _create_file_selection(self):
        frame = QWidget()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        label = QLabel("Select Behavior Key File:")
        label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo, stretch=1)

        new_btn = QPushButton("New Behavior Key File")
        new_btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        new_btn.clicked.connect(self._new_behavior_key_file)
        layout.addWidget(new_btn)

        return frame

    def _create_column_headers(self):
        frame = QWidget()
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)

        for col, (text, width) in enumerate([
            ("Behavior", 300), ("Key", 75), ("Type", None), ("ME Group", 120),
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

    def _create_behavior_entries(self, parent):
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
            ("Save", self._save_behaviors),
            ("Rename", self._rename_behavior_key),
            ("Delete", self._delete_behavior_key),
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
    # Behavior key file management
    # ------------------------------------------------------------------

    def _initialize_behavior_key(self):
        files = self._get_behavior_files()
        last_key = self.config_manager.get_last_behavior_key()

        if last_key and os.path.exists(
                os.path.join(self.behavior_key_dir, last_key)):
            self.behavior_key_file = os.path.join(
                self.behavior_key_dir, last_key)
            self._refresh_combo()
            self._combo.setCurrentText(
                last_key.replace("_behaviors.csv", ""))
            self._load_behaviors()
            self._update_entries()
        elif files:
            self.behavior_key_file = os.path.join(
                self.behavior_key_dir, files[0])
            self._refresh_combo()
            self._combo.setCurrentText(
                files[0].replace("_behaviors.csv", ""))
            self._load_behaviors()
            self._update_entries()
        else:
            self._new_behavior_key_file()

    def _get_behavior_files(self):
        files = [f for f in os.listdir(self.behavior_key_dir)
                 if f.endswith("_behaviors.csv")]
        self._behavior_key_files = {
            f: os.path.join(self.behavior_key_dir, f) for f in files}

        last_key = self.config_manager.get_last_behavior_key()
        if last_key and last_key in files:
            files.remove(last_key)
            files.insert(0, last_key)
        return files

    def _refresh_combo(self):
        self._combo.clear()
        files = self._get_behavior_files()
        if files:
            self._combo.addItems(
                [f.replace("_behaviors.csv", "") for f in files])
        else:
            self._combo.addItem("No file found")

    def _load_behaviors(self):
        if not os.path.exists(self.behavior_key_file):
            self.behaviors = [["", "", "point", ""] for _ in range(30)]
            return True

        if not self._check_file_access(self.behavior_key_file):
            QMessageBox.critical(
                self, "Error",
                "Cannot access behavior key file.\n"
                "Is it open in another application?")
            self.behaviors = [["", "", "point", ""] for _ in range(30)]
            return False

        try:
            with open(self.behavior_key_file, "r") as fh:
                self.behaviors = []
                for row in csv.reader(fh):
                    while len(row) < 4:
                        row.append("")
                    self.behaviors.append(row)
                while len(self.behaviors) < 30:
                    self.behaviors.append(["", "", "point", ""])
            return True
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Error loading behaviors: {exc}")
            self.behaviors = [["", "", "point", ""] for _ in range(30)]
            return False

    def _update_entries(self):
        for i, behavior in enumerate(self.behaviors):
            if i >= len(self._name_entries):
                break
            name, key, btype, me_group = (behavior + [""] * 4)[:4]
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
            filename = f"{text}_behaviors.csv"
            self.behavior_key_file = os.path.join(
                self.behavior_key_dir, filename)
            self._load_behaviors()
            self._update_entries()
            self.config_manager.update_last_behavior_key(filename)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _new_behavior_key_file(self):
        if self._new_dialog_open:
            return
        self._new_dialog_open = True

        name, ok = QInputDialog.getText(
            self, "New Behavior Key File",
            "Enter a name for the new Behavior Key file:\n"
            "(Use only letters, numbers, and underscores)")

        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(
                    self, "No Name Entered",
                    "You must enter a name for the Behavior Key file.")
                self._new_dialog_open = False
                return

            if not name.replace("_", "").isalnum():
                QMessageBox.warning(
                    self, "Invalid Characters",
                    "File name can only contain letters, numbers, "
                    "and underscores.")
                self._new_dialog_open = False
                return

            filename = (f"{name}_behaviors.csv"
                        if not name.endswith("_behaviors.csv") else name)
            path = os.path.join(self.behavior_key_dir, filename)

            if not self._check_file_access(path, for_writing=True):
                QMessageBox.critical(
                    self, "Error",
                    "Cannot create behavior key file.\n"
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

                self.behavior_key_file = path
                self._behavior_key_files[filename] = path
                self._refresh_combo()
                self._combo.setCurrentText(name)
                self._load_behaviors()
                self._update_entries()
            except OSError as exc:
                _remove_temp(temp)
                QMessageBox.critical(
                    self, "Error", f"Error creating file: {exc}")

        self._new_dialog_open = False

    def _rename_behavior_key(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            QMessageBox.warning(
                self, "No Selection",
                "Please select a Behavior Key file to rename.")
            return

        if not self._check_file_access(
                self.behavior_key_file, for_writing=True):
            QMessageBox.critical(
                self, "Error",
                "Cannot access the current behavior key file.\n"
                "Is it open in another application?")
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Behavior Key File",
            "Enter new name for the Behavior Key file:\n"
            "(Use only letters, numbers, and underscores)",
            text=current)

        if not ok or not new_name:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(
                self, "No Name Entered",
                "You must enter a name for the Behavior Key file.")
            return

        if not new_name.replace("_", "").isalnum():
            QMessageBox.warning(
                self, "Invalid Characters",
                "File name can only contain letters, numbers, "
                "and underscores.")
            return

        new_filename = f"{new_name}_behaviors.csv"
        old_path = self.behavior_key_file
        new_path = os.path.join(self.behavior_key_dir, new_filename)

        if os.path.exists(new_path):
            QMessageBox.warning(
                self, "File Exists",
                "A file with this name already exists.")
            return

        if not self._check_file_access(new_path, for_writing=True):
            QMessageBox.critical(
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

            self.behavior_key_file = new_path
            self._refresh_combo()
            self._combo.setCurrentText(new_name)
        except OSError as exc:
            _remove_temp(temp)
            QMessageBox.critical(
                self, "Error", f"Failed to rename the file: {exc}")

    def _delete_behavior_key(self):
        current = self._combo.currentText()
        if not current or current == "No file found":
            QMessageBox.warning(
                self, "No Selection",
                "Please select a Behavior Key file to delete.")
            return

        if not self._check_file_access(
                self.behavior_key_file, for_writing=True):
            QMessageBox.critical(
                self, "Error",
                "Cannot access the behavior key file for deletion.\n"
                "Is it open in another application?")
            return

        reply = QMessageBox.question(
            self, "Delete Confirmation",
            f"Are you sure you want to delete '{current}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(self.behavior_key_file)
            files = self._get_behavior_files()
            if files:
                self._refresh_combo()
                display = files[0].replace("_behaviors.csv", "")
                self._combo.setCurrentText(display)
                self.behavior_key_file = os.path.join(
                    self.behavior_key_dir, files[0])
                self._load_behaviors()
                self._update_entries()
            else:
                self._combo.clear()
                self._combo.addItem("No file found")
                self._new_behavior_key_file()
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to delete the file: {exc}")

    def _save_behaviors(self):
        if (not self.behavior_key_file
                or self._combo.currentText() == "No file found"):
            self._new_behavior_key_file()
            return False

        if not self._check_file_access(
                self.behavior_key_file, for_writing=True):
            QMessageBox.critical(
                self, "Error",
                "Cannot save to behavior key file.\n"
                "Is it open in another application?")
            return False

        temp = self.behavior_key_file + ".tmp"
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
            os.replace(temp, self.behavior_key_file)
            self.config_manager.update_last_behavior_key(
                os.path.basename(self.behavior_key_file))
            return True
        except OSError as exc:
            _remove_temp(temp)
            QMessageBox.critical(
                self, "Error", f"Error saving behaviors: {exc}")
            return False

    # ------------------------------------------------------------------
    # Start / cancel
    # ------------------------------------------------------------------

    def _start_video(self):
        if not any(e.text().strip() for e in self._name_entries):
            QMessageBox.warning(
                self, "No Behaviors Defined",
                "Please add behaviors before starting the video.")
            return

        if not self._save_behaviors():
            return

        reserved = {"w", "a", "s", "d"}
        assigned = set()
        for entry in self._key_entries:
            key = entry.text().strip().lower()
            if key:
                if key in reserved:
                    QMessageBox.warning(
                        self, "Invalid Shortcut Key",
                        f"The key '{key}' is reserved for video "
                        "navigation.\nPlease assign a different key.")
                    return
                if key in assigned:
                    QMessageBox.warning(
                        self, "Duplicate Shortcut Key",
                        f"The key '{key}' is assigned to multiple "
                        "behaviors.\nPlease assign unique keys.")
                    return
                assigned.add(key)

        self.config_manager.update_last_behavior_key(
            os.path.basename(self.behavior_key_file))
        self.start_video_flag = True
        self._on_start_video_cb(self.behavior_key_file)
        self.done(QDialog.DialogCode.Accepted)

    def _on_cancel(self):
        current = self._current_behaviors()
        if current != self.behaviors:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Save before going back?",
                (QMessageBox.StandardButton.Save
                 | QMessageBox.StandardButton.Discard
                 | QMessageBox.StandardButton.Cancel),
                QMessageBox.StandardButton.Save)

            if reply == QMessageBox.StandardButton.Save:
                if not self._save_behaviors():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.start_video_flag = False
        self.hide()
        self.done(QDialog.DialogCode.Rejected)
        self._on_cancel_cb()
        self.deleteLater()

    def _current_behaviors(self):
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
