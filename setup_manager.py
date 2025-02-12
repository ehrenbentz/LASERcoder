# setup_manager.py

import os
import csv
import json
import tkinter as tk
from tkinter import filedialog, messagebox, font as tkfont
from screeninfo import get_monitors
from file_picker import FilePicker

class SetupManager:
    def __init__(self, parent):
        self.parent = parent
        # Create a Toplevel for the setup UI (behavior key editor)
        self.root = tk.Toplevel(parent)
        self.root.withdraw()  # hide until ready
        self.start_video_flag = False  # flag indicating readiness to start the video

        # Set up directories relative to the current working directory.
        self.lasertag_dir = os.path.join(os.getcwd(), "lasertag")
        self.behavior_key_dir = os.path.join(self.lasertag_dir, "Behavior_Keys")
        self.annotations_dir = os.path.join(self.lasertag_dir, "Annotations")
        self.resume_dir = os.path.join(self.lasertag_dir, "Resume")

        # Initialize variables for session state and file paths.
        self.video_path = None
        self.video_name = ""
        self.annotations_file = ""
        self.session_state_file = ""  # will be set to Resume/[video_name]_session_state.json
        self.saved_state = None
        self.start_frame = 0

        # For managing behavior key files and UI elements.
        self.behaviors = [["", "", "point", ""] for _ in range(20)]
        self.behavior_key_files = {}
        self.behavior_key_file_var = tk.StringVar(self.root)
        self.behavior_entries = []
        self.ask_resume_window = None
        self.new_behavior_dialog_open = False


    def select_video_file(self):
        """Open a custom file picker and get the selected video file."""
        file_picker = FilePicker(self.root)
        self.root.wait_window(file_picker)  # Pause execution until the dialog closes

        if file_picker.selected_file:
            self.video_path = file_picker.selected_file
            self.video_name = os.path.basename(self.video_path).split('.')[0]
            self.initialize_lasertag_dir()
            self.session_state_file = os.path.join(self.resume_dir, f'{self.video_name}_session_state.json')
            print(f"Session state file: {self.session_state_file}")
            self.check_existing_session()
        else:
            print("No video selected. Exiting.")
            self.root.destroy()

    def initialize_lasertag_dir(self):
        os.makedirs(self.lasertag_dir, exist_ok=True)
        os.makedirs(self.behavior_key_dir, exist_ok=True)
        os.makedirs(self.annotations_dir, exist_ok=True)
        os.makedirs(self.resume_dir, exist_ok=True)
        print(f"Initialized LaserTAG directories:\n - {self.lasertag_dir}\n - {self.behavior_key_dir}\n - {self.annotations_dir}\n - {self.resume_dir}")

    def initialize_annotation_file(self):
        self.annotations_file = os.path.join(self.annotations_dir, f"{self.video_name}_Annotations.csv")
        if not os.path.exists(self.annotations_file):
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
                ])
            print(f"Created new annotations file: {self.annotations_file}")
        return self.annotations_file

    def check_existing_session(self):
        # If the session state file already exists, load its contents and ask the user whether to resume.
        if os.path.exists(self.session_state_file):
            with open(self.session_state_file, 'r') as f:
                self.saved_state = json.load(f)
            self.ask_resume(
                self.video_name,
                on_resume=self.resume_session,
                on_start_over=self.confirm_start_over,
                on_cancel=self.on_closing
            )
        else:
            self.start_frame = 0
            self.saved_state = None
            self.show_behavior_key_editor()

    def ask_resume(self, video_name, on_resume, on_start_over, on_cancel):
        if self.ask_resume_window is not None:
            self.ask_resume_window.destroy()
        self.ask_resume_window = tk.Toplevel(self.root)
        self.ask_resume_window.withdraw()
        self.ask_resume_window.title("Resume")
        self.center_window(self.ask_resume_window, 400, 150)
        self.ask_resume_window.deiconify()
        label = tk.Label(self.ask_resume_window,
                         text=f"A previous session was found for {video_name}.\n\nWhat would you like to do?")
        label.pack(pady=10)
        button_frame = tk.Frame(self.ask_resume_window)
        button_frame.pack(pady=10)
        resume_button = tk.Button(
            button_frame, text="Resume", command=lambda: [on_resume(), self.close_resume_window()])
        resume_button.pack(side=tk.LEFT, padx=10)
        start_over_button = tk.Button(
            button_frame, text="Start Over", command=lambda: [on_start_over(), self.close_resume_window()])
        start_over_button.pack(side=tk.LEFT, padx=10)
        cancel_button = tk.Button(
            button_frame, text="Cancel", command=lambda: [self.close_resume_window(), on_cancel()])
        cancel_button.pack(side=tk.LEFT, padx=10)
        self.ask_resume_window.grab_set()
        self.ask_resume_window.wait_window()

    def close_resume_window(self):
        if self.ask_resume_window is not None and self.ask_resume_window.winfo_exists():
            self.ask_resume_window.destroy()
            self.ask_resume_window = None

    def confirm_start_over(self):
        confirm_dialog = tk.Toplevel(self.root)
        confirm_dialog.withdraw()  # Hide it until positioned

        confirm_dialog.title("Confirm Start Over")
        self.center_window(confirm_dialog, 400, 150)  # Center the window

        label = tk.Label(confirm_dialog, text=f"Are you sure?\n\nStarting over will delete all current annotations for\n{self.video_name}.")
        label.pack(pady=10)

        button_frame = tk.Frame(confirm_dialog)
        button_frame.pack(pady=10)

        def on_confirm():
            self.annotations_file = os.path.join(self.annotations_dir, f'{self.video_name}_Annotations.csv')
            if os.path.exists(self.annotations_file):
                os.remove(self.annotations_file)
            if os.path.exists(self.session_state_file):
                os.remove(self.session_state_file)
            self.start_frame = 0
            self.saved_state = None
            confirm_dialog.destroy()
            self.show_behavior_key_editor()

        def on_cancel():
            confirm_dialog.destroy()
            if self.ask_resume_window is not None:
                self.ask_resume_window.destroy()
            self.ask_resume(
                self.video_name,
                on_resume=self.resume_session,
                on_start_over=self.confirm_start_over,
                on_cancel=self.on_closing
            )

        yes_button = tk.Button(button_frame, text="Yes", command=on_confirm)
        yes_button.pack(side=tk.LEFT, padx=10)

        no_button = tk.Button(button_frame, text="No", command=on_cancel)
        no_button.pack(side=tk.LEFT, padx=10)

        confirm_dialog.grab_set()  # Make it modal
        confirm_dialog.deiconify()
        confirm_dialog.wait_window()

    def resume_session(self):
        self.start_frame = self.saved_state.get('current_frame', 0)
        self.show_behavior_key_editor()

    def show_behavior_key_editor(self):
        self.root.title("Behavior Key Editor")
        behavior_key_frame = tk.Frame(self.root)
        behavior_key_frame.grid(row=0, column=0, columnspan=4, pady=5)

        label = tk.Label(behavior_key_frame, text="Select Behavior_Key File:")
        label.grid(row=0, column=0, padx=5)

        # List behavior key files.
        behavior_files = [f for f in os.listdir(self.behavior_key_dir) if f.endswith('_behaviors.csv')]
        self.behavior_key_files = {f: os.path.join(self.behavior_key_dir, f) for f in behavior_files}
        self.behavior_key_file_var.set(behavior_files[0] if behavior_files else 'No file found')

        self.behavior_key_menu = tk.OptionMenu(
            behavior_key_frame, self.behavior_key_file_var, *(behavior_files if behavior_files else ['No file found']))
        self.behavior_key_menu.grid(row=0, column=1, padx=5)
        self.behavior_key_file_var.trace('w', self.behavior_key_file_var_changed)

        new_behavior_key_button = tk.Button(behavior_key_frame, text="New Behavior Key File", command=self.new_behavior_key_file)
        new_behavior_key_button.grid(row=0, column=2, padx=10)

        # Column headings.
        tk.Label(self.root, text="Name").grid(row=1, column=0, padx=5, pady=5)
        tk.Label(self.root, text="Shortcut Key").grid(row=1, column=1, padx=5, pady=5)
        tk.Label(self.root, text="Type").grid(row=1, column=2, padx=5, pady=5)
        tk.Label(self.root, text="ME Group").grid(row=1, column=3, padx=5, pady=5)

        # Prepare UI entry widgets for behaviors.
        self.behavior_entries = []
        self.name_vars = []
        self.key_vars = []
        self.type_vars = []
        self.me_group_vars = []

        for i in range(20):
            name_var = tk.StringVar()
            key_var = tk.StringVar()
            type_var = tk.StringVar(value='point')
            me_group_var = tk.StringVar()

            self.name_vars.append(name_var)
            self.key_vars.append(key_var)
            self.type_vars.append(type_var)
            self.me_group_vars.append(me_group_var)

            name_entry = tk.Entry(self.root, textvariable=name_var)
            name_entry.grid(row=i + 2, column=0, padx=5, pady=2)
            key_entry = tk.Entry(self.root, textvariable=key_var)
            key_entry.grid(row=i + 2, column=1, padx=5, pady=2)

            type_frame = tk.Frame(self.root)
            type_frame.grid(row=i + 2, column=2, padx=5, pady=2)
            point_radio = tk.Radiobutton(type_frame, text="Point", variable=type_var, value='point')
            state_radio = tk.Radiobutton(type_frame, text="State", variable=type_var, value='state')
            point_radio.pack(side='left')
            state_radio.pack(side='left')

            me_group_entry = tk.Entry(self.root, textvariable=me_group_var)
            me_group_entry.grid(row=i + 2, column=3, padx=5, pady=2)

            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])

        # Control buttons.
        save_button = tk.Button(self.root, text="Save", command=self.save_behaviors)
        save_button.grid(row=0, column=4, columnspan=2, pady=10)

        delete_button = tk.Button(self.root, text="Delete", command=self.delete_behavior_key)
        delete_button.grid(row=0, column=6, columnspan=2, pady=10)

        start_button_font = tkfont.Font(weight="bold")
        start_video_button = tk.Button(self.root, text="Start Video", font=start_button_font, command=self.start_video)
        start_video_button.grid(row=1, column=6, columnspan=2, pady=10)

        cancel_button = tk.Button(self.root, text="Cancel", command=self.on_closing)
        cancel_button.grid(row=1, column=4, columnspan=2, pady=10)

        reserved_keys_label = tk.Label(self.root, text="Note: 'w', 'a', 's', 'd' are reserved for video navigation. Do not assign these keys to a behavior.")
        reserved_keys_label.grid(row=22, column=0, columnspan=4, padx=5, pady=5, sticky='w')

        self.center_window(self.root, 900, 850)
        self.root.attributes('-topmost', True)
        self.root.deiconify()
        self.update_behavior_key_editor()
        if behavior_files:
            self.behavior_key_file_var_changed()

    def update_behavior_key_editor(self):
        selected_file = self.behavior_key_file_var.get()
        if not selected_file or selected_file == 'No file found':
            self.new_behavior_key_file()
            return

        for widget in self.behavior_entries:
            widget.grid_forget()

        self.behavior_entries = []

        for i, (name_var, key_var, type_var, me_group_var) in enumerate(zip(self.name_vars, self.key_vars, self.type_vars, self.me_group_vars)):
            if i < len(self.behaviors):
                behavior = self.behaviors[i]
                while len(behavior) < 4:
                    behavior.append("")
                name, key, behavior_type, me_group = behavior
                name_var.set(name)
                key_var.set(key)
                type_var.set(behavior_type)
                me_group_var.set(me_group)
            else:
                name_var.set("")
                key_var.set("")
                type_var.set("point")
                me_group_var.set("")

            name_entry = tk.Entry(self.root, textvariable=name_var)
            name_entry.grid(row=i + 2, column=0, padx=5, pady=2)
            key_entry = tk.Entry(self.root, textvariable=key_var)
            key_entry.grid(row=i + 2, column=1, padx=5, pady=2)

            type_frame = tk.Frame(self.root)
            type_frame.grid(row=i + 2, column=2, padx=5, pady=2)
            point_radio = tk.Radiobutton(type_frame, text="Point", variable=type_var, value="point")
            state_radio = tk.Radiobutton(type_frame, text="State", variable=type_var, value="state")
            point_radio.pack(side="left")
            state_radio.pack(side="left")

            me_group_entry = tk.Entry(self.root, textvariable=me_group_var)
            me_group_entry.grid(row=i + 2, column=3, padx=5, pady=2)

            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])

    def update_behavior_key_ui(self):
        behavior_files = [f for f in os.listdir(self.behavior_key_dir) if f.endswith('_behaviors.csv')]
        self.behavior_key_files = {f: os.path.join(self.behavior_key_dir, f) for f in behavior_files}
        menu = self.behavior_key_menu['menu']
        menu.delete(0, 'end')
        for behavior_file in behavior_files:
            menu.add_command(label=behavior_file, command=tk._setit(self.behavior_key_file_var, behavior_file))
        if behavior_files:
            self.behavior_key_file_var.set(behavior_files[0])
        else:
            self.behavior_key_file_var.set('')

    def behavior_key_file_var_changed(self, *args):
        selected_file = self.behavior_key_file_var.get()
        if selected_file and selected_file != 'No file found':
            self.behavior_key_file = os.path.join(self.behavior_key_dir, selected_file)
            print(f"Loading behavior key file from: {self.behavior_key_file}")
            self.load_behaviors()
            self.update_behavior_key_editor()
        else:
            print("No behavior key file selected or available.")

    def new_behavior_key_file(self):
        if self.new_behavior_dialog_open:
            return

        self.new_behavior_dialog_open = True

        if self.behavior_key_file_var.get() and self.behavior_key_file_var.get() != 'No file found':
            if not self.save_behaviors():
                self.new_behavior_dialog_open = False
                return

        new_file_dialog = tk.Toplevel(self.root)
        new_file_dialog.withdraw()
        new_file_dialog.title("New Behavior Key File")
        
        # Center the new behavior key file window
        self.center_window(new_file_dialog, 350, 150)  

        new_file_dialog.deiconify()

        label = tk.Label(new_file_dialog, text="Enter a name for the new Behavior Key file:")
        label.pack(pady=10)

        entry = tk.Entry(new_file_dialog, width=30)
        entry.pack(padx=20, pady=5)
        entry.focus_set()

        def on_ok():
            new_behavior_key_name = entry.get().strip()
            if not new_behavior_key_name:
                messagebox.showwarning("No Name Entered", "You must enter a name for the Behavior Key file.")
                return

            if not new_behavior_key_name.endswith('_behaviors.csv'):
                new_behavior_key_name += '_behaviors.csv'

            self.behavior_key_file = os.path.join(self.behavior_key_dir, new_behavior_key_name)
            self.behaviors = [["", "", "point", ""] for _ in range(20)]
            try:
                with open(self.behavior_key_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    for behavior in self.behaviors:
                        writer.writerow(behavior)
                self.behavior_key_files[new_behavior_key_name] = self.behavior_key_file
                self.behavior_key_file_var.set(new_behavior_key_name)
                self.update_behavior_key_ui()
                self.update_behavior_key_editor()
            except Exception as e:
                print(f"File Error: An error occurred while creating the file: {e}")
                return
            finally:
                new_file_dialog.destroy()
                self.new_behavior_dialog_open = False

        ok_button = tk.Button(new_file_dialog, text="OK", command=on_ok)
        ok_button.pack(pady=5)
        new_file_dialog.grab_set()
        new_file_dialog.focus_set()
        new_file_dialog.attributes('-topmost', True)
        new_file_dialog.after_idle(new_file_dialog.attributes, '-topmost', True)
        new_file_dialog.protocol("WM_DELETE_WINDOW", lambda: [new_file_dialog.destroy(), setattr(self, 'new_behavior_dialog_open', False)])

    def save_behaviors(self):
        selected_file = self.behavior_key_file_var.get()
        if not selected_file or selected_file == 'No file found':
            self.new_behavior_key_file()
            return False
        try:
            self.behavior_key_file = self.behavior_key_files.get(selected_file, os.path.abspath(selected_file))
            with open(self.behavior_key_file, 'w', newline='') as file:
                writer = csv.writer(file)
                for i in range(len(self.behaviors)):
                    self.behaviors[i] = [
                        self.name_vars[i].get(),
                        self.key_vars[i].get(),
                        self.type_vars[i].get(),
                        self.me_group_vars[i].get()
                    ]
                    writer.writerow(self.behaviors[i])
            print(f"Behaviors saved to {self.behavior_key_file}.")
            return True
        except Exception as e:
            print(f"Error Saving File: {e}")
            return False

    def load_behaviors(self):
        selected_file = self.behavior_key_file_var.get()
        if selected_file:
            self.behavior_key_file = self.behavior_key_files.get(selected_file)
            if self.behavior_key_file and os.path.exists(self.behavior_key_file):
                try:
                    with open(self.behavior_key_file, 'r') as file:
                        reader = csv.reader(file)
                        self.behaviors = []
                        for row in reader:
                            while len(row) < 4:
                                row.append("")
                            self.behaviors.append(row)
                        while len(self.behaviors) < 20:
                            self.behaviors.append(["", "", "point", ""])
                        self.point_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'point' and row[1]}
                        self.state_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'state' and row[1]}
                        self.me_groups = {row[1]: row[3] for row in self.behaviors if row[3]}
                except Exception as e:
                    print(f"Error loading the file: {e}")
                    self.behaviors = [["", "", "point", ""] for _ in range(20)]
                    self.point_behaviors = {}
                    self.state_behaviors = {}
                    self.me_groups = {}
            else:
                self.behaviors = [["", "", "point", ""] for _ in range(20)]
                self.point_behaviors = {}
                self.state_behaviors = {}
                self.me_groups = {}
        else:
            self.behaviors = [["", "", "point", ""] for _ in range(20)]
            self.point_behaviors = {}
            self.state_behaviors = {}
            self.me_groups = {}
        self.update_behavior_key_editor()

    def delete_behavior_key(self):
        selected_file = self.behavior_key_file_var.get()
        if selected_file:
            confirmation = messagebox.askyesno(
                "Delete Confirmation", 
                f"Are you sure you want to delete '{selected_file}'?",
                parent=self.root
            )
            if confirmation:
                try:
                    os.remove(self.behavior_key_files[selected_file])
                    # Removed the extra "Success" popup.
                    del self.behavior_key_files[selected_file]
                    behavior_files_remaining = [f for f in os.listdir(self.behavior_key_dir) if f.endswith('_behaviors.csv')]
                    if behavior_files_remaining:
                        self.update_behavior_key_ui()
                        self.behavior_key_file_var.set(behavior_files_remaining[0])
                    else:
                        self.behavior_key_file_var.set('No file found')
                        self.new_behavior_key_file()
                    self.show_behavior_key_editor()
                except Exception as e:
                    print(f"Error: An error occurred while deleting the file: {e}")
        else:
            messagebox.showwarning("No Selection", "Please select a Behavior Key file to delete.", parent=self.root)

    def start_video(self):
        # Ensure behaviors are saved and valid before starting the video.
        if any(name_var.get().strip() for name_var in self.name_vars):
            if not self.save_behaviors():
                return
        if all(not name_var.get().strip() for name_var in self.name_vars):
            self.show_warning("No Behaviors Defined", "Please add behaviors before starting the video.")
            return

        reserved_keys = {'w', 'a', 's', 'd'}
        assigned_keys = set()
        for key_var in self.key_vars:
            key = key_var.get().strip().lower()
            if key:
                if key in reserved_keys:
                    self.show_warning("Invalid Shortcut Key", f"The key '{key}' is reserved for video navigation.\nPlease assign a different key.")
                    return
                if key in assigned_keys:
                    self.show_warning("Duplicate Shortcut Key", f"The key '{key}' is assigned to multiple behaviors.\nPlease assign unique keys.")
                    return
                assigned_keys.add(key)

        selected_file = self.behavior_key_file_var.get()
        self.behavior_key_file = self.behavior_key_files.get(selected_file, os.path.abspath(selected_file))

        # Initialize the session state file if it doesn't exist
        if not os.path.exists(self.session_state_file):
            with open(self.session_state_file, 'w') as f:
                json.dump({"timestamp_ms": 0}, f)
            print(f"Created new session state file: {self.session_state_file}")

        self.initialize_annotation_file()
        self.start_video_flag = True
        self.root.destroy()

    def show_warning(self, title, message):
        """Create a modal warning dialog centered on the screen."""
        warning_dialog = tk.Toplevel(self.root)
        warning_dialog.withdraw()
        warning_dialog.title(title)

        # Center the warning dialog
        self.center_window(warning_dialog, 400, 150)

        label = tk.Label(warning_dialog, text=message)
        label.pack(pady=10)

        ok_button = tk.Button(warning_dialog, text="OK", command=warning_dialog.destroy)
        ok_button.pack(pady=5)

        warning_dialog.grab_set()  # Make it modal
        warning_dialog.attributes('-topmost', True)  # Keep it on top
        warning_dialog.deiconify()
        warning_dialog.wait_window()

    def on_closing(self):
        self.root.destroy()
        print("SetupManager closed.")

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
