
import os
import sys
import csv
import types
import locale


from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Signal
from mpv import MpvRenderContext

import ctypes

# Define at module level, above the class
_GL_GET_PROC_ADDR = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)

import mpv
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox,
    QAbstractItemView, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QPoint, QEvent, QSysInfo
from PySide6.QtGui import QColor

from display_utils import get_screen_geometry, center_window
from progress_bar import ProgressBarWithText
from annotation_store import (
    AnnotationStore, format_time_human, format_time_machine, parse_time,
)
from floating_controls import (
    create_toggle_buttons, toggle_floating_controls,
    toggle_behavior_buttons, update_floating_visibility,
)
from dialogs import (
    show_coding_start_dialog, show_note_dialog, show_annotation_details,
    show_comprehensive_edit, show_edit_point_dialog, show_edit_state_dialog,
)


class MpvOpenGLWidget(QOpenGLWidget):
    """OpenGL widget that lets libmpv render frames into a Qt GL surface."""

    _frame_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.render_ctx = None
        self._frame_ready.connect(self.update)

    def init_mpv_render(self, player):
        """Create the mpv render context. Widget must be visible first."""
        self.player = player

        # Force Qt to create the native window and GL context
        self.show()
        QApplication.processEvents()

        self.makeCurrent()

        glctx = self.context()
        if glctx is None:
            raise RuntimeError("Failed to create OpenGL context")

        def get_proc_address(_ctx, name):
            if isinstance(name, str):
                name = name.encode("utf-8")
            addr = glctx.getProcAddress(name)
            if addr is None:
                return 0
            return int(addr)

        self._proc_addr_func = _GL_GET_PROC_ADDR(get_proc_address)

        # Temporary debug: check that GL functions resolve
        test_addr = glctx.getProcAddress(b"glGetString")
        print(f"GL context valid: {glctx is not None}, glGetString addr: {test_addr}, type: {type(test_addr)}")

        self.render_ctx = MpvRenderContext(
            self.player, "opengl",
            opengl_init_params={"get_proc_address": self._proc_addr_func},
        )
        self.render_ctx.update_cb = self._on_mpv_frame_ready
        self.doneCurrent()

    def _on_mpv_frame_ready(self):
        """Called from mpv's decoder thread. Emit signal to repaint on GUI thread."""
        self._frame_ready.emit()

    def initializeGL(self):
        pass

    def paintGL(self):
        if self.render_ctx is None:
            return
        ratio = self.devicePixelRatioF()
        w = int(self.width() * ratio)
        h = int(self.height() * ratio)
        fbo = self.defaultFramebufferObject()
        self.render_ctx.render(
            flip_y=True,
            opengl_fbo={"fbo": fbo, "w": w, "h": h},
        )

    def cleanup(self):
        """Free the render context. Must be called before destroying the player."""
        if self.render_ctx:
            self.render_ctx.update_cb = None
            self.makeCurrent()
            self.render_ctx.free()
            self.render_ctx = None
            self.doneCurrent()

