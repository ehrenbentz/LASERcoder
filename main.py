import os
import sys
import platform
import tkinter as tk
from setup_manager import SetupManager
from config_manager import ConfigManager

# Add logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add the current directory to PATH
os.environ["PATH"] = os.path.dirname(__file__) + os.pathsep + os.environ["PATH"]

try:
    from video_annotator import VideoAnnotator
except ImportError as e:
    logger.error(f"Failed to import VideoAnnotator: {e}")
    sys.exit(1)

def main():
    logger.debug("Starting main function")
    
    try:
        # Create the hidden main root window
        logger.debug("Creating root window")
        root = tk.Tk()
        root.withdraw()
        
        # Initialize config manager
        logger.debug("Initializing ConfigManager")
        config_manager = ConfigManager()
        
        # Create SetupManager - it will automatically show the FilesManager dialog
        logger.debug("Creating SetupManager")
        setup_manager = SetupManager(root, config_manager)  # Pass config_manager here
        
        # Wait for the SetupManager to complete its work
        logger.debug("Waiting for SetupManager window")
        if setup_manager.root and setup_manager.root.winfo_exists():
            root.wait_window(setup_manager.root)
            
        # Check if setup was completed successfully
        if setup_manager.start_video_flag and setup_manager.video_path:
            logger.debug("Setup completed successfully")
            video_path = setup_manager.video_path
            session_state_file = setup_manager.session_state_file
            behavior_file = setup_manager.behavior_key_file
            output_dir = setup_manager.output_dir
            
            # Update configuration with the selected paths
            config_manager.update_output_dir(output_dir)
            config_manager.update_video_dir(video_path)
            
            logger.debug(f"Video file selected: {video_path}")
            logger.debug(f"Using behavior file: {behavior_file}")
            logger.debug(f"Output directory: {output_dir}")
            logger.debug(f"Session state file: {session_state_file}")
            
            # Initialize and start the VideoAnnotator
            logger.debug("Creating VideoAnnotator")
            app = VideoAnnotator(root, video_path, session_state_file, behavior_file, output_dir)
            app.pack(fill='both', expand=True)
            
            logger.debug("Showing main window")
            root.deiconify()  # Show the main window
            
            logger.debug("Starting mainloop")
            root.mainloop()
        else:
            logger.debug("Setup canceled or no video selected")
            root.destroy()
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()