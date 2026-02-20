from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QLabel, QSizePolicy)
from PySide6.QtCore import Qt, QPoint


# Style sheets shared across floating windows
_TOGGLE_BTN_STYLE = """
    QPushButton {
        background-color: #808080;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #1084D9; }
    QPushButton:pressed { background-color: #006CC1; }
"""

_CONTROL_BTN_STYLE = """
    QPushButton {
        background-color: darkgrey;
        color: black;
        border: 1px solid grey;
        border-radius: 3px;
        padding: 0px;
        text-align: center;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: darkgrey; color: white; }
    QPushButton:pressed { background-color: #404040; color: white; }
"""

_POINT_BTN_STYLE = """
    QPushButton {
        background-color: #5B6770;
        color: white;
        border: 1px solid grey;
        border-radius: 3px;
        padding: 5px;
        text-align: center;
    }
    QPushButton:hover { background-color: darkgrey; color: white; }
    QPushButton:pressed { background-color: #404040; color: white; }
"""

_STATE_BTN_STYLE = """
    QPushButton {
        background-color: #7B6469;
        color: white;
        border: 1px solid grey;
        border-radius: 3px;
        padding: 5px;
        text-align: center;
    }
    QPushButton:hover { background-color: darkgrey; color: white; }
    QPushButton:pressed { background-color: #404040; color: white; }
"""


def create_toggle_buttons(annotator):
    """Create the two small floating toggle buttons (behaviour grid + controls).

    Attaches the windows to *annotator.floating_windows* and stores
    references as *annotator.behavior_toggle_window*, etc.
    """
    parent = annotator.parent

    # Behaviour toggle
    annotator.behavior_toggle_window = QWidget(parent)
    annotator.behavior_toggle_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.behavior_toggle_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.behavior_toggle_window.setStyleSheet("background-color: transparent;")

    annotator.behavior_toggle_button = QPushButton(
        "\u2637", annotator.behavior_toggle_window)
    annotator.behavior_toggle_button.setFixedSize(30, 30)
    annotator.behavior_toggle_button.setStyleSheet(_TOGGLE_BTN_STYLE)
    annotator.behavior_toggle_button.clicked.connect(
        lambda: toggle_behavior_buttons(annotator))

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
    annotator.controls_button.setStyleSheet(_TOGGLE_BTN_STYLE)
    annotator.controls_button.clicked.connect(
        lambda: toggle_floating_controls(annotator))

    # Position
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 5
    annotator.behavior_toggle_window.move(
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
    annotator.zoom_toggle_button.setStyleSheet(_TOGGLE_BTN_STYLE)
    annotator.zoom_toggle_button.clicked.connect(
        lambda: toggle_zoom_mode(annotator))

    annotator.zoom_toggle_window.move(
        video_pos.x() + annotator.video_width - 40 - margin,
        video_pos.y() + 20)

    annotator.behavior_toggle_window.show()
    annotator.controls_window.show()
    annotator.zoom_toggle_window.show()

    annotator.floating_windows.extend([
        annotator.behavior_toggle_window,
        annotator.controls_window,
        annotator.zoom_toggle_window,
    ])


_ZOOM_ACTIVE_STYLE = """
    QPushButton {
        background-color: #1084D9;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px;
        font-size: 12px;
    }
    QPushButton:hover { background-color: #3399E6; }
    QPushButton:pressed { background-color: #006CC1; }
"""


def toggle_zoom_mode(annotator):
    """Toggle video zoom mode on/off."""
    annotator.zoom_active = not annotator.zoom_active

    if annotator.zoom_active:
        annotator.zoom_toggle_button.setStyleSheet(_ZOOM_ACTIVE_STYLE)
    else:
        annotator.zoom_toggle_button.setStyleSheet(_TOGGLE_BTN_STYLE)
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
        btn.setStyleSheet(_CONTROL_BTN_STYLE)
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


def toggle_behavior_buttons(annotator):
    """Toggle the floating behaviour-buttons panel."""
    if (hasattr(annotator, "behavior_buttons_window")
            and annotator.behavior_buttons_window):
        annotator.behavior_buttons_window.deleteLater()
        annotator.behavior_buttons_window = None
    else:
        _create_behavior_buttons(annotator)


def _create_behavior_buttons(annotator):
    parent = annotator.parent
    store = annotator.store

    annotator.behavior_buttons_window = QWidget(parent)
    annotator.behavior_buttons_window.setWindowFlags(
        Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint)
    annotator.behavior_buttons_window.setAttribute(
        Qt.WidgetAttribute.WA_TranslucentBackground)
    annotator.behavior_buttons_window.setStyleSheet("background-color: transparent;")
    
    main_layout = QVBoxLayout(annotator.behavior_buttons_window)
    main_layout.setSpacing(10)
    main_layout.setContentsMargins(10, 10, 10, 10)

    # Separate behaviours by type
    point_behaviors = []
    state_behaviors = []
    for name, key, btype, _ in store.behaviors:
        if not name:
            continue
        (point_behaviors if btype == "point" else state_behaviors).append(
            (name, key))

    max_per_row = 4

    def _add_section(label_text, items, style):
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            "color: white; background-color: rgba(50,50,50,180); padding: 2px;")
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
                lambda checked, k=key: annotator.add_annotation_for_behavior(k))
            row_layout.addWidget(btn)

            count += 1
            if count >= max_per_row:
                row_layout.addStretch()
                count = 0

        if 0 < count < max_per_row and row_layout is not None:
            row_layout.addStretch()

        main_layout.addWidget(container)

    _add_section("Point Behaviors", point_behaviors, _POINT_BTN_STYLE)
    _add_section("State Behaviors", state_behaviors, _STATE_BTN_STYLE)

    # Position
    video_pos = annotator.video_frame.mapToGlobal(QPoint(0, 0))
    margin = 10
    toggle_width = annotator.behavior_toggle_button.width()
    x = video_pos.x() + margin + toggle_width + 10
    y = video_pos.y() + margin

    annotator.behavior_buttons_window.adjustSize()
    annotator.behavior_buttons_window.show()
    annotator.behavior_buttons_window.move(x, y)
    annotator.floating_windows.append(annotator.behavior_buttons_window)


def update_floating_visibility(annotator):
    """Hide/show floating windows when the main window is minimised or deactivated."""
    should_hide = (
        annotator.parent.windowState() & Qt.WindowState.WindowMinimized
        or not annotator.parent.isActiveWindow()
    )
    for w in annotator.floating_windows:
        if w is None:
            continue
        try:
            w.winId()
            if should_hide:
                w.hide()
            else:
                w.show()
        except RuntimeError:
            pass
