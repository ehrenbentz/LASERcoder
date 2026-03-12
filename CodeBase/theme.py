# theme.py — Centralized dark/light/system theme for LaserTAG

import sys
import ctypes
import subprocess
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

_current_theme = "system"

# ---------------------------------------------------------------------------
# Dark palette (matches existing hardcoded colors)
# ---------------------------------------------------------------------------
_DARK = {
    # Core backgrounds
    "window_bg": "#2b2b2b",
    "titlebar_bg": "#1f1f1f",
    "panel_bg": "#2b2b2b",
    "dialog_bg": "#2b2b2b",
    "video_bg": "#000000",
    "input_bg": "#333333",
    "menu_bg": "#2b2b2b",
    "tree_bg": "#333333",
    # Text
    "text": "#ffffff",
    "text_secondary": "#cccccc",
    "text_on_accent": "#ffffff",
    # Borders
    "border": "#3a3a3a",
    "border_light": "#444444",
    # Buttons
    "button_bg": "#808080",
    "button_hover": "#1084D9",
    "button_pressed": "#006CC1",
    "button_text": "#000000",
    # Tree widget
    "tree_selected": "#808080",
    "tree_hover": "#404040",
    "tree_header_bg": "#2b2b2b",
    # Scrollbar
    "scrollbar_bg": "#2b2b2b",
    "scrollbar_handle": "#666666",
    # Progress bar (QPainter)
    "progress_bg": "#282828",
    "progress_fill": "#000096",
    "progress_text": "#ffffff",
    # Floating controls
    "float_toggle_bg": "#808080",
    "float_control_bg": "#a9a9a9",
    "float_control_text": "#000000",
    "float_point_bg": "#5B6770",
    "float_state_bg": "#7B6469",
    # Accent
    "accent": "#1084D9",
    "accent_hover": "#3399E6",
    "accent_pressed": "#006CC1",
    # Annotation state indicators
    "active_color": "darkorange",
    "highlight_color": "dodgerblue",
    # Visualizer (QPainter)
    "viz_bg": "#ffffff",
    "viz_track": "#f0f0f0",
    "viz_state": "#6496dc",
    "viz_point": "#dc5050",
    "viz_text": "#282828",
    "viz_header_bg": "#e6e6e6",
    "viz_header_text": "#464646",
    "viz_grid": "#c8c8c8",
}

# ---------------------------------------------------------------------------
# Light palette
# ---------------------------------------------------------------------------
_LIGHT = {
    # Core backgrounds
    "window_bg": "#e8e8e8",
    "titlebar_bg": "#d0d0d0",
    "panel_bg": "#f5f5f5",
    "dialog_bg": "#f0f0f0",
    "video_bg": "#000000",
    "input_bg": "#ffffff",
    "menu_bg": "#f5f5f5",
    "tree_bg": "#ffffff",
    # Text
    "text": "#2d2d2d",
    "text_secondary": "#666666",
    "text_on_accent": "#ffffff",
    # Borders
    "border": "#c8c8c8",
    "border_light": "#d8d8d8",
    # Buttons
    "button_bg": "#d4d4d4",
    "button_hover": "#1084D9",
    "button_pressed": "#006CC1",
    "button_text": "#2d2d2d",
    # Tree widget
    "tree_selected": "#b8cfe0",
    "tree_hover": "#e6eef5",
    "tree_header_bg": "#eaeaea",
    # Scrollbar
    "scrollbar_bg": "#ebebeb",
    "scrollbar_handle": "#b0b0b0",
    # Progress bar (QPainter)
    "progress_bg": "#c0c0c0",
    "progress_fill": "#3878a8",
    "progress_text": "#000000",
    # Floating controls
    "float_toggle_bg": "#c8c8c8",
    "float_control_bg": "#bfbfbf",
    "float_control_text": "#2d2d2d",
    "float_point_bg": "#7a8a94",
    "float_state_bg": "#9a848a",
    # Accent
    "accent": "#1084D9",
    "accent_hover": "#3399E6",
    "accent_pressed": "#006CC1",
    # Annotation state indicators
    "active_color": "darkorange",
    "highlight_color": "dodgerblue",
    # Visualizer (QPainter)
    "viz_bg": "#ffffff",
    "viz_track": "#f0f0f0",
    "viz_state": "#6496dc",
    "viz_point": "#dc5050",
    "viz_text": "#2d2d2d",
    "viz_header_bg": "#e6e6e6",
    "viz_header_text": "#464646",
    "viz_grid": "#c8c8c8",
}

_palettes = {"dark": _DARK, "light": _LIGHT}

