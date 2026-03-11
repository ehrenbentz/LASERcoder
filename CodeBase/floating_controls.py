from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QLabel, QSizePolicy,
                             QApplication)
from PySide6.QtCore import Qt, QPoint

import theme


def create_toggle_buttons(annotator):
    """Create the two small floating toggle buttons (behaviour grid + controls).

    Attaches the windows to *annotator.floating_windows* and stores
    references as *annotator.event_toggle_window*, etc.
    """
    parent = annotator.parent

    # Behaviour toggle
    annotator.event_toggle_window = QWidget(parent)
    annotator.event_toggle_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.event_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.event_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.event_toggle_button = QPushButton(
        "\u2637", annotator.event_toggle_window)
    annotator.event_toggle_button.setFixedSize(30, 30)
    annotator.event_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.event_toggle_button.clicked.connect(
        lambda: toggle_event_buttons(annotator))

    # Controls toggle
    annotator.controls_window = QWidget(parent)
    annotator.controls_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.controls_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.controls_window.setStyleSheet("background-color: transparent;")

    annotator.controls_button = QPushButton(
        "\u23E3", annotator.controls_window)
    annotator.controls_button.setFixedSize(30, 30)
    annotator.controls_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.controls_button.clicked.connect(
        lambda: toggle_floating_controls(annotator))

    # Position
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 5
    annotator.event_toggle_window.move(
        video_pos.x() + margin, video_pos.y() + 20)
    annotator.controls_window.move(
        video_pos.x() + margin,
        video_pos.y() + annotator.video_height - 20)

    # Zoom toggle (upper-right corner)
    annotator.zoom_toggle_window = QWidget(parent)
    annotator.zoom_toggle_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.zoom_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.zoom_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.zoom_toggle_button = QPushButton(
        "\u2315", annotator.zoom_toggle_window)
    annotator.zoom_toggle_button.setFixedSize(30, 30)
    annotator.zoom_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
    annotator.zoom_toggle_button.clicked.connect(
        lambda: toggle_zoom_mode(annotator))

    annotator.zoom_toggle_window.move(
        video_pos.x() + annotator.video_width - 40 - margin,
        video_pos.y() + 20)

    annotator.event_toggle_window.show()
    annotator.controls_window.show()
    annotator.zoom_toggle_window.show()

    annotator.floating_windows.extend([
        annotator.event_toggle_window,
        annotator.controls_window,
        annotator.zoom_toggle_window,
    ])




def toggle_zoom_mode(annotator):
    """Toggle video zoom mode on/off."""
    annotator.zoom_active = not annotator.zoom_active

    if annotator.zoom_active:
        annotator.zoom_toggle_button.setStyleSheet(theme.zoom_active_stylesheet())
    else:
        annotator.zoom_toggle_button.setStyleSheet(theme.toggle_btn_stylesheet())
        annotator._zoom_pan_x = 0.0
        annotator._zoom_pan_y = 0.0
        # Reset zoom
        if hasattr(annotator, "player") and annotator.player:
            annotator.player.video_zoom = 0
            annotator.player.video_pan_x = 0
            annotator.player.video_pan_y = 0


def toggle_floating_controls(annotator):
    """Toggle the playback-controls floating panel."""
    if (hasattr(annotator, "floating_controls_window")
            and annotator.floating_controls_window):
        annotator.floating_controls_window.deleteLater()
        annotator.floating_controls_window = None
        annotator.play_pause_btn = None
    else:
        _create_floating_controls(annotator)


def _create_floating_controls(annotator):
    parent = annotator.parent

    annotator.floating_controls_window = QWidget(parent)
    annotator.floating_controls_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.floating_controls_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.floating_controls_window.setStyleSheet("background-color: transparent;")

    layout = QHBoxLayout(annotator.floating_controls_window)
    layout.setSpacing(40)
    layout.setContentsMargins(10, 0, 10, 0)

    buttons = [
        ("\u27F8", lambda: annotator.seek_relative(-10000)),
        ("\u27F5", lambda: annotator.seek_relative(-1000)),
        ("<<",     lambda: annotator.change_speed(-1)),
        ("\u23F8", annotator.toggle_play_pause),
        (">>",     lambda: annotator.change_speed(1)),
        ("\u27F6", lambda: annotator.seek_relative(1000)),
        ("\u27F9", lambda: annotator.seek_relative(10000)),
    ]

    for text, callback in buttons:
        btn = QPushButton(text)
        btn.setFixedSize(40, 40)
        btn.setStyleSheet(theme.control_btn_stylesheet())
        btn.clicked.connect(callback)
        if text == "\u23F8":
            annotator.play_pause_btn = btn
        layout.addWidget(btn)

    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    annotator.floating_controls_window.adjustSize()
    win_w = annotator.floating_controls_window.width()
    x = video_pos.x() + (annotator.video_width - win_w) // 2
    y = (video_pos.y() + annotator.video_height
         - annotator.floating_controls_window.height() - 10)
    annotator.floating_controls_window.move(x, y)
    annotator.floating_controls_window.show()
    annotator.floating_windows.append(annotator.floating_controls_window)


def toggle_event_buttons(annotator):
    """Toggle the floating behaviour-buttons panel."""
    if (hasattr(annotator, "event_buttons_window")
            and annotator.event_buttons_window):
        annotator.event_buttons_window.deleteLater()
        annotator.event_buttons_window = None
    else:
        _create_event_buttons(annotator)


def _create_event_buttons(annotator):
    parent = annotator.parent
    store = annotator.store

    annotator.event_buttons_window = QWidget(parent)
    annotator.event_buttons_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.event_buttons_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.event_buttons_window.setStyleSheet("background-color: transparent;")
    
    main_layout = QVBoxLayout(annotator.event_buttons_window)
    main_layout.setSpacing(10)
    main_layout.setContentsMargins(10, 10, 10, 10)

    # Separate behaviours by type
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

    _add_section("Point Events", point_events, theme.point_btn_stylesheet())
    _add_section("State Events", state_events, theme.state_btn_stylesheet())

    # Position
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 10
    toggle_width = annotator.event_toggle_button.width()
    x = video_pos.x() + margin + toggle_width + 10
    y = video_pos.y() + margin

    annotator.event_buttons_window.adjustSize()
    annotator.event_buttons_window.show()
    annotator.event_buttons_window.move(x, y)
    annotator.floating_windows.append(annotator.event_buttons_window)


def _hidden_by_settings(annotator):
    """Return the set of floating windows the user has hidden via settings."""
    from config_manager import get_config
    cfg = get_config()
    hidden = set()
    if not cfg.get_show_video_controls_toggle():
        for attr in ("controls_window", "floating_controls_window"):
            w = getattr(annotator, attr, None)
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
    return hidden


def update_floating_visibility(annotator):
    """Hide/show floating windows when the main window is minimised or deactivated."""

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
            w.winId()
            want_visible = not (should_hide or w in hidden)
            if w.isVisible() != want_visible:
                w.setVisible(want_visible)
        except RuntimeError:
            pass
