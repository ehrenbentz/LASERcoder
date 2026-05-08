# main.py

import locale
locale.setlocale(locale.LC_NUMERIC, "C")
import os
import sys
import ctypes

os.environ["LC_NUMERIC"] = "C"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window.debug=false"

# Debug logging (set to False to disable)
DEBUG_MODE = True
from debug_logger import init_logging, get_logger
init_logging(DEBUG_MODE)
logger = get_logger()

# Resolve the application directory (works both interpreted and Nuitka-compiled)
if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
    current_dir = os.path.dirname(sys.executable)
elif "__compiled__" in dir():
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))

repo_root = os.path.dirname(current_dir)

def _find_libmpv(*candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

if sys.platform == "darwin":
    import platform as _plat
    _arch = "arm64" if _plat.machine() == "arm64" else "x86_64"
    libmpv_path = _find_libmpv(
        os.path.join(current_dir, "libs", "libmpv.2.dylib"),
        os.path.join(repo_root, "libs", "mpv", "macOS", _arch, "libmpv.2.dylib"),
    )
    if libmpv_path:
        import ctypes.util
        _original_find_library = ctypes.util.find_library
        def _patched_find_library(name):
            if name == "mpv":
                return libmpv_path
            return _original_find_library(name)
        ctypes.util.find_library = _patched_find_library

elif sys.platform.startswith("linux"):
    libmpv_path = _find_libmpv(
        os.path.join(current_dir, "libmpv.so.2"),
        os.path.join(repo_root, "libs", "mpv", "linux", "libmpv.so.2"),
    )
    if libmpv_path:
        import ctypes.util
        _original_find_library = ctypes.util.find_library
        def _patched_find_library(name):
            if name == "mpv":
                return libmpv_path
            return _original_find_library(name)
        ctypes.util.find_library = _patched_find_library

if sys.platform == "win32":
    os.environ["PATH"] = current_dir + os.pathsep + os.environ.get("PATH", "")
    _win_mpv_dir = os.path.join(repo_root, "libs", "mpv", "win64")
    if os.path.isdir(_win_mpv_dir):
        os.environ["PATH"] = _win_mpv_dir + os.pathsep + os.environ["PATH"]

import mpv

import platform
from PySide6.QtCore import Qt, QEventLoop, Signal
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog
from pathlib import Path

# Import modules
from setup_manager import SetupManager
from config_manager import get_config
from video_annotator import VideoAnnotator
import theme
import icons_rc

class MainWindow(QMainWindow):
    """Main window class"""

    annotator_finished = Signal()

    def __init__(self):
        super().__init__()
        self.video_annotator = None
        self.annotator_finished.connect(self._on_annotator_finished)

    def apply_theme(self):
        """Update the main window background and title bar to match the current theme"""
        self.setStyleSheet(f"background-color: {theme.color('window_bg')};")
        theme.apply_titlebar_theme(self)

    def closeEvent(self, event):
        """Stop background threads before the widget tree is destroyed."""
        if self.video_annotator:
            va = self.video_annotator
            if hasattr(va, 'spectrogram_widget'):
                va.spectrogram_widget.stop_spectrogram()
            if hasattr(va, 'waveform_widget'):
                va.waveform_widget.cancel_extraction()
        super().closeEvent(event)

    # Setup / annotate cycle

    def start_setup_cycle(self):
        """Create a SetupManager and begin the setup flow"""
        setup = SetupManager(config_manager=get_config(), parent=self)
        setup.finished.connect(
            lambda result: self._on_setup_finished(setup, result))
        setup.start()

    def _on_setup_finished(self, setup, result):
        """Handle the result of the setup flow"""
        if result == QDialog.DialogCode.Rejected and not setup.start_video_flag:
            setup.deleteLater()
            QApplication.instance().quit()
            return

        if setup.start_video_flag and setup.video_path and setup.event_key_file:
            video_path = setup.video_path
            event_file = setup.event_key_file
            output_dir = setup.output_dir

            config = get_config()
            config.update_output_dir(output_dir)
            if not setup.multi_part_files:
                config.update_video_dir(video_path)

            logger.switch_to_output_dir(output_dir)
            logger.info("Starting annotator: video=%s output=%s",
                        video_path, output_dir)

            setup.deleteLater()

            if self.init_video_annotator(
                video_path=video_path,
                event_file=event_file,
                output_dir=output_dir
            ):
                pass
            else:
                logger.error("Failed to initialize video annotator")
                self.start_setup_cycle()
        else:
            setup.deleteLater()
            QApplication.instance().quit()

    def _on_annotator_finished(self):
        """Clean up annotator and start a new setup cycle"""
        if self.video_annotator:
            self.video_annotator.hide()
            self.video_annotator.deleteLater()
            self.video_annotator = None
        self.setCentralWidget(None)
        self.setMinimumSize(0, 0)

        self.hide()
        self.setWindowFlags(Qt.WindowType.Window)
        self.apply_theme()
        self.showMaximized()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.start_setup_cycle()

    # Video annotator

    def init_video_annotator(self, video_path, event_file, output_dir):
        """Initialize the video annotator component"""
        try:
            # If there's an existing video_annotator, clean it up first
            if self.video_annotator:
                self.video_annotator.deleteLater()
                self.video_annotator = None

            # Hide before creating the GL widget so the native window
            # surface is recreated with OpenGL support.
            was_visible = self.isVisible()
            if was_visible:
                self.hide()
                QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

            # Create new video annotator
            self.video_annotator = VideoAnnotator(
                self,
                video_path=video_path,
                event_key_file=event_file,
                output_dir=output_dir
            )

            # Set as central widget
            self.setCentralWidget(self.video_annotator)

            if sys.platform != "darwin":
                self.showFullScreen()
            self.apply_theme()
            QApplication.processEvents(
                QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            if self.video_annotator and hasattr(self.video_annotator, 'gl_widget'):
                self.video_annotator.gl_widget.update()

            logger.info("VideoAnnotator initialized successfully")
            return True
        except Exception as e:
            logger.exception("Failed to initialize VideoAnnotator: %s", e)
            if was_visible:
                self.show()
            return False

def main():
    """Main entry point"""
    try:
        logger.info("LASERcoder starting")

        # Create Qt Application
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Initialize config manager and load theme
        config_manager = get_config()
        theme.load_theme(config_manager.get_theme())
        theme.apply_config_overrides(config_manager)
        app.setStyleSheet(theme.app_stylesheet())

        # Create main window and show as maximized background
        main_window = MainWindow()
        main_window.setStyleSheet(f"background-color: {theme.color('window_bg')};")
        main_window.showMaximized()
        app.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        main_window.apply_theme()

        # Start the setup/annotate cycle and run the single event loop
        main_window.start_setup_cycle()
        result = app.exec()

        logger.info("LASERcoder exiting normally")
        return result

    except Exception as e:
        logger.critical("Unhandled error in main: %s", e, exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
