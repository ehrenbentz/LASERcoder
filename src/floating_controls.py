import math

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QLabel, QSizePolicy,
                             QApplication, QSlider)
from PySide6.QtCore import Qt, QPoint, QSize

import theme
from debug_logger import get_logger

logger = get_logger()


def create_toggle_buttons(annotator):
    parent = annotator.parent

    # Event toggle
    annotator.event_toggle_window = QWidget(parent)
    annotator.event_toggle_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.event_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.event_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.event_toggle_button = QPushButton(
        "", annotator.event_toggle_window)
    annotator.event_toggle_button.setIcon(theme.themed_icon("event_toggle"))
    annotator.event_toggle_button.setIconSize(QSize(20, 20))
    annotator.event_toggle_button.setFixedSize(30, 30)
    annotator.event_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.event_toggle_button.clicked.connect(
        lambda: toggle_event_buttons(annotator))
    annotator.event_toggle_window.setFixedSize(30, 30)

    # Position
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 2
    annotator.event_toggle_window.move(
        video_pos.x() + margin + 5, video_pos.y() + margin - 10)

    # Zoom toggle (upper-right corner)
    annotator.zoom_toggle_window = QWidget(parent)
    annotator.zoom_toggle_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.zoom_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.zoom_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.zoom_toggle_button = QPushButton(
        "", annotator.zoom_toggle_window)
    annotator.zoom_toggle_button.setIcon(theme.themed_icon("zoom"))
    annotator.zoom_toggle_button.setIconSize(QSize(20, 20))
    annotator.zoom_toggle_button.setFixedSize(30, 30)
    annotator.zoom_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.zoom_toggle_button.clicked.connect(
        lambda: toggle_zoom_mode(annotator))
    annotator.zoom_toggle_window.setFixedSize(30, 30)

    annotator.zoom_toggle_window.move(
        video_pos.x() + annotator.video_width - 30 - margin - 5,
        video_pos.y() + margin - 10)

    # Zoom level slider (hidden until zoom is activated)
    annotator.zoom_slider_window = QWidget(parent)
    annotator.zoom_slider_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.zoom_slider_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.zoom_slider_window.setStyleSheet(
        "background-color: rgba(40, 40, 40, 200); border-radius: 5px;")

    zoom_slider_layout = QHBoxLayout(annotator.zoom_slider_window)
    zoom_slider_layout.setContentsMargins(8, 4, 8, 4)
    zoom_slider_layout.setSpacing(6)

    zoom_slider_style = (
        "QSlider::groove:horizontal { background: #888; height: 6px;"
        "  border-radius: 3px; }"
        "QSlider::handle:horizontal { background: #ccc; width: 14px;"
        "  margin: -4px 0; border-radius: 7px; }"
        "QSlider::sub-page:horizontal { background: #aaa; border-radius: 3px; }"
    )

    annotator._zoom_slider = QSlider(Qt.Orientation.Horizontal)
    annotator._zoom_slider.setRange(0, 5)
    annotator._zoom_slider.setValue(2)  # Default 2x
    annotator._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    annotator._zoom_slider.setTickInterval(1)
    annotator._zoom_slider.setFixedWidth(100)
    annotator._zoom_slider.setStyleSheet(zoom_slider_style)
    annotator._zoom_slider.valueChanged.connect(
        lambda val: _on_zoom_level_changed(annotator, val))
    zoom_slider_layout.addWidget(annotator._zoom_slider)

    annotator._zoom_level_label = QLabel("2.0x")
    annotator._zoom_level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    annotator._zoom_level_label.setStyleSheet(
        "color: white; font-size: 11px; background: transparent;")
    zoom_slider_layout.addWidget(annotator._zoom_level_label)

    annotator.zoom_slider_window.setFixedSize(140, 30)
    annotator.zoom_slider_window.hide()

    annotator.event_toggle_window.show()
    annotator.zoom_toggle_window.show()

    annotator.floating_windows.extend([
        annotator.event_toggle_window,
        annotator.zoom_toggle_window,
        annotator.zoom_slider_window,
    ])




_ZOOM_LEVELS = {0: 1.25, 1: 1.5, 2: 2.0, 3: 2.5, 4: 3.0, 5: 4.0}

def _zoom_level_to_mpv(level):
    """Convert a linear zoom multiplier to MPV's log2 video_zoom value."""
    return math.log2(level)

