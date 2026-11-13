import csv
from datetime import datetime
import json
import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QWidget,
    QCheckBox, QGridLayout, QSizePolicy, QAbstractItemView,
    QInputDialog, QApplication, QFileDialog, QMenu, QComboBox, QGroupBox,
    QRadioButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PySide6.QtCore import (Qt, QTimer, QSize, QThread, Signal, QDir,
                            QSortFilterProxyModel, QEvent)
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QPen

from display_utils import get_screen_geometry, center_window, is_os_junk
from platform_utils import is_network_drive
from annotation_store import (AnnotationStore, parse_time,
                              read_all_annotation_rows,
                              is_chunked_annotations_dir,
                              validate_import_csv)
from annotations_visualizer import show_visualization_dialog
from summary_statistics_manager import (SummaryStatisticsDialog,
                                        _video_name_for)
from summary_viewer import show_table_viewer
from config_manager import get_config
from video_probe import VideoLengthCache, VideoLengthProbe
from name_rules import folder_name_problem
from dialogs import show_message, get_text, show_colors_theme_dialog
import theme


class _FileOpWorker(QThread):
    """Run a blocking file operation (backup copy, delete) off the GUI
    thread so large project trees do not freeze the dialog."""

    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            self._fn()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit()


# Columns of the video list
_VIDEO_COLUMNS = ("Name", "Length", "Size", "Date Modified",
                  "Current Position")
_COL_NAME, _COL_LENGTH, _COL_SIZE, _COL_MODIFIED, _COL_POSITION = range(5)
# Per-column value the list sorts by (the visible text is formatted)
_SORT_ROLE = Qt.ItemDataRole.UserRole + 1
# Column 0: the video file(s) behind a row (several for multi-part)
_PATHS_ROLE = Qt.ItemDataRole.UserRole + 2


def _format_length(seconds):
    """Seconds as H:MM:SS, or M:SS under one hour."""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_size(size):
    value = float(size)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            break
        value /= 1024
    if unit == "bytes":
        return f"{int(value)} bytes"
    return f"{value:.1f} {unit}" if value < 100 else f"{value:.0f} {unit}"


class _VideoItem(QTreeWidgetItem):
    """Video list row that sorts by each column's underlying value
    (seconds, bytes, timestamp) instead of its formatted text."""

    def __lt__(self, other):
        tree = self.treeWidget()
        col = tree.sortColumn() if tree is not None else 0
        mine = self.data(col, _SORT_ROLE)
        theirs = other.data(col, _SORT_ROLE)
        if mine is not None and theirs is not None:
            try:
                return mine < theirs
            except TypeError:
                pass
        return self.text(col).lower() < other.text(col).lower()


class _PathEdit(QLineEdit):
    """Path field in which Tab completes the folder name being typed.

    Tab completes as far as the folders in the parent directory allow:
    to the full name when exactly one matches, or to the part that all
    matches share.  When there is nothing to add, Tab moves to the next
    control as usual.
    """

    def event(self, event):
        if (event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Tab
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
                and self._complete()):
            return True
        return super().event(event)

    def _complete(self):
        text = self.text()
        if not text.strip() or self.cursorPosition() != len(text):
            return False
        head, prefix = os.path.split(text)
        if not head or not os.path.isdir(head):
            return False
        try:
            names = [n for n in os.listdir(head)
                     if os.path.isdir(os.path.join(head, n))]
        except OSError:
            return False
        if not prefix:
            names = [n for n in names
                     if not n.startswith(".") and not is_os_junk(n)]
        low = prefix.lower()
        matches = sorted(n for n in names if n.lower().startswith(low))
        if not matches:
            return False
        if len(matches) == 1:
            completed = matches[0]
        else:
            shared = os.path.commonprefix([m.lower() for m in matches])
            if len(shared) <= len(prefix):
                return False
            completed = matches[0][:len(shared)]
        new_text = os.path.join(head, completed)
        if new_text == text:
            return False
        self.setText(new_text)
        return True


class _NoJunkProxy(QSortFilterProxyModel):
    """Hides hidden files and OS metadata (.DS_Store, ._*, Thumbs.db,
    desktop.ini, ...) in the non-native folder chooser, on every
    platform, regardless of the file's hidden attribute."""

    def filterAcceptsRow(self, source_row, source_parent):
        idx = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(idx)
        if not isinstance(name, str):
            return True
        return not (name.startswith(".") or is_os_junk(name))


