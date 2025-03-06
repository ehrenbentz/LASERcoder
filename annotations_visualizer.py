import os
import csv
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QComboBox, QLabel, QSpinBox, QFileDialog, QFrame, 
                            QMessageBox)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont, 
                        QLinearGradient, QPainterPath, QImage, QPdfWriter, QPageSize,
                        QPageLayout)

class AnnotationsVisualizer(QFrame):
    """Timeline visualization widget for displaying state and point annotations"""
    
    def __init__(self, parent, video_name, state_events, point_events, video_duration, parse_time_func):
        super().__init__(parent)
        self.video_name = video_name
        self.state_events = state_events
        self.point_events = point_events
        self.video_duration = video_duration
        self.parse_time_func = parse_time_func
        self.setMinimumHeight(500)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setStyleSheet("background-color: white;")
        
        # Track spacing and dimensions
        self.header_height = 40
        self.track_height = 25
        self.track_spacing = 10
        self.margin_left = 150
        self.margin_right = 50
        self.margin_top = 20
        self.margin_bottom = 20
        self.tick_height = 10
        
        # Colors
        self.state_color = QColor(100, 150, 220, 180)  # Blue with transparency
        self.point_color = QColor(220, 80, 80)  # Red
        self.track_color = QColor(240, 240, 240)  # Light gray
        self.text_color = QColor(40, 40, 40)  # Dark gray
        
        # Calculate space needed for tracks
        self.state_behaviors, self.point_behaviors = self.get_unique_behaviors_by_type()
        self.calculate_height()
    
    def get_unique_behaviors_by_type(self):
        """Collects unique behavior names separated by type"""
        state_behaviors = set()
        point_behaviors = set()
        
        # Get state behaviors
        for event in self.state_events:
            if event['Name']:
                state_behaviors.add(event['Name'])
        
        # Get point behaviors
        for event in self.point_events:
            if event['Name']:
                point_behaviors.add(event['Name'])
        
        return sorted(list(state_behaviors)), sorted(list(point_behaviors))
    
    def calculate_height(self):
        """Calculates required height based on number of behaviors plus group headers"""
        section_header_height = 30  # Height for section headers
        section_spacing = 20       # Additional spacing between sections
        
        # Calculate total number of behaviors
        total_behaviors = len(self.state_behaviors) + len(self.point_behaviors)
        
        if total_behaviors == 0:
            self.required_height = self.header_height + self.margin_top + self.margin_bottom
        else:
            # If we have both types, include two section headers and section spacing
            section_headers = 0
            if self.state_behaviors:
                section_headers += 1
            if self.point_behaviors:
                section_headers += 1
            
            # Calculate total tracks height
            total_tracks_height = total_behaviors * (self.track_height + self.track_spacing)
            
            # Calculate total height with headers and spacing
            self.required_height = (
                self.header_height + 
                total_tracks_height + 
                (section_headers * section_header_height) +
                (1 if section_headers > 1 else 0) * section_spacing +
                self.margin_top + 
                self.margin_bottom
            )
        
        self.setMinimumHeight(self.required_height)
    
    def paintEvent(self, event):
        """Draws the timeline visualization"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background
        painter.fillRect(event.rect(), QColor(255, 255, 255))
        
        # Draw title
        painter.setPen(self.text_color)
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(0, 0, self.width(), self.header_height),
            Qt.AlignmentFlag.AlignCenter,
            f"Annotation Timeline for {self.video_name}"
        )
        
        # Setup for tracks
        track_font = QFont("Arial", 10)
        painter.setFont(track_font)
        
        # Draw time axis
        axis_y = self.header_height + 5
        axis_width = self.width() - self.margin_left - self.margin_right
        painter.drawLine(
            int(self.margin_left), int(axis_y), 
            int(self.margin_left + axis_width), int(axis_y)
        )
        
        # Draw time markers
        time_points = 5  # Number of time points to show
        for i in range(time_points + 1):
            x_pos = self.margin_left + (axis_width * i / time_points)
            time_value = (self.video_duration * i / time_points)
            time_str = self.format_time(time_value)
            
            painter.drawLine(
                int(x_pos), int(axis_y - 3), 
                int(x_pos), int(axis_y + 3)
            )
            painter.drawText(
                QRectF(x_pos - 50, axis_y + 5, 100, 20),
                Qt.AlignmentFlag.AlignCenter,
                time_str
            )
        
        # Define section header style
        section_header_height = 30
        section_spacing = 20
        
        section_header_font = QFont("Arial", 12, QFont.Weight.Bold)
        section_header_color = QColor(70, 70, 70)
        section_header_bg = QColor(230, 230, 230)
        
        # Initial y position after the time axis
        y_position = self.header_height + 30
        
        # Draw State Behaviors Section
        if self.state_behaviors:
            # Draw section header
            section_rect = QRectF(0, y_position, self.width(), section_header_height)
            painter.fillRect(section_rect, section_header_bg)
            painter.setPen(section_header_color)
            painter.setFont(section_header_font)
            painter.drawText(
                section_rect,
                Qt.AlignmentFlag.AlignCenter,
                "State Annotations"
            )
            
            # Move position down for first behavior
            y_position += section_header_height + 5
            
            # Reset to normal font for behaviors
            painter.setFont(track_font)
            
            # Draw each state behavior track
            for behavior in self.state_behaviors:
                # Draw behavior name
                text_rect = QRectF(0, y_position, self.margin_left - 10, self.track_height)
                painter.setPen(self.text_color)
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    behavior
                )
                
                # Clear any previous brush settings before drawing track background
                painter.setBrush(QBrush())
                
                # Draw track background
                track_rect = QRectF(
                    self.margin_left, y_position, 
                    axis_width, self.track_height
                )
                painter.fillRect(track_rect, self.track_color)
                painter.setPen(QPen(QColor(200, 200, 200)))
                painter.drawRect(track_rect)
                
                # Draw state events for this behavior
                painter.setPen(QPen(self.state_color.darker()))
                painter.setBrush(QBrush(self.state_color))
                
                for event in self.state_events:
                    if event['Name'] == behavior and event['start_time'] is not None:
                        # Calculate start and end positions
                        start_pos = self.time_to_position(event['start_time'])
                        
                        # Handle events with no end time (still active)
                        if event['end_time'] is None:
                            end_pos = self.margin_left + axis_width
                        else:
                            end_pos = self.time_to_position(event['end_time'])
                        
                        # Draw state box
                        state_rect = QRectF(
                            start_pos, y_position + 2,
                            end_pos - start_pos, self.track_height - 4
                        )
                        painter.drawRect(state_rect)
                
                # Reset brush after drawing all state events for this behavior
                painter.setBrush(QBrush())
                
                # Move to next track position
                y_position += self.track_height + self.track_spacing
            
            # Add extra spacing after state behaviors section
            if self.point_behaviors:
                y_position += section_spacing - self.track_spacing  # Adjust for already added track spacing
        
        # Draw Point Behaviors Section
        if self.point_behaviors:
            # Draw section header
            section_rect = QRectF(0, y_position, self.width(), section_header_height)
            painter.fillRect(section_rect, section_header_bg)
            painter.setPen(section_header_color)
            painter.setFont(section_header_font)
            painter.drawText(
                section_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Point Annotations"
            )
            
            # Move position down for first behavior
            y_position += section_header_height + 5
            
            # Reset to normal font for behaviors
            painter.setFont(track_font)
            
            # Draw each point behavior track
            for behavior in self.point_behaviors:
                # Draw behavior name
                text_rect = QRectF(0, y_position, self.margin_left - 10, self.track_height)
                painter.setPen(self.text_color)
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    behavior
                )
                
                # Clear any previous brush settings before drawing track background
                painter.setBrush(QBrush())
                
                # Draw track background
                track_rect = QRectF(
                    self.margin_left, y_position, 
                    axis_width, self.track_height
                )
                painter.fillRect(track_rect, self.track_color)
                painter.setPen(QPen(QColor(200, 200, 200)))
                painter.drawRect(track_rect)
                
                # Draw point events for this behavior
                painter.setPen(QPen(self.point_color, 2))
                
                for event in self.point_events:
                    if event['Name'] == behavior:
                        # Get time value either from raw_time or by parsing the time string
                        if 'raw_time' in event and event['raw_time'] is not None:
                            time_value = event['raw_time']
                        else:
                            time_str = event['time']
                            time_value = self.parse_time_func(time_str)
                        
                        # Calculate position
                        x_pos = self.time_to_position(time_value)
                        
                        # Draw point marker
                        painter.drawLine(
                            int(x_pos), int(y_position),
                            int(x_pos), int(y_position + self.track_height)
                        )
                                        
                # Reset brush and pen after drawing all point events for this behavior
                painter.setBrush(QBrush())
                painter.setPen(QPen(QColor(200, 200, 200)))
                
                # Move to next track position
                y_position += self.track_height + self.track_spacing
    
    def time_to_position(self, time_value):
        """Convert a time value to an x-position"""
        if self.video_duration <= 0:
            ratio = 0
        else:
            ratio = time_value / self.video_duration
            ratio = max(0, min(1, ratio))  # Clamp between 0 and 1
        axis_width = self.width() - self.margin_left - self.margin_right
        return self.margin_left + (ratio * axis_width)
    
    def format_time(self, seconds):
        """Format time in seconds to a human-readable string"""
        minutes = int(seconds / 60)
        seconds = seconds % 60
        return f"{minutes}m{seconds:.2f}s"
    
    def render_to_image(self, image_format="PNG", dpi=300):
        """Render the visualization to an image with the specified format and DPI"""
        # Calculate pixel dimensions based on DPI
        inches_width = self.width() / 96  # Assuming screen DPI is 96
        inches_height = self.height() / 96
        
        pixel_width = int(inches_width * dpi)
        pixel_height = int(inches_height * dpi)
        
        # Create QImage
        image = QImage(pixel_width, pixel_height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        
        # Create painter for the image
        painter = QPainter(image)
        
        # Scale the painter to account for DPI
        scale_factor = dpi / 96
        painter.scale(scale_factor, scale_factor)
        
        # Render onto the image
        self.render(painter)
        
        # End painting
        painter.end()
        
        return image, None


def show_visualization_dialog(parent, video_name, state_events, point_events, video_duration, 
                             parse_time_func, center_window_func, output_dir):
    """
    Create and show the visualization dialog for annotations.
    
    Parameters:
        parent: The parent window
        video_name: Name of the video being annotated
        state_events: List of state annotation events
        point_events: List of point annotation events
        video_duration: Duration of the video in seconds
        parse_time_func: Function to parse time strings into seconds
        center_window_func: Function to center the dialog on screen
        output_dir: Output directory for saved files
    
    Returns:
        True if visualization was shown successfully, False otherwise
    """
    try:
        # Create visualization dialog
        viz_dialog = QDialog(parent)
        viz_dialog.setWindowTitle(f"Annotation Visualization - {video_name}")
        viz_dialog.setModal(True)
        
        # Calculate 90% of screen dimensions
        screen = parent.screen()
        viz_width = int(screen.availableGeometry().width() * 0.9)
        viz_height = int(screen.availableGeometry().height() * 0.9)
        
        # Center the dialog
        center_window_func(viz_dialog, viz_width, viz_height)
        
        # Create main layout
        main_layout = QVBoxLayout(viz_dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)
        
        # Create visualization widget
        timeline_widget = AnnotationsVisualizer(
            viz_dialog, 
            video_name, 
            state_events, 
            point_events,
            video_duration,
            parse_time_func
        )
        main_layout.addWidget(timeline_widget, 1)  # Add with stretch
        
        # Create export options frame
        export_frame = QFrame()
        export_layout = QHBoxLayout(export_frame)

        # File format selection
        format_label = QLabel("Export Format:")
        export_layout.addWidget(format_label)

        format_combo = QComboBox()
        format_combo.addItems(["PNG", "JPEG"])  # Removed PDF option
        export_layout.addWidget(format_combo)

        # DPI selection
        dpi_label = QLabel("Resolution (DPI):")
        export_layout.addWidget(dpi_label)

        dpi_spinner = QSpinBox()
        dpi_spinner.setRange(100, 900)
        dpi_spinner.setValue(300)
        dpi_spinner.setSingleStep(100)
        export_layout.addWidget(dpi_spinner)

        # Add spacer
        export_layout.addStretch(1)

        # Export button
        export_button = QPushButton("Export")
        export_layout.addWidget(export_button)
        
        # OK button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(viz_dialog.accept)
        export_layout.addWidget(ok_button)
        
        main_layout.addWidget(export_frame)
        
        # Define export function
        def export_visualization():
            # Get export settings
            export_format = format_combo.currentText()
            dpi = dpi_spinner.value()
            
            # Get file extension and filter
            if export_format.upper() == "PNG":
                file_ext = ".png"
                file_filter = "PNG Images (*.png)"
            elif export_format.upper() == "JPEG":
                file_ext = ".jpg"
                file_filter = "JPEG Images (*.jpg *.jpeg)"
            else:
                # Default to PNG
                file_ext = ".png"
                file_filter = "PNG Images (*.png)"
            
            # Ask for save location
            default_name = f"{video_name}_annotations{file_ext}"
            file_path, _ = QFileDialog.getSaveFileName(
                viz_dialog,
                "Save Visualization",
                os.path.join(output_dir, default_name),
                file_filter
            )
            
            if not file_path:
                return  # User canceled
            
            try:
                # Generate image
                image, _ = timeline_widget.render_to_image(export_format, dpi)
                
                # Save image
                image.save(file_path)
                
                QMessageBox.information(
                    viz_dialog,
                    "Export Successful",
                    "Visualization exported successfully"
                )
                
            except Exception as e:
                QMessageBox.critical(
                    viz_dialog,
                    "Export Error",
                    f"Failed to export visualization: {str(e)}"
                )
        
        # Connect export button to function
        export_button.clicked.connect(export_visualization)
        
        # Show dialog
        result = viz_dialog.exec()
        
        return True
        
    except Exception as e:
        print(f"Error in visualization: {e}")
        QMessageBox.critical(
            parent,
            "Visualization Error",
            f"Failed to create visualization: {str(e)}"
        )
        return False