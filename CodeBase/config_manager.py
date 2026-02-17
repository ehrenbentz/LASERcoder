# config_manager.py

import os
import json
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QDir

class ConfigManager:
    """
    Manages LaserTAG configuration settings.

    """
    
    def __init__(self):
        """Initialize the configuration manager with default settings."""
        self.home_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        self.config_file = os.path.join(self.home_dir, '.lasertag.conf')
        self.config = None
        self.load_config()
        
    def load_config(self):
        """Load configuration from file or create with defaults if not exists."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.create_default_config()
        except Exception:
            self.config = self.create_default_config()
            
        self._validate_and_update_config()
        return self.config

    def _validate_and_update_config(self):
        """Validate configuration and ensure all required fields exist."""
        if not self.config.get('output_dir') or not os.path.exists(self.config['output_dir']):
            self.config['output_dir'] = self.home_dir
            
        if not self.config.get('video_dir') or not os.path.exists(self.config['video_dir']):
            self.config['video_dir'] = self.home_dir
            
        if 'last_behavior_key' not in self.config:
            self.config['last_behavior_key'] = None
            
        self.save_config()

    def create_default_config(self):
        """Create default configuration settings using home directory for compatibility."""
        return {
            'output_dir': self.home_dir,
            'video_dir': self.home_dir,
            'last_behavior_key': None
        }

    def save_config(self):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def get_output_dir(self):
        """Get the current output directory."""
        return self.config.get('output_dir', self.home_dir)

    def get_video_dir(self):
        """Get the current video directory."""
        return self.config.get('video_dir', self.home_dir)

    def get_last_behavior_key(self):
        """Get the last used behavior key file."""
        return self.config.get('last_behavior_key')

    def update_output_dir(self, new_dir):
        """Update the output directory if it exists."""
        if os.path.exists(new_dir):
            self.config['output_dir'] = new_dir
            self.save_config()

    def update_video_dir(self, video_path):
        """Update the video directory based on the selected video file."""
        video_dir = os.path.dirname(video_path)
        if os.path.exists(video_dir):
            self.config['video_dir'] = video_dir
            self.save_config()

    def update_last_behavior_key(self, behavior_key):
        """Update the last used behavior key file."""
        if behavior_key and isinstance(behavior_key, str):
            self.config['last_behavior_key'] = behavior_key
            self.save_config()
