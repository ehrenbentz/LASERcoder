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

    def init_video_annotator(self, video_path, session_state_file, behavior_file, output_dir):
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
                behavior_key_file=behavior_file,
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
        
        while True:  # Create a loop to allow returning to setup
            # Create and show SetupManager dialog
            setup_dialog = SetupManager(config_manager=config_manager)
            
            # Let the setup dialog run
            setup_result = setup_dialog.exec()
            
            # Check if user completely canceled out of the setup
            if setup_result == QDialog.DialogCode.Rejected and not setup_dialog.start_video_flag:
                # User canceled out of the entire process
                break
            
            # Check if setup requirements are met to start video
            if setup_dialog.start_video_flag and setup_dialog.video_path and setup_dialog.behavior_key_file:
                # Get configuration values
                video_path = setup_dialog.video_path
                session_state_file = setup_dialog.session_state_file
                behavior_file = setup_dialog.behavior_key_file
                output_dir = setup_dialog.output_dir
                
                # Update configuration
                config_manager.update_output_dir(output_dir)
                config_manager.update_video_dir(video_path)
                
                # Initialize video annotator
                if main_window.init_video_annotator(
                    video_path=video_path,
                    session_state_file=session_state_file,
                    behavior_file=behavior_file,
                    output_dir=output_dir
                ):
                    main_window.show()
                    return app.exec()  # Start the event loop and show video annotator
                else:
                    print("Failed to initialize video annotator")
                    # Continue loop to allow user to try again
            else:
                # User canceled after reaching a certain point in setup or there was an error
                # If start_video_flag is False but setup_result is Accepted, we continue the loop
                if not setup_dialog.start_video_flag and setup_result == QDialog.DialogCode.Rejected:
                    # User fully canceled - exit the app
                    break
        
        return 0
            
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())