def _on_zoom_level_changed(annotator, slider_val):
    """Handle zoom slider changes."""
    level = _ZOOM_LEVELS[slider_val]
    annotator._zoom_multiplier = level
    annotator._zoom_level_label.setText(f"{level:.1f}x")
    if (annotator.zoom_active
            and hasattr(annotator, "player") and annotator.player
            and (annotator.player.video_zoom or 0) > 0):
        annotator.player.video_zoom = _zoom_level_to_mpv(level)

def toggle_zoom_mode(annotator):
    """Toggle video zoom mode on/off"""
    annotator.zoom_active = not annotator.zoom_active

    if annotator.zoom_active:
        annotator.zoom_toggle_button.setStyleSheet(theme.zoom_active_stylesheet())
        if not hasattr(annotator, '_zoom_multiplier'):
            annotator._zoom_multiplier = 2.0
        if hasattr(annotator, 'zoom_slider_window'):
            annotator.zoom_slider_window.show()
            annotator._reposition_floating_windows()
    else:
        annotator.zoom_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
        annotator._zoom_pan_x = 0.0
        annotator._zoom_pan_y = 0.0
        if hasattr(annotator, "player") and annotator.player:
            annotator.player.video_zoom = 0
            annotator.player.video_pan_x = 0
            annotator.player.video_pan_y = 0
        if hasattr(annotator, 'zoom_slider_window'):
            annotator.zoom_slider_window.hide()


def toggle_floating_controls(annotator):
    """Toggle the playback controls floating panel"""
    logger.debug("toggle_floating_controls")
    if (hasattr(annotator, "floating_controls_window")
            and annotator.floating_controls_window):
        try:
            annotator.floating_windows.remove(annotator.floating_controls_window)
        except ValueError:
            pass
        annotator.floating_controls_window.deleteLater()
        annotator.floating_controls_window = None
        annotator.play_pause_btn = None
    else:
        _create_floating_controls(annotator)


def _create_floating_controls(annotator):
    parent = annotator.parent

    annotator.floating_controls_window = QWidget(parent)
    annotator.floating_controls_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.floating_controls_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.floating_controls_window.setStyleSheet("background-color: transparent;")

    layout = QHBoxLayout(annotator.floating_controls_window)
    layout.setSpacing(30)
    layout.setContentsMargins(10, 0, 10, 0)

    buttons = [
        ("back_big", lambda: annotator.seek_relative(-10000)),
        ("back",     lambda: annotator.seek_relative(-1000)),
        ("minus",    lambda: annotator.change_speed(-1)),
        ("play",     annotator.toggle_play_pause),
        ("plus",     lambda: annotator.change_speed(1)),
        ("forward",  lambda: annotator.seek_relative(1000)),
        ("forward_big", lambda: annotator.seek_relative(10000)),
    ]

    for icon_name, callback in buttons:
        btn = QPushButton("")
        btn.setIcon(theme.themed_icon(icon_name))
        btn.setIconSize(QSize(20, 20))
        btn.setFixedSize(32, 32)
        btn.setStyleSheet(theme.control_btn_stylesheet())
        btn.clicked.connect(callback)
        if icon_name == "play":
            annotator.play_pause_btn = btn
        layout.addWidget(btn)

    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    annotator.floating_controls_window.adjustSize()
    annotator.floating_controls_window.setFixedSize(
        annotator.floating_controls_window.size())
    win_w = annotator.floating_controls_window.width()
    x = video_pos.x() + (annotator.video_width - win_w) // 2
    y = (video_pos.y() + annotator.video_height
         - annotator.floating_controls_window.height() - 50)
    annotator.floating_controls_window.move(x, y)
    annotator.floating_controls_window.show()
    annotator.floating_windows.append(annotator.floating_controls_window)


def toggle_event_buttons(annotator):
    """Toggle the floating event-buttons panel"""
    logger.debug("toggle_event_buttons")
    if (hasattr(annotator, "event_buttons_window")
            and annotator.event_buttons_window):
        try:
            annotator.floating_windows.remove(annotator.event_buttons_window)
        except ValueError:
            pass
        annotator.event_buttons_window.deleteLater()
        annotator.event_buttons_window = None
    else:
        _create_event_buttons(annotator)


def _custom_btn_stylesheet(hex_color, opacity=0.4):
    """Generate a semi-transparent button stylesheet from a hex color"""
    from PySide6.QtGui import QColor
    c = QColor(hex_color)
    r, g, b = c.red(), c.green(), c.blue()
    a = int(opacity * 255)
    a_hover = min(255, a + 60)
    a_pressed = min(255, a + 100)
    return (
        f"QPushButton {{ background-color: rgba({r},{g},{b},{a}); color: white;"
        f"  border: 1px solid grey; border-radius: 3px; padding: 5px;"
        f"  text-align: center; }}"
        f"QPushButton:hover {{ background-color: rgba({r},{g},{b},{a_hover}); color: white; }}"
        f"QPushButton:pressed {{ background-color: rgba({r},{g},{b},{a_pressed}); color: white; }}"
    )


def _create_event_buttons(annotator):
    parent = annotator.parent
    store = annotator.store

    annotator.event_buttons_window = QWidget(parent)
    annotator.event_buttons_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.event_buttons_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.event_buttons_window.setStyleSheet("background-color: transparent;")
    
    main_layout = QVBoxLayout(annotator.event_buttons_window)
    main_layout.setSpacing(10)
    main_layout.setContentsMargins(10, 10, 10, 10)

    # Separate events by type
    point_events = []
    state_events = []
    for name, key, btype, _ in store.events:
        if not name:
            continue
        (point_events if btype == "point" else state_events).append(
            (name, key))

    max_per_row = 4

    def _add_section(label_text, items, style):
        lbl = QLabel(label_text)
        lbl.setStyleSheet(theme.event_label_stylesheet())
        main_layout.addWidget(lbl)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(2)
        container_layout.setContentsMargins(0, 0, 0, 0)

        row_layout = None
        count = 0
        for name, key in items:
            if count == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(5)
                row_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.addLayout(row_layout)

            btn = QPushButton(name)
            btn.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(style)
            btn.clicked.connect(
                lambda checked, k=key: annotator.add_annotation_for_event(k))
            row_layout.addWidget(btn)

            count += 1
            if count >= max_per_row:
                row_layout.addStretch()
                count = 0

        if 0 < count < max_per_row and row_layout is not None:
            row_layout.addStretch()

        main_layout.addWidget(container)

    from config_manager import get_config
    cfg = get_config()

    point_hex = cfg.get_point_button_color()
    state_hex = cfg.get_state_button_color()
    btn_opacity = cfg.get_event_button_opacity()
    point_style = _custom_btn_stylesheet(point_hex, btn_opacity) if point_hex else theme.point_btn_stylesheet()
    state_style = _custom_btn_stylesheet(state_hex, btn_opacity) if state_hex else theme.state_btn_stylesheet()

    _add_section("State Events", state_events, state_style)
    _add_section("Point Events", point_events, point_style)

    # Position — align top with toggle button
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    toggle_margin = 2
    toggle_width = annotator.event_toggle_button.width()
    x = video_pos.x() + toggle_margin + toggle_width + 10
    y = video_pos.y() + toggle_margin - 20

    annotator.event_buttons_window.adjustSize()
    annotator.event_buttons_window.setFixedSize(
        annotator.event_buttons_window.size())
    annotator.event_buttons_window.show()
    annotator.event_buttons_window.move(x, y)
    annotator.floating_windows.append(annotator.event_buttons_window)


def _hidden_by_settings(annotator):
    """Return the set of floating windows the user has hidden via settings"""
    from config_manager import get_config
    cfg = get_config()
    hidden = set()
    if not cfg.get_show_floating_controls():
        w = getattr(annotator, "floating_controls_window", None)
        if w:
            hidden.add(w)
    if not cfg.get_show_events_toggle():
        for attr in ("event_toggle_window", "event_buttons_window"):
            w = getattr(annotator, attr, None)
            if w:
                hidden.add(w)
    if not cfg.get_show_zoom_button():
        w = getattr(annotator, "zoom_toggle_window", None)
        if w:
            hidden.add(w)
    if not cfg.get_show_zoom_button() or not annotator.zoom_active:
        w2 = getattr(annotator, "zoom_slider_window", None)
        if w2:
            hidden.add(w2)
    return hidden


def update_floating_visibility(annotator):
    """Hide/show floating windows when the main window is minimised or deactivated"""

    is_minimized = bool(
        annotator.parent.windowState() & Qt.WindowState.WindowMinimized)

    if is_minimized:
        should_hide = True
    elif annotator.parent.isActiveWindow():
        should_hide = False
    else:
        # Check if a floating window has focus (e.g. user clicked an event
        # button).  In that case we should NOT hide.
        active = QApplication.instance().activeWindow()
        should_hide = active not in annotator.floating_windows

    hidden = _hidden_by_settings(annotator)

    for w in annotator.floating_windows:
        if w is None:
            continue
        try:
            want_visible = not (should_hide or w in hidden)
            if w.isVisible() != want_visible:
                w.setVisible(want_visible)
        except RuntimeError:
            pass
