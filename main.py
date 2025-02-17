# main.py

import os
import sys
import platform
import tkinter as tk
from setup_manager import SetupManager

# Set mpv lib directory before importing video_annotator
current_dir = os.path.dirname(os.path.abspath(__file__))

if platform.system() == "Windows":
    lib_dir = os.path.join(current_dir, "lib/Windows")
elif platform.system() == "Darwin":
    lib_dir = os.path.join(current_dir, "lib/MacOS")
elif platform.system() == "Linux":
    lib_dir = os.path.join(current_dir, "lib/Linux")
os.environ["PATH"] = lib_dir + os.pathsep + current_dir + os.pathsep + os.environ["PATH"]

from video_annotator import VideoAnnotator

def main():
    # Create the hidden main root window
    root = tk.Tk()
    root.withdraw()

    # Create SetupManager and prompt for a video file
    setup_manager = SetupManager(root)
    setup_manager.select_video_file()

    if not setup_manager.video_path:
        print("No video selected. Exiting.")
        root.destroy()
        sys.exit(0)

    if setup_manager.root and setup_manager.root.winfo_exists():
        root.wait_window(setup_manager.root)

    if setup_manager.start_video_flag:
        video_path = setup_manager.video_path
        session_state_file = setup_manager.session_state_file
        behavior_file = setup_manager.behavior_key_file

        print(f"Video file selected: {video_path}")
        print(f"Using behavior file: {behavior_file}")

        # Do NOT call root.deiconify() here; let VideoAnnotator decide when to show the window.
        app = VideoAnnotator(root, video_path, session_state_file, behavior_file)
        app.pack(fill='both', expand=True)
        root.mainloop()
    else:
        print("Setup canceled. Exiting.")
        root.destroy()
        sys.exit(0)

if __name__ == '__main__':
    main()
