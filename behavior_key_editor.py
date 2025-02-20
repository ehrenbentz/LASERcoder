# behavior_key_editor

import os
import csv
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from screeninfo import get_monitors

class BehaviorKeyEditor:
    def __init__(self, parent, behavior_key_dir, on_start_video, on_cancel, config_manager):
        self.parent = parent
        self.config_manager = config_manager
        self.root = tk.Toplevel(parent)
        self.root.attributes('-topmost', True)
        self.behavior_key_dir = behavior_key_dir
        self.on_start_video = on_start_video
        self.on_cancel = on_cancel
        
        # Initialize state variables
        self.behavior_key_file = None
        self.behaviors = [["", "", "point", ""] for _ in range(20)]
        self.behavior_key_files = {}
        self.behavior_key_file_var = tk.StringVar(self.root)
        self.behavior_entries = []
        self.new_behavior_dialog_open = False
        self.active_dialogs = []
        self._initializing = False

        # Track variables for entries
        self.name_vars = []
        self.key_vars = []
        self.type_vars = []
        self.me_group_vars = []
        
        # Setup UI
        self.setup_ui()
        
        # Initialize behavior key after UI setup
        self.initialize_behavior_key()
        self.setup_window_close()

    def initialize_behavior_key(self):
        """Initialize with last used key or create new one if none exists"""
        print("\n=== Starting behavior key initialization ===")
        last_key = self.config_manager.get_last_behavior_key()
        print(f"Last used key from config: {last_key}")
        
        # Get all available behavior files
        behavior_files = self.get_behavior_files()
        print(f"Available behavior files: {behavior_files}")
        
        if last_key and os.path.exists(os.path.join(self.behavior_key_dir, last_key)):
            print(f"Found valid last key: {last_key}")
            self.behavior_key_file = os.path.join(self.behavior_key_dir, last_key)
            display_name = last_key.replace('_behaviors.csv', '')
            print(f"Setting combo box to: {display_name}")
            
            # Directly set both the UI and internal state
            self.behavior_key_combo.set(display_name)
            self.behavior_key_file_var.set(last_key)
            self.load_behaviors()
            self.update_behavior_entries()
            
        else:
            print("No valid last key found, checking for available files")
            if behavior_files:
                first_file = behavior_files[0]
                print(f"Using first available file: {first_file}")
                self.behavior_key_file = os.path.join(self.behavior_key_dir, first_file)
                display_name = first_file.replace('_behaviors.csv', '')
                
                # Directly set both the UI and internal state
                self.behavior_key_combo.set(display_name)
                self.behavior_key_file_var.set(first_file)
                self.load_behaviors()
                self.update_behavior_entries()
                
            else:
                print("No behavior files found, will create new one")
                self.root.after(100, self.new_behavior_key_file)
        
        print("=== Behavior key initialization complete ===\n")

    def setup_ui(self):
        """Setup the UI with proper behavior key handling"""
        self.root.title("Behavior Key Editor")
        bg_color = "lightgrey"
        self.root.configure(bg=bg_color)

        # Get monitor dimensions
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        new_width = int(primary.width * 0.5)
        new_height = min(int(primary.height * 0.9), 800)  # Cap maximum height

        # Create main container frame
        self.main_container = tk.Frame(self.root, bg=bg_color)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Top frame for file selection (fixed position)
        self.top_frame = tk.Frame(self.main_container, bg=bg_color)
        self.top_frame.pack(fill=tk.X, padx=10, pady=5)
        self.create_file_selection_frame(self.top_frame, bg_color)

        # Create a canvas and scrollable frame for the middle content
        self.canvas = tk.Canvas(self.main_container, bg=bg_color)
        self.scrollbar = tk.Scrollbar(self.main_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg_color)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        
        # Create headers and entries in the scrollable frame
        self.create_column_headers(self.scrollable_frame, bg_color)
        self.create_behavior_entries(self.scrollable_frame, bg_color)

        # Bottom frame for buttons (fixed position)
        self.bottom_frame = tk.Frame(self.main_container, bg=bg_color)
        self.bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        self.create_control_buttons(self.bottom_frame, bg_color)
        self.create_reserved_keys_label(self.bottom_frame, bg_color)

        # Pack the canvas and scrollbar
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Configure window size and position
        self.center_window(self.root, new_width, new_height)
        self.root.minsize(600, 400)
        
        # Bind mouse wheel to scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Get behavior files and load last used key
        behavior_files = self.get_behavior_files()
        last_key = self.config_manager.get_last_behavior_key()

    def on_canvas_configure(self, event):
        # Update the scrollable region to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Update the canvas_frame width to match the canvas
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_column_headers(self, parent, bg_color):
        header_frame = tk.Frame(parent, bg=bg_color)
        header_frame.pack(fill=tk.X, padx=20, pady=(5,0))
        
        # Configure column weights
        header_frame.grid_columnconfigure(0, weight=3, minsize=200)  # Name
        header_frame.grid_columnconfigure(1, weight=2, minsize=100)  # Key
        header_frame.grid_columnconfigure(2, weight=2, minsize=150)  # Type
        header_frame.grid_columnconfigure(3, weight=2, minsize=100)  # ME Group

        headers = [
            ("Name", 0), ("Shortcut Key", 1), 
            ("Type", 2), ("ME Group", 3)
        ]
        
        for text, col in headers:
            label = tk.Label(
                header_frame, 
                text=text, 
                font=("Helvetica", 12, "bold"), 
                bg=bg_color
            )
            label.grid(row=0, column=col, sticky="w", padx=5)

    def create_behavior_entries(self, parent, bg_color):
        entries_frame = tk.Frame(parent, bg=bg_color)
        entries_frame.pack(fill=tk.X, padx=20)
        
        # Configure column weights to match headers
        entries_frame.grid_columnconfigure(0, weight=3, minsize=200)  # Name
        entries_frame.grid_columnconfigure(1, weight=2, minsize=100)  # Key
        entries_frame.grid_columnconfigure(2, weight=2, minsize=150)  # Type
        entries_frame.grid_columnconfigure(3, weight=2, minsize=100)  # ME Group

        for i in range(25):
            name_var = tk.StringVar()
            key_var = tk.StringVar()
            type_var = tk.StringVar(value='point')
            me_group_var = tk.StringVar()

            self.name_vars.append(name_var)
            self.key_vars.append(key_var)
            self.type_vars.append(type_var)
            self.me_group_vars.append(me_group_var)

            # Create row frame
            row_frame = tk.Frame(entries_frame, bg=bg_color)
            row_frame.grid(row=i, column=0, columnspan=4, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(0, weight=3)
            row_frame.grid_columnconfigure(1, weight=2)
            row_frame.grid_columnconfigure(2, weight=2)
            row_frame.grid_columnconfigure(3, weight=2)

            # Add entries to row
            name_entry = tk.Entry(row_frame, textvariable=name_var, font=("Helvetica", 12))
            name_entry.grid(row=0, column=0, sticky="ew", padx=5)

            key_entry = tk.Entry(row_frame, textvariable=key_var, font=("Helvetica", 12), width=10)
            key_entry.grid(row=0, column=1, sticky="w", padx=5)

            type_frame = tk.Frame(row_frame, bg=bg_color)
            type_frame.grid(row=0, column=2, sticky="w", padx=5)

            point_radio = tk.Radiobutton(type_frame, text="Point", variable=type_var, 
                                       value='point', font=("Helvetica", 12), bg=bg_color)
            state_radio = tk.Radiobutton(type_frame, text="State", variable=type_var, 
                                       value='state', font=("Helvetica", 12), bg=bg_color)
            point_radio.pack(side="left", padx=2)
            state_radio.pack(side="left", padx=2)

            me_group_entry = tk.Entry(row_frame, textvariable=me_group_var, 
                                    font=("Helvetica", 12), width=10)
            me_group_entry.grid(row=0, column=3, sticky="w", padx=5)

            self.behavior_entries.extend([name_entry, key_entry, point_radio, state_radio, me_group_entry])

    def create_control_buttons(self, parent, bg_color):
        frame = tk.Frame(parent, bg=bg_color)
        frame.pack(fill=tk.X, expand=True, pady=5)
        
        # Left-aligned buttons
        left_frame = tk.Frame(frame, bg=bg_color)
        left_frame.pack(side=tk.LEFT)
        
        buttons = [
            ("Save", self.save_behaviors),
            ("Rename", self.rename_behavior_key),  # Added Rename button
            ("Delete", self.delete_behavior_key),
            ("Cancel", self.on_cancel)
        ]
        
        for text, command in buttons:
            btn = tk.Button(left_frame, text=text, font=("Helvetica", 12),
                            command=command, bg=bg_color)
            btn.pack(side=tk.LEFT, padx=5)
        
        # Right-aligned Start Video button
        start_button = tk.Button(frame, text="Start Video", font=("Helvetica", 12, "bold"),
                                 command=self.start_video, bg=bg_color)
        start_button.pack(side=tk.RIGHT, padx=5)

    def create_reserved_keys_label(self, parent, bg_color):
        label = tk.Label(
            parent,
            text="Note: 'w', 'a', 's', 'd' are reserved for video navigation. Do not assign these keys to a behavior.",
            font=("Helvetica", 12),
            bg=bg_color
        )
        label.pack(fill=tk.X, pady=5)

    def get_behavior_files(self):
        """Get list of behavior files and organize them with last used first"""
        behavior_files = [f for f in os.listdir(self.behavior_key_dir) if f.endswith('_behaviors.csv')]
        self.behavior_key_files = {f: os.path.join(self.behavior_key_dir, f) for f in behavior_files}
        
        # If there's a last used behavior key, move it to the front of the list
        last_key = self.config_manager.get_last_behavior_key()
        if last_key and last_key in behavior_files:
            behavior_files.remove(last_key)
            behavior_files.insert(0, last_key)
        
        return behavior_files

    def behavior_key_file_var_changed(self, *args):
        """Handle behavior key file changes"""
        print("\n=== Behavior key file var changed ===")
        selected_file = self.behavior_key_file_var.get()
        print(f"Selected file: {selected_file}")
        
        if selected_file and selected_file != 'No file found':
            self.behavior_key_file = os.path.join(self.behavior_key_dir, selected_file)
            print(f"Loading behavior key file from: {self.behavior_key_file}")
            
            # Update config manager with the new selection
            print(f"Updating config with last key: {selected_file}")
            self.config_manager.update_last_behavior_key(selected_file)
            
            self.load_behaviors()
            print(f"Loaded behaviors: {self.behaviors[:2]}...")  # Show first two behaviors
            self.update_behavior_entries()
        
        print("=== Behavior key file var change complete ===\n")

    def load_behaviors(self):
        if os.path.exists(self.behavior_key_file):
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
            except Exception as e:
                print(f"Error loading behaviors: {e}")
                self.behaviors = [["", "", "point", ""] for _ in range(20)]
        else:
            self.behaviors = [["", "", "point", ""] for _ in range(20)]

    def update_behavior_entries(self):
        for i, (name_var, key_var, type_var, me_group_var) in enumerate(
            zip(self.name_vars, self.key_vars, self.type_vars, self.me_group_vars)
        ):
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

    def create_file_selection_frame(self, parent, bg_color):
        """Create file selection UI with last used behavior key handling"""
        frame = tk.Frame(parent, bg=bg_color)
        frame.pack(fill=tk.X, expand=True)
        frame.grid_columnconfigure(1, weight=1)

        file_label = tk.Label(
            frame, 
            text="Select Behavior Key File:", 
            font=("Helvetica", 12, "bold"),
            bg=bg_color
        )
        file_label.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)

        # Get behavior files
        behavior_files = self.get_behavior_files()
        display_files = [f.replace('_behaviors.csv', '') for f in behavior_files] if behavior_files else ["No file found"]
        self.file_display_map = dict(zip(display_files, behavior_files))

        style = ttk.Style()
        style.configure('Custom.TCombobox', 
                       fieldbackground='white',
                       background='white',
                       arrowsize=20)
        
        self.root.option_add('*TCombobox*Listbox.font', ('Helvetica', 12))
                       
        self.behavior_key_combo = ttk.Combobox(
            frame,
            values=display_files,
            style='Custom.TCombobox',
            state='readonly',
            font=("Helvetica", 12)
        )
        
        self.behavior_key_combo.grid(
            row=0, 
            column=1, 
            sticky="ew", 
            padx=(5, 10), 
            pady=5,
            ipady=3
        )

        # Bind the combobox selection event
        def on_select(event):
            selected_display = self.behavior_key_combo.get()
            if selected_display in self.file_display_map:
                full_filename = self.file_display_map[selected_display]
                self.behavior_key_file = os.path.join(self.behavior_key_dir, full_filename)
                self.behavior_key_file_var.set(full_filename)
                self.load_behaviors()
                self.update_behavior_entries()
                # Update config after selection
                self.config_manager.update_last_behavior_key(full_filename)
                print(f"Updated selection to: {full_filename}")
        
        self.behavior_key_combo.bind('<<ComboboxSelected>>', on_select)

        new_file_button = tk.Button(
            frame, 
            text="New Behavior Key File",
            font=("Helvetica", 12),
            command=self.new_behavior_key_file,
            bg=bg_color
        )
        new_file_button.grid(row=0, column=2, sticky="e", padx=(5, 10), pady=5)

    def update_behavior_key_menu(self):
        """Update the Combobox with current behavior files"""
        behavior_files = self.get_behavior_files()
        display_files = [f.replace('_behaviors.csv', '') for f in behavior_files] if behavior_files else ["No file found"]
        self.file_display_map = dict(zip(display_files, behavior_files))
        self.behavior_key_combo['values'] = display_files

    def new_behavior_key_file(self):
        if self.new_behavior_dialog_open:
            return

        self.new_behavior_dialog_open = True
        
        if self.behavior_key_file_var.get() and self.behavior_key_file_var.get() != 'No file found':
            if not self.save_behaviors():
                self.new_behavior_dialog_open = False
                return

        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("New Behavior Key File")
        dialog.attributes('-topmost', True)
        dialog.transient(self.root)
        
        label = tk.Label(dialog, text="Enter a name for the new Behavior Key file:", font=("Helvetica", 12))
        label.pack(pady=10)

        hint_label = tk.Label(
            dialog, 
            text="Use only letters, numbers, and underscores",
            font=("Helvetica", 10, "italic"),
            fg="gray"
        )
        hint_label.pack(pady=(0, 5))

        entry = tk.Entry(dialog, width=30, font=("Helvetica", 12))
        entry.pack(padx=20, pady=5)
        entry.focus_set()

        def validate_filename(name):
            import re
            return bool(re.match(r'^[a-zA-Z0-9_]+$', name))

        def show_invalid_chars_warning():
            warning = tk.Toplevel(dialog)
            warning.withdraw()
            warning.title("Invalid Characters")
            warning.attributes('-topmost', True)
            warning.transient(dialog)
            
            msg = "File name can only contain letters, numbers, and underscores.\nNo spaces or special characters allowed."
            label = tk.Label(warning, text=msg, wraplength=350, font=("Helvetica", 12))
            label.pack(pady=10, padx=10)
            
            ok_button = tk.Button(
                warning, 
                text="OK",
                command=warning.destroy,
                font=("Helvetica", 12)
            )
            ok_button.pack(pady=5)
            
            self.center_window(warning, 400, 150)
            warning.grab_set()
            warning.deiconify()
            warning.focus_set()

        def on_ok():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showwarning("No Name Entered", "You must enter a name for the Behavior Key file.")
                return
                
            if not validate_filename(new_name):
                show_invalid_chars_warning()
                return

            if not new_name.endswith('_behaviors.csv'):
                new_name += '_behaviors.csv'

            self.behavior_key_file = os.path.join(self.behavior_key_dir, new_name)
            self.behaviors = [["", "", "point", ""] for _ in range(20)]
            
            try:
                with open(self.behavior_key_file, 'w', newline='') as file:
                    writer = csv.writer(file)
                    for behavior in self.behaviors:
                        writer.writerow(behavior)
                        
                self.behavior_key_files[new_name] = self.behavior_key_file
                self.update_behavior_key_menu()
                display_name = new_name.replace('_behaviors.csv', '')
                self.behavior_key_combo.set(display_name)
                self.behavior_key_file_var.set(new_name)
                self.behavior_key_file_var_changed()
                
            except Exception as e:
                print(f"Error creating new file: {e}")
                return
            finally:
                dialog.destroy()
                self.new_behavior_dialog_open = False

        ok_button = tk.Button(dialog, text="OK", command=on_ok, font=("Helvetica", 12))
        ok_button.pack(pady=5)
        
        self.center_window(dialog, 350, 150)
        dialog.grab_set()
        dialog.deiconify()
        dialog.protocol("WM_DELETE_WINDOW", lambda: [dialog.destroy(), setattr(self, 'new_behavior_dialog_open', False)])

    def rename_behavior_key(self):
        selected_display = self.behavior_key_combo.get()
        if selected_display and selected_display != 'No file found':
            selected_file = self.file_display_map.get(selected_display)
            if selected_file:
                # Create rename dialog
                rename_dialog = tk.Toplevel(self.root)
                rename_dialog.withdraw()
                rename_dialog.title("Rename Behavior Key File")
                rename_dialog.attributes('-topmost', True)
                rename_dialog.transient(self.root)
                
                label = tk.Label(
                    rename_dialog, 
                    text="Enter new name for the Behavior Key file:",
                    font=("Helvetica", 12)
                )
                label.pack(pady=10)

                hint_label = tk.Label(
                    rename_dialog, 
                    text="Use only letters, numbers, and underscores",
                    font=("Helvetica", 10, "italic"),
                    fg="gray"
                )
                hint_label.pack(pady=(0, 5))

                entry = tk.Entry(rename_dialog, width=30, font=("Helvetica", 12))
                entry.insert(0, selected_display)  # Pre-fill with current name
                entry.pack(padx=20, pady=5)
                entry.focus_set()

                def validate_filename(name):
                    import re
                    return bool(re.match(r'^[a-zA-Z0-9_]+$', name))

                def show_invalid_chars_warning():
                    warning = tk.Toplevel(rename_dialog)
                    warning.withdraw()
                    warning.title("Invalid Characters")
                    warning.attributes('-topmost', True)
                    warning.transient(rename_dialog)
                    
                    msg = "File name can only contain letters, numbers, and underscores.\nNo spaces or special characters allowed."
                    label = tk.Label(warning, text=msg, wraplength=350, font=("Helvetica", 12))
                    label.pack(pady=10, padx=10)
                    
                    ok_button = tk.Button(
                        warning, 
                        text="OK",
                        command=warning.destroy,
                        font=("Helvetica", 12)
                    )
                    ok_button.pack(pady=5)
                    
                    self.center_window(warning, 400, 150)
                    warning.grab_set()
                    warning.deiconify()
                    warning.focus_set()

                def on_rename():
                    new_name = entry.get().strip()
                    if not new_name:
                        messagebox.showwarning("No Name Entered", "You must enter a name for the Behavior Key file.")
                        return
                        
                    if not validate_filename(new_name):
                        show_invalid_chars_warning()
                        return

                    new_filename = f"{new_name}_behaviors.csv"
                    old_path = os.path.join(self.behavior_key_dir, selected_file)
                    new_path = os.path.join(self.behavior_key_dir, new_filename)

                    if os.path.exists(new_path):
                        messagebox.showwarning("File Exists", "A file with this name already exists.")
                        return

                    try:
                        os.rename(old_path, new_path)
                        # Update file references
                        self.behavior_key_file = new_path
                        self.update_behavior_key_menu()
                        self.behavior_key_combo.set(new_name)
                        self.behavior_key_file_var.set(new_filename)
                        rename_dialog.destroy()
                    except Exception as e:
                        self.show_error("Error", f"Failed to rename the file: {e}")

                button_frame = tk.Frame(rename_dialog)
                button_frame.pack(pady=10)

                ok_button = tk.Button(
                    button_frame,
                    text="Rename",
                    command=on_rename,
                    font=("Helvetica", 12)
                )
                ok_button.pack(side=tk.LEFT, padx=5)

                cancel_button = tk.Button(
                    button_frame,
                    text="Cancel",
                    command=rename_dialog.destroy,
                    font=("Helvetica", 12)
                )
                cancel_button.pack(side=tk.LEFT, padx=5)

                self.center_window(rename_dialog, 400, 200)
                rename_dialog.grab_set()
                rename_dialog.deiconify()
            else:
                self.show_warning("Error", "Could not find the selected file.")
        else:
            self.show_warning("No Selection", "Please select a Behavior Key file to rename.")

    def delete_behavior_key(self):
        selected_display = self.behavior_key_combo.get()
        if selected_display and selected_display != 'No file found':
            selected_file = self.file_display_map.get(selected_display)
            if selected_file:
                # Create confirmation dialog
                confirm_dialog = tk.Toplevel(self.root)
                confirm_dialog.withdraw()
                confirm_dialog.title("Delete Confirmation")
                confirm_dialog.attributes('-topmost', True)
                confirm_dialog.transient(self.root)
                
                msg = f"Are you sure you want to delete '{selected_display}'?"
                label = tk.Label(confirm_dialog, text=msg, wraplength=350)
                label.pack(pady=10, padx=10)
                
                def on_yes():
                    confirm_dialog.destroy()
                    try:
                        os.remove(self.behavior_key_files[selected_file])
                        del self.behavior_key_files[selected_file]
                        
                        # Update the display
                        behavior_files = self.get_behavior_files()
                        if behavior_files:
                            self.update_behavior_key_menu()
                            display_name = behavior_files[0].replace('_behaviors.csv', '')
                            self.behavior_key_combo.set(display_name)
                            self.behavior_key_file_var.set(behavior_files[0])
                            self.behavior_key_file_var_changed()
                        else:
                            self.behavior_key_combo['values'] = ["No file found"]
                            self.behavior_key_combo.set("No file found")
                            self.behavior_key_file_var.set('No file found')
                            self.new_behavior_key_file()
                    except Exception as e:
                        self.show_error("Error", f"Failed to delete the file: {e}")

                def on_no():
                    confirm_dialog.destroy()
                    
                button_frame = tk.Frame(confirm_dialog)
                button_frame.pack(pady=5)
                
                yes_button = tk.Button(button_frame, text="Yes", command=on_yes, width=10)
                no_button = tk.Button(button_frame, text="No", command=on_no, width=10)
                yes_button.pack(side=tk.LEFT, padx=5)
                no_button.pack(side=tk.LEFT, padx=5)
                
                self.center_window(confirm_dialog, 400, 150)
                confirm_dialog.grab_set()
                confirm_dialog.deiconify()
                confirm_dialog.focus_set()
            else:
                self.show_warning("Error", "Could not find the selected file.")
        else:
            self.show_warning("No Selection", "Please select a Behavior Key file to delete.")

    def save_behaviors(self):
        """Save behaviors and update last used key in config"""
        selected_file = self.behavior_key_file_var.get()
        if not selected_file or selected_file == 'No file found':
            self.new_behavior_key_file()
            return False

        try:
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
                print(f"Behaviors saved to {self.behavior_key_file}")
                
                # Update last used key in config after successful save
                self.config_manager.update_last_behavior_key(selected_file)
                return True
        except Exception as e:
            print(f"Error saving behaviors: {e}")
            return False

    def start_video(self):
        # Validate that at least one behavior is defined
        if not any(name_var.get().strip() for name_var in self.name_vars):
            self.show_warning("No Behaviors Defined", "Please add behaviors before starting the video.")
            return

        # Save current behaviors
        if any(name_var.get().strip() for name_var in self.name_vars):
            if not self.save_behaviors():
                return

        # Validate shortcut keys
        reserved_keys = {'w', 'a', 's', 'd'}
        assigned_keys = set()
        
        for key_var in self.key_vars:
            key = key_var.get().strip().lower()
            if key:
                if key in reserved_keys:
                    self.show_warning(
                        "Invalid Shortcut Key",
                        f"The key '{key}' is reserved for video navigation.\nPlease assign a different key."
                    )
                    return
                if key in assigned_keys:
                    self.show_warning(
                        "Duplicate Shortcut Key",
                        f"The key '{key}' is assigned to multiple behaviors.\nPlease assign unique keys."
                    )
                    return
                assigned_keys.add(key)

        # Save the current behavior key file as the last used
        current_file = self.behavior_key_file_var.get()
        if current_file and current_file != 'No file found':
            self.config_manager.update_last_behavior_key(current_file)

        # All validations passed, start video
        self.on_start_video(self.behavior_key_file)
        self.root.destroy()    

    def show_dialog(self, dialog_class, *args, **kwargs):
        """Create and track a new dialog."""
        dialog = dialog_class(self.root, *args, **kwargs)
        self.active_dialogs.append(dialog)
        return dialog

    def show_warning(self, title, message):
        warning = tk.Toplevel(self.root)
        warning.withdraw()
        warning.title(title)
        warning.attributes('-topmost', True)
        warning.transient(self.root)
        
        self.active_dialogs.append(warning)
        
        label = tk.Label(warning, text=message, wraplength=350, font=("Helvetica", 12))  # Added font size
        label.pack(pady=10)
        
        ok_button = tk.Button(warning, text="OK", 
                            command=lambda: [warning.destroy(), 
                                          self.active_dialogs.remove(warning)],
                            font=("Helvetica", 12))  # Added font size
        ok_button.pack(pady=5)
        
        self.center_window(warning, 400, 150)
        warning.grab_set()
        warning.deiconify()
        warning.focus_set()
        warning.wait_window()

    def show_error(self, title, message):
        error_dialog = tk.Toplevel(self.root)
        error_dialog.withdraw()
        error_dialog.title(title)
        error_dialog.attributes('-topmost', True)
        error_dialog.transient(self.root)
        
        self.active_dialogs.append(error_dialog)
        
        label = tk.Label(error_dialog, text=message, wraplength=350, font=("Helvetica", 12))  # Added font size
        label.pack(pady=10, padx=10)
        
        ok_button = tk.Button(error_dialog, text="OK",
                            command=lambda: [error_dialog.destroy(),
                                          self.active_dialogs.remove(error_dialog)],
                            font=("Helvetica", 12))  # Added font size
        ok_button.pack(pady=5)
        
        self.center_window(error_dialog, 400, 150)
        error_dialog.grab_set()
        error_dialog.deiconify()
        error_dialog.focus_set()
        error_dialog.wait_window()

    def center_window(self, window, width, height):
        """Center a window on the primary monitor."""
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        x = primary.x + (primary.width // 2) - (width // 2)
        y = primary.y + (primary.height // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.update_idletasks()

    def on_cancel(self):
        """Handle cancellation of the behavior key editor"""
        if any(name_var.get().strip() for name_var in self.name_vars):
            # Check if there are unsaved changes
            current_behaviors = []
            for i in range(len(self.behaviors)):
                current_behaviors.append([
                    self.name_vars[i].get(),
                    self.key_vars[i].get(),
                    self.type_vars[i].get(),
                    self.me_group_vars[i].get()
                ])
            
            if current_behaviors != self.behaviors:
                dialog = tk.Toplevel(self.root)
                dialog.withdraw()
                dialog.title("Unsaved Changes")
                dialog.attributes('-topmost', True)
                dialog.transient(self.root)
                
                msg = "You have unsaved changes. Do you want to save before closing?"
                label = tk.Label(dialog, text=msg, wraplength=350, font=("Helvetica", 12))
                label.pack(pady=10, padx=10)
                
                button_frame = tk.Frame(dialog)
                button_frame.pack(pady=5)
                
                def on_save():
                    if self.save_behaviors():
                        dialog.destroy()
                        self.root.destroy()
                    
                def on_dont_save():
                    dialog.destroy()
                    self.root.destroy()
                    
                def on_cancel():
                    dialog.destroy()
                
                save_button = tk.Button(button_frame, text="Save", command=on_save, 
                                      font=("Helvetica", 12), width=10)
                dont_save_button = tk.Button(button_frame, text="Don't Save", 
                                           command=on_dont_save, font=("Helvetica", 12), width=10)
                cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel, 
                                        font=("Helvetica", 12), width=10)
                
                save_button.pack(side=tk.LEFT, padx=5)
                dont_save_button.pack(side=tk.LEFT, padx=5)
                cancel_button.pack(side=tk.LEFT, padx=5)
                
                self.center_window(dialog, 400, 150)
                dialog.grab_set()
                dialog.deiconify()
                dialog.focus_set()
                dialog.wait_window()
            else:
                self.root.destroy()
        else:
            self.root.destroy()

    def on_closing(self):
        """Handle window closing by cleaning up dialogs and calling cancel"""
        # Close any active dialogs
        for dialog in self.active_dialogs[:]:  # Create a copy of the list to avoid modification during iteration
            try:
                dialog.destroy()
                self.active_dialogs.remove(dialog)
            except tk.TclError:  # Dialog might already be destroyed
                self.active_dialogs.remove(dialog)
        
        # Call the cancel handler
        self.on_cancel()

    def setup_window_close(self):
        """Setup the window closing behavior"""
        # Bind the window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Bind Escape key to close
        self.root.bind('<Escape>', lambda e: self.on_closing())