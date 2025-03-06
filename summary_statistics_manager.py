# summary_statistics_manager.py

import os
import csv
import pandas as pd
import sys
from pathlib import Path
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QMessageBox, QWidget, QApplication, QListWidget, QFrame,
    QLineEdit, QCheckBox, QInputDialog, QAbstractItemView, QFileDialog,
    QListWidgetItem)
from PyQt6.QtCore import Qt, QSize, QRect
from PyQt6.QtGui import QFont

# Import the summary_statistics module
try:
    # First try to import both functions
    from summary_statistics import generate_summary_statistics, combine_summaries
except ImportError:
    # If combine_summaries doesn't exist yet, just import generate_summary_statistics
    from summary_statistics import generate_summary_statistics
    
    # Define a local function as a fallback
    def combine_summaries(summary_files, output_file):
        """
        Combine multiple summary files into a single summary file.
        This is a fallback implementation if the function is not available in summary_statistics.py
        """
        import pandas as pd
        
        all_data = []
        
        # Read all summary files
        for file_path in summary_files:
            try:
                df = pd.read_csv(file_path)
                all_data.append(df)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        if not all_data:
            print("No valid summary files found")
            return None
        
        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Group by behavior and calculate aggregated statistics
        grouped = combined_df.groupby(['Behavior', 'Type'])
        
        summary_data = []
        for (behavior, btype), group in grouped:
            # Common statistics for all behavior types
            data = {
                'Video': 'Combined',
                'Behavior': behavior,
                'Type': btype,
                'Count': group['Count'].sum(),
                'Average_Count_per_video': group['Count'].mean(),
                'Total_videos': len(group)
            }
            
            # Add type-specific statistics
            if btype == 'State':
                # For state behaviors, we aggregate durations and percentages
                data.update({
                    'Total_Duration_seconds': group['Total_Duration_seconds'].sum(),
                    'Average_Duration_per_video': group['Total_Duration_seconds'].mean(),
                    'Average_Percent_Time': group['Percent_Time'].mean()
                })
            
            # Add frequency data
            data['Average_Frequency_per_minute'] = group['Frequency_per_minute'].mean()
            
            summary_data.append(data)
        
        # Create the combined summary dataframe
        combined_summary = pd.DataFrame(summary_data)
        
        # Sort by type and behavior
        combined_summary = combined_summary.sort_values(by=['Type', 'Behavior'])
        
        # Save the combined summary
        combined_summary.to_csv(output_file, index=False)
        print(f"Combined summary saved to {output_file}")
        
        return output_file

