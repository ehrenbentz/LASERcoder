# file_picker.py

import os
import tkinter as tk
from tkinter import ttk
from screeninfo import get_monitors

class FilePicker(tk.Toplevel):
    def __init__(self, parent, initial_dir=os.getcwd(),
                 file_types=(".mp4", ".avi", ".mov", ".mts", ".mkv")):
        super().__init__(parent)
        self.title("LaserTAG - Select a Video File")
        self.file_types = file_types
        self.selected_file = None
        self.parent = parent
        self.initial_dir = os.path.abspath(initial_dir)
        self.current_dir = self.initial_dir

        # Colors
        bg_color = "lightgrey"
        list_bg = "white"

        # Size and placement (initial geometry; will be re-centered)
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        window_width = int(primary.width * 0.35)
        window_height = int(primary.height * 0.5)
        x = primary.x + (primary.width - window_width) // 2
        y = primary.y + (primary.height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Configure ttk styles
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TPanedwindow", background=bg_color)
        large_font = ("Helvetica", 12)  # Adjusted font size
        self.style.configure("TButton", font=large_font, padding=(5,2,5,2))
        self.style.configure("FileLabel.TLabel", font=("Helvetica", 12, "bold"), background=bg_color)
        # Configure a custom style for the top bar using list_bg:
        self.style.configure("TopBar.TFrame", background=bg_color)
        self.configure(background=bg_color)

        # --- Top area: Up button and current directory Entry ---
        temp_frame = ttk.Frame(self, style="TopBar.TFrame")
        temp_frame.pack(fill="x", padx=5, pady=(5,0))
        top_dir_frame = ttk.Frame(temp_frame, style="TopBar.TFrame")
        top_dir_frame.pack(fill="x", expand=True)
        # Up button with reduced width and custom padding
        self.style.configure("Custom.TButton", padding=(2, 0))
        up_btn = ttk.Button(top_dir_frame, text="↑", width=1, style="Custom.TButton", command=self.go_up)
        up_btn.grid(row=0, column=0, padx=(5,5), sticky="ns")
        # Current directory Entry
        self.current_dir_entry = tk.Entry(top_dir_frame, font=("Helvetica", 12), relief="ridge", bd=2, bg="white")
        self.current_dir_entry.grid(row=0, column=1, sticky="ew")
        top_dir_frame.columnconfigure(1, weight=1)
        self.current_dir_entry.insert(0, self.initial_dir)
        self.current_dir_entry.bind("<Return>", self.on_entry_update)

        # --- Paned window for directory list and file list ---
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        paned.pack(fill="both", expand=True, padx=5, pady=(0,5))

        # --- Directory list panel (left) ---
        self.dir_panel = ttk.Frame(paned, style="TFrame")
        paned.add(self.dir_panel, weight=1)
        dir_container = tk.Frame(self.dir_panel, bg=bg_color)
        dir_container.pack(fill="both", expand=True, padx=5, pady=5)
        self.dir_listbox = tk.Listbox(dir_container, font=("Helvetica", 12), bg=list_bg, bd=2, relief="ridge")
        self.dir_listbox.pack(side="left", fill="both", expand=True)
        dir_scrollbar = ttk.Scrollbar(dir_container, orient="vertical", command=self.dir_listbox.yview)
        dir_scrollbar.pack(side="right", fill="y")
        self.dir_listbox.configure(yscrollcommand=dir_scrollbar.set)
        # Bind double-click on a directory to update current directory
        self.dir_listbox.bind("<Double-Button-1>", self.on_dir_double_click)
        self.populate_dir_list(self.initial_dir)

        # --- File list panel (right) ---
        self.file_frame = ttk.Frame(paned, style="TFrame")
        paned.add(self.file_frame, weight=3)
        file_label = ttk.Label(self.file_frame, text="Video Files:", style="FileLabel.TLabel")
        file_label.pack(pady=(5, 0), padx=5, anchor="w")
        file_container = tk.Frame(self.file_frame, bg=bg_color)
        file_container.pack(fill="both", expand=True, padx=5, pady=(0,5))
        self.file_listbox = tk.Listbox(file_container, font=("Helvetica", 12), bg=list_bg, bd=2, relief="ridge")
        self.file_listbox.pack(side="left", fill="both", expand=True)
        self.file_listbox.bind("<Double-Button-1>", self.select_file)
        file_scrollbar = ttk.Scrollbar(file_container, orient="vertical", command=self.file_listbox.yview)
        file_scrollbar.pack(side="right", fill="y")
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)

        # --- Bottom button frame ---
        bottom_btn_frame = ttk.Frame(self, style="TFrame")
        bottom_btn_frame.pack(fill="x", padx=10, pady=5)
        select_btn = ttk.Button(bottom_btn_frame, text="Select", command=self.select_file)
        select_btn.pack(side="right", padx=5, pady=(2,2))
        cancel_btn = ttk.Button(bottom_btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right", padx=5, pady=(2,2))

        self.populate_file_list(self.initial_dir)
        # Center the window on the primary monitor
        self.center_window(self, window_width, window_height)

    def on_entry_update(self, event):
        new_dir = self.current_dir_entry.get().strip()
        if os.path.isdir(new_dir):
            self.current_dir = new_dir
            self.populate_file_list(new_dir)
            self.populate_dir_list(new_dir)
        else:
            print("Not a valid directory.")

    def go_up(self):
        parent_dir = os.path.dirname(self.current_dir)
        if not parent_dir or parent_dir == self.current_dir:
            return
        self.current_dir = parent_dir
        self.populate_file_list(parent_dir)
        self.populate_dir_list(parent_dir)
        self.current_dir_entry.delete(0, tk.END)
        self.current_dir_entry.insert(0, parent_dir)

    def populate_dir_list(self, directory):
        self.dir_listbox.delete(0, tk.END)
        if not os.path.isdir(directory):
            return
        try:
            dirs = [d for d in os.listdir(directory)
                    if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.') and not d.startswith('__')]
            dirs.sort()
        except Exception:
            dirs = []
        for d in dirs:
            self.dir_listbox.insert(tk.END, d)

    def on_dir_double_click(self, event):
        selection = self.dir_listbox.curselection()
        if selection:
            dir_name = self.dir_listbox.get(selection[0])
            new_dir = os.path.join(self.current_dir, dir_name)
            if os.path.isdir(new_dir):
                self.current_dir = new_dir
                self.current_dir_entry.delete(0, tk.END)
                self.current_dir_entry.insert(0, new_dir)
                self.populate_file_list(new_dir)
                self.populate_dir_list(new_dir)

    def populate_file_list(self, directory):
        self.file_listbox.delete(0, tk.END)
        if not os.path.isdir(directory):
            return
        try:
            items = os.listdir(directory)
        except Exception:
            return
        video_files = [f for f in items if os.path.isfile(os.path.join(directory, f))
                       and not f.startswith('.')
                       and f.lower().endswith(tuple(ext.lower() for ext in self.file_types))]
        for f in sorted(video_files):
            self.file_listbox.insert(tk.END, f)

    def select_file(self, event=None):
        selection = self.file_listbox.curselection()
        if selection:
            file_name = self.file_listbox.get(selection[0])
            self.selected_file = os.path.join(self.current_dir, file_name)
            self.destroy()
        else:
            # Create a popup notification window as Toplevel
            popup = tk.Toplevel(self)
            popup.title("Note")
                
            # Set fixed dimensions for the popup
            popup_width = 300
            popup_height = 150
                
            # Use the existing center_window method
            self.center_window(popup, popup_width, popup_height)
                
            # Configure popup style
            popup.configure(background="lightgrey")
                
            # Configure a new style for the popup label
            self.style.configure("Popup.TLabel", 
                               background="lightgrey",
                               font=("Helvetica", 12, "bold"))
                
            # Add message with centered text using new style
            message = ttk.Label(popup, text="You must select a video\nfile to proceed",
                              style="Popup.TLabel",
                              wraplength=250,
                              justify="center",
                              anchor="center")
            message.pack(pady=20, fill="x")
                
            # Add OK button
            ok_button = ttk.Button(popup, text="OK", command=popup.destroy)
            ok_button.pack(pady=5)
                
            # Bind Enter key to close dialog
            popup.bind('<Return>', lambda e: popup.destroy())
                
            # Make the popup modal (user must interact with it)
            popup.transient(self)
            popup.grab_set()
            popup.focus_set()
            self.wait_window(popup)

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