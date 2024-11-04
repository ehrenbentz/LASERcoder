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
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont

class BehaviorLogger:
    def __init__(self):
        # Stack to store deleted annotations for undo functionality
        self.deleted_annotations_stack = []
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
        self.frame_skip = 1
        self.frame_skip_factors = [1, 2, 5, 8, 10, 15, 20, 30, 40, 50]
        self.current_speed_index = 0
        self.frame_skip = self.frame_skip_factors[self.current_speed_index]
        # Initialize session-related variables
        self.saved_state = None
        self.start_frame = 0
        self.ask_resume_window = None
        # Initialize video file related variables
        self.video_path = None
        self.video_name = None
        self.session_state_file = None
        self.csv_writer = None
        self.csv_file = None
        # Initialize Behavior Key related variables
        self.behavior_key_files = {}
        self.behavior_key_file_var = None
        self.behaviors = [["", "", "point"] for _ in range(20)]
        self.point_behaviors = {}
        self.state_behaviors = {}
        self.new_behavior_dialog_open = False
        #Initialize tkinter GUI elements
        self.video_window = None
        self.canvas = None
        self.photo_image = None
        self.edit_dialog = None
        # Create a '.resume' directory if it doesn't exist
        self.resume_dir = 'resume'
        os.makedirs(self.resume_dir, exist_ok=True)
        # Initialize the Tk root window
        self.get_monitor_info()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Center the root window on the primary monitor
        self.center_window(self.root, width=970, height=700)
        # Start the video selection process 
        self.select_video_file()
        # Start Tkinter main event loop
        self.root.mainloop()

    def get_monitor_info(self):
        """Retrieve primary monitor's details and set them as instance attributes."""
        monitors = get_monitors()
        self.primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
        self.primary_screen_width = self.primary_monitor.width
        self.primary_screen_height = self.primary_monitor.height
        self.primary_screen_x = self.primary_monitor.x  # X coordinate of primary monitor
        self.primary_screen_y = self.primary_monitor.y  # Y coordinate of primary monitor
        # Print primary monitor details
        print(f"Primary Monitor: {self.primary_monitor.name}")
        print(f"Width: {self.primary_screen_width}, Height: {self.primary_screen_height}")
        print(f"X Coordinate: {self.primary_screen_x}, Y Coordinate: {self.primary_screen_y}")
        # Print details of all monitors
        for monitor in monitors:
            print(f"Monitor: {monitor.name}, Primary: {monitor.is_primary}, Width: {monitor.width}, "
                  f"Height: {monitor.height}, X: {monitor.x}, Y: {monitor.y}")
        # Return monitor attributes if needed (though they are now stored as instance variables)
        return self.primary_screen_height, self.primary_screen_width, self.primary_monitor

    def center_window(self, window, width, height):
        # Calculate the center position based on the primary monitor dimensions and position
        if len(get_monitors()) == 1:
            # No additional offset for single-monitor setup
            x_offset = int((self.primary_screen_width - width) / 2)
            y_offset = int((self.primary_screen_height - height) / 2)
        else:
            # Apply offset for multi-monitor setups
            x_offset = int((self.primary_screen_width - width) / 2) + self.primary_screen_x
            y_offset = int((self.primary_screen_height - height) / 2) + self.primary_screen_y
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
        self.ask_resume_window.withdraw()
        self.ask_resume_window.title("Resume")
        self.center_window(self.ask_resume_window, width=400, height=150)
        self.ask_resume_window.deiconify()
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
        # Save session state
        try:
            self.save_session_state()
        except Exception as e:
            print(f"Error saving session state: {e}")
        
        # Release video capture if open
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
            print("Video capture released.")
        
        # Close CSV file if open
        if self.csv_file and not self.csv_file.closed:
            try:
                self.csv_file.close()
                print("CSV file closed.")
            except Exception as e:
                print(f"Error closing CSV file: {e}")
        
        # Destroy video window if it exists
        if self.video_window and self.video_window.winfo_exists():
            self.video_window.destroy()
            print("Video window destroyed.")
        
        # Destroy root window
        if self.root and self.root.winfo_exists():
            self.root.destroy()
            print("Root window destroyed.")

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

    def auto_save_session_state(self):
        self.save_session_state()
        # Schedule the next auto-save in 10 seconds (10,000 milliseconds)
        if self.video_window and self.video_window.winfo_exists():
            self.video_window.after(10000, self.auto_save_session_state)

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
            self.behavior_key_file_var.set(behavior_files[0])
        else:
            self.behavior_key_file_var.set('No file found')

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

            # Widget for ME Group
            me_group_entry = tk.Entry(self.root, textvariable=me_group_var)
            me_group_entry.grid(row=i + 2, column=3, padx=5, pady=2)

            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])

        # "Save" button
        save_button = tk.Button(self.root, text="Save", command=self.save_behaviors)
        save_button.grid(row=0, column=4, columnspan=2, pady=10)

        # "Delete" button
        delete_button = tk.Button(self.root, text="Delete", command=self.delete_behavior_key)
        delete_button.grid(row=0, column=6, columnspan=2, pady=10)

        # "Start Video" button
        start_button_font = tkfont.Font(weight="bold")
        start_video_button = tk.Button(self.root, text="Start Video", font=start_button_font, command=self.start_video)
        start_video_button.grid(row=1, column=6, columnspan=2, pady=10)

        # "Cancel" button
        cancel_button = tk.Button(self.root, text="Cancel", command=self.on_closing)
        cancel_button.grid(row=1, column=4, columnspan=2, pady=10)

        # Message about reserved keys
        reserved_keys_label = tk.Label(self.root, text="Note: 'w', 'a', 's', 'd' are reserved for video navigation. Do not assign these keys to a behavior.")
        reserved_keys_label.grid(row=22, column=0, columnspan=4, padx=5, pady=5, sticky='w')

        # Set window size, center it, and make sure it's on top
        self.center_window(self.root, width=970, height=700)
        self.root.attributes('-topmost', True)
        self.root.deiconify()
        self.update_behavior_key_editor()
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
        new_file_dialog = tk.Toplevel(self.root)
        new_file_dialog.withdraw()
        new_file_dialog.title("New Behavior Key File")
        self.center_window(new_file_dialog, width=350, height=150)
        new_file_dialog.deiconify()
    
        # Create a label and entry for the file name input
        label = tk.Label(new_file_dialog, text="Enter a name for the new Behavior Key file:")
        label.pack(pady=10)
    
        entry = tk.Entry(new_file_dialog, width=30)  # Set a fixed width for the entry
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
                new_file_dialog.destroy()
                self.new_behavior_dialog_open = False  # Reset the flag when dialog is closed
        
        # Create OK button
        ok_button = tk.Button(new_file_dialog, text="OK", command=on_ok)
        ok_button.pack(pady=5)
        
        # Make the dialog modal to prevent interaction with the main window until it's closed
        new_file_dialog.grab_set()
        new_file_dialog.focus_set()  # Ensure the dialog has focus
    
        # Ensure the dialog stays in front of the main window
        new_file_dialog.attributes('-topmost', True)
        new_file_dialog.after_idle(new_file_dialog.attributes, '-topmost', True)
    
        # Add a protocol to reset the flag when the window is closed
        new_file_dialog.protocol("WM_DELETE_WINDOW", lambda: [new_file_dialog.destroy(), setattr(self, 'new_behavior_dialog_open', False)])
            
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
        
        # Check if no behaviors are defined
        if all(not name_var.get().strip() for name_var in self.name_vars):
            messagebox.showwarning("No Behaviors Defined", "Please add behaviors before starting the video.")
            return

        # Check for reserved keys ('w', 'a', 's', 'd') in shortcut keys
        reserved_keys = {'w', 'a', 's', 'd'}
        assigned_keys = set()
        for key_var in self.key_vars:
            key = key_var.get().strip().lower()
            if key:
                if key in reserved_keys:
                    messagebox.showwarning(
                        "Invalid Shortcut Key",
                        f"The key '{key}' is reserved for video navigation. Please assign a different key."
                    )
                    return  # Prevent starting the video
                if key in assigned_keys:
                    messagebox.showwarning(
                        "Duplicate Shortcut Key",
                        f"The key '{key}' is assigned to multiple behaviors. Please assign unique keys."
                    )
                    return  # Prevent starting the video
                assigned_keys.add(key)
        
        # Set the behavior key file path based on the selected file
        selected_file = self.behavior_key_file_var.get()  # Fetch the selected file from the dropdown
        self.behavior_key_file = self.behavior_key_files.get(
            selected_file,
            os.path.abspath(selected_file)
        )
        
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

        # Load behaviors
        self.load_behaviors()

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
        self.annotations_panel_width = 300
        self.progress_bar_height = 25
        original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        aspect_ratio = original_width / original_height if original_height != 0 else 1.0

        # Maximum dimensions available for the video frame
        max_frame_width = self.primary_screen_width - self.annotations_panel_width
        max_frame_height = self.primary_screen_height - (self.progress_bar_height + 100)

        # First, calculate potential width and height based on max_frame_width constraint
        calculated_width = min(max_frame_width, int(max_frame_height * aspect_ratio))
        calculated_height = int(calculated_width / aspect_ratio)

        # If height exceeds max_frame_height, scale down to fit within height constraint
        if calculated_height > max_frame_height:
            calculated_height = max_frame_height
            calculated_width = int(calculated_height * aspect_ratio)

        # Set frame dimensions
        self.frame_width = calculated_width
        self.frame_height = calculated_height
        self.is_paused = False
        self.total_time = self.format_time_human_readable(self.total_frames / self.fps)

        if abs((calculated_width / calculated_height) - aspect_ratio) < 0.01:
            print("Aspect ratio maintained.")
        else:
            print("Aspect ratio not maintained.")

        # Start main GUI
        self.create_video_window()
        self.load_behaviors()
        self.run_video_processing()
        self.auto_save_session_state()
                        
    def create_video_window(self):
        self.listbox_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.header_font = tkfont.Font(family="Helvetica", size=12, weight="bold")
        self.video_window = tk.Toplevel(self.root)
        self.video_window.title(f"{self.video_name}")
        self.video_window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Detect operating system and apply the appropriate maximize command
        current_os = platform.system()
        if current_os == "Windows" or current_os == "Darwin":  # Darwin is macOS
            self.video_window.state('zoomed')
        elif current_os == "Linux":
            self.video_window.attributes('-zoomed', True)

        # Main frame
        main_frame = tk.Frame(self.video_window)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Video display frame
        video_frame = tk.Frame(main_frame)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Annotations frame
        annotations_frame = tk.Frame(main_frame, width=self.annotations_panel_width + 70)
        annotations_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Configure grid layout for annotations_frame
        annotations_frame.columnconfigure(0, weight=1)
        annotations_frame.rowconfigure(1, weight=1)  # For state behaviors
        annotations_frame.rowconfigure(3, weight=1)  # For point behaviors
        annotations_frame.rowconfigure(5, weight=1)  # For state annotations
        annotations_frame.rowconfigure(7, weight=1)  # For point annotations

        # Video canvas
        self.video_canvas = tk.Canvas(video_frame, width=self.frame_width, height=self.frame_height)
        self.video_canvas.pack()

        # Progress bar
        self.progress_bar_frame = tk.Frame(video_frame, bg="black", padx=2, pady=2)
        self.progress_bar_frame.pack()
        self.progress_bar_canvas = tk.Canvas(self.progress_bar_frame, width=self.frame_width, height=self.progress_bar_height + 25, bg="lightgrey")
        self.progress_bar_canvas.pack()
        self.initialize_progress_bar()

        # Configure Treeview styles
        self.style = ttk.Style()
        self.style.configure("Treeview", font=self.listbox_font)
        self.style.configure("Treeview.Heading", font=self.header_font)

        # State Behaviors Treeview (Smaller Height)
        state_behaviors_header = tk.Frame(annotations_frame)
        state_behaviors_header.grid(row=0, column=0, sticky="ew")
        self.state_behaviors_label = tk.Label(state_behaviors_header, text="State Behaviors", font=self.header_font)
        self.state_behaviors_label.pack(side=tk.LEFT)

        self.state_behaviors_tree = ttk.Treeview(annotations_frame, columns=("Name", "Key", "ME Group"), show="headings", height=4)
        self.state_behaviors_tree.heading("Name", text="Name")
        self.state_behaviors_tree.heading("Key", text="Key")
        self.state_behaviors_tree.heading("ME Group", text="ME Group")
        self.state_behaviors_tree.column("Name", width=100)
        self.state_behaviors_tree.column("Key", width=50)
        self.state_behaviors_tree.column("ME Group", width=80)
        self.state_behaviors_tree.grid(row=1, column=0, sticky="nsew")

        # Point Behaviors Treeview (Smaller Height)
        point_behaviors_header = tk.Frame(annotations_frame)
        point_behaviors_header.grid(row=2, column=0, sticky="ew")
        self.point_behaviors_label = tk.Label(point_behaviors_header, text="Point Behaviors", font=self.header_font)
        self.point_behaviors_label.pack(side=tk.LEFT)

        self.point_behaviors_tree = ttk.Treeview(annotations_frame, columns=("Name", "Key"), show="headings", height=4)
        self.point_behaviors_tree.heading("Name", text="Name")
        self.point_behaviors_tree.heading("Key", text="Key")
        self.point_behaviors_tree.column("Name", width=100)
        self.point_behaviors_tree.column("Key", width=50)
        self.point_behaviors_tree.grid(row=3, column=0, sticky="nsew")

        # Adjust row weights to prioritize space for annotations
        annotations_frame.rowconfigure(1, weight=10)  # State Behaviors (smaller height)
        annotations_frame.rowconfigure(3, weight=10)  # Point Behaviors (smaller height)
        annotations_frame.rowconfigure(5, weight=11)  # State Annotations (larger height)
        annotations_frame.rowconfigure(7, weight=11)  # Point Annotations (larger height)

        # Populate behaviors in Treeviews
        self.populate_behavior_treeviews()

        # State Annotations Treeview
        state_annotations_header = tk.Frame(annotations_frame)
        state_annotations_header.grid(row=4, column=0, sticky="ew")
        self.state_annotations_label = tk.Label(state_annotations_header, text="State Annotations", font=self.header_font)
        self.state_annotations_label.pack(side=tk.LEFT)
        state_sort_button = tk.Button(state_annotations_header, text="Sort", command=self.sort_state_annotations, width=3)
        state_sort_button.pack(side=tk.RIGHT, padx=30)

        state_annotations_container = tk.Frame(annotations_frame)
        state_annotations_container.grid(row=5, column=0, sticky="nsew")
        state_annotations_container.columnconfigure(0, weight=1)
        state_annotations_container.rowconfigure(0, weight=1)

        self.state_annotations_tree = ttk.Treeview(state_annotations_container, columns=("Name", "Start", "End"), show="headings")
        state_scrollbar = tk.Scrollbar(state_annotations_container, orient=tk.VERTICAL, command=self.state_annotations_tree.yview)
        self.state_annotations_tree.configure(yscrollcommand=state_scrollbar.set)
        self.state_annotations_tree.heading("Name", text="Name")
        self.state_annotations_tree.heading("Start", text="Start")
        self.state_annotations_tree.heading("End", text="End")
        self.state_annotations_tree.column("Name", width=100)
        self.state_annotations_tree.column("Start", width=100)
        self.state_annotations_tree.column("End", width=100)
        self.state_annotations_tree.grid(row=0, column=0, sticky="nsew")
        state_scrollbar.grid(row=0, column=1, sticky="ns")

        # Point Annotations Treeview
        point_annotations_header = tk.Frame(annotations_frame)
        point_annotations_header.grid(row=6, column=0, sticky="ew")
        self.point_annotations_label = tk.Label(point_annotations_header, text="Point Annotations", font=self.header_font)
        self.point_annotations_label.pack(side=tk.LEFT)
        point_sort_button = tk.Button(point_annotations_header, text="Sort", command=self.sort_point_annotations, width=3)
        point_sort_button.pack(side=tk.RIGHT, padx=30)

        point_annotations_container = tk.Frame(annotations_frame)
        point_annotations_container.grid(row=7, column=0, sticky="nsew")
        point_annotations_container.columnconfigure(0, weight=1)
        point_annotations_container.rowconfigure(0, weight=1)

        self.point_annotations_tree = ttk.Treeview(point_annotations_container, columns=("Name", "Time"), show="headings")
        point_scrollbar = tk.Scrollbar(point_annotations_container, orient=tk.VERTICAL, command=self.point_annotations_tree.yview)
        self.point_annotations_tree.configure(yscrollcommand=point_scrollbar.set)
        self.point_annotations_tree.heading("Name", text="Name")
        self.point_annotations_tree.heading("Time", text="Time")
        self.point_annotations_tree.column("Name", width=100)
        self.point_annotations_tree.column("Time", width=100)
        self.point_annotations_tree.grid(row=0, column=0, sticky="nsew")
        point_scrollbar.grid(row=0, column=1, sticky="ns")
        # Buttons Frame
        buttons_frame = tk.Frame(annotations_frame)
        buttons_frame.grid(row=8, column=0, pady=5, sticky="ew")

        visualize_button = tk.Button(
            buttons_frame,
            text="Visualize Annotations",
            command=self.visualize_annotations,
            width=16
        )
        visualize_button.pack(side=tk.LEFT, padx=1)

        summary_button = tk.Button(
            buttons_frame,
            text="Summary Statistics",
            command=self.generate_summary_statistics,
            width=16
        )
        summary_button.pack(side=tk.LEFT, padx=1)


        # Event Bindings
        self.video_window.bind("<Key>", self.on_key_press)
        self.progress_bar_canvas.bind("<Button-1>", self.on_progress_bar_click)

        # Bind ctl+z for "undo"
        self.video_window.bind("<Control-z>", lambda event: self.undo_deletion())

        # Right-click menu
        self.annotation_menu = tk.Menu(self.root, tearoff=0)
        self.annotation_menu.add_command(label="Edit", command=self.edit_annotation)
        self.annotation_menu.add_command(label="Skip to Annotation", command=self.skip_to_annotation)
        self.annotation_menu.add_command(label="Delete", command=self.delete_annotation)

        # Bind right-click and Control-Click for macOS
        self.state_annotations_tree.bind("<Button-3>", self.show_annotation_menu)
        self.state_annotations_tree.bind("<Control-Button-1>", self.show_annotation_menu)
        self.point_annotations_tree.bind("<Button-3>", self.show_annotation_menu)
        self.point_annotations_tree.bind("<Control-Button-1>", self.show_annotation_menu)

        # Bind right-click to treeviews
        self.state_annotations_tree.bind("<Button-3>", self.show_annotation_menu)
        self.point_annotations_tree.bind("<Button-3>", self.show_annotation_menu)

        # Bind Delete key
        self.state_annotations_tree.bind('<Delete>', self.on_delete_key_press)
        self.point_annotations_tree.bind('<Delete>', self.on_delete_key_press)

        # Bind Delete and Backspace keys to handle deletion on macOS
        self.state_annotations_tree.bind('<Delete>', self.on_delete_key_press)
        self.state_annotations_tree.bind('<BackSpace>', self.on_delete_key_press)
        self.point_annotations_tree.bind('<Delete>', self.on_delete_key_press)
        self.point_annotations_tree.bind('<BackSpace>', self.on_delete_key_press)

        # Bind navigation keys
        self.video_window.bind("<a>", self.on_navigation_key)
        self.video_window.bind("<d>", self.on_navigation_key)
        self.video_window.bind("<w>", self.on_navigation_key)
        self.video_window.bind("<s>", self.on_navigation_key)
        self.video_window.bind("<Left>", self.on_navigation_key)
        self.video_window.bind("<Right>", self.on_navigation_key)

        # Bind play/pause
        self.video_window.bind("<space>", lambda event: self.toggle_play_pause())

        # Bind playback speed keys
        self.video_window.bind("<minus>", lambda event: self.change_playback_speed(decrease=True))
        self.video_window.bind("<equal>", lambda event: self.change_playback_speed(decrease=False))
        self.video_window.bind("<plus>", lambda event: self.change_playback_speed(decrease=False))

        # Load behaviors and annotations
        self.load_behaviors()
        self.update_behavior_listboxes()
        self.update_annotations()

    def populate_behavior_treeviews(self):
        # Clear any existing entries in the Treeviews
        self.state_behaviors_tree.delete(*self.state_behaviors_tree.get_children())
        self.point_behaviors_tree.delete(*self.point_behaviors_tree.get_children())

        # Configure the "active" tag with a background color
        self.state_behaviors_tree.tag_configure("active", background="darkorange")
        self.point_behaviors_tree.tag_configure("highlight", background="dodgerblue")

        # Insert state behaviors with background highlight if they're active
        for behavior in self.behaviors:
            name, key, b_type, me_group = behavior
            if b_type == "state":
                # If the behavior is active, apply the "active" tag for background highlighting
                tag = ("active",) if key in self.active_state_behaviors else ()
                self.state_behaviors_tree.insert("", "end", values=(name, key, me_group), tags=tag)

        # Insert point behaviors without active tagging
        for behavior in self.behaviors:
            name, key, b_type, me_group = behavior
            if b_type == "point":
                self.point_behaviors_tree.insert("", "end", values=(name, key, me_group))

    def sort_state_annotations(self):
        # Sort the state_events list by start_time
        self.state_events.sort(key=lambda x: x['start_time'] if x['start_time'] is not None else 0)
        # Update the CSV file
        self.save_sorted_annotations()
        # Update the annotations display
        self.update_annotations()

    def sort_point_annotations(self):
        # Sort the point_events list by time
        self.point_events.sort(key=lambda x: self.parse_time(x['time']) if x['time'] is not None else 0)
        # Update the CSV file
        self.save_sorted_annotations()
        # Update the annotations display
        self.update_annotations()

    def save_sorted_annotations(self):
        annotations_file = f'{self.video_name}_Annotations.csv'
        with open(annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Name', 'Start', 'End', 'Duration', 'H_start', 'H_end'])
            # Write state annotations
            for event in self.state_events:
                start_time = self.format_time_machine_readable(event['start_time'])
                end_time = self.format_time_machine_readable(event['end_time']) if event['end_time'] is not None else ''
                duration = self.format_time_machine_readable(event['end_time'] - event['start_time']) if event['end_time'] is not None else ''
                H_start = self.format_time_human_readable(event['start_time'])
                H_end = self.format_time_human_readable(event['end_time']) if event['end_time'] is not None else ''
                writer.writerow([event['Name'], start_time, end_time, duration, H_start, H_end])
            # Write point annotations
            for event in self.point_events:
                time_machine = self.format_time_machine_readable(self.parse_time(event['time']))
                writer.writerow([event['Name'], time_machine, '', '', event['time'], ''])
        # Flush and save the CSV file
        self.csv_file.flush()

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
                if self.frame_skip <= 10:
                    # Read and display the next frame
                    ret, frame = self.cap.read()
                    if not ret or frame is None:
                        # End of video
                        self.is_paused = True
                        self.current_frame = self.total_frames
                        # Save session state
                        self.save_session_state()    
                    else:
                        self.current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                        self.display_frame(frame)
                    # Skip the next frame_skip - 1 frames
                    for _ in range(self.frame_skip - 1):
                        ret, _ = self.cap.read()
                        if not ret:
                            self.is_paused = True
                            self.current_frame = self.total_frames
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
        # Clear all entries in state behaviors Treeview
        self.state_behaviors_tree.delete(*self.state_behaviors_tree.get_children())

        # Re-insert state behaviors with updated active statuses
        for key, behavior in self.state_behaviors.items():
            me_group = self.me_groups.get(key, None)
            group_label = f" (Group {me_group})" if me_group else ""
            display_name = f"{behavior}" if key in self.active_state_behaviors else behavior
            tag = ("active",) if key in self.active_state_behaviors else ()
            self.state_behaviors_tree.insert("", "end", values=(display_name, key, me_group), tags=tag)

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
        # Update the progress bar
        self.update_progress_bar()
        # Output the current speed for debugging
        print(f"Playback speed: {self.frame_skip}x")


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
        elif key == "Left":
            self.skip_seconds(-10)  # Left arrow will skip 10 seconds backward
        elif key == "Right":
            self.skip_seconds(10)   # Right arrow will skip 10 seconds forward
    
    def on_progress_bar_click(self, event):
        x = event.x
        frame = int((x / self.frame_width) * self.total_frames)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        self.current_frame = frame
        # Read and display the frame at the new position
        ret, frame = self.cap.read()
        if ret:
            self.display_frame(frame)

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

    def update_csv_state_behavior(self, updated_event):
        self.delete_state_annotation(updated_event)  # Remove the old entry
        self.csv_writer.writerow([
            updated_event['Name'],
            self.format_time_machine_readable(updated_event['start_time']),
            self.format_time_machine_readable(updated_event['end_time']),
            updated_event.get('Duration', ""),
            updated_event.get('H_start', ""),
            updated_event.get('H_end', "")
        ])
        self.csv_file.flush()  # Ensure changes are saved

    def update_csv_point_behavior(self, updated_event):
        self.delete_point_annotation(updated_event)  # Remove the old entry
        self.csv_writer.writerow([
            updated_event['Name'],
            updated_event.get('H_start', ""),
            "", "",  # End and Duration columns not used for point behaviors
            updated_event.get('H_start', ""),
            ""
        ])
        self.csv_file.flush()

    def update_csv_annotation(self, updated_annotation, is_state_annotation):
        annotations_file = f'{self.video_name}_Annotations.csv'
        with open(annotations_file, 'r') as file:
            lines = file.readlines()

        with open(annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(lines[0].strip().split(','))  # Write header
            for line in lines[1:]:
                row = line.strip().split(',')
                if row[0] == updated_annotation['Name'] and row[4] == updated_annotation.get('original_H_start', ''):
                    if is_state_annotation:
                        # Write updated state annotation
                        writer.writerow([
                            updated_annotation['Name'],
                            updated_annotation['Start'],
                            updated_annotation.get('End', ''),
                            updated_annotation.get('Duration', ''),
                            updated_annotation['H_start'],
                            updated_annotation.get('H_end', ''),
                            updated_annotation.get('Manual Edit', '')
                        ])
                    else:
                        # Write updated point annotation
                        writer.writerow([
                            updated_annotation['Name'],
                            updated_annotation['Start'],
                            '',  # End time is empty for point annotations
                            '',  # Duration is empty for point annotations
                            updated_annotation['H_start'],
                            '',  # H_end is empty for point annotations
                            updated_annotation.get('Manual Edit', '')
                        ])
                else:
                    writer.writerow(row)  # Write unchanged rows

    def initialize_progress_bar(self):
        # Draw the static background for the progress bar on the existing canvas
        self.progress_bar_canvas.create_rectangle(0, 0, self.frame_width, self.progress_bar_height, fill="grey", tags="background")

        # Add static text placeholders below the progress bar (these only need to be updated with new values)
        y_position_text = self.progress_bar_height + 15
        self.progress_bar_canvas.create_text(5, y_position_text, anchor=tk.W, text="", fill="black", font=self.listbox_font, tags="time_text_left")
        self.progress_bar_canvas.create_text(self.frame_width - 5, y_position_text, anchor=tk.E, text="", fill="black", font=self.listbox_font, tags="time_text_right")

    def update_progress_bar(self):
        # Clear only the progress bar rectangle (not the entire canvas)
        self.progress_bar_canvas.delete("progress_bar")

        # Calculate the progress as a fraction of the total width
        progress = int((self.current_frame / self.total_frames) * self.frame_width)

        # Draw the dynamic progress bar rectangle with a specific tag
        self.progress_bar_canvas.create_rectangle(0, 0, progress, self.progress_bar_height, fill="darkblue", tags="progress_bar")

        # Update the text below the progress bar
        current_time = self.format_time_human_readable(self.current_frame / self.fps)
        total_time = self.format_time_human_readable(self.total_frames / self.fps)
        playback_speed = f"{self.frame_skip}x"
        
        # Update the text elements using their tags
        self.progress_bar_canvas.itemconfig("time_text_left", text=f"{current_time} ({playback_speed})")
        self.progress_bar_canvas.itemconfig("time_text_right", text=total_time)

    def update_annotations(self):
        # Clear the state annotations treeview
        self.state_annotations_tree.delete(*self.state_annotations_tree.get_children())

        # Populate the state annotations treeview
        for event in self.state_events:
            name = event['Name']
            start_time = self.format_time_human_readable(event['start_time'])
            end_time = self.format_time_human_readable(event['end_time']) if event['end_time'] else ''
            self.state_annotations_tree.insert('', tk.END, values=(name, start_time, end_time))

        # Scroll to the bottom of the state annotations treeview
        state_items = self.state_annotations_tree.get_children()
        if state_items:
            self.state_annotations_tree.see(state_items[-1])

        # Clear the point annotations treeview
        self.point_annotations_tree.delete(*self.point_annotations_tree.get_children())

        # Populate the point annotations treeview
        for event in self.point_events:
            name = event['Name']
            time_ = event['time']
            self.point_annotations_tree.insert('', tk.END, values=(name, time_))

        # Scroll to the bottom of the point annotations treeview
        point_items = self.point_annotations_tree.get_children()
        if point_items:
            self.point_annotations_tree.see(point_items[-1])

    def show_annotation_menu(self, event):
        # Determine which treeview was clicked
        widget = event.widget
        self.selected_treeview = widget

        # Get selected item
        item_id = widget.identify_row(event.y)
        if not item_id:
            return

        widget.selection_set(item_id)
        self.selected_item = item_id

        # Set the selected index
        if self.selected_treeview == self.state_annotations_tree:
            self.selected_index = self.state_annotations_tree.index(self.selected_item)
        else:
            self.selected_index = self.point_annotations_tree.index(self.selected_item)

        # Create the menu
        self.annotation_menu = tk.Menu(self.root, tearoff=0)
        self.annotation_menu.add_command(label="Edit", command=self.edit_annotation)
        self.annotation_menu.add_command(label="Skip to Annotation", command=self.skip_to_annotation)
        self.annotation_menu.add_command(label="Delete", command=self.delete_annotation)
        self.annotation_menu.tk_popup(event.x_root, event.y_root)

    def edit_state_annotation(self):
        if self.selected_index is None:
            return
        # Get the currently selected annotation
        selected_annotation = self.state_events[self.selected_index]
        # Load the annotation data first
        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_start', 'H_end') 
        # Skip to annotation to edit, and pause video
        self.skip_to_annotation()
        # If an edit dialog is already open, destroy it
        if self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None

        # Create the edit dialog
        self.edit_dialog = tk.Toplevel(self.root)
        self.edit_dialog.protocol("WM_DELETE_WINDOW", self.on_edit_dialog_close)
        self.edit_dialog.withdraw()
        self.edit_dialog.title("Edit State Annotation")
        self.center_window(self.edit_dialog, width=275, height=250)
        self.edit_dialog.deiconify()

        # Show current annotation in non-editable fields
        tk.Label(self.edit_dialog, text="Current Annotation").grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(self.edit_dialog, text="Name:").grid(row=1, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['Name']).grid(row=1, column=1)
        tk.Label(self.edit_dialog, text="Start:").grid(row=2, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_start']).grid(row=2, column=1)
        tk.Label(self.edit_dialog, text="End:").grid(row=3, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_end']).grid(row=3, column=1)

        # Editable new annotation fields
        tk.Label(self.edit_dialog, text="New Annotation").grid(row=4, column=0, columnspan=2, pady=5)
        new_entries = {}
        new_fields = ['Name', 'H_start', 'H_end']
        for i, field in enumerate(new_fields, start=5):
            tk.Label(self.edit_dialog, text=f"{field}:").grid(row=i, column=0)
            entry = tk.Entry(self.edit_dialog)
            entry.insert(0, latest_annotation.get(field, ""))  # Use latest_annotation here
            entry.grid(row=i, column=1)  # Add grid() call to display the entry box
            new_entries[field] = entry

        # Save button
        save_button = tk.Button(
            self.edit_dialog, text="Save",
            command=lambda: self.save_state_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_start'])
        )
        save_button.grid(row=i + 1, column=0, columnspan=2, pady=10)

    def on_edit_dialog_close(self):
        if self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None
            # Save session state
            self.save_session_state()

    def edit_point_annotation(self):
        if self.selected_index is None:
            return

        # Retrieve the selected point annotation
        selected_annotation = self.point_events[self.selected_index]
        
        # Load the latest annotation data from the CSV
        latest_annotation = self.load_annotation_data(selected_annotation, 'Name', 'H_start')

        # Skip to annotation to edit, and pause video
        self.skip_to_annotation()

        # If an edit dialog is already open, destroy it
        if self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None

        # Create the edit dialog
        self.edit_dialog = tk.Toplevel(self.root)
        self.edit_dialog.protocol("WM_DELETE_WINDOW", self.on_edit_dialog_close)
        self.edit_dialog.withdraw()
        self.edit_dialog.title("Edit Point Annotation")
        self.center_window(self.edit_dialog, width=275, height=250)
        self.edit_dialog.deiconify()

        # Display current annotation in non-editable fields
        tk.Label(self.edit_dialog, text="Current Annotation").grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(self.edit_dialog, text="Name:").grid(row=1, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['Name']).grid(row=1, column=1)
        tk.Label(self.edit_dialog, text="Start:").grid(row=2, column=0)
        tk.Label(self.edit_dialog, text=latest_annotation['H_start']).grid(row=2, column=1)

        # Editable new annotation fields
        tk.Label(self.edit_dialog, text="New Annotation").grid(row=4, column=0, columnspan=2, pady=5)
        new_entries = {}
        new_fields = ['Name', 'H_start']
        for i, field in enumerate(new_fields, start=5):
            tk.Label(self.edit_dialog, text=f"{field}:").grid(row=i, column=0)
            entry = tk.Entry(self.edit_dialog)
            entry.insert(0, latest_annotation.get(field, ""))  # Load the latest annotation data
            entry.grid(row=i, column=1)
            new_entries[field] = entry

        # Save button
        save_button = tk.Button(
            self.edit_dialog, text="Save",
            command=lambda: self.save_point_annotation(new_entries, self.edit_dialog, selected_annotation, latest_annotation['H_start'])
        )
        save_button.grid(row=i + 1, column=0, columnspan=2, pady=10)

    def load_annotation_data(self, annotation, *fields):
        annotations_file = f'{self.video_name}_Annotations.csv'
        latest_annotation = {field: "" for field in fields}
        with open(annotations_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # For state, compare 'Name' and 'H_start' after converting to human-readable format
                if (
                    row['Name'] == annotation['Name'] and
                    row['H_start'] == self.format_time_human_readable(annotation.get('start_time', 0))
                ):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    break
                # For point, check 'H_start' only
                elif 'H_start' in row and row['H_start'] == annotation.get('time'):
                    latest_annotation.update({field: row.get(field, "") for field in fields})
                    break
        return latest_annotation

    def skip_to_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        values = self.selected_treeview.item(self.selected_item, 'values')

        # Determine the type of annotation
        if self.selected_treeview == self.state_annotations_tree:
            start_time_str = values[1]
        else:
            start_time_str = values[1]

        start_time = self.parse_time(start_time_str)
        if start_time is not None:
            target_frame = int(start_time * self.fps)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            self.current_frame = target_frame

            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)

            self.is_paused = True
            self.update_progress_bar()
            self.save_session_state()

    def edit_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        if self.selected_treeview == self.state_annotations_tree:
            # Call the edit method without passing extra arguments
            self.edit_state_annotation()
        else:
            # Call the edit method without passing extra arguments
            self.edit_point_annotation()

    def on_key_press(self, event):
        key = event.char
        if key == '\x1b':  # Escape key
            self.on_closing()
        elif key == ' ':  # Spacebar for play/pause
            self.toggle_play_pause()
        elif key == '-':  # Reduce playback speed
            self.change_playback_speed(decrease=True)
        elif key in ['+', '=']:  # Increase playback speed
            self.change_playback_speed(decrease=False)
        elif key:
            self.key_press(key)

    def key_press(self, key_char):
        frame_timestamp = self.current_frame / self.fps
        formatted_timestamp = self.format_time_human_readable(frame_timestamp)
        # Handle point behaviors
        if key_char in self.point_behaviors:
            Name = self.point_behaviors[key_char]
            # Log point event and update point events list
            self.point_events.append({'Name': Name, 'time': formatted_timestamp, 'y_position': 0})
            # Write the event to the CSV file
            self.csv_writer.writerow([Name, self.format_time_machine_readable(frame_timestamp), '', '', formatted_timestamp, ''])
            self.csv_file.flush()            
            # Insert into point annotations Treeview
            self.point_annotations_tree.insert("", "end", values=(Name, formatted_timestamp))
            self.update_annotations()
            # Highlight point behavior briefly
            for item in self.point_behaviors_tree.get_children():
                if self.point_behaviors_tree.item(item, "values")[0] == Name:
                    self.point_behaviors_tree.item(item, tags="highlight")
                    self.video_window.after(250, lambda item=item: self.point_behaviors_tree.item(item, tags=""))  # Remove highlight after 0.25s
            self.update_annotations()
        # Handle state behaviors
        elif key_char in self.state_behaviors:
            self.handle_state_behavior(key_char, frame_timestamp, formatted_timestamp)
        
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
            
    def deactivate_me_group(self, me_group, frame_timestamp, current_behavior_key):
        # Deactivate all active state behaviors in the same mutually exclusive group, except the current one
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

    def save_state_annotation(self, new_entries, dialog, current_annotation, original_H_start):
        updated_annotation = {field: new_entries[field].get() for field in ['Name', 'H_start', 'H_end']}
        start_time = self.parse_time(updated_annotation['H_start'])
        end_time = self.parse_time(updated_annotation['H_end'])
        
        # Calculate duration
        duration = end_time - start_time if end_time and start_time else None
        updated_annotation['Start'] = self.format_time_machine_readable(start_time)
        updated_annotation['End'] = self.format_time_machine_readable(end_time)
        updated_annotation['Duration'] = self.format_time_machine_readable(duration)
        updated_annotation['Manual Edit'] = 'manual edit'
        updated_annotation['original_H_start'] = original_H_start

        # Update CSV with new annotation data
        self.update_csv_annotation(updated_annotation, is_state_annotation=True)

        # Reload annotations
        self.load_annotations()
        self.update_annotations()

        # Save session state
        self.save_session_state()

        # Close the dialog after saving
        self.edit_dialog.destroy()
        self.edit_dialog = None

    def save_point_annotation(self, new_entries, dialog, current_annotation, original_H_start):
        updated_annotation = {field: new_entries[field].get() for field in ['Name', 'H_start']}
        start_time = self.parse_time(updated_annotation['H_start'])
        
        updated_annotation['Start'] = self.format_time_machine_readable(start_time)
        updated_annotation['Manual Edit'] = 'manual edit'
        updated_annotation['original_H_start'] = original_H_start

        # Update CSV with new point annotation data
        self.update_csv_annotation(updated_annotation, is_state_annotation=False)

        # Reload annotations
        self.load_annotations()
        self.update_annotations()

        # Save session state
        self.save_session_state()

        # Close the dialog after saving
        self.edit_dialog.destroy()
        self.edit_dialog = None

    def remove_csv_annotation(self, event, is_state_annotation):
        annotations_file = f'{self.video_name}_Annotations.csv'
        with open(annotations_file, 'r') as file:
            lines = file.readlines()
        with open(annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(lines[0].strip().split(','))  # Write the header
            for line in lines[1:]:
                row = line.strip().split(',')
                # Match state by start time and name; match point by H_start and name
                if is_state_annotation and row[0] == event['Name'] and row[1] == self.format_time_machine_readable(event['start_time']):
                    continue  # Skip this line to delete it
                elif not is_state_annotation and row[0] == event['Name'] and row[4] == event['time']:
                    continue  # Skip this line for point deletion
                writer.writerow(row)

    def on_delete_key_press(self, event):
        widget = event.widget
        if widget == self.state_annotations_tree or widget == self.point_annotations_tree:
            self.selected_treeview = widget
            selected_items = widget.selection()
            for item in selected_items:
                self.selected_item = item
                self.delete_annotation()  # This will handle both deletion and undo functionality
            self.update_annotations()
            self.save_session_state()

    def delete_state_annotation(self, index=None):
        if index is None:
            index = self.selected_index
        if isinstance(index, int) and 0 <= index < len(self.state_events):
            event = self.state_events.pop(index)
            print(f"Deleted state behavior '{event['Name']}'")
            # Update CSV file to remove the annotation
            self.remove_csv_annotation(event, is_state_annotation=True)
            # Update the annotations display
            self.update_annotations()
            # Save session state
            self.save_session_state()

    def delete_point_annotation(self, index=None):
        if index is None:
            index = self.selected_index
        if isinstance(index, int) and 0 <= index < len(self.point_events):
            event = self.point_events.pop(index)
            print(f"Deleted point annotation '{event['Name']}'")
            # Update CSV file to remove the annotation
            self.remove_csv_annotation(event, is_state_annotation=False)
            # Update the annotations display
            self.update_annotations()
            # Save session state
            self.save_session_state()

    def delete_annotation(self):
        if not hasattr(self, 'selected_treeview') or not self.selected_item:
            return

        # Store annotation to the deleted annotations stack for undo
        if self.selected_treeview == self.state_annotations_tree:
            index = self.state_annotations_tree.index(self.selected_item)
            deleted_annotation = self.state_events[index]
            self.deleted_annotations_stack.append(("state", deleted_annotation))
            self.delete_state_annotation(index)
        else:
            index = self.point_annotations_tree.index(self.selected_item)
            deleted_annotation = self.point_events[index]
            self.deleted_annotations_stack.append(("point", deleted_annotation))
            self.delete_point_annotation(index)

    def undo_deletion(self, event=None):  # Adding event parameter for compatibility with bind
        if not self.deleted_annotations_stack:
            return
        # Retrieve the last deleted annotation
        annotation_type, deleted_annotation = self.deleted_annotations_stack.pop()
        if annotation_type == "state":
            self.state_events.append(deleted_annotation)  # Restore in-memory state events
            self.update_csv_state_behavior(deleted_annotation)  # Add back to CSV
        elif annotation_type == "point":
            self.point_events.append(deleted_annotation)  # Restore in-memory point events
            self.update_csv_point_behavior(deleted_annotation)  # Add back to CSV
        # Update the annotations display in the UI
        self.update_annotations()

    def update_csv_state_behavior(self, updated_event):
        annotations_file = f'{self.video_name}_Annotations.csv'
        with open(annotations_file, 'r') as file:
            lines = file.readlines()

        with open(annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(lines[0].strip().split(',')) 
            for line in lines[1:]:
                row = line.strip().split(',')
                if row[0] == updated_event['Name'] and row[1] == self.format_time_machine_readable(updated_event['start_time']):
                    continue  # Skip the row to delete it
                writer.writerow(row)

    def update_csv_point_behavior(self, updated_event):
        annotations_file = f'{self.video_name}_Annotations.csv'
        with open(annotations_file, 'r') as file:
            lines = file.readlines()

        with open(annotations_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(lines[0].strip().split(','))  # Write header
            for line in lines[1:]:
                row = line.strip().split(',')
                if row[0] == updated_event['Name'] and row[1] == updated_event.get('H_start'):
                    continue  # Skip the row to delete it
                writer.writerow(row)

    def format_time_human_readable(self, elapsed_time):
        if elapsed_time is None:
            return "NA"
        # Try to convert to float if it's a string representation of a number
        try:
            elapsed_time = float(elapsed_time) if isinstance(elapsed_time, str) else elapsed_time
        except ValueError:
            # Return 'NA' or another default value if it's not a valid time
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
        # Read and display the frame at the new position
        ret, frame = self.cap.read()
        if ret:
            self.display_frame(frame)
        else:
            # Handle case where frame cannot be read
            print("Failed to read frame after skipping frames.")
            self.is_paused = True
            self.current_frame = self.total_frames
            # Optionally display the last valid frame
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.total_frames - 1)
            ret, frame = self.cap.read()
            if ret:
                self.display_frame(frame)

    def skip_seconds(self, seconds):
        frames_to_skip = int(seconds * self.fps)
        self.skip_frames(frames_to_skip)

    def visualize_annotations(self):
        # Close any existing dialogs
        if hasattr(self, 'visualize_dialog') and self.visualize_dialog is not None:
            self.visualize_dialog.destroy()
            self.visualize_dialog = None
        if self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None

        # Create the dialog
        self.visualize_dialog = tk.Toplevel(self.root)
        self.visualize_dialog.protocol("WM_DELETE_WINDOW", lambda: self.close_dialog('visualize_dialog'))
        self.visualize_dialog.withdraw()
        self.visualize_dialog.title("Visualize Annotations")
        self.center_window(self.visualize_dialog, width=300, height=150)
        self.visualize_dialog.deiconify()

        # Make sure the window stays on top
        self.visualize_dialog.attributes('-topmost', True)
        self.visualize_dialog.after_idle(self.visualize_dialog.attributes, '-topmost', True)

        # Add content to the dialog
        tk.Label(self.visualize_dialog, text="Annotations Visualization\nIs Currently Under Development.").pack(pady=20)
        tk.Button(self.visualize_dialog, text="OK", command=lambda: self.close_dialog('visualize_dialog')).pack(pady=5)

    def generate_summary_statistics(self):
        # Close any existing dialogs
        if hasattr(self, 'summary_dialog') and self.summary_dialog is not None:
            self.summary_dialog.destroy()
            self.summary_dialog = None
        if self.edit_dialog is not None:
            self.edit_dialog.destroy()
            self.edit_dialog = None

        # Create the dialog
        self.summary_dialog = tk.Toplevel(self.root)
        self.summary_dialog.protocol("WM_DELETE_WINDOW", lambda: self.close_dialog('summary_dialog'))
        self.summary_dialog.withdraw()
        self.summary_dialog.title("Generate Summary Statistics")
        self.center_window(self.summary_dialog, width=300, height=150)
        self.summary_dialog.deiconify()

        # Make sure the window stays on top
        self.summary_dialog.attributes('-topmost', True)
        self.summary_dialog.after_idle(self.summary_dialog.attributes, '-topmost', True)

        # Add content to the dialog
        tk.Label(self.summary_dialog, text="Generating Summary Statistics\n Is Currently Under Development").pack(pady=20)
        tk.Button(self.summary_dialog, text="OK", command=lambda: self.close_dialog('summary_dialog')).pack(pady=5)

    def close_dialog(self, dialog_name):
        dialog = getattr(self, dialog_name, None)
        if dialog is not None:
            dialog.destroy()
            setattr(self, dialog_name, None)

if __name__ == "__main__":
    BehaviorLogger()

