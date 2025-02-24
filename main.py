# main.py

import os
import sys
import platform
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QDialog
from pathlib import Path

# Add the current directory to PATH for loading dependencies before importing mpv
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = current_dir + os.pathsep + os.environ["PATH"]
import mpv

# Import modules
from setup_manager import SetupManager
from config_manager import ConfigManager
from video_annotator import VideoAnnotator

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
        app.setStyleSheet("QWidget { font-size: 12pt; }")  # Global font size change
        app.setStyle('Fusion')  # Use Fusion style for consistent look
        
        # Create main window
        main_window = MainWindow()
        
        # Initialize config manager
        config_manager = ConfigManager()
        
        # Create and show SetupManager dialog
        setup_dialog = SetupManager(config_manager=config_manager)
        
        # Let the setup dialog run - it will handle all validation internally
        setup_dialog.exec()
        
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
                return app.exec()
            else:
                print("Failed to initialize video annotator")
                return 1
        else:
            return 0
            
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())