class FilesManager(QDialog):
    """Dialog for selecting project directory and video file"""

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
        self.multi_part_files = None
        self.multi_part_video_name = None

        self._length_cache = None      # VideoLengthCache of the project
        self._length_probe = None      # running VideoLengthProbe, if any
        self._path_items = {}          # video file path -> its list rows

        self.initial_output_dir = os.path.abspath(initial_output_dir)
        self.initial_video_dir = os.path.abspath(initial_video_dir)
        self.current_video_dir = self.initial_video_dir
        self.output_dir = self.initial_output_dir

        self._screen = get_screen_geometry()

        self.setWindowTitle("LASERcoder - Select Project Directory and Video File")
        theme.apply_dialog_theme(self)

        if self.parent():
            self.parent().showMaximized()

        self._setup_ui()

        dialog_w = int(self._screen["width"] * 0.8)
        dialog_h = int(self._screen["height"] * 0.8)
        self.setMinimumSize(int(dialog_w * 0.8), int(dialog_h * 0.8))
        self.resize(dialog_w, dialog_h)

        QTimer.singleShot(500, lambda: self._warn_if_network_drive(
            self.output_dir, offer_move=True))


    # UI setup


    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # Directory rows span the full dialog width so that long paths
        # stay readable.  The path field always shows the directory in
        # use; there is no separate "selected" state.
        paths = QGridLayout()
        paths.setContentsMargins(0, 0, 0, 0)
        paths.setColumnStretch(1, 1)

        paths.addWidget(QLabel("Project Directory:"), 0, 0)
        self.output_dir_entry = _PathEdit(self.output_dir)
        self.output_dir_entry.setToolTip(self.output_dir)
        self.output_dir_entry.editingFinished.connect(
            self._on_output_dir_update)
        paths.addWidget(self.output_dir_entry, 0, 1)
        project_btn = QPushButton("Select Project Directory")
        project_btn.clicked.connect(self._browse_output_dir)
        paths.addWidget(project_btn, 0, 2)

        self._settings_btn = QPushButton("")
        self._settings_btn.setIcon(theme.themed_icon("settings"))
        self._settings_btn.setIconSize(QSize(16, 16))
        self._settings_btn.setFixedSize(26, 26)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.clicked.connect(self._show_settings_menu)
        paths.addWidget(self._settings_btn, 0, 3)

        paths.addWidget(QLabel("Video Directory:"), 1, 0)
        self.video_dir_entry = _PathEdit(self.current_video_dir)
        self.video_dir_entry.setToolTip(self.current_video_dir)
        self.video_dir_entry.editingFinished.connect(
            self._on_video_dir_update)
        paths.addWidget(self.video_dir_entry, 1, 1)
        video_btn = QPushButton("Select Video Directory")
        video_btn.clicked.connect(self._browse_video_dir)
        paths.addWidget(video_btn, 1, 2)

        main_layout.addLayout(paths)

        # Explicit single-file / multi-part choice, remembered between runs
        self.multi_part_checkbox = QCheckBox(
            "My videos are split into multiple parts "
            "(each subfolder is one video)")
        self.multi_part_checkbox.setChecked(get_config().get_multi_part_mode())
        self.multi_part_checkbox.toggled.connect(self._on_multi_part_toggled)
        main_layout.addWidget(self.multi_part_checkbox)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._build_action_panel())
        body.addWidget(self._build_video_panel(), 1)
        main_layout.addLayout(body, 1)

        # Enter in a path field must only apply that field.  Without
        # this, QDialog would also click its automatic default button.
        for btn in self.findChildren(QPushButton):
            btn.setAutoDefault(False)

        self._populate_file_list(self.current_video_dir)

    def _build_action_panel(self):
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Policy.Fixed,
                            QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        sections = [
            ("Annotations", [
                ("View Annotations", self._show_view_annotations),
                ("Import Annotations", self._show_import_annotations),
                ("Summary Statistics", self._show_summary_statistics),
                ("Export Annotations", self._show_export_annotations),
            ]),
            ("Project", [
                ("Backup Project", self._backup_project),
                ("Move Project", self._move_working_directory),
            ]),
        ]
        for title, buttons in sections:
            grp = QGroupBox(title)
            grp_lay = QVBoxLayout(grp)
            grp_lay.setSpacing(6)
            for text, slot in buttons:
                btn = QPushButton(text)
                btn.setMinimumWidth(190)
                btn.clicked.connect(slot)
                grp_lay.addWidget(btn)
            layout.addWidget(grp)

        layout.addStretch()
        return panel

    def _build_video_panel(self):
        # There is deliberately no folder tree here: double-clicking
        # through folders let a folder of separate videos be opened as
        # one multi-part video.
        file_panel = QFrame()
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(5, 5, 5, 5)
        file_layout.addWidget(QLabel("Select Video File:"))

        self.video_file_listbox = QTreeWidget()
        self.video_file_listbox.setColumnCount(len(_VIDEO_COLUMNS))
        self.video_file_listbox.setHeaderLabels(list(_VIDEO_COLUMNS))
        self.video_file_listbox.setRootIsDecorated(False)
        self.video_file_listbox.setUniformRowHeights(True)
        self.video_file_listbox.setAllColumnsShowFocus(True)
        # Every column can be resized by dragging the edge of its
        # header; the last one takes up whatever width is left over.
        # Starting widths are set when the dialog is first shown.
        header = self.video_file_listbox.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(False)
        header.setMinimumSectionSize(40)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._video_columns_sized = False
        # Click a column header to sort by it
        self.video_file_listbox.setSortingEnabled(True)
        self.video_file_listbox.sortByColumn(
            _COL_NAME, Qt.SortOrder.AscendingOrder)
        self._apply_video_list_style()
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
        hint = QLabel("Double-click a video, or select it and press Enter, "
                      "to open it")
        hint.setStyleSheet(
            f"color: {theme.color('text_secondary')};"
            " background: transparent; font-size: 11px;")
        legend.addWidget(hint)
        file_layout.addLayout(legend)

        return file_panel

    def _init_video_column_widths(self):
        """Starting column widths: each detail column fits its widest
        likely text and Name gets the rest of the list's width."""
        tree = self.video_file_listbox
        saved = get_config().get_video_column_widths()
        if saved and len(saved) == len(_VIDEO_COLUMNS):
            for col, width in enumerate(saved):
                tree.setColumnWidth(col, width)
            return
        metrics = tree.header().fontMetrics()
        samples = {
            _COL_LENGTH: "00:00:00",
            _COL_SIZE: "0000 bytes",
            _COL_MODIFIED: "0000-00-00 00:00",
            _COL_POSITION: "00:00:00",
        }
        others = 0
        for col, sample in samples.items():
            width = max(metrics.horizontalAdvance(sample),
                        metrics.horizontalAdvance(_VIDEO_COLUMNS[col])) + 36
            tree.setColumnWidth(col, width)
            others += width
        tree.setColumnWidth(
            _COL_NAME, max(200, tree.viewport().width() - others))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._video_columns_sized:
            self._video_columns_sized = True
            self._init_video_column_widths()

    def _apply_video_list_style(self):
        self.video_file_listbox.setStyleSheet(
            f"QTreeWidget {{ background-color: {theme.color('input_bg')};"
            f" color: {theme.color('text')};"
            f" border: 1px solid {theme.color('border')};"
            " border-radius: 3px; }"
            # No horizontal padding on the cells: each style adds its
            # own small text margin, which the header padding matches so
            # that cell text lines up under its column header.
            "QTreeWidget::item { padding: 2px 0px; }"
            "QTreeWidget::item:selected {"
            f" background-color: {theme.color('tree_selected')}; }}"
            "QTreeWidget::item:hover {"
            f" background-color: {theme.color('tree_hover')}; }}"
            "QHeaderView::section {"
            f" background-color: {theme.color('tree_header_bg')};"
            f" color: {theme.color('text')}; padding: 3px 6px 3px 3px;"
            " border: none;"
            f" border-bottom: 1px solid {theme.color('border_light')}; }}")


    # Directory selection


    def _set_project_directory(self, path, warn_network=True):
        """Make *path* the project directory.

        Every change of project directory goes through here, so the
        path field, the saved setting and the video status icons can
        never disagree with the directory in use.  Returns True when
        *path* was accepted.
        """
        path = os.path.normpath(path)
        if not os.path.isdir(path) or self._is_backup_dir(path):
            # Put the field back before any message box opens: the box
            # takes focus, which makes the field report editingFinished
            # a second time.
            self.output_dir_entry.setText(self.output_dir or "")
            if os.path.isdir(path):
                show_message(
                    self, "Backup Directory",
                    "This directory is a LASERcoder backup and "
                    "cannot be used as a project directory.")
            return False

        changed = path != self.output_dir
        self.output_dir = path
        self.output_dir_entry.setText(path)
        self.output_dir_entry.setToolTip(path)
        if changed:
            get_config().update_output_dir(path)
            # Status icons (and the legacy-layout migration) belong to
            # the project, so the video list is rebuilt for the new one.
            self._populate_file_list(self.current_video_dir)
            if warn_network:
                self._warn_if_network_drive(path)
        return True

    def _browse_output_dir(self):
        # The native chooser is used on purpose: it lets the user
        # create, rename and delete folders while picking one.
        start = (self.output_dir
                 if self.output_dir and os.path.isdir(self.output_dir)
                 else str(Path.home()))
        path = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", start,
            QFileDialog.Option.ShowDirsOnly)
        if path:
            self._set_project_directory(path)

    def _on_output_dir_update(self):
        path = self.output_dir_entry.text().strip()
        if not path or os.path.normpath(path) == self.output_dir:
            self.output_dir_entry.setText(self.output_dir or "")
            return
        self._set_project_directory(path)

    def _set_video_directory(self, path):
        """Show the videos in *path*.  Returns True when it was accepted."""
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            self.video_dir_entry.setText(self.current_video_dir)
            return False
        changed = path != self.current_video_dir
        self.current_video_dir = path
        self.video_dir_entry.setText(path)
        self.video_dir_entry.setToolTip(path)
        if changed:
            # Saved as soon as it is chosen, like the project directory,
            # so it is remembered even when no video is opened.
            get_config().set_video_dir(path)
            self._populate_file_list(path)
        return True

    def _browse_video_dir(self):
        path = self._pick_video_directory()
        if path:
            self._set_video_directory(path)

    def _pick_video_directory(self):
        """Folder chooser that also shows the video files inside each
        folder, so users can tell they are in the right place.

        The native pickers hide files (Windows) or grey them out
        inconsistently (macOS), so Qt's own dialog is used in directory
        mode without the dirs-only option: video files are listed but
        cannot be chosen, and the current folder is returned.
        """
        dlg = QFileDialog(self, "Select Video Directory",
                          self.current_video_dir)
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly, False)
        dlg.setOption(QFileDialog.Option.ReadOnly, True)
        dlg.setViewMode(QFileDialog.ViewMode.Detail)
        dlg.setLabelText(QFileDialog.DialogLabel.Accept, "Select Folder")
        # The corner resize grip is painted as a stray grey block under
        # the Cancel button on Windows; edges still resize the dialog.
        dlg.setSizeGripEnabled(False)
        # Show every ordinary file (no type filter, so the combo is not
        # needed) but never hidden or OS housekeeping entries: dotfiles,
        # Windows hidden/system files, Finder/Spotlight/thumbnail junk.
        dlg.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot)
        dlg.setProxyModel(_NoJunkProxy(dlg))
        for name in ("fileTypeLabel", "fileTypeCombo"):
            w = dlg.findChild(QWidget, name)
            if w is not None:
                w.hide()
        theme.apply_dialog_theme(dlg)
        dlg.resize(int(self._screen["width"] * 0.55),
                   int(self._screen["height"] * 0.6))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        selected = dlg.selectedFiles()
        path = selected[0] if selected else dlg.directory().absolutePath()
        if path and os.path.isfile(path):
            path = os.path.dirname(path)
        return path if path and os.path.isdir(path) else None

    def _on_multi_part_toggled(self, checked):
        get_config().set_multi_part_mode(checked)
        self._populate_file_list(self.current_video_dir)

    def _on_video_dir_update(self):
        path = self.video_dir_entry.text().strip()
        if not path or os.path.normpath(path) == self.current_video_dir:
            self.video_dir_entry.setText(self.current_video_dir)
            return
        self._set_video_directory(path)

    # List population


    def _list_videos(self, directory):
        """Video files directly inside *directory*, sorted."""
        extensions = tuple(ext.lower() for ext in self.file_types)
        try:
            return sorted(
                f for f in os.listdir(directory)
                if os.path.isfile(os.path.join(directory, f))
                and f.lower().endswith(extensions)
                and not is_os_junk(f))
        except OSError:
            return []

    def _list_video_folders(self, directory):
        """(folder name, [part file names]) for each subfolder of
        *directory* that holds at least one video file, sorted."""
        result = []
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return result
        for d in names:
            subdir = os.path.join(directory, d)
            if not os.path.isdir(subdir) or d.startswith(".") or is_os_junk(d):
                continue
            parts = self._list_videos(subdir)
            if parts:
                result.append((d, parts))
        return result

    def _populate_file_list(self, directory):
        """Fill the video list for the chosen folder.

        Single-file mode lists the video files in the folder.  Multi-part
        mode also lists each subfolder that contains video files as ONE
        video whose parts play back to back, so a project with a mix of
        single-file and multi-part recordings shows both.  Subfolders
        are never listed unless the box is ticked, so a folder of
        separate videos cannot be opened as one video by accident.

        Size and date come from the files, the current position from
        the project's session data, and the length from the project's
        length cache; lengths not yet known are read in the background
        and filled in as they arrive.
        """
        self._stop_length_probe()
        tree = self.video_file_listbox
        tree.setSortingEnabled(False)
        tree.clear()
        self._path_items = {}

        # Migrate old output layout before reading statuses
        if self.output_dir:
            from migration import migrate_output_dir_if_needed
            migrate_output_dir_if_needed(self.output_dir)

        if (self._length_cache is None
                or self._length_cache.output_dir != self.output_dir):
            # The Session folder is created for the cache if needed,
            # except in the home folder, which is only the placeholder
            # project directory before the user has chosen one.
            home = os.path.normcase(os.path.abspath(get_config().home_dir))
            is_home = (bool(self.output_dir) and os.path.normcase(
                os.path.abspath(self.output_dir)) == home)
            self._length_cache = VideoLengthCache(
                self.output_dir, create_session=not is_home)

        multi_part = self.multi_part_checkbox.isChecked()
        files = self._list_videos(directory)
        folders = self._list_video_folders(directory) if multi_part else []

        # Session folders are named after the video stem for single
        # files, but after the folder itself (verbatim, dots included)
        # for multi-part videos - see setup_manager.
        status_names = {f: os.path.splitext(f)[0] for f in files}
        status_names.update({d: d for d, _ in folders})
        statuses, positions = self._get_all_video_statuses(status_names)

        to_probe = []

        for fname in files:
            item = self._add_video_item(
                fname, [os.path.join(directory, fname)],
                positions.get(fname), to_probe)
            status = statuses.get(fname, "not_started")
            if status in ("complete", "in_progress"):
                item.setIcon(_COL_NAME, self._status_icon(status))

        for d, parts in folders:
            subdir = os.path.join(directory, d)
            n = len(parts)
            paths = [os.path.join(subdir, f) for f in parts]
            item = self._add_video_item(
                f"{d}  (\u29C9 {n} part{'s' if n != 1 else ''})",
                paths, positions.get(d), to_probe)
            item.setData(_COL_NAME, Qt.ItemDataRole.UserRole, {
                "type": "multi_part",
                "folder": subdir,
                "parts": paths,
            })
            status = statuses.get(d, "not_started")
            if status in ("complete", "in_progress"):
                item.setIcon(_COL_NAME, self._status_icon(status))
            else:
                item.setIcon(_COL_NAME, self._status_icon("multi_part"))

        tree.setSortingEnabled(True)

        if to_probe:
            probe = VideoLengthProbe(to_probe)
            probe.probed.connect(self._on_length_probed)
            probe.finished.connect(self._on_length_probe_finished)
            self._length_probe = probe
            probe.start()

    def _add_video_item(self, label, paths, position, to_probe):
        """Add one row for a video made of *paths* (one file, or the
        parts of a multi-part video).  Files whose length is not known
        yet are appended to *to_probe*."""
        item = _VideoItem(self.video_file_listbox)
        item.setText(_COL_NAME, label)
        item.setData(_COL_NAME, _SORT_ROLE, label.lower())
        item.setData(_COL_NAME, _PATHS_ROLE, paths)

        size, modified = 0, 0.0
        for path in paths:
            try:
                st = os.stat(path)
            except OSError:
                continue
            size += st.st_size
            modified = max(modified, st.st_mtime)
        item.setText(_COL_SIZE, _format_size(size))
        item.setData(_COL_SIZE, _SORT_ROLE, size)
        if modified:
            item.setText(_COL_MODIFIED, datetime.fromtimestamp(
                modified).strftime("%Y-%m-%d %H:%M"))
        item.setData(_COL_MODIFIED, _SORT_ROLE, modified)

        if position is not None:
            item.setText(_COL_POSITION, _format_length(position))
        item.setData(_COL_POSITION, _SORT_ROLE,
                     position if position is not None else -1.0)

        for path in paths:
            self._path_items.setdefault(path, []).append(item)
            if self._length_cache.get(path) is None:
                to_probe.append(path)
        self._refresh_item_length(item)
        return item

    def _refresh_item_length(self, item):
        """Show the row's length: the sum over its files once every one
        is known, "..." while any is still being read."""
        paths = item.data(_COL_NAME, _PATHS_ROLE) or []
        lengths = [self._length_cache.get(p) for p in paths]
        if any(v is None for v in lengths):
            text, key = "...", -1.0
        elif not lengths or any(v < 0 for v in lengths):
            text, key = "Unknown", -1.0
        else:
            key = float(sum(lengths))
            text = _format_length(key)
        item.setText(_COL_LENGTH, text)
        item.setData(_COL_LENGTH, _SORT_ROLE, key)

    def _on_length_probed(self, path, length):
        if self._length_cache is None:
            return
        self._length_cache.set(path, length)
        for item in self._path_items.get(path, []):
            self._refresh_item_length(item)

    def _on_length_probe_finished(self):
        if self._length_cache is not None:
            self._length_cache.save()
        if (self._length_probe is not None
                and self._length_probe.isFinished()):
            self._length_probe = None

    def _save_video_column_widths(self):
        if self._video_columns_sized:
            tree = self.video_file_listbox
            get_config().set_video_column_widths(
                [tree.columnWidth(c) for c in range(len(_VIDEO_COLUMNS))])

    def _stop_length_probe(self):
        """Stop the background length probe, keeping what it found."""
        probe = self._length_probe
        self._length_probe = None
        if probe is not None and probe.isRunning():
            probe.stop()
            probe.wait(3000)
        if self._length_cache is not None:
            self._length_cache.save()

    def _get_all_video_statuses(self, video_names):
        """Read the session state JSONs for all videos at once.

        *video_names* maps each list entry (file name or multi-part
        folder name) to the session folder / video name used on disk.
        Returns two dicts keyed by entry: its status ("complete" or
        "in_progress") and its saved playback position in seconds.
        Entries without a session appear in neither.
        """
        statuses, positions = {}, {}
        if not self.output_dir:
            return statuses, positions
        session_dir = os.path.join(self.output_dir, "Session")
        if not os.path.isdir(session_dir):
            return statuses, positions
        # Read all session state files in one pass
        try:
            video_dirs = {d for d in os.listdir(session_dir)
                          if not is_os_junk(d)}
        except OSError:
            return statuses, positions
        for fname, video_name in video_names.items():
            if video_name not in video_dirs:
                continue
            state_file = os.path.join(
                session_dir, video_name,
                f"{video_name}_session_state.json")
            if not os.path.isfile(state_file):
                continue
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "timestamp_sec" in data:
                    positions[fname] = float(data["timestamp_sec"])
                elif "timestamp_ms" in data:
                    positions[fname] = float(data["timestamp_ms"]) / 1000.0
                if data.get("completed"):
                    statuses[fname] = "complete"
                elif "timestamp_sec" in data or "timestamp_ms" in data:
                    # A saved playhead means a session exists.  The
                    # value itself may legitimately be 0 (video closed
                    # at the start), so test for presence, not truth.
                    statuses[fname] = "in_progress"
            except (json.JSONDecodeError, ValueError, TypeError, OSError):
                pass
        return statuses, positions

    @staticmethod
    def _status_icon(status):
        """Create a small colored circle icon for video status"""
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
        elif status == "multi_part":
            painter.setBrush(QColor("#2196F3"))
            painter.setPen(QPen(QColor("#1976D2"), 1))
            painter.drawRoundedRect(1, 4, 9, 7, 1, 1)
            painter.drawRoundedRect(4, 1, 9, 7, 1, 1)
        painter.end()
        return QIcon(pixmap)


    # Video context menu


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
            self.video_file_listbox.viewport().mapToGlobal(pos))
        if action is None:
            return

        item_data = item.data(_COL_NAME, Qt.ItemDataRole.UserRole)
        if item_data and item_data.get("type") == "multi_part":
            # Multi-part sessions are named after the folder verbatim
            video_name = os.path.basename(item_data["folder"])
        else:
            video_name = os.path.splitext(item.text(_COL_NAME))[0]
        if action == mark_complete:
            self._set_video_status(video_name, "complete")
        elif action == mark_progress:
            self._set_video_status(video_name, "in_progress")
        elif action == mark_clear:
            self._set_video_status(video_name, "clear")

    def _set_video_status(self, video_name, status):
        if not self.output_dir:
            show_message(
                self, "Warning",
                "Please select a project directory first.")
            return

        video_session_dir = os.path.join(
            self.output_dir, "Session", video_name)
        os.makedirs(video_session_dir, exist_ok=True)
        state_file = os.path.join(
            video_session_dir, f"{video_name}_session_state.json")

        if status == "clear":
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except OSError as exc:
                    show_message(
                        self, "Error",
                        f"Failed to remove session state: {exc}")
                    return
        else:
            # Load existing state or create a new one
            data = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as fh:
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
                with open(temp, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(temp, state_file)
            except OSError as exc:
                try:
                    os.remove(temp)
                except OSError:
                    pass
                show_message(
                    self, "Error",
                    f"Failed to update session state: {exc}")
                return

        self._populate_file_list(self.current_video_dir)


    # Backup guard


    def _is_backup_dir(self, path):
        """Return True if *path* is a backup directory"""
        if os.path.isfile(os.path.join(path, ".no_project")):
            return True
        return get_config().is_backup_dir(path)

    def _warn_if_network_drive(self, path, offer_move=False):
        """Show a warning if path is on a network drive. Returns True if network."""
        if not path or not is_network_drive(path):
            return False
        if offer_move:
            reply = show_message(
                self, "Network Drive Detected",
                "The selected directory appears to be on a network drive.\n\n"
                "LASERcoder uses atomic file writes that may not work "
                "reliably on network filesystems (SMB, NFS, etc.). "
                "This can lead to data loss or corrupted annotation files.\n\n"
                "Would you like to move the project to a local directory?",
                icon="question")
            if reply == QMessageBox.StandardButton.Yes:
                self._move_working_directory()
        else:
            show_message(
                self, "Network Drive Detected",
                "The selected directory appears to be on a network drive.\n\n"
                "LASERcoder uses atomic file writes that may not work "
                "reliably on network filesystems (SMB, NFS, etc.). "
                "This can lead to data loss or corrupted annotation files.\n\n"
                "Please use a local directory for your project directory.",
                icon="warning")
        return True


    # Backup project


    def _backup_project(self):
        if not self.output_dir:
            show_message(
                self, "Warning",
                "Please select a project directory first.")
            return

        dest_parent = QFileDialog.getExistingDirectory(
            self, "Select Backup Location", str(Path.home()),
            QFileDialog.Option.ShowDirsOnly)
        if not dest_parent:
            return

        default_name = os.path.basename(self.output_dir)
        name, ok = get_text(
            self, "Backup Name",
            "Enter a name for the backup folder:",
            text=default_name)
        if not ok or not name or not name.strip():
            return
        problem = folder_name_problem(name)
        if problem:
            show_message(self, "Invalid Name", problem)
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

        src_dir = self.output_dir

        def _on_done():
            # Mark the backup so it cannot be opened as a project
            try:
                marker = os.path.join(dest, ".no_project")
                with open(marker, "w", encoding="utf-8") as fh:
                    fh.write("This directory is a LASERcoder backup and "
                             "cannot be used as a project directory.\n")
            except OSError:
                pass

            get_config().add_backup_dir(dest)

            show_message(
                self, "Backup Complete",
                f"Project backed up to:\n{dest}",
                icon="information")

        def _on_error(msg):
            show_message(
                self, "Error", f"Backup failed: {msg}")

        self._run_file_op_async(
            lambda: shutil.copytree(src_dir, dest), _on_done, _on_error)

    def _run_file_op_async(self, fn, on_success, on_error):
        """Run a blocking file operation on a worker thread.

        The dialog is disabled and a wait cursor shown until the
        operation finishes, then *on_success* or *on_error* runs on the
        GUI thread.
        """
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.setEnabled(False)

        worker = _FileOpWorker(fn, parent=self)
        self._file_op_worker = worker

        def _finish():
            QApplication.restoreOverrideCursor()
            self.setEnabled(True)
            self._file_op_worker = None
            worker.deleteLater()

        def _ok():
            _finish()
            on_success()

        def _err(msg):
            _finish()
            on_error(msg)

        worker.succeeded.connect(_ok)
        worker.failed.connect(_err)
        worker.start()

    def _move_working_directory(self):
        if not self.output_dir or not os.path.isdir(self.output_dir):
            show_message(
                self, "Warning",
                "Please select a valid project directory first.")
            return

        dest = QFileDialog.getExistingDirectory(
            self, "Select New Location for Project",
            str(Path.home()), QFileDialog.Option.ShowDirsOnly)
        if not dest:
            return

        norm_dest = os.path.normpath(dest)
        norm_src = os.path.normpath(self.output_dir)

        if norm_dest == norm_src:
            show_message(
                self, "Same Location",
                "The destination is the same as the current location.")
            return

        if norm_dest.startswith(norm_src + os.sep):
            show_message(
                self, "Invalid Destination",
                "Cannot move a directory into a subdirectory of itself.",
                icon="warning")
            return

        self._warn_if_network_drive(dest)

        dir_name = os.path.basename(self.output_dir)
        dest_dir = os.path.join(dest, dir_name)

        if os.path.exists(dest_dir):
            show_message(
                self, "Destination Exists",
                f"A directory named '{dir_name}' already exists at the "
                "destination.\nPlease choose a different location.")
            return

        subdirs = ["Annotations", "Keys", "Session", "Debug"]

        try:
            os.makedirs(dest_dir)
        except OSError as exc:
            show_message(
                self, "Error",
                f"Could not create destination directory: {exc}")
            return

        moved = []
        try:
            for sub in subdirs:
                src = os.path.join(self.output_dir, sub)
                if os.path.isdir(src):
                    shutil.move(src, os.path.join(dest_dir, sub))
                    moved.append(sub)
        except OSError as exc:
            show_message(
                self, "Move Error",
                f"Error moving '{sub}': {exc}\n\n"
                f"Successfully moved: {', '.join(moved) if moved else 'none'}\n"
                f"The original directory has been partially moved.\n"
                f"Old location: {self.output_dir}\n"
                f"New location: {dest_dir}")
            return

        # The network-drive warning for the destination was shown above
        self._set_project_directory(dest_dir, warn_network=False)

        show_message(
            self, "Move Complete",
            f"Project moved successfully.\n\n"
            f"New location: {dest_dir}\n"
            f"Moved: {', '.join(moved) if moved else 'no subdirectories found'}",
            icon="information")


    # Video selection


    def _select_video_file(self, *_args):
        current_item = self.video_file_listbox.currentItem()
        if current_item:
            if not self.output_dir:
                show_message(
                    self, "Warning",
                    "Please select a project directory first using the "
                    "'Select Project Directory' button.")
                return
            if self._is_backup_dir(self.output_dir):
                show_message(
                    self, "Backup Directory",
                    "The selected project directory is a LASERcoder backup "
                    "and cannot be used as a project directory.\n\n"
                    "Please select a different project directory.")
                return
            item_data = current_item.data(
                _COL_NAME, Qt.ItemDataRole.UserRole)
            if item_data and item_data.get("type") == "multi_part":
                if not self._confirm_multi_part(item_data):
                    return
                self.multi_part_files = item_data["parts"]
                self.multi_part_video_name = os.path.basename(
                    item_data["folder"])
                self.selected_video_file = item_data["parts"][0]
            else:
                self.selected_video_file = os.path.join(
                    self.current_video_dir, current_item.text(_COL_NAME))
                self.multi_part_files = None
                self.multi_part_video_name = None
            self.done(QDialog.DialogCode.Accepted)
        else:
            show_message(
                self, "Note", "You must select a video file to proceed",
                icon="information")

    def _confirm_multi_part(self, item_data):
        """Before a multi-part folder is opened for the first time, show
        exactly which files will be joined, in order.  Skipped once the
        video has a session (the user already confirmed it)."""
        folder = os.path.basename(item_data["folder"])
        parts = item_data["parts"]
        if self.output_dir:
            state = os.path.join(
                self.output_dir, "Session", folder,
                f"{folder}_session_state.json")
            if os.path.isfile(state):
                return True
        shown = [os.path.basename(p) for p in parts[:8]]
        if len(parts) > len(shown):
            shown.append(f"... and {len(parts) - len(shown)} more")
        reply = show_message(
            self, "Open as One Multi-part Video?",
            f"\"{folder}\" will be opened as ONE continuous video made of "
            f"{len(parts)} file{'s' if len(parts) != 1 else ''}, played in "
            "this order:\n\n  " + "\n  ".join(shown)
            + "\n\nIf these are separate videos, choose No and open them "
            "one at a time from that folder instead.",
            icon="question")
        return reply == QMessageBox.StandardButton.Yes


    # View annotations


    def _show_view_annotations(self):
        ann_entries = _discover_annotations(self.output_dir)

        dlg = QDialog(self)
        dlg.setWindowTitle("View Annotations")
        theme.apply_dialog_theme(dlg)

        dlg.setMinimumWidth(400)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        grp = QGroupBox("Annotation Files")
        grp_lay = QVBoxLayout(grp)
        grp_lay.setSpacing(6)

        if ann_entries:
            desc = QLabel(
                f"{len(ann_entries)} annotation file"
                f"{'s' if len(ann_entries) != 1 else ''} found. "
                "Select a file to view.")
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent;")
            grp_lay.addWidget(desc)

            combo = QComboBox()
            for display_name, data_path in ann_entries:
                combo.addItem(display_name, data_path)
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
            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda: self._confirm_delete_annotations(
                dlg, combo.currentData(), combo.currentText()))
            btn_row_ann.addWidget(del_btn)
            grp_lay.addLayout(btn_row_ann)
        else:
            desc = QLabel(
                "No annotation files found in the selected project directory.")
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

        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.open()

    def _view_annotation_file(self, parent_dlg, path, title):
        rows = read_all_annotation_rows(path)
        if not rows:
            show_message(parent_dlg, "Empty",
                         "No annotation data found.")
            return
        import tempfile
        # Same encoding the table viewer reads with; the platform
        # default (cp1252 on Windows) breaks on non-ASCII notes/names.
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="",
            encoding="utf-8-sig")
        try:
            writer = csv.DictWriter(
                tmp, fieldnames=AnnotationStore.CSV_HEADERS)
            writer.writeheader()
            writer.writerows(rows)
            tmp.close()
            # The viewer loads the CSV into memory on open, so the
            # temp file can go right away instead of leaking per view.
            show_table_viewer(parent_dlg, tmp.name,
                              title + " Annotations")
        finally:
            tmp.close()
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    def _visualize_annotation_file(self, parent_dlg, path, title):
        state_ann, point_ann = [], []
        try:
            for row in read_all_annotation_rows(path):
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
                        "Subject": row.get("Subject", "").strip() or "NA",
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
                        "Subject": row.get("Subject", "").strip() or "NA",
                        "time": row.get("H_Start", "").strip(),
                        "raw_time": (float(raw)
                                     if raw and raw != "NA" else 0),
                        "Manual_Edit": row.get("Manual_Edit", "False"),
                        "Notes": row.get("Notes", ""),
                    })
        except Exception as exc:
            show_message(
                parent_dlg, "Error",
                f"Failed to read annotations: {exc}")
            return

        if not state_ann and not point_ann:
            show_message(
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
        if os.path.isdir(path):
            basename = os.path.basename(path)
            video_name = (os.path.basename(os.path.dirname(path))
                          if basename == "Chunks" else basename)
        else:
            video_name = (os.path.basename(path)
                          .removesuffix("_Annotations.csv")
                          .removesuffix("_Annotations"))
        # annotations_dir must be Session/VideoName/Chunks/ so
        # _session_state_path() resolves to Session/VideoName/
        chunks_dir = os.path.join(
            self.output_dir or "", "Session", video_name, "Chunks")
        store = AnnotationStore(
            video_name=video_name,
            annotations_dir=chunks_dir,
            full_annotations_file="",
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
            show_message(
                parent_dlg, "Visualization Error",
                f"Failed to create visualization: {exc}")


    # Delete annotations


    def _confirm_delete_annotations(self, parent_dlg,
                                    data_path, display_name):
        reply = show_message(
            parent_dlg, "Confirm Deletion",
            f"This will delete the annotations for "
            f"'{display_name}'.\n\nAre you sure?",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Derive video name from the path
        if os.path.isdir(data_path):
            basename = os.path.basename(data_path)
            video_name = (os.path.basename(os.path.dirname(data_path))
                          if basename == "Chunks" else basename)
        else:
            video_name = os.path.basename(data_path).removesuffix(
                "_Annotations.csv")

        # Remove annotation chunks (Session/{video}/Chunks/)
        if self.output_dir:
            chunks_dir = os.path.join(
                self.output_dir, "Session", video_name, "Chunks")
            if os.path.isdir(chunks_dir):
                try:
                    shutil.rmtree(chunks_dir)
                except OSError:
                    pass

        # Remove full annotations CSV
        if self.output_dir:
            full_csv = os.path.join(
                self.output_dir, "Annotations",
                f"{video_name}_Annotations.csv")
            if os.path.exists(full_csv):
                try:
                    os.remove(full_csv)
                except OSError:
                    pass

        # Remove session state and clean up session dir
        if self.output_dir:
            video_session_dir = os.path.join(
                self.output_dir, "Session", video_name)
            state_file = os.path.join(
                video_session_dir,
                f"{video_name}_session_state.json")
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except OSError:
                    pass
            # Remove video session dir if empty
            try:
                if (os.path.isdir(video_session_dir)
                        and not os.listdir(video_session_dir)):
                    os.rmdir(video_session_dir)
            except OSError:
                pass

        show_message(
            parent_dlg, "Deleted",
            f"Annotations for '{display_name}' have been deleted.",
            icon="information")

        # Refresh the video file list to update status icons
        self._populate_file_list(self.current_video_dir)

        parent_dlg.accept()


    # Import annotations


    def _show_import_annotations(self):
        if not self.output_dir:
            show_message(
                self, "No Project Directory",
                "Please select a project directory first.",
                icon="information")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Annotation CSV to Import",
            self.output_dir,
            "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return

        rows, video_names, error = validate_import_csv(file_path)
        if error:
            show_message(self, "Invalid File", error)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Import Annotations")
        theme.apply_dialog_theme(dlg)
        dlg.setMinimumWidth(450)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        file_label = QLabel(f"File: {os.path.basename(file_path)}")
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        video_list = sorted(video_names)
        count_label = QLabel(
            f"Found {len(rows)} annotation(s) for: "
            f"{', '.join(video_list)}")
        count_label.setWordWrap(True)
        count_label.setStyleSheet(
            f"color: {theme.color('text_secondary')};"
            " background: transparent;")
        layout.addWidget(count_label)

        target_grp = QGroupBox("Target Video")
        target_lay = QVBoxLayout(target_grp)

        combo = None
        if len(video_list) == 1:
            target_label = QLabel(video_list[0])
            target_lay.addWidget(target_label)
        else:
            combo = QComboBox()
            for name in video_list:
                combo.addItem(name)
            target_lay.addWidget(combo)
        layout.addWidget(target_grp)

        mode_grp = QGroupBox("Import Mode")
        mode_lay = QVBoxLayout(mode_grp)
        merge_radio = QRadioButton(
            "Merge — Combine with existing annotations (duplicates skipped)")
        merge_radio.setChecked(True)
        mode_lay.addWidget(merge_radio)
        replace_radio = QRadioButton(
            "Replace — Overwrite all existing annotations for this video")
        mode_lay.addWidget(replace_radio)
        layout.addWidget(mode_grp)

        layout.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(lambda: self._execute_import(
            dlg, rows,
            combo.currentText() if combo else video_list[0],
            "replace" if replace_radio.isChecked() else "merge"))
        btn_row.addWidget(import_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.open()

    def _execute_import(self, parent_dlg, all_rows, target_video, mode):
        filtered = [r for r in all_rows
                    if r.get("Video", "").strip() == target_video]
        if not filtered:
            show_message(
                parent_dlg, "No Matching Annotations",
                f"No annotations found for '{target_video}' "
                "in the selected file.")
            return

        chunks_dir = os.path.join(
            self.output_dir, "Session", target_video, "Chunks")
        has_existing = os.path.isdir(chunks_dir) and any(
            f.endswith(".csv") and "_chunk_" in f
            for f in os.listdir(chunks_dir))

        if mode == "replace" and has_existing:
            reply = show_message(
                parent_dlg, "Confirm Replace",
                f"This will replace all existing annotations for "
                f"'{target_video}'.\n\nThis cannot be undone. Continue?",
                icon="question")
            if reply != QMessageBox.StandardButton.Yes:
                return

        full_csv = os.path.join(
            self.output_dir, "Annotations",
            f"{target_video}_Annotations.csv")

        os.makedirs(chunks_dir, exist_ok=True)
        os.makedirs(os.path.dirname(full_csv), exist_ok=True)

        store = AnnotationStore(
            video_name=target_video,
            annotations_dir=chunks_dir,
            full_annotations_file=full_csv,
            event_key_file="",
            output_dir=self.output_dir)

        if mode == "merge":
            store.load_annotations()

        success, imported, skipped = store.import_annotations(
            filtered, mode)

        if success:
            msg = (f"Import complete.\n\n"
                   f"Imported {imported} annotation(s) "
                   f"for '{target_video}'.")
            if skipped > 0:
                msg += (f"\n{skipped} duplicate annotation(s) "
                        "were skipped.")
            show_message(parent_dlg, "Import Successful", msg,
                         icon="information")
            self._populate_file_list(self.current_video_dir)
            parent_dlg.accept()
        else:
            show_message(
                parent_dlg, "Import Failed",
                "Could not write annotations. "
                "Check folder permissions and try again.")


    # Export annotations


    def _show_export_annotations(self):
        ann_entries = _discover_annotations(self.output_dir)
        if not ann_entries:
            show_message(
                self, "No Annotations",
                "No annotation files found in the selected "
                "project directory.",
                icon="information")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Export Annotations")
        theme.apply_dialog_theme(dlg)
        dlg.setMinimumWidth(450)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        vid_grp = QGroupBox("Videos")
        vid_lay = QVBoxLayout(vid_grp)
        select_all = QCheckBox("Select All")
        select_all.setChecked(True)
        vid_lay.addWidget(select_all)

        video_list = QListWidget()
        video_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        for display_name, data_path in ann_entries:
            item = QListWidgetItem(display_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, data_path)
            video_list.addItem(item)
        vid_lay.addWidget(video_list)
        layout.addWidget(vid_grp, 1)

        def _toggle_all(checked):
            state = (Qt.CheckState.Checked if checked
                     else Qt.CheckState.Unchecked)
            for i in range(video_list.count()):
                video_list.item(i).setCheckState(state)

        select_all.toggled.connect(_toggle_all)

        out_grp = QGroupBox("Output")
        out_lay = QVBoxLayout(out_grp)
        combined_radio = QRadioButton("One combined CSV file")
        combined_radio.setChecked(True)
        out_lay.addWidget(combined_radio)
        per_video_radio = QRadioButton("One CSV file per video")
        out_lay.addWidget(per_video_radio)
        layout.addWidget(out_grp)

        def _export():
            checked = []
            for i in range(video_list.count()):
                item = video_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    checked.append(
                        (item.text(), item.data(Qt.ItemDataRole.UserRole)))
            self._execute_export(dlg, checked, combined_radio.isChecked())

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(_export)
        btn_row.addWidget(export_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.open()

    def _is_inside_project(self, path):
        """True when *path* lies inside the project directory."""
        if not self.output_dir:
            return False
        root = os.path.normcase(os.path.abspath(self.output_dir))
        target = os.path.normcase(os.path.abspath(path))
        return target == root or target.startswith(root + os.sep)

    def _execute_export(self, parent_dlg, entries, combined):
        """Write the annotations of *entries* ((display, path) pairs)
        to a location chosen by the user: one combined file, or one
        file per video."""
        if not entries:
            show_message(
                parent_dlg, "No Videos Selected",
                "Please select at least one video.")
            return

        home = str(Path.home())
        if combined or len(entries) == 1:
            if len(entries) == 1:
                default = f"{_video_name_for(entries[0][1])}_Annotations.csv"
            else:
                project = os.path.basename(self.output_dir or "") or "Project"
                default = f"{project}_Annotations_Combined.csv"
            dest, _ = QFileDialog.getSaveFileName(
                parent_dlg, "Export Annotations",
                os.path.join(home, default), "CSV Files (*.csv)")
            if not dest:
                return
            if not dest.lower().endswith(".csv"):
                dest += ".csv"
                if os.path.exists(dest):
                    reply = show_message(
                        parent_dlg, "File Exists",
                        f"'{os.path.basename(dest)}' already exists."
                        "\n\nOverwrite it?",
                        icon="question")
                    if reply != QMessageBox.StandardButton.Yes:
                        return
            jobs = [(os.path.normpath(dest), entries)]
        else:
            folder = QFileDialog.getExistingDirectory(
                parent_dlg, "Select Export Folder", home,
                QFileDialog.Option.ShowDirsOnly)
            if not folder:
                return
            jobs = [
                (os.path.normpath(os.path.join(
                    folder, f"{_video_name_for(path)}_Annotations.csv")),
                 [(display, path)])
                for display, path in entries]
            existing = [os.path.basename(d) for d, _ in jobs
                        if os.path.exists(d)]
            if existing:
                shown = existing[:8]
                if len(existing) > len(shown):
                    shown.append(
                        f"... and {len(existing) - len(shown)} more")
                reply = show_message(
                    parent_dlg, "Files Exist",
                    "These files already exist in the selected folder:"
                    "\n\n  " + "\n  ".join(shown)
                    + "\n\nOverwrite them?",
                    icon="question")
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # Files inside the project are LASERcoder's own working copies;
        # an export must never overwrite them.
        if any(self._is_inside_project(d) for d, _ in jobs):
            show_message(
                parent_dlg, "Choose Another Location",
                "Please export to a location outside the project "
                "directory. The files inside the project directory are "
                "managed by LASERcoder.")
            return

        written, empty, failed = [], [], []
        total_rows = 0
        for dest, group in jobs:
            rows = []
            for display, path in group:
                video_rows = read_all_annotation_rows(path)
                if not video_rows:
                    empty.append(display)
                    continue
                video_name = _video_name_for(path)
                for row in video_rows:
                    if not row.get("Video"):
                        row["Video"] = video_name
                rows.extend(video_rows)
            if not rows:
                continue
            try:
                _write_annotations_csv(dest, rows)
            except OSError as exc:
                failed.append((os.path.basename(dest), str(exc)))
                continue
            written.append(dest)
            total_rows += len(rows)

        if len(written) == 1:
            msg = (f"Exported {total_rows} annotation"
                   f"{'s' if total_rows != 1 else ''} to:\n{written[0]}")
        elif written:
            msg = (f"Exported {total_rows} annotations to {len(written)} "
                   f"files in:\n{os.path.dirname(written[0])}")
        else:
            msg = "No annotations were exported."
        if empty:
            msg += ("\n\nNo annotations were found for:\n"
                    + "\n".join(f"\u2022 {name}" for name in empty))
        if failed:
            msg += ("\n\nThese files could not be written:\n"
                    + "\n".join(f"\u2022 {name}: {err}"
                                for name, err in failed))

        if written and not failed:
            show_message(parent_dlg, "Export Complete", msg,
                         icon="information")
            parent_dlg.accept()
        else:
            show_message(parent_dlg, "Export Incomplete", msg)


    # Summary statistics


    def _show_summary_statistics(self):
        if not self.output_dir or not os.path.isdir(self.output_dir):
            show_message(
                self, "Warning",
                "Please select a project directory first.")
            return

        dlg = SummaryStatisticsDialog(
            self, self.output_dir, _discover_annotations(self.output_dir))
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.open()


    # Settings menu


    def _show_settings_menu(self):
        import time
        now_ms = int(time.monotonic() * 1000)
        if hasattr(self, '_settings_menu_closed_at') and now_ms - self._settings_menu_closed_at < 300:
            return

        menu = QMenu(self)
        menu.setStyleSheet(theme.menu_stylesheet())

        menu.addAction("Appearance").triggered.connect(
            self._show_colors_theme_dialog)

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
            self._settings_menu_closed_at = int(time.monotonic() * 1000)

    def _show_colors_theme_dialog(self):
        def _on_accept(_new_theme, _colors):
            app = QApplication.instance()
            app.setStyleSheet(theme.app_stylesheet())
            theme.apply_dialog_theme(self)
            self._settings_btn.setIcon(theme.themed_icon("settings"))
            self._apply_video_list_style()
            for w in app.topLevelWidgets():
                if hasattr(w, 'apply_theme'):
                    w.apply_theme()
        show_colors_theme_dialog(self, on_accept=_on_accept)


    # Key handling


    def closeEvent(self, event):
        # Never destroy the dialog while a background file operation
        # (backup copy, delete) is still running.
        worker = getattr(self, "_file_op_worker", None)
        if worker is not None and worker.isRunning():
            event.ignore()
            return
        self._stop_length_probe()
        self._save_video_column_widths()
        super().closeEvent(event)

    def done(self, result):
        # Accepting or rejecting the dialog ends the background length
        # probe; what it has found so far is kept.
        self._stop_length_probe()
        self._save_video_column_widths()
        super().done(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            if self.parent():
                QTimer.singleShot(0, self.parent().close)
            else:
                QTimer.singleShot(0, QApplication.quit)
        elif (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and self.video_file_listbox.hasFocus()
                and self.video_file_listbox.currentItem() is not None):
            # Enter on the highlighted video opens it.  The list leaves
            # the key unhandled on every platform, so it arrives here.
            self._select_video_file()
        else:
            super().keyPressEvent(event)


def _discover_annotations(output_dir):
    """Find annotation entries in the project directory.

    Searches two locations:
      1. Session/*/Chunks/ for chunked annotation directories
      2. Annotations/*_Annotations.csv for full CSV files

    Returns a sorted list of (display_name, data_path) tuples.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return []

    entries = []
    seen_names = set()

    # Chunked annotations under Session/*/Chunks/
    session_dir = os.path.join(output_dir, "Session")
    if os.path.isdir(session_dir):
        for name in os.listdir(session_dir):
            if is_os_junk(name):
                continue
            chunks_dir = os.path.join(session_dir, name, "Chunks")
            if is_chunked_annotations_dir(chunks_dir):
                display = name.replace("_", " ")
                entries.append((display, chunks_dir))
                seen_names.add(name)

    # Full CSV annotations under Annotations/
    ann_dir = os.path.join(output_dir, "Annotations")
    if os.path.isdir(ann_dir):
        for name in os.listdir(ann_dir):
            if (name.endswith("_Annotations.csv") and not is_os_junk(name)
                    and os.path.isfile(os.path.join(ann_dir, name))):
                video_name = name.removesuffix("_Annotations.csv")
                if video_name not in seen_names:
                    display = video_name.replace("_", " ")
                    entries.append((display, os.path.join(ann_dir, name)))

    entries.sort(key=lambda e: e[0].lower())
    return entries


def _write_annotations_csv(dest, rows):
    """Write annotation row dicts to *dest* atomically.

    Columns follow AnnotationStore.CSV_HEADERS; any extra column found
    in the rows (older files) is kept after them rather than dropped.
    Raises OSError on failure, leaving any existing *dest* untouched.
    """
    fieldnames = list(AnnotationStore.CSV_HEADERS)
    for row in rows:
        for key in row:
            if key and key not in fieldnames:
                fieldnames.append(key)

    temp = dest + ".tmp"
    try:
        with open(temp, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=fieldnames, extrasaction="ignore",
                restval="")
            writer.writeheader()
            writer.writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, dest)
    except OSError:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise
