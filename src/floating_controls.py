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
    annotator._zoom_slider.setRange(0, 6)
    annotator._zoom_slider.setValue(3)  # Default 2x
    annotator._zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    annotator._zoom_slider.setTickInterval(1)
    annotator._zoom_slider.setFixedWidth(100)
    annotator._zoom_slider.setStyleSheet(zoom_slider_style)
    annotator._zoom_slider.valueChanged.connect(
        lambda val: _on_zoom_level_changed(annotator, val))
    zoom_slider_layout.addWidget(annotator._zoom_slider)

    annotator._zoom_level_label = QLabel(f"{_ZOOM_LEVELS[3]:.1f}x")
    annotator._zoom_level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    annotator._zoom_level_label.setStyleSheet(
        "color: white; font-size: 11px; background: transparent;")
    zoom_slider_layout.addWidget(annotator._zoom_level_label)

    annotator.zoom_slider_window.setFixedSize(140, 30)
    annotator.zoom_slider_window.hide()

    # Subject toggle (just below event toggle)
    annotator.subject_toggle_window = QWidget(parent)
    annotator.subject_toggle_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.subject_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.subject_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.subject_toggle_button = QPushButton(
        "", annotator.subject_toggle_window)
    annotator.subject_toggle_button.setIcon(theme.themed_icon("subject_list"))
    annotator.subject_toggle_button.setIconSize(QSize(20, 20))
    annotator.subject_toggle_button.setFixedSize(30, 30)
    annotator.subject_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.subject_toggle_button.clicked.connect(
        lambda: toggle_subject_buttons(annotator))
    annotator.subject_toggle_window.setFixedSize(30, 30)

    annotator.subject_toggle_window.move(
        video_pos.x() + margin + 5, video_pos.y() + margin - 10 + 32)

    from config_manager import get_config
    cfg = get_config()
    toggle_opacity = cfg.get_floating_toggle_opacity()
    annotator.event_toggle_window.setWindowOpacity(toggle_opacity)
    annotator.subject_toggle_window.setWindowOpacity(toggle_opacity)
    annotator.zoom_toggle_window.setWindowOpacity(toggle_opacity)
    annotator.zoom_slider_window.setWindowOpacity(toggle_opacity)

    if not annotator.event_toggle_window.isVisible():
        annotator.event_toggle_window.show()
    if not annotator.zoom_toggle_window.isVisible():
        annotator.zoom_toggle_window.show()
    if not annotator.subject_toggle_window.isVisible():
        annotator.subject_toggle_window.show()

    annotator.floating_windows.extend([
        annotator.event_toggle_window,
        annotator.zoom_toggle_window,
        annotator.zoom_slider_window,
        annotator.subject_toggle_window,
    ])




_ZOOM_LEVELS = {0: 1.0, 1: 1.25, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.0, 6: 5.0}

def _zoom_level_to_mpv(level):
    """Convert a linear zoom multiplier to MPV's log2 video_zoom value."""
    return math.log2(level)

def _on_zoom_level_changed(annotator, slider_val):
    """Handle zoom slider changes."""
    level = _ZOOM_LEVELS[slider_val]
    annotator._zoom_multiplier = level
    annotator._zoom_level_label.setText(f"{level:.1f}x")
    if (annotator.zoom_active
            and hasattr(annotator, "player") and annotator.player):
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
    from config_manager import get_config
    cfg = get_config()
    if (hasattr(annotator, "floating_controls_window")
            and annotator.floating_controls_window):
        try:
            annotator.floating_windows.remove(annotator.floating_controls_window)
        except ValueError:
            pass
        annotator.floating_controls_window.deleteLater()
        annotator.floating_controls_window = None
        annotator.play_pause_btn = None
        cfg.set_show_floating_controls(False)
    else:
        _create_floating_controls(annotator)
        cfg.set_show_floating_controls(True)


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
    from config_manager import get_config as _get_config
    _cfg = _get_config()
    annotator.floating_controls_window.setWindowOpacity(
        max(0.1, _cfg.get_floating_controls_opacity()))
    annotator.floating_controls_window.show()
    annotator.floating_windows.append(annotator.floating_controls_window)
    # Canonical positioner runs the up-to-date Y math (the local move()
    # above uses the stale -50 offset). Without this the controls land
    # in the wrong spot until any other floating-button toggle fires
    # _reposition_floating_windows.
    annotator._reposition_floating_windows()


