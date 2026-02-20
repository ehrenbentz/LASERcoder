import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QFrame, QMessageBox, QSplitter, QWidget, QInputDialog,
    QApplication, QFileDialog, QMenu,
)
from PySide6.QtCore import Qt, QTimer

from display_utils import get_screen_geometry, center_window
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
        summary_btn = QPushButton("Generate Summary Statistics")
        summary_btn.clicked.connect(self._open_summary_statistics)
        summary_layout.addWidget(summary_btn)
        layout.addWidget(summary_frame)

        self._populate_dir_list(self.initial_output_dir)

    def _setup_video_panel(self, layout):
        # Top row: label + settings gear pushed to the right
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(QLabel("Select Video File:"))
        top_row.addStretch()

        settings_btn = QPushButton("\u2699  Settings")
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
            self.video_file_listbox.addItems(files)
        except OSError:
            pass

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
    # Summary statistics
    # ------------------------------------------------------------------

    def _open_summary_statistics(self):
        from summary_statistics_manager import SummaryStatisticsManager

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

    # ------------------------------------------------------------------
    # Settings menu
    # ------------------------------------------------------------------

    def _show_settings_menu(self):
        from config_manager import ConfigManager

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

        cfg = ConfigManager()
        float_action = menu.addAction("Show Floating Controls")
        float_action.setCheckable(True)
        float_action.setChecked(cfg.get_show_floating_controls())
        float_action.triggered.connect(
            lambda checked: cfg.update_show_floating_controls(checked))

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _apply_theme(self, name):
        from config_manager import ConfigManager
        theme.load_theme(name)
        ConfigManager().update_theme(name)

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
