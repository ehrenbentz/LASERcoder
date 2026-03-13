# config_manager.py

import os
import json
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QDir

DEFAULT_VIDEO_SETTINGS = {
    "brightness": 0, "contrast": 0, "gamma": 0,
    "saturation": 0, "hue": 0
}


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
            
        if 'last_event_key' not in self.config:
            self.config['last_event_key'] = None

        if self.config.get('theme') not in ('dark', 'light', 'system'):
            self.config['theme'] = 'system'

        if 'video_settings' not in self.config:
            self.config['video_settings'] = DEFAULT_VIDEO_SETTINGS.copy()

        self.save_config()

    def create_default_config(self):
        """Create default configuration settings using home directory for compatibility."""
        return {
            'output_dir': self.home_dir,
            'video_dir': self.home_dir,
            'last_event_key': None,
            'theme': 'system',
            'video_settings': DEFAULT_VIDEO_SETTINGS.copy(),
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

    def get_last_event_key(self):
        """Get the last used event key file."""
        return self.config.get('last_event_key')

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

    def update_last_event_key(self, event_key):
        """Update the last used event key file."""
        if event_key and isinstance(event_key, str):
            self.config['last_event_key'] = event_key
            self.save_config()

    def get_theme(self):
        """Get the current theme preference."""
        return self.config.get('theme', 'system')

    def update_theme(self, name):
        """Update the theme preference."""
        if name in ('dark', 'light', 'system'):
            self.config['theme'] = name
            self.save_config()

    def get_video_settings(self):
        """Get the global video display settings."""
        return self.config.get('video_settings', DEFAULT_VIDEO_SETTINGS.copy())

    def update_video_settings(self, settings):
        """Update and persist global video display settings."""
        self.config['video_settings'] = settings
        self.save_config()

    def get_show_floating_controls(self):
        """Get whether floating controls should be visible."""
        return self.config.get('show_floating_controls', True)

    def update_show_floating_controls(self, visible):
        """Update whether floating controls should be visible."""
        self.config['show_floating_controls'] = bool(visible)
        self.save_config()

    def get_show_video_controls_toggle(self):
        return self.config.get('show_video_controls_toggle', True)

    def set_show_video_controls_toggle(self, visible):
        self.config['show_video_controls_toggle'] = bool(visible)
        self.save_config()

    def get_show_events_toggle(self):
        return self.config.get('show_events_toggle', True)

    def set_show_events_toggle(self, visible):
        self.config['show_events_toggle'] = bool(visible)
        self.save_config()

    def get_show_zoom_button(self):
        return self.config.get('show_zoom_button', True)

    def set_show_zoom_button(self, visible):
        self.config['show_zoom_button'] = bool(visible)
        self.save_config()

    def get_backup_dirs(self):
        return self.config.get('backup_dirs', [])

    def add_backup_dir(self, path):
        dirs = self.config.get('backup_dirs', [])
        norm = os.path.normpath(path)
        if norm not in dirs:
            dirs.append(norm)
            self.config['backup_dirs'] = dirs
            self.save_config()

    def is_backup_dir(self, path):
        norm = os.path.normpath(path)
        return norm in self.config.get('backup_dirs', [])

    def get_state_highlight_color(self):
        return self.config.get('state_highlight_color', None)

    def set_state_highlight_color(self, hex_color):
        self.config['state_highlight_color'] = hex_color
        self.save_config()

    def get_point_highlight_color(self):
        return self.config.get('point_highlight_color', None)

    def set_point_highlight_color(self, hex_color):
        self.config['point_highlight_color'] = hex_color
        self.save_config()

    def get_point_button_color(self):
        return self.config.get('point_button_color', None)

    def set_point_button_color(self, hex_color):
        self.config['point_button_color'] = hex_color
        self.save_config()

    def get_state_button_color(self):
        return self.config.get('state_button_color', None)

    def set_state_button_color(self, hex_color):
        self.config['state_button_color'] = hex_color
        self.save_config()


_instance = None

def get_config():
    """Return the shared ConfigManager singleton."""
    global _instance
    if _instance is None:
        _instance = ConfigManager()
    return _instance
