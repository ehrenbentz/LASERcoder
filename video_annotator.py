# video_annotator.py

import os
import platform
import json
import tkinter as tk
import time
from tkinter import ttk, messagebox
from screeninfo import get_monitors
import mpv
import csv

class VideoAnnotator(tk.Frame):
    def __init__(self, parent, video_path, session_state_file, behavior_key_file, output_dir):
        # Track states
        self.dialog_open = False  # Track if any dialog is open
        self.pressed_keys = set()

        # Initialize the parent Frame
        super().__init__(parent)
        self.parent = parent
        self.floating_windows = []  # List to track all floating windows
        # Pack the main frame into the parent window
        self.pack(fill=tk.BOTH, expand=True)

        # Bind floating windows to parent
        self.parent.bind("<Unmap>", self.update_floating_windows_visibility)
        self.parent.bind("<Map>", self.update_floating_windows_visibility)
        self.parent.bind("<FocusIn>", self.update_floating_windows_visibility)

        # Initialize variables from other modules
        self.video_path = video_path
        self.session_state_file = session_state_file
        self.behavior_key_file = behavior_key_file
        self.output_dir = output_dir

        # Initialize in order
        self.initialize_data_structures()
        self.setup_file_paths()
        self.configure_display()
        self.setup_layout_measurements()
        self.setup_grid_layout()
        self.create_video_frame()
        self.create_controls_toggle_buttons()
        self.initialize_mpv_player()
        self.create_ui_components()
        self.load_data_and_start()
        self.setup_key_bindings()

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
        # Use the provided output_dir instead of os.getcwd()
        self.annotations_dir = os.path.join(self.output_dir, "Annotations")
        self.annotations_file = os.path.join(self.annotations_dir, f'{self.video_name}_Annotations.csv')

    def configure_display(self):
        """Configure display settings and window properties"""
        # Get primary monitor information
        monitors = get_monitors()
        primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
        
        # Set display dimensions
        self.display_width = primary_monitor.width
        self.display_height = primary_monitor.height
        self.display_x = primary_monitor.x
        self.display_y = primary_monitor.y

        # Configure window
        self.parent.title(f"LaserTag  {self.video_path}")
        self.parent.geometry(f"{self.display_width}x{self.display_height}+{self.display_x}+{self.display_y}")
        
        # Platform-specific window settings
        if platform.system() == "Windows":
            self.parent.state('zoomed')
        elif platform.system() == "Darwin":
            self.parent.state('zoomed')
        elif platform.system() == "Linux":
            self.parent.attributes("-zoomed", True)

        # Set background color
        self.parent.configure(bg="black")
        self.configure(bg="black")

    def setup_layout_measurements(self):
        """Set up layout measurements based on display size"""
        self.panel_width = int(self.display_width * 0.20)
        self.panel_height = self.display_height - int(self.display_height * 0.1)
        self.progress_bar_height = int(self.display_height * 0.025)
        self.video_width = self.display_width - self.panel_width
        self.video_height = self.panel_height - self.progress_bar_height
        self.progress_bar_width = self.video_width

    def setup_grid_layout(self):
        """Configure the grid layout"""
        self.columnconfigure(0, minsize=self.video_width, weight=1)
        self.columnconfigure(1, minsize=self.panel_width, weight=1)
        self.rowconfigure(0, minsize=self.video_height, weight=0)
        self.rowconfigure(1, minsize=self.progress_bar_height, weight=0)

    def create_video_frame(self):
        """Create the video frame"""
        self.video_frame = tk.Frame(self, bg="black", width=self.video_width, height=self.video_height)
        self.video_frame.grid(row=0, column=0, sticky="nw")
        self.video_frame.grid_propagate(False)

    def initialize_mpv_player(self):
        # Get the window id from the Tkinter video frame.
        window_id = self.video_frame.winfo_id()
        # Create an MPV player with the window id, hardware decoding, "fast" profile, and set audio sync option.
        self.player = mpv.MPV(wid=str(window_id),
                              log_handler=print,
                              hwdec="auto-safe",
                              profile="fast",
                              background_color="000000")
        # Start playing the video.
        self.player.play(self.video_path)

    def create_ui_components(self):
        """Create and configure UI components"""
        # Set fonts
        self.progress_bar_font = ("Helvetica", 12, "bold")
        self.treeview_font = ("Helvetica", 12)
        self.treeview_heading_font = ("Helvetica", 10, "bold")

        # Configure ttk style
        style = ttk.Style()
        style.configure("Treeview", font=self.treeview_font)
        style.configure("Treeview.Heading", font=self.treeview_heading_font, padding=(0, 0))

        # Create progress bar
        self.create_progress_bar()
        # Create annotation panel
        self.create_annotation_panel()

    def create_progress_bar(self):
        """Create and configure the progress bar"""
        self.progress_frame = tk.Frame(
            self,
            bg="black",
            width=self.progress_bar_width,
            height=self.progress_bar_height,
            bd=0,
            highlightthickness=0,
        )
        self.progress_frame.grid(row=1, column=0, sticky="nw")
        self.progress_frame.grid_propagate(False)

        self.progress_bar_canvas = tk.Canvas(
            self.progress_frame,
            bg="black",
            width=self.progress_bar_width,
            height=self.progress_bar_height,
            bd=0,
            highlightthickness=0,
        )
        self.progress_bar_canvas.pack()
        self.progress_bar_canvas.bind("<Button-1>", self.on_progress_click)

    def create_controls_toggle_buttons(self):
        """Create two Toplevel windows with control buttons that float over the video."""
        # Create window for behavior toggle (upper left)
        self.behavior_toggle_window = tk.Toplevel(self.parent)
        self.behavior_toggle_window.overrideredirect(True)
        self.behavior_toggle_window.configure(bg='magenta')  # Use magenta as transparent color
        self.behavior_toggle_window.attributes('-transparentcolor', 'magenta')
        
        # Create window for controls (lower left)
        self.controls_window = tk.Toplevel(self.parent)
        self.controls_window.overrideredirect(True)
        self.controls_window.configure(bg='magenta')  # Use magenta as transparent color
        self.controls_window.attributes('-transparentcolor', 'magenta')
        
        # Create behavior toggle button
        self.behavior_toggle_button = tk.Button(
            self.behavior_toggle_window,
            text="☰",
            font=("Helvetica", 14),
            command=self.toggle_behavior_buttons,
            bg='lightgrey',  # Light background for buttons
            activebackground='grey'  # Darker when clicked
        )
        self.behavior_toggle_button.pack()
        
        # Create controls button
        self.controls_button = tk.Button(
            self.controls_window,
            text="⚙",
            font=("Helvetica", 14),
            command=self.toggle_floating_controls,
            bg='lightgrey',  # Light background for buttons
            activebackground='grey'  # Darker when clicked
        )
        self.controls_button.pack()
        
        self.update_idletasks()
        
        # Position the buttons
        video_x = self.video_frame.winfo_rootx()
        video_y = self.video_frame.winfo_rooty()
        margin = 10  # Distance from video edge
        
        # Position behavior toggle (upper left)
        self.behavior_toggle_window.geometry(f"+{video_x + margin}+{video_y + margin}")
        
        # Position controls button (lower left)
        self.controls_window.geometry(f"+{video_x + margin}+{video_y + self.video_height - 30}")

    def update_floating_windows_visibility(self, event):
        """Update visibility of all floating windows"""
        windows = []
        if hasattr(self, "behavior_toggle_window"):
            windows.append(self.behavior_toggle_window)
        if hasattr(self, "controls_window"):
            windows.append(self.controls_window)
        if (hasattr(self, "floating_controls_window") and 
            self.floating_controls_window is not None and 
            self.floating_controls_window.winfo_exists()):
            windows.append(self.floating_controls_window)
        if (hasattr(self, "behavior_buttons_window") and 
            self.behavior_buttons_window is not None and 
            self.behavior_buttons_window.winfo_exists()):
            windows.append(self.behavior_buttons_window)
            
        if self.parent.state() == "iconic":
            for w in windows:
                w.withdraw()
        else:
            for w in windows:
                w.deiconify()

    def toggle_floating_controls(self):
        """Toggle a Toplevel floating control panel over the video."""
        if (hasattr(self, 'floating_controls_window') and 
            self.floating_controls_window is not None and 
            self.floating_controls_window.winfo_exists()):
            self.floating_controls_window.destroy()
            self.floating_controls_window = None
        else:
            self.floating_controls_window = tk.Toplevel(self.parent)
            self.floating_controls_window.overrideredirect(True)
            # Set up a transparent gap if desired (using, e.g., black if not used by controls)
            self.floating_controls_window.attributes("-transparentcolor", "black")
            
            fc = tk.Frame(self.floating_controls_window, bg="black")
            fc.pack()
            
            btn_opts = {
                "font": ("Helvetica", 12),
                "width": 4,
                "height": 2,
                "fg": "grey10",  # Dark grey text
                "bd": 2,
                "relief": "raised"
            }
            
            tk.Button(fc, text="❮❮", command=lambda: self.seek_relative(-10000), **btn_opts).pack(side=tk.LEFT, padx=15)
            tk.Button(fc, text="❮", command=lambda: self.seek_relative(-1000), **btn_opts).pack(side=tk.LEFT, padx=15)
            tk.Button(fc, text="⏪", command=lambda: self.change_speed(-1), **btn_opts).pack(side=tk.LEFT, padx=15)
            self.play_pause_btn = tk.Button(fc, text="■", command=self.toggle_play_pause, **btn_opts)
            self.play_pause_btn.pack(side=tk.LEFT, padx=10)
            tk.Button(fc, text="⏩", command=lambda: self.change_speed(1), **btn_opts).pack(side=tk.LEFT, padx=15)
            tk.Button(fc, text="❯", command=lambda: self.seek_relative(1000), **btn_opts).pack(side=tk.LEFT, padx=15)
            tk.Button(fc, text="❯❯", command=lambda: self.seek_relative(10000), **btn_opts).pack(side=tk.LEFT, padx=15)
            
            self.update_idletasks()
            # Position the floating controls centered along the bottom of the video frame
            video_x = self.video_frame.winfo_rootx()
            video_y = self.video_frame.winfo_rooty()
            fc_width = fc.winfo_reqwidth()
            fc_height = fc.winfo_reqheight()
            new_x = video_x + (self.video_width - fc_width) // 2
            new_y = video_y + self.video_height - fc_height
            self.floating_controls_window.geometry(f"+{new_x}+{new_y}")

    def toggle_play_pause(self):
        """Toggle play/pause and update the play/pause button icon."""
        self.toggle_play()
        self.update_play_pause_icon()

    def update_play_pause_icon(self):
        """Update the icon on the play/pause button."""
        if self.player.pause:
            self.play_pause_btn.config(text="▶")
        else:
            self.play_pause_btn.config(text="■")

    def create_behavior_buttons(self):
        """Create a Toplevel window with floating buttons at the left side of the video window.
           Organize buttons in two distinct rows - Point behaviors on top row, State behaviors on bottom row.
           Only show behavior Names, with distinct colors for each behavior type.
        """
        self.behavior_buttons_window = tk.Toplevel(self.parent)
        self.behavior_buttons_window.overrideredirect(True)
        transparent_color = "magenta"
        self.behavior_buttons_window.configure(bg=transparent_color)
        self.behavior_buttons_window.attributes("-transparentcolor", transparent_color)
        
        # Main container
        container = tk.Frame(self.behavior_buttons_window, bg=transparent_color)
        container.pack(anchor=tk.W)  # Anchor to west (left)
        
        # Create separate frames for Point and State behaviors
        point_frame = tk.Frame(container, bg=transparent_color)
        point_frame.pack(fill=tk.X, pady=(5, 2))
        
        state_frame = tk.Frame(container, bg=transparent_color)
        state_frame.pack(fill=tk.X, pady=(2, 5))
        
        # Base button options
        base_btn_opts = {
            "font": ("Helvetica", 12),
            "width": 12,
            "height": 1,
            "bd": 1,
            "relief": "raised"
        }
        
        # Updated options for each behavior type
        point_btn_opts = {
            **base_btn_opts,
            "bg": "lightgrey",      # Light grey for Point behaviors
            "fg": "black",
            "activebackground": "grey"
        }
        
        state_btn_opts = {
            **base_btn_opts,
            "bg": "darkgrey",       # Dark grey for State behaviors
            "fg": "black",
            "activebackground": "grey"
        }
        
        # Sort behaviors by type
        point_behaviors = []
        state_behaviors = []
        
        for behavior in self.behaviors:
            name, key, btype, _ = behavior
            if not name:  # Skip behaviors with no name
                continue
            if btype.lower() == "point":
                point_behaviors.append((name, key))
            else:
                state_behaviors.append((name, key))
        
        # Create Point behavior buttons (top row)
        for name, key in point_behaviors:
            b = tk.Button(point_frame, 
                          text=name,
                          command=lambda k=key: self.add_annotation_for_behavior(k),
                          **point_btn_opts)
            b.pack(side=tk.LEFT, padx=2)
        
        # Create State behavior buttons (bottom row)
        for name, key in state_behaviors:
            b = tk.Button(state_frame,
                          text=name,
                          command=lambda k=key: self.add_annotation_for_behavior(k),
                          **state_btn_opts)
            b.pack(side=tk.LEFT, padx=2)
        
        self.update_idletasks()
        
        # Position the window shifted to the right of the toggle button to avoid overlap.
        video_x = self.video_frame.winfo_rootx()
        video_y = self.video_frame.winfo_rooty()
        margin = 10  # Original margin from the video frame edge
        
        # Determine the width of the toggle button (if available) to offset the behavior buttons window.
        toggle_width = self.behavior_toggle_button.winfo_width() if hasattr(self, 'behavior_toggle_button') else 0
        new_x = video_x + margin + toggle_width + 10  # Additional 10-pixel offset from the toggle button
        new_y = video_y + margin  # 10 pixels from the top edge
        self.behavior_buttons_window.geometry(f"+{new_x}+{new_y}")
        self.floating_windows.append(self.behavior_buttons_window)

    def toggle_behavior_buttons(self):
        """Toggle the behavior buttons window on and off."""
        if (hasattr(self, "behavior_buttons_window") and 
            self.behavior_buttons_window is not None and 
            self.behavior_buttons_window.winfo_exists()):
            self.behavior_buttons_window.destroy()
            self.behavior_buttons_window = None
        else:
            self.create_behavior_buttons()

    def add_annotation_for_behavior(self, key):
        """Simulate a key-press for the given behavior key to add an annotation."""
        key = key.lower()
        if key in self.behavior_map:
            behavior_info = self.behavior_map[key]
            current_time = self.player.time_pos or 0
            formatted_time = self.format_time_human_readable(current_time)
            if behavior_info["Type"] == "State":
                self.handle_state_behavior(key, current_time, formatted_time)
            elif behavior_info["Type"] == "Point":
                # Prevent duplicate annotations
                if any(evt["Name"] == behavior_info["Name"] and evt["time"] == formatted_time for evt in self.point_events):
                    return
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
                    "Manual_Edit": "False"
                }
                self.append_annotation(record)
                self.point_events.append({
                    "Name": behavior_info["Name"],
                    "time": formatted_time,
                    "Manual_Edit": False
                })
                self.used_point_behaviors.add(key)
                self.parent.after(100, lambda: self.used_point_behaviors.discard(key))
                self.update_annotations()
                self.populate_behavior_treeviews()

    def load_data_and_start(self):
        """Load data and start playback"""
        self.load_behaviors()
        self.load_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()
        self.initialize_progress_bar()
        self.load_session_state()
        self.auto_save_session_state()

        # Process all the geometry configurations before showing the window
        self.parent.update_idletasks()
        self.parent.deiconify()
        self.parent.focus_force()


    def setup_key_bindings(self):
        """Set up all key bindings with dialog blocking"""
        def create_blocked_handler(handler):
            """Create a handler that only executes if no dialog is open"""
            def blocked_handler(event):
                if not self.dialog_open:
                    return handler(event)
            return blocked_handler

        small_skip = 1000
        med_skip = 5000
        large_skip = 10000

        # Define all the key bindings with blocking handlers
        key_bindings = {
            # Toggle play/pause
            "<space>": create_blocked_handler(self.toggle_play),

            # Small skip
            "<Shift-Right>": create_blocked_handler(lambda e: self.seek_relative(small_skip)),
            "<Shift-Left>": create_blocked_handler(lambda e: self.seek_relative(-small_skip)),
            "<D>": create_blocked_handler(lambda e: self.seek_relative(small_skip)),
            "<A>": create_blocked_handler(lambda e: self.seek_relative(-small_skip)),

            # Medium skip
            "<Right>": create_blocked_handler(lambda e: self.seek_relative(med_skip)),
            "<Left>": create_blocked_handler(lambda e: self.seek_relative(-med_skip)),
            "<d>": create_blocked_handler(lambda e: self.seek_relative(med_skip)),
            "<a>": create_blocked_handler(lambda e: self.seek_relative(-med_skip)),

            # Large skip
            "<w>": create_blocked_handler(lambda e: self.seek_relative(large_skip)),
            "<s>": create_blocked_handler(lambda e: self.seek_relative(-large_skip)),

            # Change playback speed
            "=": create_blocked_handler(lambda e: self.change_speed(1)),
            "+": create_blocked_handler(lambda e: self.change_speed(1)),
            "-": create_blocked_handler(lambda e: self.change_speed(-1)),
            "_": create_blocked_handler(lambda e: self.change_speed(-1)),

            # Other bindings
            "<Escape>": lambda e: self.on_closing(),  # Escape should always work
            "<Delete>": create_blocked_handler(self.delete_annotation_key),
            "<Control-z>": create_blocked_handler(self.undo_delete),
            "<Key>": self.on_key_press  # This one is already handled in on_key_press
        }

        # Bind all the key combinations
        for key, callback in key_bindings.items():
            self.parent.bind_all(key, callback)
        
        # Add key release binding separately (not part of the dictionary)
        self.parent.bind_all("<KeyRelease>", self.on_key_release)
        
        # Set window close protocol
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        if (self.player.duration or 0) > 0:
            self.player.time_pos = timestamp_sec
            print(f"Resumed session state at {timestamp_sec:.2f} sec.")
        else:
            self.after(200, lambda: self.schedule_resume(timestamp_sec))

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
        self.after(5000, self.auto_save_session_state)
        # Print the current player time (or 0 if not available)
        current_time = self.player.time_pos or 0
        print(f"Saved Session State: {current_time}")

    def create_annotation_panel(self):
            print(f"Annotation Panel Width: {self.panel_width}")

            # Calculate the available height for the annotation panel
            available_height = self.panel_height - self.progress_bar_height
            # Calculate equal height for each pane
            pane_height = (available_height - 40) // 4  # Subtract some padding space

            # Annotation Panel Frame (Right)
            self.annotation_border_frame = tk.Frame(self, bg="grey", bd=2, relief="solid", height=available_height)
            self.annotation_border_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=3, pady=0)
            self.annotation_frame = tk.Frame(self.annotation_border_frame, bg="gray",
                                           width=self.panel_width, height=available_height)
            self.annotation_frame.pack(fill="both", expand=True, padx=3, pady=0)

            # ------------------- State Behaviors Pane -------------------
            state_frame = tk.Frame(self.annotation_frame, bg="gray", height=pane_height)
            state_frame.pack(fill="x", pady=(0, 5))
            state_frame.pack_propagate(False)  # Prevent frame from shrinking
            
            state_label = tk.Label(state_frame, text="State Behaviors", bg="gray", fg="white",
                                 font=("Helvetica", 14, "bold"))
            state_label.pack(anchor="w")

            # Create Treeview and scrollbar with fixed height
            self.state_behaviors_tree = ttk.Treeview(state_frame, columns=("Name", "Key", "ME Group"),
                                                   show="headings", height=6)  # Adjusted height
            self.state_behaviors_tree.heading("Name", text="Name")
            self.state_behaviors_tree.heading("Key", text="Key")
            self.state_behaviors_tree.heading("ME Group", text="ME Group")
            self.state_behaviors_tree.column("Name", width=int(self.panel_width * 0.5))
            self.state_behaviors_tree.column("Key", width=int(self.panel_width * 0.15), anchor="center")
            self.state_behaviors_tree.column("ME Group", width=int(self.panel_width * 0.25), anchor="center")

            state_scrollbar = ttk.Scrollbar(state_frame, orient="vertical",
                                          command=self.state_behaviors_tree.yview)
            self.state_behaviors_tree.configure(yscrollcommand=state_scrollbar.set)
            state_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.state_behaviors_tree.pack(side=tk.LEFT, fill="both", expand=True)

            # ------------------- Point Behaviors Pane -------------------
            point_frame = tk.Frame(self.annotation_frame, bg="gray", height=pane_height)
            point_frame.pack(fill="x", pady=(0, 5))
            point_frame.pack_propagate(False)  # Prevent frame from shrinking

            point_label = tk.Label(point_frame, text="Point Behaviors", bg="gray", fg="white",
                                 font=("Helvetica", 14, "bold"))
            point_label.pack(anchor="w")

            self.point_behaviors_tree = ttk.Treeview(point_frame, columns=("Name", "Key"),
                                                   show="headings", height=6)  # Adjusted height
            self.point_behaviors_tree.heading("Name", text="Name")
            self.point_behaviors_tree.heading("Key", text="Key")
            self.point_behaviors_tree.column("Name", width=int(self.panel_width * 0.5))
            self.point_behaviors_tree.column("Key", width=int(self.panel_width * 0.25), anchor="center")

            point_scrollbar = ttk.Scrollbar(point_frame, orient="vertical",
                                          command=self.point_behaviors_tree.yview)
            self.point_behaviors_tree.configure(yscrollcommand=point_scrollbar.set)
            point_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.point_behaviors_tree.pack(side=tk.LEFT, fill="both", expand=True)

            # ------------------- State Annotations Pane -------------------
            state_anno_frame = tk.Frame(self.annotation_frame, bg="gray", height=pane_height)
            state_anno_frame.pack(fill="x", pady=(0, 5))
            state_anno_frame.pack_propagate(False)  # Prevent frame from shrinking

            state_anno_label_frame = tk.Frame(state_anno_frame, bg="gray")
            state_anno_label_frame.pack(fill="x")
            tk.Label(state_anno_label_frame, text="State Annotations", bg="gray", fg="white",
                    font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
            tk.Button(state_anno_label_frame, text="Sort", 
                     font=("Helvetica", 12), command=self.sort_state_annotations).pack(side=tk.RIGHT, padx=10, pady=0)

            self.state_annotations_tree = ttk.Treeview(state_anno_frame, 
                                                     columns=("Name", "Start", "End"),
                                                     show="headings",
                                                     height=6)  # Adjusted height
            self.state_annotations_tree.heading("Name", text="Name")
            self.state_annotations_tree.heading("Start", text="Start")
            self.state_annotations_tree.heading("End", text="End")
            self.state_annotations_tree.column("Name", width=int(self.panel_width * 0.33))
            self.state_annotations_tree.column("Start", width=int(self.panel_width * 0.25))
            self.state_annotations_tree.column("End", width=int(self.panel_width * 0.25))
            
            self.state_annotations_tree.bind("<Button-3>", self.show_annotation_menu)
            
            state_anno_scrollbar = ttk.Scrollbar(state_anno_frame, orient="vertical",
                                               command=self.state_annotations_tree.yview)
            self.state_annotations_tree.configure(yscrollcommand=state_anno_scrollbar.set)
            state_anno_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.state_annotations_tree.pack(side=tk.LEFT, fill="both", expand=True)

            # ------------------- Point Annotations Pane -------------------
            point_anno_frame = tk.Frame(self.annotation_frame, bg="gray", height=pane_height)
            point_anno_frame.pack(fill="x", pady=(0, 5))
            point_anno_frame.pack_propagate(False)  # Prevent frame from shrinking

            point_anno_label_frame = tk.Frame(point_anno_frame, bg="gray")
            point_anno_label_frame.pack(fill="x")
            tk.Label(point_anno_label_frame, text="Point Annotations", bg="gray", fg="white",
                    font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
            tk.Button(point_anno_label_frame, text="Sort", 
                     font=("Helvetica", 12), command=self.sort_point_annotations).pack(side=tk.RIGHT, padx=10, pady=0)

            self.point_annotations_tree = ttk.Treeview(point_anno_frame,
                                                     columns=("Name", "Time"),
                                                     show="headings",
                                                     height=6)  # Adjusted height
            self.point_annotations_tree.heading("Name", text="Name")
            self.point_annotations_tree.heading("Time", text="Time")
            self.point_annotations_tree.column("Name", width=int(self.panel_width * 0.33))
            self.point_annotations_tree.column("Time", width=int(self.panel_width * 0.5), anchor="center")

            self.point_annotations_tree.bind("<Button-3>", self.show_annotation_menu)

            point_anno_scrollbar = ttk.Scrollbar(point_anno_frame, orient="vertical",
                                               command=self.point_annotations_tree.yview)
            self.point_annotations_tree.configure(yscrollcommand=point_anno_scrollbar.set)
            point_anno_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.point_annotations_tree.pack(side=tk.LEFT, fill="both", expand=True)

            # ------------------- Bottom Buttons -------------------
            buttons_frame = tk.Frame(self.annotation_frame, bg="gray")
            buttons_frame.pack(fill="x", pady=5)
            
            visualize_button = tk.Button(buttons_frame, text="Visualize\nAnnotations",
                                       command=self.visualize_annotations,
                                       width=16, font=("Helvetica", 12), wraplength=int(self.panel_width * 0.3))
            visualize_button.pack(side=tk.LEFT, padx=10, pady=5)

            summary_button = tk.Button(buttons_frame, text="Summary\nStatistics",
                                     command=self.generate_summary_statistics,
                                     width=16, font=("Helvetica", 12), wraplength=int(self.panel_width * 0.3))
            summary_button.pack(side=tk.LEFT, padx=25, pady=5, anchor="center")

    def load_behaviors(self):
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
        """
        Read annotations from the CSV file (expected at self.annotations_file)
        and load them into the in-memory lists as well as update the treeviews.
        """
        # First, clear any existing in-memory events
        self.state_events.clear()
        self.point_events.clear()

        print(f"Loading annotations from: {self.annotations_file}")

        with open(self.annotations_file, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                annotation_type = row.get("Type", "").strip().lower()
                name = row.get("Name", "").strip()

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
                        'Mutually_Exclusive': row.get("Mutually_Exclusive", "False")
                    })

                elif annotation_type == "point":
                    h_start = row.get("H_Start", "").strip()
                    self.point_events.append({
                        'Name': name,
                        'time': h_start,
                        'Manual_Edit': row.get("Manual_Edit", "False")
                    })


    def update_annotations(self):
        """
        Clear and repopulate the annotation treeviews using in-memory lists.
        """
        # Update State Annotations
        self.state_annotations_tree.delete(*self.state_annotations_tree.get_children())
        for event in self.state_events:
            name = event['Name']
            start_time = self.format_time_human_readable(event['start_time'])
            end_time = self.format_time_human_readable(event['end_time']) if event['end_time'] else ""
            self.state_annotations_tree.insert('', tk.END, values=(name, start_time, end_time))
        state_items = self.state_annotations_tree.get_children()
        if state_items:
            self.state_annotations_tree.see(state_items[-1])
            self.state_annotations_tree.yview_moveto(1)

        # Update Point Annotations
        self.point_annotations_tree.delete(*self.point_annotations_tree.get_children())
        for event in self.point_events:
            name = event['Name']
            time_ = event['time']
            self.point_annotations_tree.insert('', tk.END, values=(name, time_))
        point_items = self.point_annotations_tree.get_children()
        if point_items:
            self.point_annotations_tree.see(point_items[-1])
            self.point_annotations_tree.yview_moveto(1)

    def populate_behavior_treeviews(self):
        """
        Populate both the state and point behavior treeviews using self.behaviors.
        Highlights active state behaviors and briefly highlights point behaviors when used.
        """
        # Clear existing entries
        self.state_behaviors_tree.delete(*self.state_behaviors_tree.get_children())
        self.point_behaviors_tree.delete(*self.point_behaviors_tree.get_children())

        # Configure tags for highlighting
        self.state_behaviors_tree.tag_configure("active", background="darkorange")
        self.point_behaviors_tree.tag_configure("highlight", background="dodgerblue")

        # Insert state behaviors
        for behavior in self.behaviors:
            name, key, b_type, me_group = behavior
            if b_type == "state":
                tag = ("active",) if key in self.active_state_behaviors else ()
                self.state_behaviors_tree.insert("", "end", values=(name, key, me_group), tags=tag)

        # Insert point behaviors (only two columns)
        for behavior in self.behaviors:
            name, key, b_type, _ = behavior
            if b_type == "point":
                tag = ("highlight",) if key in self.used_point_behaviors else ()
                item_id = self.point_behaviors_tree.insert("", "end", values=(name, key), tags=tag)

                # Remove highlight after 250ms
                if key in self.used_point_behaviors:
                    self.parent.after(250, lambda i=item_id: self.remove_highlight(i))

    def remove_highlight(self, item_id):
        """Remove the highlight tag safely, only if the item exists."""
        if item_id in self.point_behaviors_tree.get_children():
            self.point_behaviors_tree.item(item_id, tags="")

    def on_key_press(self, event):
        # Block key presses if a dialog is open
        if self.dialog_open:
            return
            
        key = event.char.lower()
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
                # Prevent duplicate annotations
                if any(evt["Name"] == behavior_info["Name"] and evt["time"] == formatted_time for evt in self.point_events):
                    return
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
                    "Manual_Edit": "False"
                }
                self.append_annotation(record)
                self.point_events.append({
                    "Name": behavior_info["Name"],
                    "time": formatted_time,
                    "Manual_Edit": False
                })
                self.used_point_behaviors.add(key)
                self.parent.after(100, lambda: self.used_point_behaviors.discard(key))
                self.update_annotations()
                self.populate_behavior_treeviews()

    def handle_state_behavior(self, key, frame_timestamp, formatted_timestamp):
        """
        Handle state behavior key presses: if the behavior is already active, deactivate it (logging the end time);
        otherwise, start a new state event.
        """
        Name = self.state_behaviors.get(key)
        me_group = self.me_groups.get(key, None)
        if me_group:
            print(f"Key {key} belongs to ME Group {me_group}. Deactivating other behaviors in this group.")
            self.deactivate_me_group(me_group, frame_timestamp, current_behavior_key=key)
        if key in self.active_state_behaviors:
            # End the active state behavior
            start_time = self.active_state_behaviors.pop(key)
            duration = frame_timestamp - start_time
            human_readable_start_time = self.format_time_human_readable(start_time)
            human_readable_end_time = self.format_time_human_readable(frame_timestamp)
            machine_readable_start_time = self.format_time_machine_readable(start_time)
            machine_readable_end_time = self.format_time_machine_readable(frame_timestamp)
            machine_readable_duration = self.format_time_machine_readable(duration)
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
                "Manual_Edit": "False"
            }
            self.append_annotation(record)
            for event in self.state_events:
                if event['Name'] == Name and event['end_time'] is None:
                    event['end_time'] = frame_timestamp
                    break
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
                'Mutually_Exclusive': 'True' if me_group else 'False'
            })
            self.update_annotations()
            self.populate_behavior_treeviews()

    def deactivate_me_group(self, me_group, frame_timestamp, current_behavior_key):
        """
        Deactivate any active state behaviors belonging to the same ME group (except the current one).
        """
        keys_to_remove = []
        for key, start_time in list(self.active_state_behaviors.items()):
            if self.me_groups.get(key) == me_group and key != current_behavior_key:
                Name = self.state_behaviors.get(key)
                duration = frame_timestamp - start_time
                human_readable_start_time = self.format_time_human_readable(start_time)
                human_readable_end_time = self.format_time_human_readable(frame_timestamp)
                machine_readable_start_time = self.format_time_machine_readable(start_time)
                machine_readable_end_time = self.format_time_machine_readable(frame_timestamp)
                machine_readable_duration = self.format_time_machine_readable(duration)
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
                    "Manual_Edit": "False"
                }
                self.append_annotation(record)
                for event in self.state_events:
                    if event['Name'] == Name and event['end_time'] is None:
                        event['end_time'] = frame_timestamp
                        break
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self.active_state_behaviors.pop(key)
        self.update_annotations()
        self.populate_behavior_treeviews()

    def append_annotation(self, annotation_record):
        """
        Append an annotation record to the CSV file.
        Reads existing rows, appends the new record,
        writes to a temporary file, then replaces the original.
        """
        headers = ['Video','Name','Type','Mutually_Exclusive','H_Start','H_End','Start','End','Duration','Manual_Edit']
        rows = []
        if os.path.exists(self.annotations_file):
            with open(self.annotations_file, 'r', newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        rows.append(annotation_record)
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
        with open(self.annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Video', 'Name', 'Type', 'Mutually_Exclusive', 'H_Start', 'H_End', 'Start', 'End', 'Duration', 'Manual_Edit'])
            for event in self.state_events:
                start_time = self.format_time_machine_readable(event['start_time'])
                end_time = self.format_time_machine_readable(event['end_time']) if event['end_time'] is not None else 'NA'
                duration = self.format_time_machine_readable(event['end_time'] - event['start_time']) if event['end_time'] is not None else 'NA'
                H_start = self.format_time_human_readable(event['start_time'])
                H_end = self.format_time_human_readable(event['end_time']) if event['end_time'] is not None else 'NA'
                manual_edit = 'True' if event.get('Manual_Edit') else 'False'
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
                    manual_edit
                ])
            for event in self.point_events:
                time_machine = self.format_time_machine_readable(self.parse_time(event['time']))
                manual_edit = 'True' if event.get('Manual_Edit') else 'False'
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
                    manual_edit
                ])

    def save_point_annotation(self, new_entries, dialog, selected_annotation, old_start_time):
        """
        Saves the edited point annotation.

        Parameters:
          new_entries (dict): Contains Tkinter Entry widgets for 'Name' and 'H_Start'.
          dialog (Tkinter.Toplevel): The dialog window for editing.
          selected_annotation (dict): The original point annotation that was edited.
          old_start_time (str): The original human-readable start time used to identify the annotation.
        """
        new_name = new_entries['Name'].get().strip()
        new_h_start = new_entries['H_Start'].get().strip()

        if not new_name or not new_h_start:
            messagebox.showwarning("Invalid Input", "Both Name and Start Time are required.")
            return

        print(f"Updating point annotation from {selected_annotation} to {{'Name': '{new_name}', 'H_Start': '{new_h_start}'}}")

        # Convert the human-readable start time to machine-readable time (float seconds)
        new_start_time = self.parse_time(new_h_start)

        # Update the matching annotation in the in-memory list.
        for annotation in self.point_events:
            if annotation['Name'] == selected_annotation['Name'] and annotation['time'] == old_start_time:
                annotation['Name'] = new_name
                annotation['time'] = new_h_start
                # Optionally, if you wish to track machine time as well:
                annotation['start_time'] = new_start_time
                annotation['Manual_Edit'] = True
                break

        self.save_sorted_annotations()
        self.update_annotations()
        self.dialog_open = False
        dialog.destroy()


    def save_state_annotation(self, new_entries, dialog, selected_annotation, old_start_time):
        """
        Saves the edited state annotation.

        Parameters:
          new_entries (dict): Contains Tkinter Entry widgets for 'Name', 'H_Start', and 'H_End'.
          dialog (Tkinter.Toplevel): The dialog window for editing.
          selected_annotation (dict): The original state annotation that was edited.
          old_start_time (str): The original human-readable start time used to identify the annotation.
        """
        new_name = new_entries['Name'].get().strip()
        new_h_start = new_entries['H_Start'].get().strip()
        new_h_end = new_entries['H_End'].get().strip()

        if not new_name or not new_h_start or not new_h_end:
            messagebox.showwarning("Invalid Input", "Name, Start, and End times are required.")
            return

        print(f"Updating state annotation from {selected_annotation} to {{'Name': '{new_name}', 'H_Start': '{new_h_start}', 'H_End': '{new_h_end}'}}")

        # Convert human-readable times to machine-readable values (floats)
        new_start_time = self.parse_time(new_h_start)
        new_end_time = self.parse_time(new_h_end)

        # Update the matching annotation in the in-memory list.
        for annotation in self.state_events:
            # Identify the annotation using the old human-readable start time.
            if annotation['Name'] == selected_annotation['Name'] and self.format_time_human_readable(annotation.get('start_time', 0)) == old_start_time:
                annotation['Name'] = new_name
                annotation['H_Start'] = new_h_start
                annotation['H_End'] = new_h_end
                annotation['start_time'] = new_start_time
                annotation['end_time'] = new_end_time
                annotation['Manual_Edit'] = True
                break

        self.save_sorted_annotations()
        self.update_annotations()
        self.dialog_open = False
        dialog.destroy()


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

    # ----------------------- Playback Functions -----------------------
    def toggle_play(self, event=None):
        # Toggle the pause property: True means paused, False means playing.
        self.player.pause = not self.player.pause

    def refresh_paused_frame(self):
        if not self.player.is_playing():
            self.player.set_pause(0)
            self.update()
            self.after(20, lambda: self.player.set_pause(1))

    def step_frame_if_paused(self):
        if ndlf.player.is_playing():
            a.player.next_frame()

    def seek_relative(self, offset_ms):
        # Get current time (in seconds); default to 0 if None.
        current_sec = self.player.time_pos or 0
        # Convert offset from ms to seconds.
        offset_sec = offset_ms / 1000.0
        new_time = max(current_sec + offset_sec, 0)
        self.player.time_pos = new_time
        # Optionally, refresh the frame if paused.

    def change_speed(self, delta):
        """
        Example usage: update the playback speed, and also update the speed_text.
        """
        speed_steps = [0.5, 1, 2, 3, 5, 8, 10, 15, 20, 25]
        current_rate = self.player.speed
        try:
            index = speed_steps.index(current_rate)
        except ValueError:
            index = min(range(len(speed_steps)), key=lambda i: abs(speed_steps[i] - current_rate))
        new_index = max(0, min(len(speed_steps) - 1, index + (1 if delta > 0 else -1)))
        new_rate = speed_steps[new_index]
        if new_rate != current_rate:
            self.player.speed = new_rate
            print(f"New speed: {new_rate:.2f}x")

        # Now update the speed_text
        self.progress_bar_canvas.itemconfig("speed_text", text=f"({new_rate:.1f}x)")

    def initialize_progress_bar(self):
        # Clear any existing canvas elements.
        self.progress_bar_canvas.delete("all")
        bar_height = self.progress_bar_height
        # Draw the static background.
        self.progress_bar_canvas.create_rectangle(
            0, 0, self.progress_bar_width, bar_height,
            fill="grey", tags="background"
        )
        # Pre-create the progress rectangle (initially zero-width).
        self.progress_rect = self.progress_bar_canvas.create_rectangle(
            0, 0, 0, bar_height,
            fill="#454545", tags="progress_bar"
        )
        # Create the current-time text on the left.
        self.progress_bar_canvas.create_text(
            5, bar_height / 2, anchor="w",
            text="0m0.00s",
            fill="white",
            font=self.progress_bar_font,
            tags="time_text_left"
        )
        # Create the playback speed text (which will be updated via change_speed()).
        self.progress_bar_canvas.create_text(
            110, bar_height / 2, anchor="w",
            text="(1.0x)",
            fill="white",
            font=self.progress_bar_font,
            tags="speed_text"
        )
        # Get total media length from MPV (in seconds).
        total_sec = self.player.duration or 0
        if total_sec <= 0:
            # Media not yet loaded; try again in 250ms.
            self.after(250, self.initialize_progress_bar)
            return
        total_time_str = self.format_time_human_readable(total_sec)
        # Create the total-time text (on the right) once and never update it.
        self.progress_bar_canvas.create_text(
            self.progress_bar_width - 5, bar_height / 2, anchor="e",
            text=total_time_str,
            fill="white",
            font=self.progress_bar_font,
            tags="time_text_right"
        )
        # Start polling to update the current time and progress rectangle every 500ms.
        self.poll_progress_bar()

    def poll_progress_bar(self):
        """Update the progress bar and schedule the next update in 500ms."""
        self.update_progress_bar()
        total_sec = self.player.duration or 0
        current_sec = self.player.time_pos or 0
        # If near the end of the video (within 0.5 seconds), restart playback.
        if total_sec > 0 and current_sec >= total_sec - 0.5:
            print("Video ended. Restarting from beginning.")
            # Reload the video file, replacing the current one
            self.player.command("loadfile", self.video_path, "replace")
            # Ensure playback is resumed
            self.player.pause = False
        self.after(500, self.poll_progress_bar)

        if total_sec > 0 and current_sec >= total_sec - 0.5:
            print("Video ended. Restarting from beginning.")
            # Reload the video file, replacing the current one
            self.player.command("loadfile", self.video_path, "replace")
            # Ensure playback is resumed
            self.player.pause = False

    def update_progress_bar(self):
        """Update only the dynamic parts of the progress bar."""
        total_sec = self.player.duration or 0
        current_sec = self.player.time_pos or 0
        ratio = (current_sec / total_sec) if total_sec > 0 else 0
        progress = int(ratio * self.progress_bar_width)
        # Update the coordinates of the progress rectangle.
        self.progress_bar_canvas.coords(
            self.progress_rect,
            0, 0, progress, self.progress_bar_height
        )
        # Update the current time text (left).
        current_time_str = self.format_time_human_readable(current_sec)
        self.progress_bar_canvas.itemconfig("time_text_left", text=current_time_str)
        # Ensure the text items remain on top.
        self.progress_bar_canvas.tag_raise("time_text_left")
        self.progress_bar_canvas.tag_raise("time_text_right")
        self.progress_bar_canvas.tag_raise("speed_text")

    def on_progress_click(self, event):
        click_x = event.x
        ratio = click_x / self.progress_bar_width
        total_sec = self.player.duration or 0
        if total_sec > 0:
            # Calculate the target time in seconds and update MPV's time_pos.
            target_sec = ratio * total_sec
            self.player.time_pos = target_sec

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
            for attr in floating_attrs:
                if hasattr(self, attr):
                    win = getattr(self, attr)
                    if win is not None and win.winfo_exists():
                        win.destroy()
            
            # Additionally, destroy any windows tracked in self.floating_windows
            if hasattr(self, 'floating_windows'):
                for win in self.floating_windows:
                    if win is not None and win.winfo_exists():
                        win.destroy()
                self.floating_windows.clear()

            # Save session state and stop the player
            if hasattr(self, 'player') and self.player:
                self.save_session_state()
                self.player.pause = True
                self.player.stop()

            # Finally, destroy the main window
            self.parent.destroy()
        except Exception as e:
            print(f"Error during closing: {e}")
            self.parent.destroy()

    def visualize_annotations(self):
        self.dialog_open = True
        dialog = tk.Toplevel(self.parent)
        dialog.transient(self.parent)     # Make dialog dependent on the main window
        dialog.grab_set()                 # Prevent interaction with the main window
        dialog.focus_force()              # Bring dialog to the front
        dialog.attributes('-topmost', True)  # Ensure it stays above the main window

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.title("Visualize Annotations")
        self.center_window(dialog, width=300, height=150)

        tk.Label(dialog, text="Annotations visualization is\ncurrently under development.").pack(pady=20)
        tk.Button(dialog, text="OK", command=dialog.destroy).pack(pady=5)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.on_visualization_close(dialog))

    def generate_summary_statistics(self):
        self.dialog_open = True
        dialog = tk.Toplevel(self.parent)
        dialog.transient(self.parent)
        dialog.grab_set()
        dialog.focus_force()
        dialog.attributes('-topmost', True)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.title("Summary Statistics")
        self.center_window(dialog, width=300, height=150)

        tk.Label(dialog, text="Generating summary statistics is\ncurrently under development").pack(pady=20)
        tk.Button(dialog, text="OK", command=dialog.destroy).pack(pady=5)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.on_summary_close(dialog))

    def on_visualization_close(self, dialog):
        """Handle visualization dialog closing"""
        self.dialog_open = False
        dialog.destroy()

    def on_summary_close(self, dialog):
        """Handle summary dialog closing"""
        self.dialog_open = False
        dialog.destroy()

    def center_window(self, win, width, height):
        # Identify the primary monitor
        monitors = get_monitors()
        primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
        # Calculate center position within primary monitor
        x = primary_monitor.x + (primary_monitor.width // 2) - (width // 2)
        y = primary_monitor.y + (primary_monitor.height // 2) - (height // 2)
        # Apply geometry to window
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.update_idletasks()

    # --- Annotation Menu and Editing Methods ---
    def show_annotation_menu(self, event):
        self.dialog_open = True
        # Determine which treeview was clicked
        widget = event.widget
        self.selected_treeview = widget

        # Get selected item based on click location
        item_id = widget.identify_row(event.y)
        if not item_id:
            return

        widget.selection_set(item_id)
        self.selected_item = item_id

        # Determine the selected index from the appropriate treeview
        if self.selected_treeview == self.state_annotations_tree:
            self.selected_index = self.state_annotations_tree.index(self.selected_item)
        else:
            self.selected_index = self.point_annotations_tree.index(self.selected_item)

        # Create a popup menu (using self.parent instead of self.root)
        self.annotation_menu = tk.Menu(self.parent, tearoff=0)
        self.annotation_menu.add_command(label="Edit", command=self.edit_annotation)
        self.annotation_menu.add_command(label="Skip to Annotation", command=self.skip_to_annotation)
        self.annotation_menu.add_command(label="Delete", command=self.delete_annotation)
        self.annotation_menu.tk_popup(event.x_root, event.y_root)
        self.annotation_menu.bind('<Unmap>', lambda e: self.on_menu_close())

    def on_menu_close(self):
        """Handle menu closing"""
        self.dialog_open = False
        if hasattr(self, 'annotation_menu'):
            self.annotation_menu.destroy()

    def edit_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return
        if self.selected_treeview == self.state_annotations_tree:
            self.edit_state_annotation()
        else:
            self.edit_point_annotation()

    def edit_state_annotation(self):
        if self.selected_index is None:
            return
        self.dialog_open = True

        selected_annotation = self.state_events[self.selected_index]
        if selected_annotation['end_time'] is None:
            messagebox.showwarning("Edit Error", "Please end the state behavior before editing.")
            return

        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_Start', 'H_End')
        print(f"Editing state annotation: {latest_annotation}")

        if hasattr(self, 'edit_dialog') and self.edit_dialog is not None:
            self.edit_dialog.destroy()

        self.edit_dialog = tk.Toplevel(self.parent)
        self.edit_dialog.transient(self.parent)
        self.edit_dialog.grab_set()
        self.edit_dialog.focus_force()
        self.edit_dialog.attributes('-topmost', True)
        self.edit_dialog.protocol("WM_DELETE_WINDOW", self.on_edit_dialog_close)
        self.edit_dialog.title("Edit State Annotation")
        self.center_window(self.edit_dialog, width=250, height=300)

        # Bind the Enter key to trigger the save action
        self.edit_dialog.bind("<Return>", lambda event: self.save_state_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_Start']))

        # Display current annotation (non-editable)
        tk.Label(self.edit_dialog, text="Current Annotation").grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(self.edit_dialog, text="Name:").grid(row=1, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['Name']).grid(row=1, column=1)
        tk.Label(self.edit_dialog, text="Start:").grid(row=2, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_Start']).grid(row=2, column=1)
        tk.Label(self.edit_dialog, text="End:").grid(row=3, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_End']).grid(row=3, column=1)

        # Fields for new annotation values
        tk.Label(self.edit_dialog, text="New Annotation").grid(row=4, column=0, columnspan=2, pady=5)
        new_entries = {}
        new_fields = ['Name', 'H_Start', 'H_End']
        for i, field in enumerate(new_fields, start=5):
            tk.Label(self.edit_dialog, text=f"{field}:").grid(row=i, column=0)
            entry = tk.Entry(self.edit_dialog)
            entry.insert(0, latest_annotation.get(field, ""))
            entry.grid(row=i, column=1)
            new_entries[field] = entry

        save_button = tk.Button(
            self.edit_dialog, text="Save",
            command=lambda: self.save_state_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_Start'])
        )
        save_button.grid(row=i + 1, column=0, columnspan=2, pady=10)

    def edit_point_annotation(self):
        if self.active_state_behaviors:
            messagebox.showwarning("Active Annotation", "Please end the active state before editing.")
            return

        if self.selected_index is None:
            return
        self.dialog_open = True

        selected_annotation = self.point_events[self.selected_index]
        print(f"Editing point annotation: {selected_annotation}")

        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_Start')
        print(f"Latest annotation data for editing: {latest_annotation}")

        if hasattr(self, 'edit_dialog') and self.edit_dialog is not None:
            self.edit_dialog.destroy()

        self.edit_dialog = tk.Toplevel(self.parent)
        self.edit_dialog.transient(self.parent)
        self.edit_dialog.grab_set()
        self.edit_dialog.focus_force()
        self.edit_dialog.attributes('-topmost', True)
        self.edit_dialog.protocol("WM_DELETE_WINDOW", self.on_edit_dialog_close)
        self.edit_dialog.title("Edit Point Annotation")
        self.center_window(self.edit_dialog, width=275, height=250)

        self.edit_dialog.bind("<Return>", lambda event: self.save_point_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_Start']))

        tk.Label(self.edit_dialog, text="Current Annotation").grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(self.edit_dialog, text="Name:").grid(row=1, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['Name']).grid(row=1, column=1)
        tk.Label(self.edit_dialog, text="Start:").grid(row=2, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_Start']).grid(row=2, column=1)

        tk.Label(self.edit_dialog, text="New Annotation").grid(row=4, column=0, columnspan=2, pady=5)
        new_entries = {}
        new_fields = ['Name', 'H_Start']
        for i, field in enumerate(new_fields, start=5):
            tk.Label(self.edit_dialog, text=f"{field}:").grid(row=i, column=0)
            entry = tk.Entry(self.edit_dialog)
            entry.insert(0, latest_annotation.get(field, ""))
            entry.grid(row=i, column=1)
            new_entries[field] = entry

        save_button = tk.Button(
            self.edit_dialog, text="Save",
            command=lambda: self.save_point_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_Start'])
        )
        save_button.grid(row=i + 1, column=0, columnspan=2, pady=10)

    def load_annotation_data(self, annotation, *fields):
        latest_annotation = {field: "" for field in fields}
        print(f"Loading annotation data for {annotation}")
        with open(self.annotations_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # For state annotations, compare 'Name' and 'H_Start'
                if row['Name'] == annotation['Name'] and row['H_Start'] == self.format_time_human_readable(annotation.get('start_time', 0)):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    print(f"Found matching row: {latest_annotation}")
                    break
                # For point annotations, check H_Start only
                elif 'H_Start' in row and row['H_Start'] == annotation.get('time'):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    print(f"Found matching point row: {latest_annotation}")
                    break
        return latest_annotation

    def on_edit_dialog_close(self):
        """Update on_edit_dialog_close to reset dialog state"""
        self.dialog_open = False
        if hasattr(self, 'edit_dialog') and self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None

    def skip_to_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        values = self.selected_treeview.item(self.selected_item, 'values')
        # Assume column 1 holds the human-readable start time.
        start_time_str = values[1]
        start_time = self.parse_time(start_time_str)
        if start_time is not None:
            # mpv uses seconds for the time_pos property.
            self.player.time_pos = start_time
            self.update_progress_bar()
            # Pause the player by setting pause to True.
            self.player.pause = True

    def delete_annotation(self):
        # Try to get the selection from each treeview
        state_selection = self.state_annotations_tree.selection()
        point_selection = self.point_annotations_tree.selection()
        
        if state_selection:
            # Use the state annotations treeview
            self.selected_treeview = self.state_annotations_tree
            self.selected_item = state_selection[0]
            self.selected_index = self.state_annotations_tree.index(self.selected_item)
        elif point_selection:
            # Use the point annotations treeview
            self.selected_treeview = self.point_annotations_tree
            self.selected_item = point_selection[0]
            self.selected_index = self.point_annotations_tree.index(self.selected_item)
        else:
            # No selection found in either treeview
            return

        # Proceed to remove the annotation from the corresponding list
        if self.selected_treeview == self.state_annotations_tree:
            deleted_annotation = self.state_events.pop(self.selected_index)
            self.undo_stack.append(("state", self.selected_index, deleted_annotation))
        else:
            deleted_annotation = self.point_events.pop(self.selected_index)
            self.undo_stack.append(("point", self.selected_index, deleted_annotation))
            
        self.save_sorted_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()

    def delete_annotation_key(self, event):
        self.delete_annotation()

    def undo_delete(self, event):
        if not self.undo_stack:
            return  # Nothing to undo

        # Pop the last deleted annotation info
        annotation_type, index, annotation = self.undo_stack.pop()

        if annotation_type == "state":
            # Insert back into the state events list at the original index
            self.state_events.insert(index, annotation)
        else:
            # Insert back into the point events list
            self.point_events.insert(index, annotation)
        
        self.save_sorted_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()