import os
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from screeninfo import get_monitors
from pathlib import Path

class NewDirectoryDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Create Directory")
        self.result = None
        
        # Set size and position
        width = 300
        height = 150
        self.geometry(f"{width}x{height}")
        self.center_window(width, height)
        
        # Configure style
        self.configure(background="lightgrey")
        
        # Add label
        label = ttk.Label(self, text="Enter new directory name:", 
                         font=("Helvetica", 12),
                         background="lightgrey")
        label.pack(pady=(20,10))
        
        # Add entry
        self.entry = tk.Entry(self, font=("Helvetica", 12), width=30)
        self.entry.pack(pady=(0,20))
        self.entry.focus_set()
        
        # Add buttons frame
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=20)
        
        # Add buttons
        ok_btn = ttk.Button(btn_frame, text="OK", command=self.ok_clicked)
        ok_btn.pack(side="left", expand=True, padx=5)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.cancel_clicked)
        cancel_btn.pack(side="right", expand=True, padx=5)
        
        # Bind enter and escape
        self.bind("<Return>", lambda e: self.ok_clicked())
        self.bind("<Escape>", lambda e: self.cancel_clicked())
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
    def ok_clicked(self):
        self.result = self.entry.get()
        self.destroy()
        
    def cancel_clicked(self):
        self.destroy()
        
    def center_window(self, width, height):
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        x = primary.x + (primary.width // 2) - (width // 2)
        y = primary.y + (primary.height // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

class FilesManager(tk.Toplevel):
    def __init__(self, parent, initial_output_dir=str(Path.home()), 
                 initial_video_dir=str(Path.home()),
                 file_types=(".mp4", ".avi", ".mov", ".mts", ".mkv")):
        super().__init__(parent)
        self.title("LaserTAG - Select Output Directory and Video File")

        # Platform-specific window settings
        if platform.system() == "Windows":
            self.state('zoomed')
        elif platform.system() == "Darwin":
            self.state('zoomed')
        elif platform.system() == "Linux":
            self.attributes("-zoomed", True)

        self.file_types = file_types
        self.selected_video_file = None
        self.output_dir = initial_output_dir  # Initialize with home directory
        self.parent = parent

        self.initial_output_dir = os.path.abspath(initial_output_dir)
        self.initial_video_dir = os.path.abspath(initial_video_dir)
        self.current_output_dir = self.initial_output_dir
        self.current_video_dir = self.initial_video_dir

        # Styling
        self.setup_styles()

        # Create a PanedWindow with two panels
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Left panel: Output Directory Selector (1/3 width)
        self.output_dir_panel = ttk.Frame(paned, style="TFrame")
        paned.add(self.output_dir_panel)

        # Right panel: Video File Selector (2/3 width)
        self.video_file_panel = ttk.Frame(paned, style="TFrame")
        paned.add(self.video_file_panel)

        # Force the initial position of the sash
        def set_sash_position(event=None):
            width = paned.winfo_width()
            paned.sashpos(0, (width * 2) // 5)
            
        paned.bind('<Map>', set_sash_position)
        self.create_output_dir_ui()
        self.create_video_file_ui()

    def setup_styles(self):
        bg_color = "lightgrey"
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TPanedwindow", background=bg_color)
        self.style.configure("TopBar.TFrame", background=bg_color)
        large_font = ("Helvetica", 12)
        self.style.configure("TButton", font=large_font, padding=(5,2,5,2))
        self.style.configure("Custom.TButton", padding=(2, 0))
        self.style.configure("Label.TLabel", font=("Helvetica", 12, "bold"), background=bg_color)
        self.configure(background=bg_color)

    def create_output_dir_ui(self):
        # Label
        label = ttk.Label(self.output_dir_panel, text="Select Output Directory:", style="Label.TLabel")
        label.pack(pady=(5,0), padx=5, anchor="w")

        # Directory navigation frame
        nav_frame = ttk.Frame(self.output_dir_panel, style="TopBar.TFrame")
        nav_frame.pack(fill="x", padx=5, pady=(0,5))
        
        # Up button
        up_btn = ttk.Button(nav_frame, text="↑", width=3, style="Custom.TButton", 
                           command=lambda: self.go_up('output'))
        up_btn.pack(side="left", padx=(0,5))
        
        # Entry to show current output directory
        self.output_dir_entry = tk.Entry(nav_frame, font=("Helvetica", 12), 
                                       bg="white", bd=2, relief="ridge")
        self.output_dir_entry.pack(fill="x", expand=True)
        self.output_dir_entry.insert(0, self.initial_output_dir)
        self.output_dir_entry.bind("<Return>", self.on_output_dir_update)

        # Listbox to show subdirectories
        self.output_dir_listbox = tk.Listbox(self.output_dir_panel, 
                                           font=("Helvetica", 12), 
                                           bg="white", bd=2, relief="ridge")
        self.output_dir_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.output_dir_listbox.bind("<Double-Button-1>", self.on_output_dir_double_click)
        
        # Bottom frame for buttons and label
        bottom_frame = ttk.Frame(self.output_dir_panel, style="TFrame")
        bottom_frame.pack(fill="x", padx=5, pady=(0,5))

        # Selected directory label
        self.dir_selected = tk.StringVar(value=f"Selected Output Directory: {self.initial_output_dir}")
        self.dir_selected_label = ttk.Label(bottom_frame, 
                                          textvariable=self.dir_selected,
                                          font=("Helvetica", 13))
        self.dir_selected_label.pack(fill="x", pady=(0,5))

        # Button frame
        button_frame = ttk.Frame(bottom_frame, style="TFrame")
        button_frame.pack(fill="x")
        
        # Create Directory button
        create_dir_btn = ttk.Button(button_frame, text="Create Directory", 
                                  command=self.create_directory)
        create_dir_btn.pack(side="left", padx=2)
        
        # Select Directory button
        select_dir_btn = ttk.Button(button_frame, text="Select Directory", 
                                  command=self.select_directory)
        select_dir_btn.pack(side="left", padx=2)
        
        self.populate_dir_list(self.initial_output_dir)

    def create_video_file_ui(self):
        # Label
        label = ttk.Label(self.video_file_panel, text="Select Video File:", style="Label.TLabel")
        label.pack(pady=(5,0), padx=5, anchor="w")

        # Directory navigation frame
        nav_frame = ttk.Frame(self.video_file_panel, style="TopBar.TFrame")
        nav_frame.pack(fill="x", padx=5, pady=(0,5))
        
        # Up button
        up_btn = ttk.Button(nav_frame, text="↑", width=3, style="Custom.TButton", 
                           command=lambda: self.go_up('video'))
        up_btn.pack(side="left", padx=(0,5))
        
        # Entry to show current video directory
        self.video_dir_entry = tk.Entry(nav_frame, font=("Helvetica", 12), 
                                      bg="white", bd=2, relief="ridge")
        self.video_dir_entry.pack(fill="x", expand=True)
        self.video_dir_entry.insert(0, self.initial_video_dir)
        self.video_dir_entry.bind("<Return>", self.on_video_dir_update)

        # Create a frame for both listboxes
        lists_frame = ttk.Frame(self.video_file_panel, style="TFrame")
        lists_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left side: Directories
        dir_frame = ttk.Frame(lists_frame, style="TFrame")
        dir_frame.pack(side="left", fill="both", expand=True)
        
        dir_label = ttk.Label(dir_frame, text="Directories:", style="Label.TLabel")
        dir_label.pack(anchor="w")
        
        self.video_dir_listbox = tk.Listbox(dir_frame, font=("Helvetica", 12),
                                          bg="white", bd=2, relief="ridge")
        self.video_dir_listbox.pack(fill="both", expand=True, padx=(0,2))
        self.video_dir_listbox.bind("<Double-Button-1>", self.on_video_dir_double_click)

        # Right side: Video files
        file_frame = ttk.Frame(lists_frame, style="TFrame")
        file_frame.pack(side="right", fill="both", expand=True)
        
        file_label = ttk.Label(file_frame, text="Video Files:", style="Label.TLabel")
        file_label.pack(anchor="w")
        
        self.video_file_listbox = tk.Listbox(file_frame, font=("Helvetica", 12),
                                           bg="white", bd=2, relief="ridge")
        self.video_file_listbox.pack(fill="both", expand=True, padx=(2,0))
        self.video_file_listbox.bind("<Double-Button-1>", self.select_video_file)

        # Select Video button
        select_video_btn = ttk.Button(self.video_file_panel, text="Select Video", 
                                    command=self.select_video_file)
        select_video_btn.pack(side="right", padx=5, pady=(0,5))

        self.populate_video_dir_list(self.initial_video_dir)
        self.populate_file_list(self.initial_video_dir)

    def go_up(self, panel_type):
        if panel_type == 'output':
            parent_dir = os.path.dirname(self.current_output_dir)
            if os.path.exists(parent_dir):
                self.current_output_dir = parent_dir
                self.output_dir_entry.delete(0, tk.END)
                self.output_dir_entry.insert(0, parent_dir)
                self.populate_dir_list(parent_dir)
                # Clear selected directory if changed
                if parent_dir != self.output_dir:
                    self.output_dir = None
                    self.dir_selected.set("Selected Output Directory: None")
        else:  # video panel
            parent_dir = os.path.dirname(self.current_video_dir)
            if os.path.exists(parent_dir):
                self.current_video_dir = parent_dir
                self.video_dir_entry.delete(0, tk.END)
                self.video_dir_entry.insert(0, parent_dir)
                self.populate_video_dir_list(parent_dir)
                self.populate_file_list(parent_dir)

    def create_directory(self):
        dialog = NewDirectoryDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            new_dir_path = os.path.join(self.current_output_dir, dialog.result)
            try:
                os.makedirs(new_dir_path, exist_ok=True)
                self.current_output_dir = new_dir_path
                self.output_dir_entry.delete(0, tk.END)
                self.output_dir_entry.insert(0, new_dir_path)
                self.populate_dir_list(new_dir_path)
                # Clear selected directory when new directory is created
                self.output_dir = None
                self.dir_selected.set("Selected Output Directory: None")
            except Exception as e:
                messagebox.showerror("Error", f"Could not create directory: {str(e)}")

    def select_directory(self):
        selection = self.output_dir_listbox.curselection()
        if selection:
            # If a directory is highlighted, enter and select it
            dir_name = self.output_dir_listbox.get(selection[0])
            new_dir = os.path.join(self.current_output_dir, dir_name)
            if os.path.isdir(new_dir):
                self.current_output_dir = new_dir
                self.output_dir_entry.delete(0, tk.END)
                self.output_dir_entry.insert(0, new_dir)
                self.populate_dir_list(new_dir)
                self.output_dir = new_dir
        else:
            # If no directory is highlighted, select the current directory
            self.output_dir = self.current_output_dir
            
        # Update the selected directory label
        self.dir_selected.set(f"Selected Output Directory: {self.output_dir}")

    def on_output_dir_update(self, event):
        new_dir = self.output_dir_entry.get().strip()
        if os.path.isdir(new_dir):
            self.current_output_dir = new_dir
            self.populate_dir_list(new_dir)
            if new_dir != self.output_dir:
                self.output_dir = None
                self.dir_selected.set("Selected Output Directory: None")
        else:
            print("Not a valid directory.")

    def on_video_dir_update(self, event):
        new_dir = self.video_dir_entry.get().strip()
        if os.path.isdir(new_dir):
            self.current_video_dir = new_dir
            self.populate_video_dir_list(new_dir)
            self.populate_file_list(new_dir)
        else:
            print("Not a valid directory.")

    def on_output_dir_double_click(self, event):
        selection = self.output_dir_listbox.curselection()
        if selection:
            dir_name = self.output_dir_listbox.get(selection[0])
            new_dir = os.path.join(self.current_output_dir, dir_name)
            if os.path.isdir(new_dir):
                self.current_output_dir = new_dir
                self.output_dir_entry.delete(0, tk.END)
                self.output_dir_entry.insert(0, new_dir)
                self.populate_dir_list(new_dir)
                if new_dir != self.output_dir:
                    self.output_dir = None
                    self.dir_selected.set("Selected Output Directory: None")

    def on_video_dir_double_click(self, event):
        selection = self.video_dir_listbox.curselection()
        if selection:
            dir_name = self.video_dir_listbox.get(selection[0])
            new_dir = os.path.join(self.current_video_dir, dir_name)
            if os.path.isdir(new_dir):
                self.current_video_dir = new_dir
                self.video_dir_entry.delete(0, tk.END)
                self.video_dir_entry.insert(0, new_dir)
                self.populate_video_dir_list(new_dir)
                self.populate_file_list(new_dir)

    def populate_dir_list(self, directory):
        self.output_dir_listbox.delete(0, tk.END)
        try:
            dirs = [d for d in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]
            dirs.sort()
        except Exception:
            dirs = []
        for d in dirs:
            self.output_dir_listbox.insert(tk.END, d)

    def populate_video_dir_list(self, directory):
        self.video_dir_listbox.delete(0, tk.END)
        try:
            dirs = [d for d in os.listdir(directory) 
                   if os.path.isdir(os.path.join(directory, d)) and not d.startswith('.')]
            dirs.sort()
        except Exception:
            dirs = []
        for d in dirs:
            self.video_dir_listbox.insert(tk.END, d)

    def populate_file_list(self, directory):
        self.video_file_listbox.delete(0, tk.END)
        try:
            items = os.listdir(directory)
        except Exception:
            return
        video_files = [f for f in items 
                      if os.path.isfile(os.path.join(directory, f)) 
                      and f.lower().endswith(tuple(ext.lower() for ext in self.file_types))]
        for f in sorted(video_files):
            self.video_file_listbox.insert(tk.END, f)

    def select_video_file(self, event=None):
        selection = self.video_file_listbox.curselection()
        if selection:
            if not self.output_dir:
                messagebox.showwarning("Warning", 
                                     "Please select an output directory first using the 'Select Directory' button.")
                return
                
            file_name = self.video_file_listbox.get(selection[0])
            self.selected_video_file = os.path.join(self.current_video_dir, file_name)
            self.destroy()
        else:
            popup = tk.Toplevel(self)
            popup.title("Note")
            popup_width = 300
            popup_height = 150
            self.center_window(popup, popup_width, popup_height)
            popup.configure(background="lightgrey")
            message = ttk.Label(popup, text="You must select a video file to proceed", 
                              style="Label.TLabel", wraplength=250, justify="center", 
                              anchor="center")
            message.pack(pady=20, fill="x")
            ok_button = ttk.Button(popup, text="OK", command=popup.destroy)
            ok_button.pack(pady=5)
            popup.bind('<Return>', lambda e: popup.destroy())
            popup.transient(self)
            popup.grab_set()
            popup.focus_set()
            self.wait_window(popup)

    def center_window(self, win, width, height):
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        x = primary.x + (primary.width // 2) - (width // 2)
        y = primary.y + (primary.height // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.update_idletasks()