# ---------------------------------------------------------------------------
# System detection
# ---------------------------------------------------------------------------

def _detect_system_theme():
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and "Dark" in result.stdout:
                return "dark"
            return "light"
        except Exception:
            return "dark"
    else:
        app = QApplication.instance()
        if app:
            lightness = app.palette().color(QPalette.ColorRole.Window).lightness()
            return "dark" if lightness < 128 else "light"
        return "dark"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_theme(name: str):
    global _current_theme
    _current_theme = name

def current_theme() -> str:
    return _current_theme

def _resolved() -> dict:
    if _current_theme == "system":
        return _palettes[_detect_system_theme()]
    return _palettes.get(_current_theme, _DARK)

def color(role: str) -> str:
    return _resolved().get(role, "#ff00ff")

def qcolor(role: str) -> QColor:
    return QColor(color(role))

# ---------------------------------------------------------------------------
# Title-bar theming (OS-level)
# ---------------------------------------------------------------------------

def _hex_to_colorref(hex_color: str) -> int:
    """Convert '#RRGGBB' to a COLORREF (0x00BBGGRR) for the Windows DWM API."""
    c = QColor(hex_color)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


def apply_titlebar_theme(window) -> None:
    """Apply the current theme colors to a window's native title bar.

    Windows 11+: sets caption color, text color, and border color via DWM.
    Windows 10:  enables/disables immersive dark mode for the title bar.
    macOS:       sets NSWindow appearance to dark/light Aqua.
    """
    p = _resolved()
    is_dark = (_current_theme == "dark") or (
        _current_theme == "system" and _detect_system_theme() == "dark"
    )

    if sys.platform == "win32":
        try:
            hwnd = int(window.winId())
            dwmapi = ctypes.windll.dwmapi

            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 1809+)
            dark_val = ctypes.c_int(1 if is_dark else 0)
            dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val)
            )

            # DWMWA_BORDER_COLOR = 34, DWMWA_CAPTION_COLOR = 35,
            # DWMWA_TEXT_COLOR = 36  (Windows 11 22000+)
            caption_cr = ctypes.c_uint32(_hex_to_colorref(p["titlebar_bg"]))
            text_cr = ctypes.c_uint32(_hex_to_colorref(p["text"]))
            border_cr = ctypes.c_uint32(_hex_to_colorref(p["border"]))

            dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption_cr), ctypes.sizeof(caption_cr)
            )
            dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(text_cr), ctypes.sizeof(text_cr)
            )
            dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(border_cr), ctypes.sizeof(border_cr)
            )
        except Exception:
            pass  # graceful fallback on older Windows

    elif sys.platform == "darwin":
        try:
            from ctypes import c_void_p, c_bool
            objc = ctypes.cdll.LoadLibrary("libobjc.dylib")

            sel = ctypes.CFUNCTYPE(c_void_p, ctypes.c_char_p)(
                ("sel_registerName", objc)
            )
            msg = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p)(
                ("objc_msgSend", objc)
            )
            msg_p = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p, c_void_p)(
                ("objc_msgSend", objc)
            )
            cls = ctypes.CFUNCTYPE(c_void_p, ctypes.c_char_p)(
                ("objc_getClass", objc)
            )

            # Get NSWindow from the Qt window
            nsview = c_void_p(int(window.winId()))
            nswindow = msg(nsview, sel(b"window"))

            # Create NSAppearance for dark or light
            appearance_name = (
                b"NSAppearanceNameDarkAqua" if is_dark
                else b"NSAppearanceNameAqua"
            )
            NSAppearance = cls(b"NSAppearance")
            ns_string = msg_p(
                cls(b"NSString"),
                sel(b"stringWithUTF8String:"),
                ctypes.c_char_p(appearance_name),
            )
            appearance = msg_p(
                NSAppearance,
                sel(b"appearanceNamed:"),
                ns_string,
            )
            msg_p(nswindow, sel(b"setAppearance:"), appearance)
        except Exception:
            pass  # graceful fallback


def apply_dialog_theme(dialog) -> None:
    """Apply dialog stylesheet and native title-bar colors in one call."""
    dialog.setStyleSheet(dialog_stylesheet())
    apply_titlebar_theme(dialog)


# ---------------------------------------------------------------------------
# Stylesheet generators
# ---------------------------------------------------------------------------

