
import os
import sys
import csv
import time
import types
import locale


from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Signal
from mpv import MpvRenderContext

import math
import ctypes

# Define above the class
_GL_GET_PROC_ADDR = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)

import mpv
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox,
    QAbstractItemView, QApplication, QSizePolicy, QColorDialog,
    QDialog, QGridLayout, QSplitter, QSlider, QStyle, QHeaderView,
)
from PySide6.QtCore import Qt, QTimer, QPoint, QEvent, QSysInfo, QEventLoop, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QOpenGLContext

from display_utils import get_screen_geometry, center_window
from progress_bar import ProgressBar
from waveform_widget import WaveformWidget
from annotation_store import (
    AnnotationStore, format_time_human, format_time_machine, parse_time,
)
from floating_controls import (
    create_toggle_buttons, toggle_floating_controls,
    toggle_event_buttons,
    _create_event_buttons,
)
from dialogs import (
    show_coding_start_dialog, show_note_dialog, show_annotation_details,
    show_edit_point_dialog, show_edit_state_dialog,
    show_message, show_colors_theme_dialog,
)
from config_manager import get_config
from debug_logger import get_logger
from platform_utils import enter_fullscreen_platform, exit_fullscreen_platform
import theme

logger = get_logger()


def _fmt_current(secs):
    """Format seconds as H:MM:SS.ss for the progress bar current time"""
    h = int(secs) // 3600
    m = (int(secs) % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _fmt_total(secs):
    """Format seconds as H:MM:SS for the progress bar total time"""
    h = int(secs) // 3600
    m = (int(secs) % 3600) // 60
    s = int(secs) % 60
    return f"{h}:{m:02d}:{s:02d}"


class MpvOpenGLWidget(QOpenGLWidget):
    """OpenGL widget that lets libmpv render frames into a Qt GL surface"""

    _frame_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.render_ctx = None
        self._has_first_frame = False
        self._first_frame_cb = None
        self._shutting_down = False
        self._frame_ready.connect(self._on_frame_signal)

    def _on_frame_signal(self):
        if self._shutting_down or self.render_ctx is None:
            return
        first = not self._has_first_frame
        self._has_first_frame = True
        if first:
            self.show()
        self.update()
        if first and self._first_frame_cb:
            self._first_frame_cb()

    def init_mpv_render(self, player):
        """Create the mpv render context. Widget must be visible first"""
        self.player = player

        # Force Qt to create the native window and GL context
        if not self.isVisible():
            self.show()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

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

        self.render_ctx = MpvRenderContext(
            self.player, "opengl",
            opengl_init_params={"get_proc_address": self._proc_addr_func},
        )
        self.render_ctx.update_cb = self._on_mpv_frame_ready
        self.doneCurrent()

    def _on_mpv_frame_ready(self):
        """Called from mpv's decoder thread. Emit signal to repaint on GUI thread"""
        if self._shutting_down:
            return
        try:
            self._frame_ready.emit()
        except RuntimeError:
            pass

    def _gl_clear_black(self):
        """Clear the framebuffer to black"""
        funcs = QOpenGLContext.currentContext().functions()
        funcs.glClearColor(0.0, 0.0, 0.0, 1.0)
        funcs.glClear(0x00004000)

    def initializeGL(self):
        self._gl_clear_black()

    def paintGL(self):
        if self._shutting_down or self.render_ctx is None or not self._has_first_frame:
            self._gl_clear_black()
            return
        try:
            ratio = self.devicePixelRatioF()
            w = int(self.width() * ratio)
            h = int(self.height() * ratio)
            fbo = self.defaultFramebufferObject()
            self.render_ctx.render(
                flip_y=True,
                opengl_fbo={"fbo": fbo, "w": w, "h": h},
            )
        except Exception:
            self._gl_clear_black()

    def cleanup(self):
        """Free the render context. Must be called before destroying the player"""
        self._shutting_down = True
        if self.render_ctx:
            self.render_ctx.update_cb = None
            self.makeCurrent()
            self.render_ctx.free()
            self.render_ctx = None
            self.doneCurrent()

class _AutoFitButton(QPushButton):
    """QPushButton that shrinks its font to fit the available width."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        text = self.text()
        if not text:
            return
        font = self.font()
        pad = 8
        avail = self.width() - pad
        for size in range(14, 6, -1):
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(text) <= avail:
                break
        self.setFont(font)


class VideoAnnotator(QFrame):
    """
    Main video annotator widget.

    """

    _time_pos_changed = Signal(float)
    _duration_changed = Signal(float)

    def __init__(self, parent, video_path, session_state_file,
                 event_key_file, output_dir):
        super().__init__(parent)

        self.parent = parent
        self.video_path = video_path
        self.event_key_file = event_key_file
        self.output_dir = output_dir
        self.floating_windows = []
        self.current_os = QSysInfo.productType().lower()

        # Zoom state
        self.zoom_active = False
        self._zoom_pan_x = 0.0
        self._zoom_pan_y = 0.0
        self._zoom_multiplier = 2.0
        self._shutting_down = False
        self._activation_pending = False
        self._suppress_floating_hide = False
        self._hide_pending = False
        self._last_time_pos_update = 0

        # passed through immediately
        self._watched_events = frozenset({
            QEvent.Type.Move,
            QEvent.Type.ActivationChange,
            QEvent.Type.WindowStateChange,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.KeyPress,
        })

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
        self.limit_timeline_to_coding = False
        self._video_completed = False
        self.active_state_events = {}
        self.used_point_events = set()
        self._mpv_duration = 0.0

        # Connect mpv property signals (fired from mpv thread, handled on GUI thread)
        self._time_pos_changed.connect(self._on_time_pos_changed)
        self._duration_changed.connect(self._on_duration_changed)

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
            event_key_file=event_key_file,
            output_dir=output_dir,
        )

        # Screen geometry — use the screen the window is actually on
        self.app = QApplication.instance()
        self._pre_fullscreen_geometry = self.parent.geometry()

        self.parent.setWindowTitle(f"LaserTag  {video_path}")
        self.parent.apply_theme()

        # Enter fullscreen: frameless window sized to full screen
        if sys.platform == "darwin":
            full = self.parent.screen().geometry()
            self.display_width = full.width()
            self.display_height = full.height()
            self.parent.hide()
            self.parent.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.FramelessWindowHint
            )
            self.parent.setGeometry(full)
            self.parent.show()
            QApplication.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            enter_fullscreen_platform()
        else:
            avail = self.parent.screen().availableGeometry()
            self.display_width = avail.width()
            self.display_height = avail.height()

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
        self._create_waveform_widget()
        self._create_progress_bar()
        self._create_annotation_panel()
        self._setup_key_bindings()
        self.gl_widget.setMouseTracking(True)
        self.gl_widget.installEventFilter(self)
        self.app.installEventFilter(self)
        self._init_mpv_player()
        self._load_data_and_start()
        logger.info("VideoAnnotator init complete: video=%s", video_path)

        self.state_annotations_tree.itemSelectionChanged.connect(
            self._on_state_item_selected)
        self.point_annotations_tree.itemSelectionChanged.connect(
            self._on_point_item_selected)

    # Layout

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

    def _create_waveform_widget(self):
        cfg = get_config()
        multiplier = cfg.get_waveform_height_multiplier()
        waveform_height = int(self.progress_bar_height * multiplier)

        self.waveform_widget = WaveformWidget(parent=None, annotator=self)
        self.waveform_widget.setContentsMargins(0, 0, 0, 0)
        self.waveform_widget.setFixedSize(self.progress_bar_width, waveform_height)

        hex_color = cfg.get_waveform_color()
        if hex_color:
            self.waveform_widget.set_fill_color(QColor(hex_color))
        self.waveform_widget.set_opacity(cfg.get_waveform_opacity())

        self.left_layout.addWidget(self.waveform_widget)

        is_visible = cfg.get_waveform_visible()
        self.waveform_widget.setVisible(is_visible)
        if is_visible:
            self.video_frame.setFixedHeight(self.video_height - waveform_height)

    def _reposition_floating_windows(self):
            """Reanchor floating toggle buttons to the video frame"""
            if not hasattr(self, "video_frame") or not self.video_frame:
                return
            video_pos = self.video_frame.mapToGlobal(QPoint(0, 0))
            margin = 2

            if hasattr(self, "event_toggle_window") and self.event_toggle_window:
                self.event_toggle_window.move(
                    video_pos.x() + margin + 5, video_pos.y() + margin - 10)

            if hasattr(self, "zoom_toggle_window") and self.zoom_toggle_window:
                self.zoom_toggle_window.move(
                    video_pos.x() + self.video_width - 30 - margin - 5,
                    video_pos.y() + margin - 10)

            if hasattr(self, "zoom_slider_window") and self.zoom_slider_window:
                self.zoom_slider_window.move(
                    video_pos.x() + self.video_width - 30 - margin - 5 - 145,
                    video_pos.y() + margin - 10)

            if hasattr(self, "floating_controls_window") and self.floating_controls_window:
                win_w = self.floating_controls_window.width()
                x = video_pos.x() + (self.video_width - win_w) // 2
                y = (video_pos.y() + self.video_height
                     - self.floating_controls_window.height() - 50)
                self.floating_controls_window.move(x, y)

            if hasattr(self, "event_buttons_window") and self.event_buttons_window:
                toggle_width = self.event_toggle_button.width()
                x = video_pos.x() + margin + 5 + toggle_width + 10
                y = video_pos.y() + margin - 20
                self.event_buttons_window.move(x, y)

    def _set_floating_visible(self, visible):
        """Show or hide all floating windows, pruning any deleted C++ objects.

        When *visible* is True, per-item settings are respected so that
        individually disabled toggles stay hidden.
        """
        if self._shutting_down:
            return

        if visible:
            cfg = get_config()
            hidden = set()
            if not cfg.get_show_floating_controls():
                w2 = getattr(self, "floating_controls_window", None)
                if w2:
                    hidden.add(w2)
            if not cfg.get_show_events_toggle():
                w = getattr(self, "event_toggle_window", None)
                if w:
                    hidden.add(w)
                w2 = getattr(self, "event_buttons_window", None)
                if w2:
                    hidden.add(w2)
            if not cfg.get_show_zoom_button():
                w = getattr(self, "zoom_toggle_window", None)
                if w:
                    hidden.add(w)
            if not cfg.get_show_zoom_button() or not self.zoom_active:
                w2 = getattr(self, "zoom_slider_window", None)
                if w2:
                    hidden.add(w2)
        else:
            hidden = None

        live = []
        for w in self.floating_windows:
            if w is None:
                continue
            try:
                want_visible = visible and not (hidden is not None and w in hidden)
                if w.isVisible() != want_visible:
                    w.setVisible(want_visible)
                live.append(w)
            except RuntimeError:
                pass  # C++ object deleted
        self.floating_windows[:] = live

    def _handle_activation_deferred(self):
        """Run once after ActivationChange events settle (debounced)"""
        self._activation_pending = False
        if self._shutting_down:
            return
        is_ours = (QApplication.instance().applicationState()
                   == Qt.ApplicationState.ApplicationActive)
        if is_ours:
            self._hide_pending = False
            if not self.dialog_open:
                self._set_floating_visible(True)
        elif not self.dialog_open and not self._suppress_floating_hide:
            if not self._hide_pending:
                self._hide_pending = True
                QTimer.singleShot(400, self._commit_floating_hide)

    def _commit_floating_hide(self):
        """Actually hide floating windows if still deactivated"""
        if not self._hide_pending or self._shutting_down:
            return
        self._hide_pending = False
        if QApplication.instance().applicationState() == Qt.ApplicationState.ApplicationActive:
            return
        self._set_floating_visible(False)

    def _raise_floating_windows(self):
        """Prune deleted floating windows from the list.

        Floating windows use the Tool flag which Qt keeps above their
        parent natively — no explicit raise_() needed.
        """
        if self._shutting_down:
            return
        live = []
        for w in self.floating_windows:
            if w is None:
                continue
            try:
                w.isVisible()  # raises RuntimeError if C++ object is deleted
                live.append(w)
            except RuntimeError:
                pass
        self.floating_windows[:] = live

    # Progress bar

    def _create_progress_bar(self):
        self.progress_frame = QFrame()
        self.progress_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.progress_frame.setContentsMargins(0, 0, 0, 0)
        self.progress_frame.setStyleSheet("background-color: #000000; margin: 0px; padding: 0px;")
        self.progress_frame.setFixedSize(
            self.progress_bar_width, self.progress_bar_height)

        frame_layout = QVBoxLayout(self.progress_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        self.progress_bar = ProgressBar(
            self.progress_frame, annotator=self)
        self.progress_bar.setFixedSize(
            self.progress_bar_width, self.progress_bar_height)
        frame_layout.addWidget(self.progress_bar)

        self.left_layout.addWidget(self.progress_frame)
        self.left_container.setStyleSheet("background-color: #000000;")

    def update_progress(self):
        if not hasattr(self, 'player') or not self.player:
            return
        total = self._mpv_duration or self.player.duration or 0
        current = self.player.time_pos or 0

        if total <= 0:
            return

        self._mpv_duration = total
        self.progress_bar.set_progress(self._time_to_ratio(current))
        self.progress_bar.set_left_text(_fmt_current(current))
        self.progress_bar.set_center_text(f"({self.player.speed:.1f}x)")
        if self.limit_timeline_to_coding and self.coding_end is not None:
            self.progress_bar.set_right_text(_fmt_total(self.coding_end))
        else:
            self.progress_bar.set_right_text(_fmt_total(total))
        self.progress_bar.update()

        if hasattr(self, 'waveform_widget') and self.waveform_widget.isVisible():
            self.waveform_widget.set_progress(self._time_to_ratio(current))
            self.waveform_widget.update()

    def _on_time_pos_changed(self, current):
        """Handle mpv time-pos property changes on the GUI thread."""
        if self._shutting_down:
            return
        if not hasattr(self, 'player') or not self.player:
            return
        total = self._mpv_duration
        if total <= 0:
            return

        # Coding-end check runs at full frame rate
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
            return

        # Throttle progress bar updates
        now = time.monotonic()
        if now - self._last_time_pos_update < 0.0334: # Update 30 times per second
            return
        self._last_time_pos_update = now

        self.progress_bar.set_progress(self._time_to_ratio(current))
        self.progress_bar.set_left_text(_fmt_current(current))
        self.progress_bar.set_center_text(f"({self.player.speed:.1f}x)")
        self.progress_bar.update()

        if hasattr(self, 'waveform_widget') and self.waveform_widget.isVisible():
            self.waveform_widget.set_progress(self._time_to_ratio(current))
            self.waveform_widget.update()

    def _on_duration_changed(self, total):
        """Handle mpv duration property changes on the GUI thread"""
        self._mpv_duration = total
        if self.limit_timeline_to_coding and self.coding_end is not None:
            self.progress_bar.set_right_text(_fmt_total(self.coding_end))
        else:
            self.progress_bar.set_right_text(_fmt_total(total))
        self.progress_bar.update()

        if self.coding_duration is not None and self.coding_duration > 0:
            end_time = self.coding_start + self.coding_duration
            current = self.player.time_pos or 0
            if current >= end_time:
                self.player.pause = True
                self.coding_end_reached = True

    def _init_progress_bar(self):
        self.progress_bar.set_left_text("0:00:00.00")
        self.progress_bar.set_center_text("(1.0x)")
        self.progress_bar.set_right_text("0:00:00")
        hex_color = get_config().get_progress_bar_color()
        if hex_color:
            self.progress_bar.set_fill_color(QColor(hex_color))
        self.progress_bar.update()

    def on_progress_click(self, ratio):
        total = self.player.duration or 0
        if total <= 0:
            return
        target = self._ratio_to_time(ratio)
        if target >= total - 0.1:
            self.player.time_pos = total - 0.5
            self.player.pause = True
        else:
            self.player.time_pos = target
        self.coding_end_reached = False
        self.update_progress()

    def _toggle_waveform(self):
        cfg = get_config()
        visible = not self.waveform_widget.isVisible()
        self.waveform_widget.setVisible(visible)
        cfg.set_waveform_visible(visible)

        waveform_h = self.waveform_widget.height()
        if visible:
            self.video_frame.setFixedHeight(self.video_height - waveform_h)
            resume_dir = os.path.join(self.store.output_dir, "Resume")
            self.waveform_widget.start_extraction(self.video_path, resume_dir)
        else:
            self.video_frame.setFixedHeight(self.video_height)

    def _start_waveform_extraction(self):
        if not hasattr(self, 'waveform_widget'):
            return
        resume_dir = os.path.join(self.store.output_dir, "Resume")
        self.waveform_widget.start_extraction(self.video_path, resume_dir)

    def update_coding_info_display(self):
        return

    def _time_to_ratio(self, time_sec):
        if (self.limit_timeline_to_coding
                and self.coding_start is not None
                and self.coding_end is not None
                and self.coding_end > self.coding_start):
            r = (time_sec - self.coding_start) / (self.coding_end - self.coding_start)
        else:
            total = self._mpv_duration or (self.player.duration if self.player else 0) or 0
            if total <= 0:
                return 0.0
            r = time_sec / total
        return max(0.0, min(1.0, r))

    def _ratio_to_time(self, ratio):
        ratio = max(0.0, min(1.0, ratio))
        if (self.limit_timeline_to_coding
                and self.coding_start is not None
                and self.coding_end is not None
                and self.coding_end > self.coding_start):
            return self.coding_start + ratio * (self.coding_end - self.coding_start)
        total = self._mpv_duration or (self.player.duration if self.player else 0) or 0
        return ratio * total

    def _timeline_duration(self):
        if (self.limit_timeline_to_coding
                and self.coding_start is not None
                and self.coding_end is not None
                and self.coding_end > self.coding_start):
            return self.coding_end - self.coding_start
        return self._mpv_duration or (self.player.duration if self.player else 0) or 0

    # MPV player
    def _init_mpv_player(self):
        if not self.parent.isVisible():
            self.parent.show()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        locale.setlocale(locale.LC_NUMERIC, "C")

        common_opts = dict(
            vo="libmpv",
            keep_open="yes",
            log_handler=lambda *a: None,
            profile="fast",
            video_sync="desync",
            framedrop="vo",
        )

        if sys.platform == "win32":
            platform_opts = dict(
                hwdec="auto-copy",
                opengl_swapinterval=0,
            )
        elif sys.platform == "darwin":
            platform_opts = dict(
                hwdec="auto-copy",
                opengl_swapinterval=0,
            )
        else:  # Linux
            platform_opts = dict(
                hwdec="auto-copy",
                opengl_swapinterval=0,
            )

        self.player = mpv.MPV(**common_opts, **platform_opts)
        self.gl_widget.init_mpv_render(self.player)

        # Observe mpv properties for progress updates (callbacks fire on mpv thread)
        @self.player.property_observer("time-pos")
        def _on_time_pos(_name, value):
            if self._shutting_down:
                return
            if value is not None:
                try:
                    self._time_pos_changed.emit(float(value))
                except RuntimeError:
                    pass

        @self.player.property_observer("duration")
        def _on_duration(_name, value):
            if self._shutting_down:
                return
            if value is not None and value > 0:
                try:
                    self._duration_changed.emit(float(value))
                except RuntimeError:
                    pass

    def _load_data_and_start(self):
        self.store.load_events()
        self.store.load_annotations()
        self._restore_active_state_events()
        self._update_annotations(scroll_to_bottom=True)
        self._populate_event_trees()
        self._init_progress_bar()
        self._restore_volume()
        self._load_session_state()
        self._auto_save_session_state()

        self.parent.update()

        self.player.pause = True
        self.player.play(self.video_path)

        # Safety: ensure GL widget is visible even if first-frame signal
        # never fires (e.g. codec issues or slow decode).
        def _ensure_gl_visible():
            if hasattr(self, "gl_widget") and self.gl_widget and not self.gl_widget.isVisible():
                self.gl_widget.show()
        QTimer.singleShot(2000, _ensure_gl_visible)

        # Apply saved video settings after player starts
        QTimer.singleShot(300, self._apply_video_settings)
        # Delay floating windows until after video starts
        QTimer.singleShot(500, self._show_floating_controls)
        # Start waveform extraction only if widget is already visible
        if hasattr(self, 'waveform_widget') and self.waveform_widget.isVisible():
            QTimer.singleShot(1000, self._start_waveform_extraction)

    def _show_floating_controls(self):
        create_toggle_buttons(self)
        cfg = get_config()
        if not cfg.get_show_events_toggle():
            w = getattr(self, "event_toggle_window", None)
            if w:
                w.setVisible(False)
        if not cfg.get_show_zoom_button():
            w = getattr(self, "zoom_toggle_window", None)
            if w:
                w.setVisible(False)
        self._update_annotations(scroll_to_bottom=True)
        self.update_play_pause_icon()

    # Annotation panel

    def _create_annotation_panel(self):
        tree_font = "12px"
        heading_font = "14px"

        available_h = self.panel_height - self.progress_bar_height
        btn_area_h = 95

        self.annotation_frame = QFrame(self)
        self.annotation_frame.setFrameShape(QFrame.Shape.NoFrame)
        self.annotation_frame.setStyleSheet(
            f"QFrame {{ background-color: {theme.color('panel_bg')}; border: none; }}")
        self.right_layout.addWidget(self.annotation_frame)

        main_layout = QVBoxLayout(self.annotation_frame)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        tree_style = theme.tree_stylesheet(heading_font)
        label_style = theme.heading_label_style(heading_font)
        btn_style = theme.button_stylesheet("11px")
        big_btn_style = theme.button_large_stylesheet("11px")

        def _make_tree(headers):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.NoFrame)
            frame.setStyleSheet("QFrame { border: none; background: transparent; }")
            frame.setMinimumHeight(60)
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            tree = QTreeWidget()
            tree.setRootIsDecorated(False)
            tree.setIndentation(10)
            tree.setStyleSheet(tree_style)
            tree.setHeaderLabels(headers)
            header = tree.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for i in range(1, len(headers)):
                header.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)
            tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            return frame, lay, tree

        # Track themed widgets for live re-theming
        self._heading_labels = []
        self._header_widgets = []
        self._panel_buttons = []
        self._big_buttons = []

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # State events
        sf, sl, self.state_events_tree = _make_tree(
            ["Event", "Key", "ME Group"])
        sb_header = QWidget()
        sb_header.setStyleSheet(theme.header_widget_stylesheet())
        self._header_widgets.append(sb_header)
        sb_hlay = QHBoxLayout(sb_header); sb_hlay.setContentsMargins(0, 0, 0, 0); sb_hlay.setSpacing(3)
        lbl = QLabel("State Events"); lbl.setStyleSheet(label_style)
        self._heading_labels.append(lbl)
        sb_hlay.addWidget(lbl)
        sb_hlay.addStretch()
        self._gear_btn = QPushButton(""); self._gear_btn.setStyleSheet(btn_style)
        self._gear_btn.setIcon(theme.themed_icon("settings"))
        self._gear_btn.setIconSize(QSize(16, 16))
        self._gear_btn.setFixedSize(26, 26)
        self._gear_btn.clicked.connect(self._show_settings_menu)
        self._panel_buttons.append(self._gear_btn)
        sb_hlay.addWidget(self._gear_btn)
        sl.insertWidget(0, sb_header)
        sl.addWidget(self.state_events_tree)
        splitter.addWidget(sf)

        # Point events
        pf, pl, self.point_events_tree = _make_tree(
            ["Event", "Key"])
        lbl2 = QLabel("Point Events"); lbl2.setStyleSheet(label_style)
        self._heading_labels.append(lbl2)
        pl.insertWidget(0, lbl2)
        pl.addWidget(self.point_events_tree)
        splitter.addWidget(pf)

        # State annotations
        saf, sal, self.state_annotations_tree = _make_tree(
            ["Event", "Start", "End"])
        for col in (1, 2):
            self.state_annotations_tree.headerItem().setTextAlignment(
                col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sa_header = QWidget()
        sa_header.setStyleSheet(theme.header_widget_stylesheet())
        self._header_widgets.append(sa_header)
        hlay = QHBoxLayout(sa_header); hlay.setContentsMargins(0, 0, 0, 0); hlay.setSpacing(3)
        lbl3 = QLabel("State Annotations"); lbl3.setStyleSheet(label_style)
        self._heading_labels.append(lbl3)
        hlay.addWidget(lbl3)
        sort_btn = QPushButton("Sort"); sort_btn.setStyleSheet(btn_style)
        sort_btn.setFixedWidth(50); sort_btn.setFixedHeight(22)
        sort_btn.clicked.connect(self._sort_state_annotations)
        self._panel_buttons.append(sort_btn)
        hlay.addStretch(); hlay.addWidget(sort_btn)
        sal.insertWidget(0, sa_header)
        self.state_annotations_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.state_annotations_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.state_annotations_tree.customContextMenuRequested.connect(
            self._show_annotation_menu)
        sal.addWidget(self.state_annotations_tree)
        splitter.addWidget(saf)

        # Point annotations
        paf, pal, self.point_annotations_tree = _make_tree(
            ["Event", "Time"])
        pa_header = QWidget()
        pa_header.setStyleSheet(theme.header_widget_stylesheet())
        self._header_widgets.append(pa_header)
        hlay2 = QHBoxLayout(pa_header); hlay2.setContentsMargins(0, 0, 0, 0); hlay2.setSpacing(8)
        lbl4 = QLabel("Point Annotations"); lbl4.setStyleSheet(label_style)
        self._heading_labels.append(lbl4)
        hlay2.addWidget(lbl4)
        sort_btn2 = QPushButton("Sort"); sort_btn2.setStyleSheet(btn_style)
        sort_btn2.setFixedWidth(50); sort_btn2.setFixedHeight(22)
        sort_btn2.clicked.connect(self._sort_point_annotations)
        self._panel_buttons.append(sort_btn2)
        hlay2.addStretch(); hlay2.addWidget(sort_btn2)
        pal.insertWidget(0, pa_header)
        self.point_annotations_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.point_annotations_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.point_annotations_tree.customContextMenuRequested.connect(
            self._show_annotation_menu)
        pal.addWidget(self.point_annotations_tree)
        splitter.addWidget(paf)

        saved_sizes = get_config().get_splitter_sizes()
        if saved_sizes and len(saved_sizes) == 4:
            splitter.setSizes(saved_sizes)
        else:
            quarter = (available_h - btn_area_h - 15) // 4
            splitter.setSizes([quarter, quarter, quarter, quarter])
        splitter.splitterMoved.connect(
            lambda: get_config().set_splitter_sizes(splitter.sizes()))
        main_layout.addWidget(splitter, 1)

        # Bottom buttons — two rows
        btn_frame = QFrame()
        btn_frame.setFixedHeight(btn_area_h)
        btn_outer = QVBoxLayout(btn_frame)
        btn_outer.setContentsMargins(0, 3, 0, 0)
        btn_outer.setSpacing(4)

        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)
        btn_h = 30
        grid_btns = [
            ("Coding Segment", self.set_coding_start, 0, 0),
            ("Visualize", self.visualize_annotations, 0, 1),
            ("Edit Event Key", self._edit_event_key, 0, 2),
            ("Mark Complete", self._mark_video_complete, 1, 0),
        ]
        for text, callback, row, col in grid_btns:
            b = _AutoFitButton(text)
            b.setStyleSheet(big_btn_style)
            b.setFixedHeight(btn_h)
            b.clicked.connect(callback)
            self._big_buttons.append(b)
            btn_grid.addWidget(b, row, col)
            if text == "Mark Complete":
                self._mark_complete_btn = b
        btn_outer.addLayout(btn_grid)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(2)

        ctrl_btn_w = 24
        ctrl_btn_h = 22
        ctrl_style = (
            f"QPushButton {{ background: transparent; color: {theme.color('text')};"
            f"  border: none; font-size: 18px; padding: 0px; }}"
            f"QPushButton:hover {{ background: rgba(128,128,128,40); border-radius: 3px; }}"
            f"QPushButton:pressed {{ background: rgba(128,128,128,80); border-radius: 3px; }}"
        )

        # Playback controls — left side
        playback_buttons = [
            ("back_big", lambda: self.seek_relative(-10000)),
            ("back",     lambda: self.seek_relative(-1000)),
            ("play",     self.toggle_play_pause),
            ("forward",  lambda: self.seek_relative(1000)),
            ("forward_big", lambda: self.seek_relative(10000)),
        ]

        self._ctrl_buttons = []
        for i, (icon_name, callback) in enumerate(playback_buttons):
            btn = QPushButton("")
            btn.setIcon(theme.themed_icon(icon_name))
            btn.setIconSize(QSize(16, 16))
            btn.setStyleSheet(ctrl_style)
            btn.setFixedSize(ctrl_btn_w, ctrl_btn_h)
            btn.clicked.connect(callback)
            self._ctrl_buttons.append(btn)
            audio_row.addWidget(btn)
            if i == 2:
                self._panel_play_pause_btn = btn

        # Spacer between playback and speed controls
        audio_row.addStretch()

        # Speed controls — center
        speed_down = QPushButton("")
        speed_down.setIcon(theme.themed_icon("minus"))
        speed_down.setIconSize(QSize(16, 16))
        speed_down.setStyleSheet(ctrl_style)
        speed_down.setFixedSize(ctrl_btn_w, ctrl_btn_h)
        speed_down.clicked.connect(lambda: self.change_speed(-1))
        self._ctrl_buttons.append(speed_down)
        audio_row.addWidget(speed_down)

        speed_up = QPushButton("")
        speed_up.setIcon(theme.themed_icon("plus"))
        speed_up.setIconSize(QSize(16, 16))
        speed_up.setStyleSheet(ctrl_style)
        speed_up.setFixedSize(ctrl_btn_w, ctrl_btn_h)
        speed_up.clicked.connect(lambda: self.change_speed(1))
        self._ctrl_buttons.append(speed_up)
        audio_row.addWidget(speed_up)

        # Spacer between speed and volume controls
        audio_row.addStretch()

        # Volume slider and mute — right side
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(100)
        self._volume_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self._volume_slider.setMaximumWidth(80)
        self._volume_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #555; height: 6px;"
            "  border-radius: 3px; }"
            "QSlider::handle:horizontal { background: #ccc; width: 12px;"
            "  margin: -3px 0; border-radius: 6px; }"
            "QSlider::sub-page:horizontal { background: #888; border-radius: 3px; }"
        )
        self._volume_slider.valueChanged.connect(self._on_volume_changed)

        def _volume_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                val = QStyle.sliderValueFromPosition(
                    self._volume_slider.minimum(),
                    self._volume_slider.maximum(),
                    int(event.position().x()),
                    self._volume_slider.width())
                self._volume_slider.setValue(val)
            QSlider.mousePressEvent(self._volume_slider, event)

        self._volume_slider.mousePressEvent = _volume_click
        audio_row.addWidget(self._volume_slider)

        self._mute_btn = QPushButton("")
        self._mute_btn.setIcon(theme.themed_icon("sound"))
        self._mute_btn.setIconSize(QSize(16, 16))
        self._mute_btn.setStyleSheet(ctrl_style)
        self._mute_btn.setFixedSize(ctrl_btn_w, ctrl_btn_w)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._ctrl_buttons.append(self._mute_btn)
        audio_row.addWidget(self._mute_btn)

        btn_outer.addLayout(audio_row)

        main_layout.addWidget(btn_frame)

        # Click-selection handlers
        self.state_annotations_tree.itemClicked.connect(
            lambda item: self._handle_tree_selection(
                self.state_annotations_tree, item))
        self.point_annotations_tree.itemClicked.connect(
            lambda item: self._handle_tree_selection(
                self.point_annotations_tree, item))

    # Annotation data helpers

    def _update_annotations(self, scroll_to_bottom=False):
        for tree, events, fmt_fn in [
            (self.state_annotations_tree, self.store.state_events,
             lambda evt: [evt["Event"],
                          format_time_human(evt["start_time"]),
                          format_time_human(evt["end_time"]) if evt["end_time"] else ""]),
            (self.point_annotations_tree, self.store.point_events,
             lambda evt: [evt["Event"], evt["time"]]),
        ]:
            scrollbar = tree.verticalScrollBar()
            saved_pos = scrollbar.value()
            tree.clear()
            for evt in events:
                item = QTreeWidgetItem(fmt_fn(evt))
                if tree is self.state_annotations_tree:
                    for col in (1, 2):
                        item.setTextAlignment(
                            col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tree.addTopLevelItem(item)
            if scroll_to_bottom:
                n = tree.topLevelItemCount()
                if n > 0:
                    tree.scrollToItem(
                        tree.topLevelItem(n - 1),
                        QAbstractItemView.ScrollHint.EnsureVisible)
            else:
                scrollbar.setValue(saved_pos)

    def _populate_event_trees(self):
        self.state_events_tree.clear()
        self.point_events_tree.clear()
        cfg = get_config()
        state_hex = cfg.get_state_highlight_color()
        point_hex = cfg.get_point_highlight_color()
        active_color = (QColor(state_hex) if state_hex
                        else theme.qcolor("active_color"))
        highlight_color = (QColor(point_hex) if point_hex
                           else theme.qcolor("highlight_color"))

        for name, key, btype, me_group in self.store.events:
            if btype == "state":
                item = QTreeWidgetItem([name, key, me_group])
                if key in self.active_state_events:
                    for c in range(item.columnCount()):
                        item.setBackground(c, active_color)
                self.state_events_tree.addTopLevelItem(item)
            elif btype == "point":
                item = QTreeWidgetItem([name, key])
                if key in self.used_point_events:
                    for c in range(item.columnCount()):
                        item.setBackground(c, highlight_color)
                    QTimer.singleShot(
                        250, lambda i=item: self._remove_highlight(i))
                self.point_events_tree.addTopLevelItem(item)

    def _remove_highlight(self, item):
        tree = self.point_events_tree
        if item in [tree.topLevelItem(i)
                    for i in range(tree.topLevelItemCount())]:
            for c in range(item.columnCount()):
                item.setBackground(c, QColor("transparent"))

    # Settings menu

    def _show_settings_menu(self):
        menu = QMenu(self.parent)
        menu.setStyleSheet(theme.menu_stylesheet())

        cfg = get_config()

        controls_action = menu.addAction("Show Floating Controls")
        controls_action.setCheckable(True)
        controls_action.setChecked(
            hasattr(self, "floating_controls_window")
            and self.floating_controls_window is not None)
        controls_action.triggered.connect(
            lambda checked: self._toggle_floating_item(
                "video_controls", checked))

        waveform_action = menu.addAction("Show Audio Track")
        waveform_action.setCheckable(True)
        waveform_action.setChecked(
            hasattr(self, "waveform_widget")
            and self.waveform_widget.isVisible())
        waveform_action.triggered.connect(
            lambda checked: self._toggle_floating_item(
                "waveform", checked))

        events_action = menu.addAction("Show Events Toggle")
        events_action.setCheckable(True)
        events_action.setChecked(cfg.get_show_events_toggle())
        events_action.triggered.connect(
            lambda checked: self._toggle_floating_item(
                "events", checked))

        zoom_action = menu.addAction("Show Zoom Button")
        zoom_action.setCheckable(True)
        zoom_action.setChecked(cfg.get_show_zoom_button())
        zoom_action.triggered.connect(
            lambda checked: self._toggle_floating_item(
                "zoom", checked))

        menu.addSeparator()
        menu.addAction("Audio && Video Settings").triggered.connect(
            self._show_av_settings_dialog)
        menu.addAction("Appearance").triggered.connect(
            self._show_colors_theme_dialog)

        btn = self.sender()
        if btn:
            self.player.pause = True
            self.dialog_open = True
            try:
                menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
            finally:
                self.dialog_open = False

    def _toggle_floating_item(self, item, checked):
        from floating_controls import toggle_floating_controls
        cfg = get_config()
        if item == "video_controls":
            has_panel = (hasattr(self, "floating_controls_window")
                         and self.floating_controls_window is not None)
            if checked and not has_panel:
                toggle_floating_controls(self)
            elif not checked and has_panel:
                toggle_floating_controls(self)
        elif item == "waveform":
            self._toggle_waveform()
        elif item == "events":
            cfg.set_show_events_toggle(checked)
            w = getattr(self, "event_toggle_window", None)
            if w:
                w.setVisible(checked)
            # Also hide/show the expanded event buttons panel
            w2 = getattr(self, "event_buttons_window", None)
            if w2 and not checked:
                w2.setVisible(False)
        elif item == "zoom":
            cfg.set_show_zoom_button(checked)
            w = getattr(self, "zoom_toggle_window", None)
            if w:
                w.setVisible(checked)
            w2 = getattr(self, "zoom_slider_window", None)
            if w2 and not checked:
                w2.setVisible(False)

    def _show_av_settings_dialog(self):
        from dialogs import show_av_settings_dialog
        show_av_settings_dialog(self)

    def _show_colors_theme_dialog(self):
        from floating_controls import toggle_event_buttons
        self.dialog_open = True

        def _on_accept(new_theme, colors):
            # Full theme refresh (panels, trees, buttons, etc.)
            self._apply_theme(new_theme)
            # Refresh annotator-specific elements
            self._populate_event_trees()
            self.progress_bar.set_fill_color(colors["progress_fill"])
            self.progress_bar.update()
            if hasattr(self, 'waveform_widget'):
                cfg = get_config()
                self.waveform_widget.set_fill_color(
                    colors.get("waveform_fill", QColor(0, 150, 255)))
                self.waveform_widget.set_opacity(cfg.get_waveform_opacity())
                new_h = int(self.progress_bar_height
                            * cfg.get_waveform_height_multiplier())
                self.waveform_widget.setFixedHeight(new_h)
                if self.waveform_widget.isVisible():
                    self.video_frame.setFixedHeight(self.video_height - new_h)
            if (hasattr(self, "event_buttons_window")
                    and self.event_buttons_window):
                toggle_event_buttons(self)
                toggle_event_buttons(self)

        dlg = show_colors_theme_dialog(self.parent, on_accept=_on_accept)
        dlg.finished.connect(lambda _: setattr(self, 'dialog_open', False))

    def _apply_video_settings(self):
        """Apply saved video settings to the player. Per-video overrides global"""
        per_video = self.store.load_video_settings()
        if per_video:
            settings = per_video
        else:
            settings = get_config().get_video_settings()
        for prop in ("brightness", "contrast", "gamma", "saturation", "hue"):
            val = settings.get(prop, 0)
            if val != 0:
                try:
                    setattr(self.player, prop, val)
                except Exception:
                    pass

    def _apply_theme(self, name):
        theme.load_theme(name)
        cfg = get_config()
        cfg.update_theme(name)

        heading_font = "14px"

        # Re-apply global stylesheet
        app = QApplication.instance()
        app.setStyleSheet(theme.app_stylesheet())

        # Re-apply main window background
        self.parent.apply_theme()

        # Re-apply annotation panel frame
        self.annotation_frame.setStyleSheet(
            f"QFrame {{ background-color: {theme.color('panel_bg')}; border: none; }}")

        # Re-apply tree styles
        tree_style = theme.tree_stylesheet(heading_font)
        for tree in (self.state_events_tree, self.point_events_tree,
                     self.state_annotations_tree, self.point_annotations_tree):
            tree.setStyleSheet(tree_style)

        # Re-apply heading labels
        label_style = theme.heading_label_style(heading_font)
        for lbl in self._heading_labels:
            lbl.setStyleSheet(label_style)

        # Re-apply header widget backgrounds
        header_bg = theme.header_widget_stylesheet()
        for hw in self._header_widgets:
            hw.setStyleSheet(header_bg)

        # Re-apply small panel buttons (Sort, gear)
        btn_style = theme.button_stylesheet("11px")
        for btn in self._panel_buttons:
            btn.setStyleSheet(btn_style)
        if hasattr(self, '_gear_btn'):
            self._gear_btn.setIcon(theme.themed_icon("settings"))

        # Re-apply transport control buttons
        ctrl_style = (
            f"QPushButton {{ background: transparent; color: {theme.color('text')};"
            f"  border: none; font-size: 18px; padding: 0px; }}"
            f"QPushButton:hover {{ background: rgba(128,128,128,40); border-radius: 3px; }}"
            f"QPushButton:pressed {{ background: rgba(128,128,128,80); border-radius: 3px; }}"
        )
        ctrl_icons = ["back_big", "back", "play", "forward", "forward_big",
                      "minus", "plus"]
        for i, btn in enumerate(getattr(self, '_ctrl_buttons', [])):
            btn.setStyleSheet(ctrl_style)
            if i < len(ctrl_icons):
                icon_name = ctrl_icons[i]
                if i == 2:
                    paused = getattr(self.player, 'pause', True)
                    icon_name = "play" if paused else "pause"
                btn.setIcon(theme.themed_icon(icon_name))
        mute_btn = getattr(self, '_mute_btn', None)
        if mute_btn:
            muted = getattr(self.player, 'mute', False)
            mute_btn.setIcon(theme.themed_icon("mute" if muted else "sound"))

        # Re-apply big bottom buttons
        big_btn_style = theme.button_large_stylesheet("11px")
        for btn in self._big_buttons:
            btn.setStyleSheet(big_btn_style)

        # Refresh QPainter-based widgets
        self.progress_bar.update()

        # Refresh floating toggle buttons
        for attr in ("event_toggle_button",):
            btn = getattr(self, attr, None)
            if btn:
                try:
                    btn.setStyleSheet(theme.toggle_btn_stylesheet())
                    btn.setIcon(theme.themed_icon("event_toggle"))
                except RuntimeError:
                    pass
        if hasattr(self, "zoom_toggle_button") and self.zoom_toggle_button:
            try:
                if self.zoom_active:
                    self.zoom_toggle_button.setStyleSheet(theme.zoom_active_stylesheet())
                else:
                    self.zoom_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
                self.zoom_toggle_button.setIcon(theme.themed_icon("zoom"))
            except RuntimeError:
                pass

        # Recreate floating controls if open (to pick up new styles)
        if hasattr(self, "floating_controls_window") and self.floating_controls_window:
            toggle_floating_controls(self)
            toggle_floating_controls(self)
        if hasattr(self, "event_buttons_window") and self.event_buttons_window:
            toggle_event_buttons(self)
            toggle_event_buttons(self)

    # Sorting

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

    # Session state

    def save_session_state(self):
        current = self.player.time_pos
        if current is None:
            return False
        ok = self.store.save_session_state(
            float(current), self.coding_start, self.coding_duration,
            self.coding_end, self.coding_end_reached,
            self.limit_timeline_to_coding)
        if not ok and not getattr(self, "_auto_saving", False):
            self.on_write_error(
                "Cannot save session state.\n"
                "Is the file open in another application?")
        return ok

    def _restore_active_state_events(self):
        """Re-populate active_state_events from incomplete annotations on disk"""
        name_to_key = {v: k for k, v in self.store.state_event_keys.items()}
        for evt in self.store.state_events:
            if evt["end_time"] is None and evt["start_time"] is not None:
                key = name_to_key.get(evt["Event"])
                if key:
                    self.active_state_events[key] = evt["start_time"]

    def _load_session_state(self):
        state = self.store.load_session_state()
        if state is None:
            self._update_mark_complete_btn(False)
            self.update_coding_info_display()
            return

        self.coding_start = state["coding_start"]
        self.coding_duration = state["coding_duration"]
        self.coding_end = state["coding_end"]
        self.coding_end_reached = state["coding_end_reached"]
        self.limit_timeline_to_coding = state.get("limit_timeline_to_coding", False)
        self._update_mark_complete_btn(state.get("completed", False))
        self.update_coding_info_display()

        ts = state["timestamp_sec"]
        self._schedule_resume(ts)

        if self.coding_end is not None and ts >= self.coding_end:
            self.coding_end_reached = True

    def _auto_save_session_state(self):
        if self._shutting_down:
            return
        try:
            if (hasattr(self, "player") and self.player
                    and self.parent and self.parent.isVisible()):
                self._auto_saving = True
                ok = self.save_session_state()
                if not ok:
                    self._auto_save_failures = getattr(
                        self, "_auto_save_failures", 0) + 1
                    if self._auto_save_failures >= 3:
                        # Volume may be disconnected — stop hammering
                        self._auto_saving = False
                        logger.warning("Auto-save failed %d times, pausing",
                                       self._auto_save_failures)
                        if self._shutting_down:
                            return
                        self._show_warning(
                            "Save Error",
                            "Unable to save session state after multiple "
                            "attempts.\nIs the output drive still connected?\n\n"
                            "Auto-save has been paused.")
                        return
                else:
                    self._auto_save_failures = 0
            else:
                return
        finally:
            self._auto_saving = False

        if not self._shutting_down and self.parent and self.parent.isVisible():
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

    # Key bindings

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
            (Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(5000)),
            (Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(-5000)),
            Qt.Key.Key_Equal: blocked(lambda: self.change_speed(1)),
            Qt.Key.Key_Plus: blocked(lambda: self.change_speed(1)),
            Qt.Key.Key_Minus: blocked(lambda: self.change_speed(-1)),
            Qt.Key.Key_Underscore: blocked(lambda: self.change_speed(-1)),
            Qt.Key.Key_Backspace: blocked(self._reset_speed),
            Qt.Key.Key_Escape: self.return_to_file_selection,
            Qt.Key.Key_Delete: blocked(self.delete_annotation),
            (Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier): blocked(self.undo_delete),
            (Qt.Key.Key_Z, Qt.KeyboardModifier.MetaModifier): blocked(self.undo_delete),
            Qt.Key.Key_Comma: blocked(self.frame_back_step),
            Qt.Key.Key_Period: blocked(self.frame_step),
        }

        if get_config().get_wasd_navigation():
            self.key_bindings.update({
                (Qt.Key.Key_D, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(1000)),
                (Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier): blocked(lambda: self.seek_relative(-1000)),
                (Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(5000)),
                (Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier): blocked(lambda: self.seek_relative(-5000)),
                Qt.Key.Key_W: blocked(lambda: self.seek_relative(10000)),
                Qt.Key.Key_S: blocked(lambda: self.seek_relative(-10000)),
            })

    def eventFilter(self, obj, event):
        if self._shutting_down:
            return super().eventFilter(obj, event)

        etype = event.type()

        # Fast path: skip events we never handle (paint, timer, layout, etc.)
        if etype not in self._watched_events:
            return super().eventFilter(obj, event)

        if etype != QEvent.Type.KeyPress:
            if obj is not self.parent and obj is not self.gl_widget:
                if not (sys.platform == "darwin"
                        and etype == QEvent.Type.MouseButtonPress):
                    return super().eventFilter(obj, event)

        if obj is self.parent:
            if etype == QEvent.Type.Move:
                self._reposition_floating_windows()

            if etype in (QEvent.Type.ActivationChange,
                        QEvent.Type.WindowStateChange):
                state = self.parent.windowState()
                is_minimized = bool(
                    state & Qt.WindowState.WindowMinimized
                )
                if is_minimized:
                    self._set_floating_visible(False)
                elif not self._activation_pending:
                    self._activation_pending = True
                    QTimer.singleShot(
                        100, self._handle_activation_deferred)

        if (sys.platform == "darwin"
                and etype == QEvent.Type.MouseButtonPress
                and isinstance(obj, QWidget)):

            obj_window = obj.window()
            if obj_window == self.parent or obj_window in self.floating_windows:
                self._hide_pending = False
                self._suppress_floating_hide = True
                QTimer.singleShot(
                    600, lambda: setattr(self, '_suppress_floating_hide', False))

        if (obj is self.gl_widget
                and self.zoom_active
                and hasattr(self, "player") and self.player):
            if etype == QEvent.Type.MouseButtonPress:
                pos = event.position() if hasattr(event, "position") else event.pos()
                click_x = pos.x() / self.gl_widget.width()
                click_y = pos.y() / self.gl_widget.height()

                cur_zoom = self.player.video_zoom or 0
                if cur_zoom == 0:
                    # First click: zoom in centered on click location
                    self._zoom_pan_x = 0.5 - click_x
                    self._zoom_pan_y = 0.5 - click_y
                    self.player.video_zoom = math.log2(self._zoom_multiplier)
                    self.player.video_pan_x = self._zoom_pan_x
                    self.player.video_pan_y = self._zoom_pan_y
                else:
                    # Already zoomed: start drag
                    self._drag_start_x = pos.x()
                    self._drag_start_y = pos.y()
                    self._drag_pan_start_x = self._zoom_pan_x
                    self._drag_pan_start_y = self._zoom_pan_y
                return True

            if etype == QEvent.Type.MouseMove and (self.player.video_zoom or 0) > 0:
                if hasattr(self, "_drag_start_x"):
                    pos = event.position() if hasattr(event, "position") else event.pos()
                    w = self.gl_widget.width()
                    vid_w = self.player.width or 1
                    vid_h = self.player.height or 1
                    displayed_h = w * vid_h / vid_w
                    dx = (pos.x() - self._drag_start_x) / w
                    dy = (pos.y() - self._drag_start_y) / displayed_h
                    scale = 2 ** (self.player.video_zoom or 1)
                    self._zoom_pan_x = self._drag_pan_start_x + dx / scale
                    self._zoom_pan_y = self._drag_pan_start_y + dy / scale
                    self.player.video_pan_x = self._zoom_pan_x
                    self.player.video_pan_y = self._zoom_pan_y
                    return True

            if etype == QEvent.Type.MouseButtonRelease:
                if hasattr(self, "_drag_start_x"):
                    del self._drag_start_x
                    del self._drag_start_y
                return True

        if etype == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if event.isAutoRepeat() and key not in (
                    Qt.Key.Key_Up, Qt.Key.Key_Down):
                if not self.dialog_open:
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
                if char and char in self.store.event_map:
                    self._handle_event_key(char)
                    return True

        elif event.type() == QEvent.Type.KeyRelease:
            if not self.dialog_open:
                char = event.text().lower()
                if char and char in self.store.event_map:
                    self.pressed_keys.discard(char)
                    return True

        return super().eventFilter(obj, event)

    # Event handling

    def _handle_event_key(self, key):
        info = self.store.event_map[key]
        current = self.player.time_pos or 0
        fmt = format_time_human(current)
        logger.info("Event key '%s' (%s) at %s", key, info["Type"], fmt)

        if info["Type"] == "State":
            self.handle_state_event(key, current, fmt)
        elif info["Type"] == "Point":
            self._add_point_annotation(key, info, current, fmt)

    def add_annotation_for_event(self, key):
        key = key.lower()
        if key not in self.store.event_map:
            return
        info = self.store.event_map[key]
        current = self.player.time_pos or 0
        fmt = format_time_human(current)

        if info["Type"] == "State":
            self.handle_state_event(key, current, fmt)
        elif info["Type"] == "Point":
            self._add_point_annotation(key, info, current, fmt)

    def _add_point_annotation(self, key, info, current_time, formatted_time):
        if any(e["Event"] == info["Event"] and e["time"] == formatted_time
               for e in self.store.point_events):
            return

        record = {
            "Video": self.video_name, "Event": info["Event"], "Type": "Point",
            "Mutually_Exclusive": "False", "H_Start": formatted_time,
            "H_End": "", "Start": f"{current_time:.2f}", "End": "",
            "Duration": "", "Manual_Edit": "False", "Notes": "",
        }

        if not self.store.append_annotation(record):
            self.on_write_error()
            return

        self.store.point_events.append({
            "Event": info["Event"], "time": formatted_time,
            "Manual_Edit": False, "Notes": "",
        })
        self.used_point_events.add(key)
        QTimer.singleShot(100, lambda: self.used_point_events.discard(key))
        self._update_annotations(scroll_to_bottom=True)
        self._populate_event_trees()

    def handle_state_event(self, key, frame_ts, formatted_ts):
        name = self.store.state_event_keys.get(key)
        me_group = self.store.me_groups.get(key)

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            return False

        if key in self.active_state_events:
            start = self.active_state_events[key]
            dur = frame_ts - start
            if dur <= 0:
                if self.player:
                    self.player.pause = True
                self._show_warning(
                    "Invalid Annotation",
                    f"Cannot end \"{name}\": the current time "
                    f"({format_time_human(frame_ts)}) is not after the start time "
                    f"({format_time_human(start)}).\n\n"
                    "Please seek to a point after the start time and try again."
                )
                return False
            self.active_state_events.pop(key)
            for evt in self.store.state_events:
                if evt["Event"] == name and evt["end_time"] is None:
                    evt["end_time"] = frame_ts
                    break
            if not self.store.save_sorted_annotations():
                return False
            self._update_annotations()
            self._populate_event_trees()
            return True
        else:
            if me_group:
                if not self._deactivate_me_group(me_group, frame_ts, key):
                    return False

            record = {
                "Video": self.video_name, "Event": name, "Type": "State",
                "Mutually_Exclusive": "True" if me_group else "False",
                "H_Start": format_time_human(frame_ts),
                "H_End": "NA",
                "Start": format_time_machine(frame_ts),
                "End": "NA", "Duration": "NA",
                "Manual_Edit": "False", "Notes": "",
            }
            if not self.store.append_annotation(record):
                self.on_write_error()
                return False

            self.active_state_events[key] = frame_ts
            self.store.state_events.append({
                "Event": name, "start_time": frame_ts, "end_time": None,
                "Type": "State",
                "Mutually_Exclusive": "True" if me_group else "False",
                "Notes": "",
            })
            self._update_annotations(scroll_to_bottom=True)
            self._populate_event_trees()
            return True

    def _deactivate_me_group(self, me_group, frame_ts, current_key):
        to_deactivate = [
            k for k in self.active_state_events
            if self.store.me_groups.get(k) == me_group and k != current_key]

        if not to_deactivate:
            return True

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error(
                "Cannot deactivate mutually exclusive events.\n"
                "Annotations file is inaccessible.")
            return False

        removed = []
        for key in to_deactivate:
            start = self.active_state_events[key]
            name = self.store.state_event_keys.get(key)
            dur = frame_ts - start
            if dur <= 0:
                if self.player:
                    self.player.pause = True
                self._show_warning(
                    "Invalid Annotation",
                    f"Cannot end \"{name}\": the current time "
                    f"({format_time_human(frame_ts)}) is not after the start time "
                    f"({format_time_human(start)}).\n\n"
                    "Please seek to a point after the start time and try again."
                )
                return False

            removed.append(key)
            for evt in self.store.state_events:
                if evt["Event"] == name and evt["end_time"] is None:
                    evt["end_time"] = frame_ts
                    break

        for key in removed:
            self.active_state_events.pop(key)

        if removed:
            if not self.store.save_sorted_annotations():
                return False
            self._update_annotations()
            self._populate_event_trees()
        return True

    # Playback controls

    def toggle_play_pause(self):
        paused = not self.player.pause
        self.player.pause = paused
        logger.debug("Play/pause toggled: paused=%s", paused)
        self._set_play_pause_icon(paused)

    def update_play_pause_icon(self):
        paused = getattr(self.player, 'pause', True)
        self._set_play_pause_icon(paused)

    def _set_play_pause_icon(self, paused):
        icon = theme.themed_icon("play" if paused else "pause")
        btn = getattr(self, "play_pause_btn", None)
        if btn and btn.isVisible():
            try:
                btn.setIcon(icon)
            except RuntimeError:
                self.play_pause_btn = None
        panel_btn = getattr(self, "_panel_play_pause_btn", None)
        if panel_btn:
            try:
                panel_btn.setIcon(icon)
            except RuntimeError:
                self._panel_play_pause_btn = None

    def _restore_volume(self):
        cfg = get_config()
        vol = cfg.get_volume()
        muted = cfg.get_muted()
        self._volume_slider.blockSignals(True)
        if muted:
            self._volume_slider.setValue(0)
        else:
            self._volume_slider.setValue(vol)
        self._volume_slider.blockSignals(False)
        if self.player:
            self.player.mute = muted
            self.player.volume = vol
        self._mute_btn.setIcon(theme.themed_icon("mute" if muted else "sound"))

    def _toggle_mute(self):
        if not self.player:
            return
        cfg = get_config()
        if not self.player.mute:
            # Mute: save current volume, move slider to 0
            self.player.mute = True
            cfg.set_muted(True)
            self._volume_slider.blockSignals(True)
            self._volume_slider.setValue(0)
            self._volume_slider.blockSignals(False)
        else:
            # Unmute: restore saved volume
            self.player.mute = False
            cfg.set_muted(False)
            vol = cfg.get_volume()
            self._volume_slider.blockSignals(True)
            self._volume_slider.setValue(vol)
            self._volume_slider.blockSignals(False)
        self._mute_btn.setIcon(theme.themed_icon("mute" if self.player.mute else "sound"))

    def _on_volume_changed(self, value):
        if not self.player:
            return
        cfg = get_config()
        if value == 0 and not self.player.mute:
            # Slider dragged to zero: mute
            self.player.mute = True
            cfg.set_muted(True)
            self._mute_btn.setIcon(theme.themed_icon("mute"))
        elif value > 0 and self.player.mute:
            # Slider dragged up from zero: unmute
            self.player.mute = False
            cfg.set_muted(False)
            self._mute_btn.setIcon(theme.themed_icon("sound"))
        if value > 0:
            cfg.set_volume(value)
        self.player.volume = value

    def seek_relative(self, offset_ms):
        total = self.player.duration or 0
        current = self.player.time_pos or 0
        new_time = current + offset_ms / 1000.0

        # Clamp to coding segment when timeline is limited
        if (self.limit_timeline_to_coding
                and self.coding_start is not None
                and self.coding_end is not None
                and self.coding_end > self.coding_start):
            new_time = max(self.coding_start, min(new_time, self.coding_end))

        if new_time >= total:
            new_time = max(0, total - 0.5)
            self.player.time_pos = new_time
            self.player.pause = True
        else:
            self.player.time_pos = max(0, new_time)

        self._reset_coding_end_flag()
        self.update_progress()

    def frame_step(self):
        """Advance one frame forward."""
        self.player.command("frame-step")
        self._reset_coding_end_flag()
        QTimer.singleShot(100, self.update_progress)

    def frame_back_step(self):
        """Step one frame backward using precise seek for responsiveness."""
        self.player.pause = True
        fps = self.player.container_fps or self.player.estimated_vf_fps
        if fps and fps > 0:
            self.player.command("seek", -1.0 / fps, "relative+exact")
        else:
            self.player.command("frame-back-step")
        self._reset_coding_end_flag()
        QTimer.singleShot(100, self.update_progress)

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
            if new_rate < current:
                self.player.command("seek", 0, "relative+exact")
            self.progress_bar.set_center_text(f"({new_rate:.1f}x)")
            self.progress_bar.update()

    def _reset_speed(self):
        if self.player.speed != 1.0:
            self.player.speed = 1.0
            self.player.command("seek", 0, "relative+exact")
            self.progress_bar.set_center_text("(1.0x)")
            self.progress_bar.update()

    def _reset_coding_end_flag(self):
        current = self.player.time_pos or 0
        if (self.coding_duration is not None
                and self.coding_start is not None
                and current < self.coding_start + self.coding_duration - 0.5
                and self.coding_end_reached):
            self.coding_end_reached = False

    # Selection helpers

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

    # Context menu & annotation actions

    def _show_annotation_menu(self, point):
        if self.player:
            self.player.pause = True

        tree = self.sender()
        self.selected_treeview = tree
        item = tree.itemAt(point)
        if not item:
            return

        selected = tree.selectedItems()
        menu = QMenu(self.parent)
        menu.setStyleSheet(theme.menu_stylesheet())

        if len(selected) > 1:
            count = len(selected)
            menu.addAction(f"Delete Selected ({count})",
                           self._delete_selected_annotations)
        else:
            tree.setCurrentItem(item)
            self.selected_item = item
            self.selected_index = tree.indexOfTopLevelItem(item)
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

    def _delete_selected_annotations(self):
        if self.selected_treeview is None:
            return

        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            return

        tree = self.selected_treeview
        selected = tree.selectedItems()
        if not selected:
            return

        indices = sorted(
            [tree.indexOfTopLevelItem(item) for item in selected],
            reverse=True)

        is_state = (tree == self.state_annotations_tree)
        lst = self.store.state_events if is_state else self.store.point_events
        atype = "state" if is_state else "point"

        for idx in indices:
            if 0 <= idx < len(lst):
                deleted = dict(lst[idx])
                self.undo_stack.append((atype, idx, deleted))
                lst.pop(idx)

        if not self.store.save_sorted_annotations():
            return

        self._update_annotations()
        self._populate_event_trees()
        self.selected_treeview = None
        self.selected_item = None
        self.selected_index = None

    def delete_annotation(self):
        if self.selected_treeview is None or self.selected_item is None:
            return
        logger.info("Delete annotation at index %s", self.selected_index)

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
        self._populate_event_trees()
        self.selected_treeview = None
        self.selected_item = None
        self.selected_index = None

    def undo_delete(self):
        if not self.undo_stack:
            return
        logger.info("Undo delete")

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
        self._populate_event_trees()

    # Delegates to dialog module

    def set_coding_start(self):
        show_coding_start_dialog(self)

    def add_note_to_annotation(self):
        show_note_dialog(self)

    def view_annotation_details(self):
        show_annotation_details(self)

    # Save helpers (point / state edit callbacks used by dialogs)

    def save_point_annotation(self, new_entries, dialog, selected, old_time):
        if not self.store.check_file_access():
            if self.player:
                self.player.pause = True
            self.on_write_error()
            dialog.reject()
            return False

        new_name = new_entries["Event"].text().strip()
        new_start = new_entries["H_Start"].text().strip()
        if not new_name or not new_start:
            show_message(
                self.parent, "Invalid Input",
                "Both Event and Start Time are required.")
            return False

        for ann in self.store.point_events:
            if ann["Event"] == selected["Event"] and ann["time"] == old_time:
                if ann["Event"] != new_name or ann["time"] != new_start:
                    ann["Manual_Edit"] = True
                ann["Event"] = new_name
                ann["time"] = new_start
                break
        else:
            dialog.reject()
            return False

        if not self.store.save_sorted_annotations():
            for ann in self.store.point_events:
                if ann["Event"] == new_name and ann["time"] == new_start:
                    ann["Event"] = selected["Event"]
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

        new_name = new_entries["Event"].text().strip()
        new_h_start = new_entries["H_Start"].text().strip()
        new_h_end = new_entries["H_End"].text().strip()
        if not new_name or not new_h_start or not new_h_end:
            show_message(
                self.parent, "Invalid Input",
                "Event, Start, and End times are required.")
            return False

        try:
            new_start = parse_time(new_h_start)
            new_end = parse_time(new_h_end)
        except ValueError:
            show_message(
                self.parent, "Invalid Time Format",
                "Could not parse time values. Please check format.")
            return False

        original = None
        for ann in self.store.state_events:
            if (ann["Event"] == selected["Event"]
                    and format_time_human(ann.get("start_time", 0)) == old_time):
                original = dict(ann)
                ann["Event"] = new_name
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
                if ann["Event"] == new_name and ann["start_time"] == new_start:
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
        with open(self.store.annotations_file, "r", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if (row.get("Event", "") == annotation["Event"]
                        and row["H_Start"] == format_time_human(
                            annotation.get("start_time", 0))):
                    result.update({f: row.get(f, "") for f in fields})
                    break
                elif row.get("H_Start") == annotation.get("time"):
                    result.update({f: row.get(f, "") for f in fields})
                    break
        return result

    # Visualize annotations

    def visualize_annotations(self):
        was_playing = False
        if self.player:
            was_playing = not self.player.pause
            self.player.pause = True

        self.dialog_open = True

        def _on_viz_closed():
            self.dialog_open = False
            self._set_floating_visible(True)
            if self.player and was_playing:
                self.player.pause = False

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

            self._set_floating_visible(False)
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
                store=self.store,
                on_closed=_on_viz_closed,
            )
        except ImportError:
            self.dialog_open = False
            self._set_floating_visible(True)
            self._show_warning(
                "Visualization Module Error",
                "Could not load the visualization module.")
        except Exception as exc:
            self.dialog_open = False
            self._set_floating_visible(True)
            self._show_warning(
                "Visualization Error",
                f"Failed to create visualization: {exc}")

    def _load_annotations_for_viz(self):
        state_ann, point_ann = [], []
        if not os.path.exists(self.store.annotations_file):
            return list(self.store.state_events), list(self.store.point_events)

        try:
            with open(self.store.annotations_file, "r", newline="", encoding="utf-8-sig") as fh:
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
                            "Mutually_Exclusive": row.get("Mutually_Exclusive", "False"),
                            "Notes": row.get("Notes", ""),
                        })
                    elif atype == "point":
                        raw = row.get("Start", "0").strip()
                        point_ann.append({
                            "Event": row.get("Event", "").strip(),
                            "time": row.get("H_Start", "").strip(),
                            "raw_time": float(raw) if raw and raw != "NA" else 0,
                            "Manual_Edit": row.get("Manual_Edit", "False"),
                            "Notes": row.get("Notes", ""),
                        })
        except Exception:
            return list(self.store.state_events), list(self.store.point_events)

        return state_ann, point_ann

    # Event key editor

    def _mark_video_complete(self):
        is_complete = self._video_completed
        if is_complete:
            action_text = "Mark this video as in progress?"
            title = "Mark In Progress"
        else:
            action_text = "Mark this video as complete?"
            title = "Mark Complete"

        self.dialog_open = True
        msg = QMessageBox(self.parent)
        msg.setWindowTitle(title)
        msg.setText(action_text)
        theme.apply_dialog_theme(msg)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)

        def _on_finished(result):
            self.dialog_open = False
            msg.deleteLater()
            if result == QMessageBox.StandardButton.Yes:
                if is_complete:
                    self.store.unmark_completed()
                    self._update_mark_complete_btn(False)
                else:
                    self.store.mark_completed()
                    self._update_mark_complete_btn(True)

        msg.finished.connect(_on_finished)
        msg.open()

    def _update_mark_complete_btn(self, completed):
        self._video_completed = completed
        if hasattr(self, "_mark_complete_btn"):
            if completed:
                self._mark_complete_btn.setText("Mark\nIn Progress")
            else:
                self._mark_complete_btn.setText("Mark Video\nComplete")

    def _edit_event_key(self):
        f"parent.windowState={self.parent.windowState()}"
        was_playing = False
        if self.player:
            was_playing = not self.player.pause
            self.player.pause = True

        self.save_session_state()
        saved = (self.coding_start, self.coding_duration,
                 getattr(self, "coding_end", None), self.coding_end_reached)

        self.dialog_open = True

        try:
            from event_key_editor import EventKeyEditor
            bk_dir = os.path.dirname(self.event_key_file)
            cfg = get_config()

            def on_close(bk_file):
                if bk_file and os.path.exists(bk_file):
                    self.event_key_file = bk_file
                    self.store.event_key_file = bk_file
                    self.active_state_events.clear()
                    self.store.load_events()
                    self.store.load_annotations()
                    self._update_annotations()
                    self._populate_event_trees()

                    if (hasattr(self, "event_buttons_window")
                            and self.event_buttons_window):
                        self.event_buttons_window.deleteLater()
                        self.event_buttons_window = None
                        _create_event_buttons(self)

                    self._update_annotations(scroll_to_bottom=True)
                    (self.coding_start, self.coding_duration,
                     self.coding_end, self.coding_end_reached) = saved
                    self.update_coding_info_display()
                    self.save_session_state()

            editor = EventKeyEditor(
                self.parent, bk_dir,
                on_start_video=on_close, on_cancel=lambda: None,
                config_manager=cfg)
            editor.resize(int(self.display_width * 0.5),
                          int(self.display_height * 0.8))

            def _on_editor_finished(_result):
                self.dialog_open = False
                if not editor.start_video_flag:
                    on_close(self.event_key_file)
                if self.player and was_playing:
                    self.player.pause = False

            editor.finished.connect(_on_editor_finished)
            editor.open()
        except Exception as exc:
            self._show_warning(
                "Error",
                f"Failed to open event key editor: {exc}")

    # Error handling

    def _show_warning(self, title, message):
        """Show a warning dialog above the fullscreen window"""
        logger.warning("Warning dialog: %s — %s", title, message)
        self.dialog_open = True
        dlg = QMessageBox(self.parent)
        theme.apply_dialog_theme(dlg)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setWindowTitle(title)
        dlg.setText(message)
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)

        def _on_finished(_result):
            self.dialog_open = False
            dlg.deleteLater()

        dlg.finished.connect(_on_finished)
        dlg.open()

    def on_write_error(self, message=None):
        logger.error("Write error: %s", message or "file inaccessible")
        if self.player:
            self.player.pause = True

        self.dialog_open = True
        dlg = QMessageBox(self.parent)
        theme.apply_dialog_theme(dlg)
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setWindowTitle("File Access Error")
        dlg.setText(message or
                    "Annotations file is inaccessible.\n"
                    "Is it open in another application?")
        dlg.setStandardButtons(QMessageBox.StandardButton.Ok)

        def _on_finished(_result):
            self.dialog_open = False
            dlg.deleteLater()

        dlg.finished.connect(_on_finished)
        dlg.open()

    # Cleanup

    def _stop_player_safe(self):
        """Stop mpv and free GL resources in the correct order.

        Must be called with self._shutting_down already True.
        Sequence: pause → stop (halts decoder) → disconnect signals
        → drain event queue → free render context → terminate player.
        """
        if not hasattr(self, "player") or not self.player:
            return
        try:
            self.player.pause = True
            self.player.stop()
        except Exception:
            pass
        # Disconnect the frame-ready signal so queued emissions become no-ops
        if hasattr(self, "gl_widget") and self.gl_widget:
            try:
                self.gl_widget._frame_ready.disconnect(
                    self.gl_widget._on_frame_signal)
            except (RuntimeError, TypeError):
                pass
        # Drain any signals that were queued before stop() took effect
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        # NOW safe to free the render context (no concurrent decoder activity)
        if hasattr(self, "gl_widget") and self.gl_widget:
            self.gl_widget.cleanup()
            self.gl_widget.player = None
        try:
            self.player.terminate()
        except Exception:
            pass
        self.player = None

    def on_closing(self):
        logger.info("on_closing() started")
        self._shutting_down = True
        if hasattr(self, 'waveform_widget'):
            self.waveform_widget.cancel_extraction()
        try:
            exit_fullscreen_platform()

            # Remove event filters
            try:
                self.parent.removeEventFilter(self)
            except Exception:
                pass
            try:
                self.app.removeEventFilter(self)
            except Exception:
                pass
            try:
                if hasattr(self, "gl_widget") and self.gl_widget:
                    self.gl_widget.removeEventFilter(self)
            except Exception:
                pass

            for attr in ("floating_controls_window", "event_buttons_window",
                         "event_toggle_window",
                         "zoom_toggle_window", "zoom_slider_window",
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
                self._stop_player_safe()

            self.parent.close()
        except Exception:
            self.parent.close()

    def return_to_file_selection(self):
        if getattr(self, "_returning", False):
            return
        logger.info("return_to_file_selection() started")
        self._returning = True
        self._shutting_down = True
        try:
            exit_fullscreen_platform()

            # Remove event filters before tearing down widgets
            try:
                self.parent.removeEventFilter(self)
            except Exception:
                pass
            try:
                self.app.removeEventFilter(self)
            except Exception:
                pass
            try:
                if hasattr(self, "gl_widget") and self.gl_widget:
                    self.gl_widget.removeEventFilter(self)
            except Exception:
                pass

            if hasattr(self, "player") and self.player:
                try:
                    self.save_session_state()
                except Exception:
                    pass
                self._stop_player_safe()

            for attr in ("floating_controls_window", "event_buttons_window",
                         "event_toggle_window",
                         "zoom_toggle_window", "zoom_slider_window",
                         "edit_dialog"):
                w = getattr(self, attr, None)
                if w is not None:
                    try:
                        w.hide()
                        w.deleteLater()
                    except Exception:
                        pass

            for w in list(self.floating_windows):
                if w is not None:
                    try:
                        w.hide()
                        w.deleteLater()
                    except Exception:
                        pass
            self.floating_windows.clear()

            if self.parent:
                self.parent.hide()
                self.parent.annotator_finished.emit()
            else:
                QApplication.quit()
        except Exception as exc:
            if self.parent:
                self._show_warning(
                    "Error",
                    f"Error returning to file selection: {exc}")
                self.parent.close()
        finally:
            self._returning = False

    # Convenience aliases (used by floating_controls / dialogs modules)

    def format_time_human_readable(self, t):
        return format_time_human(t)

    def format_time_machine_readable(self, t):
        return format_time_machine(t)

    def parse_time(self, s):
        return parse_time(s)
