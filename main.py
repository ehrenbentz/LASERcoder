import sys
import tkinter as tk
from setup_manager import SetupManager
from video_annotator import VideoAnnotator

def main():
    # Create the main root window (hidden initially)
    root = tk.Tk()
    root.withdraw()

    # Create SetupManager and prompt for a video file.
    setup_manager = SetupManager(root)
    setup_manager.select_video_file()

    # If no video was selected, exit immediately.
    if not setup_manager.video_path:
        print("No video selected. Exiting.")
        root.destroy()
        sys.exit(0)

    # Ensure the `setup_manager.root` window exists before waiting for it
    if setup_manager.root and setup_manager.root.winfo_exists():
        root.wait_window(setup_manager.root)

    # If the user clicked "Start Video", launch VideoAnnotator passing the session state file.
    if setup_manager.start_video_flag:
        video_path = setup_manager.video_path
        session_state_file = setup_manager.session_state_file  # session state file path

        # Set the behavior file on the VideoAnnotator class.
        VideoAnnotator.behavior_file = setup_manager.behavior_key_file

        print(f"Video file selected: {video_path}")
        print(f"Using behavior file: {VideoAnnotator.behavior_file}")

        root.deiconify()  # Show the main root
        app = VideoAnnotator(root, video_path, session_state_file)
        app.pack(fill='both', expand=True)
        root.mainloop()
    else:
        print("Setup canceled. Exiting.")
        root.destroy()
        sys.exit(0)

if __name__ == '__main__':
    main()