def toggle_event_buttons(annotator):
    """Toggle the floating event-buttons panel"""
    logger.debug("toggle_event_buttons")
    from config_manager import get_config
    cfg = get_config()
    if (hasattr(annotator, "event_buttons_window")
            and annotator.event_buttons_window):
        try:
            annotator.floating_windows.remove(annotator.event_buttons_window)
        except ValueError:
            pass
        annotator.event_buttons_window.deleteLater()
        annotator.event_buttons_window = None
        cfg.set_events_list_expanded(False)
    else:
        _create_event_buttons(annotator)
        cfg.set_events_list_expanded(True)
    _reposition_subject_buttons(annotator)


def _reposition_subject_buttons(annotator):
    """Reposition subject buttons relative to event buttons if both are visible."""
    sbw = getattr(annotator, "subject_buttons_window", None)
    if sbw is None or not sbw.isVisible():
        return
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 2
    event_win = getattr(annotator, "event_buttons_window", None)
    if event_win is not None and event_win.isVisible():
        x = event_win.x()
        y = event_win.y() + event_win.height() + 5
    else:
        toggle_win = getattr(annotator, "subject_toggle_window", None)
        if toggle_win is not None:
            x = toggle_win.x() + toggle_win.width() + 10
            y = toggle_win.y()
        else:
            x = video_pos.x() + margin + 5 + 40
            y = video_pos.y() + margin - 10 + 32
    sbw.move(x, y)