class VideoAnnotator(QFrame):
    """
    Main video annotator widget.

    """

    def __init__(self, parent, video_path, session_state_file,
                 behavior_key_file, output_dir):
        super().__init__(parent)

        self.parent = parent
        self.video_path = video_path
        self.behavior_key_file = behavior_key_file
        self.output_dir = output_dir
        self.floating_windows = []
        self.progress_timer = None
        self.current_os = QSysInfo.productType().lower()

        # UI selection state
        self.dialog_open = False
        self.pressed_keys = set()
        self.selected_treeview = None
        self.selected_item = None
        self.selected_index = None
        self.undo_stack = []

        # Coding parameters
        self.coding_start = 0
        self.coding_duration = None
        self.coding_end = None
        self.coding_end_reached = False
        self.active_state_behaviors = {}
        self.used_point_behaviors = set()

        # File paths
        self.video_name = os.path.basename(video_path).split(".")[0]
        annotations_dir = os.path.join(output_dir, "Annotations")
        annotations_file = os.path.join(
            annotations_dir, f"{self.video_name}_Annotations.csv")

        # Data layer
        self.store = AnnotationStore(
            video_name=self.video_name,
            annotations_file=annotations_file,
            session_state_file=session_state_file,
            behavior_key_file=behavior_key_file,
            output_dir=output_dir,
        )

        # Screen geometry
        screen = get_screen_geometry()
        self.app = QApplication.instance()
        self.display_width = screen["width"]
        self.display_height = screen["height"]

        self.parent.setWindowTitle(f"LaserTag  {video_path}")
        self.parent.setGeometry(
            screen["x"], screen["y"], screen["width"], screen["height"])
        self.parent.showMaximized()

        # Layout measurements
        self.panel_width = int(self.display_width * 0.2)
        self.panel_height = int(self.display_height) - int(self.display_height * 0.1)
        self.progress_bar_height = int(self.display_height * 0.025)
        self.video_width = self.display_width - self.panel_width
        self.video_height = self.panel_height
        self.progress_bar_width = self.video_width

        # Build UI
        self._setup_layout()
        self._create_video_frame()
        create_toggle_buttons(self)
        self._create_progress_bar()
        self._create_annotation_panel()
        self._setup_key_bindings()
        self.app.installEventFilter(self)
        self._init_mpv_player()
        self._load_data_and_start()

        self.state_annotations_tree.itemSelectionChanged.connect(
            self._on_state_item_selected)
        self.point_annotations_tree.itemSelectionChanged.connect(
            self._on_point_item_selected)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_layout(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.left_container = QWidget()
        self.left_layout = QVBoxLayout(self.left_container)
        self.left_layout.setSpacing(0)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.left_container)

        self.right_container = QWidget()
        self.right_container.setFixedWidth(self.panel_width)
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setSpacing(3)
        self.right_layout.setContentsMargins(3, 0, 3, 0)
        self.main_layout.addWidget(self.right_container)

    def _create_video_frame(self):
        self.video_frame = QFrame()
        self.video_frame.setFixedSize(self.video_width, self.video_height)

        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        self.gl_widget = MpvOpenGLWidget(self.video_frame)
        video_layout.addWidget(self.gl_widget)

        self.left_layout.addWidget(self.video_frame)

    # ------------------------------------------------------------------
    # Progress bar
    # ------------------------------------------------------------------

    def _create_progress_bar(self):
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("background-color: black;")
        self.progress_frame.setFixedSize(
            self.progress_bar_width, self.progress_bar_height + 20)

        frame_layout = QVBoxLayout(self.progress_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.coding_info_label = QLabel()
        self.coding_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.coding_info_label.setStyleSheet(
            "color: white; font-size: 10px; padding-right: 10px; margin: 0;")
        self.coding_info_label.setFixedHeight(20)
        frame_layout.addWidget(self.coding_info_label)

        self.progress_bar = ProgressBarWithText(
            self.progress_frame, annotator=self)
        self.progress_bar.setFixedSize(
            self.progress_bar_width, self.progress_bar_height)
        frame_layout.addWidget(self.progress_bar)

        self.left_layout.addWidget(self.progress_frame)
        self.left_container.setStyleSheet("background-color: black;")
        self.update_coding_info_display()

    def update_progress(self):
        total = self.player.duration or 0
        current = self.player.time_pos or 0

        if total <= 0:
            return

        self.progress_bar.set_progress(current / total)
        self.progress_bar.set_left_text(format_time_human(current))
        self.progress_bar.set_center_text(f"({self.player.speed:.1f}x)")
        self.progress_bar.set_right_text(format_time_human(total))

        # Check coding-end
        if (self.coding_duration is not None
                and self.coding_start is not None
                and current >= self.coding_start + self.coding_duration
                and not self.coding_end_reached
                and not self.player.pause):
            self.coding_end_reached = True
            self.player.pause = True
            self._auto_saving = True
            self.save_session_state()
            self._auto_saving = False
            self._show_coding_end_prompt(current)

    def _show_coding_end_prompt(self, current_sec):
        if self.active_state_behaviors:
            resp = QMessageBox.question(
                self.parent, "Coding Duration Reached",
                "Coding duration reached\n"
                "Do you wish to end the active state behaviors?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                for key in list(self.active_state_behaviors):
                    self.handle_state_behavior(
                        key, current_sec, format_time_human(current_sec))
        else:
            QMessageBox.information(
                self.parent, "Coding Duration Reached",
                "Coding duration reached")

    def _poll_progress(self):
        if not hasattr(self, "player") or not self.player:
            return
        try:
            self.update_progress()
        except Exception:
            pass
        QTimer.singleShot(250, self._poll_progress)

    def _init_progress_bar(self):
        total = self.player.duration or 0
        if total <= 0:
            QTimer.singleShot(250, self._init_progress_bar)
            return

        self.progress_bar.set_left_text("0m0.00s")
        self.progress_bar.set_center_text("(1.0x)")
        self.progress_bar.set_right_text(format_time_human(total))

        if self.coding_duration is not None and self.coding_duration > 0:
            end_time = self.coding_start + self.coding_duration
            current = self.player.time_pos or 0
            if current >= end_time:
                self.player.pause = True
                self.coding_end_reached = True
                QTimer.singleShot(
                    500, lambda: self._show_coding_end_prompt(current))

        self._poll_progress()

    def on_progress_click(self, ratio):
        total = self.player.duration or 0
        if total <= 0:
            return
        target = ratio * total
        if target >= total - 0.1:
            self.player.time_pos = total - 0.5
            self.player.pause = True
        else:
            self.player.time_pos = target
        self.coding_end_reached = False
        self.update_progress()

    def update_coding_info_display(self):
        if not hasattr(self, "coding_info_label"):
            return
        if self.coding_start and self.coding_start > 0:
            start_str = format_time_human(self.coding_start)
            if self.coding_duration and self.coding_duration > 0:
                end_time = self.coding_start + self.coding_duration
                self.coding_info_label.setText(
                    f"Coding Start: {start_str} | "
                    f"Duration: {format_time_human(self.coding_duration)} | "
                    f"End: {format_time_human(end_time)}")
            else:
                self.coding_info_label.setText(f"Coding Start: {start_str}")
            self.coding_info_label.setVisible(True)
        else:
            self.coding_info_label.setVisible(False)

    # ------------------------------------------------------------------
    # MPV player
    # ------------------------------------------------------------------

    def _init_mpv_player(self):
        self.parent.show()
        QApplication.processEvents()
        locale.setlocale(locale.LC_NUMERIC, "C")  # Ensure locale is correct for mpv
        self.player = mpv.MPV(
            vo="libmpv",
            keep_open="yes",
            log_handler=print,
            hwdec="auto",
            profile="fast",
        )
        self.gl_widget.init_mpv_render(self.player)

    def _load_data_and_start(self):
        self.store.load_behaviors()
        self.store.load_annotations()
        self._update_annotations()
        self._populate_behavior_trees()
        self._init_progress_bar()
        self._load_session_state()
        self._auto_save_session_state()

        self.parent.update()
        self.parent.show()
        self.parent.activateWindow()
        self.parent.raise_()
        self.player.play(self.video_path)
        QTimer.singleShot(100, self._scroll_annotations_to_bottom)

    # ------------------------------------------------------------------
    # Annotation panel
    # ------------------------------------------------------------------

    def _create_annotation_panel(self):
        tree_font = "12px"
        heading_font = "12px"

        available_h = self.panel_height - self.progress_bar_height
        pane_h = (available_h - 15) // 4

        self.annotation_frame = QFrame(self)
        self.annotation_frame.setFrameStyle(
            QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.annotation_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
            }""")
        self.right_layout.addWidget(self.annotation_frame)

        main_layout = QVBoxLayout(self.annotation_frame)
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)

        tree_style = (
            "QTreeWidget {"
            "  background-color: #333333; border: 1px solid #444444;"
            "  border-radius: 4px; color: #ffffff; font-size: " + tree_font + ";}"
            "QTreeWidget::item { height: 18px; padding: 0px; margin: 0px;"
            "  font-size: " + tree_font + ";}"
            "QTreeWidget::item:selected { background-color: #808080; color: white; }"
            "QTreeWidget::item:hover { background-color: #404040; }"
            "QHeaderView::section {"
            "  background-color: #2b2b2b; color: #ffffff; font-weight: bold;"
            "  font-size: " + heading_font + "; padding: 2px;"
            "  border: none; border-bottom: 1px solid #444444; }"
            "QScrollBar:vertical { border: none; background: #2b2b2b; width: 10px; }"
            "QScrollBar::handle:vertical { background: #666666; min-height: 20px;"
            "  border-radius: 5px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )
        label_style = ("color: white; font-weight: bold; font-size: "
                        + heading_font + ";")
        btn_style = (
            "QPushButton { background-color: #808080; color: white;"
            "  border: none; border-radius: 4px; padding: 3px 8px;"
            "  font-size: " + heading_font + ";}"
            "QPushButton:hover { background-color: #1084D9; }"
            "QPushButton:pressed { background-color: #006CC1; }"
        )
        big_btn_style = (
            "QPushButton { background-color: #808080; color: white;"
            "  border: none; border-radius: 4px; padding: 4px;"
            "  min-width: 100px; min-height: 40px;"
            "  font-size: " + heading_font + ";}"
            "QPushButton:hover { background-color: #1084D9; }"
            "QPushButton:pressed { background-color: #006CC1; }"
        )

        def _make_tree(headers, widths, height):
            frame = QFrame()
            frame.setFixedHeight(height)
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(1)
            tree = QTreeWidget()
            tree.setStyleSheet(tree_style)
            tree.setHeaderLabels(headers)
            for i, w in enumerate(widths):
                tree.setColumnWidth(i, int(self.panel_width * w))
            tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return frame, lay, tree

        # State behaviours
        sf, sl, self.state_behaviors_tree = _make_tree(
            ["Name", "Key", "ME Group"], [0.5, 0.15, 0.25], pane_h)
        sl.addWidget(QLabel("State Behaviors").setStyleSheet(label_style) or
                     QLabel("State Behaviors"))
        lbl = QLabel("State Behaviors"); lbl.setStyleSheet(label_style)
        sl.insertWidget(0, lbl)
        sl.addWidget(self.state_behaviors_tree)
        main_layout.addWidget(sf)

        # Point behaviours
        pf, pl, self.point_behaviors_tree = _make_tree(
            ["Name", "Key"], [0.6, 0.3], pane_h)
        lbl2 = QLabel("Point Behaviors"); lbl2.setStyleSheet(label_style)
        pl.insertWidget(0, lbl2)
        pl.addWidget(self.point_behaviors_tree)
        main_layout.addWidget(pf)

        # State annotations
        saf, sal, self.state_annotations_tree = _make_tree(
            ["Name", "Start", "End"], [0.33, 0.25, 0.25], pane_h)
        sa_header = QWidget()
        hlay = QHBoxLayout(sa_header); hlay.setContentsMargins(0, 0, 0, 0); hlay.setSpacing(3)
        lbl3 = QLabel("State Annotations"); lbl3.setStyleSheet(label_style)
        hlay.addWidget(lbl3)
        sort_btn = QPushButton("Sort"); sort_btn.setStyleSheet(btn_style)
        sort_btn.setFixedWidth(50); sort_btn.setFixedHeight(22)
        sort_btn.clicked.connect(self._sort_state_annotations)
        hlay.addStretch(); hlay.addWidget(sort_btn)
        sal.insertWidget(0, sa_header)
        self.state_annotations_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.state_annotations_tree.customContextMenuRequested.connect(
            self._show_annotation_menu)
        sal.addWidget(self.state_annotations_tree)
        main_layout.addWidget(saf)

        # Point annotations
        paf, pal, self.point_annotations_tree = _make_tree(
            ["Name", "Time"], [0.4, 0.5], pane_h)
        pa_header = QWidget()
        hlay2 = QHBoxLayout(pa_header); hlay2.setContentsMargins(0, 0, 0, 0); hlay2.setSpacing(8)
        lbl4 = QLabel("Point Annotations"); lbl4.setStyleSheet(label_style)
        hlay2.addWidget(lbl4)
        sort_btn2 = QPushButton("Sort"); sort_btn2.setStyleSheet(btn_style)
        sort_btn2.setFixedWidth(50); sort_btn2.setFixedHeight(22)
        sort_btn2.clicked.connect(self._sort_point_annotations)
        hlay2.addStretch(); hlay2.addWidget(sort_btn2)
        pal.insertWidget(0, pa_header)
        self.point_annotations_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.point_annotations_tree.customContextMenuRequested.connect(
            self._show_annotation_menu)
        pal.addWidget(self.point_annotations_tree)
        main_layout.addWidget(paf)

        # Bottom buttons
        btn_frame = QFrame()
        btn_lay = QHBoxLayout(btn_frame)
        btn_lay.setContentsMargins(0, 3, 0, 0)
        btn_lay.setSpacing(6)

        for text, callback in [
            ("Set\nCoding Start", self.set_coding_start),
            ("Visualize\nAnnotations", self.visualize_annotations),
            ("Edit\nBehavior Key", self._edit_behavior_key),
        ]:
            b = QPushButton(text)
            b.setStyleSheet(big_btn_style)
            b.clicked.connect(callback)
            btn_lay.addWidget(b)

        main_layout.addWidget(btn_frame)

        # Click-selection handlers
        self.state_annotations_tree.itemClicked.connect(
            lambda item: self._handle_tree_selection(
                self.state_annotations_tree, item))
        self.point_annotations_tree.itemClicked.connect(
            lambda item: self._handle_tree_selection(
                self.point_annotations_tree, item))

    # ------------------------------------------------------------------
    # Annotation data helpers
    # ------------------------------------------------------------------

    def _update_annotations(self):
        self.state_annotations_tree.clear()
        for evt in self.store.state_events:
            start = format_time_human(evt["start_time"])
            end = format_time_human(evt["end_time"]) if evt["end_time"] else ""
            self.state_annotations_tree.addTopLevelItem(
                QTreeWidgetItem([evt["Name"], start, end]))

        self.point_annotations_tree.clear()
        for evt in self.store.point_events:
            self.point_annotations_tree.addTopLevelItem(
                QTreeWidgetItem([evt["Name"], evt["time"]]))

        QTimer.singleShot(50, self._scroll_annotations_to_bottom)

    def _scroll_annotations_to_bottom(self):
        for tree in (self.state_annotations_tree, self.point_annotations_tree):
            n = tree.topLevelItemCount()
            if n > 0:
                tree.scrollToItem(
                    tree.topLevelItem(n - 1),
                    QAbstractItemView.ScrollHint.EnsureVisible)

    def _populate_behavior_trees(self):
        self.state_behaviors_tree.clear()
        self.point_behaviors_tree.clear()
        active_color = QColor("darkorange")
        highlight_color = QColor("dodgerblue")

        for name, key, btype, me_group in self.store.behaviors:
            if btype == "state":
                item = QTreeWidgetItem([name, key, me_group])
                if key in self.active_state_behaviors:
                    for c in range(item.columnCount()):
                        item.setBackground(c, active_color)
                self.state_behaviors_tree.addTopLevelItem(item)
            elif btype == "point":
                item = QTreeWidgetItem([name, key])
                if key in self.used_point_behaviors:
                    for c in range(item.columnCount()):
                        item.setBackground(c, highlight_color)
                    QTimer.singleShot(
                        250, lambda i=item: self._remove_highlight(i))
                self.point_behaviors_tree.addTopLevelItem(item)

    def _remove_highlight(self, item):
        tree = self.point_behaviors_tree
        if item in [tree.topLevelItem(i)
                    for i in range(tree.topLevelItemCount())]:
            for c in range(item.columnCount()):
                item.setBackground(c, QColor("transparent"))

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _sort_state_annotations(self):
        self.store.state_events.sort(
            key=lambda e: e["start_time"] if e["start_time"] is not None else 0)
        self.store.save_sorted_annotations()
        self._update_annotations()

    def _sort_point_annotations(self):
        self.store.point_events.sort(
            key=lambda e: parse_time(e["time"]) if e["time"] else 0)
        self.store.save_sorted_annotations()
        self._update_annotations()

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    def save_session_state(self):
        current = self.player.time_pos
        if current is None:
            return False
        ok = self.store.save_session_state(
            float(current), self.coding_start, self.coding_duration,
            self.coding_end, self.coding_end_reached)
        if not ok and not getattr(self, "_auto_saving", False):
            self.on_write_error(
                "Cannot save session state.\n"
                "Is the file open in another application?")
        return ok

    def _load_session_state(self):
        state = self.store.load_session_state()
        if state is None:
            self.update_coding_info_display()
            return

        self.coding_start = state["coding_start"]
        self.coding_duration = state["coding_duration"]
        self.coding_end = state["coding_end"]
        self.coding_end_reached = state["coding_end_reached"]
        self.update_coding_info_display()

        ts = state["timestamp_sec"]
        self._schedule_resume(ts)

        if self.coding_end is not None and ts >= self.coding_end:
            self.coding_end_reached = True

    def _auto_save_session_state(self):
        try:
            if (hasattr(self, "player") and self.player
                    and self.parent and self.parent.isVisible()):
                self._auto_saving = True
                self.save_session_state()
            else:
                return
        finally:
            self._auto_saving = False

        if self.parent and self.parent.isVisible():
            QTimer.singleShot(5000, self._auto_save_session_state)

    def _schedule_resume(self, timestamp_sec):
        if (self.player.duration or 0) > 0:
            self.player.time_pos = timestamp_sec
            if (self.coding_duration is not None
                    and self.coding_start is not None
                    and timestamp_sec >= self.coding_start + self.coding_duration):
                self.player.pause = True
        else:
            QTimer.singleShot(
                200, lambda: self._schedule_resume(timestamp_sec))

    # ------------------------------------------------------------------
    # Key bindings
    # ------------------------------------------------------------------

    def _setup_key_bindings(self):
        self.parent.installEventFilter(self)

        def blocked(handler):
            def wrapper(*a, **kw):
                if not self.dialog_open:
                    return handler(*a, **kw)
            return wrapper

        self.key_bindings = {
            Qt.Key.Key_Space: blocked(self.toggle_play_pause),
            (Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(1000)),
            (Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(-1000)),
            (Qt.Key.Key_D, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(1000)),
            (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(-1000)),
            (Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(5000)),
            (Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(-5000)),
            (Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(5000)),
            (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(-5000)),
            Qt.Key.Key_W: blocked(lambda: self.seek_relative(10000)),
            Qt.Key.Key_S: blocked(lambda: self.seek_relative(-10000)),
            Qt.Key.Key_Equal: blocked(lambda: self.change_speed(1)),
            Qt.Key.Key_Plus: blocked(lambda: self.change_speed(1)),
            Qt.Key.Key_Minus: blocked(lambda: self.change_speed(-1)),
            Qt.Key.Key_Underscore: blocked(lambda: self.change_speed(-1)),
            Qt.Key.Key_Backspace: blocked(self._reset_speed),
            Qt.Key.Key_Escape: self.return_to_file_selection,
            Qt.Key.Key_Delete: blocked(self.delete_annotation),
            (Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier): blocked(self.undo_delete),
            (Qt.Key.Key_Z, Qt.KeyboardModifier.MetaModifier): blocked(self.undo_delete),
        }

    def eventFilter(self, obj, event):
        if obj == self.parent:
            if event.type() in (QEvent.Type.ActivationChange,
                                QEvent.Type.WindowStateChange):
                if sys.platform == "darwin":
                    # On macOS, check if ANY of our windows are active
                    app = QApplication.instance()
                    active = app.activeWindow()
                    any_active = (
                        active == self.parent
                        or active in self.floating_windows
                    )
                    for w in self.floating_windows:
                        if w:
                            w.setVisible(any_active and self.parent.isVisible())
                else:
                    update_floating_visibility(self)

        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if event.isAutoRepeat() and key not in (
                    Qt.Key.Key_Up, Qt.Key.Key_Down):
                return True

            if key == Qt.Key.Key_Escape and not self.dialog_open:
                self.return_to_file_selection()
                return True

            if not self.dialog_open:
                # Mask to only the modifiers we care about
                clean_mods = modifiers & (
                    Qt.KeyboardModifier.ShiftModifier
                    | Qt.KeyboardModifier.ControlModifier
                    | Qt.KeyboardModifier.AltModifier
                    | Qt.KeyboardModifier.MetaModifier
                )

                combo = (key, clean_mods)
                if combo in self.key_bindings:
                    self.key_bindings[combo]()
                    return True

                # Try with NoModifier explicitly if no relevant modifiers are held
                if clean_mods == Qt.KeyboardModifier.NoModifier:
                    combo_no = (key, Qt.KeyboardModifier.NoModifier)
                    if combo_no in self.key_bindings:
                        self.key_bindings[combo_no]()
                        return True

                if key in self.key_bindings and isinstance(
                        self.key_bindings[key], types.FunctionType):
                    self.key_bindings[key]()
                    return True

                char = event.text().lower()
                if char and char in self.store.behavior_map:
                    self._handle_behavior_key(char)
                    return True

        elif event.type() == QEvent.Type.KeyRelease:
            char = event.text().lower()
            if char:
                self.pressed_keys.discard(char)
                return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Behaviour handling
    # ------------------------------------------------------------------

    def _handle_behavior_key(self, key):
        info = self.store.behavior_map[key]
        current = self.player.time_pos or 0
        fmt = format_time_human(current)

        if info["Type"] == "State":
            self.handle_state_behavior(key, current, fmt)
        elif info["Type"] == "Point":
            self._add_point_annotation(key, info, current, fmt)

    def add_annotation_for_behavior(self, key):
        key = key.lower()
        if key not in self.store.behavior_map:
            return
        info = self.store.behavior_map[key]
        current = self.player.time_pos or 0
        fmt = format_time_human(current)

        if info["Type"] == "State":
            self.handle_state_behavior(key, current, fmt)
        elif info["Type"] == "Point":
            self._add_point_annotation(key, info, current, fmt)

    def _add_point_annotation(self, key, info, current_time, formatted_time):
        if any(e["Name"] == info["Name"] and e["time"] == formatted_time
               for e in self.store.point_events):
            return

        record = {
            "Video": self.video_name, "Name": info["Name"], "Type": "Point",
            "Mutually_Exclusive": "False", "H_Start": formatted_time,
            "H_End": "", "Start": f"{current_time:.2f}", "End": "",
            "Duration": "", "Manual_Edit": "False", "Notes": "",
        }

        if not self.store.append_annotation(record):
            self.on_write_error()
            return

        self.store.point_events.append({
            "Name": info["Name"], "time": formatted_time,
            "Manual_Edit": False, "Notes": "",
        })
        self.used_point_behaviors.add(key)
        QTimer.singleShot(100, lambda: self.used_point_behaviors.discard(key))
        self._update_annotations()
        self._populate_behavior_trees()

    def handle_state_behavior(self, key, frame_ts, formatted_ts):
        name = self.store.state_behaviors.get(key)
        me_group = self.store.me_groups.get(key)

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            return False

        if key in self.active_state_behaviors:
            start = self.active_state_behaviors[key]
            dur = frame_ts - start
            record = {
                "Video": self.video_name, "Name": name, "Type": "State",
                "Mutually_Exclusive": "True" if me_group else "False",
                "H_Start": format_time_human(start),
                "H_End": format_time_human(frame_ts),
                "Start": format_time_machine(start),
                "End": format_time_machine(frame_ts),
                "Duration": format_time_machine(dur),
                "Manual_Edit": "False", "Notes": "",
            }
            if not self.store.append_annotation(record):
                return False

            self.active_state_behaviors.pop(key)
            for evt in self.store.state_events:
                if evt["Name"] == name and evt["end_time"] is None:
                    evt["end_time"] = frame_ts
                    break
            self._update_annotations()
            self._populate_behavior_trees()
            return True
        else:
            if me_group:
                if not self._deactivate_me_group(me_group, frame_ts, key):
                    return False

            self.active_state_behaviors[key] = frame_ts
            self.store.state_events.append({
                "Name": name, "start_time": frame_ts, "end_time": None,
                "Type": "State",
                "Mutually_Exclusive": "True" if me_group else "False",
                "Notes": "",
            })
            self._update_annotations()
            self._populate_behavior_trees()
            return True

    def _deactivate_me_group(self, me_group, frame_ts, current_key):
        to_deactivate = [
            k for k in self.active_state_behaviors
            if self.store.me_groups.get(k) == me_group and k != current_key]

        if not to_deactivate:
            return True

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error(
                "Cannot deactivate mutually exclusive behaviors.\n"
                "Annotations file is inaccessible.")
            return False

        removed = []
        for key in to_deactivate:
            start = self.active_state_behaviors[key]
            name = self.store.state_behaviors.get(key)
            dur = frame_ts - start
            record = {
                "Video": self.video_name, "Name": name, "Type": "State",
                "Mutually_Exclusive": "True",
                "H_Start": format_time_human(start),
                "H_End": format_time_human(frame_ts),
                "Start": format_time_machine(start),
                "End": format_time_machine(frame_ts),
                "Duration": format_time_machine(dur),
                "Manual_Edit": "False", "Notes": "",
            }
            if not self.store.append_annotation(record):
                return False

            removed.append(key)
            for evt in self.store.state_events:
                if evt["Name"] == name and evt["end_time"] is None:
                    evt["end_time"] = frame_ts
                    break

        for key in removed:
            self.active_state_behaviors.pop(key)

        if removed:
            self._update_annotations()
            self._populate_behavior_trees()
        return True

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def toggle_play_pause(self):
        self.player.pause = not self.player.pause
        self.update_play_pause_icon()

    def update_play_pause_icon(self):
        btn = getattr(self, "play_pause_btn", None)
        if btn and btn.isVisible():
            try:
                btn.setText("\u25B6" if self.player.pause else "\u23F8")
            except RuntimeError:
                self.play_pause_btn = None

    def seek_relative(self, offset_ms):
        total = self.player.duration or 0
        current = self.player.time_pos or 0
        new_time = current + offset_ms / 1000.0

        if new_time >= total:
            new_time = max(0, total - 0.5)
            self.player.time_pos = new_time
            self.player.pause = True
        else:
            self.player.time_pos = max(0, new_time)

        self._reset_coding_end_flag()
        self.update_progress()

    def change_speed(self, delta):
        steps = [0.5, 1, 2, 3, 5, 8, 10, 15, 20, 25]
        current = self.player.speed
        try:
            idx = steps.index(current)
        except ValueError:
            idx = min(range(len(steps)),
                      key=lambda i: abs(steps[i] - current))
        new_idx = max(0, min(len(steps) - 1,
                             idx + (1 if delta > 0 else -1)))
        new_rate = steps[new_idx]
        if new_rate != current:
            self.player.speed = new_rate
            self.progress_bar.set_center_text(f"({new_rate:.1f}x)")

    def _reset_speed(self):
        if self.player.speed != 1.0:
            self.player.speed = 1.0
            self.progress_bar.set_center_text("(1.0x)")

    def _reset_coding_end_flag(self):
        current = self.player.time_pos or 0
        if (self.coding_duration is not None
                and self.coding_start is not None
                and current < self.coding_start + self.coding_duration - 0.5
                and self.coding_end_reached):
            self.coding_end_reached = False

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _on_state_item_selected(self):
        self.selected_treeview = self.state_annotations_tree
        items = self.state_annotations_tree.selectedItems()
        if items:
            self.selected_item = items[0]
            self.selected_index = self.state_annotations_tree.indexOfTopLevelItem(items[0])

    def _on_point_item_selected(self):
        self.selected_treeview = self.point_annotations_tree
        items = self.point_annotations_tree.selectedItems()
        if items:
            self.selected_item = items[0]
            self.selected_index = self.point_annotations_tree.indexOfTopLevelItem(items[0])

    def _handle_tree_selection(self, tree, item):
        self.selected_treeview = tree
        self.selected_item = item
        if tree == self.state_annotations_tree:
            self.selected_index = tree.indexOfTopLevelItem(item)
        else:
            self.selected_index = tree.indexOfTopLevelItem(item)

    # ------------------------------------------------------------------
    # Context menu & annotation actions
    # ------------------------------------------------------------------

    def _show_annotation_menu(self, point):
        if self.player:
            self.player.pause = True

        tree = self.sender()
        self.selected_treeview = tree
        item = tree.itemAt(point)
        if not item:
            return

        tree.setCurrentItem(item)
        self.selected_item = item
        self.selected_index = tree.indexOfTopLevelItem(item)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu::item { padding: 4px 25px; }"
            "QMenu::item:selected { background-color: #808080; color: white; }")
        menu.addAction("Edit", self.edit_annotation)
        menu.addAction("Add Note", lambda: show_note_dialog(self))
        menu.addAction("View Details", lambda: show_annotation_details(self))
        menu.addAction("Skip to Annotation", self._skip_to_annotation)
        menu.addAction("Delete", self.delete_annotation)
        menu.exec(tree.viewport().mapToGlobal(point))

    def edit_annotation(self):
        if not self.selected_item:
            return
        if self.selected_treeview == self.state_annotations_tree:
            show_edit_state_dialog(self)
        else:
            show_edit_point_dialog(self)

    def _skip_to_annotation(self):
        if not self.selected_item:
            return
        time_str = self.selected_item.text(1)
        t = parse_time(time_str)
        if t is not None:
            self.player.time_pos = t
            self.update_progress()
            self.player.pause = True

    def delete_annotation(self):
        if self.selected_treeview is None or self.selected_item is None:
            return

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            return

        if self.selected_treeview == self.state_annotations_tree:
            deleted = dict(self.store.state_events[self.selected_index])
            self.undo_stack.append(("state", self.selected_index, deleted))
            self.store.state_events.pop(self.selected_index)
        else:
            deleted = dict(self.store.point_events[self.selected_index])
            self.undo_stack.append(("point", self.selected_index, deleted))
            self.store.point_events.pop(self.selected_index)

        if not self.store.save_sorted_annotations():
            return

        self._update_annotations()
        self._populate_behavior_trees()
        self.selected_treeview = None
        self.selected_item = None
        self.selected_index = None

    def undo_delete(self):
        if not self.undo_stack:
            return

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            return

        atype, idx, annotation = self.undo_stack.pop()
        lst = (self.store.state_events if atype == "state"
               else self.store.point_events)

        if idx >= len(lst):
            lst.append(annotation)
        else:
            lst.insert(idx, annotation)

        if not self.store.save_sorted_annotations():
            self.undo_stack.append((atype, idx, annotation))
            return

        self._update_annotations()
        self._populate_behavior_trees()

    # ------------------------------------------------------------------
    # Delegates to dialog module
    # ------------------------------------------------------------------

    def set_coding_start(self):
        show_coding_start_dialog(self)

    def add_note_to_annotation(self):
        show_note_dialog(self)

    def view_annotation_details(self):
        show_annotation_details(self)

    # ------------------------------------------------------------------
    # Save helpers (point / state edit callbacks used by dialogs)
    # ------------------------------------------------------------------

    def save_point_annotation(self, new_entries, dialog, selected, old_time):
        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            dialog.reject()
            return False

        new_name = new_entries["Name"].text().strip()
        new_start = new_entries["H_Start"].text().strip()
        if not new_name or not new_start:
            QMessageBox.warning(
                self.parent, "Invalid Input",
                "Both Name and Start Time are required.")
            return False

        for ann in self.store.point_events:
            if ann["Name"] == selected["Name"] and ann["time"] == old_time:
                if ann["Name"] != new_name or ann["time"] != new_start:
                    ann["Manual_Edit"] = True
                ann["Name"] = new_name
                ann["time"] = new_start
                break
        else:
            dialog.reject()
            return False

        if not self.store.save_sorted_annotations():
            for ann in self.store.point_events:
                if ann["Name"] == new_name and ann["time"] == new_start:
                    ann["Name"] = selected["Name"]
                    ann["time"] = old_time
                    break
            dialog.reject()
            return False

        self._update_annotations()
        self.dialog_open = False
        dialog.accept()
        return True

    def save_state_annotation(self, new_entries, dialog, selected, old_time):
        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            dialog.reject()
            return False

        new_name = new_entries["Name"].text().strip()
        new_h_start = new_entries["H_Start"].text().strip()
        new_h_end = new_entries["H_End"].text().strip()
        if not new_name or not new_h_start or not new_h_end:
            QMessageBox.warning(
                self.parent, "Invalid Input",
                "Name, Start, and End times are required.")
            return False

        try:
            new_start = parse_time(new_h_start)
            new_end = parse_time(new_h_end)
        except ValueError:
            QMessageBox.warning(
                self.parent, "Invalid Time Format",
                "Could not parse time values. Please check format.")
            return False

        original = None
        for ann in self.store.state_events:
            if (ann["Name"] == selected["Name"]
                    and format_time_human(ann.get("start_time", 0)) == old_time):
                original = dict(ann)
                ann["Name"] = new_name
                ann["start_time"] = new_start
                ann["end_time"] = new_end
                ann["Manual_Edit"] = True
                ann.setdefault("Notes", "")
                break

        if original is None:
            dialog.reject()
            return False

        if not self.store.save_sorted_annotations():
            for ann in self.store.state_events:
                if ann["Name"] == new_name and ann["start_time"] == new_start:
                    ann.update(original)
                    break
            dialog.reject()
            return False

        self._update_annotations()
        self.dialog_open = False
        dialog.accept()
        return True

    def load_annotation_data(self, annotation, *fields):
        result = {f: "" for f in fields}
        with open(self.store.annotations_file, "r") as fh:
            for row in csv.DictReader(fh):
                if (row["Name"] == annotation["Name"]
                        and row["H_Start"] == format_time_human(
                            annotation.get("start_time", 0))):
                    result.update({f: row.get(f, "") for f in fields})
                    break
                elif row.get("H_Start") == annotation.get("time"):
                    result.update({f: row.get(f, "") for f in fields})
                    break
        return result

    # ------------------------------------------------------------------
    # Visualize annotations
    # ------------------------------------------------------------------

    def visualize_annotations(self):
        was_playing = False
        if self.player:
            was_playing = not self.player.pause
            self.player.pause = True

        self.dialog_open = True
        try:
            from annotations_visualizer import show_visualization_dialog

            state_ann, point_ann = self._load_annotations_for_viz()

            coding_start = self.coding_start or 0
            coding_end = getattr(self, "coding_end", None)
            has_bounds = coding_start > 0 or (coding_end is not None and coding_end > 0)

            bounds = {
                "has_bounds": has_bounds,
                "start": coding_start,
                "end": coding_end,
                "whole_video": True,
            }

            if has_bounds:
                from PySide6.QtWidgets import QDialog as _D
                dlg = _D(self.parent)
                dlg.setWindowTitle("Select Visualization Range")
                dlg.setWindowFlags(
                    dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                dlg.setModal(True)
                lay = QVBoxLayout(dlg)

                parts = []
                if coding_start > 0:
                    parts.append(f"Start: {format_time_human(coding_start)}")
                if coding_end is not None:
                    parts.append(f"End: {format_time_human(coding_end)}")
                lay.addWidget(QLabel(
                    f"Coding bounds detected:\n{', '.join(parts)}\n\n"
                    "What would you like to visualize?"))

                blay = QHBoxLayout()
                blay.addStretch(1)
                for text, code in [("Whole Video", 1),
                                   ("Coded Segment Only", 2),
                                   ("Cancel", 0)]:
                    b = QPushButton(text)
                    b.clicked.connect(lambda _, c=code: dlg.done(c))
                    blay.addWidget(b)
                    blay.addSpacing(10)
                blay.addStretch(1)
                lay.addLayout(blay)

                result = dlg.exec()
                if result == 0:
                    self.dialog_open = False
                    return
                bounds["whole_video"] = (result == 1)

            show_visualization_dialog(
                parent=self.parent,
                video_name=self.video_name,
                state_events=state_ann,
                point_events=point_ann,
                video_duration=self.player.duration or 0,
                parse_time_func=parse_time,
                center_window_func=center_window,
                output_dir=self.output_dir,
                bounds=bounds,
            )
        except ImportError:
            QMessageBox.warning(
                self.parent, "Visualization Module Error",
                "Could not load the visualization module.")
        except Exception as exc:
            QMessageBox.critical(
                self.parent, "Visualization Error",
                f"Failed to create visualization: {exc}")
        finally:
            self.dialog_open = False
            if self.player and was_playing:
                self.player.pause = False

    def _load_annotations_for_viz(self):
        state_ann, point_ann = [], []
        if not os.path.exists(self.store.annotations_file):
            return list(self.store.state_events), list(self.store.point_events)

        try:
            with open(self.store.annotations_file, "r", newline="") as fh:
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
                            "Name": row.get("Name", "").strip(),
                            "start_time": start, "end_time": end,
                            "Type": "State",
                            "Mutually_Exclusive": row.get("Mutually_Exclusive", "False"),
                            "Notes": row.get("Notes", ""),
                        })
                    elif atype == "point":
                        raw = row.get("Start", "0").strip()
                        point_ann.append({
                            "Name": row.get("Name", "").strip(),
                            "time": row.get("H_Start", "").strip(),
                            "raw_time": float(raw) if raw and raw != "NA" else 0,
                            "Manual_Edit": row.get("Manual_Edit", "False"),
                            "Notes": row.get("Notes", ""),
                        })
        except Exception:
            return list(self.store.state_events), list(self.store.point_events)

        return state_ann, point_ann

    # ------------------------------------------------------------------
    # Behavior key editor
    # ------------------------------------------------------------------

    def _edit_behavior_key(self):
        was_playing = False
        if self.player:
            was_playing = not self.player.pause
            self.player.pause = True

        self.save_session_state()
        saved = (self.coding_start, self.coding_duration,
                 getattr(self, "coding_end", None), self.coding_end_reached)

        for w in self.floating_windows:
            try:
                if w and w.isVisible():
                    w.hide()
            except RuntimeError:
                continue

        try:
            from behavior_key_editor import BehaviorKeyEditor
            from config_manager import ConfigManager

            bk_dir = os.path.dirname(self.behavior_key_file)
            cfg = ConfigManager()

            def on_close(bk_file):
                if bk_file and os.path.exists(bk_file):
                    self.behavior_key_file = bk_file
                    self.store.behavior_key_file = bk_file
                    self.active_state_behaviors.clear()
                    self.store.load_behaviors()
                    self.store.load_annotations()
                    self._update_annotations()
                    self._populate_behavior_trees()

                    if (hasattr(self, "behavior_buttons_window")
                            and self.behavior_buttons_window):
                        self.behavior_buttons_window.deleteLater()
                        self.behavior_buttons_window = None
                        from floating_controls import _create_behavior_buttons
                        _create_behavior_buttons(self)

                    QTimer.singleShot(100, self._scroll_annotations_to_bottom)
                    (self.coding_start, self.coding_duration,
                     self.coding_end, self.coding_end_reached) = saved
                    self.update_coding_info_display()
                    self.save_session_state()

            self.dialog_open = True
            editor = BehaviorKeyEditor(
                self.parent, bk_dir,
                on_start_video=on_close, on_cancel=lambda: None,
                config_manager=cfg)
            center_window(editor,
                          int(self.display_width * 0.5),
                          int(self.display_height * 0.8))
            editor.exec()
            self.dialog_open = False
        except Exception as exc:
            QMessageBox.critical(
                self.parent, "Error",
                f"Failed to open behavior key editor: {exc}")
        finally:
            for w in self.floating_windows:
                try:
                    if w and not w.isVisible():
                        w.show()
                except RuntimeError:
                    continue
            if self.player and was_playing:
                self.player.pause = False

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def on_write_error(self, message=None):
        if self.player:
            self.player.pause = True

        self.dialog_open = True
        dlg = QMessageBox(self.parent)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setWindowTitle("File Access Error")
        dlg.setText(message or
                    "Annotations file is inaccessible.\n"
                    "Is it open in another application?")
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
        dlg.setWindowFlags(
            dlg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dlg.exec()
        self.dialog_open = False

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def on_closing(self):
        try:
            if hasattr(self, "progress_timer") and self.progress_timer:
                self.progress_timer.stop()
            QTimer.singleShot(0, lambda: None)

            for attr in ("floating_controls_window", "behavior_buttons_window",
                         "behavior_toggle_window", "controls_window",
                         "edit_dialog"):
                w = getattr(self, attr, None)
                if w is not None:
                    w.deleteLater()

            for w in self.floating_windows:
                if w is not None:
                    w.deleteLater()
            self.floating_windows.clear()

            if hasattr(self, "player") and self.player:
                self.save_session_state()
                self.player.pause = True

                # Free render context before stopping the player
                if hasattr(self, "gl_widget") and self.gl_widget:
                    self.gl_widget.cleanup()

                self.player.stop()

            self.parent.close()
        except Exception:
            self.parent.close()

    def return_to_file_selection(self):
        if getattr(self, "_returning", False):
            QApplication.exit(0)
            return

        self._returning = True
        try:
            if hasattr(self, "player") and self.player:
                try:
                    self.save_session_state()
                except Exception:
                    pass
                try:
                    self.player.pause = True

                    # Free render context before stopping the player
                    if hasattr(self, "gl_widget") and self.gl_widget:
                        self.gl_widget.cleanup()

                    self.player.stop()
                except Exception:
                    pass
                self.player = None

            for w in list(self.floating_windows):
                if w is not None:
                    try:
                        w.hide()
                        w.deleteLater()
                    except Exception:
                        pass
            self.floating_windows.clear()

            if self.parent:
                from setup_manager import SetupManager
                from config_manager import ConfigManager

                main_window = self.parent
                if hasattr(main_window, "video_annotator"):
                    old = main_window.video_annotator
                    main_window.video_annotator = None
                    if old:
                        try:
                            old.hide()
                            old.deleteLater()
                        except Exception:
                            pass

                setup = SetupManager(config_manager=ConfigManager())
                try:
                    setup.exec()
                    if (setup.start_video_flag and setup.video_path
                            and setup.behavior_key_file):
                        main_window.init_video_annotator(
                            video_path=setup.video_path,
                            session_state_file=setup.session_state_file,
                            behavior_file=setup.behavior_key_file,
                            output_dir=setup.output_dir)
                        main_window.show()
                    else:
                        main_window.close()
                except Exception:
                    main_window.close()
            else:
                QApplication.quit()
        except Exception as exc:
            if self.parent:
                QMessageBox.critical(
                    self.parent, "Error",
                    f"Error returning to file selection: {exc}")
                self.parent.close()
        finally:
            self._returning = False

    # ------------------------------------------------------------------
    # Convenience aliases (used by floating_controls / dialogs modules)
    # ------------------------------------------------------------------

    def format_time_human_readable(self, t):
        return format_time_human(t)

    def format_time_machine_readable(self, t):
        return format_time_machine(t)

    def parse_time(self, s):
        return parse_time(s)
