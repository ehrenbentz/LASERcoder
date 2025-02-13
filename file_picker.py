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

        print(f"Initial directory: {self.initial_dir}")

        # Define a subtle greyscale palette.
        bg_color    = "#2471a3"
        tree_bg = "#eaf2f8"

        # Monitor sizing
        monitors = get_monitors()
        primary = next((m for m in monitors if m.is_primary), monitors[0])
        window_width = int(primary.width * 0.5)
        window_height = int(primary.height * 0.6)
        x = primary.x + (primary.width - window_width) // 3
        y = primary.y + (primary.height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Styling
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Configure backgrounds:
        self.style.configure(
            "TFrame",
            background=bg_color
        )
        self.style.configure(
            "TPanedwindow",
            background=bg_color
        )
        
        large_font = ("Helvetica", 14)
        self.style.configure("Treeview", 
                             font=large_font, 
                             background=tree_bg, 
                             fieldbackground=tree_bg)
        self.style.configure("TButton", font=large_font)
        self.style.configure("FileLabel.TLabel",
                             font=("Helvetica", 13, "bold"),
                             background=bg_color)
        
        # Set the toplevel window background (for non-ttk areas)
        self.configure(background=bg_color)

        # Create a horizontal paned window with our styled background.
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Directory tree panel (ttk.Frame).
        self.dir_frame = ttk.Frame(paned, style="TFrame")
        paned.add(self.dir_frame, weight=1)

        # File list panel (ttk.Frame).
        self.file_frame = ttk.Frame(paned, style="TFrame")
        paned.add(self.file_frame, weight=3)

        # Label at the top for "Video Files:"
        file_label = ttk.Label(
            self.file_frame,
            text="Video Files:",
            style="FileLabel.TLabel"
        )
        file_label.pack(pady=(15, 5), padx=10, anchor="w")

        # Create a single inner frame (non-ttk) for extra padding.
        # Because this is a tk.Frame, we can set bg directly.
        inner_frame = tk.Frame(self.file_frame, bg=bg_color)
        inner_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Directory tree
        self.dir_tree = ttk.Treeview(self.dir_frame, show="tree")
        self.dir_tree.pack(fill="both", expand=True)

        # File list
        self.file_listbox = tk.Listbox(
            inner_frame,
            font=("Helvetica", 16),
            bg=tree_bg
        )
        self.file_listbox.pack(fill="both", expand=True)

        # Buttons at the bottom (ttk.Frame) for background
        btn_frame = ttk.Frame(self, style="TFrame")
        btn_frame.pack(fill="x", padx=10, pady=5)
        select_btn = ttk.Button(btn_frame, text="Select", command=self.select_file)
        select_btn.pack(side="left", padx=5)
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side="right", padx=5)

        # Build the directory tree
        root_node = self.dir_tree.insert(
            "", "end", text=self.initial_dir, open=True, values=[self.initial_dir]
        )
        self.populate_tree(root_node, self.initial_dir)

        # Bind events
        self.dir_tree.bind("<<TreeviewOpen>>", self.on_tree_expand)
        self.dir_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Populate file list
        self.populate_file_list(self.initial_dir)

    def has_subdirectory(self, path):
        """Return True if the directory has any subdirectories."""
        try:
            for entry in os.listdir(path):
                full = os.path.join(path, entry)
                if os.path.isdir(full):
                    return True
        except Exception:
            pass
        return False

    def populate_tree(self, parent_node, parent_path):
        """Populate a tree node with its immediate subdirectories."""
        try:
            subdirs = [
                d for d in os.listdir(parent_path)
                if os.path.isdir(os.path.join(parent_path, d))
            ]
            subdirs.sort()
        except Exception:
            subdirs = []
        for d in subdirs:
            full_path = os.path.join(parent_path, d)
            node = self.dir_tree.insert(parent_node, "end", text=d, values=[full_path])
            if self.has_subdirectory(full_path):
                self.dir_tree.insert(node, "end", text="dummy")

    def on_tree_expand(self, event):
        """When a tree node is expanded, populate it if needed."""
        node = self.dir_tree.focus()
        path = self.dir_tree.item(node, "values")[0]
        children = self.dir_tree.get_children(node)
        if children:
            first_child = children[0]
            if self.dir_tree.item(first_child, "text") == "dummy":
                self.dir_tree.delete(first_child)
                self.populate_tree(node, path)

    def on_tree_select(self, event):
        """When a directory is selected in the tree, update the file list."""
        node = self.dir_tree.focus()
        if node:
            path = self.dir_tree.item(node, "values")[0]
            self.current_dir = path
            self.populate_file_list(path)

    def populate_file_list(self, directory):
        """Populate the file listbox with video files from the selected directory."""
        self.file_listbox.delete(0, tk.END)
        if not os.path.isdir(directory):
            return
        try:
            items = os.listdir(directory)
        except Exception:
            return
        video_files = [
            f for f in items
            if os.path.isfile(os.path.join(directory, f))
            and f.lower().endswith(tuple(ext.lower() for ext in self.file_types))
        ]
        for f in sorted(video_files):
            self.file_listbox.insert(tk.END, f)

    def select_file(self, event=None):
        """Select the file and close the dialog."""
        selection = self.file_listbox.curselection()
        if selection:
            file_name = self.file_listbox.get(selection[0])
            self.selected_file = os.path.join(self.current_dir, file_name)
        self.destroy()
