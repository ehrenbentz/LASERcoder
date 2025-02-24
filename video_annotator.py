# video_annotator.py

import os
import json
import csv
import mpv
from PyQt6.QtWidgets import (QFrame, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QScrollBar, QMenu, QDialog, QLineEdit, QTextEdit, QMessageBox,
    QAbstractItemView, QFormLayout, QGroupBox, QDialogButtonBox,
    QGridLayout, QApplication, QStackedLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QEvent, QRect
from PyQt6.QtGui import QColor, QPainter, QAction, QScreen

class VideoAnnotator(QFrame):
    """Main video annotator class using PyQt6"""
    
    def __init__(self, parent, video_path, session_state_file, behavior_key_file, output_dir):
        super().__init__(parent)
        
        # Track states
        self.dialog_open = False
        self.pressed_keys = set()
        
        # Store parameters
        self.parent = parent
        self.video_path = video_path
        self.session_state_file = session_state_file
        self.behavior_key_file = behavior_key_file
        self.output_dir = output_dir
        self.floating_windows = []
        
        # Initialize core components
        self.initialize_data_structures()
        self.setup_file_paths()
        self.configure_display()
        self.setup_layout_measurements()
        self.setup_layout()
        self.create_video_frame()
        self.create_controls_toggle_buttons()
        self.initialize_mpv_player()
        self.create_ui_components()
        self.load_data_and_start()
        self.setup_key_bindings()

        self.app.installEventFilter(self)

    def initialize_data_structures(self):
        """Initialize all data structures for annotations and behaviors"""
        self.state_events = []  # State annotation events
        self.point_events = []  # Point annotation events
        self.active_state_behaviors = {}  # Active state keys
        self.behaviors = []  # All behavior definitions
        self.state_behaviors = {}  # key -> name for state behaviors
        self.point_behaviors = {}  # key -> name for point behaviors
        self.me_groups = {}  # key -> ME group (if any)
        self.behavior_map = {}  # key -> {Name, Type}
        self.used_point_behaviors = set()  # For highlighting point behaviors
        self.undo_stack = []  # Stack for undo functionality

    def setup_file_paths(self):
        """Set up all necessary file paths based on the chosen output directory"""
        self.video_name = os.path.basename(self.video_path).split('.')[0]
        self.annotations_dir = os.path.join(self.output_dir, "Annotations")
        self.annotations_file = os.path.join(self.annotations_dir, f'{self.video_name}_Annotations.csv')

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
        
        # Configure window
        self.parent.setWindowTitle(f"LaserTag  {self.video_path}")
        self.parent.showMaximized()
        
        # Set background color
        self.setStyleSheet("background-color: black;")

    def center_window(self, window, width, height):
        """Center a window on the primary monitor"""
        # Get screen center position
        screen_center = self.screen.geometry().center()
        
        # Set window size
        window.resize(width, height)
        
        # Calculate center position
        x = screen_center.x() - (width // 2)
        y = screen_center.y() - (height // 2)
        
        # Set window position
        window.move(x, y)

    def setup_layout_measurements(self):
        self.panel_width = int(self.display_width * 0.2)
        self.panel_height = int(self.display_height) - int(self.display_height * 0.1)
        self.progress_bar_height = int(self.display_height * 0.025)
        self.video_width = int(self.display_width) - int(self.panel_width)
        self.video_height = int(self.panel_height)  
        self.progress_bar_width = int(self.video_width)

        print(f"Monitor height: {self.display_height}")
        print(f"Monitor width: {self.display_width}")
        print(f"Panel Height: {self.panel_height}")
        print(f"Panel Width: {self.panel_width}")
        print(f"Progress Bar Height: {self.progress_bar_height}")
        print(f"Progress Bar Width: {self.progress_bar_width}")
        print(f"Video Height: {self.video_height}")
        print(f"Video Width: {self.video_width}")

    def setup_layout(self):
        """Configure the main layout"""
        # Create main horizontal layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Create left side container for video and progress bar
        self.left_container = QWidget()
        self.left_layout = QVBoxLayout(self.left_container)
        self.left_layout.setSpacing(0)
        self.left_layout.setContentsMargins(0, 0, 0, 0)

        # Add left container to main layout
        self.main_layout.addWidget(self.left_container)

        # Create right side container for annotation panel
        self.right_container = QWidget()
        self.right_container.setFixedWidth(self.panel_width)
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setSpacing(3)
        self.right_layout.setContentsMargins(3, 0, 3, 0)

        # Add right container to main layout
        self.main_layout.addWidget(self.right_container)

    def create_video_frame(self):
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setFixedSize(self.video_width, self.video_height)
        self.left_layout.addWidget(self.video_frame)

    def initialize_mpv_player(self):
        """Initialize the MPV player"""
        # Get the window id from the video frame
        window_id = int(self.video_frame.winId())
        
        # Create an MPV player with the window id
        self.player = mpv.MPV(wid=str(window_id),
                             log_handler=print,
                             hwdec="auto-safe",
                             profile="fast",
                             background_color="000000")
        
        # Start playing the video
        self.player.play(self.video_path)

    def create_ui_components(self):
        """Create and configure UI components"""        
        # Create progress bar
        self.create_progress_bar()
        # Create annotation panel
        self.create_annotation_panel()

    def update_floating_windows_visibility(self):
        """Update visibility of all floating windows"""
        windows = [
            self.behavior_toggle_window,
            self.controls_window
        ]
        
        if hasattr(self, "floating_controls_window") and self.floating_controls_window:
            windows.append(self.floating_controls_window)
        if hasattr(self, "behavior_buttons_window") and self.behavior_buttons_window:
            windows.append(self.behavior_buttons_window)
        
        # Check if main window is minimized
        is_minimized = self.parent.isMinimized()
        
        for window in windows:
            if window and not window.isDestroyed():
                if is_minimized:
                    window.hide()
                else:
                    window.show()

    def create_progress_bar(self):
        """Create a custom progress bar with time labels"""
        # Create a frame to hold the progress bar
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("background-color: black;")
        self.progress_frame.setFixedSize(self.progress_bar_width, self.progress_bar_height)
        
        # Create a single layout for the frame
        frame_layout = QVBoxLayout(self.progress_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        
        # Create a custom widget that handles both progress display and text
        class ProgressBarWithText(QWidget):
            def __init__(self, parent=None, annotator=None):
                super().__init__(parent)
                self.progress = 0.0
                self.left_text = "0m0.00s"
                self.center_text = "(1.0x)"
                self.right_text = "Total Time"
                self.annotator = annotator  # Store reference to VideoAnnotator
                self.setMouseTracking(True)
            
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Draw background
                painter.fillRect(0, 0, self.width(), self.height(), QColor(40, 40, 40))
                
                # Draw progress fill
                if self.progress > 0:
                    progress_width = int(self.width() * self.progress)
                    painter.fillRect(0, 0, progress_width, self.height(), QColor(0, 0, 255))
                
                # Draw text
                painter.setPen(QColor(255, 255, 255))  # White text
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                
                # Calculate text positions
                text_y = self.height() // 2 + 5  # Vertically center text
                
                # Left text (current time)
                painter.drawText(10, text_y, self.left_text)
                
                # Center text (speed)
                center_x = (self.width() - painter.fontMetrics().horizontalAdvance(self.center_text)) // 2
                painter.drawText(center_x, text_y, self.center_text)
                
                # Right text (total time)
                right_x = self.width() - painter.fontMetrics().horizontalAdvance(self.right_text) - 10
                painter.drawText(right_x, text_y, self.right_text)
        
            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton and self.annotator:
                    ratio = event.position().x() / self.width()
                    ratio = max(0.0, min(1.0, ratio))
                    # Call the VideoAnnotator's method directly
                    self.annotator.on_progress_click(ratio)
        
        # Create the custom progress bar with a reference to self (VideoAnnotator)
        self.progress_bar = ProgressBarWithText(self.progress_frame, annotator=self)
        self.progress_bar.setFixedSize(self.progress_bar_width, self.progress_bar_height)
        
        # Add update methods to the VideoAnnotator class
        def update_left_text(self, text):
            self.progress_bar.left_text = text
            self.progress_bar.update()
        
        def update_center_text(self, text):
            self.progress_bar.center_text = text
            self.progress_bar.update()
        
        def update_right_text(self, text):
            self.progress_bar.right_text = text
            self.progress_bar.update()
        
        # Add the progress_update method directly to the progress_bar object
        def set_progress(self, value):
            self.progress = max(0.0, min(1.0, value))
            self.update()
        
        # Attach methods
        import types
        self.update_left_text = types.MethodType(update_left_text, self)
        self.update_center_text = types.MethodType(update_center_text, self)
        self.update_right_text = types.MethodType(update_right_text, self)
        self.progress_bar.setProgress = types.MethodType(set_progress, self.progress_bar)
        
        # Add to layout
        frame_layout.addWidget(self.progress_bar)
        self.left_layout.addWidget(self.progress_frame)

    def update_progress(self):
        """Update progress bar and labels"""
        total_sec = self.player.duration or 0
        current_sec = self.player.time_pos or 0

        if total_sec > 0:
            ratio = current_sec / total_sec
            # Directly update progress bar with the current ratio
            self.progress_bar.setProgress(ratio)
            
            # Update current time label
            current_time_str = self.format_time_human_readable(current_sec)
            self.update_left_text(current_time_str)
            
            # Update playback speed label
            current_speed = self.player.speed
            self.update_center_text(f"({current_speed:.1f}x)")
            
            # Make sure the total time is also displayed
            total_time_str = self.format_time_human_readable(total_sec)
            self.update_right_text(total_time_str)

    def poll_progress_bar(self):
        """Update progress bar periodically and handle video end properly"""
        # Update the progress bar
        self.update_progress()
        
        try:
            total_sec = self.player.duration or 0
            current_sec = self.player.time_pos
            
            # Handle case where time_pos returns None or 0 at high speeds
            if current_sec is None:
                print("Warning: Could not get current time position, using last known position")
                # Schedule next update and return without further processing
                QTimer.singleShot(200, self.poll_progress_bar)
                return
                
            # At high speeds, MPV might return 0.0 when at end of file
            # Check if we're at end of file using player property
            eof_reached = self.player.eof_reached if hasattr(self.player, 'eof_reached') else False
            at_end = (total_sec > 0 and current_sec >= total_sec - 0.5) or eof_reached
            
            if at_end:
                print(f"Video reached end. Position: {current_sec}/{total_sec}, EOF: {eof_reached}")
                
                # Force pause regardless of the specific condition
                self.player.pause = True
                
                try:
                    # Try to position to just before the end for a clean frame
                    last_frame_pos = max(0, total_sec - 0.5)
                    self.player.time_pos = last_frame_pos
                    print(f"Set position to last frame at {last_frame_pos}")
                    
                    # Force a progress update to show the correct position
                    self.update_progress()
                except Exception as e:
                    print(f"Error setting last frame position: {e}")
                    
                    # If positioning fails, try restarting the video as a fallback
                    try:
                        print("Reloading video as fallback")
                        # We're using loadfile with replace to maintain the player instance
                        self.player.command("loadfile", self.video_path, "replace")
                        self.player.pause = True  # Ensure it's paused
                    except Exception as reload_error:
                        print(f"Error reloading video: {reload_error}")
        except Exception as e:
            print(f"Error in progress bar update: {e}")
        
        # Schedule next update
        QTimer.singleShot(200, self.poll_progress_bar)

    def initialize_progress_bar(self):
        """Initialize the progress bar"""
        total_sec = self.player.duration or 0
        if total_sec <= 0:
            # Media not yet loaded; try again in 250ms
            QTimer.singleShot(250, self.initialize_progress_bar)
            return
        
        # Set initial values
        self.update_left_text("0m0.00s")
        self.update_center_text("(1.0x)")
        
        # Set total time
        total_time_str = self.format_time_human_readable(total_sec)
        self.update_right_text(total_time_str)
        
        # Start progress polling
        self.poll_progress_bar()

    def on_progress_click(self, ratio):
        """Handle progress bar clicks with end-of-video handling"""
        total_sec = self.player.duration or 0
        if total_sec > 0:
            target_sec = ratio * total_sec
            
            # Check if clicking near/at the end of the video
            if target_sec >= total_sec - 0.1:
                # Set to just before the end and pause
                self.player.time_pos = total_sec - 0.5
                self.player.pause = True
            else:
                self.player.time_pos = target_sec
            
            # Update progress immediately
            self.update_progress()

    def create_controls_toggle_buttons(self):
        """Create floating control buttons"""
        # Create behavior toggle window
        self.behavior_toggle_window = QWidget(self.parent)
        self.behavior_toggle_window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.behavior_toggle_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create behavior toggle button
        self.behavior_toggle_button = QPushButton("☰", self.behavior_toggle_window)
        self.behavior_toggle_button.setFixedSize(30, 30)
        self.behavior_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: lightgrey;
                border: 1px solid grey;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: grey;
            }
        """)
        self.behavior_toggle_button.clicked.connect(self.toggle_behavior_buttons)
        
        # Create controls window
        self.controls_window = QWidget(self.parent)
        self.controls_window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.controls_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create controls button
        self.controls_button = QPushButton("⚙", self.controls_window)
        self.controls_button.setFixedSize(30, 30)
        self.controls_button.setStyleSheet("""
            QPushButton {
                background-color: lightgrey;
                border: 1px solid grey;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: grey;
            }
        """)
        self.controls_button.clicked.connect(self.toggle_floating_controls)
        
        # Position the windows
        video_pos = self.video_frame.mapToGlobal(QPoint(0, 0))
        margin = 10
        self.behavior_toggle_window.move(video_pos.x() + margin, video_pos.y() + margin)
        self.controls_window.move(video_pos.x() + margin, 
                                video_pos.y() + self.video_height - 40)
        
        # Show the windows
        self.behavior_toggle_window.show()
        self.controls_window.show()
        
        # Add to floating windows list
        self.floating_windows.extend([self.behavior_toggle_window, self.controls_window])

    def toggle_floating_controls(self):
        """Toggle the floating controls panel"""
        if hasattr(self, 'floating_controls_window') and self.floating_controls_window:
            self.floating_controls_window.deleteLater()
            self.floating_controls_window = None
        else:
            self.create_floating_controls()

    def create_floating_controls(self):
        """Create the floating controls panel"""
        # Create floating window
        self.floating_controls_window = QWidget(self.parent)
        self.floating_controls_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.floating_controls_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create main layout
        layout = QHBoxLayout(self.floating_controls_window)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 0, 15, 0)
        
        # Define button style
        button_style = """
            QPushButton {
                background-color: lightgrey;
                color: #202020;
                border: 2px solid grey;
                border-radius: 5px;
                font-size: 12px;
                min-width: 40px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: grey;
                color: white;
            }
            QPushButton:pressed {
                background-color: #404040;
                color: white;
            }
        """
        
        # Create control buttons with appropriate symbols and callbacks
        buttons = [
            ("❮❮", lambda: self.seek_relative(-10000)),
            ("❮", lambda: self.seek_relative(-1000)),
            ("⏪", lambda: self.change_speed(-1)),
            ("■", self.toggle_play_pause),
            ("⏩", lambda: self.change_speed(1)),
            ("❯", lambda: self.seek_relative(1000)),
            ("❯❯", lambda: self.seek_relative(10000))
        ]
        
        for text, callback in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet(button_style)
            btn.clicked.connect(callback)
            if text == "■":
                self.play_pause_btn = btn
            layout.addWidget(btn)
        
        # Position the window
        video_pos = self.video_frame.mapToGlobal(QPoint(0, 0))
        self.floating_controls_window.adjustSize()
        window_width = self.floating_controls_window.width()
        x = video_pos.x() + (self.video_width - window_width) // 2
        y = video_pos.y() + self.video_height - self.floating_controls_window.height() - 10
        self.floating_controls_window.move(x, y)
        
        # Show the window and add to floating windows list
        self.floating_controls_window.show()
        self.floating_windows.append(self.floating_controls_window)

    def toggle_play_pause(self):
        """Toggle play/pause state and update button icon"""
        self.player.pause = not self.player.pause
        self.update_play_pause_icon()

    def update_play_pause_icon(self):
        """Update the play/pause button icon based on current state"""
        if hasattr(self, 'play_pause_btn'):
            self.play_pause_btn.setText("▶" if self.player.pause else "■")

    def toggle_behavior_buttons(self):
        """Toggle the behavior buttons panel"""
        if hasattr(self, "behavior_buttons_window") and self.behavior_buttons_window:
            self.behavior_buttons_window.deleteLater()
            self.behavior_buttons_window = None
        else:
            self.create_behavior_buttons()

    def create_behavior_buttons(self):
        """Create the floating behavior buttons panel"""
        # Create main window
        self.behavior_buttons_window = QWidget(self.parent)
        self.behavior_buttons_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint
        )
        self.behavior_buttons_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Create main layout
        layout = QVBoxLayout(self.behavior_buttons_window)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 5, 0, 5)
        
        # Create frames for point and state behaviors
        point_frame = QWidget()
        point_layout = QHBoxLayout(point_frame)
        point_layout.setSpacing(2)
        point_layout.setContentsMargins(0, 0, 0, 0)
        
        state_frame = QWidget()
        state_layout = QHBoxLayout(state_frame)
        state_layout.setSpacing(2)
        state_layout.setContentsMargins(0, 0, 0, 0)
        
        # Button styles
        point_style = """
            QPushButton {
                background-color: lightgrey;
                color: black;
                border: 1px solid grey;
                border-radius: 3px;
                padding: 5px;
                min-width: 100px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: grey;
                color: white;
            }
            QPushButton:pressed {
                background-color: #404040;
                color: white;
            }
        """
        
        state_style = """
            QPushButton {
                background-color: darkgrey;
                color: black;
                border: 1px solid grey;
                border-radius: 3px;
                padding: 5px;
                min-width: 100px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: grey;
                color: white;
            }
            QPushButton:pressed {
                background-color: #404040;
                color: white;
            }
        """
        
        # Sort behaviors by type
        point_behaviors = []
        state_behaviors = []
        
        for behavior in self.behaviors:
            name, key, btype, _ = behavior
            if not name:
                continue
            if btype.lower() == "point":
                point_behaviors.append((name, key))
            else:
                state_behaviors.append((name, key))
        
        # Create point behavior buttons
        for name, key in point_behaviors:
            btn = QPushButton(name)
            btn.setStyleSheet(point_style)
            # Use lambda with default argument to capture the correct key value
            btn.clicked.connect(lambda checked, k=key: self.add_annotation_for_behavior(k))
            point_layout.addWidget(btn)
        
        # Create state behavior buttons
        for name, key in state_behaviors:
            btn = QPushButton(name)
            btn.setStyleSheet(state_style)
            # Use lambda with default argument to capture the correct key value
            btn.clicked.connect(lambda checked, k=key: self.add_annotation_for_behavior(k))
            state_layout.addWidget(btn)
        
        # Add frames to main layout
        layout.addWidget(point_frame)
        layout.addWidget(state_frame)
        
        # Position the window relative to the toggle button
        video_pos = self.video_frame.mapToGlobal(QPoint(0, 0))
        margin = 10
        toggle_width = self.behavior_toggle_button.width()
        x = video_pos.x() + margin + toggle_width + 10
        y = video_pos.y() + margin
        
        # Show window and set position
        self.behavior_buttons_window.show()
        self.behavior_buttons_window.move(x, y)
        
        # Add to floating windows list
        self.floating_windows.append(self.behavior_buttons_window)

    def add_annotation_for_behavior(self, key):
        """Add an annotation for the given behavior key"""
        key = key.lower()
        if key in self.behavior_map:
            behavior_info = self.behavior_map[key]
            current_time = self.player.time_pos or 0
            formatted_time = self.format_time_human_readable(current_time)
            
            if behavior_info["Type"] == "State":
                self.handle_state_behavior(key, current_time, formatted_time)
            elif behavior_info["Type"] == "Point":
                # Check for duplicate annotations
                if any(evt["Name"] == behavior_info["Name"] and evt["time"] == formatted_time 
                      for evt in self.point_events):
                    return
                
                # Create annotation record
                record = {
                    "Video": self.video_name,
                    "Name": behavior_info["Name"],
                    "Type": "Point",
                    "Mutually_Exclusive": "False",
                    "H_Start": formatted_time,
                    "H_End": "",
                    "Start": f"{current_time:.2f}",
                    "End": "",
                    "Duration": "",
                    "Manual_Edit": "False",
                    "Notes": ""
                }
                
                # Add annotation to records
                self.append_annotation(record)
                self.point_events.append({
                    "Name": behavior_info["Name"],
                    "time": formatted_time,
                    "Manual_Edit": False,
                    "Notes": ""
                })
                
                # Handle highlighting
                self.used_point_behaviors.add(key)
                QTimer.singleShot(100, lambda: self.used_point_behaviors.discard(key))
                
                # Update UI
                self.update_annotations()
                self.populate_behavior_treeviews()

    def add_note_to_annotation(self):
        """Show dialog to add a note to the selected annotation."""
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return
            
        # Determine whether we're dealing with state or point annotation
        if self.selected_treeview == self.state_annotations_tree:
            annotation = self.state_events[self.selected_index]
        else:
            annotation = self.point_events[self.selected_index]
            
        # Create a dialog for entering notes
        self.dialog_open = True
        
        # Create the dialog window
        if hasattr(self, 'note_dialog') and self.note_dialog is not None:
            self.note_dialog.deleteLater()
                
        self.note_dialog = QDialog(self.parent)
        self.note_dialog.setWindowFlags(self.note_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.note_dialog.setWindowTitle("Add Note")
        self.note_dialog.setModal(True)
        self.center_window(self.note_dialog, 400, 300)
        
        # Layout for the dialog
        layout = QVBoxLayout(self.note_dialog)
        
        # Show annotation info
        info_text = f"Adding note to: {annotation['Name']}"
        if self.selected_treeview == self.state_annotations_tree:
            info_text += f" ({self.format_time_human_readable(annotation['start_time'])})"
        else:
            info_text += f" ({annotation['time']})"
        info_label = QLabel(info_text)
        layout.addWidget(info_label)
        
        # Show existing note if any
        existing_note = annotation.get('Notes', "")
        # Convert dots back to newlines for display (if they were previously saved)
        if " . " in existing_note:
            existing_note = existing_note.replace(" . ", "\n")
        
        note_label = QLabel("Note:")
        layout.addWidget(note_label)
        
        # Create a text widget for the note
        self.note_text = QTextEdit()
        self.note_text.setMinimumHeight(150)
        self.note_text.setText(existing_note)
        layout.addWidget(self.note_text)
        
        # Add buttons
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(lambda: self.save_note_to_annotation(annotation))
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.on_note_dialog_close)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addWidget(button_frame)
        
        # Handle dialog closing
        self.note_dialog.finished.connect(self.on_note_dialog_close)
        
        # Show dialog
        self.note_dialog.exec()

    def load_data_and_start(self):
        """Load data and start playback"""
        # Load behaviors and annotations
        self.load_behaviors()
        self.load_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()
        self.initialize_progress_bar()
        self.load_session_state()
        self.auto_save_session_state()

        # Process all geometry configurations before showing the window
        self.parent.update()
        self.parent.show()
        self.parent.activateWindow()
        self.parent.raise_()

    def handle_behavior_key_press(self, key):
        """Handle behavior key press"""
        behavior_info = self.behavior_map[key]
        current_time = self.player.time_pos or 0
        formatted_time = self.format_time_human_readable(current_time)
        
        if behavior_info["Type"] == "State":
            self.handle_state_behavior(key, current_time, formatted_time)
        elif behavior_info["Type"] == "Point":
            # Check for duplicates
            if any(evt["Name"] == behavior_info["Name"] and evt["time"] == formatted_time 
                   for evt in self.point_events):
                return
                
            # Create point annotation
            record = {
                "Video": self.video_name,
                "Name": behavior_info["Name"],
                "Type": "Point",
                "Mutually_Exclusive": "False",
                "H_Start": formatted_time,
                "H_End": "",
                "Start": f"{current_time:.2f}",
                "End": "",
                "Duration": "",
                "Manual_Edit": "False",
                "Notes": ""
            }
            
            # Add to records
            self.append_annotation(record)
            self.point_events.append({
                "Name": behavior_info["Name"],
                "time": formatted_time,
                "Manual_Edit": False,
                "Notes": ""
            })
            
            # Handle highlighting
            self.used_point_behaviors.add(key)
            QTimer.singleShot(100, lambda: self.used_point_behaviors.discard(key))
            
            # Update UI
            self.update_annotations()
            self.populate_behavior_treeviews()

    def setup_key_bindings(self):
        """Set up all key bindings with dialog blocking"""
        # Install event filter on parent window to catch key events
        self.parent.installEventFilter(self)
        
        # Define key handler decorator
        def create_blocked_handler(handler):
            """Create a handler that only executes if no dialog is open"""
            def blocked_handler(*args, **kwargs):
                if not self.dialog_open:
                    return handler(*args, **kwargs)
            return blocked_handler

        # Store key bindings for reference - use the same functions as the buttons
        self.key_bindings = {
            # Toggle play/pause
            Qt.Key.Key_Space: create_blocked_handler(self.toggle_play_pause),

            # Small skip forward/backward
            Qt.Key.Key_Right | Qt.KeyboardModifier.ShiftModifier: create_blocked_handler(lambda: self.seek_relative(1000)),
            Qt.Key.Key_Left | Qt.KeyboardModifier.ShiftModifier: create_blocked_handler(lambda: self.seek_relative(-1000)),
            Qt.Key.Key_D | Qt.KeyboardModifier.ShiftModifier: create_blocked_handler(lambda: self.seek_relative(1000)),
            Qt.Key.Key_A | Qt.KeyboardModifier.ShiftModifier: create_blocked_handler(lambda: self.seek_relative(-1000)),

            # Medium skip
            Qt.Key.Key_Right: create_blocked_handler(lambda: self.seek_relative(5000)),
            Qt.Key.Key_Left: create_blocked_handler(lambda: self.seek_relative(-5000)),
            Qt.Key.Key_D: create_blocked_handler(lambda: self.seek_relative(5000)),
            Qt.Key.Key_A: create_blocked_handler(lambda: self.seek_relative(-5000)),

            # Large skip
            Qt.Key.Key_W: create_blocked_handler(lambda: self.seek_relative(10000)),
            Qt.Key.Key_S: create_blocked_handler(lambda: self.seek_relative(-10000)),

            # Speed control - use the same function as the speed buttons
            Qt.Key.Key_Equal: create_blocked_handler(lambda: self.change_speed(1)),
            Qt.Key.Key_Plus: create_blocked_handler(lambda: self.change_speed(1)),
            Qt.Key.Key_Minus: create_blocked_handler(lambda: self.change_speed(-1)),
            Qt.Key.Key_Underscore: create_blocked_handler(lambda: self.change_speed(-1)),

            # Reset speed to 1x with Backspace
            Qt.Key.Key_Backspace: create_blocked_handler(self.reset_speed),

            # Other controls
            Qt.Key.Key_Escape: self.return_to_file_selection,  # Modified to use new method instead of on_closing
            Qt.Key.Key_Delete: create_blocked_handler(self.delete_annotation),
        }

        # Add Control+Z for undo
        self.key_bindings[Qt.Key.Key_Z | Qt.KeyboardModifier.ControlModifier] = create_blocked_handler(self.undo_delete)

    def eventFilter(self, obj, event):
        """Handle key events"""
        if event.type() == QEvent.Type.KeyPress:
            # Handle special keys defined in key_bindings
            key = event.key()
            modifiers = event.modifiers()
            combined_key = key | modifiers.value

            # Escape key should work even if no dialog is open
            if key == Qt.Key.Key_Escape and not self.dialog_open:
                self.return_to_file_selection()
                return True  # Event handled
                
            # Only process if no dialog is open
            if not self.dialog_open:
                # Check if this is a special key combination
                if combined_key in self.key_bindings:
                    self.key_bindings[combined_key]()
                    return True  # Event handled

        elif event.type() == QEvent.Type.KeyRelease:
            char = event.text().lower()
            if char:
                self.pressed_keys.discard(char)
                return True  # Event handled

        # Pass other events to the parent class
        return super().eventFilter(obj, event)

    def handle_point_behavior(self, key, current_time, formatted_time):
        """Handle point behavior key press"""
        behavior_info = self.behavior_map[key]
        
        # Create point annotation record
        record = {
            "Video": self.video_name,
            "Name": behavior_info["Name"],
            "Type": "Point",
            "Mutually_Exclusive": "False",
            "H_Start": formatted_time,
            "H_End": "",
            "Start": f"{current_time:.2f}",
            "End": "",
            "Duration": "",
            "Manual_Edit": "False",
            "Notes": ""
        }
        
        # Add to records
        self.append_annotation(record)
        self.point_events.append({
            "Name": behavior_info["Name"],
            "time": formatted_time,
            "Manual_Edit": False,
            "Notes": ""
        })
        
        # Handle highlighting
        self.used_point_behaviors.add(key)
        QTimer.singleShot(100, lambda: self.used_point_behaviors.discard(key))
        
        # Update UI
        self.update_annotations()
        self.populate_behavior_treeviews()

    def on_key_release(self, event):
        """Handle key release events by removing the key from pressed_keys"""
        key = event.char.lower()
        self.pressed_keys.discard(key)

    def save_session_state(self):
        """Save the current video position to the session state file."""
        try:
            # Get current position before doing anything else
            current_time = self.player.time_pos
            if current_time is None:
                print("Warning: Could not get current time position")
                return
                
            # Ensure we have a valid timestamp
            current_time = float(current_time)
            if current_time <= 0:
                print("Warning: Invalid timestamp value:", current_time)
                return
                
            resume_dir = os.path.join(self.output_dir, "Resume")
            file_path = os.path.join(resume_dir, f"{self.video_name}_session_state.json")
            
            # Create session state data
            session_state = {"timestamp_sec": current_time}
            
            # Save to file
            with open(file_path, "w") as f:
                json.dump(session_state, f)
            print(f"Successfully saved session state: {current_time:.3f} seconds")
            
        except Exception as e:
            print(f"Error saving session state: {e}")

    def schedule_resume(self, timestamp_sec):
        """Schedule resume of video playback"""
        if (self.player.duration or 0) > 0:
            self.player.time_pos = timestamp_sec
            print(f"Resumed session state at {timestamp_sec:.2f} sec.")
        else:
            # Use QTimer instead of after()
            QTimer.singleShot(200, lambda: self.schedule_resume(timestamp_sec))

    def load_session_state(self):
        resume_dir = os.path.join(self.output_dir, "Resume")
        file_path = os.path.join(resume_dir, f"{self.video_name}_session_state.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                session_state = json.load(f)
                # Support both old (ms) and new (sec) format
                if 'timestamp_ms' in session_state:
                    timestamp_sec = session_state.get("timestamp_ms", 0) / 1000.0
                else:
                    timestamp_sec = session_state.get("timestamp_sec", 0)
                self.schedule_resume(timestamp_sec)
        else:
            print("No session state found.")

    def auto_save_session_state(self):
        self.save_session_state()
        # Changed from self.after to QTimer
        QTimer.singleShot(5000, self.auto_save_session_state)

    def create_annotation_panel(self):
            """Create and configure the annotation panel with scrollable trees and proper sizing"""
            print(f"Annotation Panel Width: {self.panel_width}")
            
            # Define font sizes for easy adjustment
            tree_font = "12px"
            heading_font = "12px"
            
            # Calculate heights
            available_height = self.panel_height - self.progress_bar_height
            pane_height = (available_height - 15) // 4  # Reduced padding space to fit more content
            
            # Create border frame with improved styling
            self.annotation_frame = QFrame(self)
            self.annotation_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
            self.annotation_frame.setStyleSheet("""
                QFrame {
                    background-color: #2b2b2b;
                    border: 1px solid #3a3a3a;
                    border-radius: 4px;
                }
            """)
            
            # Add annotation frame to right container
            self.right_layout.addWidget(self.annotation_frame)
            
            # Create main layout for annotation panel
            main_layout = QVBoxLayout(self.annotation_frame)
            main_layout.setContentsMargins(3, 3, 3, 3)
            main_layout.setSpacing(3)
            
            # Common styles
            tree_style = """
                QTreeWidget {
                    background-color: #333333;
                    border: 1px solid #444444;
                    border-radius: 4px;
                    color: #ffffff;
                    font-size: """ + tree_font + """;
                }
                QTreeWidget::item {
                    height: 18px;
                    padding: 0px;
                    margin: 0px;
                    font-size: """ + tree_font + """;
                }
                QTreeWidget::item:selected {
                    background-color: #0078D7;
                    color: white;
                }
                QTreeWidget::item:hover {
                    background-color: #404040;
                }
                QHeaderView::section {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: """ + heading_font + """;
                    padding: 2px;
                    border: none;
                    border-bottom: 1px solid #444444;
                }
                QScrollBar:vertical {
                    border: none;
                    background: #2b2b2b;
                    width: 10px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #666666;
                    min-height: 20px;
                    border-radius: 5px;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """
            
            label_style = "color: white; font-weight: bold; font-size: " + heading_font + ";"
            
            button_style = """
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: """ + heading_font + """;
                }
                QPushButton:hover {
                    background-color: #1084D9;
                }
                QPushButton:pressed {
                    background-color: #006CC1;
                }
            """
            
            # ------------------- State Behaviors Pane -------------------
            state_frame = QFrame()
            state_frame.setFixedHeight(pane_height)
            state_layout = QVBoxLayout(state_frame)
            state_layout.setContentsMargins(0, 0, 0, 0)
            state_layout.setSpacing(1)
            
            state_label = QLabel("State Behaviors")
            state_label.setStyleSheet(label_style)
            state_layout.addWidget(state_label)
            
            self.state_behaviors_tree = QTreeWidget()
            self.state_behaviors_tree.setStyleSheet(tree_style)
            self.state_behaviors_tree.setHeaderLabels(["Name", "Key", "ME Group"])
            self.state_behaviors_tree.setColumnWidth(0, int(self.panel_width * 0.5))
            self.state_behaviors_tree.setColumnWidth(1, int(self.panel_width * 0.15))
            self.state_behaviors_tree.setColumnWidth(2, int(self.panel_width * 0.25))
            self.state_behaviors_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.state_behaviors_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            state_layout.addWidget(self.state_behaviors_tree)
            
            main_layout.addWidget(state_frame)
            
            # ------------------- Point Behaviors Pane -------------------
            point_frame = QFrame()
            point_frame.setFixedHeight(pane_height)
            point_layout = QVBoxLayout(point_frame)
            point_layout.setContentsMargins(0, 0, 0, 0)
            point_layout.setSpacing(1)
            
            point_label = QLabel("Point Behaviors")
            point_label.setStyleSheet(label_style)
            point_layout.addWidget(point_label)
            
            self.point_behaviors_tree = QTreeWidget()
            self.point_behaviors_tree.setStyleSheet(tree_style)
            self.point_behaviors_tree.setHeaderLabels(["Name", "Key"])
            self.point_behaviors_tree.setColumnWidth(0, int(self.panel_width * 0.6))
            self.point_behaviors_tree.setColumnWidth(1, int(self.panel_width * 0.3))
            self.point_behaviors_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.point_behaviors_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            point_layout.addWidget(self.point_behaviors_tree)
            
            main_layout.addWidget(point_frame)
            
            # ------------------- State Annotations Pane -------------------
            state_anno_frame = QFrame()
            state_anno_frame.setFixedHeight(pane_height)
            state_anno_layout = QVBoxLayout(state_anno_frame)
            state_anno_layout.setContentsMargins(0, 0, 0, 0)
            state_anno_layout.setSpacing(1)
            
            # Header with label and sort button
            state_anno_header = QWidget()
            header_layout = QHBoxLayout(state_anno_header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(3)
            
            state_anno_label = QLabel("State Annotations")
            state_anno_label.setStyleSheet(label_style)
            header_layout.addWidget(state_anno_label)
            
            state_sort_button = QPushButton("Sort")
            state_sort_button.setStyleSheet(button_style)
            state_sort_button.setFixedWidth(50)
            state_sort_button.setFixedHeight(22)
            state_sort_button.clicked.connect(self.sort_state_annotations)
            header_layout.addStretch()
            header_layout.addWidget(state_sort_button)
            
            state_anno_layout.addWidget(state_anno_header)
            
            self.state_annotations_tree = QTreeWidget()
            self.state_annotations_tree.setStyleSheet(tree_style)
            self.state_annotations_tree.setHeaderLabels(["Name", "Start", "End"])
            self.state_annotations_tree.setColumnWidth(0, int(self.panel_width * 0.33))
            self.state_annotations_tree.setColumnWidth(1, int(self.panel_width * 0.25))
            self.state_annotations_tree.setColumnWidth(2, int(self.panel_width * 0.25))
            self.state_annotations_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.state_annotations_tree.customContextMenuRequested.connect(self.show_annotation_menu)
            self.state_annotations_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.state_annotations_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            state_anno_layout.addWidget(self.state_annotations_tree)
            
            main_layout.addWidget(state_anno_frame)
            
            # ------------------- Point Annotations Pane -------------------
            point_anno_frame = QFrame()
            point_anno_frame.setFixedHeight(pane_height)
            point_anno_layout = QVBoxLayout(point_anno_frame)
            point_anno_layout.setContentsMargins(0, 0, 0, 0)
            point_anno_layout.setSpacing(1)
            
            # Header with label and sort button
            point_anno_header = QWidget()
            header_layout = QHBoxLayout(point_anno_header)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(8)
            
            point_anno_label = QLabel("Point Annotations")
            point_anno_label.setStyleSheet(label_style)
            header_layout.addWidget(point_anno_label)
            
            point_sort_button = QPushButton("Sort")
            point_sort_button.setStyleSheet(button_style)
            point_sort_button.setFixedWidth(50)
            point_sort_button.setFixedHeight(22)
            point_sort_button.clicked.connect(self.sort_point_annotations)
            header_layout.addStretch()
            header_layout.addWidget(point_sort_button)
            
            point_anno_layout.addWidget(point_anno_header)
            
            self.point_annotations_tree = QTreeWidget()
            self.point_annotations_tree.setStyleSheet(tree_style)
            self.point_annotations_tree.setHeaderLabels(["Name", "Time"])
            self.point_annotations_tree.setColumnWidth(0, int(self.panel_width * 0.4))
            self.point_annotations_tree.setColumnWidth(1, int(self.panel_width * 0.5))
            self.point_annotations_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.point_annotations_tree.customContextMenuRequested.connect(self.show_annotation_menu)
            self.point_annotations_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.point_annotations_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            point_anno_layout.addWidget(self.point_annotations_tree)
            
            main_layout.addWidget(point_anno_frame)
            
            # ------------------- Bottom Buttons -------------------
            buttons_frame = QFrame()
            buttons_layout = QHBoxLayout(buttons_frame)
            buttons_layout.setContentsMargins(0, 3, 0, 0)
            buttons_layout.setSpacing(6)
            
            button_size_policy = """
                QPushButton {
                    background-color: #0078D7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px;
                    min-width: 100px;
                    min-height: 40px;
                    font-size: """ + heading_font + """;
                }
                QPushButton:hover {
                    background-color: #1084D9;
                }
                QPushButton:pressed {
                    background-color: #006CC1;
                }
            """
            
            visualize_button = QPushButton("Visualize\nAnnotations")
            visualize_button.setStyleSheet(button_size_policy)
            visualize_button.clicked.connect(self.visualize_annotations)
            buttons_layout.addWidget(visualize_button)
            
            summary_button = QPushButton("Summary\nStatistics")
            summary_button.setStyleSheet(button_size_policy)
            summary_button.clicked.connect(self.generate_summary_statistics)
            buttons_layout.addWidget(summary_button)
            
            main_layout.addWidget(buttons_frame)

    def load_behaviors(self):
        """Load behaviors from CSV file"""
        print(f"Loading behaviors from: {self.behavior_key_file}")
        with open(self.behavior_key_file, "r", newline="") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if not row or len(row) < 3:
                    continue
                name = row[0].strip()
                key = row[1].strip().lower()
                btype = row[2].strip().lower()  # Expected 'state' or 'point'
                me_group = row[3].strip() if len(row) > 3 else ""

                if btype == "state":
                    self.state_behaviors[key] = name
                    if me_group:
                        self.me_groups[key] = me_group
                elif btype == "point":
                    self.point_behaviors[key] = name

                self.behavior_map[key] = {"Name": name, "Type": btype.capitalize()}
                self.behaviors.append((name, key, btype, me_group))

    def load_annotations(self):
        """Read annotations from CSV file and load into memory"""
        # Clear existing events
        self.state_events.clear()
        self.point_events.clear()

        print(f"Loading annotations from: {self.annotations_file}")

        with open(self.annotations_file, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                annotation_type = row.get("Type", "").strip().lower()
                name = row.get("Name", "").strip()
                notes = row.get("Notes", "")

                if annotation_type == "state":
                    # Handle missing or 'NA' values safely
                    start = row.get("Start", "").strip()
                    end = row.get("End", "").strip()

                    start_time = float(start) if start and start != "NA" else None
                    end_time = float(end) if end and end != "NA" else None

                    self.state_events.append({
                        'Name': name,
                        'start_time': start_time,
                        'end_time': end_time,
                        'Type': 'State',
                        'Mutually_Exclusive': row.get("Mutually_Exclusive", "False"),
                        'Notes': notes
                    })

                elif annotation_type == "point":
                    h_start = row.get("H_Start", "").strip()
                    self.point_events.append({
                        'Name': name,
                        'time': h_start,
                        'Manual_Edit': row.get("Manual_Edit", "False"),
                        'Notes': notes
                    })

    def update_annotations(self):
        """Update annotation treeviews with current data"""
        # Update State Annotations
        self.state_annotations_tree.clear()
        for event in self.state_events:
            name = event['Name']
            start_time = self.format_time_human_readable(event['start_time'])
            end_time = self.format_time_human_readable(event['end_time']) if event['end_time'] else ""
            item = QTreeWidgetItem([name, start_time, end_time])
            self.state_annotations_tree.addTopLevelItem(item)
        
        # Scroll to last item if exists
        if self.state_annotations_tree.topLevelItemCount() > 0:
            last_item = self.state_annotations_tree.topLevelItem(
                self.state_annotations_tree.topLevelItemCount() - 1
            )
            self.state_annotations_tree.scrollToItem(
                last_item, QAbstractItemView.ScrollHint.EnsureVisible
            )

        # Update Point Annotations
        self.point_annotations_tree.clear()
        for event in self.point_events:
            name = event['Name']
            time_ = event['time']
            item = QTreeWidgetItem([name, time_])
            self.point_annotations_tree.addTopLevelItem(item)
        
        # Scroll to last item if exists
        if self.point_annotations_tree.topLevelItemCount() > 0:
            last_item = self.point_annotations_tree.topLevelItem(
                self.point_annotations_tree.topLevelItemCount() - 1
            )
            self.point_annotations_tree.scrollToItem(
                last_item, QAbstractItemView.ScrollHint.EnsureVisible
            )

    def populate_behavior_treeviews(self):
        """Populate behavior treeviews with current data"""
        # Clear existing entries
        self.state_behaviors_tree.clear()
        self.point_behaviors_tree.clear()

        # Define highlight colors
        active_color = QColor("darkorange")
        highlight_color = QColor("dodgerblue")

        # Insert state behaviors
        for behavior in self.behaviors:
            name, key, b_type, me_group = behavior
            if b_type == "state":
                item = QTreeWidgetItem([name, key, me_group])
                if key in self.active_state_behaviors:
                    for col in range(item.columnCount()):
                        item.setBackground(col, active_color)
                self.state_behaviors_tree.addTopLevelItem(item)

        # Insert point behaviors
        for behavior in self.behaviors:
            name, key, b_type, _ = behavior
            if b_type == "point":
                item = QTreeWidgetItem([name, key])
                if key in self.used_point_behaviors:
                    for col in range(item.columnCount()):
                        item.setBackground(col, highlight_color)
                    # Remove highlight after 250ms
                    QTimer.singleShot(250, lambda i=item: self.remove_highlight(i))
                self.point_behaviors_tree.addTopLevelItem(item)

    def remove_highlight(self, item):
        """Remove highlight from a tree item"""
        # Check if item still exists in tree
        if item in [self.point_behaviors_tree.topLevelItem(i) 
                   for i in range(self.point_behaviors_tree.topLevelItemCount())]:
            for col in range(item.columnCount()):
                item.setBackground(col, QColor("transparent"))

    def handle_key_press(self, event):
        """Handle key press events from Qt"""
        # Block key presses if a dialog is open
        if self.dialog_open:
            return
            
        # Get the key text and convert to lowercase
        key = event.text().lower()
        if not key:
            return
            
        # If key is already pressed, ignore this press
        if key in self.pressed_keys:
            return
            
        # Add key to pressed keys set
        self.pressed_keys.add(key)
            
        if key in self.behavior_map:
            behavior_info = self.behavior_map[key]
            current_time = self.player.time_pos or 0
            formatted_time = self.format_time_human_readable(current_time)
            
            if behavior_info["Type"] == "State":
                self.handle_state_behavior(key, current_time, formatted_time)
            elif behavior_info["Type"] == "Point":
                self.handle_point_behavior(key, current_time, formatted_time)

    def handle_point_behavior(self, key, current_time, formatted_time):
        """Handle point behavior key press"""
        behavior_info = self.behavior_map[key]
        
        # Prevent duplicate annotations
        if any(evt["Name"] == behavior_info["Name"] and evt["time"] == formatted_time 
               for evt in self.point_events):
            return
            
        # Create annotation record
        record = {
            "Video": self.video_name,
            "Name": behavior_info["Name"],
            "Type": "Point",
            "Mutually_Exclusive": "False",
            "H_Start": formatted_time,
            "H_End": "",
            "Start": f"{current_time:.2f}",
            "End": "",
            "Duration": "",
            "Manual_Edit": "False",
            "Notes": ""
        }
        
        # Add annotation to records
        self.append_annotation(record)
        self.point_events.append({
            "Name": behavior_info["Name"],
            "time": formatted_time,
            "Manual_Edit": False,
            "Notes": ""
        })
        
        # Handle highlighting
        self.used_point_behaviors.add(key)
        QTimer.singleShot(100, lambda: self.used_point_behaviors.discard(key))
        
        # Update UI
        self.update_annotations()
        self.populate_behavior_treeviews()

    def handle_state_behavior(self, key, frame_timestamp, formatted_timestamp):
        """Handle state behavior key press"""
        Name = self.state_behaviors.get(key)
        me_group = self.me_groups.get(key, None)
        
        # Handle mutually exclusive group
        if me_group:
            print(f"Key {key} belongs to ME Group {me_group}. Deactivating other behaviors in this group.")
            self.deactivate_me_group(me_group, frame_timestamp, current_behavior_key=key)
        
        if key in self.active_state_behaviors:
            # End the active state behavior
            start_time = self.active_state_behaviors.pop(key)
            duration = frame_timestamp - start_time
            
            # Format timestamps
            human_readable_start_time = self.format_time_human_readable(start_time)
            human_readable_end_time = self.format_time_human_readable(frame_timestamp)
            machine_readable_start_time = self.format_time_machine_readable(start_time)
            machine_readable_end_time = self.format_time_machine_readable(frame_timestamp)
            machine_readable_duration = self.format_time_machine_readable(duration)
            
            # Create record
            record = {
                "Video": self.video_name,
                "Name": Name,
                "Type": "State",
                "Mutually_Exclusive": "True" if me_group else "False",
                "H_Start": human_readable_start_time,
                "H_End": human_readable_end_time,
                "Start": machine_readable_start_time,
                "End": machine_readable_end_time,
                "Duration": machine_readable_duration,
                "Manual_Edit": "False",
                "Notes": ""
            }
            
            # Save record
            self.append_annotation(record)
            
            # Update state events
            for event in self.state_events:
                if event['Name'] == Name and event['end_time'] is None:
                    event['end_time'] = frame_timestamp
                    break
                    
            # Update UI
            self.update_annotations()
            self.populate_behavior_treeviews()
        else:
            # Start a new state behavior
            self.active_state_behaviors[key] = frame_timestamp
            self.state_events.append({
                'Name': Name,
                'start_time': frame_timestamp,
                'end_time': None,
                'Type': 'State',
                'Mutually_Exclusive': 'True' if me_group else 'False',
                'Notes': ""
            })
            
            # Update UI
            self.update_annotations()
            self.populate_behavior_treeviews()

    def deactivate_me_group(self, me_group, frame_timestamp, current_behavior_key):
        """Deactivate behaviors in mutually exclusive group"""
        keys_to_remove = []
        
        for key, start_time in list(self.active_state_behaviors.items()):
            if self.me_groups.get(key) == me_group and key != current_behavior_key:
                Name = self.state_behaviors.get(key)
                duration = frame_timestamp - start_time
                
                # Format timestamps
                human_readable_start_time = self.format_time_human_readable(start_time)
                human_readable_end_time = self.format_time_human_readable(frame_timestamp)
                machine_readable_start_time = self.format_time_machine_readable(start_time)
                machine_readable_end_time = self.format_time_machine_readable(frame_timestamp)
                machine_readable_duration = self.format_time_machine_readable(duration)
                
                # Create record
                record = {
                    "Video": self.video_name,
                    "Name": Name,
                    "Type": "State",
                    "Mutually_Exclusive": "True",
                    "H_Start": human_readable_start_time,
                    "H_End": human_readable_end_time,
                    "Start": machine_readable_start_time,
                    "End": machine_readable_end_time,
                    "Duration": machine_readable_duration,
                    "Manual_Edit": "False",
                    "Notes": ""
                }
                
                # Save record
                self.append_annotation(record)
                
                # Update state events
                for event in self.state_events:
                    if event['Name'] == Name and event['end_time'] is None:
                        event['end_time'] = frame_timestamp
                        break
                        
                keys_to_remove.append(key)
        
        # Remove deactivated behaviors
        for key in keys_to_remove:
            self.active_state_behaviors.pop(key)
        
        # Update UI
        self.update_annotations()
        self.populate_behavior_treeviews()

    def append_annotation(self, annotation_record):
        """Append annotation record to CSV file"""
        # Define headers
        headers = ['Video', 'Name', 'Type', 'Mutually_Exclusive', 'H_Start', 'H_End',
                  'Start', 'End', 'Duration', 'Manual_Edit', 'Notes']
        
        # Read existing rows
        rows = []
        if os.path.exists(self.annotations_file):
            with open(self.annotations_file, 'r', newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Ensure Notes field exists
                    if 'Notes' not in row:
                        row['Notes'] = ""
                    rows.append(row)
        
        # Ensure Notes field in new record
        if 'Notes' not in annotation_record:
            annotation_record['Notes'] = ""
            
        # Append new record
        rows.append(annotation_record)
        
        # Write to temporary file and replace original
        temp_file = self.annotations_file + ".tmp"
        with open(temp_file, 'w', newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(temp_file, self.annotations_file)

    def sort_state_annotations(self):
        self.state_events.sort(key=lambda x: x['start_time'] if x['start_time'] is not None else 0)
        self.save_sorted_annotations()
        self.update_annotations()

    def sort_point_annotations(self):
        self.point_events.sort(key=lambda x: self.parse_time(x['time']) if x['time'] is not None else 0)
        self.save_sorted_annotations()
        self.update_annotations()

    def save_sorted_annotations(self):
        """Save annotations to file with proper Manual_Edit handling"""
        with open(self.annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Video', 'Name', 'Type', 'Mutually_Exclusive', 'H_Start', 'H_End', 
                            'Start', 'End', 'Duration', 'Manual_Edit', 'Notes'])
            
            # Save state events
            for event in self.state_events:
                start_time = self.format_time_machine_readable(event['start_time'])
                end_time = self.format_time_machine_readable(event['end_time']) if event['end_time'] is not None else 'NA'
                duration = self.format_time_machine_readable(event['end_time'] - event['start_time']) if event['end_time'] is not None else 'NA'
                H_start = self.format_time_human_readable(event['start_time'])
                H_end = self.format_time_human_readable(event['end_time']) if event['end_time'] is not None else 'NA'
                manual_edit = str(event.get('Manual_Edit', False))  # Get Manual_Edit value, default to False
                notes = event.get('Notes', "")
                
                writer.writerow([
                    self.video_name,
                    event['Name'],
                    event.get('Type', 'State'),
                    event.get('Mutually_Exclusive', 'False'),
                    H_start,
                    H_end,
                    start_time,
                    end_time,
                    duration,
                    manual_edit,
                    notes
                ])
                
            # Save point events
            for event in self.point_events:
                time_machine = self.format_time_machine_readable(self.parse_time(event['time']))
                manual_edit = str(event.get('Manual_Edit', False))  # Get Manual_Edit value, default to False
                notes = event.get('Notes', "")
                
                writer.writerow([
                    self.video_name,
                    event['Name'],
                    event.get('Type', 'Point'),
                    event.get('Mutually_Exclusive', 'False'),
                    event['time'],
                    'NA',
                    time_machine,
                    'NA',
                    'NA',
                    manual_edit,
                    notes
                ])

    def save_point_annotation(self, new_entries, dialog, selected_annotation, old_start_time):
        """Saves the edited point annotation."""
        new_name = new_entries['Name'].text().strip()
        new_h_start = new_entries['H_Start'].text().strip()

        if not new_name or not new_h_start:
            messagebox.showwarning("Invalid Input", "Both Name and Start Time are required.")
            return

        print(f"Updating point annotation from {selected_annotation} to {{'Name': '{new_name}', 'H_Start': '{new_h_start}'}}")

        # Update only the specific matching annotation in the in-memory list
        found_and_updated = False
        for annotation in self.point_events:
            if annotation['Name'] == selected_annotation['Name'] and annotation['time'] == old_start_time:
                # Only set Manual_Edit to True if the name or time changed
                if annotation['Name'] != new_name or annotation['time'] != new_h_start:
                    annotation['Manual_Edit'] = True
                annotation['Name'] = new_name
                annotation['time'] = new_h_start
                found_and_updated = True
                break
        
        if not found_and_updated:
            print(f"Warning: Could not find matching annotation to update")
            return

        self.save_sorted_annotations()
        self.update_annotations()
        self.dialog_open = False
        dialog.destroy()

    def save_state_annotation(self, new_entries, dialog, selected_annotation, old_start_time):
        """
        Saves the edited state annotation.

        Parameters:
          new_entries (dict): Contains QLineEdit widgets for 'Name', 'H_Start', and 'H_End'.
          dialog (QDialog): The dialog window for editing.
          selected_annotation (dict): The original state annotation that was edited.
          old_start_time (str): The original human-readable start time used to identify the annotation.
        """
        new_name = new_entries['Name'].text().strip()
        new_h_start = new_entries['H_Start'].text().strip()
        new_h_end = new_entries['H_End'].text().strip()

        if not new_name or not new_h_start or not new_h_end:
            QMessageBox.warning(self, "Invalid Input", "Name, Start, and End times are required.")
            return

        print(f"Updating state annotation from {selected_annotation} to {{'Name': '{new_name}', 'H_Start': '{new_h_start}', 'H_End': '{new_h_end}'}}")

        # Convert human-readable times to machine-readable values (floats)
        new_start_time = self.parse_time(new_h_start)
        new_end_time = self.parse_time(new_h_end)

        # Update the matching annotation in the in-memory list.
        for annotation in self.state_events:
            # Identify the annotation using the old human-readable start time.
            if (annotation['Name'] == selected_annotation['Name'] and 
                self.format_time_human_readable(annotation.get('start_time', 0)) == old_start_time):
                annotation['Name'] = new_name
                annotation['start_time'] = new_start_time
                annotation['end_time'] = new_end_time
                annotation['Manual_Edit'] = True
                # Preserve existing notes
                if 'Notes' not in annotation:
                    annotation['Notes'] = ""
                break

        self.save_sorted_annotations()
        self.update_annotations()
        self.dialog_open = False
        dialog.accept()

    def format_time_human_readable(self, elapsed_time):
        minutes, seconds = divmod(float(elapsed_time), 60)
        return f"{int(minutes)}m{seconds:04.2f}s"

    def format_time_machine_readable(self, elapsed_time):
        return f"{float(elapsed_time):.2f}"

    def parse_time(self, time_str):
        if 'm' in time_str and 's' in time_str:
            m, s = time_str.split('m')
            return int(m) * 60 + float(s.rstrip('s'))
        return float(time_str)

    def toggle_play(self, event=None):
        """Toggle play/pause state"""
        self.player.pause = not self.player.pause

    def refresh_paused_frame(self):
        """Refresh the current frame when paused"""
        if not self.player.is_playing():
            self.player.pause = False
            self.update()
            # Fix: Use a regular function instead of lambda for assignment
            def set_pause():
                self.player.pause = True
            QTimer.singleShot(20, set_pause)

    def step_frame_if_paused(self):
        """Step forward one frame if paused"""
        if self.player.is_playing():
            self.player.next_frame()

    def seek_relative(self, offset_ms):
        """Seek relative to current position with end-of-video handling"""
        total_sec = self.player.duration or 0
        current_sec = self.player.time_pos or 0
        offset_sec = offset_ms / 1000.0
        
        # Calculate the new position
        new_time = current_sec + offset_sec
        
        # Check if seeking beyond the end of the video
        if new_time >= total_sec:
            print(f"Attempting to seek beyond end of video. Pausing at last frame.")
            new_time = max(0, total_sec - 0.5)  # Set to just before the end
            self.player.time_pos = new_time
            self.player.pause = True  # Pause playback
        else:
            # Normal seek within video bounds
            new_time = max(0, new_time)  # Ensure we don't go below 0
            self.player.time_pos = new_time
        
        # Update progress bar immediately to reflect new position
        self.update_progress()

    def change_speed(self, delta):
        """Change playback speed"""
        speed_steps = [0.5, 1, 2, 3, 5, 8, 10, 15, 20, 25]
        current_rate = self.player.speed
        
        try:
            index = speed_steps.index(current_rate)
        except ValueError:
            index = min(range(len(speed_steps)), 
                       key=lambda i: abs(speed_steps[i] - current_rate))
        
        new_index = max(0, min(len(speed_steps) - 1, index + (1 if delta > 0 else -1)))
        new_rate = speed_steps[new_index]
        
        if new_rate != current_rate:
            self.player.speed = new_rate
            print(f"New speed: {new_rate:.2f}x")
            
            # Use the new method to update the center text
            self.update_center_text(f"({new_rate:.1f}x)")

    def reset_speed(self):
        """Reset playback speed to 1x"""
        current_rate = self.player.speed
        if current_rate != 1.0:
            self.player.speed = 1.0
            print("Reset speed to 1.0x")
            
            # Update the center text in the progress bar
            self.update_center_text("(1.0x)")

    def on_closing(self):
        """Handle application closing and ensure floating windows are destroyed."""
        try:
            # List of attribute names for floating windows to destroy
            floating_attrs = [
                'floating_controls_window',
                'behavior_buttons_window',
                'behavior_toggle_window',
                'controls_window',
                'edit_dialog'
            ]
            
            # Delete floating windows
            for attr in floating_attrs:
                if hasattr(self, attr):
                    win = getattr(self, attr)
                    if win is not None:
                        win.deleteLater()

            # Delete additional tracked windows
            if hasattr(self, 'floating_windows'):
                for win in self.floating_windows:
                    if win is not None:
                        win.deleteLater()
                self.floating_windows.clear()
            
            # Save session state and stop player
            if hasattr(self, 'player') and self.player:
                self.save_session_state()
                self.player.pause = True
                self.player.stop()
            
            # Close main window
            self.parent.close()
            
        except Exception as e:
            print(f"Error during closing: {e}")
            self.parent.close()

    def visualize_annotations(self):
        """Show visualization dialog"""
        self.dialog_open = True
        
        # Create dialog
        dialog = QDialog(self.parent)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dialog.setWindowTitle("Visualize Annotations")
        dialog.setModal(True)
        
        # Center dialog
        self.center_window(dialog, 300, 150)
        
        # Create layout
        layout = QVBoxLayout(dialog)
        
        # Add label
        label = QLabel("Annotations visualization is\ncurrently under development.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        # Add OK button
        button = QPushButton("OK")
        button.clicked.connect(lambda: self.on_visualization_close(dialog))
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
                
        # Show dialog
        dialog.exec()

    def generate_summary_statistics(self):
        """Show summary statistics dialog"""
        self.dialog_open = True
        
        # Create dialog
        dialog = QDialog(self.parent)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        dialog.setWindowTitle("Summary Statistics")
        dialog.setModal(True)
        
        # Center dialog
        self.center_window(dialog, 300, 150)
        
        # Create layout
        layout = QVBoxLayout(dialog)
        
        # Add label
        label = QLabel("Generating summary statistics is\ncurrently under development")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        # Add OK button
        button = QPushButton("OK")
        button.clicked.connect(lambda: self.on_summary_close(dialog))
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Set up close handling
        dialog.finished.connect(lambda: self.on_summary_close(dialog))
        
        # Show dialog
        dialog.exec()

    def on_visualization_close(self, dialog):
        """Handle visualization dialog closing"""
        self.dialog_open = False
        dialog.accept()

    def on_summary_close(self, dialog):
        """Handle summary dialog closing"""
        self.dialog_open = False
        dialog.accept()

    def show_annotation_menu(self, point):
        """Show context menu for annotation item"""
        # Pause the video
        if hasattr(self, 'player') and self.player:
            self.player.pause = True
        
        # Determine which tree widget was clicked
        tree_widget = self.sender()
        self.selected_treeview = tree_widget
        
        # Get selected item at click position
        item = tree_widget.itemAt(point)
        if not item:
            return
        
        tree_widget.setCurrentItem(item)
        self.selected_item = item
        
        # Get selected index
        if self.selected_treeview == self.state_annotations_tree:
            self.selected_index = self.state_annotations_tree.indexOfTopLevelItem(item)
        else:
            self.selected_index = self.point_annotations_tree.indexOfTopLevelItem(item)
        
        # Create context menu
        menu = QMenu(self)
        menu.addAction("Edit", self.edit_annotation)
        menu.addAction("Add Note", self.add_note_to_annotation)
        menu.addAction("View Details", self.view_annotation_details)
        menu.addAction("Skip to Annotation", self.skip_to_annotation)
        menu.addAction("Delete", self.delete_annotation)
        
        # Show menu at cursor position
        menu.exec(tree_widget.viewport().mapToGlobal(point))

    def view_annotation_details(self):
        """Show annotation details dialog"""
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return
        
        # Get annotation data
        if self.selected_treeview == self.state_annotations_tree:
            annotation = self.state_events[self.selected_index]
            annotation_type = "State"
        else:
            annotation = self.point_events[self.selected_index]
            annotation_type = "Point"
        
        # Create dialog
        self.dialog_open = True
        
        if hasattr(self, 'details_dialog') and self.details_dialog is not None:
            self.details_dialog.deleteLater()
        
        self.details_dialog = QDialog(self.parent)
        self.details_dialog.setWindowFlags(
            self.details_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self.details_dialog.setWindowTitle(f"Annotation Details - {annotation['Name']}")
        self.details_dialog.setModal(True)
        self.center_window(self.details_dialog, 500, 400)
        
        # Create main layout
        main_layout = QVBoxLayout(self.details_dialog)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Create details grid
        details_widget = QWidget()
        details_layout = QGridLayout(details_widget)
        details_layout.setColumnStretch(1, 1)
        main_layout.addWidget(details_widget)
        
        # Common details
        details = [
            ("Name:", annotation['Name']),
            ("Type:", annotation_type),
            ("Video:", self.video_name)
        ]
        
        # Add type-specific details
        if annotation_type == "State":
            start_time = self.format_time_human_readable(annotation['start_time'])
            end_time = self.format_time_human_readable(annotation['end_time']) if annotation['end_time'] is not None else "NA"
            
            # Calculate duration
            if annotation['end_time'] is not None and annotation['start_time'] is not None:
                duration = annotation['end_time'] - annotation['start_time']
                duration_str = self.format_time_human_readable(duration)
            else:
                duration_str = "NA"
            
            additional_details = [
                ("Start Time:", start_time),
                ("End Time:", end_time),
                ("Duration:", duration_str),
                ("Mutually Exclusive:", annotation.get('Mutually_Exclusive', 'False'))
            ]
            details.extend(additional_details)
        else:  # Point annotation
            details.append(("Time:", annotation['time']))
        
        # Add manual edit status
        if 'Manual_Edit' in annotation:
            details.append(("Manually Edited:", str(annotation['Manual_Edit'])))
        
        # Display details in grid
        for row, (label, value) in enumerate(details):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            value_widget = QLabel(value)
            details_layout.addWidget(label_widget, row, 0)
            details_layout.addWidget(value_widget, row, 1)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)
        
        # Notes section
        notes_label = QLabel("Notes:")
        notes_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(notes_label)
        
        # Get existing note and convert dots to newlines
        existing_note = annotation.get('Notes', "")
        if " . " in existing_note:
            existing_note = existing_note.replace(" . ", "\n")
        
        # Create text editor for notes
        self.details_note_text = QTextEdit()
        self.details_note_text.setMinimumHeight(100)
        self.details_note_text.setText(existing_note)
        self.details_note_text.setReadOnly(True)
        main_layout.addWidget(self.details_note_text)
        
        # Button frame
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add buttons
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(
            lambda: self.open_comprehensive_edit(annotation, annotation_type)
        )
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.on_details_dialog_close)
        
        button_layout.addWidget(edit_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        main_layout.addWidget(button_frame)
        
        # Connect close event
        self.details_dialog.finished.connect(self.on_details_dialog_close)
        
        # Show dialog
        self.details_dialog.exec()

    def open_comprehensive_edit(self, annotation, annotation_type):
        """Open a comprehensive edit dialog for both timing and notes."""
        # Close the details dialog if open
        if hasattr(self, 'details_dialog') and self.details_dialog:
            self.on_details_dialog_close()
        
        self.dialog_open = True
        
        # Create edit dialog
        edit_dialog = QDialog(self.parent)
        edit_dialog.setWindowFlags(
            edit_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        edit_dialog.setWindowTitle(f"Edit {annotation_type} Annotation")
        edit_dialog.setModal(True)
        self.center_window(edit_dialog, 400, 500)
        
        # Create main layout
        main_layout = QVBoxLayout(edit_dialog)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Create form layout for entries
        form_layout = QFormLayout()
        entries = {}
        
        # Common fields
        fields = ['Name']
        if annotation_type == 'State':
            fields.extend(['H_Start', 'H_End'])
        else:
            fields.append('H_Start')
        
        # Create entry fields
        for field in fields:
            entry = QLineEdit()
            if field == 'Name':
                entry.setText(annotation['Name'])
            elif field == 'H_Start':
                if annotation_type == 'State':
                    entry.setText(self.format_time_human_readable(annotation['start_time']))
                else:
                    entry.setText(annotation['time'])
            elif field == 'H_End':
                if annotation['end_time'] is not None:
                    entry.setText(self.format_time_human_readable(annotation['end_time']))
            
            # Add to form layout with proper label
            form_layout.addRow(field.replace('H_', '') + ':', entry)
            entries[field] = entry
        
        main_layout.addLayout(form_layout)
        
        # Notes section
        notes_label = QLabel("Notes:")
        main_layout.addWidget(notes_label)
        
        # Get existing note and convert dots to newlines
        existing_note = annotation.get('Notes', "")
        if " . " in existing_note:
            existing_note = existing_note.replace(" . ", "\n")
        
        # Create text editor for notes
        notes_text = QTextEdit()
        notes_text.setMinimumHeight(150)
        notes_text.setText(existing_note)
        main_layout.addWidget(notes_text)
        
        # Button frame
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        
        def save_comprehensive_edit():
            # Get values from entries
            new_values = {field: entry.text().strip() for field, entry in entries.items()}
            new_note = notes_text.toPlainText().strip()
            
            # Convert newlines to dots for storage
            new_note = new_note.replace("\n", " . ")
            
            # Update the annotation
            if annotation_type == 'State':
                # Convert times to float values
                new_start = self.parse_time(new_values['H_Start'])
                new_end = self.parse_time(new_values['H_End'])
                
                # Find and update the annotation in state_events
                for evt in self.state_events:
                    if (evt['Name'] == annotation['Name'] and 
                        evt['start_time'] == annotation['start_time']):
                        # Check if time or name changed before setting Manual_Edit
                        if (evt['Name'] != new_values['Name'] or 
                            evt['start_time'] != new_start or 
                            evt['end_time'] != new_end):
                            evt['Manual_Edit'] = True
                        evt['Name'] = new_values['Name']
                        evt['start_time'] = new_start
                        evt['end_time'] = new_end
                        evt['Notes'] = new_note
                        break
            else:
                # Find and update the annotation in point_events
                for evt in self.point_events:
                    if evt['Name'] == annotation['Name'] and evt['time'] == annotation['time']:
                        # Check if time or name changed before setting Manual_Edit
                        if (evt['Name'] != new_values['Name'] or 
                            evt['time'] != new_values['H_Start']):
                            evt['Manual_Edit'] = True
                        evt['Name'] = new_values['Name']
                        evt['time'] = new_values['H_Start']
                        evt['Notes'] = new_note
                        break
            
            # Save changes to file
            self.save_sorted_annotations()
            self.update_annotations()
            
            # Close dialog
            self.dialog_open = False
            edit_dialog.accept()
        
        def cancel_edit():
            self.dialog_open = False
            edit_dialog.reject()
        
        # Create and add buttons
        save_button = QPushButton("Save")
        save_button.clicked.connect(save_comprehensive_edit)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(cancel_edit)
        
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        
        main_layout.addWidget(button_frame)
        
        # Connect dialog finished signal
        edit_dialog.finished.connect(lambda: setattr(self, 'dialog_open', False))
        
        # Show dialog
        edit_dialog.exec()

    def save_note_to_annotation(self, annotation):
        """Save the entered note to the annotation."""
        if not hasattr(self, 'note_text'):
            return
        
        # Get note text
        note = self.note_text.toPlainText().strip()
        
        # Replace newlines with dots for CSV compatibility
        note = note.replace("\n", " . ").replace("\r", " . ")
        
        # Update annotation in memory
        annotation['Notes'] = note
        
        # Save to file
        self.save_sorted_annotations()
        
        # Close dialog
        self.on_note_dialog_close()

    def on_menu_close(self):
        """Handle menu closing"""
        # Don't set dialog_open to False here
        if hasattr(self, 'annotation_menu'):
            self.annotation_menu.deleteLater()

    def on_edit_dialog_close(self):
        """Handle edit dialog closing"""
        self.dialog_open = False
        if hasattr(self, 'edit_dialog') and self.edit_dialog is not None:
            self.edit_dialog.deleteLater()
            self.edit_dialog = None

    def on_note_dialog_close(self):
        """Handle note dialog closing"""
        self.dialog_open = False
        if hasattr(self, 'note_dialog') and self.note_dialog is not None:
            self.note_dialog.deleteLater()
            self.note_dialog = None

    def on_details_dialog_close(self):
        """Handle details dialog closing"""
        self.dialog_open = False
        if hasattr(self, 'details_dialog') and self.details_dialog is not None:
            self.details_dialog.deleteLater()
            self.details_dialog = None

    def edit_annotation(self):
        """Edit the selected annotation"""
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return
        if self.selected_treeview == self.state_annotations_tree:
            self.edit_state_annotation()
        else:
            self.edit_point_annotation()

    def edit_state_annotation(self):
        """Edit a state annotation"""
        if self.selected_index is None:
            return
        
        self.dialog_open = True
        selected_annotation = self.state_events[self.selected_index]
        
        if selected_annotation['end_time'] is None:
            QMessageBox.warning(self, "Edit Error", "Please end the state behavior before editing.")
            return

        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_Start', 'H_End')
        print(f"Editing state annotation: {latest_annotation}")

        # Create edit dialog
        edit_dialog = QDialog(self.parent)
        edit_dialog.setWindowFlags(edit_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        edit_dialog.setWindowTitle("Edit State Annotation")
        edit_dialog.setModal(True)
        self.center_window(edit_dialog, 250, 300)

        # Create layout
        layout = QVBoxLayout(edit_dialog)

        # Current annotation section
        current_group = QGroupBox("Current Annotation")
        current_layout = QFormLayout()
        current_layout.addRow("Name:", QLabel(latest_annotation['Name']))
        current_layout.addRow("Start:", QLabel(latest_annotation['H_Start']))
        current_layout.addRow("End:", QLabel(latest_annotation['H_End']))
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        # New annotation section
        new_group = QGroupBox("New Annotation")
        new_layout = QFormLayout()
        new_entries = {}
        new_fields = ['Name', 'H_Start', 'H_End']
        
        for field in new_fields:
            entry = QLineEdit()
            entry.setText(latest_annotation.get(field, ""))
            new_layout.addRow(field.replace('H_', '') + ':', entry)
            new_entries[field] = entry
        
        new_group.setLayout(new_layout)
        layout.addWidget(new_group)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(
            lambda: self.save_state_annotation(new_entries, edit_dialog, 
                                             selected_annotation, latest_annotation['H_Start'])
        )
        button_box.rejected.connect(edit_dialog.reject)
        layout.addWidget(button_box)

        # Handle dialog closing
        edit_dialog.finished.connect(lambda: self.on_edit_dialog_close())
        
        # Show dialog
        edit_dialog.exec()

    def edit_point_annotation(self):
        """Edit a point annotation"""
        if self.active_state_behaviors:
            QMessageBox.warning(self, "Active Annotation", 
                              "Please end the active state before editing.")
            return

        if self.selected_index is None:
            return
            
        self.dialog_open = True
        selected_annotation = self.point_events[self.selected_index]
        print(f"Editing point annotation: {selected_annotation}")

        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_Start')
        print(f"Latest annotation data for editing: {latest_annotation}")

        # Create edit dialog
        edit_dialog = QDialog(self.parent)
        edit_dialog.setWindowFlags(edit_dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        edit_dialog.setWindowTitle("Edit Point Annotation")
        edit_dialog.setModal(True)
        self.center_window(edit_dialog, 275, 250)

        # Create layout
        layout = QVBoxLayout(edit_dialog)

        # Current annotation section
        current_group = QGroupBox("Current Annotation")
        current_layout = QFormLayout()
        current_layout.addRow("Name:", QLabel(latest_annotation['Name']))
        current_layout.addRow("Time:", QLabel(latest_annotation['H_Start']))
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        # New annotation section
        new_group = QGroupBox("New Annotation")
        new_layout = QFormLayout()
        new_entries = {}
        new_fields = ['Name', 'H_Start']
        
        for field in new_fields:
            entry = QLineEdit()
            entry.setText(latest_annotation.get(field, ""))
            new_layout.addRow(field.replace('H_', '') + ':', entry)
            new_entries[field] = entry
            
        new_group.setLayout(new_layout)
        layout.addWidget(new_group)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(
            lambda: self.save_point_annotation(new_entries, edit_dialog, 
                                             selected_annotation, latest_annotation['H_Start'])
        )
        button_box.rejected.connect(edit_dialog.reject)
        layout.addWidget(button_box)

        # Handle dialog closing
        edit_dialog.finished.connect(lambda: self.on_edit_dialog_close())
        
        # Show dialog
        edit_dialog.exec()

    def load_annotation_data(self, annotation, *fields):
        """Load annotation data from file"""
        latest_annotation = {field: "" for field in fields}
        print(f"Loading annotation data for {annotation}")
        
        with open(self.annotations_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # For state annotations, compare Name and H_Start
                if (row['Name'] == annotation['Name'] and 
                    row['H_Start'] == self.format_time_human_readable(
                        annotation.get('start_time', 0))):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    print(f"Found matching row: {latest_annotation}")
                    break
                # For point annotations, check H_Start only
                elif ('H_Start' in row and 
                      row['H_Start'] == annotation.get('time')):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    print(f"Found matching point row: {latest_annotation}")
                    break
        return latest_annotation

    def skip_to_annotation(self):
        """Skip to selected annotation's time"""
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        # Get time from selected item
        time_column = 1  # Assume column 1 holds the start time
        time_str = self.selected_item.text(time_column)
        start_time = self.parse_time(time_str)
        
        if start_time is not None:
            # Set player position and pause
            self.player.time_pos = start_time
            self.update_progress()
            self.player.pause = True

    def delete_annotation(self):
        """Delete selected annotation"""
        # Get selected item
        if self.selected_treeview == self.state_annotations_tree:
            deleted_annotation = self.state_events.pop(self.selected_index)
            self.undo_stack.append(("state", self.selected_index, deleted_annotation))
        else:
            deleted_annotation = self.point_events.pop(self.selected_index)
            self.undo_stack.append(("point", self.selected_index, deleted_annotation))
        
        # Update UI
        self.save_sorted_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()

    def delete_annotation_key(self):
        """Handle delete key press"""
        self.delete_annotation()

    def undo_delete(self):
        """Undo last annotation deletion"""
        if not self.undo_stack:
            return  # Nothing to undo

        # Get last deleted annotation
        annotation_type, index, annotation = self.undo_stack.pop()

        # Restore annotation
        if annotation_type == "state":
            self.state_events.insert(index, annotation)
        else:
            self.point_events.insert(index, annotation)
        
        # Update UI
        self.save_sorted_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()

    def return_to_file_selection(self):
        """
        Save session state, close video annotator, and return to file selection UI.
        """
        try:
            # 1. Save session state
            self.save_session_state()
            
            # 2. Clean up resources
            if hasattr(self, 'player') and self.player:
                self.player.pause = True
                self.player.stop()
            
            # Close floating windows
            floating_attrs = [
                'floating_controls_window',
                'behavior_buttons_window',
                'behavior_toggle_window',
                'controls_window',
                'edit_dialog'
            ]
            
            for attr in floating_attrs:
                if hasattr(self, attr):
                    win = getattr(self, attr)
                    if win is not None:
                        win.deleteLater()

            for win in self.floating_windows:
                if win is not None:
                    win.deleteLater()
            self.floating_windows.clear()
            
            # 3. Create and show new SetupManager
            from setup_manager import SetupManager
            from config_manager import ConfigManager
            
            config_manager = ConfigManager()
            setup_dialog = SetupManager(config_manager=config_manager, parent=self.parent)
            
            # First remove the video annotator from parent
            if self.parent:
                self.parent.setCentralWidget(None)
                self.deleteLater()
            
            # Show the setup dialog
            setup_dialog.exec()
            
            # Check if setup was successful and create new video annotator
            if setup_dialog.start_video_flag and setup_dialog.video_path and setup_dialog.behavior_key_file:
                # Initialize new video annotator with new parameters
                new_video_annotator = VideoAnnotator(
                    self.parent,
                    video_path=setup_dialog.video_path,
                    session_state_file=setup_dialog.session_state_file,
                    behavior_key_file=setup_dialog.behavior_key_file,
                    output_dir=setup_dialog.output_dir
                )
                
                # Set as central widget
                self.parent.setCentralWidget(new_video_annotator)
            else:
                # If user cancels, close the application
                self.parent.close()
                
        except Exception as e:
            print(f"Error returning to file selection: {e}")
            # If error occurs, close the application
            if self.parent:
                self.parent.close()