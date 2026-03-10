import locale
locale.setlocale(locale.LC_NUMERIC, "C")

import colorsys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QPen, QBrush


def is_macos_resource_fork(name):
    """Return True if *name* is a macOS resource-fork / indexing file."""
    return name.startswith("._") or name == ".DS_Store"


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


_HUE_ANGLE = 30
_HUE_OFFSET = 30.0


def generate_default_colors(event_names):
    """Generate distinct colors for a set of event names using golden-angle hue spacing."""
    cmap = {}
    for i, name in enumerate(sorted(event_names)):
        hue = (_HUE_OFFSET + i * _HUE_ANGLE) % 360
        r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.55, 0.65)
        cmap[name] = QColor(int(r * 255), int(g * 255), int(b * 255))
    return cmap


def make_color_icon(color, size=16):
    """Create a small colored rounded-rect icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color).darker(150), 1))
    p.setBrush(QBrush(color))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
    p.end()
    return QIcon(pm)
