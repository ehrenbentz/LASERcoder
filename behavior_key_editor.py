# behavior_key_editor.py

import os
import csv
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QPushButton, QLineEdit, QRadioButton,
    QScrollArea, QFrame, QMessageBox, QComboBox,
    QButtonGroup, QGridLayout, QInputDialog, QApplication,
    QSizePolicy, QScrollBar)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QScreen

class BehaviorKeyEditor(QDialog):
    """Dialog for editing behavior key definitions."""
    
    def __init__(self, parent, behavior_key_dir, on_start_video, on_cancel, config_manager):
        """Initialize the BehaviorKeyEditor"""
        super().__init__(parent)
        
        # Store parameters
        self.behavior_key_dir = behavior_key_dir
        self.on_start_video_callback = on_start_video
        self.on_cancel_callback = on_cancel
        self.config_manager = config_manager
        
        # Initialize state variables
        self.behavior_key_file = None
        self.behaviors = [["", "", "point", ""] for _ in range(30)]  # Changed from 20 to 30
        self.behavior_key_files = {}
        self.new_behavior_dialog_open = False
        self._initializing = False
        self.start_video_flag = False
        
        # Track active dialogs
        self.active_dialogs = []
        
        # Track UI elements
        self.name_entries = []
        self.key_entries = []
        self.type_groups = []
        self.me_group_entries = []
        self.behavior_key_combo = None
        
        # Set window properties
        self.setWindowTitle("Behavior Key Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        
        # Configure display
        self.configure_display()
        
        # Create UI
        self.setup_ui()
        
        # Initialize behavior key
        self.initialize_behavior_key()
        
        # Maximize parent window if it exists
        if parent:
            parent.showMaximized()

    def configure_display(self):
        """Configure display settings and window properties"""
        self.app = QApplication.instance() or QApplication([])
        # Get the primary screen
        self.screen = self.app.primaryScreen()
        self.scaling_factor = self.screen.devicePixelRatio()
        
        # Get available geometry from the primary screen (returns a QRect)
        # This accounts for taskbars and other system UI elements
        geom = self.screen.availableGeometry()
        self.display_width = geom.width()
        self.display_height = geom.height()
        self.display_x = geom.x()
        self.display_y = geom.y()
        
        # Set dimension for the editor window
        self.editor_width = int(self.display_width * 0.5)
        self.editor_height = int(self.display_height * 0.8)

    def setup_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # File selection area
        file_selection = self.create_file_selection_frame()
        main_layout.addWidget(file_selection)
        
        # Column headers
        headers = self.create_column_headers()
        main_layout.addWidget(headers)
        
        # Scrollable behavior entries
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)  # Always show vertical scrollbar
        
        scroll_content = QWidget()
        self.create_behavior_entries(scroll_content)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area, 1)  # Give the scroll area a stretch factor
        
        # Control buttons
        buttons = self.create_control_buttons()
        main_layout.addWidget(buttons)
        
        # Reserved keys note
        note = QLabel("Note: 'w', 'a', 's', 'd' are reserved for video navigation. Do not assign these keys to a behavior.")
        note.setWordWrap(True)
        main_layout.addWidget(note)
        
        # Set an appropriate minimum size to prevent UI issues
        screen = QApplication.instance().primaryScreen()
        avail_geom = screen.availableGeometry()
        min_width = min(600, int(avail_geom.width() * 0.45))
        min_height = min(400, int(avail_geom.height() * 0.5))
        self.setMinimumSize(min_width, min_height)
        
        # Now set the desired size based on screen dimensions
        self.resize(self.editor_width, self.editor_height)
        
        # Center the window properly
        self.center_window(self, self.editor_width, self.editor_height)

    def create_file_selection_frame(self):
        """Create the file selection frame."""
        frame = QWidget()
        layout = QHBoxLayout(frame)
        
        # Set appropriate margins to avoid layout issues
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Label
        label = QLabel("Select Behavior Key File:")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        
        # Combo box
        self.behavior_key_combo = QComboBox()
        self.behavior_key_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.behavior_key_combo.currentTextChanged.connect(self.on_behavior_key_changed)
        layout.addWidget(self.behavior_key_combo, stretch=1)
        
        # New file button
        new_file_btn = QPushButton("New Behavior Key File")
        new_file_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        new_file_btn.clicked.connect(self.new_behavior_key_file)
        layout.addWidget(new_file_btn)
        
        return frame

    def create_column_headers(self):
        """Create the column headers with proper alignment."""
        frame = QWidget()
        layout = QGridLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Fixed widths ensure header and entry alignment
        name_label = QLabel("Name")
        name_label.setStyleSheet("font-weight: bold;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        name_label.setFixedWidth(300)  # Fixed width for Name column
        layout.addWidget(name_label, 0, 0)
        
        key_label = QLabel("Key")
        key_label.setStyleSheet("font-weight: bold;")
        key_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        key_label.setFixedWidth(75)  # Fixed width for Shortcut Key column
        layout.addWidget(key_label, 0, 1)
        
        type_label = QLabel("Type")
        type_label.setStyleSheet("font-weight: bold;")
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(type_label, 0, 2)
        
        me_label = QLabel("ME Group")
        me_label.setStyleSheet("font-weight: bold;")
        me_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        me_label.setFixedWidth(120)  # Fixed width for ME Group column
        layout.addWidget(me_label, 0, 3)
        
        # Allow the Type column to stretch
        layout.setColumnStretch(2, 1)
        
        return frame

    def create_behavior_entries(self, parent):
        """Create the behavior entry rows with improved alignment."""
        layout = QGridLayout(parent)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        for row in range(30):
            # Name entry with fixed width matching header
            name_entry = QLineEdit()
            name_entry.setFixedWidth(300)
            name_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            name_entry.setTextMargins(0, 0, 0, 0)
            layout.addWidget(name_entry, row, 0)
            self.name_entries.append(name_entry)
            
            # Key entry with fixed width matching header
            key_entry = QLineEdit()
            key_entry.setFixedWidth(75)
            key_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(key_entry, row, 1)
            self.key_entries.append(key_entry)
            
            # Type radio buttons in a container widget
            type_widget = QWidget()
            type_layout = QHBoxLayout(type_widget)
            type_layout.setContentsMargins(0, 0, 0, 0)
            type_layout.setSpacing(5)
            type_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            type_group = QButtonGroup()
            point_radio = QRadioButton("Point")
            state_radio = QRadioButton("State")
            type_group.addButton(point_radio)
            type_group.addButton(state_radio)
            point_radio.setChecked(True)
            
            type_layout.addWidget(point_radio)
            type_layout.addWidget(state_radio)
            layout.addWidget(type_widget, row, 2)
            self.type_groups.append(type_group)
            
            # ME Group entry with fixed width matching header
            me_group_entry = QLineEdit()
            me_group_entry.setFixedWidth(120)
            me_group_entry.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(me_group_entry, row, 3)
            self.me_group_entries.append(me_group_entry)
        
        # Allow the Type column to stretch
        layout.setColumnStretch(2, 1)

    def create_control_buttons(self):
        """Create the control buttons."""
        frame = QWidget()
        layout = QHBoxLayout(frame)
        
        # Left-aligned buttons
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_behaviors)
        layout.addWidget(save_btn)
        
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self.rename_behavior_key)
        layout.addWidget(rename_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_behavior_key)
        layout.addWidget(delete_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.on_cancel)
        layout.addWidget(cancel_btn)
        
        # Right-aligned Start Video button
        layout.addStretch()
        start_btn = QPushButton("Start Video")
        start_btn.clicked.connect(self.start_video)
        start_btn.setStyleSheet("font-weight: bold;")
        layout.addWidget(start_btn)
        
        return frame

    def initialize_behavior_key(self):
        """Initialize with last used key or create new one."""
        # Get available behavior files
        behavior_files = self.get_behavior_files()
        
        # Get last used key
        last_key = self.config_manager.get_last_behavior_key()
        
        if last_key and os.path.exists(os.path.join(self.behavior_key_dir, last_key)):
            self.behavior_key_file = os.path.join(self.behavior_key_dir, last_key)
            display_name = last_key.replace('_behaviors.csv', '')
            
            # Update combo box
            self.update_behavior_key_menu()
            self.behavior_key_combo.setCurrentText(display_name)
            
            # Load behaviors
            self.load_behaviors()
            self.update_behavior_entries()
            
        elif behavior_files:
            first_file = behavior_files[0]
            self.behavior_key_file = os.path.join(self.behavior_key_dir, first_file)
            display_name = first_file.replace('_behaviors.csv', '')
            
            # Update combo box
            self.update_behavior_key_menu()
            self.behavior_key_combo.setCurrentText(display_name)
            
            # Load behaviors
            self.load_behaviors()
            self.update_behavior_entries()
            
        else:
            self.new_behavior_key_file()

    def get_behavior_files(self):
        """Get list of behavior files."""
        behavior_files = [f for f in os.listdir(self.behavior_key_dir) 
                        if f.endswith('_behaviors.csv')]
        self.behavior_key_files = {f: os.path.join(self.behavior_key_dir, f) 
                                 for f in behavior_files}
        
        # Move last used key to front if it exists
        last_key = self.config_manager.get_last_behavior_key()
        if last_key and last_key in behavior_files:
            behavior_files.remove(last_key)
            behavior_files.insert(0, last_key)
        
        return behavior_files

    def update_behavior_key_menu(self):
        """Update the combo box with current behavior files."""
        self.behavior_key_combo.clear()
        behavior_files = self.get_behavior_files()
        
        if behavior_files:
            display_files = [f.replace('_behaviors.csv', '') for f in behavior_files]
            self.behavior_key_combo.addItems(display_files)
        else:
            self.behavior_key_combo.addItem("No file found")

    def load_behaviors(self):
        """Load behaviors from file."""
        if os.path.exists(self.behavior_key_file):
            try:
                with open(self.behavior_key_file, 'r') as file:
                    reader = csv.reader(file)
                    self.behaviors = []
                    for row in reader:
                        while len(row) < 4:
                            row.append("")
                        self.behaviors.append(row)
                    while len(self.behaviors) < 30:  # Changed from 20 to 30
                        self.behaviors.append(["", "", "point", ""])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error loading behaviors: {str(e)}")
                self.behaviors = [["", "", "point", ""] for _ in range(30)]  # Changed from 20 to 30
        else:
            self.behaviors = [["", "", "point", ""] for _ in range(30)]  # Changed from 20 to 30
            
    def update_behavior_entries(self):
        """Update UI entries with current behaviors."""
        for i, behavior in enumerate(self.behaviors):
            if i < len(self.name_entries):
                name, key, behavior_type, me_group = behavior + [""] * (4 - len(behavior))
                
                self.name_entries[i].setText(name)
                self.key_entries[i].setText(key)
                
                # Update radio buttons
                radios = self.type_groups[i].buttons()
                if behavior_type == "state":
                    radios[1].setChecked(True)
                else:
                    radios[0].setChecked(True)
                
                self.me_group_entries[i].setText(me_group)

    def new_behavior_key_file(self):
        """Create a new behavior key file."""
        if self.new_behavior_dialog_open:
            return
            
        self.new_behavior_dialog_open = True
        
        dialog = QInputDialog(self)
        dialog.setWindowTitle("New Behavior Key File")
        dialog.setLabelText("Enter a name for the new Behavior Key file:\n(Use only letters, numbers, and underscores)")
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Set dialog position
        self.center_window(dialog, 400, 150)
        
        # Store dialog in active_dialogs list
        self.active_dialogs.append(dialog)
        
        name, ok = dialog.getText(self, dialog.windowTitle(), dialog.labelText())
        
        # Remove dialog from active_dialogs
        if dialog in self.active_dialogs:
            self.active_dialogs.remove(dialog)
        
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "No Name Entered",
                                  "You must enter a name for the Behavior Key file.")
                self.new_behavior_dialog_open = False
                return
                
            if not name.replace('_', '').isalnum():
                QMessageBox.warning(self, "Invalid Characters",
                                  "File name can only contain letters, numbers, and underscores.")
                self.new_behavior_dialog_open = False
                return
                
            new_name = f"{name}_behaviors.csv" if not name.endswith('_behaviors.csv') else name
            self.behavior_key_file = os.path.join(self.behavior_key_dir, new_name)
            
            try:
                with open(self.behavior_key_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    for behavior in [["", "", "point", ""] for _ in range(30)]:  # Changed from 20 to 30
                        writer.writerow(behavior)
                        
                self.behavior_key_files[new_name] = self.behavior_key_file
                self.update_behavior_key_menu()
                self.behavior_key_combo.setCurrentText(name)
                self.load_behaviors()
                self.update_behavior_entries()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error creating file: {str(e)}")
                
        self.new_behavior_dialog_open = False

    def rename_behavior_key(self):
        """Rename the current behavior key file."""
        current_name = self.behavior_key_combo.currentText()
        if not current_name or current_name == "No file found":
            QMessageBox.warning(self, "No Selection",
                              "Please select a Behavior Key file to rename.")
            return
            
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Behavior Key File")
        dialog.setLabelText("Enter new name for the Behavior Key file:\n(Use only letters, numbers, and underscores)")
        dialog.setTextValue(current_name)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Set dialog position
        self.center_window(dialog, 400, 150)
        
        # Store dialog in active_dialogs list
        self.active_dialogs.append(dialog)
        
        new_name, ok = dialog.getText(self, dialog.windowTitle(), dialog.labelText(), text=current_name)
        
        # Remove dialog from active_dialogs
        if dialog in self.active_dialogs:
            self.active_dialogs.remove(dialog)
        
        if ok and new_name:
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "No Name Entered",
                                  "You must enter a name for the Behavior Key file.")
                return
                
            if not new_name.replace('_', '').isalnum():
                QMessageBox.warning(self, "Invalid Characters",
                                  "File name can only contain letters, numbers, and underscores.")
                return
                
            new_filename = f"{new_name}_behaviors.csv"
            old_path = self.behavior_key_file
            new_path = os.path.join(self.behavior_key_dir, new_filename)
            
            if os.path.exists(new_path):
                QMessageBox.warning(self, "File Exists",
                                  "A file with this name already exists.")
                return
                
            try:
                os.rename(old_path, new_path)
                self.behavior_key_file = new_path
                self.update_behavior_key_menu()
                self.behavior_key_combo.setCurrentText(new_name)
                
            except Exception as e:
                QMessageBox.critical(self, "Error",
                                   f"Failed to rename the file: {str(e)}")

    def delete_behavior_key(self):
        """Delete the current behavior key file."""
        current_name = self.behavior_key_combo.currentText()
        if not current_name or current_name == "No file found":
            QMessageBox.warning(self, "No Selection",
                              "Please select a Behavior Key file to delete.")
            return
            
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Confirmation")
        msg_box.setText(f"Are you sure you want to delete '{current_name}'?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Set dialog position
        self.center_window(msg_box, 300, 150)
        
        # Store dialog in active_dialogs list
        self.active_dialogs.append(msg_box)
        
        reply = msg_box.exec()
        
        # Remove dialog from active_dialogs
        if msg_box in self.active_dialogs:
            self.active_dialogs.remove(msg_box)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(self.behavior_key_file)
                
                # Update the display
                behavior_files = self.get_behavior_files()
                if behavior_files:
                    self.update_behavior_key_menu()
                    display_name = behavior_files[0].replace('_behaviors.csv', '')
                    self.behavior_key_combo.setCurrentText(display_name)
                    self.behavior_key_file = os.path.join(self.behavior_key_dir, behavior_files[0])
                    self.load_behaviors()
                    self.update_behavior_entries()
                else:
                    self.behavior_key_combo.clear()
                    self.behavior_key_combo.addItem("No file found")
                    self.new_behavior_key_file()
                    
            except Exception as e:
                QMessageBox.critical(self, "Error",
                                   f"Failed to delete the file: {str(e)}")

    def save_behaviors(self):
        """Save behaviors to file."""
        if not self.behavior_key_file or self.behavior_key_combo.currentText() == "No file found":
            self.new_behavior_key_file()
            return False
            
        try:
            with open(self.behavior_key_file, 'w', newline='') as file:
                writer = csv.writer(file)
                for i in range(30):  # Changed from 20 to 30
                    behavior = [
                        self.name_entries[i].text(),
                        self.key_entries[i].text(),
                        "state" if self.type_groups[i].buttons()[1].isChecked() else "point",
                        self.me_group_entries[i].text()
                    ]
                    writer.writerow(behavior)
                    
            # Update config
            filename = os.path.basename(self.behavior_key_file)
            self.config_manager.update_last_behavior_key(filename)
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Error",
                               f"Error saving behaviors: {str(e)}")
            return False

    def start_video(self):
        """Handle starting the video with proper validation."""
        
        # Check if any behaviors are defined
        if not any(entry.text().strip() for entry in self.name_entries):
            QMessageBox.warning(self, "No Behaviors Defined",
                              "Please add behaviors before starting the video.")
            return
            
        # Save current behaviors
        if not self.save_behaviors():
            return
            
        # Validate shortcut keys
        reserved_keys = {'w', 'a', 's', 'd'}
        assigned_keys = set()
        
        for entry in self.key_entries:
            key = entry.text().strip().lower()
            if key:
                if key in reserved_keys:
                    QMessageBox.warning(
                        self,
                        "Invalid Shortcut Key",
                        f"The key '{key}' is reserved for video navigation.\n"
                        "Please assign a different key."
                    )
                    return
                if key in assigned_keys:
                    QMessageBox.warning(
                        self,
                        "Duplicate Shortcut Key",
                        f"The key '{key}' is assigned to multiple behaviors.\n"
                        "Please assign unique keys."
                    )
                    return
                assigned_keys.add(key)
                
        # Save as last used
        filename = os.path.basename(self.behavior_key_file)
        self.config_manager.update_last_behavior_key(filename)
        
        # All validation passed, set the start_video_flag to True
        self.start_video_flag = True
        
        # Call the callback provided by the parent
        self.on_start_video_callback(self.behavior_key_file)
        
        # Close the dialog
        self.done(QDialog.DialogCode.Accepted)

    def closeEvent(self, event):
        """Handle window close events."""
        # Pass the event on for normal handling
        event.accept()

    def on_behavior_key_changed(self, text):
        """Handle behavior key selection changes."""
        if text and text != "No file found":
            filename = f"{text}_behaviors.csv"
            self.behavior_key_file = os.path.join(self.behavior_key_dir, filename)
            self.load_behaviors()
            self.update_behavior_entries()
            self.config_manager.update_last_behavior_key(filename)

    def on_closing(self):
        """Handle window closing by cleaning up dialogs and calling cancel."""
        # Close any active dialogs
        for dialog in self.active_dialogs[:]:
            try:
                dialog.close()
                self.active_dialogs.remove(dialog)
            except Exception:
                # Dialog might already be closed
                if dialog in self.active_dialogs:
                    self.active_dialogs.remove(dialog)
        
        # Call cancel handler without recursion
        if not self._initializing:  # Prevent recursion during initialization
            self._initializing = True
            try:
                # Check for unsaved changes
                current_behaviors = []
                for i in range(30):  # Changed from 20 to 30
                    behavior = [
                        self.name_entries[i].text(),
                        self.key_entries[i].text(),
                        "state" if self.type_groups[i].buttons()[1].isChecked() else "point",
                        self.me_group_entries[i].text()
                    ]
                    current_behaviors.append(behavior)
                    
                if current_behaviors != self.behaviors:
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Unsaved Changes")
                    msg_box.setText("You have unsaved changes. Do you want to save before closing?")
                    msg_box.setStandardButtons(
                        QMessageBox.StandardButton.Save | 
                        QMessageBox.StandardButton.Discard | 
                        QMessageBox.StandardButton.Cancel
                    )
                    msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
                    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                    
                    # Set dialog position
                    self.center_window(msg_box, 300, 150)
                    
                    # Store dialog in active_dialogs list
                    self.active_dialogs.append(msg_box)
                    
                    reply = msg_box.exec()
                    
                    # Remove dialog from active_dialogs
                    if msg_box in self.active_dialogs:
                        self.active_dialogs.remove(msg_box)
                    
                    if reply == QMessageBox.StandardButton.Save:
                        if self.save_behaviors():
                            self.done(QDialog.DialogCode.Rejected)
                    elif reply == QMessageBox.StandardButton.Discard:
                        self.done(QDialog.DialogCode.Rejected)
                else:
                    self.done(QDialog.DialogCode.Rejected)
            finally:
                self._initializing = False

    def on_cancel(self):
        """Handle cancellation."""
        self.on_closing()

    def setup_window_close(self):
        """Setup window closing behavior and keyboard shortcuts."""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            self.on_closing()
        else:
            super().keyPressEvent(event)

    def center_window(self, window, width, height):
        """Center a window on the primary screen."""
        # Calculate the center position
        x = self.display_x + (self.display_width - width) // 2
        y = self.display_y + (self.display_height - height) // 2
        
        # Set a minimum size first to prevent resizing issues
        window.setMinimumSize(QSize(int(width * 0.8), int(height * 0.8)))
        
        # Now set the geometry based on available screen space
        screen = QApplication.instance().primaryScreen()
        avail_geom = screen.availableGeometry()
        
        # Ensure the window fits within the available screen space
        if width > avail_geom.width():
            width = int(avail_geom.width() * 0.9)
        if height > avail_geom.height():
            height = int(avail_geom.height() * 0.9)
            
        # Ensure window is fully visible on screen
        if x < avail_geom.x():
            x = avail_geom.x()
        if y < avail_geom.y():
            y = avail_geom.y()
        if x + width > avail_geom.x() + avail_geom.width():
            x = avail_geom.x() + avail_geom.width() - width
        if y + height > avail_geom.y() + avail_geom.height():
            y = avail_geom.y() + avail_geom.height() - height
            
        # Set geometry and preferred size
        window.setGeometry(x, y, width, height)
        window.resize(width, height)
        
        # Make sure the window is not maximized
        window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMaximized)