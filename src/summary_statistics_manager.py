import os
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QApplication, QListWidget, QCheckBox, QComboBox, QGroupBox,
    QAbstractItemView, QListWidgetItem, QMenu,
)
from PySide6.QtCore import Qt, QEvent, QTimer

from display_utils import is_os_junk
from summary_statistics import (generate_summary_statistics,
                                combine_summaries, combined_summary_videos,
                                combined_summary_sidecar)
from summary_viewer import show_table_viewer, show_boxplot_viewer
from dialogs import show_message, get_text
import theme


_COMBINED_SUFFIX = "_Combined_Summary.csv"
_INDIVIDUAL_SUFFIX = "_Summary.csv"


def _video_name_for(path):
    """Video name for an annotation source: legacy CSV, a chunk folder,
    or a Session/{video}/Chunks folder (whose own basename is 'Chunks')."""
    if os.path.isdir(path):
        base = os.path.basename(path)
        if base == "Chunks":
            return os.path.basename(os.path.dirname(path))
        return base
    return os.path.basename(path).removesuffix("_Annotations.csv")


class SummaryStatisticsDialog(QDialog):
    """Generate and view summary statistics for one project.

    An experiment is a named set of videos.  Generating it writes a
    summary for each of its videos (Individual_Summaries) and one
    combined summary across them (Combined_Summaries); the table and
    box plot views read those files.
    """

    # The key labelled "delete" on Mac keyboards is Backspace
    _DELETE_KEYS = ((Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
                    if sys.platform == "darwin" else (Qt.Key.Key_Delete,))

    def __init__(self, parent, output_dir, ann_entries):
        """*ann_entries* is a list of (display_name, data_path) pairs for
        the annotated videos of the project in *output_dir*."""
        super().__init__(parent)

        self._entries = list(ann_entries)
        summary_dir = os.path.join(output_dir, "Annotations", "Summaries")
        self._ind_dir = os.path.join(summary_dir, "Individual_Summaries")
        self._comb_dir = os.path.join(summary_dir, "Combined_Summaries")

        self.setWindowTitle("Summary Statistics")
        theme.apply_dialog_theme(self)
        self.setMinimumWidth(460)

        self._setup_ui()
        self._reload_experiments()

    # UI setup

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        exp_grp = QGroupBox("Experiment")
        exp_lay = QVBoxLayout(exp_grp)
        self._exp_combo = QComboBox()
        self._exp_combo.setToolTip(
            "Right-click, or press Delete, to delete the selected "
            "experiment")
        self._exp_combo.currentIndexChanged.connect(
            self._on_experiment_changed)
        self._exp_combo.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._exp_combo.customContextMenuRequested.connect(
            lambda pos: self._show_experiment_menu(
                self._exp_combo.mapToGlobal(pos)))
        # Delete key and right-click, on the box and on its open list.
        # The list is fetched once, BEFORE any filter is installed, and
        # eventFilter only compares against these references: the box
        # creates its list on the first view() call and sends itself
        # events while doing so, so calling view() from the filter
        # recursed without end (a stack overflow on Windows).
        self._exp_view = self._exp_combo.view()
        self._exp_viewport = self._exp_view.viewport()
        self._exp_combo.installEventFilter(self)
        self._exp_view.installEventFilter(self)
        self._exp_viewport.installEventFilter(self)
        exp_lay.addWidget(self._exp_combo)
        layout.addWidget(exp_grp)

        self._generate_btn = QPushButton("Generate Summary")
        self._generate_btn.setEnabled(bool(self._entries))
        self._generate_btn.clicked.connect(self._generate)
        layout.addWidget(self._generate_btn)

        vid_grp = QGroupBox("Videos")
        vid_lay = QVBoxLayout(vid_grp)
        if self._entries:
            self._select_all = QCheckBox("Select All")
            self._select_all.setChecked(True)
            self._select_all.clicked.connect(self._toggle_select_all)
            vid_lay.addWidget(self._select_all)
        else:
            self._select_all = None
            note = QLabel(
                "No annotation files found in the selected "
                "project directory.")
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {theme.color('text_secondary')};"
                " background: transparent;")
            vid_lay.addWidget(note)

        self._video_list = QListWidget()
        self._video_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        for display_name, data_path in self._entries:
            item = QListWidgetItem(display_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, data_path)
            self._video_list.addItem(item)
        self._video_list.itemChanged.connect(self._sync_select_all)
        self._video_list.setVisible(bool(self._entries))
        vid_lay.addWidget(self._video_list)
        layout.addWidget(vid_grp, 1)

        res_grp = QGroupBox("Results")
        res_lay = QVBoxLayout(res_grp)
        self._table_combo = QComboBox()
        res_lay.addWidget(self._table_combo)
        # The two view buttons share one row at equal width
        view_row = QHBoxLayout()
        self._view_table_btn = QPushButton("View Table")
        self._view_table_btn.clicked.connect(self._view_table)
        view_row.addWidget(self._view_table_btn, 1)
        self._boxplot_btn = QPushButton("View Box Plots")
        self._boxplot_btn.clicked.connect(self._view_box_plots)
        view_row.addWidget(self._boxplot_btn, 1)
        res_lay.addLayout(view_row)
        layout.addWidget(res_grp)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        for btn in self.findChildren(QPushButton):
            btn.setAutoDefault(False)

    # Experiments

    def _experiment_names(self):
        if not os.path.isdir(self._comb_dir):
            return []
        return sorted(
            (f.removesuffix(_COMBINED_SUFFIX)
             for f in os.listdir(self._comb_dir)
             if f.endswith(_COMBINED_SUFFIX) and not is_os_junk(f)),
            key=str.lower)

    def _combined_path(self, experiment):
        return os.path.join(
            self._comb_dir, f"{experiment}{_COMBINED_SUFFIX}")

    def _current_experiment(self):
        """Name of the selected experiment, or None when there is none."""
        return self._exp_combo.currentData()

    def _reload_experiments(self, select=None):
        names = self._experiment_names()
        self._exp_combo.blockSignals(True)
        self._exp_combo.clear()
        for name in names:
            self._exp_combo.addItem(name.replace("_", " "), name)
        if not names:
            self._exp_combo.addItem("No experiments yet", None)
        self._exp_combo.setEnabled(bool(names))
        index = self._exp_combo.findData(select) if select else 0
        self._exp_combo.setCurrentIndex(max(index, 0))
        self._exp_combo.blockSignals(False)
        self._on_experiment_changed()

    def _on_experiment_changed(self, _index=None):
        experiment = self._current_experiment()

        # Tick the videos the experiment was built from.  With no
        # experiment, or one with no record of its videos, every video
        # is ticked.
        videos = (combined_summary_videos(self._combined_path(experiment))
                  if experiment else None)
        self._video_list.blockSignals(True)
        for i in range(self._video_list.count()):
            item = self._video_list.item(i)
            name = _video_name_for(item.data(Qt.ItemDataRole.UserRole))
            ticked = videos is None or name in videos
            item.setCheckState(Qt.CheckState.Checked if ticked
                               else Qt.CheckState.Unchecked)
        self._video_list.blockSignals(False)
        self._sync_select_all()
        self._update_results(experiment, videos)

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype not in (QEvent.Type.KeyPress,
                         QEvent.Type.MouseButtonPress):
            return super().eventFilter(obj, event)
        combo = self._exp_combo
        view = self._exp_view
        if (etype == QEvent.Type.KeyPress
                and (obj is combo or obj is view)
                and event.key() in self._DELETE_KEYS):
            if obj is view:
                index = view.currentIndex()
                combo.hidePopup()
                if index.isValid():
                    combo.setCurrentIndex(index.row())
            QTimer.singleShot(0, self._delete_experiment)
            return True
        if (obj is self._exp_viewport
                and etype == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton):
            # Right-click on an entry of the open list: select it, close
            # the list, then offer the menu.  The list itself would
            # treat the click as a plain selection.
            index = view.indexAt(event.position().toPoint())
            global_pos = event.globalPosition().toPoint()
            combo.hidePopup()
            if index.isValid():
                combo.setCurrentIndex(index.row())
            QTimer.singleShot(
                0, lambda: self._show_experiment_menu(global_pos))
            return True
        return super().eventFilter(obj, event)

    def _show_experiment_menu(self, global_pos):
        if not self._current_experiment():
            return
        menu = QMenu(self)
        menu.setStyleSheet(theme.menu_stylesheet())
        delete_action = menu.addAction("Delete Experiment")
        if menu.exec(global_pos) == delete_action:
            self._delete_experiment()

    def _update_results(self, experiment, videos):
        """Fill the Results section for *experiment* (None = none yet)."""
        self._table_combo.clear()
        has_results = bool(experiment) and os.path.isfile(
            self._combined_path(experiment))
        if has_results:
            self._table_combo.addItem(
                "Combined", self._combined_path(experiment))
            if os.path.isdir(self._ind_dir):
                for fname in sorted(os.listdir(self._ind_dir),
                                    key=str.lower):
                    if (not fname.endswith(_INDIVIDUAL_SUFFIX)
                            or is_os_junk(fname)):
                        continue
                    video = fname.removesuffix(_INDIVIDUAL_SUFFIX)
                    if videos is not None and video not in videos:
                        continue
                    self._table_combo.addItem(
                        video.replace("_", " "),
                        os.path.join(self._ind_dir, fname))
        self._table_combo.setEnabled(has_results)
        self._view_table_btn.setEnabled(has_results)
        self._boxplot_btn.setEnabled(has_results)

    def _remove_unused_individual(self, videos):
        """Delete the per-video summaries of *videos* that no experiment
        uses any more, so no summary is left behind that would never be
        regenerated.  Per-video summaries are shared between
        experiments; if any experiment has no record of its videos,
        everything is kept."""
        still_used = set()
        for name in self._experiment_names():
            used = combined_summary_videos(self._combined_path(name))
            if used is None:
                return
            still_used |= used
        for video in set(videos) - still_used:
            try:
                os.remove(os.path.join(
                    self._ind_dir, f"{video}{_INDIVIDUAL_SUFFIX}"))
            except OSError:
                pass

    def _delete_experiment(self):
        """Delete the selected experiment's combined summary, and the
        per-video summaries that no other experiment uses.  Annotations
        are never touched."""
        experiment = self._current_experiment()
        if not experiment:
            return
        reply = show_message(
            self, "Delete Experiment",
            f"Delete the summary statistics for "
            f"'{experiment.replace('_', ' ')}'?\n\n"
            "Annotations are not affected. The summary can be "
            "generated again at any time.",
            icon="question")
        if reply != QMessageBox.StandardButton.Yes:
            return

        combined_path = self._combined_path(experiment)
        videos = combined_summary_videos(combined_path)
        try:
            os.remove(combined_path)
        except OSError as exc:
            show_message(
                self, "Error",
                f"Could not delete the combined summary: {exc}")
            return
        try:
            os.remove(combined_summary_sidecar(combined_path))
        except OSError:
            pass

        if videos:
            self._remove_unused_individual(videos)

        self._reload_experiments()

    # Video checklist

    def _toggle_select_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._video_list.blockSignals(True)
        for i in range(self._video_list.count()):
            self._video_list.item(i).setCheckState(state)
        self._video_list.blockSignals(False)

    def _sync_select_all(self, _item=None):
        if self._select_all is None:
            return
        count = self._video_list.count()
        self._select_all.setChecked(count > 0 and all(
            self._video_list.item(i).checkState() == Qt.CheckState.Checked
            for i in range(count)))

    def _checked_paths(self):
        paths = []
        for i in range(self._video_list.count()):
            item = self._video_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    # Generation

    def _generate(self):
        """Ask for the experiment name, write a summary for every ticked
        video, then the combined summary of the experiment from those.

        The name is pre-filled with the selected experiment: keeping it
        updates that experiment, changing it creates another."""
        selected = self._checked_paths()
        if not selected:
            show_message(
                self, "No Videos Selected",
                "Please select at least one video.")
            return

        current = self._current_experiment()
        name, ok = get_text(
            self, "Experiment Name",
            "Enter a name for this experiment:", text=current or "")
        if not ok:
            return
        experiment = "".join(
            c for c in name if c.isalnum() or c in " _-").strip()
        if not experiment:
            show_message(
                self, "Experiment Name",
                "Please enter a name for the experiment.")
            return

        combined_path = self._combined_path(experiment)
        if experiment != current and os.path.exists(combined_path):
            reply = show_message(
                self, "Summary Exists",
                f"A combined summary named '{experiment}' "
                "already exists.\n\nOverwrite it?",
                icon="question")
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Videos the experiment was built from before this run
        previous_videos = (combined_summary_videos(combined_path)
                           if os.path.exists(combined_path) else None)

        try:
            os.makedirs(self._ind_dir, exist_ok=True)
            os.makedirs(self._comb_dir, exist_ok=True)
        except OSError as exc:
            show_message(
                self, "Error",
                f"Could not create the Summaries directory: {exc}")
            return

        # Individual summaries are always regenerated from the current
        # annotations, never reused: a reused file would leave out
        # anything annotated since it was written.
        ind_paths, empty, failed = [], [], []
        combine_error = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in selected:
                video_name = _video_name_for(path)
                out = os.path.join(
                    self._ind_dir, f"{video_name}{_INDIVIDUAL_SUFFIX}")
                try:
                    result = generate_summary_statistics(path, out)
                except Exception as exc:
                    failed.append((video_name, str(exc)))
                    continue
                if result:
                    ind_paths.append(result)
                else:
                    empty.append(video_name)

            if ind_paths:
                try:
                    if not combine_summaries(ind_paths, combined_path):
                        combine_error = "the summaries contained no data"
                except Exception as exc:
                    combine_error = str(exc)
        finally:
            QApplication.restoreOverrideCursor()

        details = ""
        if empty:
            details += ("\n\nThese videos contained no observations:\n"
                        + "\n".join(f"• {n}" for n in empty))
        if failed:
            details += ("\n\nThese videos could not be processed:\n"
                        + "\n".join(f"• {n}: {e}" for n, e in failed))

        if not ind_paths:
            show_message(
                self, "No Summaries",
                "No summaries could be generated." + details)
            return
        if combine_error:
            show_message(
                self, "Error",
                f"Could not write the combined summary: {combine_error}"
                + details)
            return

        # A video dropped from the experiment would otherwise keep a
        # per-video summary that is never updated again.
        if previous_videos:
            self._remove_unused_individual(previous_videos)

        self._reload_experiments(select=experiment)
        count = len(ind_paths)
        show_message(
            self, "Summary Complete",
            f"Summarized {count} video{'s' if count != 1 else ''} "
            f"for '{experiment.replace('_', ' ')}'." + details,
            icon="warning" if (empty or failed) else "information")

    # Viewing

    def _view_table(self):
        path = self._table_combo.currentData()
        if not path:
            return
        title = self._exp_combo.currentText()
        if self._table_combo.currentIndex() > 0:
            title = self._table_combo.currentText()
        show_table_viewer(self, path, f"{title} Summary")

    def _view_box_plots(self):
        experiment = self._current_experiment()
        if not experiment:
            return
        show_boxplot_viewer(
            self, self._comb_dir,
            select_file=self._combined_path(experiment))