def app_stylesheet() -> str:
    p = _resolved()
    return (
        f"QWidget {{ font-size: 12pt; }}"
        f"QMessageBox {{ background-color: {p['dialog_bg']}; color: {p['text']}; }}"
        f"QMessageBox QLabel {{ color: {p['text']}; background: transparent; }}"
        f"QMessageBox QPushButton {{ background-color: {p['button_bg']}; color: {p['button_text']};"
        f"  border: none; border-radius: 4px; padding: 5px 12px; min-width: 70px; }}"
        f"QMessageBox QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QMessageBox QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
        f"QInputDialog {{ background-color: {p['dialog_bg']}; color: {p['text']}; }}"
        f"QInputDialog QLabel {{ color: {p['text']}; background: transparent; }}"
        f"QInputDialog QLineEdit {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QInputDialog QPushButton {{ background-color: {p['button_bg']}; color: {p['button_text']};"
        f"  border: none; border-radius: 4px; padding: 5px 12px; min-width: 70px; }}"
        f"QInputDialog QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QInputDialog QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
        f"QFileDialog {{ background-color: {p['dialog_bg']}; color: {p['text']}; }}"
    )

def dialog_stylesheet() -> str:
    p = _resolved()
    return (
        f"QDialog {{ background-color: {p['dialog_bg']}; color: {p['text']}; }}"
        f"QWidget {{ background-color: {p['dialog_bg']}; color: {p['text']}; }}"
        f"QFrame {{ background-color: {p['dialog_bg']}; }}"
        f"QLabel {{ color: {p['text']}; background: transparent; }}"
        f"QLineEdit {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QTextEdit {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QGroupBox {{ color: {p['text']}; border: 1px solid {p['border']};"
        f"  border-radius: 4px; margin-top: 8px; padding-top: 14px;"
        f"  background-color: {p['dialog_bg']}; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px; }}"
        f"QPushButton {{ background-color: {p['button_bg']}; color: {p['button_text']};"
        f"  border: none; border-radius: 4px; padding: 5px 12px; }}"
        f"QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
        f"QRadioButton {{ color: {p['text']}; background: transparent; }}"
        f"QRadioButton::indicator {{ width: 14px; height: 14px;"
        f"  border: 2px solid {p['border']}; border-radius: 9px;"
        f"  background-color: {p['input_bg']}; }}"
        f"QRadioButton::indicator:checked {{ border: 2px solid {p['accent']};"
        f"  background-color: {p['accent']}; }}"
        f"QComboBox {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QComboBox QAbstractItemView {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  selection-background-color: {p['button_hover']}; }}"
        f"QSpinBox {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QListWidget {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; }}"
        f"QListWidget::item:selected {{ background-color: {p['tree_selected']}; }}"
        f"QListWidget::item:hover {{ background-color: {p['tree_hover']}; }}"
        f"QSplitter {{ background-color: {p['dialog_bg']}; }}"
        f"QSplitter::handle {{ background-color: {p['border']}; }}"
        f"QMessageBox {{ background-color: {p['dialog_bg']}; }}"
        f"QDialogButtonBox QPushButton {{ min-width: 70px; }}"
        f"QScrollArea {{ background: {p['dialog_bg']}; border: none; }}"
        f"QScrollBar:vertical {{ border: none; background: {p['scrollbar_bg']}; width: 10px; }}"
        f"QScrollBar::handle:vertical {{ background: {p['scrollbar_handle']}; min-height: 20px;"
        f"  border-radius: 5px; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
    )

def menu_stylesheet() -> str:
    p = _resolved()
    return (
        f"QMenu {{ background-color: {p['menu_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; }}"
        f"QMenu::item {{ padding: 6px 28px 6px 28px; }}"
        f"QMenu::item:selected {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QMenu::indicator {{ width: 16px; height: 16px;"
        f"  margin-left: 6px; }}"
        f"QMenu::indicator:checked {{ image: none;"
        f"  background-color: {p['accent']};"
        f"  border: 1px solid {p['accent']}; border-radius: 3px; }}"
        f"QMenu::indicator:unchecked {{ image: none;"
        f"  background-color: {p['input_bg']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; }}"
    )

