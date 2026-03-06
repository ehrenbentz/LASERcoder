# main.py

import locale
locale.setlocale(locale.LC_NUMERIC, "C")
import os
import sys
import ctypes

os.environ["LC_NUMERIC"] = "C"

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

# Windows
if sys.platform == "win32":
    os.environ["PATH"] = current_dir + os.pathsep + os.environ.get("PATH", "")

import mpv

import platform
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog
from pathlib import Path

# Import modules
from setup_manager import SetupManager
from config_manager import ConfigManager
from video_annotator import VideoAnnotator
import theme

class MainWindow(QMainWindow):
    """Main window class for the LaserTAG application."""
    
    def __init__(self):
        super().__init__()
        self.video_annotator = None

    def init_video_annotator(self, video_path, session_state_file, event_file, output_dir):
        """Initialize the video annotator component."""
        try:
            # If there's an existing video_annotator, clean it up first
            if self.video_annotator:
                self.video_annotator.deleteLater()
                self.video_annotator = None
            
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
            
            # Show the main window if it's not already visible
            if not self.isVisible():
                self.show()
            
            return True
        except Exception as e:
            print(f"Failed to initialize VideoAnnotator: {e}")
            return False

def main():
    """Main entry point for the LaserTAG application."""
    try:        
        # Create Qt Application
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # Initialize config manager and load theme
        config_manager = ConfigManager()
        theme.load_theme(config_manager.get_theme())
        app.setStyleSheet(theme.app_stylesheet())

        # Create main window
        main_window = MainWindow()
        
        while True:
            # Create and show SetupManager dialog
            setup_dialog = SetupManager(config_manager=config_manager)
            setup_result = setup_dialog.exec()

            if setup_result == QDialog.DialogCode.Rejected and not setup_dialog.start_video_flag:
                break

            if setup_dialog.start_video_flag and setup_dialog.video_path and setup_dialog.event_key_file:
                video_path = setup_dialog.video_path
                session_state_file = setup_dialog.session_state_file
                event_file = setup_dialog.event_key_file
                output_dir = setup_dialog.output_dir

                config_manager.update_output_dir(output_dir)
                config_manager.update_video_dir(video_path)

                if main_window.init_video_annotator(
                    video_path=video_path,
                    session_state_file=session_state_file,
                    event_file=event_file,
                    output_dir=output_dir
                ):
                    main_window.show()
                    app.exec()

                    # Clean up old video annotator before possibly looping
                    if main_window.video_annotator:
                        main_window.video_annotator.hide()
                        main_window.video_annotator.deleteLater()
                        main_window.video_annotator = None
                    main_window.setCentralWidget(None)
                    app.processEvents()

                    # Check if we should return to file selection or exit
                    if not getattr(main_window, '_return_to_setup', False):
                        break
                    main_window._return_to_setup = False
                else:
                    print("Failed to initialize video annotator")
            else:
                if not setup_dialog.start_video_flag and setup_result == QDialog.DialogCode.Rejected:
                    break

        return 0
            
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())