# video_annotator.py

import os
import platform
import json
import tkinter as tk
from tkinter import ttk, messagebox
from screeninfo import get_monitors
import vlc
import csv

class VideoAnnotator(tk.Frame):
    def __init__(self, parent, video_path, session_state_file, behavior_key_file):
        # Initialize the parent Frame first
        super().__init__(parent)
        self.parent = parent
        self.video_path = video_path
        self.session_state_file = session_state_file
        self.behavior_key_file = behavior_key_file

        # Pack the main frame into the parent window
        self.pack(fill=tk.BOTH, expand=True)

        # Initialize in order
        self.initialize_data_structures()
        self.setup_file_paths()
        self.configure_display()
        self.setup_layout_measurements()
        self.setup_grid_layout()
        self.create_video_frame()
        self.initialize_vlc_player()
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
        """Set up all necessary file paths"""
        self.video_name = os.path.basename(self.video_path).split('.')[0]
        self.annotations_dir = os.path.join(os.getcwd(), "lasertag", "Annotations")
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
            self.parent.attributes("-topmost", True)
            self.parent.state('zoomed')
        elif platform.system() == "Darwin":
            self.parent.attributes("-topmost", True)
            self.parent.state('zoomed')
            # Ensure VLC can find plugins on macOS
            os.environ["VLC_PLUGIN_PATH"] = "/Applications/VLC.app/Contents/MacOS/plugins"
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

    def initialize_vlc_player(self):
        """Initialize VLC player with platform-specific settings"""
        # Configure VLC arguments based on platform
        vlc_args = ["--quiet", "--no-video-title-show"]

        if platform.system() == "Darwin":
            vlc_args.extend([
                "--vout=macosx",
                "--hw-decoder=videotoolbox"
            ])
        elif platform.system() == "Windows":
            vlc_args.extend([
                "--directx-device=default"
            ])
        else:  # Linux
            vlc_args.extend([
                "--no-xlib"
            ])

        # Create VLC instance and player
        self.instance = vlc.Instance(*vlc_args)
        if not self.instance:
            messagebox.showerror("VLC Error", "Failed to initialize VLC instance.")
            self.destroy()
            return

        # Create and configure media player
        self.player = self.instance.media_player_new()
        media = self.instance.media_new(self.video_path)
        self.player.set_media(media)

        # Platform-specific video output configuration
        window_id = self.video_frame.winfo_id()
        if platform.system() == "Darwin":
            self.player.set_nsobject(window_id)
        elif platform.system() == "Windows":
            self.player.set_hwnd(window_id)
        else:  # Linux
            self.player.set_xwindow(window_id)

    def create_ui_components(self):
        """Create and configure UI components"""
        # Set fonts
        self.progress_bar_font = ("Helvetica", 13, "bold")
        self.treeview_font = ("Helvetica", 12)
        self.treeview_heading_font = ("Helvetica", 12, "bold")

        # Configure ttk style
        style = ttk.Style()
        style.configure("Treeview", font=self.treeview_font)
        style.configure("Treeview.Heading", font=self.treeview_heading_font)

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

    def load_data_and_start(self):
        """Load data and start playback"""
        self.load_behaviors()
        self.load_annotations()
        self.update_annotations()
        self.populate_behavior_treeviews()
        self.initialize_progress_bar()
        self.load_session_state()
        self.auto_save_session_state()
        self.player.play()

    def setup_key_bindings(self):
        """Set up all key bindings"""

        small_skip=1000
        med_skip=5000
        large_skip=10000

        key_bindings = {
            # Toggle play/pause
            "<space>": self.toggle_play,

            # Small skip
            "<Shift-Right>": lambda e: self.seek_relative(small_skip),
            "<Shift-Left>": lambda e: self.seek_relative(-small_skip),
            "<D>": lambda e: self.seek_relative(small_skip),
            "<A>": lambda e: self.seek_relative(-small_skip),

            # Medium skip
            "<Right>": lambda e: self.seek_relative(med_skip),
            "<Left>": lambda e: self.seek_relative(-med_skip),
            "<d>": lambda e: self.seek_relative(med_skip),
            "<a>": lambda e: self.seek_relative(-med_skip),

            # Large skip
            "<w>": lambda e: self.seek_relative(large_skip),
            "<s>": lambda e: self.seek_relative(-large_skip),

            # Change playback speed
            "=": lambda e: self.change_speed(1),
            "+": lambda e: self.change_speed(1),
            "-": lambda e: self.change_speed(-1),
            "_": lambda e: self.change_speed(-1),

            # Other bindings
            "<Escape>": lambda e: self.on_closing(),
            "<Delete>": self.delete_annotation_key,
            "<Control-z>": self.undo_delete,
            "<Key>": self.on_key_press,
        }

        for key, callback in key_bindings.items():
            self.parent.bind(key, callback)

        # Set window close protocol
        self.parent.protocol("WM_DELETE_WINDOW", self.on_closing)

    def save_session_state(self):
        """
        Saves the current video time (in milliseconds) as session state.
        The file is saved to Resume/[video_file]_session_state.json.
        """
        resume_dir = os.path.join(os.getcwd(), "lasertag/Resume")
        # Get the current time in ms from the VLC player
        current_time = self.player.get_time()
        session_state = {"timestamp_ms": current_time}
        file_path = os.path.join(resume_dir, f"{self.video_name}_session_state.json")
        with open(file_path, "w") as f:
            json.dump(session_state, f)
        print(f"Session state saved at {current_time} ms.")

    def load_session_state(self):
        """
        Loads the session state if available and schedules the video to resume from
        the saved timestamp.
        """
        resume_dir = os.path.join(os.getcwd(), "lasertag", "Resume")
        file_path = os.path.join(resume_dir, f"{self.video_name}_session_state.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                session_state = json.load(f)
            timestamp_ms = session_state.get("timestamp_ms", 0)
            # Instead of setting the time immediately, call a helper that waits for the media to be ready.
            self.schedule_resume(timestamp_ms)
        else:
            print("No session state found.")

    def schedule_resume(self, timestamp_ms):
        """
        Wait until the media is loaded (player.get_length() > 0) then set the video time.
        """
        if self.player.get_length() > 0:
            self.player.set_time(timestamp_ms)
            print(f"Resumed session state at {timestamp_ms} ms.")
        else:
            # Check again after 200ms
            self.after(200, lambda: self.schedule_resume(timestamp_ms))

    def auto_save_session_state(self):
        """
        Automatically saves the session state and schedules the next save in 10 seconds.
        """
        self.save_session_state()
        self.after(1000, self.auto_save_session_state)

    def create_annotation_panel(self):
        print(f"Annotation Panel Width: {self.panel_width}")

        # Annotation Panel Frame (Right)
        self.annotation_border_frame = tk.Frame(self, bg="grey", bd=2, relief="solid", height=self.video_height)
        self.annotation_border_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=3, pady=0)
        self.annotation_frame = tk.Frame(self.annotation_border_frame, bg="gray",
                                         width=self.panel_width, height=self.video_height)
        self.annotation_frame.pack(fill="both", expand=True, padx=3, pady=0)

        # ------------------- Behavior Treeviews -------------------
        # State Behaviors
        state_frame = tk.Frame(self.annotation_frame, bg="gray")
        state_frame.pack(fill="x", pady=(0, 5))
        state_label = tk.Label(state_frame, text="State Behaviors", bg="gray", fg="white",
                               font=("Helvetica", 14, "bold"))
        state_label.pack(anchor="w")

        # Create Treeview and scrollbar
        self.state_behaviors_tree = ttk.Treeview(state_frame, columns=("Name", "Key", "ME Group"),
                                                 show="headings", height=5)
        self.state_behaviors_tree.heading("Name", text="Name")
        self.state_behaviors_tree.heading("Key", text="Key")
        self.state_behaviors_tree.heading("ME Group", text="ME Group")
        self.state_behaviors_tree.column("Name", width=int(self.panel_width * 0.5))
        self.state_behaviors_tree.column("Key", width=int(self.panel_width * 0.15))
        self.state_behaviors_tree.column("ME Group", width=int(self.panel_width * 0.35))

        # Scrollbar for state behaviors
        state_scrollbar = ttk.Scrollbar(state_frame, orient="vertical",
                                        command=self.state_behaviors_tree.yview)
        self.state_behaviors_tree.configure(yscrollcommand=state_scrollbar.set)
        state_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.state_behaviors_tree.pack(side=tk.LEFT, fill="both", expand=True)

        # Point Behaviors
        point_frame = tk.Frame(self.annotation_frame, bg="gray")
        point_frame.pack(fill="x", pady=(0, 5))
        point_label = tk.Label(point_frame, text="Point Behaviors", bg="gray", fg="white",
                               font=("Helvetica", 14, "bold"))
        point_label.pack(anchor="w")

        self.point_behaviors_tree = ttk.Treeview(point_frame, columns=("Name", "Key"),
                                                 show="headings", height=5)
        self.point_behaviors_tree.heading("Name", text="Name")
        self.point_behaviors_tree.heading("Key", text="Key")
        self.point_behaviors_tree.column("Name", width=int(self.panel_width * 0.75))
        self.point_behaviors_tree.column("Key", width=int(self.panel_width * 0.25))

        # Scrollbar for point behaviors
        point_scrollbar = ttk.Scrollbar(point_frame, orient="vertical",
                                        command=self.point_behaviors_tree.yview)
        self.point_behaviors_tree.configure(yscrollcommand=point_scrollbar.set)
        point_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.point_behaviors_tree.pack(side=tk.LEFT, fill="both", expand=True)

        # ------------------- Annotations Treeviews -------------------
        # State Annotations
        state_anno_frame = tk.Frame(self.annotation_frame, bg="gray")
        state_anno_frame.pack(fill="both", expand=True, pady=(0, 5))
        state_anno_label_frame = tk.Frame(state_anno_frame, bg="gray")
        state_anno_label_frame.pack(fill="x")
        tk.Label(state_anno_label_frame, text="State Annotations", bg="gray", fg="white",
                 font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        tk.Button(state_anno_label_frame, text="Sort", command=self.sort_state_annotations)\
           .pack(side=tk.RIGHT, padx=10, pady=5)

        self.state_annotations_tree = ttk.Treeview(state_anno_frame,columns=("Name", "Start", "End"),show="headings")
        self.state_annotations_tree.heading("Name", text="Name")
        self.state_annotations_tree.heading("Start", text="Start")
        self.state_annotations_tree.heading("End", text="End")
        self.state_annotations_tree.column("Name", width=int(self.panel_width * 0.33))
        self.state_annotations_tree.column("Start", width=int(self.panel_width * 0.33))
        self.state_annotations_tree.column("End", width=int(self.panel_width * 0.33))
        
        # Bind right-click to open menus
        self.state_annotations_tree.bind("<Button-3>", self.show_annotation_menu)
        
        # Scrollbar for state annotations
        state_anno_scrollbar = ttk.Scrollbar(state_anno_frame, orient="vertical",
                                             command=self.state_annotations_tree.yview)
        self.state_annotations_tree.configure(yscrollcommand=state_anno_scrollbar.set)
        state_anno_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.state_annotations_tree.pack(side=tk.LEFT, fill="both", expand=True)

        # Point Annotations
        point_anno_frame = tk.Frame(self.annotation_frame, bg="gray")
        point_anno_frame.pack(fill="both", expand=True, pady=(0, 5))
        point_anno_label_frame = tk.Frame(point_anno_frame, bg="gray")
        point_anno_label_frame.pack(fill="x")
        tk.Label(point_anno_label_frame, text="Point Annotations", bg="gray", fg="white",
                 font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        tk.Button(point_anno_label_frame, text="Sort", command=self.sort_point_annotations)\
           .pack(side=tk.RIGHT, padx=10, pady=5)

        self.point_annotations_tree = ttk.Treeview(point_anno_frame,
                                                   columns=("Name", "Time"),
                                                   show="headings")
        self.point_annotations_tree.heading("Name", text="Name")
        self.point_annotations_tree.heading("Time", text="Time")
        self.point_annotations_tree.column("Name", width=int(self.panel_width * 0.3))
        self.point_annotations_tree.column("Time", width=int(self.panel_width * 0.7))

        # Bind right-click to open menus
        self.point_annotations_tree.bind("<Button-3>", self.show_annotation_menu)

        # Scrollbar for point annotations
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
                                     width=16, wraplength=int(self.panel_width * 0.3))
        visualize_button.pack(side=tk.LEFT, padx=10, pady=5)
        summary_button = tk.Button(buttons_frame, text="Summary\nStatistics",
                                   command=self.generate_summary_statistics,
                                   width=16, wraplength=int(self.panel_width * 0.3))
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
        """
        Process key presses. For state behaviors, delegate to handle_state_behavior;
        for point behaviors, append a new point annotation.
        """
        key = event.char.lower()
        if not key:  # Ignore keys that do not produce a character (e.g., Shift)
            return
        if key in self.behavior_map:
            behavior_info = self.behavior_map[key]
            current_time = self.player.get_time() / 1000.0  # Convert ms to seconds
            formatted_time = self.format_time_human_readable(current_time)

            if behavior_info["Type"] == "State":
                self.handle_state_behavior(key, current_time, formatted_time)

            elif behavior_info["Type"] == "Point":
                # Ensure the annotation is only added once
                if any(event["Name"] == behavior_info["Name"] and event["time"] == formatted_time for event in self.point_events):
                    return  # Prevent duplicate entries

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

                # Add the event to in-memory storage
                self.point_events.append({
                    "Name": behavior_info["Name"],
                    "time": formatted_time,
                    "Manual_Edit": False
                })

                # Mark the point behavior as used (for highlighting)
                self.used_point_behaviors.add(key)
                self.parent.after(100, lambda: self.used_point_behaviors.discard(key))

                # Update treeviews
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

    # ----------------------- VLC Playback Functions -----------------------
    def toggle_play(self, event=None):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def refresh_paused_frame(self):
        if not self.player.is_playing():
            self.player.set_pause(0)
            self.update()
            self.after(20, lambda: self.player.set_pause(1))

    def step_frame_if_paused(self):
        if ndlf.player.is_playing():
            a.player.next_frame()

    def seek_relative(self, offset_ms):
        current_time = self.player.get_time()
        new_time = max(current_time + offset_ms, 0)
        self.player.set_time(new_time)
        self.refresh_paused_frame()

    def change_speed(self, delta):
        """
        Example usage: update the playback speed, and also update the speed_text.
        """
        speed_steps = [0.5, 1, 2, 3, 4, 5, 8, 10, 15, 20, 30]
        current_rate = self.player.get_rate()
        try:
            index = speed_steps.index(current_rate)
        except ValueError:
            index = min(range(len(speed_steps)), key=lambda i: abs(speed_steps[i] - current_rate))
        new_index = max(0, min(len(speed_steps) - 1, index + (1 if delta > 0 else -1)))
        new_rate = speed_steps[new_index]
        if new_rate != current_rate:
            self.player.set_rate(new_rate)
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
        # Create the playback speed text (it will be updated via change_speed()).
        self.progress_bar_canvas.create_text(
            110, bar_height / 2, anchor="w",
            text="(1.0x)",
            fill="white",
            font=self.progress_bar_font,
            tags="speed_text"
        )
        # Get total media length.
        total_ms = self.player.get_length()
        if total_ms <= 0:
            # Media not yet loaded; try again in 250ms.
            self.after(250, self.initialize_progress_bar)
            return
        total_sec = total_ms / 1000.0
        total_time_str = self.format_time_human_readable(total_sec)
        # Create the total-time text (on the right) once and never update it.
        self.progress_bar_canvas.create_text(
            self.progress_bar_width - 5, bar_height / 2, anchor="e",
            text=total_time_str,
            fill="white",
            font=self.progress_bar_font,
            tags="time_text_right"
        )
        # Start polling to update the current time and progress rectangle (every 500ms).
        self.poll_progress_bar()

    def poll_progress_bar(self):
        """Update the progress bar and schedule the next update in 500ms."""
        self.update_progress_bar()
        state = self.player.get_state()
        if state == vlc.State.Ended:
            print("Video ended. Restarting from beginning.")
            self.player.stop()
            self.player.set_time(0)
            self.player.play()
        self.after(500, self.poll_progress_bar)

    def update_progress_bar(self):
        """Update only the dynamic parts of the progress bar."""
        total_ms = self.player.get_length()
        current_ms = self.player.get_time()
        ratio = (current_ms / total_ms) if total_ms > 0 else 0
        progress = int(ratio * self.progress_bar_width)

        # Update the coordinates of the existing progress rectangle.
        self.progress_bar_canvas.coords(
            self.progress_rect,
            0, 0, progress, self.progress_bar_height
        )

        # Update the current time text (left).
        current_sec = current_ms / 1000.0
        current_time_str = self.format_time_human_readable(current_sec)
        self.progress_bar_canvas.itemconfig("time_text_left", text=current_time_str)

        # Ensure that the text items remain on top.
        self.progress_bar_canvas.tag_raise("time_text_left")
        self.progress_bar_canvas.tag_raise("time_text_right")
        self.progress_bar_canvas.tag_raise("speed_text")

    def on_progress_click(self, event):
        click_x = event.x
        ratio = click_x / self.progress_bar_width
        total_ms = self.player.get_length()
        if total_ms > 0:
            target_ms = int(ratio * total_ms)
            self.player.set_time(target_ms)

    def on_closing(self):
        self.player.stop()
        self.parent.destroy()

    def visualize_annotations(self):
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

    def generate_summary_statistics(self):
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
        if hasattr(self, 'edit_dialog') and self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None
            # Optionally save session state here:
            # self.save_session_state()

    def skip_to_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        values = self.selected_treeview.item(self.selected_item, 'values')
        # Assume column 1 holds the human-readable start time
        start_time_str = values[1]
        start_time = self.parse_time(start_time_str)
        if start_time is not None:
            # VLC uses milliseconds; convert seconds to ms
            self.player.set_time(int(start_time * 1000))
            self.refresh_paused_frame()
            self.update_progress_bar()
            self.player.pause()

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
