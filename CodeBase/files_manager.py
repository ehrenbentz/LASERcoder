import csv
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

from display_utils import get_screen_geometry, center_window
from annotation_store import AnnotationStore, parse_time
from annotations_visualizer import show_visualization_dialog
from summary_statistics_manager import SummaryStatisticsManager
from summary_viewer import show_table_viewer, show_boxplot_viewer
import theme


class FilesManager(QDialog):
    """Dialog for selecting output directory and video file."""

    def __init__(self, parent=None, initial_output_dir=str(Path.home()),
                 initial_video_dir=str(Path.home()),
                 file_types=(".mp4", ".avi", ".mov", ".mts", ".mkv")):
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
        self.setStyleSheet(theme.dialog_stylesheet())

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
        summary_btn = QPushButton("Summary Statistics")
        summary_btn.clicked.connect(self._show_summary_menu)
        summary_layout.addWidget(summary_btn)
        spacer = QPushButton()
        spacer.setEnabled(False)
        spacer.setStyleSheet("border: none; background: transparent;")
        summary_layout.addWidget(spacer)
        layout.addWidget(summary_frame)

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
                and f.lower().endswith(extensions))
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
            existing = set(os.listdir(resume_dir))
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
    # Directory actions
    # ------------------------------------------------------------------

    def _create_directory(self):
        name, ok = QInputDialog.getText(
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
                QMessageBox.critical(
                    self, "Error", f"Could not create directory: {exc}")

    def _delete_directory(self):
        current_item = self.output_dir_listbox.currentItem()
        if not current_item:
            QMessageBox.warning(
                self, "Warning", "Please select a directory to delete.")
            return

        dir_name = current_item.text()
        dir_path = os.path.join(self.current_output_dir, dir_name)

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete directory '{dir_name}'?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if os.listdir(dir_path):
                confirm = QMessageBox.question(
                    self, "Non-empty Directory",
                    f"Directory '{dir_name}' is not empty. Delete anyway?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if confirm != QMessageBox.StandardButton.Yes:
                    return

            shutil.rmtree(dir_path)
            self._populate_dir_list(self.current_output_dir)
            QMessageBox.information(
                self, "Success",
                f"Directory '{dir_name}' has been deleted.")
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Could not delete directory: {exc}")

    def _select_directory(self):
        current_item = self.output_dir_listbox.currentItem()
        if current_item:
            new_dir = os.path.join(
                self.current_output_dir, current_item.text())
            if os.path.isdir(new_dir):
                self.current_output_dir = new_dir
                self.output_dir_entry.setText(new_dir)
                self._populate_dir_list(new_dir)
                self.output_dir = new_dir
        else:
            self.output_dir = self.current_output_dir
        self.dir_selected_label.setText(
            f"Selected Output Directory: {self.output_dir}")

    # ------------------------------------------------------------------
    # Video selection
    # ------------------------------------------------------------------

    def _select_video_file(self, _item=None):
        current_item = self.video_file_listbox.currentItem()
        if current_item:
            if not self.output_dir:
                QMessageBox.warning(
                    self, "Warning",
                    "Please select an output directory first using the "
                    "'Select Directory' button.")
                return
            self.selected_video_file = os.path.join(
                self.current_video_dir, current_item.text())
            self.done(QDialog.DialogCode.Accepted)
        else:
            QMessageBox.information(
                self, "Note", "You must select a video file to proceed")

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
                if f.endswith("_Annotations.csv"))

        dlg = QDialog(self)
        dlg.setWindowTitle("View Annotations")
        dlg.setStyleSheet(theme.dialog_stylesheet())
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
            QMessageBox.critical(
                parent_dlg, "Error",
                f"Failed to read annotations: {exc}")
            return

        if not state_ann and not point_ann:
            QMessageBox.information(
                parent_dlg, "No Annotations",
                "No annotations found to visualize.")
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
            QMessageBox.critical(
                parent_dlg, "Visualization Error",
                f"Failed to create visualization: {exc}")

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
            QMessageBox.critical(
                self, "Error",
                f"Failed to open Summary Statistics Manager: {exc}")

    def _show_summary_menu(self):
        # Scan for existing summary files
        ind_files, comb_files = [], []
        summary_base = os.path.join(self.output_dir, "Summary") if self.output_dir else ""
        ind_dir  = os.path.join(summary_base, "Individual_summaries")
        comb_dir = os.path.join(summary_base, "Combined_summaries")

        if os.path.isdir(ind_dir):
            ind_files = sorted(
                f for f in os.listdir(ind_dir) if f.endswith(".csv"))
        if os.path.isdir(comb_dir):
            comb_files = sorted(
                f for f in os.listdir(comb_dir) if f.endswith(".csv"))

        dlg = QDialog(self)
        dlg.setWindowTitle("Summary Statistics")
        dlg.setStyleSheet(theme.dialog_stylesheet())
        dlg.setModal(True)
        dlg.setMinimumWidth(420)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # ── Generate section ────────────────────────────────────────────
        gen_grp = QGroupBox("Generate")
        gen_lay = QVBoxLayout(gen_grp)
        gen_lay.setSpacing(6)
        gen_desc = QLabel(
            "Create individual or combined summary statistics\n"
            "from annotation files.")
        gen_desc.setWordWrap(True)
        gen_desc.setStyleSheet(
            f"color: {theme.color('text_secondary')}; background: transparent;")
        gen_lay.addWidget(gen_desc)
        gen_btn = QPushButton("Generate Statistics...")
        gen_lay.addWidget(gen_btn)
        layout.addWidget(gen_grp)

        # ── View Individual Summaries ────────────────────────────────────
        combo_ind = None
        view_ind_btn = None
        if ind_files:
            ind_grp = QGroupBox("Individual Summaries")
            ind_lay = QVBoxLayout(ind_grp)
            ind_lay.setSpacing(6)
            ind_desc = QLabel(
                f"{len(ind_files)} individual summary file"
                f"{'s' if len(ind_files) != 1 else ''} available.")
            ind_desc.setStyleSheet(
                f"color: {theme.color('text_secondary')}; background: transparent;")
            ind_lay.addWidget(ind_desc)
            row = QHBoxLayout()
            combo_ind = QComboBox()
            for fname in ind_files:
                title = fname.replace("_Summary.csv", "").replace("_", " ")
                combo_ind.addItem(title, os.path.join(ind_dir, fname))
            row.addWidget(combo_ind, 1)
            view_ind_btn = QPushButton("View")
            row.addWidget(view_ind_btn)
            ind_lay.addLayout(row)
            layout.addWidget(ind_grp)

        # ── View Combined Summaries ──────────────────────────────────────
        combo_comb = None
        view_comb_btn = None
        if comb_files:
            comb_grp = QGroupBox("Combined Summaries")
            comb_lay = QVBoxLayout(comb_grp)
            comb_lay.setSpacing(6)
            comb_desc = QLabel(
                f"{len(comb_files)} combined summary file"
                f"{'s' if len(comb_files) != 1 else ''} available.")
            comb_desc.setStyleSheet(
                f"color: {theme.color('text_secondary')}; background: transparent;")
            comb_lay.addWidget(comb_desc)
            row2 = QHBoxLayout()
            combo_comb = QComboBox()
            for fname in comb_files:
                title = (fname.replace("_Combined_Summary.csv", "")
                              .replace("_", " "))
                combo_comb.addItem(title, os.path.join(comb_dir, fname))
            row2.addWidget(combo_comb, 1)
            view_comb_btn = QPushButton("View")
            row2.addWidget(view_comb_btn)
            comb_lay.addLayout(row2)
            layout.addWidget(comb_grp)

        # ── Visualize section ────────────────────────────────────────────
        viz_grp = QGroupBox("Visualize")
        viz_lay = QVBoxLayout(viz_grp)
        viz_lay.setSpacing(6)
        viz_desc = QLabel(
            "View box plots of combined summary data across videos.")
        viz_desc.setWordWrap(True)
        viz_desc.setStyleSheet(
            f"color: {theme.color('text_secondary')}; background: transparent;")
        viz_lay.addWidget(viz_desc)
        boxplot_btn = QPushButton("Summary Box Plots...")
        viz_lay.addWidget(boxplot_btn)
        layout.addWidget(viz_grp)

        # ── Close ────────────────────────────────────────────────────────
        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # Wire up actions using a post-exec action slot so the dialog is
        # fully closed before secondary dialogs open.
        action = [None]

        gen_btn.clicked.connect(lambda: _set("generate"))
        if view_ind_btn:
            view_ind_btn.clicked.connect(lambda: _open_viewer(
                combo_ind.currentData(), combo_ind.currentText()))
        if view_comb_btn:
            view_comb_btn.clicked.connect(lambda: _open_viewer(
                combo_comb.currentData(), combo_comb.currentText()))
        boxplot_btn.clicked.connect(lambda: _set("boxplots"))

        def _open_viewer(path, title):
            show_table_viewer(dlg, path, title)

        def _set(val):
            action[0] = val
            dlg.accept()

        dlg.exec()

        # Execute chosen action after dialog is gone
        if action[0] == "generate":
            self._open_summary_statistics()
        elif action[0] == "boxplots":
            self._open_boxplot_viewer()

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

        self.setStyleSheet(theme.dialog_stylesheet())

        if self.parent():
            self.parent().setStyleSheet(theme.dialog_stylesheet())

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
