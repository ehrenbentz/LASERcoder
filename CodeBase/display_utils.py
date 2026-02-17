import locale
locale.setlocale(locale.LC_NUMERIC, "C")

import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def get_screen_geometry():
    """Return the available screen geometry for the primary monitor.

    Returns a dict with keys: width, height, x, y, scaling_factor.
    """
    app = QApplication.instance() or QApplication([])
    screen = app.primaryScreen()
    geom = screen.availableGeometry()
    return {
        "width": geom.width(),
        "height": geom.height(),
        "x": geom.x(),
        "y": geom.y(),
        "scaling_factor": screen.devicePixelRatio(),
        "screen": screen,
    }


def center_window(window, width, height, screen_info=None):
    """Center *window* on the primary screen, clamping to available space."""
    if screen_info is None:
        screen_info = get_screen_geometry()

    avail_w = screen_info["width"]
    avail_h = screen_info["height"]
    avail_x = screen_info["x"]
    avail_y = screen_info["y"]

    # Clamp to available space
    width = min(width, int(avail_w * 0.95))
    height = min(height, int(avail_h * 0.95))

    x = avail_x + (avail_w - width) // 2
    y = avail_y + (avail_h - height) // 2

    # Keep fully on-screen
    if x < avail_x:
        x = avail_x
    if y < avail_y:
        y = avail_y
    if x + width > avail_x + avail_w:
        x = avail_x + avail_w - width
    if y + height > avail_y + avail_h:
        y = avail_y + avail_h - height

    window.setGeometry(x, y, width, height)
    window.resize(width, height)
    window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMaximized)
