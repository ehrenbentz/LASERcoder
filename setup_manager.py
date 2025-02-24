# setup_manager.py

import os
import csv
import json
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QWidget, QApplication)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

# import modules
from config_manager import ConfigManager
from files_manager import FilesManager
from behavior_key_editor import BehaviorKeyEditor

class SetupManager(QDialog):
    """Dialog for managing initial setup of video annotation session."""
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """Initialize the SetupManager.
        
        Args:
            config_manager: Instance of ConfigManager for handling configuration
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.config_manager = config_manager
        
        # Initialize state variables
        self.start_video_flag = False
        self.video_path = None
        self.video_name = ""
        self.behavior_key_file = None
        self.saved_state = None
        self.start_frame = 0
        
        # Initialize directories
        self.output_dir = self.config_manager.get_output_dir()
        self.behavior_key_dir = None
        self.annotations_dir = None
        self.resume_dir = None
        
        # Initialize file paths
        self.annotations_file = ""
        self.session_state_file = ""
        
        # Set window properties
        self.setWindowTitle("LaserTAG Setup")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(QSize(400, 200))
        
        # Handle window close event
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # Configure display settings
        self.configure_display()
        
        # Start setup process
        self.start_setup()
        
    def configure_display(self):
        """Configure display settings and window properties"""
        self.app = QApplication.instance() or QApplication([])
        # Get the primary screen
        self.screen = self.app.primaryScreen()
        self.scaling_factor = self.screen.devicePixelRatio()
        
        # Get geometry from the primary screen (returns a QRect)
        geom = self.screen.geometry()
        self.display_width = geom.width()
        self.display_height = geom.height()
        self.display_x = geom.x()
        self.display_y = geom.y()
        
    def closeEvent(self, event):
        """Handle window close event."""
        # Just let the close event proceed normally
        event.accept()
        
    def start_setup(self):
        """Initial setup process to get the output directory and video file."""
        try:
            files_manager = FilesManager(
                self,
                initial_output_dir=self.config_manager.get_output_dir(),
                initial_video_dir=self.config_manager.get_video_dir()
            )
            
            # Execute the files manager dialog
            files_manager_result = files_manager.exec()
            
            if files_manager_result == QDialog.DialogCode.Accepted:
                # Check if files were selected
                if files_manager.output_dir and files_manager.selected_video_file:
                    # Update configuration with new directories
                    self.config_manager.update_output_dir(files_manager.output_dir)
                    self.config_manager.update_video_dir(files_manager.selected_video_file)
                    
                    self.output_dir = files_manager.output_dir
                    self.video_path = files_manager.selected_video_file
                    # Handle multiple dots in filename
                    self.video_name = Path(self.video_path).stem
                    
                    self.initialize_output_dir()
                    self.initialize_file_paths()
                    self.check_existing_session()
                else:
                    QMessageBox.warning(self, "Warning", "No video or output directory selected.")
                    self.done(QDialog.DialogCode.Rejected)
            else:
                self.done(QDialog.DialogCode.Rejected)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error in setup process: {str(e)}")
            self.done(QDialog.DialogCode.Rejected)
            
    def initialize_output_dir(self):
        """Create the subdirectory structure based on the selected output directory."""
        try:
            self.behavior_key_dir = os.path.join(self.output_dir, "Behavior_Keys")
            self.annotations_dir = os.path.join(self.output_dir, "Annotations")
            self.resume_dir = os.path.join(self.output_dir, "Resume")
            os.makedirs(self.output_dir, exist_ok=True)
            os.makedirs(self.behavior_key_dir, exist_ok=True)
            os.makedirs(self.annotations_dir, exist_ok=True)
            os.makedirs(self.resume_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creating directories: {str(e)}")
            self.done(QDialog.DialogCode.Rejected)
            
    def initialize_file_paths(self):
        """Initialize file paths for annotations and session state."""
        self.annotations_file = os.path.join(self.annotations_dir, f"{self.video_name}_Annotations.csv")
        self.session_state_file = os.path.join(self.resume_dir, f"{self.video_name}_session_state.json")
        
    def create_empty_files(self):
        """Create new empty annotation and session state files."""
        try:
            # Create empty annotation file
            with open(self.annotations_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    'Video',
                    'Name',
                    'Type',
                    'Mutually_Exclusive',
                    'H_Start',
                    'H_End',
                    'Start',
                    'End',
                    'Duration',
                    'Manual_Edit',
                    'Notes'  # Added Notes field
                ])
            
            # Create empty session state file with timestamp in milliseconds
            with open(self.session_state_file, 'w') as f:
                json.dump({"timestamp_ms": 0, "current_frame": 0}, f)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creating files: {str(e)}")
            self.done(QDialog.DialogCode.Rejected)
            
    def check_existing_session(self):
        """Check if a previous session exists and handle accordingly."""
        try:
            if os.path.exists(self.session_state_file):
                with open(self.session_state_file, 'r') as f:
                    self.saved_state = json.load(f)
                    # Convert from milliseconds to seconds if using old format
                    if 'timestamp_ms' in self.saved_state:
                        self.saved_state['timestamp_sec'] = self.saved_state['timestamp_ms'] / 1000.0
                self.show_resume_dialog()
            else:
                self.start_frame = 0
                self.saved_state = None
                self.create_empty_files()
                self.show_behavior_key_editor()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error checking existing session: {str(e)}")
            self.done(QDialog.DialogCode.Rejected)
            
    def show_resume_dialog(self):
        """Show dialog asking user if they want to resume previous session."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Resume Session")
        dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(dialog)
        
        # Add message with custom font
        message = QLabel(f"A previous session was found for {self.video_name}.\n\nWhat would you like to do?")
        font = QFont()
        message.setFont(font)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        button_style = """
            QPushButton {
                padding: 8px 16px;
                min-width: 100px;
            }
        """
        
        resume_btn = QPushButton("Resume")
        resume_btn.setFont(font)
        resume_btn.setStyleSheet(button_style)
        resume_btn.clicked.connect(lambda: self.handle_resume_choice("resume", dialog))
        
        start_over_btn = QPushButton("Start Over")
        start_over_btn.setFont(font)
        start_over_btn.setStyleSheet(button_style)
        start_over_btn.clicked.connect(lambda: self.handle_resume_choice("start_over", dialog))
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFont(font)
        cancel_btn.setStyleSheet(button_style)
        cancel_btn.clicked.connect(lambda: self.handle_resume_choice("cancel", dialog))
        
        button_layout.addWidget(resume_btn)
        button_layout.addWidget(start_over_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addSpacing(20)  # Add some spacing between message and buttons
        layout.addLayout(button_layout)
        
        # Center dialog on screen
        self.center_window(dialog, 500, 250)
        
        dialog.exec()
        
    def handle_resume_choice(self, choice, dialog):
        """Handle the user's choice from the resume dialog."""
        dialog.close()
        
        if choice == "resume":
            self.resume_session()
        elif choice == "start_over":
            self.confirm_start_over()
        else:  # cancel
            self.done(QDialog.DialogCode.Rejected)
            
    def confirm_start_over(self):
        """Show confirmation dialog for starting over."""
        reply = QMessageBox.question(
            self,
            "Confirm Start Over",
            f"Are you sure?\n\nStarting over will delete all current annotations for\n{self.video_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Delete existing files
            files_to_delete = [self.session_state_file, self.annotations_file]
            for file_path in files_to_delete:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        QMessageBox.warning(self, "Warning", f"Error deleting file {file_path}: {str(e)}")
            
            # Reset state
            self.start_frame = 0
            self.saved_state = None
            
            # Create new empty files
            self.create_empty_files()
            
            self.show_behavior_key_editor()
        else:
            self.show_resume_dialog()
            
    def resume_session(self):
        """Resume the previous session."""
        if self.saved_state:
            # Get current_frame from saved state, defaulting to timestamp conversion if not present
            if 'current_frame' in self.saved_state:
                self.start_frame = self.saved_state['current_frame']
            elif 'timestamp_ms' in self.saved_state:
                # Convert milliseconds to frame number (assuming frame rate if needed)
                self.start_frame = int(self.saved_state['timestamp_ms'] / 1000.0 * 30)  # assuming 30fps
        else:
            self.start_frame = 0
            
        self.show_behavior_key_editor()
        
    def show_behavior_key_editor(self):
        """Show the behavior key editor dialog."""
        try:
            behavior_editor = BehaviorKeyEditor(
                self,
                self.behavior_key_dir,
                on_start_video=self.on_start_video,
                on_cancel=self.on_cancel,
                config_manager=self.config_manager
            )
            
            # Execute the dialog
            result = behavior_editor.exec()
            
            # Check if the start_video_flag is set - BehaviorKeyEditor will handle its own validation
            if behavior_editor.start_video_flag:
                self.start_video_flag = True
                self.behavior_key_file = behavior_editor.behavior_key_file
                self.done(QDialog.DialogCode.Accepted)
            else:
                self.done(QDialog.DialogCode.Rejected)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error showing behavior key editor: {str(e)}")
            self.done(QDialog.DialogCode.Rejected)
            
    def on_start_video(self, behavior_key_file):
        """Handle starting the video."""
        self.behavior_key_file = behavior_key_file
        self.start_video_flag = True
        
    def on_cancel(self):
        """Handle cancellation."""
        self.start_video_flag = False
        self.done(QDialog.DialogCode.Rejected)
        
    def center_window(self, window, width, height):
        """Center a window on the primary screen."""
        # Calculate the center position
        x = self.display_x + (self.display_width - width) // 2
        y = self.display_y + (self.display_height - height) // 2
        
        # Set the geometry
        window.setGeometry(x, y, width, height)
        
        # Set a minimum size to prevent the window from being resized too small
        window.setMinimumSize(int(width * 0.8), int(height * 0.8))
        
        # Set preferred size
        window.resize(width, height)
        
        # Make sure the window is not maximized
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMaximized)