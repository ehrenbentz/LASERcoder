#! /usr/bin/python3

# imports
import cv2
import csv
import os
import platform
import time
import json
from screeninfo import get_monitors
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

class BehaviorLogger:
    def __init__(self):
        # Initialize behavior types
        self.behaviors = []
        self.point_behaviors = {}
        self.state_behaviors = {}
        self.active_state_behaviors = {}
        self.state_events = []
        self.point_events = []
        self.behavior_entries = []
        self.name_vars = []
        self.key_vars = []
        self.type_vars = []
        self.me_group_vars = []
        # Initialize video processing variables
        self.fps = 0
        self.frame_width = 0
        self.frame_height = 0
        self.total_frames = 0
        self.current_frame = 0
        self.is_paused = False
        self.frame_skip = 1  # Frame skipping for playback speed
        self.frame_skip_factors = [1, 2, 5, 8, 15, 20, 30, 40, 50]
        self.current_speed_index = 0  # Start at normal speed (index 0 in the frame_skip_factors list)
        self.frame_skip = self.frame_skip_factors[self.current_speed_index]  # Initial frame skipping (normal speed)
        # Initialize session-related variables
        self.saved_state = None  # Will hold the saved session state
        self.start_frame = 0     # Frame to start from when resuming a session
        self.ask_resume_window = None  # Handle for the "ask resume" window
        # Initialize video file related variables
        self.video_path = None    # Path to the selected video file
        self.video_name = None    # Name of the selected video
        self.session_state_file = None  # Path to the session state file
        self.csv_writer = None
        self.csv_file = None
        # Initialize Behavior Key related variables
        self.behavior_key_files = {}
        self.behavior_key_file_var = None
        self.behaviors = [["", "", "point"] for _ in range(20)]  # Initialize with 20 blank behaviors
        self.point_behaviors = {}
        self.state_behaviors = {}     
        self.new_behavior_dialog_open = False          
        # Initialize the Tk root window
        self.root = tk.Tk()
        self.root.withdraw()  # Start hidden
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window closing
        #Initialize tkinter GUI elements
        self.video_window = None  # For displaying video frames
        self.canvas = None       # Canvas for drawing annotations
        self.photo_image = None  # Frame to hold the video and annotations
        self.bold_font = tkfont.Font(family="Helvetica",  size=9, weight="bold")
        self.fg_color='black'
        self.bg_color='gray75'

        # Create a '.resume' directory if it doesn't exist
        self.resume_dir = 'resume'
        os.makedirs(self.resume_dir, exist_ok=True)

        # Initialize Display variables
        monitors = get_monitors()
        self.primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
        self.primary_screen_width = self.primary_monitor.width
        self.primary_screen_height = self.primary_monitor.height

        # Start the video selection process 
        self.select_video_file()

        # Start Tkinter main event loop
        self.root.mainloop()

    def center_window(self, window, width=1025, height=725):
        # Ensure Tkinter root is updated before fetching screen size
        self.root.update_idletasks()

        # Get screen width and height using Tkinter
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Calculate x and y coordinates to center the window
        x_offset = int((screen_width - width) / 2)
        y_offset = int((screen_height - height) / 2)

        # Set the window size and position
        window.geometry(f"{width}x{height}+{x_offset}+{y_offset}")
    
    def select_video_file(self):
        # Open file dialog to select the video file
        self.video_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", ("*.mp4", "*.avi", "*.mov", "*.MP4", "*.AVI", "*.MOV")),
                ("All files", "*.*"),
            ],
        )
        if self.video_path:
            self.video_name = os.path.basename(self.video_path).split('.')[0]
            self.session_state_file = os.path.join(self.resume_dir, f'{self.video_name}_session_state.json')
            # Initialize video capture with the selected video file
            self.cap = cv2.VideoCapture(self.video_path)
            # Check for an existing session
            self.check_existing_session()
        else:
            print("No video selected. Exiting.")
            self.root.destroy()

    def initialize_annotation_file(self):
        annotations_file = f'{self.video_name}_Annotations.csv'
        if not os.path.exists(annotations_file):
            with open(annotations_file, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Name', 'Start', 'End', 'Duration', 'H_start', 'H_end'])
            print(f"Created new annotations file: {annotations_file}")
        return annotations_file

    def check_existing_session(self):
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
            # No session file, directly open the behavior editor
            self.start_frame = 0
            self.saved_state = None
            self.show_behavior_key_editor()

    def ask_resume(self, video_name, on_resume, on_start_over, on_cancel):
        # Create a new ask_resume window
        if self.ask_resume_window is not None:
            self.ask_resume_window.destroy()
        self.ask_resume_window = tk.Toplevel(self.root)
        self.ask_resume_window.title("Resume")
        self.center_window(self.ask_resume_window, width=400, height=150)
        label = tk.Label(self.ask_resume_window, text=f"A previous session was found for {video_name}.\n\nWhat would you like to do?")
        label.pack(pady=10)
        button_frame = tk.Frame(self.ask_resume_window)
        button_frame.pack(pady=10)
        resume_button = tk.Button(button_frame, text="Resume", command=lambda: [on_resume(), self.close_resume_window()])
        resume_button.pack(side=tk.LEFT, padx=10)
        start_over_button = tk.Button(button_frame, text="Start Over", command=lambda: [on_start_over(), self.close_resume_window()])
        start_over_button.pack(side=tk.LEFT, padx=10)
        # Move close_resume_window before on_cancel to ensure window closure happens first
        cancel_button = tk.Button(button_frame, text="Cancel", command=lambda: [self.close_resume_window(), on_cancel()])
        cancel_button.pack(side=tk.LEFT, padx=10)
        # Make this dialog modal by waiting for it to close before continuing
        self.ask_resume_window.grab_set()
        self.ask_resume_window.wait_window()

    def close_resume_window(self):
        # Check if the window still exists and is not destroyed
        if self.ask_resume_window is not None and self.ask_resume_window.winfo_exists():
            self.ask_resume_window.destroy()
            self.ask_resume_window = None  # Ensure we reset the variable after destroying the window

    def confirm_start_over(self):
        confirm = messagebox.askyesno(
            "Confirm Start Over",
            f"Are you sure?\n\nStarting over will delete all current annotations for\n{self.video_name}."
        )
        if confirm:
            # Delete annotations file and session state
            annotations_file = f'{self.video_name}_Annotations.csv'
            if os.path.exists(annotations_file):
                os.remove(annotations_file)
            if os.path.exists(self.session_state_file):
                os.remove(self.session_state_file)
            self.start_frame = 0
            self.saved_state = None
            # Show the behavior editor UI
            self.show_behavior_key_editor()
        else:
            # Close previous ask_resume_window before reopening
            if self.ask_resume_window is not None:
                self.ask_resume_window.destroy()
            # Re-open the original ask_resume window
            self.ask_resume(
                self.video_name,
                on_resume=self.resume_session,
                on_start_over=self.confirm_start_over,
                on_cancel=self.on_closing
            )

    def resume_session(self):
        self.start_frame = self.saved_state.get('current_frame', 0)
        self.show_behavior_key_editor()

    def on_closing(self):
        try:
            self.save_session_state()
        except Exception as e:
            print(f"Error saving session state: {e}")
        try:
            if hasattr(self, 'cap'):
                if self.cap.isOpened():
                    self.cap.release()
                    print("Video capture released.")
        except Exception as e:
            print(f"Error releasing video capture: {e}")
    
        try:
            if self.csv_file and not self.csv_file.closed:
                self.csv_file.close()
                print("CSV file closed.")
        except Exception as e:
            print(f"Error closing CSV file: {e}")
    
        try:
            if self.video_window:
                self.video_window.destroy()
        except Exception as e:
            print(f"Error destroying video window: {e}")
    
        try:
            self.root.destroy()
        except Exception as e:
            print(f"Error destroying root window: {e}")

    def save_session_state(self):
        try:
            state = {
                'video_path': self.video_path,
                'current_frame': getattr(self, 'current_frame', 0),
                'frame_timestamp': self.current_frame / self.fps if hasattr(self, 'current_frame') and self.fps else 0
            }
            # Ensure 'resume' directory exists
            os.makedirs(self.resume_dir, exist_ok=True)
            with open(self.session_state_file, 'w') as f:
                json.dump(state, f)
                print(f"Session state saved as {self.session_state_file}")
        except Exception as e:
            print(f"Error saving session state {e}")

    def show_behavior_key_editor(self):
        # Set the window title to "Behavior Key Editor"
        self.root.title("Behavior Key Editor")

        # Create the behavior key editor UI
        behavior_key_frame = tk.Frame(self.root)
        behavior_key_frame.grid(row=0, column=0, columnspan=4, pady=5)

        # Label for selecting behavior key file
        label = tk.Label(behavior_key_frame, text="Select Behavior_Key File:")
        label.grid(row=0, column=0, padx=5)

        # Find all behavior key files
        behavior_files = [f for f in os.listdir('.') if f.endswith('_behaviors.csv')]

        # Create a mapping from file names to their full paths
        self.behavior_key_files = {f: os.path.abspath(f) for f in behavior_files}

        # Variable to store the selected behavior key file
        self.behavior_key_file_var = tk.StringVar()

        if behavior_files:
            self.behavior_key_file_var.set(behavior_files[0])  # Default value
        else:
            self.behavior_key_file_var.set('No file found')  # Set to a placeholder if no files are found

        # Create OptionMenu to select behavior key file
        self.behavior_key_menu = tk.OptionMenu(behavior_key_frame, self.behavior_key_file_var, *(behavior_files if behavior_files else ['No file found']))
        self.behavior_key_menu.grid(row=0, column=1, padx=5)

        # Add trace to detect changes in the selected behavior key file
        self.behavior_key_file_var.trace('w', self.behavior_key_file_var_changed)

        # Button to create a new behavior key file
        new_Behavior_Key_button = tk.Button(behavior_key_frame, text="New Behavior Key File", command=self.new_behavior_key_file)
        new_Behavior_Key_button.grid(row=0, column=2, padx=10)

        # Headings for the behavior key editor
        tk.Label(self.root, text="Name").grid(row=1, column=0, padx=5, pady=5)
        tk.Label(self.root, text="Shortcut Key").grid(row=1, column=1, padx=5, pady=5)
        tk.Label(self.root, text="Type").grid(row=1, column=2, padx=5, pady=5)
        tk.Label(self.root, text="ME Group").grid(row=1, column=3, padx=5, pady=5)

        # Initialize behavior variables and entry widgets
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

            # Create Entry widgets for Name, Shortcut Key, and ME Group
            name_entry = tk.Entry(self.root, textvariable=name_var)
            name_entry.grid(row=i + 2, column=0, padx=5, pady=2)
            key_entry = tk.Entry(self.root, textvariable=key_var)
            key_entry.grid(row=i + 2, column=1, padx=5, pady=2)

            # Radio buttons for Point or State
            type_frame = tk.Frame(self.root)
            type_frame.grid(row=i + 2, column=2, padx=5, pady=2)
            point_radio = tk.Radiobutton(type_frame, text="Point", variable=type_var, value='point')
            state_radio = tk.Radiobutton(type_frame, text="State", variable=type_var, value='state')
            point_radio.pack(side='left')
            state_radio.pack(side='left')

            # Entry widget for ME Group
            me_group_entry = tk.Entry(self.root, textvariable=me_group_var)
            me_group_entry.grid(row=i + 2, column=3, padx=5, pady=2)

            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])

        # "Save" button
        save_button = tk.Button(self.root, text="Save", command=self.save_behaviors)
        save_button.grid(row=0, column=4, columnspan=2, pady=10)

        # "Delete" button
        delete_button = tk.Button(self.root, text="Delete", command=self.delete_behavior_key)
        delete_button.grid(row=0, column=6, columnspan=2, pady=10)

        # "Start Video" button with bold text
        bold_font = tkfont.Font(weight="bold")
        start_video_button = tk.Button(self.root, text="Start Video", font=bold_font, command=self.start_video)
        start_video_button.grid(row=1, column=6, columnspan=2, pady=10)

        # "Cancel" button
        cancel_button = tk.Button(self.root, text="Cancel", command=self.on_closing)
        cancel_button.grid(row=1, column=4, columnspan=2, pady=10)

        # Set window size, center it, and make sure it's on top
        self.center_window(self.root)  # Center the window on the screen
        self.root.attributes('-topmost', True)  # Ensure the window stays on top
        self.root.deiconify()  # Make the root window visible
        self.update_behavior_key_editor()
        # Trigger the behavior key selection programmatically
        if behavior_files:
            self.behavior_key_file_var_changed()

    def update_behavior_key_editor(self):
        # Check if a behavior key file is loaded or exists
        selected_file = self.behavior_key_file_var.get()
    
        if not selected_file or selected_file == 'No file found':
            # If no file is found or selected, call new_behavior_key_file to create one
            self.new_behavior_key_file()
            return  # Exit this function to prevent further execution before a new file is created
    
        # Clear the existing behavior entries
        for widget in self.behavior_entries:
            widget.grid_forget()  # Remove all behavior entry widgets from the grid
    
        self.behavior_entries = []  # Reset the list of behavior entry widgets
    
        # Update the fields with the current behaviors
        for i, (name_var, key_var, type_var, me_group_var) in enumerate(zip(self.name_vars, self.key_vars, self.type_vars, self.me_group_vars)):
            if i < len(self.behaviors):
                # Ensure each behavior has 4 elements, pad with empty strings if necessary
                behavior = self.behaviors[i]
                while len(behavior) < 4:
                    behavior.append("")  # Add empty strings for missing values
                name, key, behavior_type, me_group = behavior
    
                # Update the variables that back the Entry widgets
                name_var.set(name)
                key_var.set(key)
                type_var.set(behavior_type)
                me_group_var.set(me_group)  # Set the ME group value
            else:
                # If there aren't enough existing behaviors, fill with empty/default values
                name_var.set("")
                key_var.set("")
                type_var.set("point")
                me_group_var.set("")
    
            # Create Entry widgets and attach them to the grid for editing behavior fields
            name_entry = tk.Entry(self.root, textvariable=name_var)
            name_entry.grid(row=i + 2, column=0, padx=5, pady=2)
            key_entry = tk.Entry(self.root, textvariable=key_var)
            key_entry.grid(row=i + 2, column=1, padx=5, pady=2)
    
            # Use radio buttons for "Point" or "State"
            type_frame = tk.Frame(self.root)
            type_frame.grid(row=i + 2, column=2, padx=5, pady=2)
            point_radio = tk.Radiobutton(type_frame, text="Point", variable=type_var, value="point")
            state_radio = tk.Radiobutton(type_frame, text="State", variable=type_var, value="state")
            point_radio.pack(side="left")
            state_radio.pack(side="left")
    
            # Add Entry widget for ME Group
            me_group_entry = tk.Entry(self.root, textvariable=me_group_var)
            me_group_entry.grid(row=i + 2, column=3, padx=5, pady=2)
    
            # Track all the widgets
            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])
            
    def update_behavior_key_ui(self):
        # Find all behavior key files again
        behavior_files = [f for f in os.listdir('.') if f.endswith('_behaviors.csv')]
        self.behavior_key_files = {f: os.path.abspath(f) for f in behavior_files}
    
        # Rebuild the OptionMenu widget using the stored reference to the OptionMenu
        menu = self.behavior_key_menu['menu']  # Access the menu directly
        menu.delete(0, 'end')  # Clear existing entries
    
        # Add the updated behavior key files to the dropdown
        for behavior_file in behavior_files:
            menu.add_command(label=behavior_file, command=tk._setit(self.behavior_key_file_var, behavior_file))
    
        # Set the first item as the default if behavior files exist
        if behavior_files:
            self.behavior_key_file_var.set(behavior_files[0])
        else:
            self.behavior_key_file_var.set('')  # Clear the selection if no files are found

    def behavior_key_file_var_changed(self, *args):
        self.load_behaviors()
        self.update_behavior_key_editor()

    def new_behavior_key_file(self):
        # Check if the dialog is already open, and return if it is
        if self.new_behavior_dialog_open:
            return
    
        # Set the flag to indicate that the dialog is open
        self.new_behavior_dialog_open = True
    
        # Save the currently loaded file, if any
        if self.behavior_key_file_var.get() and self.behavior_key_file_var.get() != 'No file found':
            if not self.save_behaviors():
                self.new_behavior_dialog_open = False
                return
    
        # Create the dialog for entering the new file name
        dialog = tk.Toplevel(self.root)
        dialog.title("New Behavior Key File")
    
        # Center the dialog on the screen and set dimensions
        self.center_window(dialog, width=350, height=150)
    
        # Create a label and entry for the file name input
        label = tk.Label(dialog, text="Enter a name for the new Behavior Key file:")
        label.pack(pady=10)
    
        entry = tk.Entry(dialog, width=30)  # Set a fixed width for the entry
        entry.pack(padx=20, pady=5)
        entry.focus_set()  # Set the focus on the Entry widget
    
        # Function to close the dialog and handle the entered value
        def on_ok():
            new_behavior_key_name = entry.get().strip()
            if not new_behavior_key_name:
                messagebox.showwarning("No Name Entered", "You must enter a name for the Behavior Key file.")
                return
    
            if not new_behavior_key_name.endswith('_behaviors.csv'):
                new_behavior_key_name += '_behaviors.csv'
    
            self.behavior_key_file = new_behavior_key_name
    
            # Clear the behavior editor fields to make it empty for the new file
            self.behaviors = [["", "", "point", ""] for _ in range(20)]  # Reset behaviors to empty
    
            # Create the new behavior key file with empty fields
            try:
                with open(self.behavior_key_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    # Write the empty fields in the new file
                    for behavior in self.behaviors:
                        writer.writerow(behavior)
    
                # Add the new file to the dropdown list and set it as the selected file
                behavior_key_path = os.path.abspath(self.behavior_key_file)
                self.behavior_key_files[self.behavior_key_file] = behavior_key_path
                self.behavior_key_file_var.set(self.behavior_key_file)
    
                # Update the dropdown and refresh the editor with the new (empty) file
                self.update_behavior_key_ui()
                self.update_behavior_key_editor()
    
            except Exception as e:
                print(f"File Error: An error occurred while creating the file: {e}")
                return
            finally:
                dialog.destroy()
                self.new_behavior_dialog_open = False  # Reset the flag when dialog is closed
        
        # Create OK button
        ok_button = tk.Button(dialog, text="OK", command=on_ok)
        ok_button.pack(pady=5)
        
        # Make the dialog modal to prevent interaction with the main window until it's closed
        dialog.grab_set()
        dialog.focus_set()  # Ensure the dialog has focus
    
        # Ensure the dialog stays in front of the main window
        dialog.attributes('-topmost', True)
        dialog.after_idle(dialog.attributes, '-topmost', True)
    
        # Add a protocol to reset the flag when the window is closed
        dialog.protocol("WM_DELETE_WINDOW", lambda: [dialog.destroy(), setattr(self, 'new_behavior_dialog_open', False)])
            
    def save_behaviors(self):
        # Check if a behavior key file is selected
        selected_file = self.behavior_key_file_var.get()
    
        # If no valid file is loaded, trigger the creation of a new file
        if not selected_file or selected_file == 'No file found':
            self.new_behavior_key_file()  # Call the function to create a new behavior key file
            return False  # Exit after creating a new file, no need to proceed
    
        # Save behaviors to the selected file
        try:
            self.behavior_key_file = self.behavior_key_files.get(selected_file, os.path.abspath(selected_file))
            with open(self.behavior_key_file, 'w', newline='') as file:
                writer = csv.writer(file)
                # Save the behaviors from the editor
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
                            # Ensure the row has 4 columns (name, key, type, ME group)
                            while len(row) < 4:
                                row.append("")  # Add empty strings for missing columns
                            self.behaviors.append(row)
                        while len(self.behaviors) < 20:
                            self.behaviors.append(["", "", "point", ""])  # Add empty rows as needed
                            
                        # Populate the point, state behaviors, and ME groups
                        self.point_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'point' and row[1]}
                        self.state_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'state' and row[1]}
                        self.me_groups = {row[1]: row[3] for row in self.behaviors if row[3]}  # Store ME groups
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
        self.update_behavior_key_editor()  # Ensure this updates the editor after loading
                
    def delete_behavior_key(self):
        selected_file = self.behavior_key_file_var.get()
        if selected_file:
            confirmation = messagebox.askyesno("Delete Confirmation", f"Are you sure you want to delete '{selected_file}'?")
            if confirmation:
                try:
                    # Delete the file from the file system
                    os.remove(self.behavior_key_files[selected_file])
                    messagebox.showinfo("Success", f"'{selected_file}' has been deleted.")
                    # Remove the file from the behavior_key_files dictionary
                    del self.behavior_key_files[selected_file]
    
                    # Check if there are any _behaviors.csv files left after deletion
                    behavior_files_remaining = [f for f in os.listdir('.') if f.endswith('_behaviors.csv')]
                    
                    if behavior_files_remaining:
                        # Update the behavior_key_file_var dropdown with remaining files
                        self.update_behavior_key_ui()
                        self.behavior_key_file_var.set(behavior_files_remaining[0])
                    else:
                        # If no more behavior files exist, prompt the user to create a new one
                        self.behavior_key_file_var.set('No file found')
                        self.new_behavior_key_file()
    
                    # Clear the editor fields by rebuilding the editor
                    self.show_behavior_key_editor()
                except Exception as e:
                    print(f"Error: An error occurred while deleting the file: {e}")
        else:
            messagebox.showwarning("No Selection", "Please select a Behavior Key file to delete.")
    
    def start_video(self):
        # Check if there is information entered in the behavior editor
        if any(name_var.get().strip() for name_var in self.name_vars):
            # Save the behaviors before starting the video
            if not self.save_behaviors():
                return  # If saving fails, exit

        # If no behaviors are defined, prompt the user to add behaviors
        if all(not name.get().strip() for name in self.name_vars):
            messagebox.showwarning("No Behaviors Defined", "Please add behaviors before starting the video.")
            return

        # Set the behavior key file path based on the selected file
        selected_file = self.behavior_key_file_var.get()  # Fetch the selected file from the dropdown
        self.behavior_key_file = self.behavior_key_files.get(
            selected_file,
            os.path.abspath(selected_file)
        )

        # Check if there are no behaviors defined in the editor
        if all(not name.get().strip() for name in self.name_vars):
            messagebox.showwarning(
                "No Behaviors Defined",
                "No behaviors are defined. Please add behaviors before starting the video."
            )
            return  # Exit if no behaviors are defined

        # Hide root window
        self.root.withdraw()

        # Save updated behaviors to the Behavior Key file
        if not self.save_behaviors():
            return  # If saving failed, do not proceed

        # Create _Annotations.csv
        self.initialize_annotation_file()

        # Open CSV file and initialize csv_writer
        annotations_file = f'{self.video_name}_Annotations.csv'
        self.csv_file = open(annotations_file, 'a', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        if os.stat(annotations_file).st_size == 0:
            # Updated header without 'Total Count/Duration' column
            self.csv_writer.writerow(['Name', 'Start', 'End', 'Duration', 'H_start', 'H_end'])

        # Load annotations
        self.load_annotations()

        # Open the video and get its properties
        self.cap = cv2.VideoCapture(self.video_path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps == 0:
            print("Warning: FPS of video is 0. Defaulting to 30 FPS.")
            self.fps = 30.0  # Default to 30 if FPS is zero

        # Set starting frame
        self.current_frame = self.start_frame if hasattr(self, 'start_frame') else 0
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)

    
        # Calculate video frame dimensions while maintaining aspect ratio
        original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        aspect_ratio = original_width / original_height if original_height != 0 else 1.0
    
        # Calculate width and height to fit within the available space
        self.panel_width = 300  # Width of the annotation panel
        self.bar_height = 20    # Height of the progress bar
        max_frame_width = self.primary_screen_width - self.panel_width
        max_frame_height = self.primary_screen_height - self.bar_height
    
        if max_frame_width / aspect_ratio <= max_frame_height:
            self.frame_width = max_frame_width
            self.frame_height = int(self.frame_width / aspect_ratio)
        else:
            self.frame_height = max_frame_height
            self.frame_width = int(self.frame_height * aspect_ratio)
    
        self.is_paused = False
        self.total_time = self.format_time_human_readable(self.total_frames / self.fps)
    
        # Update behaviors list with any changes
        self.load_behaviors()
    
        # Create the video display window
        self.create_video_window()
    
        # Start video processing
        self.run_video_processing()
                        
    def create_video_window(self):
        self.video_window = tk.Toplevel(self.root)
        self.video_window.title(f"{self.video_name}")
        self.video_window.protocol("WM_DELETE_WINDOW", self.on_closing)
    
        # Detect operating system and apply the appropriate maximize command
        current_os = platform.system()
        if current_os == "Windows" or current_os == "Darwin":  # "Darwin" is macOS
            self.video_window.state('zoomed')
        elif current_os == "Linux":
            self.video_window.attributes('-zoomed', True)    
    
        # Change the background color of the main frame to dark grey
        main_frame = tk.Frame(self.video_window, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True)
    
        # Create the video display frame
        video_frame = tk.Frame(main_frame, bg=self.bg_color)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
        # Increase the width of the annotations frame
        annotations_frame = tk.Frame(main_frame, width=self.panel_width + 70, bg=self.bg_color)
        annotations_frame.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
    
        # In the video display frame, create the Canvas for the video frame
        self.video_canvas = tk.Canvas(video_frame, width=self.frame_width, height=self.frame_height)
        self.video_canvas.pack()
    
        # Create the progress bar Canvas
        self.bar_height = 20  # Height of the progress bar itself
        self.progress_bar_canvas = tk.Canvas(video_frame, width=self.frame_width, height=self.bar_height + 30, bg=self.bg_color)
        self.progress_bar_canvas.pack()
    
        # Create the State Behaviors list box
        self.state_behaviors_label = tk.Label(annotations_frame, text="State Behaviors", font=('Helvetica', 12, 'bold'), bg=self.bg_color, fg=self.fg_color)
        self.state_behaviors_label.pack(pady=5)
        self.state_behaviors_listbox = tk.Listbox(annotations_frame, width=70, font=self.bold_font, bg=self.bg_color, fg=self.fg_color)
        self.state_behaviors_listbox.pack(fill=tk.BOTH, expand=True)
    
        # Create the State Behaviors annotations box
        self.state_annotations_label = tk.Label(annotations_frame, text="State Annotations", font=('Helvetica', 12, 'bold'), bg=self.bg_color, fg=self.fg_color)
        self.state_annotations_label.pack(pady=5)
        self.state_annotations_listbox = tk.Listbox(annotations_frame, width=70, font=self.bold_font, bg=self.bg_color, fg=self.fg_color)
        self.state_annotations_listbox.pack(fill=tk.BOTH, expand=True)
    
        # Create the Point Behaviors list box
        self.point_behaviors_label = tk.Label(annotations_frame, text="Point Behaviors", font=('Helvetica', 12, 'bold'), bg=self.bg_color, fg=self.fg_color)
        self.point_behaviors_label.pack(pady=5)
        self.point_behaviors_listbox = tk.Listbox(annotations_frame, width=70, font=self.bold_font, bg=self.bg_color, fg=self.fg_color)
        self.point_behaviors_listbox.pack(fill=tk.BOTH, expand=True)
    
        # Create the point Behaviors annotations box
        self.point_annotations_label = tk.Label(annotations_frame, text="Point Annotations", font=('Helvetica', 12, 'bold'), bg=self.bg_color, fg=self.fg_color)
        self.point_annotations_label.pack(pady=5)
        self.point_annotations_listbox = tk.Listbox(annotations_frame, width=70, font=self.bold_font, bg=self.bg_color, fg=self.fg_color)
        self.point_annotations_listbox.pack(fill=tk.BOTH, expand=True)
    
        # Bind events to the video_canvas
        self.video_canvas.bind("<Button-1>", self.on_mouse_click)
        self.video_window.bind("<Key>", self.on_key_press)
        self.progress_bar_canvas.bind("<Button-1>", self.on_progress_bar_click)
    
        # Bind double-click events for deleting annotations
        self.state_annotations_listbox.bind('<Double-1>', self.on_state_annotation_double_click)
        self.point_annotations_listbox.bind('<Double-1>', self.on_point_annotation_double_click)
    
        # Bind Delete key for state and point annotations
        self.state_annotations_listbox.bind('<Delete>', self.on_delete_key_press)
        self.point_annotations_listbox.bind('<Delete>', self.on_delete_key_press)
    
        # Bind arrow keys to navigation functions
        self.video_window.bind("<Left>", self.on_arrow_key)
        self.video_window.bind("<Right>", self.on_arrow_key)
        self.video_window.bind("<Up>", self.on_arrow_key)
        self.video_window.bind("<Down>", self.on_arrow_key)

        # Bind arrow keys to navigation functions
        self.video_window.bind("<a>", self.on_navigation_key)
        self.video_window.bind("<d>", self.on_navigation_key)
        self.video_window.bind("<w>", self.on_navigation_key)
        self.video_window.bind("<s>", self.on_navigation_key)

        # Bind spacebar for play/pause
        self.video_window.bind("<space>", lambda event: self.toggle_play_pause())

        # Bind "-" key to decrease playback speed
        self.video_window.bind("<minus>", lambda event: self.change_playback_speed(decrease=True))

        # Bind "=" and "+" keys to increase playback speed
        self.video_window.bind("<equal>", lambda event: self.change_playback_speed(decrease=False))
        self.video_window.bind("<plus>", lambda event: self.change_playback_speed(decrease=False))

        # Load behavior lists into GUI    
        self.update_behavior_listboxes()
    
        # Initialize annotations display
        self.update_annotations()
                       
    def run_video_processing(self):
        try:
            # Load behaviors
            self.point_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'point' and row[1]}
            self.state_behaviors = {row[1]: row[0] for row in self.behaviors if row[2] == 'state' and row[1]}
            self.all_behaviors = {row[1]: (row[0], row[2]) for row in self.behaviors if row[1]}
            # Start the frame update within the Tkinter event loop
            self.update_frame()
        except Exception as e:
            print(f"Error in run_video_processing: {e}")
            self.on_closing()

    def update_frame(self):
        try:
            if not self.is_paused:
                start_time = time.time()

                # For playback speeds <= 10x, use regular frame skipping logic
                if self.frame_skip <= 8:
                    # Read and display the next frame
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        # End of video
                        self.is_paused = True
                        self.current_frame = self.total_frames
                        return
                    else:
                        self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                        self.display_frame(frame)

                    # Skip the next frame_skip - 1 frames
                    for _ in range(self.frame_skip - 1):
                        ret, _ = self.cap.read()
                        if not ret:
                            self.is_paused = True
                            self.current_frame = self.total_frames
                            break
                        else:
                            self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))

                    # Calculate the time taken to process frames
                    processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                    # Calculate the delay to maintain original FPS, adjusted for processing time
                    delay = max(1, int(1000 / self.fps - processing_time))
                    self.video_window.after(delay, self.update_frame)

                # For playback speeds > 10x, skip large chunks of frames
                else:
                    if self.frame_skip == 15:
                        seconds_to_skip = 4
                    elif self.frame_skip == 20:
                        seconds_to_skip = 6
                    elif self.frame_skip == 30:
                        seconds_to_skip = 9
                    elif self.frame_skip == 40:
                        seconds_to_skip = 12
                    elif self.frame_skip == 50:
                        seconds_to_skip = 15

                    # Use skip_seconds method to skip ahead
                    self.skip_seconds(seconds_to_skip)

                    # Read and display only one frame after the large skip
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        # End of video
                        self.is_paused = True
                        self.current_frame = self.total_frames
                        return
                    else:
                        self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                        self.display_frame(frame)

                    # For high-speed playback, delay the next frame update to simulate skipping
                    self.video_window.after(100, self.update_frame)

            else:
                # If paused, check again after a short delay
                self.video_window.after(100, self.update_frame)

        except Exception as e:
            print(f"Error in update_frame: {e}")
            self.on_closing()

    def update_behavior_listboxes(self):
        # Clear the existing entries in both listboxes
        self.state_behaviors_listbox.delete(0, tk.END)
        self.point_behaviors_listbox.delete(0, tk.END)
    
        # Add the loaded state behaviors to the state_behaviors_listbox
        for key, behavior in self.state_behaviors.items():
            me_group = self.me_groups.get(key, None)  # Get ME group (if any)
            group_label = f" (Group {me_group})" if me_group else ""
            # Check if the behavior is currently active and change the color accordingly
            if key in self.active_state_behaviors:
                # Active behaviors are shown in a different color
                self.state_behaviors_listbox.insert(tk.END, f"{behavior}  ({key}){group_label} (Active)")
                self.state_behaviors_listbox.itemconfig(tk.END, {'fg': 'darkorange'})
            else:
                self.state_behaviors_listbox.insert(tk.END, f"{behavior}  ({key}){group_label}")
    
        # Add the loaded point behaviors to the point_behaviors_listbox
        for key, behavior in self.point_behaviors.items():
            self.point_behaviors_listbox.insert(tk.END, f"{behavior}  ({key}) ")

    def on_key_press(self, event):
        key = event.char

        if key == '\x1b':  # Escape key
            self.on_closing()
        elif key == ' ':  # Spacebar for play/pause
            self.toggle_play_pause()
        elif key == '-':  # Reduce playback speed
            self.change_playback_speed(decrease=True)
        elif key in ['+', '=']:  # Increase playback speed ('=' is for the '+' key without shift)
            self.change_playback_speed(decrease=False)
        else:
            self.key_press(ord(key))

    def toggle_play_pause(self):
        # Toggle between play and pause
        self.is_paused = not self.is_paused
        print("Paused" if self.is_paused else "Playing")

    def change_playback_speed(self, decrease=False):
        # Update the current speed index based on the key pressed
        if decrease:
            self.current_speed_index = max(0, self.current_speed_index - 1)  # Decrease speed, but don't go below index 0
        else:
            self.current_speed_index = min(len(self.frame_skip_factors) - 1, self.current_speed_index + 1)  # Increase speed, but don't exceed the max index

        # Set the new frame skipping factor
        self.frame_skip = self.frame_skip_factors[self.current_speed_index]

        # Output the current speed for debugging
        print(f"Playback speed: {self.frame_skip}x")

    def on_arrow_key(self, event):
        key = event.keysym  # Get the symbolic name of the key (e.g., 'Left', 'Right')

        if key == "Left":
            self.skip_seconds(-10)  # Left arrow will skip 10 seconds backward
        elif key == "Right":
            self.skip_seconds(10)   # Right arrow will skip 10 seconds forward
        elif key == "Up":
            self.skip_frames(5)     # Up arrow will skip 5 frames forward
        elif key == "Down":
            self.skip_frames(-5)    # Down arrow will skip 5 frames backward

    def on_navigation_key(self, event):
        key = event.keysym  # Get the symbolic name of the key
        if key == "a":
            self.skip_seconds(-10)  # Left arrow or 'a' will skip 10 seconds backward
        elif key == "d":
            self.skip_seconds(10)   # Right arrow or 'd' will skip 10 seconds forward
        elif key == "w":
            self.skip_frames(5)     # Up arrow or 'w' will skip 5 frames forward
        elif key == "s":
            self.skip_frames(-5)    # Down arrow or 's' will skip 5 frames backward
    
    def on_progress_bar_click(self, event):
        x = event.x
        frame = int((x / self.frame_width) * self.total_frames)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        self.current_frame = frame
        # Read and display the frame at the new position
        ret, frame = self.cap.read()
        if ret:
            self.display_frame(frame)

    def key_press(self, key):
        frame_timestamp = self.current_frame / self.fps
        formatted_timestamp = self.format_time_human_readable(frame_timestamp)
    
        try:
            key_char = chr(key)
        except ValueError:
            key_char = None
    
        # Handle point behaviors
        if key_char in self.point_behaviors:
            Name = self.point_behaviors[key_char]
            # Log point event and update point events list
            self.point_events.append({'Name': Name, 'time': formatted_timestamp, 'y_position': 0})
    
            # Write the event to the CSV file
            self.csv_writer.writerow([Name, self.format_time_machine_readable(frame_timestamp), '', '', formatted_timestamp, ''])
            self.csv_file.flush()
    
            # Update point annotations display
            self.point_annotations_listbox.insert(tk.END, f"{Name}: {formatted_timestamp}")
    
            # Update the annotations and listboxes
            self.update_annotations()  # This updates both state and point annotations
    
        # Handle state behaviors
        elif key_char in self.state_behaviors:
            # Instead of handling directly, call handle_state_behavior
            self.handle_state_behavior(key_char, frame_timestamp, formatted_timestamp)
    
        else:
            # Print unhandled keys and return
            print(f"Unhandled key press: {key}")
    
    def deactivate_me_group(self, me_group, frame_timestamp, current_behavior_key):
        """Deactivate all active state behaviors in the same mutually exclusive group, except the current one."""
        to_remove = []
        print(f"Deactivating ME group: {me_group}, except for the current behavior: {current_behavior_key}")
    
        for key, start_time in list(self.active_state_behaviors.items()):
            # Check if the behavior belongs to the same ME group, but skip the current behavior
            if self.me_groups.get(key) == me_group and key != current_behavior_key:
                Name = self.state_behaviors[key]
                duration = frame_timestamp - start_time
                formatted_duration = f"{duration:.2f}"
                formatted_start_time = self.format_time_human_readable(start_time)
                formatted_end_time = self.format_time_human_readable(frame_timestamp)
    
                # Deactivate the state behavior and log it to CSV
                print(f"Deactivating behavior: {Name} (Key: {key}, ME Group: {me_group})")
                self.csv_writer.writerow([Name, self.format_time_machine_readable(start_time),
                                          self.format_time_machine_readable(frame_timestamp),
                                          self.format_time_machine_readable(duration),
                                          formatted_start_time, formatted_end_time])
                
                # Update the state_events list with the end time (for GUI update)
                for event in self.state_events:
                    if event['Name'] == Name and event['end_time'] is None:
                        event['end_time'] = frame_timestamp  # Update the end time in state_events list
                        break
    
                to_remove.append(key)
    
        # Remove deactivated behaviors from active state behaviors
        for key in to_remove:
            print(f"Removing active state: {key}")
            self.active_state_behaviors.pop(key)
    
        # Update annotations and behavior listboxes
        self.update_annotations()
        self.update_behavior_listboxes()
        
    def handle_state_behavior(self, key, frame_timestamp, formatted_timestamp):
        """Handles state behavior events triggered by key presses."""
        Name = self.state_behaviors[key]
        me_group = self.me_groups.get(key, None)  # Get the ME group (if any) for the state behavior
    
        # Deactivate other behaviors in the same ME group, but skip the current behavior
        if me_group:
            print(f"Key {key} belongs to ME Group {me_group}. Deactivating other behaviors in this group.")
            self.deactivate_me_group(me_group, frame_timestamp, current_behavior_key=key)
    
        if key in self.active_state_behaviors:
            # End the state behavior
            start_time = self.active_state_behaviors.pop(key)
            duration = frame_timestamp - start_time
            formatted_duration = f"{duration:.2f}"
            formatted_start_time = self.format_time_human_readable(start_time)
            formatted_end_time = self.format_time_human_readable(frame_timestamp)
    
            # Log the state behavior
            for event in self.state_events:
                if event['Name'] == Name and event['end_time'] is None:
                    event['end_time'] = frame_timestamp
                    break
            self.csv_writer.writerow([Name, self.format_time_machine_readable(start_time),
                                      self.format_time_machine_readable(frame_timestamp),
                                      self.format_time_machine_readable(duration),
                                      formatted_start_time, formatted_end_time])
            self.csv_file.flush()
            self.update_annotations()
            self.update_behavior_listboxes()
        else:
            # Start a new state behavior
            self.active_state_behaviors[key] = frame_timestamp
            self.state_events.append({'Name': Name, 'start_time': frame_timestamp, 'end_time': None})
            self.update_annotations()
            self.update_behavior_listboxes()
            
    def load_annotations(self):
        self.point_events = []
        self.state_events = []
        annotations_file = f'{self.video_name}_Annotations.csv'
        if os.path.exists(annotations_file):
            try:
                with open(annotations_file, 'r') as file:
                    reader = csv.DictReader(file)
                    # Check if the file is empty or has no 'Name' column
                    if reader.fieldnames is None or 'Name' not in reader.fieldnames:
                        raise KeyError("'Name' column not found in the CSV file.")
                    for row in reader:
                        Name = row.get('Name', '')  # Safely get the 'Name' field
                        start_time_str = row.get('H_start', '')
                        end_time_str = row.get('H_end', '')
                        start_time = self.parse_time(start_time_str) if start_time_str else None
                        end_time = self.parse_time(end_time_str) if end_time_str else None
                        if end_time_str:
                            # State behavior
                            self.state_events.append({'Name': Name, 'start_time': start_time, 'end_time': end_time})
                        else:
                            # Point behavior
                            time_ = self.parse_time(start_time_str)
                            formatted_time = self.format_time_human_readable(time_)
                            self.point_events.append({'Name': Name, 'time': formatted_time, 'y_position': 0})
            except KeyError as e:
                print(f"Error: {e}")
                messagebox.showerror("Error", f"An error occurred: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while loading annotations: {e}")
        else:
            # No annotations file found or it's empty
            print(f"No annotations file found for {self.video_name}. Starting fresh.")
            
    def display_frame(self, frame):
        # Resize the video frame
        resized_frame = cv2.resize(frame, (int(self.frame_width), int(self.frame_height)))
        rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        # Convert to ImageTk format
        self.photo_image = ImageTk.PhotoImage(image=pil_image)
        # Display the image on the video_canvas
        self.video_canvas.create_image(0, 0, image=self.photo_image, anchor=tk.NW)
        # Update the progress bar
        self.update_progress_bar()

    def delete_state_behavior(self, event):
        # Remove the event from the state_events list
        self.state_events.remove(event)
        print(f"Deleted state behavior '{event['Name']}'")
        # Update the CSV file by removing the state behavior
        self.update_csv_state_behavior(event)

    def update_csv_state_behavior(self, event):
        # Close the CSV file if it's open
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
        annotations_file = f'{self.video_name}_Annotations.csv'
        # Remove the corresponding entry from the CSV file and rewrite it
        try:
            with open(annotations_file, 'r') as file:
                lines = file.readlines()
            with open(annotations_file, 'w', newline='') as file:
                for line in lines:
                    if not (event['Name'] in line and self.format_time_machine_readable(event['start_time']) in line):
                        file.write(line)
            # Reopen the CSV file and reinitialize the writer
            self.csv_file = open(annotations_file, 'a', newline='')
            self.csv_writer = csv.writer(self.csv_file)
        except Exception as e:
            print(f"An error occurred while updating the CSV: {e}")

    def update_progress_bar(self):
        self.progress_bar_canvas.delete("all")
        progress = int((self.current_frame / self.total_frames) * self.frame_width)
        self.progress_bar_canvas.create_rectangle(0, 0, progress, self.bar_height, fill="darkblue")
        current_time = self.format_time_human_readable(self.current_frame / self.fps)
        total_time = self.format_time_human_readable(self.total_frames / self.fps)
        playback_speed = f"{self.frame_skip}x"
        
        # Move the text below the progress bar
        y_position_text = self.bar_height + 15  # Adjust the vertical position for the text to be below the progress bar
        self.progress_bar_canvas.create_text(5, y_position_text, anchor=tk.W, text=f"{current_time} ({playback_speed})", fill="black", font=self.bold_font)
        self.progress_bar_canvas.create_text(self.frame_width - 5, y_position_text, anchor=tk.E, text=total_time, fill="black", font=self.bold_font)

    def update_annotations(self):
        # Clear the state annotations listbox
        self.state_annotations_listbox.delete(0, tk.END)
        self.displayed_state_events = self.state_events[-12:]  # Display the last 12 events
    
        # Update the state annotations
        for event in self.displayed_state_events:
            start_time = self.format_time_human_readable(event['start_time'])
    
            # If the behavior is still active (no end time), show an open-ended annotation
            if event['end_time'] is None:
                self.state_annotations_listbox.insert(tk.END, f"{event['Name']}: {start_time} - ")
            else:
                end_time = self.format_time_human_readable(event['end_time'])
                self.state_annotations_listbox.insert(tk.END, f"{event['Name']}: {start_time} - {end_time}")
    
        # Update point annotations
        self.point_annotations_listbox.delete(0, tk.END)  # Clear old point annotations
        self.displayed_point_events = self.point_events[-12:]  # Display the last 12 point events
    
        for event in self.displayed_point_events:
            time_ = event['time']
            self.point_annotations_listbox.insert(tk.END, f"{event['Name']}: {time_}")
    
    def on_mouse_click(self, event):
        x, y = event.x, event.y
        self.handle_mouse_click(x, y)

    def on_state_annotation_double_click(self, event):
        selection = self.state_annotations_listbox.curselection()
        if selection:
            index = selection[0]
            # Use the actual displayed events instead of full state_events
            event_dict = self.displayed_state_events[index]
            self.delete_state_behavior(event_dict)
            self.update_annotations()

    def on_point_annotation_double_click(self, event):
        selection = self.point_annotations_listbox.curselection()
        if selection:
            index = selection[0]
            # Use the actual displayed events instead of full point_events
            event_dict = self.displayed_point_events[index]
            self.delete_annotation(event_dict)
            self.update_annotations()

    def on_delete_key_press(self, event):
        # Check which listbox triggered the event
        widget = event.widget
        # Check if it's from the state annotations listbox
        if widget == self.state_annotations_listbox:
            selection = self.state_annotations_listbox.curselection()
            if selection:
                index = selection[0]
                # Use the actual number of displayed state events
                event_dict = self.displayed_state_events[index]
                self.delete_state_behavior(event_dict)
                self.update_annotations()
        # Check if it's from the point annotations listbox
        elif widget == self.point_annotations_listbox:
            selection = self.point_annotations_listbox.curselection()
            if selection:
                index = selection[0]
                # Use the actual number of displayed point events
                event_dict = self.displayed_point_events[index]
                self.delete_annotation(event_dict)
                self.update_annotations()

    def delete_annotation(self, event):
        # Remove the event from the point_events list
        self.point_events.remove(event)
        # Close the CSV file if it's open
        if self.csv_file and not self.csv_file.closed:
            self.csv_file.close()
        # Use the correct annotations file name
        annotations_file = f'{self.video_name}_Annotations.csv'
        # Remove the corresponding entry from the CSV file
        try:
            with open(annotations_file, 'r') as file:
                lines = file.readlines()
            with open(annotations_file, 'w', newline='') as file:
                for line in lines:
                    if not (event['Name'] in line and event['time'] in line):
                        file.write(line)
            # Reopen the CSV file and reinitialize the writer
            self.csv_file = open(annotations_file, 'a', newline='')
            self.csv_writer = csv.writer(self.csv_file)
        except Exception as e:
            print(f"An error occurred while deleting annotation: {e}")

    def format_time_human_readable(self, elapsed_time):
        if elapsed_time is None:
            return "NA"
        minutes, seconds = divmod(elapsed_time, 60)
        return f"{int(minutes)}m{seconds:.2f}s"

    def format_time_machine_readable(self, elapsed_time):
        if elapsed_time is None:
            return "NA"
        return f"{elapsed_time:.2f}"

    def parse_time(self, time_str):
        if not time_str:
            return None
        if 'm' in time_str and 's' in time_str:
            try:
                m, s = time_str.split('m')
                s = s.rstrip('s')
                return int(m) * 60 + float(s)
            except ValueError:
                return None
        else:
            try:
                return float(time_str)
            except ValueError:
                return None

    def skip_frames(self, frames):
        new_frame = self.current_frame + frames
        new_frame = max(0, min(self.total_frames - 1, new_frame))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, new_frame)
        self.current_frame = new_frame

    def skip_seconds(self, seconds):
        frames_to_skip = int(seconds * self.fps)
        self.skip_frames(frames_to_skip)

if __name__ == "__main__":
    BehaviorLogger()