class SummaryStatisticsManager(QDialog):
    """Dialog for managing summary statistics generation."""
    
    def __init__(self, parent=None, initial_dir=str(Path.home())):
        super().__init__(parent)
        
        # Initialize state variables
        self.selected_files = []
        self.initial_dir = os.path.abspath(initial_dir)
        self.current_dir = self.initial_dir
        
        # Set window properties
        self.setWindowTitle("LaserTAG - Generate Summary Statistics")
        
        # Configure display settings
        self.configure_display()
        
        # Setup UI components
        self.setup_ui()
        
        # Set size and center this dialog
        dialog_width = int(self.display_width * 0.4)
        dialog_height = int(self.display_height * 0.7)
        self.center_window(dialog_width, dialog_height)

    def configure_display(self):
        """Configure display settings and window properties"""
        self.app = QApplication.instance() or QApplication([])
        # Get the primary screen
        self.screen = self.app.primaryScreen()
        self.scaling_factor = self.screen.devicePixelRatio()
        
        # Get geometry from the primary screen (returns a QRect)
        geom = self.screen.availableGeometry()
        self.display_width = geom.width()
        self.display_height = geom.height()
        self.display_x = geom.x()
        self.display_y = geom.y()

    def center_window(self, width, height):
        """Center the window on the primary screen using Qt6's native functions."""
        # Calculate the center position
        x = self.display_x + (self.display_width - width) // 2
        y = self.display_y + (self.display_height - height) // 2
        
        # Set the geometry
        self.setGeometry(x, y, width, height)
        
        # Set a minimum size to prevent the window from being resized too small
        self.setMinimumSize(int(width * 0.4), int(height * 0.7))
        
        # Set preferred size
        self.resize(width, height)
        
        # Make sure the window is not maximized
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)
    
    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Directory selection section
        dir_section = self.create_directory_section()
        main_layout.addWidget(dir_section)
        
        # File selection section
        file_section = self.create_file_section()
        main_layout.addWidget(file_section, 1)  # Give this section more vertical space
        
        # Action buttons section
        action_section = self.create_action_section()
        main_layout.addWidget(action_section)
    
    def create_directory_section(self):
        """Create the directory selection section."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        
        # Directory selection header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Select Directory with Annotation Files:"))
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Directory navigation
        nav_layout = QHBoxLayout()
        
        # Up button
        up_btn = QPushButton("↑")
        up_btn.setFixedWidth(30)
        up_btn.clicked.connect(self.go_up)
        nav_layout.addWidget(up_btn)
        
        # Directory entry
        self.dir_entry = QLineEdit(self.initial_dir)
        self.dir_entry.returnPressed.connect(self.on_dir_update)
        nav_layout.addWidget(self.dir_entry)
        
        # Browse button
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_directory)
        nav_layout.addWidget(browse_btn)
        
        layout.addLayout(nav_layout)
        
        # Directory listing
        layout.addWidget(QLabel("Directories:"))
        self.dir_listbox = QListWidget()
        self.dir_listbox.itemDoubleClicked.connect(self.on_dir_double_click)
        layout.addWidget(self.dir_listbox)
        
        # Populate initial directory list
        self.populate_dir_list(self.initial_dir)
        
        return frame
    
    def create_file_section(self):
        """Create the file selection section."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        
        # File selection header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Select Annotation Files:"))
        
        # Select All checkbox
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.setTristate(False)
        self.select_all_checkbox.setChecked(False)  # Make it checked by default
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        header_layout.addWidget(self.select_all_checkbox)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Create a custom list widget for checkable items
        self.file_listbox = QListWidget()
        self.file_listbox.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.file_listbox.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.file_listbox)

        
        # Update the initial file list
        self.populate_file_list(self.initial_dir)
        
        return frame
    
    def create_action_section(self):
        """Create the action buttons section."""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        
        # Generate individual summaries button
        individual_btn = QPushButton("Generate Individual Summaries")
        individual_btn.clicked.connect(self.generate_individual_summaries)
        layout.addWidget(individual_btn)
        
        # Generate combined summary button
        combined_btn = QPushButton("Generate Combined Summary")
        combined_btn.clicked.connect(self.generate_combined_summary)
        layout.addWidget(combined_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        return frame
    
    def go_up(self):
        """Navigate up one directory level."""
        parent_dir = os.path.dirname(self.current_dir)
        if os.path.exists(parent_dir):
            self.current_dir = parent_dir
            self.dir_entry.setText(parent_dir)
            self.populate_dir_list(parent_dir)
            self.populate_file_list(parent_dir)
    
    def browse_directory(self):
        """Open directory browser dialog."""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Directory", 
            self.current_dir
        )
        
        if dir_path:
            self.current_dir = dir_path
            self.dir_entry.setText(dir_path)
            self.populate_dir_list(dir_path)
            self.populate_file_list(dir_path)
    
    def on_dir_update(self):
        """Handle directory entry updates."""
        new_dir = self.dir_entry.text().strip()
        if os.path.isdir(new_dir):
            self.current_dir = new_dir
            self.populate_dir_list(new_dir)
            self.populate_file_list(new_dir)
    
    def on_dir_double_click(self, item):
        """Handle double-click on directory list item."""
        dir_name = item.text()
        new_dir = os.path.join(self.current_dir, dir_name)
        if os.path.isdir(new_dir):
            self.current_dir = new_dir
            self.dir_entry.setText(new_dir)
            self.populate_dir_list(new_dir)
            self.populate_file_list(new_dir)
    
    def populate_dir_list(self, directory):
        """Populate the directory list."""
        self.dir_listbox.clear()
        try:
            dirs = [d for d in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]
            dirs.sort()
            self.dir_listbox.addItems(dirs)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error accessing directory: {str(e)}")
    
    def populate_file_list(self, directory):
        """Populate the file list with annotation files."""
        self.file_listbox.clear()
        try:
            files = [f for f in os.listdir(directory) 
                     if os.path.isfile(os.path.join(directory, f)) and 
                     f.endswith('_Annotations.csv')]
            files.sort()
            
            # Add items as checkable, defaulting to checked
            for file_name in files:
                item = QListWidgetItem(file_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)  # Always check by default
                self.file_listbox.addItem(item)
                
            # Update the select all checkbox to be checked by default
            if files:
                self.select_all_checkbox.setChecked(True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error accessing directory: {str(e)}")
    
    def toggle_select_all(self, state):
        if self.select_all_checkbox.isChecked():
            # Select all
            for i in range(self.file_listbox.count()):
                self.file_listbox.item(i).setCheckState(Qt.CheckState.Checked)
        else:
            # Deselect all
            for i in range(self.file_listbox.count()):
                self.file_listbox.item(i).setCheckState(Qt.CheckState.Unchecked)
    
    def get_selected_files(self):
        """Get list of selected files with full paths."""
        selected_files = []
        for i in range(self.file_listbox.count()):
            item = self.file_listbox.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_files.append(os.path.join(self.current_dir, item.text()))
        return selected_files
    
    def generate_individual_summaries(self):
        """Generate individual summary statistics for selected files."""
        selected_files = self.get_selected_files()
        
        if not selected_files:
            QMessageBox.warning(self, "No Files Selected", "Please select at least one annotation file.")
            return
        
        # Get the base directory (should be the output directory where Annotations is located)
        base_dir = os.path.dirname(os.path.dirname(selected_files[0]))
        summary_dir = self.ensure_summary_dir(base_dir)
        
        if not summary_dir:
            return
            
        # Create ONLY the Individual_summaries subdirectory
        individual_dir = os.path.join(summary_dir, "Individual_summaries")
        try:
            os.makedirs(individual_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create Individual_summaries directory: {str(e)}")
            return
        
        # Process each selected file
        success_count = 0
        failed_files = []
        
        # Process the files without dialogs
        for file_path in selected_files:
            try:
                # Generate summary statistics with custom output path in Individual_summaries directory
                video_name = os.path.basename(file_path).replace("_Annotations.csv", "")
                custom_output = os.path.join(individual_dir, f"{video_name}_Summary.csv")
                output_file = generate_summary_statistics(file_path, custom_output)
                if output_file:
                    success_count += 1
            except Exception as e:
                failed_files.append((os.path.basename(file_path), str(e)))
        
        # Show completion message
        if failed_files:
            error_message = "The following files could not be processed:\n\n"
            for file_name, error in failed_files:
                error_message += f"• {file_name}: {error}\n"
            
            QMessageBox.warning(
                self, 
                "Processing Completed with Errors", 
                f"Successfully generated {success_count} summary files.\n\n{error_message}"
            )
        else:
            QMessageBox.information(
                self, 
                "Processing Complete", 
                f"Successfully generated {success_count} summary files   "
            )

    def generate_combined_summary(self):
        """Generate only a combined summary for all selected files."""
        selected_files = self.get_selected_files()
        
        if not selected_files:
            QMessageBox.warning(self, "No Files Selected", "Please select at least one annotation file.")
            return
        
        # Check if summary files exist for all selected annotation files
        base_dir = os.path.dirname(os.path.dirname(selected_files[0]))
        summary_dir = self.ensure_summary_dir(base_dir)
        
        if not summary_dir:
            return
            
        # Create ONLY the Combined_summaries subdirectory
        combined_dir = os.path.join(summary_dir, "Combined_summaries")
        try:
            os.makedirs(combined_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create Combined_summaries directory: {str(e)}")
            return
            
        # Define the individual summaries directory path (but don't create it)
        individual_dir = os.path.join(summary_dir, "Individual_summaries")
        
        # Prompt user for an experiment name
        experiment_name, ok = QInputDialog.getText(
            self, 
            "Experiment Name", 
            "Enter a name for this experiment/analysis:"
        )
        
        if not ok or not experiment_name:
            return
        
        # Make sure the name doesn't contain characters that are invalid for filenames
        experiment_name = ''.join(c for c in experiment_name if c.isalnum() or c in ' _-')
        
        # Check for existing summary files and create a list of missing ones
        missing_summaries = []
        existing_summaries = []
        
        for file_path in selected_files:
            video_name = os.path.basename(file_path).replace("_Annotations.csv", "")
            # Look for individual summaries in the Individual_summaries directory
            summary_path = os.path.join(individual_dir, f"{video_name}_Summary.csv")
            
            # Also check the old location (for backward compatibility)
            old_summary_path = os.path.join(summary_dir, f"{video_name}_Summary.csv")
            
            if os.path.exists(summary_path):
                existing_summaries.append(summary_path)
            elif os.path.exists(old_summary_path):
                # If found in old location, add it to existing summaries
                existing_summaries.append(old_summary_path)
            else:
                missing_summaries.append((file_path, video_name))
        
        # If there are missing summaries, ask the user if they want to generate them first
        if missing_summaries and existing_summaries:
            missing_names = [name for _, name in missing_summaries]
            response = QMessageBox.question(
                self,
                "Missing Summary Files",
                f"Some summary files don't exist yet. Do you want to generate them first?\n\n"
                f"Missing files: {', '.join(missing_names)}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if response == QMessageBox.StandardButton.Cancel:
                return
            elif response == QMessageBox.StandardButton.Yes:
                QMessageBox.information(
                    self,
                    "Generate Individual Summaries",
                    "Please use the 'Generate Individual Summaries' button first, then try again."
                )
                return
            # If No, continue with only existing summaries
        
        # If no summary files exist at all, inform the user
        if not existing_summaries:
            QMessageBox.information(
                self,
                "No Summary Files",
                "No summary files found. Please use 'Generate Individual Summaries' first."
            )
            return
        
        try:
            # Create the combined annotations file in the Combined_summaries directory
            combined_annotations = self.combine_annotation_files(selected_files, experiment_name, combined_dir)
            
            # Generate the meta-summary from existing individual summaries
            combined_summary_path = os.path.join(combined_dir, f"{experiment_name}_Combined_Summary.csv   ")
            combine_summaries(existing_summaries, combined_summary_path)
            
            # Success message
            QMessageBox.information(
                self, 
                "Combined Analysis", 
                f"Combined Summary:\n{os.path.basename(combined_summary_path)}\n\n"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Error generating combined analysis: {str(e)}"
            )

    def combine_annotation_files(self, file_paths, experiment_name, combined_dir):
        """
        Combine multiple annotation files into one.
        
        Args:
            file_paths: List of paths to annotation files
            experiment_name: Name for the combined file
            combined_dir: Directory to save combined results
            
        Returns:
            Path to the combined annotations file
        """
        # Place the combined file in the Combined_summaries directory
        combined_file_path = os.path.join(combined_dir, f"{experiment_name}_Annotations_Combined.csv")
        
        # Check if file already exists
        if os.path.exists(combined_file_path):
            try:
                # Try to rename the existing file with a timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = combined_file_path.replace(".csv", f"_backup_{timestamp}.csv")
                os.rename(combined_file_path, backup_path)
                print(f"Existing file renamed to {backup_path}")
            except Exception as e:
                print(f"Could not rename existing file: {e}")
                # We'll try to overwrite it
        
        # Read all files into dataframes
        dataframes = []
        failed_files = []
        
        for file_path in file_paths:
            try:
                df = pd.read_csv(file_path)
                
                # Add a check for empty dataframes
                if df.empty:
                    failed_files.append((os.path.basename(file_path), "File is empty"))
                    continue
                    
                # Ensure the dataframe has all required columns
                required_columns = ['Video', 'Name', 'Type']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    # Try to fix common issues
                    if 'Video' not in df.columns:
                        # Add Video column using the filename
                        video_name = os.path.basename(file_path).replace("_Annotations.csv", "")
                        df['Video'] = video_name
                    
                    # If still missing essential columns, skip this file
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        failed_files.append((os.path.basename(file_path), 
                                          f"Missing required columns: {', '.join(missing_columns)}"))
                        continue
                
                dataframes.append(df)
            except Exception as e:
                failed_files.append((os.path.basename(file_path), str(e)))
        
        # Show warning for failed files
        if failed_files:
            warning_message = "The following files could not be processed and will be skipped:\n\n"
            for file_name, reason in failed_files:
                warning_message += f"• {file_name}: {reason}\n"
            
            QMessageBox.warning(
                self,
                "File Processing Warnings",
                warning_message
            )
        
        if not dataframes:
            QMessageBox.critical(self, "Error", "No valid annotation files could be read.")
            return None
        
        # Combine all dataframes
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Save the combined dataframe
        try:
            # First attempt to create a temp file to check if we can write to this location
            temp_file = combined_file_path + ".tmp"
            combined_df.to_csv(temp_file, index=False)
            
            # If successful, replace the original file
            if os.path.exists(temp_file):
                if os.path.exists(combined_file_path):
                    os.remove(combined_file_path)
                os.rename(temp_file, combined_file_path)
            
            return combined_file_path
        except Exception as e:
            # Cleanup temp file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
                    
            QMessageBox.critical(
                self, 
                "Error", 
                f"Error saving combined annotations: {str(e)}"
            )
            return None

    def ensure_summary_dir(self, base_dir):
        """Ensure that only the main Summary directory exists, without subdirectories."""
        summary_dir = os.path.join(base_dir, "Summary")
        try:
            os.makedirs(summary_dir, exist_ok=True)
            return summary_dir
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create Summary directory: {str(e)}")
            return None