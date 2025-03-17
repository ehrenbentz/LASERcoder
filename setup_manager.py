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
        
        # Keep track of open dialogs
        self.behavior_editor = None
        self.files_manager = None
        
        # Set window properties
        self.setWindowTitle("LaserTAG")
        
        # Handle window close event
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        # Configure display settings
        self.configure_display()
        
        # Start setup process
        self.start_setup()
        
    def configure_display(self):
        """Configure display settings and window properties using available screen geometry."""
        self.app = QApplication.instance() or QApplication([])
        self.screen = self.app.primaryScreen()
        self.scaling_factor = self.screen.devicePixelRatio()
        
        # Use available geometry to account for system elements like taskbars
        geom = self.screen.availableGeometry()
        self.display_width = geom.width()
        self.display_height = geom.height()
        self.display_x = geom.x()
        self.display_y = geom.y()

    def center_window(self, window, width, height):
        """Center a window on the primary screen."""
        # Calculate the center position
        x = self.display_x + (self.display_width - width) // 2
        y = self.display_y + (self.display_height - height) // 2
        
        # Set the geometry
        window.setGeometry(x, y, width, height)
                
        # Set preferred size
        window.resize(width, height)
        
        # Make sure the window is not maximized
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMaximized)

    def closeEvent(self, event):
        """Handle window close event."""
        # Just let the close event proceed normally
        event.accept()
        
    def start_setup(self):
        """Initial setup process to get the output directory and video file."""
        self.show_files_manager()
            
    def show_files_manager(self):
        """Show the files manager dialog and handle its result."""
        try:
            # Make sure any open behavior editor is closed first
            if self.behavior_editor:
                self.behavior_editor.close()
                self.behavior_editor = None
            
            self.files_manager = FilesManager(
                self,
                initial_output_dir=self.config_manager.get_output_dir(),
                initial_video_dir=self.config_manager.get_video_dir()
            )
            
            # Execute the files manager dialog
            files_manager_result = self.files_manager.exec()
            
            if files_manager_result == QDialog.DialogCode.Accepted:
                # Check if files were selected
                if self.files_manager.output_dir and self.files_manager.selected_video_file:
                    # Update configuration with new directories
                    self.config_manager.update_output_dir(self.files_manager.output_dir)
                    self.config_manager.update_video_dir(self.files_manager.selected_video_file)
                    
                    self.output_dir = self.files_manager.output_dir
                    self.video_path = self.files_manager.selected_video_file
                    # Handle multiple dots in filename
                    self.video_name = Path(self.video_path).stem
                    
                    # Clean up the files_manager reference
                    self.files_manager = None
                    
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
        """Create new empty annotation and session state files with error handling."""
        try:
            # Create empty annotation file
            try:
                # First check if we can write to the file location by using a temp file
                temp_annotations_file = self.annotations_file + ".tmp"
                with open(temp_annotations_file, 'w', newline='') as file:
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
                        'Notes'
                    ])
                
                # If successful, replace the actual file
                os.replace(temp_annotations_file, self.annotations_file)
            except (PermissionError, OSError) as e:
                # Clean up temp file if it exists
                if os.path.exists(temp_annotations_file):
                    try:
                        os.remove(temp_annotations_file)
                    except:
                        pass
                
                QMessageBox.critical(self, "Error", 
                                  "Cannot create annotations file.\nIs it open in another application?")
                self.show_files_manager()  # Return to files manager instead of closing
                return False
                
            # Create empty session state file with timestamp in seconds
            try:
                # First check if we can write to the file location by using a temp file
                temp_session_state_file = self.session_state_file + ".tmp"
                with open(temp_session_state_file, 'w') as f:
                    # Use the saved_state if it exists, otherwise create a default state
                    state_data = self.saved_state if self.saved_state else {
                        "timestamp_sec": 0.0,
                        "current_frame": 0,
                        "coding_start": 0.0,
                        "coding_duration": None,
                        "coding_end": None,
                        "coding_end_reached": False
                    }
                    json.dump(state_data, f)
                
                # If successful, replace the actual file
                os.replace(temp_session_state_file, self.session_state_file)
            except (PermissionError, OSError) as e:
                # Clean up temp file if it exists
                if os.path.exists(temp_session_state_file):
                    try:
                        os.remove(temp_session_state_file)
                    except:
                        pass
                
                QMessageBox.critical(self, "Error", 
                                  "Cannot create session state file.\nIs it open in another application?")
                self.show_files_manager()  # Return to files manager instead of closing
                return False
                
            return True
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error creating files: {str(e)}")
            self.show_files_manager()  # Return to files manager instead of closing
            return False
            
    def check_existing_session(self):
        """Check if a previous session exists and handle accordingly with error handling."""
        try:
            # Check if we can access the session state file
            if os.path.exists(self.session_state_file):
                try:
                    with open(self.session_state_file, 'r') as f:
                        self.saved_state = json.load(f)
                        # Convert from milliseconds to seconds if using old format
                        if 'timestamp_ms' in self.saved_state:
                            self.saved_state['timestamp_sec'] = self.saved_state['timestamp_ms'] / 1000.0
                    
                    # Check if we can access the annotations file
                    if os.path.exists(self.annotations_file):
                        try:
                            with open(self.annotations_file, 'r') as f:
                                # Just try to read a bit to verify access
                                f.read(1)
                        except (PermissionError, OSError):
                            QMessageBox.critical(self, "Error", 
                                              "Cannot access annotations file.\nIs it open in another application?")
                            self.show_files_manager()  # Return to files manager instead of closing
                            return
                    
                    self.show_resume_dialog()
                except (PermissionError, OSError):
                    QMessageBox.critical(self, "Error", 
                                      "Cannot access session state file.\nIs it open in another application?")
                    self.show_files_manager()  # Return to files manager instead of closing
                    return
                except json.JSONDecodeError:
                    QMessageBox.warning(self, "Warning", 
                                      "Session state file is corrupted. Starting a new session.")
                    if self.create_empty_files():
                        self.show_behavior_key_editor()
            else:
                self.start_frame = 0
                self.saved_state = None
                if self.create_empty_files():
                    self.show_behavior_key_editor()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error checking existing session: {str(e)}")
            self.show_files_manager()  # Return to files manager instead of closing
            
    def confirm_start_over(self):
        """Show confirmation dialog for starting over with error handling."""
        reply = QMessageBox.question(
            self,
            "Confirm Start Over",
            f"Are you sure?\n\nStarting over will delete all current annotations for\n{self.video_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Try to delete existing files
            files_to_delete = [self.session_state_file, self.annotations_file]
            deletion_failed = False
            
            for file_path in files_to_delete:
                if os.path.exists(file_path):
                    try:
                        # First check if we can write to the file
                        with open(file_path, 'a'):
                            pass
                        
                        # If we can write, try to delete it
                        os.remove(file_path)
                    except (PermissionError, OSError):
                        QMessageBox.warning(self, "Warning", 
                                          f"Cannot delete {os.path.basename(file_path)}.\nIs it open in another application?")
                        deletion_failed = True
                        break
                    except Exception as e:
                        QMessageBox.warning(self, "Warning", f"Error deleting file {file_path}: {str(e)}")
                        deletion_failed = True
                        break
            
            if deletion_failed:
                # Go back to resume dialog if deletion failed
                self.show_resume_dialog()
                return
            
            # Reset state
            self.start_frame = 0
            self.saved_state = {
                "timestamp_sec": 0.0,
                "coding_start": 0.0, 
                "coding_duration": None,
                "coding_end": None,
                "coding_end_reached": False,
                "current_frame": 0
            }
            
            # Create new empty files
            if self.create_empty_files():
                self.show_behavior_key_editor()
        else:
            self.show_resume_dialog()

    def show_resume_dialog(self):
        """Show dialog asking user if they want to resume previous session."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Resume Session")
        dialog.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(dialog)
        
        # Add message
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
        
        layout.addSpacing(20)
        layout.addLayout(button_layout)
        
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        dialog.rejected.connect(lambda: self.handle_resume_choice("cancel", dialog))
        
        dialog.exec()
   
    def handle_resume_choice(self, choice, dialog):
        """Handle the user's choice from the resume dialog."""
        try:
            dialog.rejected.disconnect()
        except:
            pass
        
        dialog.accept()
        
        # Now process the choice
        if choice == "resume":
            self.resume_session()
        elif choice == "start_over":
            self.confirm_start_over()
        else:  # cancel
            self.show_files_manager()

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
            # Clean up any existing behavior editor
            if self.behavior_editor:
                self.behavior_editor.close()
                self.behavior_editor = None
                
            # Create a new behavior editor
            self.behavior_editor = BehaviorKeyEditor(
                self,
                self.behavior_key_dir,
                on_start_video=self.on_start_video,
                on_cancel=self.on_behavior_key_cancel,
                config_manager=self.config_manager
            )
            
            # Execute the dialog
            result = self.behavior_editor.exec()
            
            # Check if the start_video_flag is set - BehaviorKeyEditor will handle its own validation
            if self.behavior_editor and self.behavior_editor.start_video_flag:
                self.start_video_flag = True
                self.behavior_key_file = self.behavior_editor.behavior_key_file
                self.behavior_editor = None  # Clear the reference
                self.done(QDialog.DialogCode.Accepted)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error showing behavior key editor: {str(e)}")
            self.behavior_editor = None  # Clear the reference on error
            self.show_files_manager()  # Return to files manager instead of closing
            
    def on_start_video(self, behavior_key_file):
        """Handle starting the video."""
        self.behavior_key_file = behavior_key_file
        self.start_video_flag = True
        
    def on_cancel(self):
        """Handle cancellation from the main flow."""
        self.start_video_flag = False
        self.done(QDialog.DialogCode.Rejected)
        
    def on_behavior_key_cancel(self):
        """Handle cancellation from the behavior key editor by returning to files manager."""
        # Save the reference to the editor so we can properly close it
        behavior_editor_to_close = self.behavior_editor
        
        # Clear our reference to the editor
        self.behavior_editor = None
        
        # Clear the start_video_flag
        self.start_video_flag = False
        
        # Show the files manager (which will properly close the behavior editor in its setup)
        self.show_files_manager()

    def check_behavior_key_file_access(self, behavior_key_file):
        """
        Check if the behavior key file is accessible.
        
        Args:
            behavior_key_file: Path to the behavior key file
            
        Returns:
            bool: True if file is accessible, False otherwise
        """
        if not os.path.exists(behavior_key_file):
            return False
            
        try:
            # Try to open the file for reading to verify access
            with open(behavior_key_file, 'r') as f:
                f.read(1)  # Just read a bit to verify access
            return True
        except (PermissionError, OSError):
            QMessageBox.critical(self, "Error", 
                              f"Cannot access behavior key file.\nIs it open in another application?")
            return False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error accessing behavior key file: {str(e)}")
            return False

    def keyPressEvent(self, event):
        """Handle key press events in the SetupManager dialog."""
        from PyQt6.QtCore import Qt
        
        # If ESC key is pressed, close the application
        if event.key() == Qt.Key.Key_Escape:
            print("ESC pressed in SetupManager - closing application")
            
            # Reject the dialog 
            self.reject()
            
            # Set start_video_flag to False to signal we're exiting
            self.start_video_flag = False
            
            # Close the parent application directly
            if self.parent():
                # Use QTimer to ensure this happens after event processing
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self.parent().close)
            else:
                # If no parent, use QApplication to exit
                from PyQt6.QtWidgets import QApplication
                QTimer.singleShot(0, QApplication.quit)
        else:
            # For other keys, use default handling
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle window close events (X button)."""
        # Accept the close event for this dialog
        event.accept()
        
        # Close the entire application
        if self.parent():
            self.parent().close()
        else:
            # If no parent, use QApplication to exit
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()