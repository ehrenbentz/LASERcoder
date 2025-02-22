import os
import csv
import json
import tkinter as tk
from config_manager import ConfigManager
from files_manager import FilesManager
from behavior_key_editor import BehaviorKeyEditor
from screeninfo import get_monitors

class SetupManager:
    def __init__(self, parent, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.root = tk.Toplevel(parent)
        self.root.transient(parent)
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.start_video_flag = False
        
        # Initialize config manager and directories
        self.output_dir = self.config_manager.get_output_dir()
        self.behavior_key_dir = None
        self.annotations_dir = None
        self.resume_dir = None
        
        # Initialize file paths
        self.video_path = None
        self.video_name = ""
        self.annotations_file = ""
        self.session_state_file = ""
        self.behavior_key_file = None
        self.saved_state = None
        self.start_frame = 0
        
        # Initialize windows
        self.ask_resume_window = None
        
        # Start the setup process
        self.root.withdraw()  # Hide initially
        self.root.after(100, self.start_setup)  # Schedule setup after window creation

    def start_setup(self):
        """Initial setup process to get the output directory and video file."""
        try:
            files_manager = FilesManager(
                self.root,
                initial_output_dir=self.config_manager.get_output_dir(),
                initial_video_dir=self.config_manager.get_video_dir()
            )
            
            # Wait for FilesManager to complete
            self.root.wait_window(files_manager)
            
            # Check if files were selected
            if hasattr(files_manager, 'output_dir') and hasattr(files_manager, 'selected_video_file'):
                if files_manager.output_dir and files_manager.selected_video_file:
                    # Update configuration with new directories
                    self.config_manager.update_output_dir(files_manager.output_dir)
                    self.config_manager.update_video_dir(files_manager.selected_video_file)
                    
                    self.output_dir = files_manager.output_dir
                    self.video_path = files_manager.selected_video_file
                    self.video_name = os.path.basename(self.video_path).split('.')[0]
                    self.initialize_output_dir()
                    self.initialize_file_paths()
                    print(f"Session state file: {self.session_state_file}")
                    self.check_existing_session()
                else:
                    print("No video or output directory selected. Exiting.")
                    self.on_closing()
            else:
                print("FilesManager did not complete properly. Exiting.")
                self.on_closing()
                
        except Exception as e:
            print(f"Error in start_setup: {e}")
            self.on_closing()

    def initialize_output_dir(self):
        """Create the subdirectory structure based on the selected output directory."""
        self.behavior_key_dir = os.path.join(self.output_dir, "Behavior_Keys")
        self.annotations_dir = os.path.join(self.output_dir, "Annotations")
        self.resume_dir = os.path.join(self.output_dir, "Resume")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.behavior_key_dir, exist_ok=True)
        os.makedirs(self.annotations_dir, exist_ok=True)
        os.makedirs(self.resume_dir, exist_ok=True)
        print(f"Initialized output directories:\n - {self.output_dir}\n - {self.behavior_key_dir}\n - {self.annotations_dir}\n - {self.resume_dir}")

    def initialize_file_paths(self):
        """Initialize file paths for annotations and session state."""
        self.annotations_file = os.path.join(self.annotations_dir, f"{self.video_name}_Annotations.csv")
        self.session_state_file = os.path.join(self.resume_dir, f"{self.video_name}_session_state.json")

    def create_empty_files(self):
        """Create new empty annotation and session state files."""
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
                'Manual_Edit'
                'Notes'
            ])
        print(f"Created new annotations file: {self.annotations_file}")

        # Create empty session state file
        with open(self.session_state_file, 'w') as f:
            json.dump({"timestamp_ms": 0}, f)
        print(f"Created new session state file: {self.session_state_file}")

    def check_existing_session(self):
        """Check if a previous session exists and handle accordingly."""
        if os.path.exists(self.session_state_file):
            with open(self.session_state_file, 'r') as f:
                self.saved_state = json.load(f)
                # Convert from milliseconds to seconds if using old format
                if 'timestamp_ms' in self.saved_state:
                    self.saved_state['timestamp_sec'] = self.saved_state['timestamp_ms'] / 1000.0
            self.ask_resume(
                self.video_name,
                on_resume=self.resume_session,
                on_start_over=self.confirm_start_over,
                on_cancel=self.on_closing
            )
        else:
            self.start_frame = 0
            self.saved_state = None
            self.create_empty_files()
            self.show_behavior_key_editor()

    def ask_resume(self, video_name, on_resume, on_start_over, on_cancel):
        """Show dialog asking user if they want to resume previous session."""
        if self.ask_resume_window is not None and self.ask_resume_window.winfo_exists():
            self.ask_resume_window.destroy()
            
        self.ask_resume_window = tk.Toplevel(self.root)
        self.ask_resume_window.withdraw()
        self.ask_resume_window.title("Resume")
        self.ask_resume_window.protocol("WM_DELETE_WINDOW", on_cancel)
        
        label = tk.Label(self.ask_resume_window,
                        text=f"A previous session was found for {video_name}.\n\nWhat would you like to do?",
                        font=("Helvetica", 12))  # Added font size
        label.pack(pady=20)  # Increased padding
        
        button_frame = tk.Frame(self.ask_resume_window)
        button_frame.pack(pady=20)  # Increased padding
        
        def handle_resume():
            self.close_resume_window()
            on_resume()

        def handle_start_over():
            self.close_resume_window()
            on_start_over()
            
        def handle_cancel():
            self.close_resume_window()
            on_cancel()
        
        # Added font size to all buttons
        resume_button = tk.Button(
            button_frame, text="Resume", 
            command=handle_resume,
            font=("Helvetica", 12))
        resume_button.pack(side=tk.LEFT, padx=15)  # Increased padding
        
        start_over_button = tk.Button(
            button_frame, text="Start Over", 
            command=handle_start_over,
            font=("Helvetica", 12))
        start_over_button.pack(side=tk.LEFT, padx=15)  # Increased padding
        
        cancel_button = tk.Button(
            button_frame, text="Cancel", 
            command=handle_cancel,
            font=("Helvetica", 12))
        cancel_button.pack(side=tk.LEFT, padx=15)  # Increased padding
        
        self.center_window(self.ask_resume_window, 500, 200)  # Increased window size
        self.ask_resume_window.grab_set()
        self.ask_resume_window.deiconify()

    def confirm_start_over(self):
        """Show confirmation dialog for starting over and handle response."""
        confirm_dialog = tk.Toplevel(self.root)
        confirm_dialog.withdraw()
        confirm_dialog.title("Confirm Start Over")
        
        # Define on_cancel before setting it as protocol
        def on_cancel():
            confirm_dialog.destroy()
            self.ask_resume(
                self.video_name,
                on_resume=self.resume_session,
                on_start_over=self.confirm_start_over,
                on_cancel=self.on_closing
            )
        
        confirm_dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        
        label = tk.Label(confirm_dialog, 
                        text=f"Are you sure?\n\nStarting over will delete all current annotations for\n{self.video_name}",
                        font=('TkDefaultFont', 12))
        label.pack(pady=10)
        
        button_frame = tk.Frame(confirm_dialog)
        button_frame.pack(pady=10)
        
        def on_confirm():
            # Delete existing files
            files_to_delete = [self.session_state_file, self.annotations_file]
            for file_path in files_to_delete:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Deleted file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")
            # Reset state
            self.start_frame = 0
            self.saved_state = None
            
            # Create new empty files
            self.create_empty_files()
            
            confirm_dialog.destroy()
            self.show_behavior_key_editor()
        
        yes_button = tk.Button(button_frame, text="Yes", command=on_confirm, font=('TkDefaultFont', 12))
        yes_button.pack(side=tk.LEFT, padx=10)
        
        no_button = tk.Button(button_frame, text="No", command=on_cancel, font=('TkDefaultFont', 12))
        no_button.pack(side=tk.LEFT, padx=10)
        
        self.center_window(confirm_dialog, 400, 150)
        confirm_dialog.grab_set()
        confirm_dialog.deiconify()

    def resume_session(self):
        """Resume the previous session."""
        if self.saved_state:
            self.start_frame = self.saved_state.get('current_frame', 0)
        else:
            self.start_frame = 0
        self.show_behavior_key_editor()

    def close_resume_window(self):
        """Close the resume dialog window."""
        if self.ask_resume_window is not None and self.ask_resume_window.winfo_exists():
            self.ask_resume_window.destroy()
            self.ask_resume_window = None

    def show_behavior_key_editor(self):
        """Show the behavior key editor dialog."""
        behavior_editor = BehaviorKeyEditor(
            self.root,
            self.behavior_key_dir,
            on_start_video=self.on_start_video,
            on_cancel=self.on_closing,
            config_manager=self.config_manager
        )

    def on_start_video(self, behavior_key_file):
        """Handle starting the video."""
        self.behavior_key_file = behavior_key_file
        self.start_video_flag = True
        self.root.destroy()

    def on_closing(self):
        """Handle window closing."""
        # Close any open dialogs
        if self.ask_resume_window and self.ask_resume_window.winfo_exists():
            self.ask_resume_window.destroy()
            
        # Destroy all child windows
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Toplevel) and widget.winfo_exists():
                widget.destroy()
                
        # Finally destroy the main window
        self.root.destroy()
        print("SetupManager closed.")

    def center_window(self, window, width, height):
        """Center a window on the primary monitor."""
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        x = primary.x + (primary.width // 2) - (width // 2)
        y = primary.y + (primary.height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.update_idletasks()