def tree_stylesheet(heading_font="12px") -> str:
    p = _resolved()
    return (
        f"QTreeWidget {{"
        f"  background-color: {p['tree_bg']}; border: 1px solid {p['border_light']};"
        f"  border-radius: 4px; color: {p['text']}; font-size: {heading_font}; }}"
        f"QTreeWidget::item {{ height: 18px; padding: 0px; margin: 0px;"
        f"  font-size: {heading_font}; }}"
        f"QTreeWidget::item:selected {{ background-color: {p['tree_selected']}; color: {p['text_on_accent']}; }}"
        f"QTreeWidget::item:hover {{ background-color: {p['tree_hover']}; }}"
        f"QHeaderView::section {{"
        f"  background-color: {p['tree_header_bg']}; color: {p['text']}; font-weight: bold;"
        f"  font-size: {heading_font}; padding: 2px;"
        f"  border: none; border-bottom: 1px solid {p['border_light']}; }}"
        f"QScrollBar:vertical {{ border: none; background: {p['scrollbar_bg']}; width: 10px; }}"
        f"QScrollBar::handle:vertical {{ background: {p['scrollbar_handle']}; min-height: 20px;"
        f"  border-radius: 5px; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}"
    )

def button_stylesheet(heading_font="12px") -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['button_bg']}; color: {p['button_text']};"
        f"  border: none; border-radius: 4px; padding: 3px 8px;"
        f"  font-size: {heading_font}; }}"
        f"QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
    )

def button_large_stylesheet(heading_font="12px") -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['button_bg']}; color: {p['button_text']};"
        f"  border: none; border-radius: 4px; padding: 4px;"
        f"  font-size: {heading_font}; }}"
        f"QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
    )

def heading_label_style(heading_font="12px") -> str:
    p = _resolved()
    return f"color: {p['text']}; font-weight: bold; font-size: {heading_font};"

def panel_frame_stylesheet() -> str:
    p = _resolved()
    return (
        f"QFrame {{"
        f"  background-color: {p['panel_bg']};"
        f"  border: 1px solid {p['border']};"
        f"  border-radius: 4px;"
        f"}}"
    )

def input_stylesheet() -> str:
    p = _resolved()
    return (
        f"QLineEdit {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
        f"QTextEdit {{ background-color: {p['input_bg']}; color: {p['text']};"
        f"  border: 1px solid {p['border']}; border-radius: 3px; padding: 3px; }}"
    )

def groupbox_stylesheet() -> str:
    p = _resolved()
    return (
        f"QGroupBox {{ color: {p['text']}; border: 1px solid {p['border']};"
        f"  border-radius: 4px; margin-top: 8px; padding-top: 14px; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 3px; }}"
    )

# ---------------------------------------------------------------------------
# Floating-control stylesheets
# ---------------------------------------------------------------------------

def toggle_btn_stylesheet() -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['float_toggle_bg']}; color: {p['text']};"
        f"  border: none; border-radius: 4px; padding: 4px; font-size: 12px; }}"
        f"QPushButton:hover {{ background-color: {p['button_hover']}; color: {p['text_on_accent']}; }}"
        f"QPushButton:pressed {{ background-color: {p['button_pressed']}; color: {p['text_on_accent']}; }}"
    )

def zoom_active_stylesheet() -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['accent']}; color: {p['text_on_accent']};"
        f"  border: none; border-radius: 4px; padding: 4px; font-size: 12px; }}"
        f"QPushButton:hover {{ background-color: {p['accent_hover']}; }}"
        f"QPushButton:pressed {{ background-color: {p['accent_pressed']}; }}"
    )

def control_btn_stylesheet() -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['float_control_bg']}; color: {p['float_control_text']};"
        f"  border: 1px solid grey; border-radius: 3px; padding: 0px;"
        f"  text-align: center; font-size: 14px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: darkgrey; color: white; }}"
        f"QPushButton:pressed {{ background-color: #404040; color: white; }}"
    )

def point_btn_stylesheet() -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['float_point_bg']}; color: white;"
        f"  border: 1px solid grey; border-radius: 3px; padding: 5px;"
        f"  text-align: center; }}"
        f"QPushButton:hover {{ background-color: darkgrey; color: white; }}"
        f"QPushButton:pressed {{ background-color: #404040; color: white; }}"
    )

def state_btn_stylesheet() -> str:
    p = _resolved()
    return (
        f"QPushButton {{ background-color: {p['float_state_bg']}; color: white;"
        f"  border: 1px solid grey; border-radius: 3px; padding: 5px;"
        f"  text-align: center; }}"
        f"QPushButton:hover {{ background-color: darkgrey; color: white; }}"
        f"QPushButton:pressed {{ background-color: #404040; color: white; }}"
    )

def coding_info_label_style() -> str:
    p = _resolved()
    return f"color: {p['progress_text']}; font-size: 10px; padding-right: 10px; margin: 0;"

def header_widget_stylesheet() -> str:
    p = _resolved()
    return f"background-color: {p['panel_bg']};"

def event_label_stylesheet() -> str:
    return "color: white; background-color: rgba(50,50,50,180); padding: 2px;"
