# main.py

import locale
locale.setlocale(locale.LC_NUMERIC, "C")
import os
import sys
import ctypes

os.environ["LC_NUMERIC"] = "C"
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window.debug=false"

# --- Debug logging (set to False to disable) ---
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

# MacOS
if sys.platform == "darwin":
    libs_dir = os.path.join(current_dir, "libs")
    libmpv_path = os.path.join(libs_dir, "libmpv.2.dylib")
    if os.path.exists(libmpv_path):
        import ctypes.util
        _original_find_library = ctypes.util.find_library
        def _patched_find_library(name):
            if name == "mpv":
                return libmpv_path
            return _original_find_library(name)
        ctypes.util.find_library = _patched_find_library

# Linux
elif sys.platform.startswith("linux"):
    libmpv_path = os.path.join(current_dir, "libmpv.so.2")
    if os.path.exists(libmpv_path):
        import ctypes.util
        _original_find_library = ctypes.util.find_library
        def _patched_find_library(name):
            if name == "mpv":
                return libmpv_path
            return _original_find_library(name)
        ctypes.util.find_library = _patched_find_library

# Windows
if sys.platform == "win32":
    os.environ["PATH"] = current_dir + os.pathsep + os.environ.get("PATH", "")

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

class MainWindow(QMainWindow):
    """Main window class for the LaserTAG application."""

    annotator_finished = Signal()

    def __init__(self):
        super().__init__()
        self.video_annotator = None
        self.annotator_finished.connect(self._on_annotator_finished)

    def apply_theme(self):
        """Update the main window background and title bar to match the current theme."""
        self.setStyleSheet(f"background-color: {theme.color('window_bg')};")
        theme.apply_titlebar_theme(self)

    # ------------------------------------------------------------------
    # Setup / annotate cycle
    # ------------------------------------------------------------------

    def start_setup_cycle(self):
        """Create a SetupManager and begin the setup flow."""
        setup = SetupManager(config_manager=get_config(), parent=self)
        setup.finished.connect(
            lambda result: self._on_setup_finished(setup, result))
        setup.start()

    def _on_setup_finished(self, setup, result):
        """Handle the result of the setup flow."""
        if result == QDialog.DialogCode.Rejected and not setup.start_video_flag:
            setup.deleteLater()
            QApplication.instance().quit()
            return

        if setup.start_video_flag and setup.video_path and setup.event_key_file:
            video_path = setup.video_path
            session_state_file = setup.session_state_file
            event_file = setup.event_key_file
            output_dir = setup.output_dir

            config = get_config()
            config.update_output_dir(output_dir)
            config.update_video_dir(video_path)

            logger.switch_to_output_dir(output_dir)
            logger.info("Starting annotator: video=%s output=%s",
                        video_path, output_dir)

            setup.deleteLater()

            if self.init_video_annotator(
                video_path=video_path,
                session_state_file=session_state_file,
                event_file=event_file,
                output_dir=output_dir
            ):
                # On macOS, VideoAnnotator.__init__ already showed the
                # parent with fullscreen presentation.  An extra show()
                # here would reset the dock/menubar hiding.
                if sys.platform != "darwin":
                    self.show()
                # Annotator runs in the single app event loop.
                # When done, it emits annotator_finished.
            else:
                logger.error("Failed to initialize video annotator")
                self.start_setup_cycle()
        else:
            setup.deleteLater()
            QApplication.instance().quit()

    def _on_annotator_finished(self):
        """Clean up annotator and start a new setup cycle."""
        if self.video_annotator:
            self.video_annotator.hide()
            self.video_annotator.deleteLater()
            self.video_annotator = None
        self.setCentralWidget(None)
        # Restore normal window (remove FramelessWindowHint)
        self.hide()
        self.setWindowFlags(Qt.WindowType.Window)
        self.apply_theme()
        self.showMaximized()
        QApplication.processEvents(
            QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.start_setup_cycle()

    # ------------------------------------------------------------------
    # Video annotator
    # ------------------------------------------------------------------

    def init_video_annotator(self, video_path, session_state_file, event_file, output_dir):
        """Initialize the video annotator component."""
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
                session_state_file=session_state_file,
                event_key_file=event_file,
                output_dir=output_dir
            )

            # Set as central widget
            self.setCentralWidget(self.video_annotator)

            # On macOS, VideoAnnotator.__init__ already showed the parent
            # with fullscreen flags.  Calling show() again would reset the
            # display.  On other platforms the window may still be hidden
            # from the hide() call above.
            if sys.platform != "darwin":
                self.show()
            self.apply_theme()

            logger.info("VideoAnnotator initialized successfully")
            return True
        except Exception as e:
            logger.exception("Failed to initialize VideoAnnotator: %s", e)
            if was_visible:
                self.show()
            return False

def main():
    """Main entry point for the LaserTAG application."""
    try:
        logger.info("LaserTAG starting")

        # Create Qt Application
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Initialize config manager and load theme
        config_manager = get_config()
        theme.load_theme(config_manager.get_theme())
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

        logger.info("LaserTAG exiting normally")
        return result

    except Exception as e:
        logger.critical("Unhandled error in main: %s", e, exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
