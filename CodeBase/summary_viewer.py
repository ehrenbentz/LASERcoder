import os
import csv

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QScrollArea, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QColorDialog, QSizePolicy, QFrame, QComboBox, QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, QSize, QMargins
from PySide6.QtGui import QColor, QBrush, QPainter, QPen, QPixmap, QIcon, QFont
from PySide6.QtCharts import (
    QChart, QChartView, QBoxPlotSeries, QBoxSet,
    QBarCategoryAxis, QValueAxis,
)

import theme
from display_utils import (get_screen_geometry, center_window,
                           generate_default_colors, make_color_icon,
                           is_os_junk)


# ---------------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------------

def _load_csv(path):
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))
    except (OSError, csv.Error):
        return []


# ===========================================================================
# Sortable table item (numeric-aware)
# ===========================================================================

class _NumericTableItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically when the text is a number."""

    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except (ValueError, TypeError):
            return self.text().lower() < other.text().lower()


# ===========================================================================
# 1.  Simple read-only spreadsheet viewer
# ===========================================================================

def show_table_viewer(parent, csv_path, title=None):
    """Open a plain read-only spreadsheet dialog for a summary CSV."""
    rows = _load_csv(csv_path)
    if not rows:
        theme.show_message(
            parent, "Empty File",
            f"No data found in:\n{os.path.basename(csv_path)}",
            icon="information")
        return

    clean = title or os.path.basename(csv_path).replace(".csv", "").replace("_", " ")
    dlg = _TableViewer(parent, rows, clean)
    dlg.exec()


class _TableViewer(QDialog):

    def __init__(self, parent, rows, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        theme.apply_dialog_theme(self)
        theme.stay_on_top(self)

        screen = get_screen_geometry()
        center_window(self,
                      int(screen["width"]  * 0.85),
                      int(screen["height"] * 0.80))
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        cols = list(rows[0].keys())
        table = QTableWidget(len(rows), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Expanding)

        for r, row in enumerate(rows):
            for c, col in enumerate(cols):
                text = str(row.get(col, ""))
                item = _NumericTableItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, item)

        table.setSortingEnabled(True)

        table.resizeColumnsToContents()
        # Add padding so text isn't cramped against column edges
        header = table.horizontalHeader()
        for c in range(len(cols)):
            header.resizeSection(c, header.sectionSize(c) + 20)
        header.setStretchLastSection(False)

        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# ===========================================================================
# 2.  Combined-summary bar chart viewer ("boxplots")
# ===========================================================================

# Numeric columns from individual summaries for box plots (per-video values)
_BOXPLOT_COLS = [
    ("Count",                   "Count"),
    ("Observations_per_minute", "Observations / min"),
    ("Total_Duration_seconds",  "Total Duration (s)"),
    ("Percent_Time",            "Percent Time (%)"),
]


def show_boxplot_viewer(parent, combined_dir):
    """Open the combined-summary box plot viewer."""
    dlg = _BoxplotViewer(parent, combined_dir)
    dlg.exec()


class _BoxplotViewer(QDialog):

    _BTN_STYLE = (
        "QPushButton { border: 1px solid grey; border-radius: 2px;"
        " padding: 0px; min-width: 20px; max-width: 20px;"
        " min-height: 20px; max-height: 20px; }"
        "QPushButton:hover { border: 1px solid white; }"
    )
    _ARROW_STYLE = (
        "QPushButton { border: none; padding: 0px;"
        " min-width: 18px; max-width: 18px;"
        " min-height: 14px; max-height: 14px; font-size: 10px; }"
        "QPushButton:hover { background-color: rgba(128,128,128,80); }"
    )

    def __init__(self, parent, combined_dir):
        super().__init__(parent)
        self._combined_dir = combined_dir
        self._ind_rows     = []       # rows from individual summaries (coded)
        self._whole_rows   = []       # rows recomputed for whole-video mode
        self._event_order  = []       # display order of events
        self._event_vis    = {}       # event -> bool (visible)
        self._col_vis      = {}       # col_key -> bool (visible)
        self._color_map    = {}       # event -> QColor
        self._color_btns   = {}       # event -> QPushButton
        self._chart_views  = []       # list of QChartView for export
        self._event_scroll_ref = [None]
        self._col_cbs      = {}       # col_key -> QCheckBox
        self._use_whole_video = False
        self._whole_computed = False   # lazily compute whole-video rows

        # Scan for combined summary CSVs (used for file selector labels)
        self._available = []
        if combined_dir and os.path.isdir(combined_dir):
            self._available = sorted(
                os.path.join(combined_dir, f)
                for f in os.listdir(combined_dir)
                if f.endswith(".csv") and not is_os_junk(f))

        # Individual summaries directory (sibling of Combined_summaries)
        self._ind_dir = ""
        self._ann_dir = ""
        if combined_dir:
            summary_base = os.path.dirname(combined_dir)
            self._ind_dir = os.path.join(summary_base, "Individual_summaries")
            self._ann_dir = os.path.join(
                os.path.dirname(summary_base), "Annotations")

        # Default all columns visible
        for col, _ in _BOXPLOT_COLS:
            self._col_vis[col] = True

        self.setWindowTitle("Summary Box Plots")
        theme.apply_dialog_theme(self)
        theme.stay_on_top(self)

        self.setMinimumSize(720, 520)
        self.showMaximized()

        self._build_ui()

        if self._available:
            self._load_file(0)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Left control panel (fixed width, internally scrollable) ─────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(260)
        left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_inner = QWidget()
        left_lay = QVBoxLayout(left_inner)
        left_lay.setContentsMargins(4, 4, 4, 4)
        left_lay.setSpacing(6)

        # ── File selector ────────────────────────────────────────────────
        file_box = QGroupBox("Summary File")
        file_lay = QVBoxLayout(file_box)
        self._file_combo = QComboBox()
        if not self._available:
            self._file_combo.addItem("No combined summaries found")
            self._file_combo.setEnabled(False)
        else:
            for path in self._available:
                label = (os.path.basename(path)
                         .replace("_Combined_Summary.csv", "")
                         .replace("_", " "))
                self._file_combo.addItem(label, path)
        self._file_combo.currentIndexChanged.connect(
            lambda idx: self._load_file(idx) if self._available else None)
        file_lay.addWidget(self._file_combo)
        left_lay.addWidget(file_box)

        # ── Calculate per ────────────────────────────────────────────────
        calc_box = QGroupBox("Calculate per")
        calc_lay = QVBoxLayout(calc_box)
        calc_lay.setContentsMargins(4, 4, 4, 4)
        calc_lay.setSpacing(2)

        self._calc_group = QButtonGroup(self)
        self._rb_coded = QRadioButton("Coded Segments")
        self._rb_whole = QRadioButton("Whole Videos")
        self._rb_coded.setChecked(True)
        self._calc_group.addButton(self._rb_coded, 0)
        self._calc_group.addButton(self._rb_whole, 1)
        self._calc_group.idToggled.connect(self._on_calc_mode_changed)
        calc_lay.addWidget(self._rb_coded)
        calc_lay.addWidget(self._rb_whole)
        left_lay.addWidget(calc_box)

        # ── Events (checkboxes + order + colours) ───────────────────────
        events_box = QGroupBox("Events")
        events_box_lay = QVBoxLayout(events_box)
        events_box_lay.setContentsMargins(4, 4, 4, 4)
        events_box_lay.setSpacing(2)

        # Select / Deselect All
        self._events_select_all = QCheckBox("Select All")
        self._events_select_all.setChecked(True)
        self._events_select_all.stateChanged.connect(
            self._on_events_select_all)
        events_box_lay.addWidget(self._events_select_all)

        self._events_scroll = QScrollArea()
        self._events_scroll.setWidgetResizable(True)
        self._events_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._events_scroll.setMinimumHeight(100)
        events_box_lay.addWidget(self._events_scroll)
        left_lay.addWidget(events_box, 1)

        # ── Columns (show / hide) ───────────────────────────────────────
        cols_box = QGroupBox("Columns")
        cols_lay = QVBoxLayout(cols_box)
        cols_lay.setContentsMargins(4, 4, 4, 4)
        cols_lay.setSpacing(2)

        self._cols_select_all = QCheckBox("Select All")
        self._cols_select_all.setChecked(True)
        self._cols_select_all.stateChanged.connect(
            self._on_cols_select_all)
        cols_lay.addWidget(self._cols_select_all)

        self._col_cbs.clear()
        for col, lbl in _BOXPLOT_COLS:
            cb = QCheckBox(lbl)
            cb.setChecked(True)
            cb.stateChanged.connect(
                lambda state, c=col: self._on_col_vis_changed(c, bool(state)))
            cols_lay.addWidget(cb)
            self._col_cbs[col] = cb
        left_lay.addWidget(cols_box)

        # ── Buttons ──────────────────────────────────────────────────────
        export_btn = QPushButton("Export...")
        export_btn.clicked.connect(self._export)
        left_lay.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        left_lay.addWidget(close_btn)

        left_scroll.setWidget(left_inner)
        outer.addWidget(left_scroll)

        # ── Right: figure scroll area ────────────────────────────────────
        self._fig_scroll = QScrollArea()
        self._fig_scroll.setWidgetResizable(True)
        self._fig_scroll.setWidget(
            self._msg_widget("Select a combined summary file to generate charts."))

        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.Shape.StyledPanel)
        right_lay = QVBoxLayout(right_frame)
        right_lay.setContentsMargins(4, 4, 4, 4)
        right_lay.addWidget(self._fig_scroll)
        outer.addWidget(right_frame, 1)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _load_file(self, index):
        if not self._available or index < 0 or index >= len(self._available):
            return
        comb_path = self._available[index]

        # Load combined summary to get the list of events
        comb_rows = _load_csv(comb_path)

        # Load all individual summary files for per-video distributions
        self._ind_rows = []
        if self._ind_dir and os.path.isdir(self._ind_dir):
            for fname in sorted(os.listdir(self._ind_dir)):
                if fname.endswith("_Summary.csv") and not is_os_junk(fname):
                    self._ind_rows.extend(
                        _load_csv(os.path.join(self._ind_dir, fname)))

        # Reset whole-video cache (recomputed lazily on demand)
        self._whole_rows = []
        self._whole_computed = False

        # Build event list from combined summary (authoritative event set)
        events = [r.get("Event", "") for r in comb_rows if r.get("Event")]
        new_order = []
        for e in events:
            if e not in new_order:
                new_order.append(e)
        self._event_order = new_order

        defaults = generate_default_colors(new_order)
        for e in new_order:
            if e not in self._color_map:
                self._color_map[e] = defaults[e]
            if e not in self._event_vis:
                self._event_vis[e] = True
        self._color_map = {e: c for e, c in self._color_map.items()
                           if e in new_order}
        self._event_vis = {e: v for e, v in self._event_vis.items()
                           if e in new_order}

        self._rebuild_event_list()
        self._generate()

    def _compute_whole_video_rows(self):
        """Recompute individual summary rows ignoring coding parameters."""
        if self._whole_computed:
            return
        self._whole_computed = True
        self._whole_rows = []

        if not self._ann_dir or not os.path.isdir(self._ann_dir):
            return

        from summary_statistics import compute_summary_rows

        for fname in sorted(os.listdir(self._ann_dir)):
            if fname.endswith("_Annotations.csv") and not is_os_junk(fname):
                path = os.path.join(self._ann_dir, fname)
                rows = compute_summary_rows(path, use_whole_video=True)
                if rows:
                    self._whole_rows.extend(rows)

    # ------------------------------------------------------------------
    # Calculate-per toggle
    # ------------------------------------------------------------------

    def _on_calc_mode_changed(self, btn_id, checked):
        if not checked:
            return
        self._use_whole_video = (btn_id == 1)
        if self._use_whole_video:
            self._compute_whole_video_rows()
        self._generate()

    # ------------------------------------------------------------------
    # Event list (checkboxes + arrows + colour swatches)
    # ------------------------------------------------------------------

    def _on_events_select_all(self, state):
        checked = bool(state)
        for e in self._event_order:
            self._event_vis[e] = checked
        self._rebuild_event_list()
        self._generate()

    def _rebuild_event_list(self):
        old = self._event_scroll_ref[0]
        if old is not None:
            old.setParent(None)
            old.deleteLater()

        container = QWidget()
        vlay = QVBoxLayout(container)
        vlay.setContentsMargins(2, 2, 2, 2)
        vlay.setSpacing(2)

        self._color_btns.clear()

        for idx, event in enumerate(self._event_order):
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(2)

            # Up / Down arrows
            arrow_col = QVBoxLayout()
            arrow_col.setContentsMargins(0, 0, 0, 0)
            arrow_col.setSpacing(0)

            up_btn = QPushButton("\u25b2")
            up_btn.setStyleSheet(self._ARROW_STYLE)
            up_btn.setEnabled(idx > 0)
            up_btn.clicked.connect(
                lambda _, e=event: self._move_event(e, -1))

            dn_btn = QPushButton("\u25bc")
            dn_btn.setStyleSheet(self._ARROW_STYLE)
            dn_btn.setEnabled(idx < len(self._event_order) - 1)
            dn_btn.clicked.connect(
                lambda _, e=event: self._move_event(e, 1))

            arrow_col.addWidget(up_btn)
            arrow_col.addWidget(dn_btn)
            row_l.addLayout(arrow_col)

            # Visibility checkbox
            cb = QCheckBox(event)
            cb.setChecked(self._event_vis.get(event, True))
            cb.stateChanged.connect(
                lambda state, e=event: self._on_vis_changed(e, bool(state)))
            row_l.addWidget(cb, 1)

            # Colour swatch
            color_btn = QPushButton()
            color_btn.setFixedSize(20, 20)
            color_btn.setStyleSheet(self._BTN_STYLE)
            color_btn.setIcon(make_color_icon(
                self._color_map.get(event, QColor("#888888"))))
            color_btn.setIconSize(QSize(16, 16))
            color_btn.clicked.connect(self._make_color_cb(event))
            self._color_btns[event] = color_btn
            row_l.addWidget(color_btn)

            vlay.addWidget(row_w)

        vlay.addStretch()
        self._events_scroll.setWidget(container)
        self._event_scroll_ref[0] = container

        # Sync the select-all checkbox state without triggering signals
        all_on = all(self._event_vis.get(e, True)
                     for e in self._event_order)
        self._events_select_all.blockSignals(True)
        self._events_select_all.setChecked(all_on)
        self._events_select_all.blockSignals(False)

    def _move_event(self, event, direction):
        idx = self._event_order.index(event)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._event_order):
            return
        self._event_order[idx], self._event_order[new_idx] = (
            self._event_order[new_idx], self._event_order[idx])
        self._rebuild_event_list()
        self._generate()

    def _on_vis_changed(self, event, visible):
        self._event_vis[event] = visible
        # Sync select-all without triggering its signal
        all_on = all(self._event_vis.get(e, True)
                     for e in self._event_order)
        self._events_select_all.blockSignals(True)
        self._events_select_all.setChecked(all_on)
        self._events_select_all.blockSignals(False)
        self._generate()

    # ------------------------------------------------------------------
    # Column visibility
    # ------------------------------------------------------------------

    def _on_cols_select_all(self, state):
        checked = bool(state)
        for col, _ in _BOXPLOT_COLS:
            self._col_vis[col] = checked
            self._col_cbs[col].blockSignals(True)
            self._col_cbs[col].setChecked(checked)
            self._col_cbs[col].blockSignals(False)
        self._generate()

    def _on_col_vis_changed(self, col, visible):
        self._col_vis[col] = visible
        all_on = all(self._col_vis.get(c, True) for c, _ in _BOXPLOT_COLS)
        self._cols_select_all.blockSignals(True)
        self._cols_select_all.setChecked(all_on)
        self._cols_select_all.blockSignals(False)
        self._generate()

    # ------------------------------------------------------------------
    # Figure generation — box plots from individual per-video data
    # ------------------------------------------------------------------

    @staticmethod
    def _msg_widget(text):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        return lbl

    def _set_fig_widget(self, widget):
        self._fig_scroll.setWidget(widget)

    def _active_rows(self):
        """Return the row set matching the current calculate-per mode."""
        if self._use_whole_video:
            return self._whole_rows
        return self._ind_rows

    @staticmethod
    def _compute_box_stats(values):
        """Return (lower_extreme, lower_quartile, median, upper_quartile,
        upper_extreme) for a list of floats, or None if too few values."""
        if not values:
            return None
        s = sorted(values)
        n = len(s)
        if n == 1:
            v = s[0]
            return (v, v, v, v, v)

        def _percentile(data, p):
            k = (len(data) - 1) * p / 100.0
            f = int(k)
            c = f + 1
            if c >= len(data):
                return data[f]
            return data[f] + (k - f) * (data[c] - data[f])

        q1 = _percentile(s, 25)
        med = _percentile(s, 50)
        q3 = _percentile(s, 75)
        iqr = q3 - q1
        lo = min(v for v in s if v >= q1 - 1.5 * iqr)
        hi = max(v for v in s if v <= q3 + 1.5 * iqr)
        return (lo, q1, med, q3, hi)

    def _generate(self):
        self._chart_views = []

        rows = self._active_rows()
        if not rows:
            self._set_fig_widget(
                self._msg_widget("No individual summary data found.\n"
                                 "Generate individual summaries first."))
            return

        visible_events = [e for e in self._event_order
                          if self._event_vis.get(e, True)]
        if not visible_events:
            self._set_fig_widget(
                self._msg_widget("No events selected. Check at least one event."))
            return

        # Build per-event value lists from individual summaries
        event_data = {e: {} for e in visible_events}
        for row in rows:
            ev = row.get("Event", "").strip()
            if ev not in event_data:
                continue
            for col, _ in _BOXPLOT_COLS:
                if not self._col_vis.get(col, True):
                    continue
                raw = row.get(col, "")
                if raw == "" or raw is None:
                    continue
                try:
                    event_data[ev].setdefault(col, []).append(float(raw))
                except (ValueError, TypeError):
                    pass

        # Filter to visible columns that have data
        plot_cols = []
        for col, lbl in _BOXPLOT_COLS:
            if not self._col_vis.get(col, True):
                continue
            if any(event_data.get(e, {}).get(col) for e in visible_events):
                plot_cols.append((col, lbl))

        if not plot_cols:
            self._set_fig_widget(
                self._msg_widget("No data for the selected events and columns."))
            return

        # Resolve theme colours for chart background / text
        chart_bg = QColor(theme.color("dialog_bg"))
        text_color = QColor(theme.color("text"))
        grid_color = QColor(theme.color("border"))
        grid_color.setAlpha(80)

        title_font = QFont("Arial", 14)
        title_font.setBold(True)
        label_font = QFont("Arial", 12)
        label_font.setBold(True)
        axis_pen = QPen(text_color, 2)

        container = QWidget()
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(0, 0, 0, 0)
        container_lay.setSpacing(40)

        for col, lbl in plot_cols:
            chart = QChart()
            chart.setTitle(lbl)
            chart.setTitleFont(title_font)
            chart.setTitleBrush(QBrush(text_color))
            chart.setBackgroundBrush(QBrush(chart_bg))
            chart.setMargins(QMargins(4, 4, 4, 20))
            chart.legend().setVisible(False)

            series = QBoxPlotSeries()
            categories = []
            y_min = float("inf")
            y_max = float("-inf")

            for e in visible_events:
                vals = event_data.get(e, {}).get(col, [])
                stats = self._compute_box_stats(vals)
                if stats is None:
                    continue

                categories.append(e)
                lo, q1, med, q3, hi = stats
                y_min = min(y_min, lo)
                y_max = max(y_max, hi)

                box = QBoxSet(e)
                box.setValue(0, lo)
                box.setValue(1, q1)
                box.setValue(2, med)
                box.setValue(3, q3)
                box.setValue(4, hi)

                clr = self._color_map.get(e, QColor("#888888"))
                box.setBrush(QBrush(clr))
                box.setPen(QPen(clr.darker(150), 1))
                series.append(box)

            if not categories:
                continue

            chart.addSeries(series)

            # Category axis (X)
            ax_x = QBarCategoryAxis()
            ax_x.append(categories)
            ax_x.setLabelsFont(label_font)
            ax_x.setLabelsColor(text_color)
            ax_x.setLabelsAngle(90)
            ax_x.setTruncateLabels(False)
            ax_x.setGridLineVisible(False)
            ax_x.setLinePen(axis_pen)
            chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)

            # Value axis (Y)
            margin = (y_max - y_min) * 0.08 if y_max > y_min else 1.0
            ax_y = QValueAxis()
            ax_y.setRange(y_min - margin, y_max + margin)
            ax_y.setTitleText(lbl)
            ax_y.setTitleFont(label_font)
            ax_y.setTitleBrush(QBrush(text_color))
            ax_y.setLabelsFont(label_font)
            ax_y.setLabelsColor(text_color)
            ax_y.setLinePen(axis_pen)
            ax_y.setGridLinePen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
            chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)

            series.attachAxis(ax_x)
            series.attachAxis(ax_y)

            view = QChartView(chart)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            view.setMinimumHeight(350)
            container_lay.addWidget(view)
            self._chart_views.append(view)

        container_lay.addStretch()
        self._set_fig_widget(container)

    # ------------------------------------------------------------------
    # Colour picking
    # ------------------------------------------------------------------

    def _make_color_cb(self, event_name):
        def _pick():
            current = self._color_map.get(event_name, QColor("#888888"))
            chosen = QColorDialog.getColor(
                current, self, f"Color for {event_name}")
            if chosen.isValid():
                self._color_map[event_name] = chosen
                btn = self._color_btns.get(event_name)
                if btn:
                    btn.setIcon(make_color_icon(chosen))
                self._generate()
        return _pick

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export(self):
        if not self._chart_views:
            theme.show_message(self, "No Figure",
                               "Generate a chart first before exporting.")
            return

        # Resolution picker
        dlg = QDialog(self)
        dlg.setWindowTitle("Export Options")
        theme.apply_dialog_theme(dlg)
        theme.stay_on_top(dlg)
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel("Resolution (DPI):"))
        dpi_combo = QComboBox()
        dpi_combo.addItem("300", 300)
        dpi_combo.addItem("600", 600)
        dpi_combo.addItem("900", 900)
        lay.addWidget(dpi_combo)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        dpi = dpi_combo.currentData()

        path, filt = QFileDialog.getSaveFileName(
            self, "Export Figure", "summary_charts.png",
            "PNG Images (*.png);;JPEG Images (*.jpg)")
        if not path:
            return

        fmt = "JPG" if "jpg" in filt.lower() else "PNG"
        if fmt == "JPG" and not path.lower().endswith(".jpg"):
            path += ".jpg"
        elif fmt == "PNG" and not path.lower().endswith(".png"):
            path += ".png"

        try:
            from PySide6.QtCore import QRect
            scale = dpi / 96.0
            w = max(v.width() for v in self._chart_views)
            scaled_w = int(w * scale)
            scaled_h_each = int(self._chart_views[0].height() * scale)
            total_h = scaled_h_each * len(self._chart_views)

            pm = QPixmap(scaled_w, total_h)
            pm.fill(QColor(theme.color("dialog_bg")))
            painter = QPainter(pm)
            y_off = 0
            for v in self._chart_views:
                target = QRect(0, y_off, scaled_w, scaled_h_each)
                v.render(painter, target)
                y_off += scaled_h_each
            painter.end()
            quality = 95 if fmt == "JPG" else -1
            pm.save(path, fmt, quality)
            theme.show_message(
                self, "Export Successful", f"Figure saved to:\n{path}",
                icon="information")
        except Exception as exc:
            theme.show_message(self, "Export Error", str(exc))
