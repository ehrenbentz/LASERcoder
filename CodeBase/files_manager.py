import csv
from datetime import datetime
import json
import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QSplitter, QWidget,
    QInputDialog, QApplication, QFileDialog, QMenu, QComboBox, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QPen

from display_utils import get_screen_geometry, center_window, is_os_junk
from annotation_store import AnnotationStore, parse_time
from annotations_visualizer import show_visualization_dialog
from summary_statistics_manager import SummaryStatisticsManager
from summary_viewer import show_table_viewer, show_boxplot_viewer
from config_manager import get_config
import theme


class FilesManager(QDialog):
    """Dialog for selecting output directory and video file."""

    def __init__(self, parent=None, initial_output_dir=str(Path.home()),
                 initial_video_dir=str(Path.home()),
                 file_types=(
                     # Common containers
                     ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
                     # MPEG transport / program streams
                     ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".m2v", ".vob",
                     # Matroska / WebM variants
                     ".mk3d",
                     # MP4 variants
                     ".m4v", ".3gp", ".3g2",
                     # Professional / camera formats
                     ".mxf", ".r3d",
                     # Ogg / Nut
                     ".ogv", ".ogm", ".nut",
                     # RealMedia / DivX / ASF
                     ".rm", ".rmvb", ".divx", ".asf",
                     # Flash
                     ".f4v", ".swf",
                     # DVD / Blu-ray
                     ".ifo",
                     # Raw / lossless
                     ".y4m", ".dv",
                 )):
        super().__init__(parent)

        self.file_types = file_types
        self.selected_video_file = None

        self.initial_output_dir = os.path.abspath(initial_output_dir)
        self.initial_video_dir = os.path.abspath(initial_video_dir)
        self.current_output_dir = self.initial_output_dir
        self.current_video_dir = self.initial_video_dir
        self.output_dir = self.initial_output_dir

        self._screen = get_screen_geometry()

        self.setWindowTitle("LaserTAG - Select Output Directory and Video File")
        theme.apply_dialog_theme(self)
        theme.stay_on_top(self)

        if self.parent():
            self.parent().showMaximized()

        self._setup_ui()

        dialog_w = int(self._screen["width"] * 0.8)
        dialog_h = int(self._screen["height"] * 0.8)
        self.setMinimumSize(int(dialog_w * 0.8), int(dialog_h * 0.8))
        center_window(self, dialog_w, dialog_h, self._screen)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        output_panel = QFrame()
        self._setup_output_panel(QVBoxLayout(output_panel))
        splitter.addWidget(output_panel)

        video_panel = QFrame()
        self._setup_video_panel(QVBoxLayout(video_panel))
        splitter.addWidget(video_panel)

        width = int(self._screen["width"] * 0.6)
        splitter.setSizes([int(width / 3), int(2 * width / 3)])

    def _setup_output_panel(self, layout):
        layout.addWidget(QLabel("Select Output Directory:"))

        nav_frame = QFrame()
        nav = QHBoxLayout(nav_frame)
        nav.setContentsMargins(0, 0, 0, 0)

        up_btn = QPushButton("\u2191")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(lambda: self._go_up("output"))
        nav.addWidget(up_btn)

        self.output_dir_entry = QLineEdit(self.initial_output_dir)
        self.output_dir_entry.returnPressed.connect(self._on_output_dir_update)
        nav.addWidget(self.output_dir_entry)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        nav.addWidget(browse_btn)

        layout.addWidget(nav_frame)

        self.output_dir_listbox = QListWidget()
        self.output_dir_listbox.itemDoubleClicked.connect(
            self._on_output_dir_double_click)
        layout.addWidget(self.output_dir_listbox)

        self.dir_selected_label = QLabel(
            f"Selected Output Directory: {self.output_dir}")
        layout.addWidget(self.dir_selected_label)

        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        create_btn = QPushButton("Create Directory")
        create_btn.clicked.connect(self._create_directory)
        btn_layout.addWidget(create_btn)

        delete_btn = QPushButton("Delete Directory")
        delete_btn.clicked.connect(self._delete_directory)
        btn_layout.addWidget(delete_btn)

        select_btn = QPushButton("Select Directory")
        select_btn.clicked.connect(self._select_directory)
        btn_layout.addWidget(select_btn)

        layout.addWidget(btn_frame)

        summary_frame = QFrame()
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(0, 5, 0, 0)
        view_ann_btn = QPushButton("View Annotations")
        view_ann_btn.clicked.connect(self._show_view_annotations)
        summary_layout.addWidget(view_ann_btn)
        del_ann_btn = QPushButton("Delete Annotations")
        del_ann_btn.clicked.connect(self._show_delete_annotations)
        summary_layout.addWidget(del_ann_btn)
        summary_btn = QPushButton("Summary Statistics")
        summary_btn.clicked.connect(self._show_summary_menu)
        summary_layout.addWidget(summary_btn)
        layout.addWidget(summary_frame)

        backup_frame = QFrame()
        backup_layout = QHBoxLayout(backup_frame)
        backup_layout.setContentsMargins(0, 5, 0, 0)
        backup_btn = QPushButton("Backup Project")
        backup_btn.clicked.connect(self._backup_project)
        backup_layout.addWidget(backup_btn)
        for _ in range(2):
            spacer = QPushButton()
            spacer.setEnabled(False)
            spacer.setStyleSheet("border: none; background: transparent;")
            backup_layout.addWidget(spacer)
        layout.addWidget(backup_frame)

        self._populate_dir_list(self.initial_output_dir)

    def _setup_video_panel(self, layout):
        # Top row: label + settings gear pushed to the right
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(QLabel("Select Video File:"))
        top_row.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._show_settings_menu)
        top_row.addWidget(settings_btn)

        layout.addLayout(top_row)

        nav_frame = QFrame()
        nav = QHBoxLayout(nav_frame)
        nav.setContentsMargins(0, 0, 0, 0)

        up_btn = QPushButton("\u2191")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(lambda: self._go_up("video"))
        nav.addWidget(up_btn)

        self.video_dir_entry = QLineEdit(self.initial_video_dir)
        self.video_dir_entry.returnPressed.connect(self._on_video_dir_update)
        nav.addWidget(self.video_dir_entry)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_video_dir)
        nav.addWidget(browse_btn)

        layout.addWidget(nav_frame)

        video_container = QWidget()
        layout.addWidget(video_container, 1)
        container_layout = QVBoxLayout(video_container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        sub_splitter = QSplitter(Qt.Orientation.Horizontal)
        container_layout.addWidget(sub_splitter)

        # Directories sub-panel
        dir_panel = QFrame()
        dir_layout = QVBoxLayout(dir_panel)
        dir_layout.setContentsMargins(5, 5, 5, 5)
        dir_layout.addWidget(QLabel("Directories:"))

        self.video_dir_listbox = QListWidget()
        self.video_dir_listbox.itemDoubleClicked.connect(
            self._on_video_dir_double_click)
        dir_layout.addWidget(self.video_dir_listbox, 1)

        spacer = QWidget()
        spacer.setFixedHeight(30)
        dir_layout.addWidget(spacer)
        sub_splitter.addWidget(dir_panel)

        # Video files sub-panel
        file_panel = QFrame()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(5, 5, 5, 5)
        file_layout.addWidget(QLabel("Video Files:"))

        self.video_file_listbox = QListWidget()
        self.video_file_listbox.itemDoubleClicked.connect(
            self._select_video_file)
        self.video_file_listbox.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_file_listbox.customContextMenuRequested.connect(
            self._show_video_context_menu)
        file_layout.addWidget(self.video_file_listbox, 1)

        # Status legend
        legend = QHBoxLayout()
        legend.setContentsMargins(0, 2, 0, 2)
        legend.setSpacing(12)
        for status, label_text in [
            ("in_progress", "In Progress"),
            ("complete", "Complete"),
        ]:
            icon_label = QLabel()
            icon_label.setPixmap(
                FilesManager._status_icon(status).pixmap(QSize(14, 14)))
            icon_label.setFixedSize(14, 14)
            text_label = QLabel(label_text)
            text_label.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent; font-size: 11px;")
            legend.addWidget(icon_label)
            legend.addWidget(text_label)
        legend.addStretch()
        file_layout.addLayout(legend)

        select_btn = QPushButton("Select Video")
        select_btn.setFixedSize(150, 30)
        select_btn.clicked.connect(self._select_video_file)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(select_btn)
        btn_row.addStretch(0)
        file_layout.addLayout(btn_row)

        sub_splitter.addWidget(file_panel)
        sub_splitter.setSizes([
            int(sub_splitter.width() / 2),
            int(sub_splitter.width() / 2),
        ])

        self._populate_video_dir_list(self.initial_video_dir)
        self._populate_file_list(self.initial_video_dir)

    # ------------------------------------------------------------------
    # Directory navigation
    # ------------------------------------------------------------------

    def _go_up(self, panel):
        if panel == "output":
            parent = os.path.dirname(self.current_output_dir)
            if os.path.exists(parent):
                self.current_output_dir = parent
                self.output_dir_entry.setText(parent)
                self._populate_dir_list(parent)
                if parent != self.output_dir:
                    self.output_dir = None
                    self.dir_selected_label.setText(
                        "Selected Output Directory: None")
        else:
            parent = os.path.dirname(self.current_video_dir)
            if os.path.exists(parent):
                self.current_video_dir = parent
                self.video_dir_entry.setText(parent)
                self._populate_video_dir_list(parent)
                self._populate_file_list(parent)

    def _browse_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.current_output_dir,
            QFileDialog.Option.ShowDirsOnly)
        if path:
            if self._is_backup_dir(path):
                theme.show_message(
                    self, "Backup Directory",
                    "This directory is a LaserTAG backup and "
                    "cannot be used as a project directory.")
                return
            self.current_output_dir = path
            self.output_dir_entry.setText(path)
            self._populate_dir_list(path)
            self.output_dir = path
            self.dir_selected_label.setText(
                f"Selected Output Directory: {self.output_dir}")

    def _browse_video_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Video Directory", self.current_video_dir,
            QFileDialog.Option.ShowDirsOnly)
        if path:
            self.current_video_dir = path
            self.video_dir_entry.setText(path)
            self._populate_video_dir_list(path)
            self._populate_file_list(path)

    def _on_output_dir_update(self):
        path = self.output_dir_entry.text().strip()
        if os.path.isdir(path):
            if self._is_backup_dir(path):
                theme.show_message(
                    self, "Backup Directory",
                    "This directory is a LaserTAG backup and "
                    "cannot be used as a project directory.")
                return
            self.current_output_dir = path
            self._populate_dir_list(path)
            if path != self.output_dir:
                self.output_dir = path
                self.dir_selected_label.setText(
                    f"Selected Output Directory: {self.output_dir}")

    def _on_video_dir_update(self):
        path = self.video_dir_entry.text().strip()
        if os.path.isdir(path):
            self.current_video_dir = path
            self._populate_video_dir_list(path)
            self._populate_file_list(path)

    def _on_output_dir_double_click(self, item):
        new_dir = os.path.join(self.current_output_dir, item.text())
        if os.path.isdir(new_dir):
            if self._is_backup_dir(new_dir):
                theme.show_message(
                    self, "Backup Directory",
                    "This directory is a LaserTAG backup and "
                    "cannot be used as a project directory.")
                return
            self.current_output_dir = new_dir
            self.output_dir_entry.setText(new_dir)
            self._populate_dir_list(new_dir)
            self.output_dir = new_dir
            self.dir_selected_label.setText(
                f"Selected Output Directory: {self.output_dir}")

    def _on_video_dir_double_click(self, item):
        new_dir = os.path.join(self.current_video_dir, item.text())
        if os.path.isdir(new_dir):
            self.current_video_dir = new_dir
            self.video_dir_entry.setText(new_dir)
            self._populate_video_dir_list(new_dir)
            self._populate_file_list(new_dir)

    # ------------------------------------------------------------------
    # List population
    # ------------------------------------------------------------------

    def _populate_dir_list(self, directory):
        self.output_dir_listbox.clear()
        try:
            dirs = sorted(
                d for d in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, d))
                and not d.startswith("."))
            self.output_dir_listbox.addItems(dirs)
        except OSError:
            pass

    def _populate_video_dir_list(self, directory):
        self.video_dir_listbox.clear()
        try:
            dirs = sorted(
                d for d in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, d))
                and not d.startswith("."))
            self.video_dir_listbox.addItems(dirs)
        except OSError:
            pass

    def _populate_file_list(self, directory):
        self.video_file_listbox.clear()
        try:
            extensions = tuple(ext.lower() for ext in self.file_types)
            files = sorted(
                f for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
                and f.lower().endswith(extensions)
                and not is_os_junk(f))
            statuses = self._get_all_video_statuses(files)
            for fname in files:
                item = QListWidgetItem(fname)
                status = statuses.get(fname, "not_started")
                if status == "complete":
                    item.setIcon(self._status_icon("complete"))
                elif status == "in_progress":
                    item.setIcon(self._status_icon("in_progress"))
                self.video_file_listbox.addItem(item)
        except OSError:
            pass

    def _get_all_video_statuses(self, filenames):
        """Check session state JSONs for all videos at once."""
        result = {}
        if not self.output_dir:
            return result
        resume_dir = os.path.join(self.output_dir, "Resume")
        if not os.path.isdir(resume_dir):
            return result
        # Read all session state files in one pass
        existing = set()
        try:
            existing = {f for f in os.listdir(resume_dir)
                        if not is_os_junk(f)}
        except OSError:
            return result
        for fname in filenames:
            video_name = os.path.splitext(fname)[0]
            state_file = f"{video_name}_session_state.json"
            if state_file not in existing:
                continue
            try:
                with open(os.path.join(resume_dir, state_file), "r") as f:
                    data = json.load(f)
                if data.get("completed"):
                    result[fname] = "complete"
                elif data.get("timestamp_sec"):
                    result[fname] = "in_progress"
            except (json.JSONDecodeError, ValueError, OSError):
                pass
        return result

    @staticmethod
    def _status_icon(status):
        """Create a small colored circle icon for video status."""
        size = 14
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if status == "complete":
            painter.setBrush(QColor("#4CAF50"))
            painter.setPen(QPen(QColor("#388E3C"), 1))
            painter.drawEllipse(1, 1, size - 2, size - 2)
            # Draw checkmark
            pen = QPen(QColor("white"), 1.8)
            painter.setPen(pen)
            painter.drawLine(4, 7, 6, 10)
            painter.drawLine(6, 10, 10, 4)
        elif status == "in_progress":
            painter.setBrush(QColor("#FFC107"))
            painter.setPen(QPen(QColor("#FFA000"), 1))
            painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        return QIcon(pixmap)

    # ------------------------------------------------------------------
    # Video context menu
    # ------------------------------------------------------------------

    def _show_video_context_menu(self, pos):
        item = self.video_file_listbox.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        menu.setStyleSheet(theme.menu_stylesheet())

        mark_complete = menu.addAction("Mark Complete")
        mark_progress = menu.addAction("Mark In Progress")
        mark_clear = menu.addAction("Clear Status")

        action = menu.exec(
            self.video_file_listbox.mapToGlobal(pos))
        if action is None:
            return

        fname = item.text()
        if action == mark_complete:
            self._set_video_status(fname, "complete")
        elif action == mark_progress:
            self._set_video_status(fname, "in_progress")
        elif action == mark_clear:
            self._set_video_status(fname, "clear")

    def _set_video_status(self, filename, status):
        if not self.output_dir:
            theme.show_message(
                self, "Warning",
                "Please select an output directory first.")
            return

        video_name = os.path.splitext(filename)[0]
        resume_dir = os.path.join(self.output_dir, "Resume")
        os.makedirs(resume_dir, exist_ok=True)
        state_file = os.path.join(
            resume_dir, f"{video_name}_session_state.json")

        if status == "clear":
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except OSError as exc:
                    theme.show_message(
                        self, "Error",
                        f"Failed to remove session state: {exc}")
                    return
        else:
            # Load existing state or create a new one
            data = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r") as fh:
                        data = json.load(fh)
                except (json.JSONDecodeError, OSError):
                    data = {}

            if status == "complete":
                data["completed"] = True
                data.setdefault("timestamp_sec", 0)
            elif status == "in_progress":
                data.pop("completed", None)
                data.setdefault("timestamp_sec", 1)

            temp = state_file + ".tmp"
            try:
                with open(temp, "w") as fh:
                    json.dump(data, fh)
                os.replace(temp, state_file)
            except OSError as exc:
                try:
                    os.remove(temp)
                except OSError:
                    pass
                theme.show_message(
                    self, "Error",
                    f"Failed to update session state: {exc}")
                return

        self._populate_file_list(self.current_video_dir)

    # ------------------------------------------------------------------
    # Backup guard
    # ------------------------------------------------------------------

    def _is_backup_dir(self, path):
        """Return True if *path* is a backup directory."""
        if os.path.isfile(os.path.join(path, ".no_project")):
            return True
        return get_config().is_backup_dir(path)

    # ------------------------------------------------------------------
    # Backup project
    # ------------------------------------------------------------------

    def _backup_project(self):
        if not self.output_dir:
            theme.show_message(
                self, "Warning",
                "Please select an output directory first.")
            return

        dest_parent = QFileDialog.getExistingDirectory(
            self, "Select Backup Location", str(Path.home()),
            QFileDialog.Option.ShowDirsOnly)
        if not dest_parent:
            return

        default_name = os.path.basename(self.output_dir)
        name, ok = theme.get_text(
            self, "Backup Name",
            "Enter a name for the backup folder:",
            text=default_name)
        if not ok or not name or not name.strip():
            return
        date_stamp = datetime.now().strftime("%Y%m%d")
        base_name = f"{name.strip()}_BKP_{date_stamp}"
        name = base_name
        dest = os.path.normpath(os.path.join(dest_parent, name))
        counter = 1
        while os.path.exists(dest):
            name = f"{base_name}.{counter}"
            dest = os.path.normpath(os.path.join(dest_parent, name))
            counter += 1

        try:
            shutil.copytree(self.output_dir, dest)
        except OSError as exc:
            theme.show_message(
                self, "Error", f"Backup failed: {exc}")
            return

        # Mark the backup so it cannot be opened as a project
        try:
            marker = os.path.join(dest, ".no_project")
            with open(marker, "w") as fh:
                fh.write("This directory is a LaserTAG backup and "
                         "cannot be used as a project directory.\n")
        except OSError:
            pass

        get_config().add_backup_dir(dest)

        theme.show_message(
            self, "Backup Complete",
            f"Project backed up to:\n{dest}",
            icon="information")

    # ------------------------------------------------------------------
    # Directory actions
    # ------------------------------------------------------------------

    def _create_directory(self):
        name, ok = theme.get_text(
            self, "Create Directory", "Enter new directory name:")
        if ok and name:
            new_path = os.path.join(self.current_output_dir, name)
            try:
                os.makedirs(new_path, exist_ok=True)
                self.current_output_dir = new_path
                self.output_dir_entry.setText(new_path)
                self._populate_dir_list(new_path)
                self.output_dir = new_path
                self.dir_selected_label.setText(
                    f"Selected Output Directory: {self.output_dir}")
            except OSError as exc:
                theme.show_message(
                    self, "Error", f"Could not create directory: {exc}")

    def _delete_directory(self):
        current_item = self.output_dir_listbox.currentItem()
        if not current_item:
            theme.show_message(
                self, "Warning", "Please select a directory to delete.")
            return

        dir_name = current_item.text()
        dir_path = os.path.join(self.current_output_dir, dir_name)

        reply = theme.show_message(
            self, "Confirm Deletion",
            f"Are you sure you want to delete directory '{dir_name}'?\n"
            "This cannot be undone.",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if os.listdir(dir_path):
                confirm = theme.show_message(
                    self, "Non-empty Directory",
                    f"Directory '{dir_name}' is not empty. Delete anyway?",
                    icon="question")
                if confirm != QMessageBox.StandardButton.Yes:
                    return

            shutil.rmtree(dir_path)
            self._populate_dir_list(self.current_output_dir)
            theme.show_message(
                self, "Success",
                f"Directory '{dir_name}' has been deleted.",
                icon="information")
        except OSError as exc:
            theme.show_message(
                self, "Error", f"Could not delete directory: {exc}")

    def _select_directory(self):
        current_item = self.output_dir_listbox.currentItem()
        if current_item:
            new_dir = os.path.join(
                self.current_output_dir, current_item.text())
            if os.path.isdir(new_dir):
                if self._is_backup_dir(new_dir):
                    theme.show_message(
                        self, "Backup Directory",
                        "This directory is a LaserTAG backup and "
                        "cannot be used as a project directory.")
                    return
                self.current_output_dir = new_dir
                self.output_dir_entry.setText(new_dir)
                self._populate_dir_list(new_dir)
                self.output_dir = new_dir
        else:
            if self._is_backup_dir(self.current_output_dir):
                theme.show_message(
                    self, "Backup Directory",
                    "This directory is a LaserTAG backup and "
                    "cannot be used as a project directory.")
                return
            self.output_dir = self.current_output_dir
        if self.output_dir:
            get_config().update_output_dir(self.output_dir)
        self.dir_selected_label.setText(
            f"Selected Output Directory: {self.output_dir}")

    # ------------------------------------------------------------------
    # Video selection
    # ------------------------------------------------------------------

    def _select_video_file(self, _item=None):
        current_item = self.video_file_listbox.currentItem()
        if current_item:
            if not self.output_dir:
                theme.show_message(
                    self, "Warning",
                    "Please select an output directory first using the "
                    "'Select Directory' button.")
                return
            if self._is_backup_dir(self.output_dir):
                theme.show_message(
                    self, "Backup Directory",
                    "The selected output directory is a LaserTAG backup "
                    "and cannot be used as a project directory.\n\n"
                    "Please select a different output directory.")
                return
            self.selected_video_file = os.path.join(
                self.current_video_dir, current_item.text())
            self.done(QDialog.DialogCode.Accepted)
        else:
            theme.show_message(
                self, "Note", "You must select a video file to proceed",
                icon="information")

    # ------------------------------------------------------------------
    # View annotations
    # ------------------------------------------------------------------

    def _show_view_annotations(self):
        ann_dir = ""
        if self.output_dir:
            ann_dir = os.path.join(self.output_dir, "Annotations")

        ann_files = []
        if ann_dir and os.path.isdir(ann_dir):
            ann_files = sorted(
                f for f in os.listdir(ann_dir)
                if f.endswith("_Annotations.csv")
                and not is_os_junk(f))

        dlg = QDialog(self)
        dlg.setWindowTitle("View Annotations")
        theme.apply_dialog_theme(dlg)
        theme.stay_on_top(dlg)
        dlg.setModal(True)
        dlg.setMinimumWidth(400)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        grp = QGroupBox("Annotation Files")
        grp_lay = QVBoxLayout(grp)
        grp_lay.setSpacing(6)

        if ann_files:
            desc = QLabel(
                f"{len(ann_files)} annotation file"
                f"{'s' if len(ann_files) != 1 else ''} found. "
                "Select a file to view.")
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent;")
            grp_lay.addWidget(desc)

            combo = QComboBox()
            for fname in ann_files:
                title = (fname.replace("_Annotations.csv", "")
                              .replace("_", " "))
                combo.addItem(title, os.path.join(ann_dir, fname))
            grp_lay.addWidget(combo)

            btn_row_ann = QHBoxLayout()
            view_btn = QPushButton("View Spreadsheet")
            view_btn.clicked.connect(lambda: self._view_annotation_file(
                dlg, combo.currentData(), combo.currentText()))
            btn_row_ann.addWidget(view_btn)
            viz_btn = QPushButton("Visualize")
            viz_btn.clicked.connect(lambda: self._visualize_annotation_file(
                dlg, combo.currentData(), combo.currentText()))
            btn_row_ann.addWidget(viz_btn)
            grp_lay.addLayout(btn_row_ann)
        else:
            desc = QLabel(
                "No annotation files found in the selected output directory.")
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent;")
            grp_lay.addWidget(desc)

        layout.addWidget(grp)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _view_annotation_file(self, parent_dlg, path, title):
        show_table_viewer(parent_dlg, path, title + " Annotations")

    def _visualize_annotation_file(self, parent_dlg, path, title):
        state_ann, point_ann = [], []
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    atype = row.get("Type", "").strip().lower()
                    if atype == "state":
                        start, end = 0, None
                        try:
                            s = row.get("Start", "").strip()
                            if s and s != "NA":
                                start = float(s)
                            e = row.get("End", "").strip()
                            if e and e != "NA":
                                end = float(e)
                        except ValueError:
                            hs = row.get("H_Start", "").strip()
                            he = row.get("H_End", "").strip()
                            if hs and hs != "NA":
                                start = parse_time(hs)
                            if he and he != "NA":
                                end = parse_time(he)
                        state_ann.append({
                            "Event": row.get("Event", "").strip(),
                            "start_time": start, "end_time": end,
                            "Type": "State",
                            "Mutually_Exclusive": row.get(
                                "Mutually_Exclusive", "False"),
                            "Notes": row.get("Notes", ""),
                        })
                    elif atype == "point":
                        raw = row.get("Start", "0").strip()
                        point_ann.append({
                            "Event": row.get("Event", "").strip(),
                            "time": row.get("H_Start", "").strip(),
                            "raw_time": (float(raw)
                                         if raw and raw != "NA" else 0),
                            "Manual_Edit": row.get("Manual_Edit", "False"),
                            "Notes": row.get("Notes", ""),
                        })
        except Exception as exc:
            theme.show_message(
                parent_dlg, "Error",
                f"Failed to read annotations: {exc}")
            return

        if not state_ann and not point_ann:
            theme.show_message(
                parent_dlg, "No Annotations",
                "No annotations found to visualize.",
                icon="information")
            return

        # Estimate duration from annotation timestamps
        max_time = 0
        for e in state_ann:
            if e["end_time"] is not None:
                max_time = max(max_time, e["end_time"])
            max_time = max(max_time, e["start_time"])
        for e in point_ann:
            max_time = max(max_time, e.get("raw_time", 0))
        video_duration = max_time * 1.05 if max_time > 0 else 60

        # Build a lightweight store for viz settings persistence
        video_name = os.path.splitext(os.path.basename(path))[0]
        video_name = video_name.replace("_Annotations", "")
        store = AnnotationStore(
            video_name=video_name,
            annotations_file=path,
            session_state_file="",
            event_key_file="",
            output_dir=self.output_dir or "",
        )

        # Load coding bounds from session state if available
        state = store.load_session_state()
        coding_start = 0
        coding_end = None
        if state:
            coding_start = state.get("coding_start", 0)
            coding_end = state.get("coding_end")

        has_bounds = (coding_start > 0
                      or (coding_end is not None and coding_end > 0))
        bounds = {
            "has_bounds": has_bounds,
            "start": coding_start,
            "end": coding_end,
            "whole_video": True,
        }

        try:
            show_visualization_dialog(
                parent=parent_dlg,
                video_name=video_name,
                state_events=state_ann,
                point_events=point_ann,
                video_duration=video_duration,
                parse_time_func=parse_time,
                center_window_func=center_window,
                output_dir=self.output_dir or "",
                bounds=bounds,
                store=store,
            )
        except Exception as exc:
            theme.show_message(
                parent_dlg, "Visualization Error",
                f"Failed to create visualization: {exc}")

    # ------------------------------------------------------------------
    # Delete annotations
    # ------------------------------------------------------------------

    def _show_delete_annotations(self):
        ann_dir = ""
        if self.output_dir:
            ann_dir = os.path.join(self.output_dir, "Annotations")

        ann_files = []
        if ann_dir and os.path.isdir(ann_dir):
            ann_files = sorted(
                f for f in os.listdir(ann_dir)
                if f.endswith("_Annotations.csv")
                and not is_os_junk(f))

        if not ann_files:
            theme.show_message(
                self, "No Annotations",
                "No annotation files found in the selected "
                "output directory.",
                icon="information")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Delete Annotations")
        theme.apply_dialog_theme(dlg)
        theme.stay_on_top(dlg)
        dlg.setModal(True)
        dlg.setMinimumWidth(400)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel("Which annotations would you like to remove?")
        layout.addWidget(label)

        combo = QComboBox()
        for fname in ann_files:
            title = (fname.replace("_Annotations.csv", "")
                          .replace("_", " "))
            combo.addItem(title, fname)
        layout.addWidget(combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(
            lambda: self._confirm_delete_annotations(
                dlg, ann_dir, combo.currentData(), combo.currentText()))
        btn_row.addWidget(delete_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _confirm_delete_annotations(self, parent_dlg, ann_dir,
                                    filename, display_name):
        reply = theme.show_message(
            parent_dlg, "Confirm Deletion",
            f"This will delete the annotations for "
            f"'{display_name}'.\n\nAre you sure?",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        ann_path = os.path.join(ann_dir, filename)
        video_name = filename.replace("_Annotations.csv", "")

        # Remove annotation file
        try:
            os.remove(ann_path)
        except OSError as exc:
            theme.show_message(
                parent_dlg, "Error",
                f"Failed to delete annotations: {exc}")
            return

        # Remove associated session state file
        if self.output_dir:
            resume_dir = os.path.join(self.output_dir, "Resume")
            state_file = os.path.join(
                resume_dir, f"{video_name}_session_state.json")
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except OSError:
                    pass

        theme.show_message(
            parent_dlg, "Deleted",
            f"Annotations for '{display_name}' have been deleted.",
            icon="information")

        # Refresh the video file list to update status icons
        self._populate_file_list(self.current_video_dir)

        parent_dlg.accept()

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    def _open_summary_statistics(self):
        if self.output_dir:
            annotations_dir = os.path.join(self.output_dir, "Annotations")
            start_dir = (annotations_dir if os.path.exists(annotations_dir)
                         else self.output_dir)
        else:
            start_dir = self.current_output_dir

        try:
            SummaryStatisticsManager(self, start_dir).exec()
        except Exception as exc:
            theme.show_message(
                self, "Error",
                f"Failed to open Summary Statistics Manager: {exc}")

    def _show_summary_menu(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Summary Statistics")
        theme.apply_dialog_theme(dlg)
        theme.stay_on_top(dlg)
        dlg.setModal(True)
        dlg.setMinimumWidth(360)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel("What would you like to do?")
        layout.addWidget(label)

        gen_btn = QPushButton("Generate Summaries")
        box_btn = QPushButton("Generate Box Plots")
        gen_btn.clicked.connect(lambda: dlg.done(1))
        box_btn.clicked.connect(lambda: dlg.done(2))
        layout.addWidget(gen_btn)
        layout.addWidget(box_btn)

        # Show view options if summaries already exist
        summary_base = (os.path.join(self.output_dir, "Summary")
                        if self.output_dir else "")
        ind_dir = os.path.join(summary_base, "Individual_summaries")
        comb_dir = os.path.join(summary_base, "Combined_summaries")
        has_ind = os.path.isdir(ind_dir) and any(
            f.endswith(".csv") for f in os.listdir(ind_dir)
            if not is_os_junk(f))
        has_comb = os.path.isdir(comb_dir) and any(
            f.endswith(".csv") for f in os.listdir(comb_dir)
            if not is_os_junk(f))

        if has_ind or has_comb:
            layout.addSpacing(6)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            layout.addWidget(sep)
            view_label = QLabel("Previously generated:")
            view_label.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent;")
            layout.addWidget(view_label)

            if has_ind:
                view_ind_btn = QPushButton("View Individual Summaries")
                view_ind_btn.clicked.connect(lambda: dlg.done(3))
                layout.addWidget(view_ind_btn)
            if has_comb:
                view_comb_btn = QPushButton("View Combined Summaries")
                view_comb_btn.clicked.connect(lambda: dlg.done(4))
                layout.addWidget(view_comb_btn)
                view_box_btn = QPushButton("View Box Plots")
                view_box_btn.clicked.connect(lambda: dlg.done(5))
                layout.addWidget(view_box_btn)

        result = dlg.exec()

        if result == 1:
            self._open_summary_statistics()
        elif result == 2:
            self._generate_boxplots_flow()
        elif result == 3:
            self._view_existing_summaries(ind_dir, "Individual")
        elif result == 4:
            self._view_existing_summaries(comb_dir, "Combined")
        elif result == 5:
            self._open_boxplot_viewer()

    def _generate_boxplots_flow(self):
        """Generate combined summaries then show box plots."""
        if not self.output_dir:
            theme.show_message(
                self, "Warning",
                "Please select an output directory first.")
            return

        ann_dir = os.path.join(self.output_dir, "Annotations")
        if not os.path.isdir(ann_dir):
            theme.show_message(
                self, "No Annotations",
                "No Annotations folder found in the output directory.")
            return

        ann_files = sorted(
            os.path.join(ann_dir, f) for f in os.listdir(ann_dir)
            if f.endswith("_Annotations.csv") and not is_os_junk(f))
        if not ann_files:
            theme.show_message(
                self, "No Annotations",
                "No annotation files found.")
            return

        from summary_statistics import generate_summary_statistics, combine_summaries

        experiment_name, ok = theme.get_text(
            self, "Experiment Name",
            "Enter a name for this experiment/analysis:")
        if not ok or not experiment_name:
            return
        experiment_name = "".join(
            c for c in experiment_name if c.isalnum() or c in " _-")

        summary_dir = os.path.join(self.output_dir, "Summary")
        ind_dir = os.path.join(summary_dir, "Individual_summaries")
        comb_dir = os.path.join(summary_dir, "Combined_summaries")
        for d in (ind_dir, comb_dir):
            os.makedirs(d, exist_ok=True)

        # Check if combined summary already exists
        combined_path = os.path.join(
            comb_dir, f"{experiment_name}_Combined_Summary.csv")
        if os.path.exists(combined_path):
            reply = theme.show_message(
                self, "Summary Exists",
                f"A combined summary named '{experiment_name}' "
                "already exists.\n\nOverwrite it?",
                icon="question")
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Generate individual summaries
        ind_paths = []
        for path in ann_files:
            video_name = os.path.basename(path).replace(
                "_Annotations.csv", "")
            out = os.path.join(ind_dir, f"{video_name}_Summary.csv")
            if os.path.exists(out):
                ind_paths.append(out)
                continue
            try:
                result = generate_summary_statistics(path, out)
                if result:
                    ind_paths.append(result)
            except Exception:
                pass

        if not ind_paths:
            theme.show_message(
                self, "No Summaries",
                "Could not generate any summary files.")
            return

        # Generate combined summary
        combined_path = os.path.join(
            comb_dir, f"{experiment_name}_Combined_Summary.csv")
        try:
            combine_summaries(ind_paths, combined_path)
        except Exception as exc:
            theme.show_message(
                self, "Error",
                f"Error generating combined summary: {exc}")
            return

        # Show box plots
        show_boxplot_viewer(self, comb_dir)

    def _view_existing_summaries(self, directory, kind):
        """Show a picker for existing summary CSVs."""
        files = sorted(
            f for f in os.listdir(directory)
            if f.endswith(".csv") and not is_os_junk(f))
        if not files:
            theme.show_message(
                self, "No Files",
                f"No {kind.lower()} summary files found.",
                icon="information")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"View {kind} Summaries")
        theme.apply_dialog_theme(dlg)
        theme.stay_on_top(dlg)
        dlg.setModal(True)
        dlg.setMinimumWidth(400)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        combo = QComboBox()
        for fname in files:
            title = (fname.replace("_Combined_Summary.csv", "")
                          .replace("_Summary.csv", "")
                          .replace("_", " "))
            combo.addItem(title, os.path.join(directory, fname))
        layout.addWidget(combo)

        btn_row = QHBoxLayout()
        view_btn = QPushButton("View")
        view_btn.clicked.connect(lambda: show_table_viewer(
            dlg, combo.currentData(), combo.currentText()))
        btn_row.addWidget(view_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _open_boxplot_viewer(self):
        comb_dir = ""
        if self.output_dir:
            comb_dir = os.path.join(
                self.output_dir, "Summary", "Combined_summaries")
        show_boxplot_viewer(self, comb_dir)

    # ------------------------------------------------------------------
    # Settings menu
    # ------------------------------------------------------------------

    def _show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(theme.menu_stylesheet())

        theme_menu = menu.addMenu("Theme")
        current = theme.current_theme()
        for name in ("system", "dark", "light"):
            action = theme_menu.addAction(name.capitalize())
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(
                lambda checked, n=name: self._apply_theme(n))

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _apply_theme(self, name):
        from config_manager import get_config
        theme.load_theme(name)
        get_config().update_theme(name)

        app = QApplication.instance()
        app.setStyleSheet(theme.app_stylesheet())

        theme.apply_dialog_theme(self)

        # Update the main window background (not a Qt parent of this dialog)
        for w in QApplication.instance().topLevelWidgets():
            if hasattr(w, 'apply_theme'):
                w.apply_theme()

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            if self.parent():
                QTimer.singleShot(0, self.parent().close)
            else:
                QTimer.singleShot(0, QApplication.quit)
        else:
            super().keyPressEvent(event)