def _custom_btn_stylesheet(hex_color, opacity=0.4, size_mult=1.0):
    """Generate a semi-transparent button stylesheet from a hex color.

    size_mult: 0.5..2.0 multiplier applied to padding and font size so
    the floating event/subject buttons can be scaled from the
    Appearance settings dialog.
    """
    from PySide6.QtGui import QColor
    c = QColor(hex_color)
    r, g, b = c.red(), c.green(), c.blue()
    bg_alpha = int(opacity * 255)
    text_alpha = int(max(0.1, opacity) * 255)
    pad_v = max(2, int(round(5 * size_mult)))
    pad_h = max(4, int(round(8 * size_mult)))
    font_px = max(9, int(round(13 * size_mult)))
    return (
        f"QPushButton {{ background-color: rgba({r},{g},{b},{bg_alpha});"
        f"  color: rgba(255,255,255,{text_alpha});"
        f"  border: 1px solid rgba(255,255,255,{text_alpha});"
        f"  border-radius: 3px;"
        f"  padding: {pad_v}px {pad_h}px;"
        f"  font-size: {font_px}px;"
        f"  text-align: center; }}"
        f"QPushButton:hover {{ background-color: rgba({r},{g},{b},{min(255, bg_alpha + 40)}); }}"
        f"QPushButton:pressed {{ background-color: rgba({r},{g},{b},255); }}"
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
    main_layout.setSpacing(8)
    # Shared 5px margins so the events panel and subject panel align
    # on the left when both are visible.
    main_layout.setContentsMargins(5, 5, 5, 5)

    # Separate events by type
    point_events = []
    state_events = []
    for name, key, btype, _ in store.events:
        if not name:
            continue
        (point_events if btype == "point" else state_events).append(
            (name, key))

    max_per_row = 4

    from config_manager import get_config
    cfg = get_config()
    header_style = theme.event_label_stylesheet(
        cfg.get_floating_header_color(),
        cfg.get_floating_header_opacity())

    def _add_section(label_text, items, style):
        lbl = QLabel(label_text)
        lbl.setStyleSheet(header_style)
        if not cfg.get_show_floating_headers():
            lbl.hide()
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

    point_hex = cfg.get_point_button_color() or theme.color('float_point_bg')
    state_hex = cfg.get_state_button_color() or theme.color('float_state_bg')
    btn_opacity = cfg.get_floating_buttons_opacity()
    size_mult = cfg.get_floating_button_size()
    point_style = _custom_btn_stylesheet(point_hex, btn_opacity, size_mult)
    state_style = _custom_btn_stylesheet(state_hex, btn_opacity, size_mult)

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
    # Use the canonical positioner so the buttons land at the correct
    # Y baseline and any dependent windows (subject buttons) re-align.
    annotator._reposition_floating_windows()


def toggle_subject_buttons(annotator):
    """Toggle the floating subject-buttons panel"""
    logger.debug("toggle_subject_buttons")
    from config_manager import get_config
    cfg = get_config()
    if (hasattr(annotator, "subject_buttons_window")
            and annotator.subject_buttons_window):
        try:
            annotator.floating_windows.remove(annotator.subject_buttons_window)
        except ValueError:
            pass
        annotator.subject_buttons_window.deleteLater()
        annotator.subject_buttons_window = None
        annotator._subject_btn_map = {}
        cfg.set_subject_list_expanded(False)
    else:
        _create_subject_buttons(annotator)
        cfg.set_subject_list_expanded(True)


def _create_subject_buttons(annotator):
    parent = annotator.parent

    annotator.subject_buttons_window = QWidget(parent)
    annotator.subject_buttons_window.setWindowFlags(
        Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool)
    annotator.subject_buttons_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.subject_buttons_window.setStyleSheet("background-color: transparent;")

    layout = QVBoxLayout(annotator.subject_buttons_window)
    layout.setSpacing(3)
    # Shared 5px margins to match the events panel for left-edge alignment.
    layout.setContentsMargins(5, 5, 5, 5)

    from config_manager import get_config
    cfg = get_config()

    lbl = QLabel("Subjects")
    lbl.setStyleSheet(theme.event_label_stylesheet(
        cfg.get_floating_header_color(),
        cfg.get_floating_header_opacity()))
    if not cfg.get_show_floating_headers():
        lbl.hide()
    layout.addWidget(lbl)
    subject_hex = cfg.get_subject_button_color()
    btn_opacity = cfg.get_floating_buttons_opacity()
    size_mult = cfg.get_floating_button_size()
    default_hex = "#008080"
    from PySide6.QtGui import QColor

    annotator._subject_btn_map = {}

    pad_v = max(2, int(round(5 * size_mult)))
    pad_h = max(4, int(round(8 * size_mult)))
    font_px = max(9, int(round(13 * size_mult)))

    for name in annotator.subject_names:
        per_color = getattr(annotator, 'subject_colors', {}).get(name, "")
        hex_color = per_color or subject_hex or default_hex
        normal_style = _custom_btn_stylesheet(hex_color, btn_opacity, size_mult)

        c = QColor(hex_color)
        r, g, b = c.red(), c.green(), c.blue()
        active_style = (
            f"QPushButton {{ background-color: rgba({r},{g},{b},{int(0.8*255)}); color: white;"
            f"  border: 2px solid white; border-radius: 3px;"
            f"  padding: {pad_v}px {pad_h}px;"
            f"  font-size: {font_px}px;"
            f"  text-align: center; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: rgba({r},{g},{b},{int(0.9*255)}); }}"
            f"QPushButton:pressed {{ background-color: rgba({r},{g},{b},255); }}"
        )

        btn = QPushButton(name)
        btn.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if name in annotator.active_subjects:
            btn.setStyleSheet(active_style)
        else:
            btn.setStyleSheet(normal_style)
        btn.clicked.connect(
            lambda checked, n=name: _on_subject_button_clicked(annotator, n))
        layout.addWidget(btn)
        annotator._subject_btn_map[name] = btn

    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 2

    annotator.subject_buttons_window.adjustSize()
    annotator.subject_buttons_window.setFixedSize(
        annotator.subject_buttons_window.size())

    # Align with event buttons row — same x, below the event buttons panel
    event_win = getattr(annotator, "event_buttons_window", None)
    if event_win is not None and event_win.isVisible():
        x = event_win.x()
        y = event_win.y() + event_win.height() + 5
    else:
        # Fall back: position to the right of the subject toggle
        toggle_win = getattr(annotator, "subject_toggle_window", None)
        if toggle_win is not None:
            x = toggle_win.x() + toggle_win.width() + 10
            y = toggle_win.y()
        else:
            x = video_pos.x() + margin + 5 + 40
            y = video_pos.y() + margin - 10 + 32

    annotator.subject_buttons_window.move(x, y)
    annotator.subject_buttons_window.show()
    annotator.floating_windows.append(annotator.subject_buttons_window)
    # Canonical positioner runs the up-to-date Y baseline math and
    # handles the event-buttons-visible / not-visible branches uniformly.
    annotator._reposition_floating_windows()


def _on_subject_button_clicked(annotator, subject_name):
    """Toggle a subject on/off when its floating button is clicked"""
    if subject_name in annotator.active_subjects:
        annotator.active_subjects.discard(subject_name)
    else:
        annotator._deactivate_me_subjects(subject_name)
        annotator.active_subjects.add(subject_name)

    annotator._update_subject_overlay()
    annotator.store.save_active_subjects(list(annotator.active_subjects))
    _refresh_subject_button_styles(annotator)


def _refresh_subject_button_styles(annotator):
    """Update subject button styles to reflect active state.

    Must use the same size_mult-aware padding/font as _create_subject_buttons,
    otherwise clicking a subject reverts that button to default size while
    leaving the (correctly-sized) header large — making the buttons look
    like they shrank."""
    if not hasattr(annotator, '_subject_btn_map'):
        return

    from config_manager import get_config
    cfg = get_config()
    subject_hex = cfg.get_subject_button_color()
    btn_opacity = cfg.get_floating_buttons_opacity()
    size_mult = cfg.get_floating_button_size()
    default_hex = "#008080"
    from PySide6.QtGui import QColor

    pad_v = max(2, int(round(5 * size_mult)))
    pad_h = max(4, int(round(8 * size_mult)))
    font_px = max(9, int(round(13 * size_mult)))

    for name, btn in annotator._subject_btn_map.items():
        try:
            per_color = getattr(annotator, 'subject_colors', {}).get(name, "")
            hex_color = per_color or subject_hex or default_hex
            normal_style = _custom_btn_stylesheet(
                hex_color, btn_opacity, size_mult)

            c = QColor(hex_color)
            r, g, b = c.red(), c.green(), c.blue()
            active_style = (
                f"QPushButton {{ background-color: rgba({r},{g},{b},{int(0.8*255)}); color: white;"
                f"  border: 2px solid white; border-radius: 3px;"
                f"  padding: {pad_v}px {pad_h}px;"
                f"  font-size: {font_px}px;"
                f"  text-align: center; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: rgba({r},{g},{b},{int(0.9*255)}); }}"
                f"QPushButton:pressed {{ background-color: rgba({r},{g},{b},255); }}"
            )

            if name in annotator.active_subjects:
                btn.setStyleSheet(active_style)
            else:
                btn.setStyleSheet(normal_style)
        except RuntimeError:
            pass


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
    if not cfg.get_show_subject_list():
        w = getattr(annotator, "subject_buttons_window", None)
        if w:
            hidden.add(w)
        w2 = getattr(annotator, "subject_toggle_window", None)
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
