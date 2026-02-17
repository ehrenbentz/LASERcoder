import os
import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QApplication, QListWidget, QFrame, QLineEdit, QCheckBox, QInputDialog,
    QAbstractItemView, QFileDialog, QListWidgetItem,
)
from PySide6.QtCore import Qt

from display_utils import get_screen_geometry, center_window
from summary_statistics import generate_summary_statistics, combine_summaries


class SummaryStatisticsManager(QDialog):
    """Dialog for generating and combining summary statistics."""

    def __init__(self, parent=None, initial_dir=str(Path.home())):
        super().__init__(parent)

        self.selected_files = []
        self.initial_dir = os.path.abspath(initial_dir)
        self.current_dir = self.initial_dir

        self.setWindowTitle("LaserTAG - Generate Summary Statistics")

        screen = get_screen_geometry()
        self._display_width = screen["width"]
        self._display_height = screen["height"]

        self._setup_ui()

        dialog_w = int(self._display_width * 0.4)
        dialog_h = int(self._display_height * 0.7)
        self.setMinimumSize(int(dialog_w * 0.4), int(dialog_h * 0.7))
        center_window(self, dialog_w, dialog_h, screen)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        main_layout.addWidget(self._create_directory_section())
        main_layout.addWidget(self._create_file_section(), 1)
        main_layout.addWidget(self._create_action_section())

    def _create_directory_section(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        header = QHBoxLayout()
        header.addWidget(QLabel("Select Directory with Annotation Files:"))
        header.addStretch()
        layout.addLayout(header)

        nav = QHBoxLayout()

        up_btn = QPushButton("\u2191")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(self._go_up)
        nav.addWidget(up_btn)

        self.dir_entry = QLineEdit(self.initial_dir)
        self.dir_entry.returnPressed.connect(self._on_dir_update)
        nav.addWidget(self.dir_entry)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_directory)
        nav.addWidget(browse_btn)

        layout.addLayout(nav)

        layout.addWidget(QLabel("Directories:"))
        self.dir_listbox = QListWidget()
        self.dir_listbox.itemDoubleClicked.connect(self._on_dir_double_click)
        layout.addWidget(self.dir_listbox)

        self._populate_dir_list(self.initial_dir)
        return frame

    def _create_file_section(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        header = QHBoxLayout()
        header.addWidget(QLabel("Select Annotation Files:"))

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.setTristate(False)
        self.select_all_checkbox.setChecked(False)
        self.select_all_checkbox.stateChanged.connect(self._toggle_select_all)
        header.addWidget(self.select_all_checkbox)

        header.addStretch()
        layout.addLayout(header)

        self.file_listbox = QListWidget()
        self.file_listbox.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.file_listbox.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.file_listbox)

        self._populate_file_list(self.initial_dir)
        return frame

    def _create_action_section(self):
        frame = QFrame()
        layout = QHBoxLayout(frame)

        individual_btn = QPushButton("Generate Individual Summaries")
        individual_btn.clicked.connect(self._generate_individual_summaries)
        layout.addWidget(individual_btn)

        combined_btn = QPushButton("Generate Combined Summary")
        combined_btn.clicked.connect(self._generate_combined_summary)
        layout.addWidget(combined_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        return frame

    # ------------------------------------------------------------------
    # Directory navigation
    # ------------------------------------------------------------------

    def _go_up(self):
        parent = os.path.dirname(self.current_dir)
        if os.path.exists(parent):
            self._navigate_to(parent)

    def _browse_directory(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.current_dir)
        if path:
            self._navigate_to(path)

    def _on_dir_update(self):
        path = self.dir_entry.text().strip()
        if os.path.isdir(path):
            self._navigate_to(path)

    def _on_dir_double_click(self, item):
        path = os.path.join(self.current_dir, item.text())
        if os.path.isdir(path):
            self._navigate_to(path)

    def _navigate_to(self, path):
        self.current_dir = path
        self.dir_entry.setText(path)
        self._populate_dir_list(path)
        self._populate_file_list(path)

    def _populate_dir_list(self, directory):
        self.dir_listbox.clear()
        try:
            dirs = sorted(
                d for d in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, d))
                and not d.startswith("."))
            self.dir_listbox.addItems(dirs)
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Error accessing directory: {exc}")

    def _populate_file_list(self, directory):
        self.file_listbox.clear()
        try:
            files = sorted(
                f for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
                and f.endswith("_Annotations.csv"))

            for name in files:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self.file_listbox.addItem(item)

            if files:
                self.select_all_checkbox.setChecked(True)
        except OSError as exc:
            QMessageBox.critical(
                self, "Error", f"Error accessing directory: {exc}")

    def _toggle_select_all(self, _state):
        checked = (Qt.CheckState.Checked if self.select_all_checkbox.isChecked()
                   else Qt.CheckState.Unchecked)
        for i in range(self.file_listbox.count()):
            self.file_listbox.item(i).setCheckState(checked)

    def _get_selected_files(self):
        selected = []
        for i in range(self.file_listbox.count()):
            item = self.file_listbox.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(os.path.join(self.current_dir, item.text()))
        return selected

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_individual_summaries(self):
        selected = self._get_selected_files()
        if not selected:
            QMessageBox.warning(
                self, "No Files Selected",
                "Please select at least one annotation file.")
            return

        base_dir = os.path.dirname(os.path.dirname(selected[0]))
        summary_dir = self._ensure_summary_dir(base_dir)
        if not summary_dir:
            return

        individual_dir = os.path.join(summary_dir, "Individual_summaries")
        try:
            os.makedirs(individual_dir, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self, "Error",
                f"Could not create Individual_summaries directory: {exc}")
            return

        success_count = 0
        failed, empty = [], []

        for path in selected:
            try:
                video_name = os.path.basename(path).replace(
                    "_Annotations.csv", "")
                out = os.path.join(individual_dir, f"{video_name}_Summary.csv")
                if generate_summary_statistics(path, out):
                    success_count += 1
                else:
                    empty.append(video_name)
            except Exception as exc:
                failed.append((os.path.basename(path), str(exc)))

        msg = f"Successfully generated {success_count} summary files"
        if empty:
            msg += "\n\nThe following files contained no observations:"
            for name in empty:
                msg += f"\n\u2022 {name}"
        if failed:
            msg += "\n\nThe following files could not be processed:"
            for name, err in failed:
                msg += f"\n\u2022 {name.replace('_Annotations.csv', '')}: {err}"
            QMessageBox.warning(self, "Processing Completed with Errors", msg)
        else:
            QMessageBox.information(self, "Processing Complete", msg)

        return success_count, empty, failed

    def _generate_combined_summary(self):
        selected = self._get_selected_files()
        if not selected:
            QMessageBox.warning(
                self, "No Files Selected",
                "Please select at least one annotation file.")
            return

        base_dir = os.path.dirname(os.path.dirname(selected[0]))
        summary_dir = self._ensure_summary_dir(base_dir)
        if not summary_dir:
            return

        combined_summaries_dir = os.path.join(summary_dir, "Combined_summaries")
        combined_annotations_dir = os.path.join(summary_dir, "Combined_Annotations")
        individual_dir = os.path.join(summary_dir, "Individual_summaries")

        for d in (combined_summaries_dir, combined_annotations_dir, individual_dir):
            try:
                os.makedirs(d, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(
                    self, "Error",
                    f"Could not create directory {os.path.basename(d)}: {exc}")
                return

        experiment_name, ok = QInputDialog.getText(
            self, "Experiment Name",
            "Enter a name for this experiment/analysis:")
        if not ok or not experiment_name:
            return
        experiment_name = "".join(
            c for c in experiment_name if c.isalnum() or c in " _-")

        # Locate existing individual summaries
        missing, existing = [], []
        for path in selected:
            video_name = os.path.basename(path).replace(
                "_Annotations.csv", "")
            individual_path = os.path.join(
                individual_dir, f"{video_name}_Summary.csv")
            old_path = os.path.join(summary_dir, f"{video_name}_Summary.csv")

            if os.path.exists(individual_path):
                existing.append(individual_path)
            elif os.path.exists(old_path):
                existing.append(old_path)
            else:
                missing.append((path, video_name))

        if missing:
            names = [n for _, n in missing]
            resp = QMessageBox.question(
                self, "Missing Summary Files",
                "Some summary files don't exist yet. Generate them first?\n\n"
                f"Missing: {', '.join(names)}",
                (QMessageBox.StandardButton.Yes
                 | QMessageBox.StandardButton.No
                 | QMessageBox.StandardButton.Cancel))

            if resp == QMessageBox.StandardButton.Cancel:
                return
            if resp == QMessageBox.StandardButton.Yes:
                empty, failed = [], []
                for path, video_name in missing:
                    try:
                        out = os.path.join(
                            individual_dir, f"{video_name}_Summary.csv")
                        result = generate_summary_statistics(path, out)
                        if result:
                            existing.append(result)
                        else:
                            empty.append(video_name)
                    except Exception as exc:
                        failed.append((video_name, str(exc)))

                if empty or failed:
                    msg = f"Generated {len(existing)} summaries."
                    if empty:
                        msg += "\n\nEmpty: " + ", ".join(empty)
                    if failed:
                        msg += "\n\nFailed: " + ", ".join(
                            f"{n}: {e}" for n, e in failed)
                    resp2 = QMessageBox.question(
                        self, "Some Files Could Not Be Processed",
                        f"{msg}\n\nContinue with available files?",
                        (QMessageBox.StandardButton.Yes
                         | QMessageBox.StandardButton.No))
                    if resp2 == QMessageBox.StandardButton.No:
                        return

        if not existing:
            QMessageBox.information(
                self, "No Summary Files",
                "No summary files found. "
                "Please use 'Generate Individual Summaries' first.")
            return

        try:
            combined_ann = self._combine_annotation_files(
                selected, experiment_name, combined_annotations_dir)
            combined_sum_path = os.path.join(
                combined_summaries_dir,
                f"{experiment_name}_Combined_Summary.csv")
            combine_summaries(existing, combined_sum_path)

            ann_name = (os.path.basename(combined_ann)
                        if combined_ann else "Could not be created")
            QMessageBox.information(
                self, "Combined Analysis",
                f"Combined Summary:\n{os.path.basename(combined_sum_path)}"
                f"\n\nCombined Annotations:\n{ann_name}")
        except Exception as exc:
            QMessageBox.critical(
                self, "Error",
                f"Error generating combined analysis: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _combine_annotation_files(self, file_paths, experiment_name,
                                  combined_annotations_dir):
        """Merge multiple annotation CSVs into a single file."""
        out_path = os.path.join(
            combined_annotations_dir,
            f"{experiment_name}_Annotations_Combined.csv")

        # Back up an existing file
        if os.path.exists(out_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = out_path.replace(".csv", f"_backup_{ts}.csv")
            try:
                os.rename(out_path, backup)
            except OSError:
                pass

        all_rows = []
        fieldnames = None
        failed = []

        for path in file_paths:
            try:
                with open(path, "r", newline="") as fh:
                    reader = csv.DictReader(fh)
                    rows = list(reader)
                    if not rows:
                        failed.append((os.path.basename(path), "File is empty"))
                        continue

                    if fieldnames is None:
                        fieldnames = reader.fieldnames

                    # Ensure Video column exists
                    for row in rows:
                        if not row.get("Video"):
                            row["Video"] = os.path.basename(path).replace(
                                "_Annotations.csv", "")

                    all_rows.extend(rows)
            except OSError as exc:
                failed.append((os.path.basename(path), str(exc)))

        if not all_rows or fieldnames is None:
            QMessageBox.critical(
                self, "Error", "No valid annotation files could be read.")
            return None

        try:
            temp = out_path + ".tmp"
            with open(temp, "w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            os.replace(temp, out_path)
            return out_path
        except OSError as exc:
            if os.path.exists(out_path + ".tmp"):
                try:
                    os.remove(out_path + ".tmp")
                except OSError:
                    pass
            QMessageBox.critical(
                self, "Error",
                f"Error saving combined annotations: {exc}")
            return None

    def _ensure_summary_dir(self, base_dir):
        summary_dir = os.path.join(base_dir, "Summary")
        try:
            os.makedirs(summary_dir, exist_ok=True)
            return summary_dir
        except OSError as exc:
            QMessageBox.critical(
                self, "Error",
                f"Could not create Summary directory: {exc}")
            return None
