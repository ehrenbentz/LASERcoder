# files_manager.py

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QFrame,
    QMessageBox, QSplitter, QWidget, QInputDialog, QApplication)
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QFont

# Add current directory to PATH for importing modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

class FilesManager(QDialog):
    """Dialog for selecting output directory and video file."""
    
    def __init__(self, parent=None, initial_output_dir=str(Path.home()), 
                 initial_video_dir=str(Path.home()),
                 file_types=(".mp4", ".avi", ".mov", ".mts", ".mkv")):
        super().__init__(parent)
        
        self.file_types = file_types
        self.selected_video_file = None
        
        self.initial_output_dir = os.path.abspath(initial_output_dir)
        self.initial_video_dir = os.path.abspath(initial_video_dir)
        self.current_output_dir = self.initial_output_dir
        self.current_video_dir = self.initial_video_dir
        
        # Set initial output directory selected by default
        self.output_dir = self.initial_output_dir
        
        # Configure display settings
        self.configure_display()
        
        # Set window properties
        self.setWindowTitle("LaserTAG - Select Output Directory and Video File")
        
        # Maximize parent but not this dialog
        if self.parent():
            self.parent().showMaximized()
        
        # Setup UI components
        self.setup_ui()
        
        # Set size and center this dialog
        dialog_width = int(self.display_width * 0.8)
        dialog_height = int(self.display_height * 0.8)
        self.center_window(dialog_width, dialog_height)
        
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

    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QHBoxLayout(self)
        
        # Create splitter for resizable panels
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel: Output Directory Selector
        output_panel = QFrame()
        output_layout = QVBoxLayout(output_panel)
        self.setup_output_panel(output_layout)
        main_splitter.addWidget(output_panel)
        
        # Right panel: Video File Selector
        video_panel = QFrame()
        video_layout = QVBoxLayout(video_panel)
        self.setup_video_panel(video_layout)
        main_splitter.addWidget(video_panel)
        
        # Main splitter - divide into 1/3 for output and 2/3 for video
        width = int(self.display_width * 0.6)  # Total dialog width
        main_splitter.setSizes([int(width/3), int(2*width/3)])

    def setup_video_panel(self, layout):
        """Set up the video file selection panel."""
        # Label
        layout.addWidget(QLabel("Select Video File:"))
        
        # Navigation frame
        nav_frame = QFrame()
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Up button
        up_btn = QPushButton("↑")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(lambda: self.go_up('video'))
        nav_layout.addWidget(up_btn)
        
        # Directory entry
        self.video_dir_entry = QLineEdit(self.initial_video_dir)
        self.video_dir_entry.returnPressed.connect(self.on_video_dir_update)
        nav_layout.addWidget(self.video_dir_entry)
        
        layout.addWidget(nav_frame)
        
        # Create a main container that will take up all available vertical space
        video_container = QWidget()
        layout.addWidget(video_container, 1)  # Add stretch factor to make it fill available space
        
        video_container_layout = QVBoxLayout(video_container)
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a sub-splitter for directories and files
        sub_splitter = QSplitter(Qt.Orientation.Horizontal)
        video_container_layout.addWidget(sub_splitter)
        
        # Left sub-panel: Directories
        dir_panel = QFrame()
        # Remove the box frame shape to eliminate the border
        dir_layout = QVBoxLayout(dir_panel)
        dir_layout.setContentsMargins(5, 5, 5, 5)
        
        dir_layout.addWidget(QLabel("Directories:"))
        self.video_dir_listbox = QListWidget()
        self.video_dir_listbox.itemDoubleClicked.connect(self.on_video_dir_double_click)
        dir_layout.addWidget(self.video_dir_listbox, 1)  # Add stretch factor
        
        # Add empty space at the bottom to match the height with the right panel
        spacer = QWidget()
        spacer.setFixedHeight(30)  # Match the height of the Select Video button
        dir_layout.addWidget(spacer)
        
        sub_splitter.addWidget(dir_panel)
        
        # Right sub-panel: Video files
        file_panel = QFrame()
        # Remove the box frame shape to eliminate the border
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(5, 5, 5, 5)
        
        file_layout.addWidget(QLabel("Video Files:"))
        self.video_file_listbox = QListWidget()
        self.video_file_listbox.itemDoubleClicked.connect(self.select_video_file)
        file_layout.addWidget(self.video_file_listbox, 1)  # Add stretch factor
        
        # Add Select Video button aligned only under the right panel
        select_video_btn = QPushButton("Select Video")
        select_video_btn.setFixedSize(150, 30)
        select_video_btn.clicked.connect(self.select_video_file)
        
        # Create an HBox layout to position the button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()  # This pushes the button to the right
        btn_layout.addWidget(select_video_btn)
        btn_layout.addStretch(0)  # Optional: add a small margin on the right
        
        file_layout.addLayout(btn_layout)
        
        sub_splitter.addWidget(file_panel)
        
        # Set equal sizes for the sub-splitter
        sub_splitter.setSizes([int(sub_splitter.width()/2), int(sub_splitter.width()/2)])
        
        # Populate initial lists
        self.populate_video_dir_list(self.initial_video_dir)
        self.populate_file_list(self.initial_video_dir)

    def setup_output_panel(self, layout):
        """Set up the output directory selection panel."""
        # Label
        layout.addWidget(QLabel("Select Output Directory:"))
        
        # Navigation frame
        nav_frame = QFrame()
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        
        # Up button
        up_btn = QPushButton("↑")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(lambda: self.go_up('output'))
        nav_layout.addWidget(up_btn)
        
        # Directory entry
        self.output_dir_entry = QLineEdit(self.initial_output_dir)
        self.output_dir_entry.returnPressed.connect(self.on_output_dir_update)
        nav_layout.addWidget(self.output_dir_entry)
        
        layout.addWidget(nav_frame)
        
        # Directory list
        self.output_dir_listbox = QListWidget()
        self.output_dir_listbox.itemDoubleClicked.connect(self.on_output_dir_double_click)
        layout.addWidget(self.output_dir_listbox)
        
        # Selected directory label - initialized with the default output directory
        self.dir_selected_label = QLabel(f"Selected Output Directory: {self.output_dir}")
        layout.addWidget(self.dir_selected_label)
        
        # Button frame
        btn_frame = QFrame()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Directory button
        create_dir_btn = QPushButton("Create Directory")
        create_dir_btn.clicked.connect(self.create_directory)
        btn_layout.addWidget(create_dir_btn)
        
        # Delete Directory button
        delete_dir_btn = QPushButton("Delete Directory")
        delete_dir_btn.clicked.connect(self.delete_directory)
        btn_layout.addWidget(delete_dir_btn)
        
        # Select Directory button
        select_dir_btn = QPushButton("Select Directory")
        select_dir_btn.clicked.connect(self.select_directory)
        btn_layout.addWidget(select_dir_btn)
        
        layout.addWidget(btn_frame)
        
        # Summary Statistics button (moved below the other buttons)
        summary_frame = QFrame()
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(0, 5, 0, 0)

        summary_btn = QPushButton("Generate Summary Statistics")
        summary_btn.clicked.connect(self.open_summary_statistics)
        summary_layout.addWidget(summary_btn)

        layout.addWidget(summary_frame)
        
        # Populate initial directory list
        self.populate_dir_list(self.initial_output_dir)

    def go_up(self, panel_type):
        """Navigate up one directory level."""
        if panel_type == 'output':
            parent_dir = os.path.dirname(self.current_output_dir)
            if os.path.exists(parent_dir):
                self.current_output_dir = parent_dir
                self.output_dir_entry.setText(parent_dir)
                self.populate_dir_list(parent_dir)
                if parent_dir != self.output_dir:
                    self.output_dir = None
                    self.dir_selected_label.setText("Selected Output Directory: None")
        else:  # video panel
            parent_dir = os.path.dirname(self.current_video_dir)
            if os.path.exists(parent_dir):
                self.current_video_dir = parent_dir
                self.video_dir_entry.setText(parent_dir)
                self.populate_video_dir_list(parent_dir)
                self.populate_file_list(parent_dir)

    def create_directory(self):
        """Show dialog to create a new directory."""
        dir_name, ok = QInputDialog.getText(
            self,
            "Create Directory",
            "Enter new directory name:",
            QLineEdit.EchoMode.Normal
        )
        
        if ok and dir_name:
            new_dir_path = os.path.join(self.current_output_dir, dir_name)
            try:
                os.makedirs(new_dir_path, exist_ok=True)
                self.current_output_dir = new_dir_path
                self.output_dir_entry.setText(new_dir_path)
                self.populate_dir_list(new_dir_path)
                self.output_dir = new_dir_path  # Automatically select the newly created directory
                self.dir_selected_label.setText(f"Selected Output Directory: {self.output_dir}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {str(e)}")

    def delete_directory(self):
        """Delete the currently selected directory."""
        # Get the selected directory
        current_item = self.output_dir_listbox.currentItem()
        if not current_item:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select a directory to delete."
            )
            return
        
        dir_name = current_item.text()
        dir_path = os.path.join(self.current_output_dir, dir_name)
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete directory '{dir_name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Check if directory is empty
                if os.listdir(dir_path):
                    confirm_non_empty = QMessageBox.question(
                        self,
                        "Non-empty Directory",
                        f"Directory '{dir_name}' is not empty. Delete anyway?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if confirm_non_empty != QMessageBox.StandardButton.Yes:
                        return
                
                # Delete the directory (and all contents if non-empty)
                import shutil
                shutil.rmtree(dir_path)
                
                # Refresh the directory list
                self.populate_dir_list(self.current_output_dir)
                
                QMessageBox.information(
                    self,
                    "Success",
                    f"Directory '{dir_name}' has been deleted."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Could not delete directory: {str(e)}"
                )

    def select_directory(self):
        """Select the current or highlighted directory as output directory."""
        current_item = self.output_dir_listbox.currentItem()
        if current_item:
            # If a directory is highlighted, enter and select it
            dir_name = current_item.text()
            new_dir = os.path.join(self.current_output_dir, dir_name)
            if os.path.isdir(new_dir):
                self.current_output_dir = new_dir
                self.output_dir_entry.setText(new_dir)
                self.populate_dir_list(new_dir)
                self.output_dir = new_dir
        else:
            # If no directory is highlighted, select the current directory
            self.output_dir = self.current_output_dir
            
        # Update the selected directory label
        self.dir_selected_label.setText(f"Selected Output Directory: {self.output_dir}")

    def on_output_dir_update(self):
        """Handle output directory entry updates."""
        new_dir = self.output_dir_entry.text().strip()
        if os.path.isdir(new_dir):
            self.current_output_dir = new_dir
            self.populate_dir_list(new_dir)
            # Keep the selected directory status
            if new_dir != self.output_dir:
                self.output_dir = new_dir
                self.dir_selected_label.setText(f"Selected Output Directory: {self.output_dir}")

    def on_video_dir_update(self):
        """Handle video directory entry updates."""
        new_dir = self.video_dir_entry.text().strip()
        if os.path.isdir(new_dir):
            self.current_video_dir = new_dir
            self.populate_video_dir_list(new_dir)
            self.populate_file_list(new_dir)

    def on_output_dir_double_click(self, item):
        """Handle double-click on output directory list item."""
        dir_name = item.text()
        new_dir = os.path.join(self.current_output_dir, dir_name)
        if os.path.isdir(new_dir):
            self.current_output_dir = new_dir
            self.output_dir_entry.setText(new_dir)
            self.populate_dir_list(new_dir)
            # Update selected directory
            self.output_dir = new_dir
            self.dir_selected_label.setText(f"Selected Output Directory: {self.output_dir}")

    def on_video_dir_double_click(self, item):
        """Handle double-click on video directory list item."""
        dir_name = item.text()
        new_dir = os.path.join(self.current_video_dir, dir_name)
        if os.path.isdir(new_dir):
            self.current_video_dir = new_dir
            self.video_dir_entry.setText(new_dir)
            self.populate_video_dir_list(new_dir)
            self.populate_file_list(new_dir)

    def populate_dir_list(self, directory):
        """Populate the output directory list."""
        self.output_dir_listbox.clear()
        try:
            dirs = [d for d in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]
            dirs.sort()
            self.output_dir_listbox.addItems(dirs)
        except Exception:
            pass

    def populate_video_dir_list(self, directory):
        """Populate the video directory list."""
        self.video_dir_listbox.clear()
        try:
            dirs = [d for d in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]
            dirs.sort()
            self.video_dir_listbox.addItems(dirs)
        except Exception:
            pass

    def populate_file_list(self, directory):
        """Populate the video file list."""
        self.video_file_listbox.clear()
        try:
            items = os.listdir(directory)
            video_files = [f for f in items 
                          if os.path.isfile(os.path.join(directory, f)) 
                          and f.lower().endswith(tuple(ext.lower() for ext in self.file_types))]
            self.video_file_listbox.addItems(sorted(video_files))
        except Exception:
            pass

    def select_video_file(self, item=None):
        """Handle video file selection."""
        current_item = self.video_file_listbox.currentItem()
        if current_item:
            if not self.output_dir:
                msg = QMessageBox.warning(
                    self, 
                    "Warning", 
                    "Please select an output directory first using the 'Select Directory' button."
                )
                return
                
            file_name = current_item.text()
            self.selected_video_file = os.path.join(self.current_video_dir, file_name)
            
            # Simply close the dialog with acceptance
            self.done(QDialog.DialogCode.Accepted)
        else:
            msg = QMessageBox.information(
                self, 
                "Note", 
                "You must select a video file to proceed"
            )

    def center_window(self, width, height):
        """Center the window on the primary screen using Qt6's native functions."""
        # Calculate the center position
        x = self.display_x + (self.display_width - width) // 2
        y = self.display_y + (self.display_height - height) // 2
        
        # Set the geometry
        self.setGeometry(x, y, width, height)
        
        # Set a minimum size to prevent the window from being resized too small
        self.setMinimumSize(int(width * 0.8), int(height * 0.8))
        
        # Set preferred size
        self.resize(width, height)
        
        # Make sure the window is not maximized
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)

    def resizeEvent(self, event):
        """Handle window resize events."""
        super().resizeEvent(event)
        # Ensure lists maintain proper size ratio
        if hasattr(self, 'video_dir_listbox') and hasattr(self, 'video_file_listbox'):
            width = self.video_file_listbox.parentWidget().width()
            self.video_dir_listbox.parentWidget().setMinimumWidth(width)
            self.video_file_listbox.parentWidget().setMinimumWidth(width)

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Return:
            # Handle Enter key for video selection
            if self.video_file_listbox.hasFocus():
                self.select_video_file()
            # Handle Enter key for directory navigation
            elif self.output_dir_listbox.hasFocus():
                self.select_directory()
        elif event.key() == Qt.Key.Key_Escape:
            # Simply close with rejection
            self.done(QDialog.DialogCode.Rejected)
        else:
            # Pass other key events to parent
            super().keyPressEvent(event)

    def open_summary_statistics(self):
        """Open the Summary Statistics Manager dialog."""
        try:
            # Import here to avoid circular imports
            from summary_statistics_manager import SummaryStatisticsManager
            
            # Start with the Annotations directory in the currently selected output directory
            if hasattr(self, 'output_dir') and self.output_dir:
                annotations_dir = os.path.join(self.output_dir, "Annotations")
                if os.path.exists(annotations_dir):
                    start_dir = annotations_dir
                else:
                    start_dir = self.output_dir
            else:
                start_dir = self.current_output_dir
            
            # Create and show the summary statistics manager
            stats_manager = SummaryStatisticsManager(self, start_dir)
            stats_manager.exec()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Summary Statistics Manager: {str(e)}"
            )