import os
import tkinter as tk
from tkinter import ttk, messagebox
from screeninfo import get_monitors

class FilePicker(tk.Toplevel):
    def __init__(self, parent, initial_dir=os.getcwd(), 
                 file_types=(".mp4", ".avi", ".mov", ".MP4", ".AVI", ".MOV", ".mts", ".MTS", ".mkv", ".MKV")):
        super().__init__(parent)
        self.title("Select a Video File")
        self.file_types = file_types
        self.selected_file = None
        self.parent = parent
        self.initial_dir = initial_dir
        print(f"Initial directory: {self.initial_dir}")

        # Get primary monitor dimensions and center the window.
        monitors = get_monitors()
        primary_monitor = next((m for m in monitors if m.is_primary), monitors[0])
        width, height = 500, 400
        x = primary_monitor.x + (primary_monitor.width // 2) - (width // 2)
        y = primary_monitor.y + (primary_monitor.height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Create UI elements.
        self.create_widgets()
        self.populate_file_list(self.initial_dir)

        # Bind the Enter key on the dialog itself.
        self.bind("<Return>", self.select_file)

    def create_widgets(self):
        """Create and layout the widgets in the file picker window."""
        self.folder_label = tk.Label(self, text="Current Folder:", font=("Helvetica", 12, "bold"))
        self.folder_label.pack(pady=5)

        # Folder Entry displays the current directory.
        self.folder_entry = tk.Entry(self, font=("Helvetica", 12))
        self.folder_entry.pack(fill="x", padx=10)
        self.folder_entry.insert(0, self.initial_dir)

        # Listbox for files and folders.
        self.file_listbox = tk.Listbox(self, font=("Helvetica", 12), height=15)
        self.file_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.file_listbox.bind("<Double-Button-1>", self.select_file)  # Double-click selects.
        self.file_listbox.bind("<Return>", self.select_file)          # Enter key selects.
        self.file_listbox.bind("<Up>", self.move_selection_up)
        self.file_listbox.bind("<Down>", self.move_selection_down)

        # Button frame with Up, Select, and Cancel buttons.
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=5)

        self.up_btn = tk.Button(btn_frame, text="Up", command=self.go_up, font=("Helvetica", 12))
        self.up_btn.pack(side="left", padx=10)

        self.select_btn = tk.Button(btn_frame, text="Select", command=self.select_file, font=("Helvetica", 12))
        self.select_btn.pack(side="left", padx=10)

        self.cancel_btn = tk.Button(btn_frame, text="Cancel", command=self.destroy, font=("Helvetica", 12))
        self.cancel_btn.pack(side="right", padx=10)

    def populate_file_list(self, directory):
        """Populate the file listbox with subdirectories and video files in the given directory."""
        self.file_listbox.delete(0, tk.END)

        if not os.path.isdir(directory):
            print(f"Invalid directory: {directory}")
            return

        print(f"Scanning directory: {directory}")

        # List subdirectories and video files.
        items = os.listdir(directory)
        subdirs = [item for item in items if os.path.isdir(os.path.join(directory, item))]
        video_files = [item for item in items if os.path.isfile(os.path.join(directory, item)) 
                       and item.lower().endswith(tuple(ext.lower() for ext in self.file_types))]

        # Insert subdirectories with a “[DIR]” prefix.
        for d in sorted(subdirs):
            self.file_listbox.insert(tk.END, "[DIR] " + d)
        # Insert video files.
        for f in sorted(video_files):
            self.file_listbox.insert(tk.END, f)

    def select_file(self, event=None):
        """Handle selection: if a directory is selected, navigate into it; if a file, set selected_file and close."""
        selection = self.file_listbox.curselection()
        if selection:
            item = self.file_listbox.get(selection[0])
            if item.startswith("[DIR] "):
                # Navigate into the directory.
                folder_name = item.replace("[DIR] ", "", 1)
                new_dir = os.path.join(self.folder_entry.get(), folder_name)
                self.folder_entry.delete(0, tk.END)
                self.folder_entry.insert(0, new_dir)
                self.populate_file_list(new_dir)
            else:
                # A file was selected.
                self.selected_file = os.path.join(self.folder_entry.get(), item)
                self.destroy()

    def move_selection_up(self, event):
        """Move selection up in the file list."""
        current_selection = self.file_listbox.curselection()
        if current_selection:
            new_index = max(0, current_selection[0] - 1)
        else:
            new_index = self.file_listbox.size() - 1
        self.file_listbox.selection_clear(0, tk.END)
        self.file_listbox.selection_set(new_index)
        self.file_listbox.activate(new_index)

    def move_selection_down(self, event):
        """Move selection down in the file list."""
        current_selection = self.file_listbox.curselection()
        if current_selection:
            new_index = min(self.file_listbox.size() - 1, current_selection[0] + 1)
        else:
            new_index = 0
        self.file_listbox.selection_clear(0, tk.END)
        self.file_listbox.selection_set(new_index)
        self.file_listbox.activate(new_index)

    def go_up(self):
        """Go to the parent folder."""
        current_dir = self.folder_entry.get()
        parent_dir = os.path.dirname(current_dir)
        self.folder_entry.delete(0, tk.END)
        self.folder_entry.insert(0, parent_dir)
        self.populate_file_list(parent_dir)
